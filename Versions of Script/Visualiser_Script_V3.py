import os
import subprocess
import random
import re
import shutil
import sys
import math
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QButtonGroup,
    QRadioButton,
    QFrame,
    QMessageBox,
    QGraphicsDropShadowEffect,
    QComboBox,
)
from PyQt5.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    QThread,
    pyqtSignal,
    QTimer,
)
from PyQt5.QtGui import (
    QFont,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QBrush,
    QPixmap,
)


MAX_WIDTH_FREE = 3840
MAX_WIDTH_STUDIO = 8000
MAX_WIDTH_AUTO = 32000

FPS_VALUES = [23.976, 24.0, 25.0, 29.97, 30.0, 48.0, 50.0, 59.94, 60.0]
FPS_LABELS = ["23.976", "24", "25", "29.97", "30", "48", "50", "59.94", "60"]


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def find_ffmpeg():
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    local = os.path.join(base_dir, ffmpeg_name)
    if os.path.isfile(local):
        return local
    try:
        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        cmd = ["where", "ffmpeg"] if sys.platform == "win32" else ["which", "ffmpeg"]
        r = subprocess.run(
            cmd, capture_output=True, text=True, check=True, creationflags=cf
        )
        return r.stdout.splitlines()[0].strip()
    except (subprocess.CalledProcessError, IndexError):
        return None


def create_safe_filename(filename):
    name = os.path.splitext(filename)[0]
    return re.sub(r"[ '\"&()]", "", name.replace(" ", "_"))


def get_audio_duration(file_path, ffmpeg_path):
    """Return audio duration in seconds, or None on failure."""
    cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    ffprobe_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), ffprobe_name)
    if not os.path.isfile(ffprobe_path):
        ffprobe_path = ffprobe_name

    try:
        r = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            check=True,
            creationflags=cf,
        )
        return float(r.stdout.strip())
    except Exception:
        pass

    try:
        r = subprocess.run(
            [ffmpeg_path, "-i", file_path],
            capture_output=True,
            text=True,
            creationflags=cf,
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass

    return None


def process_waveform_image(input_path, output_path, target_width):
    """Collapse waveform PNG to a 1-pixel-tall strip at target_width."""
    try:
        with Image.open(input_path) as img:
            img = img.convert("L")
            np_img = np.array(img)
            row_sums = np.sum(np_img, axis=1)
            non_empty = np.where(row_sums > np_img.shape[1] * 5)[0]
            if len(non_empty) == 0:
                Image.new("L", (target_width, 1), 0).save(output_path)
                return True
            waveform = np_img[non_empty[0] : non_empty[-1] + 1, :]
            if waveform.max() > waveform.min():
                norm = (
                    (waveform - waveform.min())
                    * 255.0
                    / (waveform.max() - waveform.min())
                ).astype(np.uint8)
            else:
                norm = waveform
            Image.fromarray(norm).resize(
                (target_width, 1), Image.Resampling.BILINEAR
            ).save(output_path)
            return True
    except Exception as e:
        print(f"process_waveform_image error: {e}")
        return False


def _generate_100band_filters():
    """
    100 bandpass filters, logarithmically spaced from 20 Hz to 20 kHz.
    Bandwidth per band = half the distance to adjacent center frequencies.
    """
    freqs = np.geomspace(20, 20000, 100)
    filters = []
    for i in range(100):
        f_int = max(1, int(round(freqs[i])))
        if i == 0:
            bw = freqs[1] - freqs[0]
        elif i == 99:
            bw = freqs[99] - freqs[98]
        else:
            bw = (freqs[i + 1] - freqs[i - 1]) / 2.0
        bw_int = max(1, int(round(bw)))
        filters.append(f"bandpass=f={f_int}:w={bw_int}")
    return filters


_100BAND_FILTERS = _generate_100band_filters()


def get_preset_config(preset_choice):
    """Return filter configuration dict for the selected preset."""
    return {
        "1": {
            "name": "Full Spectrum (1-band)",
            "bands": 1,
            "filters": [],
            "colors": ["white"],
            "scale": "sqrt",
        },
        "2": {
            "name": "3-band (Low/Mid/High)",
            "bands": 3,
            "filters": [
                "lowpass=f=250",
                "highpass=f=250,lowpass=f=4000",
                "highpass=f=4000",
            ],
            "colors": ["red", "green", "blue"],
            "scale": "sqrt",
        },
        "3": {
            "name": "10-band (Logarithmic)",
            "bands": 10,
            "filters": [
                "bandpass=f=20:w=20",
                "bandpass=f=50:w=30",
                "bandpass=f=120:w=50",
                "bandpass=f=300:w=80",
                "bandpass=f=700:w=150",
                "bandpass=f=1700:w=300",
                "bandpass=f=4000:w=600",
                "bandpass=f=9000:w=1200",
                "bandpass=f=15000:w=2000",
                "bandpass=f=20000:w=3000",
            ],
            "colors": ["white"] * 10,
            "scale": "sqrt",
        },
        "4": {
            "name": "25-band (High Resolution)",
            "bands": 25,
            "filters": [
                "bandpass=f=20:w=20",
                "bandpass=f=32:w=22",
                "bandpass=f=50:w=28",
                "bandpass=f=80:w=35",
                "bandpass=f=120:w=45",
                "bandpass=f=180:w=55",
                "bandpass=f=270:w=70",
                "bandpass=f=400:w=85",
                "bandpass=f=600:w=105",
                "bandpass=f=900:w=130",
                "bandpass=f=1300:w=160",
                "bandpass=f=2000:w=200",
                "bandpass=f=3000:w=250",
                "bandpass=f=4500:w=300",
                "bandpass=f=6800:w=370",
                "bandpass=f=10000:w=450",
                "bandpass=f=13000:w=530",
                "bandpass=f=16000:w=620",
                "bandpass=f=18000:w=710",
                "bandpass=f=19000:w=800",
                "bandpass=f=19500:w=900",
                "bandpass=f=19800:w=1000",
                "bandpass=f=19900:w=1100",
                "bandpass=f=19950:w=1200",
                "bandpass=f=20000:w=1300",
            ],
            "colors": ["white"] * 25,
            "scale": "sqrt",
        },
        "5": {
            "name": "100-band",
            "bands": 100,
            "filters": _100BAND_FILTERS,
            "colors": ["white"] * 100,
            "scale": "sqrt",
            "gamma": 0.75,
        },
    }.get(preset_choice)


class ModernButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Inter", 10, QFont.Bold))
        self.setMinimumHeight(45)
        self.normal_color = QColor(25, 162, 212)
        self.hover_color = QColor(80, 200, 255)
        self.progress_color = QColor(15, 100, 140)
        self.progress = 0
        self.is_processing = False
        self._build_shadow(15)
        self.update_style()

    def _build_shadow(self, blur):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur)
        shadow.setColor(QColor(25, 162, 212, 150))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

    def _animate_shadow(self, start, end):
        shadow = self.graphicsEffect()
        if shadow:
            anim = QPropertyAnimation(shadow, b"blurRadius")
            anim.setDuration(200)
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.start()

    def enterEvent(self, event):
        if not self.is_processing:
            self.update_style(self.hover_color)
            self._animate_shadow(15, 25)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_processing:
            self.update_style(self.normal_color)
            self._animate_shadow(25, 15)
        super().leaveEvent(event)

    def set_progress(self, value):
        self.progress = value
        self.is_processing = True
        self.update_style()

    def reset(self):
        self.progress = 0
        self.is_processing = False
        self.update_style()
        self.setText("Process Audio Files")

    def update_style(self, color=None):
        if color is None:
            color = self.normal_color
        if self.is_processing:
            p = self.progress / 100.0
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {color.name()}, stop:{p} {color.name()},
                        stop:{min(p+0.001,1.0)} {self.progress_color.name()},
                        stop:1 {self.progress_color.name()});
                    color:white; border:none; border-radius:8px;
                    padding:10px 20px; font-weight:bold;
                }}
            """
            )
            if self.progress < 100:
                self.setText(f"Processing: {self.progress}%")
        else:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 {color.lighter(120).name()}, stop:1 {color.name()});
                    color:white; border:none; border-radius:8px;
                    padding:10px 20px; font-weight:bold;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 {self.hover_color.lighter(120).name()},
                        stop:1 {self.hover_color.name()});
                }}
                QPushButton:pressed {{ background:{color.darker(120).name()}; }}
                QPushButton:disabled {{ background:#555555; color:#AAAAAA; }}
            """
            )


class ToggleSwitch(QWidget):
    """A sliding ON/OFF toggle switch (left = OFF, right = ON)."""

    toggled = pyqtSignal(bool)

    def isChecked(self):
        return self._checked

    def setChecked(self, val):
        self._checked = bool(val)
        self._anim_pos = 1.0 if self._checked else 0.0
        self.update()
        self.toggled.emit(self._checked)

    def setEnabled(self, val):
        super().setEnabled(val)
        self.update()

    def __init__(self, label="", parent=None):
        super().__init__(parent)
        self._label = label
        self._checked = False
        self._anim_pos = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"_switch_pos")
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        label_px = max(0, len(label) * 7)
        self.setFixedSize(52 + 8 + label_px + 4, 36)

    def _get_pos(self):
        return self._anim_pos

    def _set_pos(self, v):
        self._anim_pos = v
        self.update()

    _switch_pos = pyqtProperty(float, _get_pos, _set_pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._checked = not self._checked
            self._anim.stop()
            self._anim.setStartValue(self._anim_pos)
            self._anim.setEndValue(1.0 if self._checked else 0.0)
            self._anim.start()
            self.toggled.emit(self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        disabled = not self.isEnabled()
        TRACK_W, TRACK_H = 52, 26
        KNOB_D = 20
        track_x = 0
        track_y = (self.height() - TRACK_H) // 2

        if self._checked and not disabled:
            track_col = QColor(25, 162, 212)
        elif disabled:
            track_col = QColor(50, 50, 50)
        else:
            track_col = QColor(60, 60, 60)

        p.setBrush(QBrush(track_col))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(
            track_x, track_y, TRACK_W, TRACK_H, TRACK_H // 2, TRACK_H // 2
        )

        if not disabled:
            border_col = (
                QColor(25, 162, 212) if self._checked else QColor(100, 100, 100)
            )
        else:
            border_col = QColor(70, 70, 70)
        p.setBrush(Qt.NoBrush)
        pen_border = p.pen()
        from PyQt5.QtGui import QPen

        p.setPen(QPen(border_col, 1.5))
        p.drawRoundedRect(
            track_x, track_y, TRACK_W, TRACK_H, TRACK_H // 2, TRACK_H // 2
        )

        knob_travel = TRACK_W - TRACK_H
        knob_x = track_x + (TRACK_H - KNOB_D) // 2 + int(self._anim_pos * knob_travel)
        knob_y = track_y + (TRACK_H - KNOB_D) // 2

        if disabled:
            knob_col = QColor(90, 90, 90)
        elif self._checked:
            knob_col = QColor(255, 255, 255)
        else:
            knob_col = QColor(180, 180, 180)

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(knob_col))
        p.drawEllipse(knob_x, knob_y, KNOB_D, KNOB_D)

        if self._label:
            text_x = TRACK_W + 8
            if disabled:
                text_col = QColor(80, 80, 80)
            elif self._checked:
                text_col = QColor(255, 255, 255)
            else:
                text_col = QColor(136, 136, 136)
            p.setPen(text_col)
            p.setFont(QFont("Inter", 9, QFont.Bold))
            p.drawText(
                text_x,
                0,
                self.width() - text_x,
                self.height(),
                Qt.AlignVCenter | Qt.AlignLeft,
                self._label,
            )

        p.end()

    def sizeHint(self):
        from PyQt5.QtCore import QSize

        label_px = max(0, len(self._label) * 7)
        return QSize(52 + 8 + label_px + 4, 36)


class ModernRadioButton(QRadioButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Inter", 10))
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(25, 162, 212, 100))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        self.update_style()

    def update_style(self):
        self.setStyleSheet(
            f"""
            QRadioButton {{
                color:#FFFFFF; background-color:#282828;
                padding:12px 15px; border-radius:8px;
                font-weight:{'bold' if self.isChecked() else 'normal'};
            }}
            QRadioButton::indicator {{
                width:20px; height:20px; border-radius:10px;
                border:2px solid #B3B3B3;
            }}
            QRadioButton::indicator:checked {{
                background-color:#19a2d4; border:2px solid #19a2d4;
            }}
            QRadioButton:hover {{ background-color:#2a2a2a; color:#19a2d4; }}
            QRadioButton:checked {{ background-color:#2a2a2a; color:#19a2d4; }}
        """
        )

    def nextCheckState(self):
        super().nextCheckState()
        self.update_style()


class ModernComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Inter", 10))
        self.setMinimumHeight(40)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(25, 162, 212, 100))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        self.setStyleSheet(
            """
            QComboBox {
                background-color:#282828; color:#FFFFFF;
                border:2px solid #B3B3B3; border-radius:8px;
                padding:8px 15px; font-weight:normal;
            }
            QComboBox:hover { border-color:#19a2d4; color:#19a2d4; }
            QComboBox::drop-down { border:none; width:30px; }
            QComboBox::down-arrow {
                image:none;
                border-left:5px solid transparent;
                border-right:5px solid transparent;
                border-top:5px solid #B3B3B3;
                width:0px; height:0px;
            }
            QComboBox QAbstractItemView {
                background-color:#282828; color:#FFFFFF;
                border:2px solid #19a2d4; border-radius:8px;
                selection-background-color:#19a2d4; outline:none;
            }
            QComboBox QAbstractItemView::item {
                padding:8px 15px; border-bottom:1px solid #333333;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color:#19a2d4; color:#FFFFFF;
            }
        """
        )


class DropArea(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 140)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(25, 162, 212, 100))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        self.update_style()
        self.setText("Drop audio files here\nor click to browse")
        self.setAcceptDrops(True)

    def update_style(self, hover=False, active=False):
        if active:
            border = "#19a2d4"
            color = "#19a2d4"
            weight = "bold"
        elif hover:
            border = "#19a2d4"
            color = "#B3B3B3"
            weight = "normal"
        else:
            border = "#B3B3B3"
            color = "#B3B3B3"
            weight = "normal"
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #2a2a2a, stop:1 #282828);
                border:2px dashed {border}; border-radius:10px;
                color:{color}; font-size:14px; font-weight:{weight};
            }}
        """
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.update_style(False, True)

    def dragLeaveEvent(self, event):
        self.update_style()

    def dropEvent(self, event):
        self.update_style()
        if event.mimeData().hasUrls():
            paths = [
                u.toLocalFile()
                for u in event.mimeData().urls()
                if os.path.exists(u.toLocalFile())
            ]
            w = self.window()
            if hasattr(w, "handle_dropped_files"):
                w.handle_dropped_files(paths)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            w = self.window()
            if hasattr(w, "browse_for_files"):
                w.browse_for_files()


class ProcessingThread(QThread):
    progress_updated = pyqtSignal(int, str)
    processing_finished = pyqtSignal(bool, str)

    def __init__(
        self,
        audio_files,
        output_path,
        preset_choice,
        output_format,
        target_width,
        auto_length_fps,
        studio_mode,
        parent=None,
    ):
        super().__init__(parent)
        self.audio_files = audio_files
        self.output_path = output_path
        self.preset_choice = preset_choice
        self.output_format = output_format
        self.target_width = target_width
        self.auto_length_fps = auto_length_fps
        self.studio_mode = studio_mode
        self.is_running = True

    def run(self):
        try:
            n = len(self.audio_files)
            for i, fp in enumerate(self.audio_files):
                if not self.is_running:
                    break
                self.progress_updated.emit(
                    int(i / n * 100), f"Processing: {os.path.basename(fp)}"
                )
                if not self.process_audio_file(fp):
                    self.processing_finished.emit(
                        False, f"Failed to process: {os.path.basename(fp)}"
                    )
                    return
            self.processing_finished.emit(
                True, f"Processing completed! Files saved to: {self.output_path}"
            )
        except Exception as e:
            self.processing_finished.emit(False, f"Error: {e}")

    def stop(self):
        self.is_running = False

    def _resolve_width(self, file_path):
        """Compute output width, always capped by the licence limit."""
        max_w = MAX_WIDTH_STUDIO if self.studio_mode else MAX_WIDTH_FREE
        if self.auto_length_fps > 0:
            auto_cap = MAX_WIDTH_AUTO if self.studio_mode else MAX_WIDTH_FREE
            ffmpeg = find_ffmpeg()
            if ffmpeg:
                dur = get_audio_duration(file_path, ffmpeg)
                if dur:
                    return min(auto_cap, max(1, math.ceil(dur * self.auto_length_fps)))
        return min(self.target_width, max_w)

    def _cf(self):
        return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    def process_audio_file(self, file_path):
        original_dir = os.getcwd()
        try:
            os.chdir(self.output_path)

            config = get_preset_config(self.preset_choice)
            if not config:
                return False

            ffmpeg = find_ffmpeg()
            if not ffmpeg:
                self.progress_updated.emit(
                    0, "FFmpeg not found. Please install FFmpeg."
                )
                return False

            width = self._resolve_width(file_path)
            scale = config.get("scale", "sqrt")
            gamma = config.get("gamma", None)
            safe = create_safe_filename(os.path.basename(file_path))
            ext = self.get_format_extension()
            cf = self._cf()

            def apply_gamma(pil_img, g):
                """Apply gamma correction: pixels^(1/g) brightens when g>1, darkens when g<1."""
                if g is None or g == 1.0:
                    return pil_img
                mode = pil_img.mode
                arr = np.array(pil_img.convert("L"), dtype=np.float32) / 255.0
                arr = np.power(arr, 1.0 / g)
                arr = (arr * 255.0).clip(0, 255).astype(np.uint8)
                result = Image.fromarray(arr, "L")
                if mode == "RGB":
                    result = result.convert("RGB")
                return result

            def wavespic_filter(w, h, col):
                return f"showwavespic=s={w}x{h}:colors={col}:scale={scale}"

            if config["bands"] == 1:
                tmp = f"temp_waveforms_{random.randint(1000,9999)}"
                w_png = f"{tmp}/{safe}_waveform.png"
                r_png = f"{tmp}/{safe}_resized.png"
                out = f"{safe}_Waveform_1b.{ext}"
                os.makedirs(tmp, exist_ok=True)
                try:
                    subprocess.run(
                        [
                            ffmpeg,
                            "-i",
                            file_path,
                            "-filter_complex",
                            f"aformat=channel_layouts=mono,"
                            + wavespic_filter(width, 240, "white"),
                            "-frames:v",
                            "1",
                            "-y",
                            w_png,
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                        creationflags=cf,
                    )
                    if process_waveform_image(w_png, r_png, width):
                        with Image.open(r_png) as img:
                            stretched = (
                                apply_gamma(img, gamma)
                                .convert("RGB")
                                .resize((width, 10), Image.Resampling.NEAREST)
                            )
                            self.save_image_in_format(stretched, out)
                    else:
                        return False
                except subprocess.CalledProcessError:
                    return False
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                os.chdir(original_dir)
                return os.path.exists(out)

            n_bands = config["bands"]
            tmp = f"temp_waveforms_{random.randint(1000,9999)}"
            os.makedirs(tmp, exist_ok=True)

            fc = f"aformat=channel_layouts=mono,asplit={n_bands}"
            fc += "".join(f"[in{i}]" for i in range(1, n_bands + 1))
            fc += ";"
            fc += ";".join(
                f"[in{i}]{config['filters'][i-1]}[out{i}]"
                for i in range(1, n_bands + 1)
            )

            cmd = [ffmpeg, "-i", file_path, "-filter_complex", fc]
            for i in range(1, n_bands + 1):
                cmd += ["-map", f"[out{i}]", f"{tmp}/{safe}_band{i}.wav"]

            try:
                subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=cf,
                )
            except subprocess.CalledProcessError:
                shutil.rmtree(tmp, ignore_errors=True)
                os.chdir(original_dir)
                return False

            wh = 200
            imgs = []
            for band in range(1, n_bands + 1):
                bwav = f"{tmp}/{safe}_band{band}.wav"
                bpng = f"{tmp}/{safe}_waveform{band}.png"
                rpng = f"{tmp}/{safe}_resized{band}.png"
                col = config["colors"][band - 1]
                try:
                    subprocess.run(
                        [
                            ffmpeg,
                            "-i",
                            bwav,
                            "-filter_complex",
                            wavespic_filter(width, wh, col),
                            "-frames:v",
                            "1",
                            "-y",
                            bpng,
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                        creationflags=cf,
                    )
                except subprocess.CalledProcessError:
                    imgs.append(None)
                    continue
                imgs.append(rpng if process_waveform_image(bpng, rpng, width) else None)

            if any(p for p in imgs if p):
                if config["bands"] == 3:
                    final = Image.new("RGB", (width, n_bands))
                    for y, p in enumerate(imgs):
                        if p and os.path.exists(p):
                            with Image.open(p) as bi:
                                final.paste(bi.convert("RGB"), (0, y))
                    final = apply_gamma(final, gamma).resize(
                        (width, 10), Image.Resampling.NEAREST
                    )
                else:
                    final = Image.new("L", (width, n_bands))
                    for y, p in enumerate(imgs):
                        if p and os.path.exists(p):
                            with Image.open(p) as bi:
                                final.paste(bi.convert("L"), (0, y))
                    final = apply_gamma(final, gamma)

                out = f"{safe}_Waveform_{n_bands}b.{ext}"
                self.save_image_in_format(final, out)

            shutil.rmtree(tmp, ignore_errors=True)
            os.chdir(original_dir)
            return True

        except Exception as e:
            print(f"process_audio_file error: {e}")
            try:
                os.chdir(original_dir)
            except Exception:
                pass
            return False

    def get_format_extension(self):
        return {0: "png", 1: "png", 2: "jpg", 3: "jpg"}.get(self.output_format, "png")

    def save_image_in_format(self, image, path):
        try:
            if path.endswith(".png"):
                compress = 0 if self.output_format == 0 else 6
                image.save(path, "PNG", compress_level=compress)
            elif path.endswith(".jpg"):
                if image.mode != "RGB":
                    image = image.convert("RGB")
                quality = 95 if self.output_format == 2 else 30
                image.save(path, "JPEG", quality=quality, optimize=True)
        except Exception as e:
            print(f"save_image error: {e}")
            fallback = path.rsplit(".", 1)[0] + ".png"
            image.save(fallback, "PNG")


class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setAttribute(Qt.WA_TranslucentBackground)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 0, 10, 0)
        outer.setSpacing(0)

        try:
            ip = resource_path("Visualiser_Logo.png")
            if os.path.exists(ip):
                pix = QPixmap(ip).scaled(
                    22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                ico = QLabel(self)
                ico.setPixmap(pix)
                ico.setFixedSize(22, 22)
                ico.setStyleSheet("background:transparent;")
                ico.setAttribute(Qt.WA_TransparentForMouseEvents)
                outer.addWidget(ico)
                outer.addSpacing(8)
        except Exception:
            pass

        outer.addStretch()

        self._min_btn = QPushButton("–", self)
        self._min_btn.setFixedSize(28, 28)
        self._min_btn.setCursor(Qt.PointingHandCursor)
        self._min_btn.setStyleSheet(
            """
            QPushButton { background:#2a2a2a; color:#cccccc; border:none;
                          border-radius:6px; font-size:14px; font-weight:bold; }
            QPushButton:hover { background:#3a3a3a; color:white; }
        """
        )
        self._min_btn.clicked.connect(self._on_min)
        outer.addWidget(self._min_btn)

        outer.addSpacing(6)

        self._close_btn = QPushButton("✕", self)
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(
            """
            QPushButton { background:#2a2a2a; color:#cccccc; border:none;
                          border-radius:6px; font-size:11px; font-weight:bold; }
            QPushButton:hover { background:#c0392b; color:white; }
        """
        )
        self._close_btn.clicked.connect(self._on_close)
        outer.addWidget(self._close_btn)

        self._title = QLabel("Audio Visualiser Converter", self)
        self._title.setFont(QFont("Inter", 10, QFont.Bold))
        self._title.setStyleSheet("color:#1dbef9; background:transparent;")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setAttribute(Qt.WA_TranslucentBackground)
        self._title.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._title.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        self._title.setGeometry(0, 0, self.width(), self.height())
        self._title.raise_()
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        RADIUS = 12
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height() + RADIUS, RADIUS, RADIUS)
        p.fillPath(path, QBrush(QColor(0x0D, 0x0D, 0x0D)))
        p.end()

    def _on_min(self):
        self.window().showMinimized()

    def _on_close(self):
        self.window().close()


class DurationReaderThread(QThread):
    """Reads a single audio file's duration without blocking the UI."""

    duration_ready = pyqtSignal(float)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            dur = get_audio_duration(self.file_path, ffmpeg)
            if dur and dur > 0:
                self.duration_ready.emit(dur)


class AudioVisualizerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.audio_files = []
        self.output_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.preset_choice = "3"
        self.output_format = 1
        self.studio_mode = False
        self.auto_length_enabled = True
        self.processing_thread = None
        self.current_progress = 0
        self.animation_duration = 2000
        self._single_file_duration = None
        self._duration_thread = None

        self._drag_pos = None

        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._tick_progress)

        self._setup_ui()
        self._setup_styles()
        self._update_mode_info()

    def _setup_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(998, 589)

        try:
            ip = resource_path("Visualiser_Logo.png")
            if os.path.exists(ip):
                self.setWindowIcon(QIcon(ip))
        except Exception as e:
            print(f"Icon load error: {e}")

        class RoundedRoot(QWidget):
            RADIUS = 12

            def paintEvent(self, event):
                p = QPainter(self)
                p.setRenderHint(QPainter.Antialiasing)
                path = QPainterPath()
                path.addRoundedRect(
                    0, 0, self.width(), self.height(), self.RADIUS, self.RADIUS
                )
                p.setClipPath(path)
                p.fillPath(path, QBrush(QColor(0x12, 0x12, 0x12)))
                p.end()

        root = RoundedRoot()
        root.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        root_layout.addWidget(self.title_bar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color:#222222;")
        root_layout.addWidget(sep)

        content = QWidget()
        root_layout.addWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 16, 28, 16)
        layout.setSpacing(10)

        creator = QLabel(
            '<span style="color:white;">by </span>'
            '<a href="https://sh4rkk.com/shop" '
            'style="color:#6ed1ff;text-decoration:underline;">sh4rk</a>'
        )
        creator.setAlignment(Qt.AlignCenter)
        creator.setOpenExternalLinks(True)
        creator.setFont(QFont("Inter", 10))
        layout.addWidget(creator)

        studio_row = QHBoxLayout()
        studio_row.setSpacing(12)

        studio_lbl = QLabel("Licence Mode:")
        studio_lbl.setFont(QFont("Inter", 11, QFont.Bold))
        studio_lbl.setStyleSheet("color:#FFFFFF;")
        studio_row.addWidget(studio_lbl)

        self.studio_toggle = ToggleSwitch("DaVinci Resolve Studio")
        self.studio_toggle.setChecked(False)
        self.studio_toggle.toggled.connect(self._on_studio_toggled)
        studio_row.addWidget(self.studio_toggle)

        studio_row.addStretch()

        self.mode_info_label = QLabel("Free Mode  |  Fixed Width: 3,840 px")
        self.mode_info_label.setFont(QFont("Inter", 10))
        self.mode_info_label.setStyleSheet("color:#888888;")
        studio_row.addWidget(self.mode_info_label)

        layout.addLayout(studio_row)

        self.drop_area = DropArea(self)
        layout.addWidget(self.drop_area)

        out_row = QHBoxLayout()
        out_row.setSpacing(10)
        out_lbl = QLabel("Output Path:")
        out_lbl.setFont(QFont("Inter", 12, QFont.Bold))
        out_lbl.setStyleSheet("color:#FFFFFF; font-size:12px; font-weight:bold;")
        out_row.addWidget(out_lbl)
        self.output_path_label = QLabel(self.output_path)
        self.output_path_label.setStyleSheet(
            """
            QLabel {
                color:#B3B3B3; background-color:#282828;
                border-radius:5px; padding:8px; font-size:11px;
            }
        """
        )
        self.output_path_label.setMinimumHeight(30)
        self.output_path_label.setWordWrap(True)
        self.output_path_label.setMaximumHeight(50)
        out_row.addWidget(self.output_path_label, 1)
        self.browse_button = ModernButton("Browse")
        self.browse_button.clicked.connect(self.select_output_path)
        out_row.addWidget(self.browse_button)
        layout.addLayout(out_row)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(10)
        fmt_lbl = QLabel("Output Format:")
        fmt_lbl.setFont(QFont("Inter", 12, QFont.Bold))
        fmt_lbl.setStyleSheet("color:#FFFFFF; font-size:12px; font-weight:bold;")
        fmt_row.addWidget(fmt_lbl)
        self.format_combo = ModernComboBox()
        self.format_combo.addItems(
            [
                "PNG HQ - Lossless Compression - Highest Quality",
                "PNG - Standard Compression - Good Quality",
                "JPG - 95% Quality - Noisy, Fast",
                "JPG LQ - 30% Quality - Very Noisy, Fastest",
            ]
        )
        self.format_combo.setCurrentIndex(1)
        self.format_combo.currentIndexChanged.connect(
            lambda i: setattr(self, "output_format", i)
        )
        fmt_row.addWidget(self.format_combo, 1)
        layout.addLayout(fmt_row)

        auto_row = QHBoxLayout()
        auto_row.setSpacing(12)

        auto_lbl = QLabel("Width Mode:")
        auto_lbl.setFont(QFont("Inter", 11, QFont.Bold))
        auto_lbl.setStyleSheet("color:#FFFFFF;")
        auto_row.addWidget(auto_lbl)

        self.auto_toggle = ToggleSwitch("Auto Length")
        self.auto_toggle.setChecked(True)
        self.auto_toggle.toggled.connect(self._on_auto_toggled)
        auto_row.addWidget(self.auto_toggle)

        self.fps_label = QLabel("  Target FPS:")
        self.fps_label.setFont(QFont("Inter", 10, QFont.Bold))
        self.fps_label.setStyleSheet("color:#FFFFFF;")
        self.fps_label.setVisible(True)
        auto_row.addWidget(self.fps_label)

        self.fps_combo = ModernComboBox()
        self.fps_combo.addItems(FPS_LABELS)
        self.fps_combo.setCurrentIndex(1)
        self.fps_combo.setFixedWidth(95)
        self.fps_combo.setVisible(True)
        self.fps_combo.currentIndexChanged.connect(self._update_mode_info)
        auto_row.addWidget(self.fps_combo)

        fps_unit = QLabel("fps")
        fps_unit.setFont(QFont("Inter", 10))
        fps_unit.setStyleSheet("color:#888888;")
        fps_unit.setVisible(True)
        self.fps_unit_label = fps_unit
        auto_row.addWidget(fps_unit)

        auto_row.addStretch()

        self.auto_hint = QLabel("")
        self.auto_hint.setFont(QFont("Inter", 9))
        self.auto_hint.setStyleSheet("color:#7a9ab5;")
        auto_row.addWidget(self.auto_hint)

        layout.addLayout(auto_row)

        preset_lbl = QLabel("Select Mode:")
        preset_lbl.setFont(QFont("Inter", 13, QFont.Bold))
        preset_lbl.setStyleSheet("color:#FFFFFF; font-size:13px; font-weight:bold;")
        layout.addWidget(preset_lbl)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)

        self.preset_1 = ModernRadioButton("1-band")
        self.preset_2 = ModernRadioButton("3-band")
        self.preset_3 = ModernRadioButton("10-band")
        self.preset_4 = ModernRadioButton("25-band")
        self.preset_5 = ModernRadioButton("100-band")

        self.preset_group = QButtonGroup(self)
        for idx, btn in enumerate(
            [self.preset_1, self.preset_2, self.preset_3, self.preset_4, self.preset_5],
            start=1,
        ):
            self.preset_group.addButton(btn, idx)
            preset_row.addWidget(btn)

        self.preset_3.setChecked(True)
        self.preset_group.buttonClicked.connect(self._update_radio_styles)
        layout.addLayout(preset_row)

        self.process_button = ModernButton("Process Audio Files")
        self.process_button.clicked.connect(self.process_files)
        self.process_button.setEnabled(False)
        layout.addWidget(self.process_button)

        layout.addStretch(1)

    def _is_interactive(self, widget):
        """Return True if widget is a button, combo, or toggle that should NOT drag."""
        interactive_types = (
            QPushButton,
            QComboBox,
            ToggleSwitch,
            DropArea,
            QRadioButton,
        )
        w = widget
        while w is not None:
            if isinstance(w, interactive_types):
                return True
            w = w.parent()
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if child is None or not self._is_interactive(child):
                self._drag_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            delta = event.globalPos() - self._drag_pos
            self._drag_pos = event.globalPos()
            self.move(self.pos() + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _setup_styles(self):
        self.setStyleSheet(
            """
            QMainWindow { background:transparent; }
            QWidget#qt_central_widget { background:transparent; }
        """
        )

    def _on_studio_toggled(self, checked):
        self.studio_mode = checked
        self._update_mode_info()

    def _on_auto_toggled(self, checked):
        self.auto_length_enabled = checked
        self.fps_label.setVisible(checked)
        self.fps_combo.setVisible(checked)
        self.fps_unit_label.setVisible(checked)
        self._update_mode_info()

    def _update_mode_info(self):
        mode_str = "Studio" if self.studio_mode else "Free"
        if self.auto_length_enabled:
            cap_w = MAX_WIDTH_AUTO if self.studio_mode else MAX_WIDTH_FREE
            fps = FPS_VALUES[self.fps_combo.currentIndex()]
            px_per_min = int(60 * fps)

            max_secs = cap_w / fps
            max_total_s = int(max_secs)
            max_m = max_total_s // 60
            max_s = max_total_s % 60
            if max_m > 0:
                max_str = f"{max_m}m {max_s:02d}s"
            else:
                max_str = f"{max_total_s}s"

            self.mode_info_label.setText(
                f"{mode_str} Mode  |  Auto Length @ {fps} fps  |  Cap: {cap_w:,} px"
            )

            if len(self.audio_files) == 1 and self._single_file_duration is not None:
                dur_s = self._single_file_duration
                dur_mins = dur_s / 60
                px_out = min(cap_w, max(1, math.ceil(dur_s * fps)))
                total_s = int(dur_s)
                m_part = total_s // 60
                s_part = total_s % 60
                if m_part > 0:
                    dur_str = f"{m_part}m {s_part:02d}s"
                else:
                    dur_str = f"{s_part}s"
                self.auto_hint.setText(f"{dur_str} = {px_out:,} px  |  Max = {max_str}")
            else:
                self.auto_hint.setText(
                    f"Max Audio Length = {max_str}  |  1 min audio = {px_per_min:,} pixels"
                )
        else:
            fixed_w = MAX_WIDTH_STUDIO if self.studio_mode else MAX_WIDTH_FREE
            self.mode_info_label.setText(
                f"{mode_str} Mode  |  Fixed Width: {fixed_w:,} px"
            )
            self.auto_hint.setText("")

    def select_output_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.output_path
        )
        if path:
            self.output_path = path
            self.output_path_label.setText(path)

    def browse_for_files(self):
        try:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Audio Files",
                "",
                "Audio Files (*.mp3 *.flac *.ogg *.wav *.m4a)",
            )
            if files:
                self.handle_dropped_files(files)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to browse files: {e}")

    def handle_dropped_files(self, file_paths):
        try:
            exts = (".mp3", ".flac", ".ogg", ".wav", ".m4a")
            valid = [f for f in file_paths if f.lower().endswith(exts)]
            if not valid:
                self.drop_area.setText(
                    "No valid audio files found.\nDrop audio files here\nor click to browse"
                )
                self.process_button.setEnabled(False)
                return
            for f in valid:
                if f not in self.audio_files:
                    self.audio_files.append(f)
            if self.audio_files:
                dirs = set(os.path.dirname(f) for f in self.audio_files)
                self.output_path = (
                    list(dirs)[0]
                    if len(dirs) == 1
                    else os.path.join(os.path.expanduser("~"), "Downloads")
                )
                self.output_path_label.setText(self.output_path)
                names = [os.path.basename(f) for f in self.audio_files]
                if len(names) <= 3:
                    txt = f"{len(self.audio_files)} file(s) selected:\n" + "\n".join(
                        names
                    )
                else:
                    txt = (
                        f"{len(self.audio_files)} file(s) selected:\n"
                        + "\n".join(names[:3])
                        + f"\n+{len(names)-3} more"
                    )
                self.drop_area.setText(txt)
                self.process_button.setEnabled(True)
            else:
                self.drop_area.setText("Drop audio files here\nor click to browse")
                self.process_button.setEnabled(False)

            self._refresh_duration_hint()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process dropped files: {e}")
            self.drop_area.setText("Drop audio files here\nor click to browse")

    def _refresh_duration_hint(self):
        """Start a background duration read if exactly 1 file, else update hint directly."""
        if self._duration_thread and self._duration_thread.isRunning():
            self._duration_thread.terminate()
            self._duration_thread = None

        if len(self.audio_files) == 1:
            self._single_file_duration = None
            self.auto_hint.setText("Reading duration…")
            self._duration_thread = DurationReaderThread(self.audio_files[0])
            self._duration_thread.duration_ready.connect(self._on_duration_ready)
            self._duration_thread.finished.connect(
                lambda: (
                    self._update_mode_info()
                    if self._single_file_duration is None
                    else None
                )
            )
            self._duration_thread.start()
        else:
            self._single_file_duration = None
            self._update_mode_info()

    def _on_duration_ready(self, seconds):
        self._single_file_duration = seconds
        self._update_mode_info()

    def _all_presets(self):
        return [
            self.preset_1,
            self.preset_2,
            self.preset_3,
            self.preset_4,
            self.preset_5,
        ]

    def _update_radio_styles(self):
        for btn in self._all_presets():
            btn.update_style()

    def process_files(self):
        if not self.audio_files:
            return

        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            QMessageBox.critical(
                self,
                "Error",
                "FFmpeg not found. Please install FFmpeg and ensure it is in your PATH "
                "or in the same directory as this application.",
            )
            return

        btn = self.preset_group.checkedButton()
        preset_map = {
            self.preset_1: ("1", 900),
            self.preset_2: ("2", 1850),
            self.preset_3: ("3", 2000),
            self.preset_4: ("4", 4500),
            self.preset_5: ("5", 20000),
        }
        self.preset_choice, base_dur = preset_map.get(btn, ("3", 2000))
        if self.output_format == 0:
            base_dur += 200
        self.animation_duration = base_dur * len(self.audio_files)

        max_w = (
            MAX_WIDTH_AUTO
            if self.auto_length_enabled
            else (MAX_WIDTH_STUDIO if self.studio_mode else MAX_WIDTH_FREE)
        )
        auto_fps = (
            FPS_VALUES[self.fps_combo.currentIndex()]
            if self.auto_length_enabled
            else 0.0
        )

        for b in self._all_presets():
            b.setEnabled(False)
        self.drop_area.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.studio_toggle.setEnabled(False)
        self.auto_toggle.setEnabled(False)
        self.fps_combo.setEnabled(False)
        self.process_button.setEnabled(False)
        self.process_button.set_progress(0)

        self.current_progress = 0
        interval = max(10, int(self.animation_duration / 90))
        self.progress_timer.start(interval)

        self.processing_thread = ProcessingThread(
            self.audio_files,
            self.output_path,
            self.preset_choice,
            self.output_format,
            max_w,
            auto_fps,
            self.studio_mode,
        )
        self.processing_thread.progress_updated.connect(self._on_progress)
        self.processing_thread.processing_finished.connect(self._on_finished)
        self.processing_thread.start()

    def _tick_progress(self):
        if self.current_progress < 90:
            self.current_progress += 1
            self.process_button.set_progress(self.current_progress)
        else:
            self.progress_timer.stop()

    def _on_progress(self, value, message):
        pass

    def _on_finished(self, success, message):
        self.progress_timer.stop()
        if success:
            self._animate_to_100()
            QTimer.singleShot(600, self._reset_button)
        else:
            self._reset_button()
            QMessageBox.critical(self, "Error", message)
        self._enable_controls()

    def _animate_to_100(self):
        self._final_anim = QPropertyAnimation(self, b"_final_prog_prop")
        self._final_anim.setDuration(500)
        self._final_anim.setStartValue(self.current_progress)
        self._final_anim.setEndValue(100)
        self._final_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._final_anim.valueChanged.connect(self.process_button.set_progress)
        self._final_anim.start()

    def _get_fp(self):
        return self.current_progress

    def _set_fp(self, v):
        self.current_progress = v

    _final_prog_prop = pyqtProperty(int, _get_fp, _set_fp)

    def _reset_button(self):
        self.process_button.reset()

    def _enable_controls(self):
        for b in self._all_presets():
            b.setEnabled(True)
        self.drop_area.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.studio_toggle.setEnabled(True)
        self.auto_toggle.setEnabled(True)
        self.fps_combo.setEnabled(True)
        self.process_button.setEnabled(True)

    def closeEvent(self, event):
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.processing_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Inter", 10))
    app.setStyle("Fusion")
    window = AudioVisualizerGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

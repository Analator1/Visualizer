import os
import subprocess
import random
import re
import shutil
import sys
import numpy as np
from PIL import Image
from tqdm import tqdm
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QProgressBar, QButtonGroup,
                             QRadioButton, QFrame, QSizePolicy, QMessageBox, QGraphicsDropShadowEffect, QComboBox)
from PyQt5.QtCore import (Qt, QSize, QPropertyAnimation, QEasingCurve, QPoint, 
                          pyqtProperty, QThread, pyqtSignal, QTimer, QUrl)
from PyQt5.QtGui import (QFont, QPalette, QColor, QRadialGradient, QPainter, QIcon,
                         QPainterPath, QBrush, QLinearGradient, QDesktopServices, QPixmap)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

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
        self.update_style()
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(25, 162, 212, 150))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        
    def enterEvent(self, event):
        if not self.is_processing:
            self.update_style(self.hover_color)
            shadow = self.graphicsEffect()
            if shadow:
                anim = QPropertyAnimation(shadow, b"blurRadius")
                anim.setDuration(200)
                anim.setStartValue(15)
                anim.setEndValue(25)
                anim.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if not self.is_processing:
            self.update_style(self.normal_color)
            shadow = self.graphicsEffect()
            if shadow:
                anim = QPropertyAnimation(shadow, b"blurRadius")
                anim.setDuration(200)
                anim.setStartValue(25)
                anim.setEndValue(15)
                anim.start()
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
            progress_percent = self.progress / 100.0
            
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 {color.name()}, stop: {progress_percent} {color.name()},
                        stop: {progress_percent + 0.001} {self.progress_color.name()}, stop: 1 {self.progress_color.name()});
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-weight: bold;
                }}
            """)
            
            if self.progress < 100:
                self.setText(f"Processing: {self.progress}%")
        else:
            gradient = QLinearGradient(0, 0, 0, self.height())
            gradient.setColorAt(0, color.lighter(120))
            gradient.setColorAt(1, color)
            
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 {color.lighter(120).name()}, stop: 1 {color.name()});
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 {self.hover_color.lighter(120).name()}, stop: 1 {self.hover_color.name()});
                }}
                QPushButton:pressed {{
                    background: {color.darker(120).name()};
                }}
                QPushButton:disabled {{
                    background: #555555;
                    color: #AAAAAA;
                }}
            """)

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
        self.setStyleSheet(f"""
            QRadioButton {{
                color: #FFFFFF;
                background-color: #282828;
                padding: 12px 15px;
                border-radius: 8px;
                font-weight: {'bold' if self.isChecked() else 'normal'};
            }}
            QRadioButton::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid #B3B3B3;
            }}
            QRadioButton::indicator:checked {{
                background-color: #19a2d4;
                border: 2px solid #19a2d4;
            }}
            QRadioButton:hover {{
                background-color: #2a2a2a;
                color: #19a2d4;
            }}
            QRadioButton:checked {{
                background-color: #2a2a2a;
                color: #19a2d4;
            }}
        """)
        
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
        
        self.update_style()
        
    def update_style(self):
        self.setStyleSheet("""
            QComboBox {
                background-color: #282828;
                color: #FFFFFF;
                border: 2px solid #B3B3B3;
                border-radius: 8px;
                padding: 8px 15px;
                font-weight: normal;
            }
            QComboBox:hover {
                border-color: #19a2d4;
                color: #19a2d4;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #B3B3B3;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #282828;
                color: #FFFFFF;
                border: 2px solid #19a2d4;
                border-radius: 8px;
                selection-background-color: #19a2d4;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 15px;
                border-bottom: 1px solid #333333;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #19a2d4;
                color: #FFFFFF;
            }
        """)

class DropArea(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 200)
        
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
            self.setStyleSheet("""
                QLabel {
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #2a2a2a, stop: 1 #282828);
                    border: 2px dashed #19a2d4;
                    border-radius: 10px;
                    color: #19a2d4;
                    font-size: 14px;
                    font-weight: bold;
                }
            """)
        elif hover:
            self.setStyleSheet("""
                QLabel {
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #2a2a2a, stop: 1 #282828);
                    border: 2px dashed #19a2d4;
                    border-radius: 10px;
                    color: #B3B3B3;
                    font-size: 14px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #2a2a2a, stop: 1 #282828);
                    border: 2px dashed #B3B3B3;
                    border-radius: 10px;
                    color: #B3B3B3;
                    font-size: 14px;
                }
            """)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.update_style(False, True)
            
    def dragLeaveEvent(self, event):
        self.update_style()
        
    def dropEvent(self, event):
        self.update_style()
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            file_paths = []
            for url in urls:
                file_path = url.toLocalFile()
                if os.path.exists(file_path):
                    file_paths.append(file_path)
            
            main_window = self.window()
            if hasattr(main_window, 'handle_dropped_files'):
                main_window.handle_dropped_files(file_paths)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            main_window = self.window()
            if hasattr(main_window, 'browse_for_files'):
                main_window.browse_for_files()

class ProcessingThread(QThread):
    progress_updated = pyqtSignal(int, str)
    processing_finished = pyqtSignal(bool, str)
    
    def __init__(self, audio_files, output_path, preset_choice, output_format, parent=None):
        super().__init__(parent)
        self.audio_files = audio_files
        self.output_path = output_path
        self.preset_choice = preset_choice
        self.output_format = output_format
        self.is_running = True
        
    def run(self):
        try:
            total_files = len(self.audio_files)
            for i, file_path in enumerate(self.audio_files):
                if not self.is_running:
                    break
                    
                file_name = os.path.basename(file_path)
                progress_percent = int((i / total_files) * 100)
                self.progress_updated.emit(progress_percent, f"Processing: {file_name}")
                
                success = self.process_audio_file(file_path)
                if not success:
                    self.processing_finished.emit(False, f"Failed to process: {file_name}")
                    return
                
            self.processing_finished.emit(True, f"Processing completed! Files saved to: {self.output_path}")
        except Exception as e:
            self.processing_finished.emit(False, f"Error: {str(e)}")
            
    def stop(self):
        self.is_running = False
        
    def process_audio_file(self, file_path):
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        try:
            original_dir = os.getcwd()
            os.chdir(self.output_path)
            
            config = get_preset_config(self.preset_choice)
            if not config:
                return False
                
            ffmpeg_path = find_ffmpeg()
            if not ffmpeg_path:
                self.progress_updated.emit(0, "FFmpeg not found. Please install FFmpeg.")
                return False
                
            file_name = os.path.basename(file_path)
            safe_name = create_safe_filename(file_name)
            
            if config['bands'] == 1:
                temp_folder = f"temp_waveforms_{random.randint(1000, 9999)}"
                os.makedirs(temp_folder, exist_ok=True)
                
                waveform_png = f"{temp_folder}/{safe_name}_waveform.png"
                resized_png = f"{temp_folder}/{safe_name}_resized.png"
                
                format_ext = self.get_format_extension()
                output_file = f"{safe_name}_Waveform_1b.{format_ext}"
                
                try:
                    subprocess.run(
                        [ffmpeg_path, "-i", file_path, "-filter_complex", 
                         "aformat=channel_layouts=mono,showwavespic=s=3840x240:colors=white:scale=sqrt", 
                         "-frames:v", "1", "-y", waveform_png],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                        creationflags=creation_flags
                    )
                    
                    if process_waveform_image(waveform_png, resized_png, 3840):
                        with Image.open(resized_png) as img:
                            rgb_img = img.convert('RGB')
                            stretched_img = rgb_img.resize((3840, 10), Image.Resampling.NEAREST)
                            
                            self.save_image_in_format(stretched_img, output_file)
                    else:
                        return False
                        
                except subprocess.CalledProcessError:
                    return False
                finally:
                    for f in os.listdir(temp_folder):
                        if f.startswith(f"{safe_name}_"):
                            try:
                                os.remove(os.path.join(temp_folder, f))
                            except OSError:
                                pass
                    shutil.rmtree(temp_folder, ignore_errors=True)
                    
                return os.path.exists(output_file)
            
            temp_folder = f"temp_waveforms_{random.randint(1000, 9999)}"
            os.makedirs(temp_folder, exist_ok=True)
            
            filter_complex = "aformat=channel_layouts=mono"
            
            if config['bands'] > 1:
                filter_complex += f",asplit={config['bands']}"
                for i in range(1, config['bands'] + 1):
                    filter_complex += f"[in{i}]"
                filter_complex += ";" 
                
                for i in range(1, config['bands'] + 1):
                    filter_complex += f"[in{i}]{config['filters'][i-1]}[out{i}];"
            
            cmd = [ffmpeg_path, "-i", file_path, "-filter_complex", filter_complex.rstrip(';')]
            
            for i in range(1, config['bands'] + 1):
                cmd.extend(["-map", f"[out{i}]", f"{temp_folder}/{safe_name}_band{i}.wav"])
            
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags
                )
            except subprocess.CalledProcessError:
                return False
            
            resized_images = []
            width = 3840
            waveform_height = 200
            
            for band in range(1, config['bands'] + 1):
                input_wav = f"{temp_folder}/{safe_name}_band{band}.wav"
                waveform_png = f"{temp_folder}/{safe_name}_waveform{band}.png"
                resized_png = f"{temp_folder}/{safe_name}_resized{band}.png"
                
                color = config['colors'][band-1]
                try:
                    subprocess.run(
                        [ffmpeg_path, "-i", input_wav, "-filter_complex",
                         f"showwavespic=s={width}x{waveform_height}:colors={color}:scale=sqrt",
                         "-frames:v", "1", "-y", waveform_png],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                        creationflags=creation_flags
                    )
                except subprocess.CalledProcessError:
                    resized_images.append(None)
                    continue
                
                if process_waveform_image(waveform_png, resized_png, width):
                    resized_images.append(resized_png)
                else:
                    resized_images.append(None)
            
            if any(resized_images):
                if config['bands'] == 3:
                    final_image = Image.new('RGB', (width, config['bands']))
                    for y, img_path in enumerate(resized_images):
                        if img_path and os.path.exists(img_path):
                            try:
                                with Image.open(img_path) as band_img:
                                    band_img = band_img.convert('RGB')
                                    final_image.paste(band_img, (0, y))
                            except Exception:
                                pass
                    final_image = final_image.resize((width, 10), Image.Resampling.NEAREST)
                else:
                    final_image = Image.new('L', (width, config['bands']))
                    for y, img_path in enumerate(resized_images):
                        if img_path and os.path.exists(img_path):
                            try:
                                with Image.open(img_path) as band_img:
                                    band_img = band_img.convert('L')
                                    final_image.paste(band_img, (0, y))
                            except Exception:
                                pass
                
                format_ext = self.get_format_extension()
                output_file = f"{safe_name}_Waveform_{config['bands']}b.{format_ext}"
                
                self.save_image_in_format(final_image, output_file)
            
            for f in os.listdir(temp_folder):
                if f.startswith(f"{safe_name}_"):
                    try:
                        os.remove(os.path.join(temp_folder, f))
                    except OSError:
                        pass
            
            shutil.rmtree(temp_folder, ignore_errors=True)
            
            os.chdir(original_dir)
            
            return True
            
        except Exception as e:
            print(f"Error in process_audio_file: {e}")
            try:
                os.chdir(original_dir)
            except:
                pass
            return False
    
    def get_format_extension(self):
        """Get file extension based on selected format"""
        format_map = {
            0: "png",
            1: "png",
            2: "jpg",
            3: "jpg",
        }
        return format_map.get(self.output_format, "png")
    
    def save_image_in_format(self, image, output_path):
        """Save image in the selected format with appropriate settings"""
        try:
            if output_path.endswith('.png'):
                if self.output_format == 0:
                    image.save(output_path, format='PNG', compress_level=0)
                else:
                    image.save(output_path, format='PNG', compress_level=6)
                    
            elif output_path.endswith('.jpg'):
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                    
                if self.output_format == 2:
                    image.save(output_path, format='JPEG', quality=95, optimize=True)
                else:
                    image.save(output_path, format='JPEG', quality=30, optimize=True)
                    
        except Exception as e:
            print(f"Error saving image in format: {e}")
            fallback_path = output_path.split('.')[0] + '.png'
            image.save(fallback_path, format='PNG')

class AudioVisualizerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.audio_files = []
        self.output_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.preset_choice = '3'
        self.output_format = 1
        self.processing_thread = None
        self.progress_animation = None
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress_animation)
        
        self.setup_ui()
        self.setup_styles()
        
    def setup_ui(self):
        self.setWindowTitle("Audio Visualiser Converter")
        self.setFixedSize(1000, 670)
        try:
            icon_path = resource_path("Visualiser_Logo.png")

            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon.fromTheme("finance", QIcon(icon_path)))
            else:
                print(f"Error: Window icon file not found at {icon_path}")

        except Exception as e:
            print(f"Could not load window icon: {e}.")
            if 'icon_path' in locals():
                print(f"Attempted path: {icon_path}")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        title_label = QLabel("Audio Visualiser Converter")
        title_label.setAlignment(Qt.AlignCenter)
        
        title_label.setStyleSheet("""
            QLabel {
                color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #1dbef9, stop: 1 #1bb1e7);
                font-size: 28px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        title_label.setFont(QFont("Inter", 28, QFont.Bold))
        main_layout.addWidget(title_label)
        
        creator_label = QLabel(
            '<span style="color: white;">by </span>'
            '<a href="https://sh4rkk.com/shop" style="color:#6ed1ff; text-decoration: underline;">sh4rk</a>'
        )
        creator_label.setAlignment(Qt.AlignCenter)
        creator_label.setOpenExternalLinks(True)
        creator_label.setFont(QFont("Inter", 12))
        main_layout.addWidget(creator_label)

        self.drop_area = DropArea(self)
        main_layout.addWidget(self.drop_area)
        
        output_layout = QHBoxLayout()
        output_layout.setSpacing(10)
        
        output_label = QLabel("Output Path:")
        output_label.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
        output_label.setFont(QFont("Inter", 12, QFont.Bold))
        output_layout.addWidget(output_label)
        
        self.output_path_label = QLabel(self.output_path)
        self.output_path_label.setStyleSheet("""
            QLabel {
                color: #B3B3B3;
                background-color: #282828;
                border-radius: 5px;
                padding: 8px;
                font-size: 11px;
            }
        """)
        self.output_path_label.setMinimumHeight(30)
        self.output_path_label.setWordWrap(True)
        self.output_path_label.setMaximumHeight(50)
        output_layout.addWidget(self.output_path_label, 1)
        
        self.browse_button = ModernButton("Browse")
        self.browse_button.clicked.connect(self.select_output_path)
        output_layout.addWidget(self.browse_button)
        
        main_layout.addLayout(output_layout)
        
        format_layout = QHBoxLayout()
        format_layout.setSpacing(10)
        
        format_label = QLabel("Output Format:")
        format_label.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
        format_label.setFont(QFont("Inter", 12, QFont.Bold))
        format_layout.addWidget(format_label)
        
        self.format_combo = ModernComboBox()
        formats = [
            "PNG HQ - Lossless Compression - Highest Quality",
            "PNG - Standard Compression - Good Quality", 
            "JPG - 95% Quality - Noisy, Fast",
            "JPG LQ - 30% Quality - Very Noisy, Fastest"
        ]
        self.format_combo.addItems(formats)
        self.format_combo.setCurrentIndex(1)
        self.format_combo.currentIndexChanged.connect(self.format_changed)
        format_layout.addWidget(self.format_combo, 1)
        
        main_layout.addLayout(format_layout)
        
        preset_label = QLabel("Select Mode:")
        preset_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        preset_label.setFont(QFont("Inter", 14, QFont.Bold))
        main_layout.addWidget(preset_label)
        
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(15)
        
        self.preset_1 = ModernRadioButton("1-band")
        self.preset_2 = ModernRadioButton("3-band")
        self.preset_3 = ModernRadioButton("10-band (Recommended)")
        self.preset_4 = ModernRadioButton("25-band")
        
        self.preset_group = QButtonGroup(self)
        self.preset_group.addButton(self.preset_1, 1)
        self.preset_group.addButton(self.preset_2, 2)
        self.preset_group.addButton(self.preset_3, 3)
        self.preset_group.addButton(self.preset_4, 4)
        
        self.preset_3.setChecked(True)
        
        preset_layout.addWidget(self.preset_1)
        preset_layout.addWidget(self.preset_2)
        preset_layout.addWidget(self.preset_3)
        preset_layout.addWidget(self.preset_4)
        
        main_layout.addLayout(preset_layout)
        
        self.process_button = ModernButton("Process Audio Files")
        self.process_button.clicked.connect(self.process_files)
        self.process_button.setEnabled(False)
        main_layout.addWidget(self.process_button)
        
        main_layout.addStretch(1)
        
        for btn in [self.preset_1, self.preset_2, self.preset_3, self.preset_4]:
            self.preset_group.buttonClicked.connect(self.update_radio_styles)
        
    def setup_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: #121212;
            }}
            QWidget {{
                background-color: #121212;
            }}
        """)
        
    def format_changed(self, index):
        self.output_format = index
        
    def update_radio_styles(self):
        for btn in [self.preset_1, self.preset_2, self.preset_3, self.preset_4]:
            btn.update_style()
        
    def select_output_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_path)
        if path:
            self.output_path = path
            self.output_path_label.setText(path)
            
    def browse_for_files(self):
        try:
            files, _ = QFileDialog.getOpenFileNames(
                self, 
                "Select Audio Files", 
                "", 
                "Audio Files (*.mp3 *.flac *.ogg *.wav *.m4a)"
            )
            if files:
                self.handle_dropped_files(files)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to browse files: {str(e)}")
            
    def handle_dropped_files(self, file_paths):
        try:
            extensions = ('.mp3', '.flac', '.ogg', '.wav', '.m4a')
            valid_files = [f for f in file_paths if f.lower().endswith(extensions)]
            
            if not valid_files:
                self.drop_area.setText("No valid audio files found.\nDrop audio files here\nor click to browse")
                self.process_button.setEnabled(False)
                return
                
            for file_path in valid_files:
                if file_path not in self.audio_files:
                    self.audio_files.append(file_path)
            
            if self.audio_files:
                file_dirs = set(os.path.dirname(f) for f in self.audio_files)
                
                if len(file_dirs) == 1:
                    self.output_path = list(file_dirs)[0]
                else:
                    self.output_path = os.path.join(os.path.expanduser("~"), "Downloads")
                
                self.output_path_label.setText(self.output_path)
                
                file_names = [os.path.basename(f) for f in self.audio_files]
                
                if len(file_names) <= 3:
                    display_text = f"{len(self.audio_files)} file(s) selected:\n" + "\n".join(file_names)
                else:
                    display_text = f"{len(self.audio_files)} file(s) selected:\n" + "\n".join(file_names[:3]) + f"\n+{len(file_names) - 3} more"
                
                self.drop_area.setText(display_text)
                self.process_button.setEnabled(True)
            else:
                self.drop_area.setText("Drop audio files here\nor click to browse")
                self.process_button.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process dropped files: {str(e)}")
            self.drop_area.setText("Drop audio files here\nor click to browse")
            
    def process_files(self):
        if not self.audio_files:
            return
            
        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            QMessageBox.critical(self, "Error", 
                "FFmpeg not found. Please install FFmpeg and ensure it's in your PATH "
                "or in the same directory as this application.")
            return
            
        selected_button = self.preset_group.checkedButton()
        if selected_button == self.preset_1:
            self.preset_choice = '1'
            base_duration = 900
        elif selected_button == self.preset_2:
            self.preset_choice = '2'
            base_duration = 1850
        elif selected_button == self.preset_3:
            self.preset_choice = '3'
            base_duration = 2000
        elif selected_button == self.preset_4:
            self.preset_choice = '4'
            base_duration = 4500
            
        if self.output_format == 0:
            base_duration += 200
            
        self.animation_duration = base_duration * len(self.audio_files)
            
        self.drop_area.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.preset_1.setEnabled(False)
        self.preset_2.setEnabled(False)
        self.preset_3.setEnabled(False)
        self.preset_4.setEnabled(False)
        self.process_button.setEnabled(False)
        
        self.process_button.set_progress(0)
        
        self.current_progress = 0
        self.target_progress = 90
        self.progress_step = 1
        self.progress_interval = self.animation_duration / 90
        
        self.progress_timer.start(int(self.progress_interval))
        
        self.processing_thread = ProcessingThread(self.audio_files, self.output_path, self.preset_choice, self.output_format)
        self.processing_thread.progress_updated.connect(self.update_progress)
        self.processing_thread.processing_finished.connect(self.processing_finished)
        self.processing_thread.start()
        
    def update_progress_animation(self):
        if self.current_progress < self.target_progress:
            self.current_progress += self.progress_step
            self.process_button.set_progress(self.current_progress)
        else:
            self.progress_timer.stop()
        
    def update_progress(self, value, message):
        pass
        
    def processing_finished(self, success, message):
        self.progress_timer.stop()
        
        if success:
            self.animate_final_progress()
            
            QTimer.singleShot(10, lambda: self.show_completion_message(message))
        else:
            self.reset_button()
            QMessageBox.critical(self, "Error", message)
            
        self.drop_area.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.preset_1.setEnabled(True)
        self.preset_2.setEnabled(True)
        self.preset_3.setEnabled(True)
        self.preset_4.setEnabled(True)
        self.process_button.setEnabled(True)
            
    def animate_final_progress(self):
        self.final_animation = QPropertyAnimation(self, b"final_progress")
        self.final_animation.setDuration(500)
        self.final_animation.setStartValue(self.current_progress)
        self.final_animation.setEndValue(100)
        self.final_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.final_animation.valueChanged.connect(self.update_final_progress)
        self.final_animation.start()
    
    def update_final_progress(self, value):
        self.process_button.set_progress(value)
    
    def get_final_progress(self):
        return self.current_progress
    
    def set_final_progress(self, value):
        self.current_progress = value
        self.process_button.set_progress(value)
    
    final_progress = pyqtProperty(int, get_final_progress, set_final_progress)
    
    def show_completion_message(self, message):
        self.process_button.setText("Processing: 90%")
        
        QTimer.singleShot(500, self.reset_button)
        
    def reset_button(self):
        self.process_button.reset()
        
    def closeEvent(self, event):
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.processing_thread.wait()
        event.accept()

def find_ffmpeg():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if sys.platform == "win32":
        ffmpeg_name = "ffmpeg.exe"
    else:
        ffmpeg_name = "ffmpeg"
    
    local_ffmpeg = os.path.join(base_dir, ffmpeg_name)
    if os.path.isfile(local_ffmpeg):
        return local_ffmpeg
    
    try:
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True, check=True, creationflags=creation_flags)
        else:
            result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True, check=True)
        return result.stdout.splitlines()[0].strip()
    except (subprocess.CalledProcessError, IndexError):
        return None

def create_safe_filename(filename):
    name = os.path.splitext(filename)[0]
    name = re.sub(r"[ '\"&()]", "", name.replace(" ", "_"))
    return name

def process_waveform_image(input_path, output_path, target_width=3840):
    """Process waveform image to 1px height while maintaining proportions"""
    try:
        with Image.open(input_path) as img:
            img = img.convert('L')
            np_img = np.array(img)
            row_sums = np.sum(np_img, axis=1)
            non_empty_rows = np.where(row_sums > np_img.shape[1] * 5)[0]
            
            if len(non_empty_rows) == 0:
                Image.new('L', (target_width, 1), 0).save(output_path)
                return True
                
            min_row, max_row = non_empty_rows[0], non_empty_rows[-1]
            waveform = np_img[min_row:max_row+1, :]
            
            if waveform.max() > waveform.min():
                normalized = ((waveform - waveform.min()) * 255.0 / (waveform.max() - waveform.min())).astype(np.uint8)
            else:
                normalized = waveform
            
            final_img = Image.fromarray(normalized).resize((target_width, 1), Image.Resampling.BILINEAR)
            final_img.save(output_path)
            return True
            
    except Exception as e:
        print(f"Error processing waveform: {e}")
        return False

def get_preset_config(preset_choice):
    """Return filter configuration for selected preset"""
    presets = {
        '1': {
            'name': "Full Spectrum (1-band)",
            'bands': 1,
            'filters': [],
            'colors': ['white']
        },
        '2': {
            'name': "3-band (Low/Mid/High)",
            'bands': 3,
            'filters': [
                "lowpass=f=250",
                "highpass=f=250,lowpass=f=4000",
                "highpass=f=4000"
            ],
            'colors': ['red', 'green', 'blue']
        },
        '3': {
            'name': "10-band (Logarithmic)",
            'bands': 10,
            'filters': [
                "bandpass=f=20:w=20",
                "bandpass=f=50:w=30",
                "bandpass=f=120:w=50",
                "bandpass=f=300:w=80",
                "bandpass=f=700:w=150",
                "bandpass=f=1700:w=300",
                "bandpass=f=4000:w=600",
                "bandpass=f=9000:w=1200",
                "bandpass=f=15000:w=2000",
                "bandpass=f=20000:w=3000"
            ],
            'colors': ['white'] * 10
        },
        '4': {
            'name': "25-band (High Resolution)",
            'bands': 25,
            'filters': [
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
                "bandpass=f=20000:w=1300"
            ],
            'colors': ['white'] * 25
        }
    }
    return presets.get(preset_choice)

def main():
    app = QApplication(sys.argv)
    font = QFont("Inter", 10)
    app.setFont(font)
    app.setStyle("Fusion")
    window = AudioVisualizerGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
# -*- mode: python ; coding: utf-8 -*-
import sys
block_cipher = None

if sys.platform.startswith('win'):
    ffmpeg_binary_path = 'ffmpeg.exe'
else:
    ffmpeg_binary_path = 'ffmpeg'

binaries_to_bundle = [
    (ffmpeg_binary_path, '.')
]

datas_to_bundle = [
    ('Visualiser_Logo.png', '.')
]


a = Analysis(
    ['VisualiserV3.py'],
    pathex=[],
    binaries=binaries_to_bundle,
    datas=datas_to_bundle,
    hiddenimports=[
        'PyQt5.sip',
        'numpy.core._dtype_ctypes'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tcl', '_tkinter', 'FixTk',
        'unittest', 'doctest', 'pydoc', 'pydoc_data',
        'matplotlib', 'pandas', 'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    exclude_binaries=False,
    name='Audio Visualiser Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
    uac_uiaccess=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    version='version.txt',
    icon='Visualiser_Logo.ico',
)

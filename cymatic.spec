# PyInstaller spec file — builds a macOS .app bundle
# Run: pyinstaller cymatic.spec

import sys
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE

block_cipher = None

a = Analysis(
    ['cymatic/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'moderngl',
        'pygame',
        'sounddevice',
        'soundfile',
        'numpy',
        'cffi',
        '_sounddevice_data',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'PIL', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='CymaticVisualizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True,
    upx_exclude=[],
    name='CymaticVisualizer',
)

app = BUNDLE(
    coll,
    name='CymaticVisualizer.app',
    icon=None,
    bundle_identifier='com.otherworlding.cymatic',
    info_plist={
        'NSMicrophoneUsageDescription': 'Cymatic Visualizer uses your microphone to react to audio.',
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '1.0.0',
    },
)

# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für MediaDust.

    pyinstaller --noconfirm --clean build.spec

macOS   → dist/MediaDust.app   (onedir-Bundle mit Info.plist)
Windows → dist/MediaDust.exe   (onefile, ohne Konsole)
Linux   → dist/MediaDust       (onefile-Binary)

yt-dlp und ffmpeg werden NICHT eingebündelt – die App lädt sie beim ersten Start herunter.
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH)
APP_NAME = "MediaDust"
VERSION = "0.2.2"
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

datas = [(str(ROOT / "assets" / "icon.png"), "assets")]

hiddenimports = ["certifi"]
if IS_MAC:
    hiddenimports += ["objc", "AppKit", "Foundation"]

# Nicht benötigte Qt-Module weglassen → deutlich kleineres Bundle
excludes = [
    "tkinter", "unittest", "pydoc_data",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech", "PySide6.QtWebChannel",
    "PySide6.QtWebSockets", "PySide6.QtHttpServer", "PySide6.QtGraphs", "PySide6.QtQuick3D",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

if IS_MAC:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        strip=False,
        upx=False,
        console=False,
        argv_emulation=False,
        target_arch=None,          # Architektur des bauenden Pythons (arm64 auf Apple Silicon)
        codesign_identity=None,    # ad-hoc-Signatur; eigene Developer-ID hier eintragen
        entitlements_file=None,
        icon=str(ROOT / "assets" / "icon.icns"),
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(ROOT / "assets" / "icon.icns"),
        bundle_identifier="com.mediadust.app",
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSHumanReadableCopyright": "MediaDust – nutzt yt-dlp (Unlicense) und ffmpeg (LGPL/GPL)",
        },
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name=APP_NAME,
        debug=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        icon=str(ROOT / "assets" / "icon.ico") if IS_WIN else None,
    )

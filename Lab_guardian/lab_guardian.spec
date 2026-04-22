# -*- mode: python ; coding: utf-8 -*-
# lab_guardian.spec
#
# PyInstaller spec for Lab Guardian.
# Produces a single self-contained binary: dist/lab_guardian
#
# Build command (run from the Lab_guardian/ directory):
#   pyinstaller lab_guardian.spec
# --------------------------------------------------------------------------

import sys
import os
from pathlib import Path

# Resolve the project root (directory containing this spec file)
PROJECT_ROOT = Path(SPECPATH)                 # PyInstaller sets SPECPATH

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
# PyInstaller's static analyser cannot always detect dynamic imports
# (e.g. `import pyudev` inside a try/except at runtime).  List every module
# that is imported lazily or conditionally so it ends up in the bundle.

hidden_imports = [
    # stdlib used at runtime
    "sqlite3",
    "tkinter",
    "tkinter.ttk",
    "asyncio",
    "threading",
    "urllib.parse",
    "socket",
    "logging",
    "json",
    "shutil",
    "glob",
    "getpass",
    "struct",
    "platform",
    "subprocess",
    "re",
    "dataclasses",
    # third-party
    "psutil",
    "psutil._pslinux",
    "psutil._psposix",
    "requests",
    "requests.adapters",
    "requests.auth",
    "requests.cookies",
    "requests.exceptions",
    "requests.models",
    "requests.sessions",
    "requests.structures",
    "requests.utils",
    "urllib3",
    "urllib3.contrib",
    "urllib3.util",
    "certifi",
    "charset_normalizer",
    "idna",
    "netifaces",
    "pyudev",
    "pyudev.device",
    "pyudev.monitor",
    # Optional — Firefox sessionstore private-window detection
    # If lz4 is present it will be included; if absent PyInstaller silently skips it.
    "lz4",
    "lz4.block",
    # lab_guardian sub-packages (ensure all are bundled)
    "lab_guardian",
    "lab_guardian.config",
    "lab_guardian.db",
    "lab_guardian.dispatcher",
    "lab_guardian.gui",
    "lab_guardian.monitor",
    "lab_guardian.monitor.browser_history",
    "lab_guardian.monitor.device_monitor",
    "lab_guardian.monitor.network_monitor",
    "lab_guardian.monitor.process_monitor",
]

# ---------------------------------------------------------------------------
# Data files to bundle (non-Python assets)
# ---------------------------------------------------------------------------
# Format: (source_path, destination_dir_inside_bundle)

datas = []

# Bundle the application icon if it exists
icon_src = PROJECT_ROOT / "assets" / "icon.png"
if icon_src.exists():
    datas.append((str(icon_src), "assets"))

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy packages we definitely don't use
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "PIL",
        "cv2",
        "PyQt5",
        "PyQt6",
        "wx",
        "gi",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Single-file (onefile) executable
# ---------------------------------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="lab_guardian",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,       # compress the binary (needs upx installed; silently skipped if absent)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # no terminal window — pure GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icon for the executable (used in taskbar on supported platforms)
    icon=str(icon_src) if icon_src.exists() else None,
)

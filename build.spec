# PyInstaller spec for Lingnan YOLOv8 desktop app.
#
# Usage:
#   pyinstaller build.spec
#
# Output:
#   dist/Lingnan/Lingnan.exe
#
# This build targets the PyTorch/Ultralytics .pt backend. ONNX Runtime is
# intentionally excluded because the current distributable model is best.pt and
# the ONNX package chain is not needed for the green Windows build.
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

ROOT = Path(SPECPATH)

os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "runtime_data" / "ultralytics"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "runtime_data" / "ultralytics" / "matplotlib"))

datas = []
binaries = []
hidden_imports = []

# Ultralytics needs its cfg YAML files at runtime; torch/torchvision need their
# DLLs and metadata collected for a self-contained Windows folder. Matplotlib is
# used by the training result page to generate local training charts.
for pkg in ("ultralytics", "torch", "torchvision", "matplotlib"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hidden_imports += pkg_hidden

# Model files. build.bat or the manual build step copies best.pt to the
# candidate name expected by the app.
for model_name in ("yolov8s_xh_best.pt", "yolov8s.pt"):
    model_path = ROOT / "models" / model_name
    if model_path.exists():
        datas.append((str(model_path), "models"))

# Chinese font for PDF/PIL rendering.
for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
    p = Path(fp)
    if p.exists():
        datas.append((str(p), "fonts"))
        break

excludes = [
    "scipy",
    "pandas",
    "onnx",
    "onnxruntime",
    "tensorflow",
    "jupyter",
    "notebook",
    "IPython",
    "pytest",
]

hidden_imports += [
    "openpyxl",
    "reportlab.lib",
    "reportlab.pdfgen",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "requests",
    "qfluentwidgets",
]

a = Analysis(
    ["app.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon = ROOT / "lingnan" / "assets" / "icon.ico"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Lingnan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon) if icon.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Lingnan",
)

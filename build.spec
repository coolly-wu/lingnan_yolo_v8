# PyInstaller spec for 廉江红橙病虫害智能检测防治系统
#
# 使用：
#   pyinstaller build.spec
# 产物：dist/XHGan/XHGan.exe + 数据资源
#
# 若要单文件：把 onefile=True，但启动会较慢且模型解压到 temp 目录

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH)  # PyInstaller 注入的项目根

# 数据 (源, 目标相对路径)
datas = []

# 知识库：lianjiang_hongcheng.db 启动时自动生成，无需打包；但 prescriptions_seed 已在源码中
# 模型：用户自行放入 models/，这里不强打包；若已存在 yolov8s_xh_best_int8.onnx 则带上
model = ROOT / "models" / "yolov8s_xh_best_int8.onnx"
if model.exists():
    datas.append((str(model), "models"))
# 备选：先打包占位（演示用）
for fallback in ["yolov8s.pt", "yolov8n.pt"]:
    p = ROOT / "models" / fallback
    if p.exists():
        datas.append((str(p), "models"))
        break

# 中文字体（用于 PDF 与 PIL 渲染）
font_paths = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]
for fp in font_paths:
    p = Path(fp)
    if p.exists():
        datas.append((str(p), "fonts"))
        break

# 排除大体积无用依赖
excludes = [
    "matplotlib", "scipy", "pandas",
    "torch", "torchvision",  # 部署仅用 ORT，无须 PyTorch
    "tensorflow",
    "jupyter", "notebook", "IPython",
]

hidden_imports = [
    "openpyxl",
    "reportlab.lib", "reportlab.pdfgen",
    "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    "onnxruntime",
]

a = Analysis(
    ["app.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="XHGan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # 不弹黑窗
    icon=str(ROOT / "xhgan" / "assets" / "icon.ico")
        if (ROOT / "xhgan" / "assets" / "icon.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="XHGan",
)

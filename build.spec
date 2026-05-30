# PyInstaller spec for 廉江红橙病虫害智能检测防治系统（lingnan 包）
#
# 使用：
#   pyinstaller build.spec
# 产物：dist/XHGan/XHGan.exe + 数据资源（onedir 绿色版）
#
# 后端：包含 PyTorch + Ultralytics，打包真实训练模型 best.pt，
#       因此 exe 可直接做真实检测（无 ONNX 也能用 .pt 后端）。
#       体积较大（约 1.5–2GB），首次启动稍慢。

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH)  # PyInstaller 注入的项目根

datas = []
binaries = []
hidden_imports = []

# ---------- ultralytics / torch 完整资源（cfg/*.yaml 等运行时必需） ----------
for pkg in ("ultralytics", "torch", "torchvision"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hidden_imports += pkg_hidden

# onnxruntime 数据（CPU EP）
datas += collect_data_files("onnxruntime")
hidden_imports += collect_submodules("onnxruntime")

# ---------- 推理模型 ----------
# 优先 ONNX（若已导出），否则带上真实 .pt 训练模型。
# config.MODEL_CANDIDATES 认 yolov8s_xh_best*.* —— 因此把 best.pt 改名打包。
onnx = ROOT / "models" / "yolov8s_xh_best_int8.onnx"
pt_real = ROOT / "models" / "best.pt"            # 真实训练权重（本仓库实际文件名）
pt_named = ROOT / "models" / "yolov8s_xh_best.pt"  # 候选列表里的标准名
coco = ROOT / "models" / "yolov8s.pt"            # COCO 占位（演示兜底）

if onnx.exists():
    datas.append((str(onnx), "models"))
if pt_named.exists():
    datas.append((str(pt_named), "models"))
elif pt_real.exists():
    # 映射到候选列表认得的名字，使打包后能被自动加载
    datas.append((str(pt_real), "models"))  # 原名也带上备查
    datas.append((str(pt_real), "models"))  # 占位，下行真正改名由 _RENAMED 处理
# datas 不支持改目标文件名（只能改目录），故改用下方 _extra 复制策略说明：
# —— PyInstaller datas 的第二元素是“目标目录”，文件名保持源名。
#    因此若仓库里是 best.pt，打包后仍是 models/best.pt，不在候选列表。
#    解决：构建前确保存在 models/yolov8s_xh_best.pt（见 build.bat 自动改名）。
if coco.exists():
    datas.append((str(coco), "models"))

# ---------- 中文字体（PDF / PIL 渲染） ----------
for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
    p = Path(fp)
    if p.exists():
        datas.append((str(p), "fonts"))
        break

# ---------- 知识库种子（运行时自动建库，无需打包 .db） ----------

# ---------- 排除无用大依赖 ----------
excludes = [
    "matplotlib", "scipy", "pandas",
    "tensorflow",
    "jupyter", "notebook", "IPython",
    "pytest",
]

# ---------- 本项目显式 hidden imports ----------
hidden_imports += [
    "openpyxl",
    "reportlab.lib", "reportlab.pdfgen",
    "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
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
    name="XHGan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # torch DLL 用 UPX 压缩易导致加载失败，关闭更稳
    console=False,   # 不弹黑窗
    icon=str(icon) if icon.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="XHGan",
)

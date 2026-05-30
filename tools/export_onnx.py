"""把 .pt 导出为 ONNX：用于 ONNX Runtime CPU 部署

用法：
    python -m tools.export_onnx --weights runs/detect/yolov8s_xh/weights/best.pt
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="导出 ONNX 模型")
    p.add_argument("--weights", required=True, help="best.pt 路径")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--opset", type=int, default=12)
    p.add_argument("--simplify", action="store_true", default=True)
    p.add_argument("--dynamic", action="store_true",
                   help="动态 batch / shape（部分 ORT 优化失效，默认关闭）")
    p.add_argument("--output", default=None,
                   help="拷贝到 models/ 下的目标文件名，默认 yolov8s_xh_best.onnx")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pt = Path(args.weights)
    if not pt.exists():
        print(f"[ERR] 权重不存在：{pt}", file=sys.stderr)
        return 1

    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERR] 请先 `pip install ultralytics`", file=sys.stderr)
        return 1

    print(f"==> 导出 ONNX: {pt}")
    model = YOLO(str(pt))
    onnx_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        opset=args.opset,
        simplify=args.simplify,
        dynamic=args.dynamic,
    )
    onnx_path = Path(onnx_path)
    print(f"    生成 ONNX: {onnx_path}")

    # 拷贝到 models/
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target_name = args.output or "yolov8s_xh_best.onnx"
    target = MODELS_DIR / target_name
    shutil.copy2(onnx_path, target)
    print(f"==> 已拷贝到部署位置: {target}")
    print("    下一步可选：python -m tools.quantize_int8 --input {} --calibration ...".format(target))
    return 0


if __name__ == "__main__":
    sys.exit(main())

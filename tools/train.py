"""一键训练 yolov8s_xh

用法：
    python -m tools.train --data path/to/data.yaml --epochs 300

需先在算法工作站安装：
    pip install ultralytics
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = PROJECT_ROOT / "lianjiang_hongcheng_dataset" / "data.yaml"
DEFAULT_CFG = PROJECT_ROOT / "tools" / "yolov8s_xh.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="训练 YOLOv8s-XH（廉江红橙专用）")
    p.add_argument("--data", default=str(DEFAULT_DATA),
                   help=f"数据集 data.yaml 路径（默认 {DEFAULT_DATA}）")
    p.add_argument("--cfg", default=str(DEFAULT_CFG),
                   help="模型架构 yaml（默认 yolov8s_xh.yaml）")
    p.add_argument("--pretrained", default="yolov8s.pt",
                   help="预训练权重（迁移学习起点）")
    p.add_argument("--epochs", type=int, default=300)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--device", default="0",
                   help="GPU 编号（'0' / '0,1' / 'cpu'）")
    p.add_argument("--name", default="yolov8s_xh",
                   help="runs/detect/<name> 目录名")
    p.add_argument("--resume", action="store_true",
                   help="从上一次中断处续训")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not Path(args.data).exists():
        print(f"[ERR] data.yaml 不存在：{args.data}", file=sys.stderr)
        print(
            "请先按技术规范 §2 准备数据集，目录结构示例：\n"
            "    lianjiang_hongcheng_dataset/\n"
            "      ├── images/{train,val,test}/*.jpg\n"
            "      ├── labels/{train,val,test}/*.txt\n"
            "      └── data.yaml",
            file=sys.stderr,
        )
        return 1
    if not Path(args.cfg).exists():
        print(f"[ERR] 模型 yaml 不存在：{args.cfg}", file=sys.stderr)
        return 1

    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERR] 请先 `pip install ultralytics`", file=sys.stderr)
        return 1

    print(f"==> 训练 YOLOv8s-XH: {args.cfg}")
    print(f"    data       = {args.data}")
    print(f"    pretrained = {args.pretrained}")
    print(f"    epochs     = {args.epochs}")
    print(f"    imgsz      = {args.imgsz}")
    print(f"    batch      = {args.batch}")
    print(f"    device     = {args.device}")
    print(f"    name       = {args.name}")
    print()

    model = YOLO(args.cfg).load(args.pretrained)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        name=args.name,
        resume=args.resume,
        # 田间专项增强（技术规范 §3.2）
        hsv_h=0.02, hsv_s=0.8, hsv_v=0.5,
        degrees=15.0, translate=0.15, scale=0.6,
        mixup=0.15, copy_paste=0.2,
        patience=80,
        cos_lr=True,
        amp=True,
    )
    print()
    print("==> 训练完成，best.pt 位于 runs/detect/{}/weights/best.pt".format(args.name))
    print("    下一步：python -m tools.export_onnx --weights runs/detect/{}/weights/best.pt".format(args.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Subprocess entry point for Ultralytics training."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from . import config as C


def publish_trained_weights(run_dir: str | Path, models_dir: str | Path = C.MODELS_DIR) -> list[Path]:
    """Copy trained YOLO weights from a run directory into project models/."""
    run_dir = Path(run_dir)
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    weight_dir = run_dir / "weights"
    targets = (
        (weight_dir / "best.pt", models_dir / "best.pt"),
        (weight_dir / "best.pt", models_dir / "yolov8s_xh_best.pt"),
        (weight_dir / "last.pt", models_dir / "yolov8s_xh_last.pt"),
    )
    for src, dst in targets:
        if src.exists():
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Train YOLOv8s-XH dataset")
    parser.add_argument("--model", default="yolov8s.pt")
    parser.add_argument("--data", required=True)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--project", default="")
    parser.add_argument("--name", default="yolov8s_xh")
    args = parser.parse_args()

    from ultralytics import YOLO

    project = args.project or str(Path("runtime_data") / "training_runs")
    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        hsv_h=0.02,
        hsv_s=0.8,
        hsv_v=0.5,
        degrees=15,
        translate=0.15,
        scale=0.6,
        mixup=0.15,
        copy_paste=0.2,
        close_mosaic=10,
        project=project,
        name=args.name,
    )
    save_dir = Path(getattr(model.trainer, "save_dir", Path(project) / args.name))
    copied = publish_trained_weights(save_dir)
    if copied:
        print("已保存训练模型到 models 目录：")
        for path in copied:
            print(f"  {path}")
    else:
        print(f"未找到可发布的训练权重：{save_dir / 'weights'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

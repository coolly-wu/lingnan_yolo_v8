"""ONNX → INT8 静态量化（PTQ）

技术规范 §7.2：
    INT8 量化使速度 ↑2~3×、体积 ↓4×，精度损失需 ≤ 1.5 pt。
    若不可控请保留 FP32 备份。

用法：
    python -m tools.quantize_int8 \\
        --input  models/yolov8s_xh_best.onnx \\
        --output models/yolov8s_xh_best_int8.onnx \\
        --calibration_dir lianjiang_hongcheng_dataset/images/val \\
        --num_samples 500
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ONNX INT8 静态量化")
    p.add_argument("--input", required=True, help="FP32 ONNX 路径")
    p.add_argument("--output", required=True, help="量化后 ONNX 输出")
    p.add_argument("--calibration_dir", required=True,
                   help="校准图集目录（建议覆盖 12 类 × 5 物候期）")
    p.add_argument("--num_samples", type=int, default=500,
                   help="校准样本数（500 即可，越大精度越稳）")
    p.add_argument("--imgsz", type=int, default=640)
    return p.parse_args(argv)


def _letterbox(img: np.ndarray, new_size: tuple[int, int]) -> np.ndarray:
    import cv2
    nh, nw = new_size
    h, w = img.shape[:2]
    r = min(nw / w, nh / h)
    rw, rh = int(round(w * r)), int(round(h * r))
    resized = cv2.resize(img, (rw, rh), interpolation=cv2.INTER_LINEAR)
    pad_w, pad_h = nw - rw, nh - rh
    top, left = pad_h // 2, pad_w // 2
    out = np.full((nh, nw, 3), 114, dtype=np.uint8)
    out[top:top + rh, left:left + rw] = resized
    return out


class _ImgCalibReader:
    """OnnxRuntime CalibrationDataReader 实现"""

    def __init__(self, files: list[Path], input_name: str, imgsz: int):
        import cv2
        self.cv2 = cv2
        self.iter = iter(files)
        self.input_name = input_name
        self.imgsz = imgsz

    def get_next(self):
        try:
            f = next(self.iter)
        except StopIteration:
            return None
        img = self.cv2.imread(str(f))
        if img is None:
            data = np.fromfile(str(f), dtype=np.uint8)
            img = self.cv2.imdecode(data, self.cv2.IMREAD_COLOR)
        if img is None:
            return self.get_next()
        lb = _letterbox(img, (self.imgsz, self.imgsz))
        rgb = self.cv2.cvtColor(lb, self.cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        chw = rgb.transpose(2, 0, 1)[None]
        return {self.input_name: chw}

    def rewind(self):
        pass


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    src = Path(args.input)
    if not src.exists():
        print(f"[ERR] 输入 ONNX 不存在：{src}", file=sys.stderr)
        return 1
    cal_dir = Path(args.calibration_dir)
    if not cal_dir.exists():
        print(f"[ERR] 校准目录不存在：{cal_dir}", file=sys.stderr)
        return 1

    try:
        import onnxruntime as ort
        from onnxruntime.quantization import (
            CalibrationDataReader,
            QuantFormat,
            QuantType,
            quantize_static,
        )
    except ImportError:
        print("[ERR] 请先 `pip install onnxruntime` 与 `pip install onnx`",
              file=sys.stderr)
        return 1

    # 收集校准样本
    files = sorted(
        [p for p in cal_dir.rglob("*") if p.suffix.lower() in
         {".jpg", ".jpeg", ".png", ".bmp"}]
    )
    if not files:
        print("[ERR] 校准目录无可用图片", file=sys.stderr)
        return 1
    random.seed(42)
    random.shuffle(files)
    files = files[:args.num_samples]
    print(f"==> 校准样本：{len(files)} 张")

    # 检测输入名
    sess = ort.InferenceSession(str(src), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    print(f"    input  = {input_name}")
    print(f"    output = {[o.name for o in sess.get_outputs()]}")

    reader = _ImgCalibReader(files, input_name, args.imgsz)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"==> 量化中（约 1~3 分钟）…")
    quantize_static(
        model_input=str(src),
        model_output=str(out),
        calibration_data_reader=reader,
        quant_format=QuantFormat.QDQ,
        per_channel=False,
        activation_type=QuantType.QInt8,
        weight_type=QuantType.QInt8,
    )
    print(f"==> 量化完成: {out} ({out.stat().st_size / 1024 / 1024:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

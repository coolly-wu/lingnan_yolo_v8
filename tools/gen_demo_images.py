"""生成演示用合成图：12 类病虫害每类几张

每张图：
  · 绿色叶片 / 黄色果实纯色背景
  · 模拟病斑（噪点 + 颜色块）
  · 文本水印标注是哪一类（仅供 UI 联调时人眼对照）

用法：
    python -m tools.gen_demo_images --num_per_class 2 --output runtime_data/demo
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="生成演示用合成图")
    p.add_argument("--num_per_class", type=int, default=2)
    p.add_argument("--size", type=int, default=720)
    p.add_argument("--output", default=str(PROJECT_ROOT / "runtime_data" / "demo"))
    return p.parse_args(argv)


# 12 类背景偏好：果叶 vs 果实
DISEASE_PRESETS = [
    {"key": "huanglongbing", "name": "柑橘黄龙病",   "bg": (60, 140, 60),   "spot": (60, 200, 220), "spots": 30},
    {"key": "canker",        "name": "柑橘溃疡病",   "bg": (50, 130, 70),   "spot": (40, 60, 110),  "spots": 18},
    {"key": "scab",          "name": "柑橘疮痂病",   "bg": (40, 150, 90),   "spot": (60, 130, 170), "spots": 22},
    {"key": "anthracnose",   "name": "柑橘炭疽病",   "bg": (60, 110, 50),   "spot": (40, 50, 90),   "spots": 14},
    {"key": "black_spot",    "name": "柑橘黑斑病",   "bg": (40, 130, 200),  "spot": (30, 30, 30),   "spots": 16},
    {"key": "red_mite",      "name": "柑橘红蜘蛛",   "bg": (40, 150, 80),   "spot": (40, 40, 220),  "spots": 80},
    {"key": "psyllid",       "name": "柑橘木虱",     "bg": (60, 140, 70),   "spot": (160, 110, 60), "spots": 28},
    {"key": "leaf_miner",    "name": "柑橘潜叶蛾",   "bg": (30, 120, 50),   "spot": (230, 230, 230),"spots": 12},
    {"key": "aphids",        "name": "柑橘蚜虫",     "bg": (50, 150, 80),   "spot": (40, 200, 40),  "spots": 60},
    {"key": "scale_insects", "name": "柑橘介壳虫",   "bg": (90, 80, 70),    "spot": (220, 220, 220),"spots": 18},
    {"key": "flower_bud_midge","name": "柑橘花蕾蛆", "bg": (200, 200, 180), "spot": (90, 130, 60),  "spots": 10},
    {"key": "blackfly",      "name": "柑橘黑刺粉虱", "bg": (50, 140, 70),   "spot": (10, 10, 10),   "spots": 50},
]


def _make_image(preset: dict, size: int, seed: int) -> np.ndarray:
    import cv2
    rng = np.random.default_rng(seed)
    h = w = size
    img = np.full((h, w, 3), preset["bg"], dtype=np.uint8)
    # 加噪点（叶面纹理）
    noise = rng.normal(0, 18, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    # 模拟主病斑
    n = preset["spots"]
    color = preset["spot"]
    for _ in range(n):
        cx = int(rng.integers(20, w - 20))
        cy = int(rng.integers(20, h - 20))
        r = int(rng.integers(4, 18))
        cv2.circle(img, (cx, cy), r, color, -1)
        # 边缘虚化
        cv2.circle(img, (cx, cy), r + 2,
                   tuple(int(c * 0.6) for c in color), 1)
    # 主病斑（大）
    big_cx = int(rng.integers(size * 0.3, size * 0.7))
    big_cy = int(rng.integers(size * 0.3, size * 0.7))
    big_r = int(size * 0.12)
    cv2.circle(img, (big_cx, big_cy), big_r, color, -1)
    # 水印
    cv2.rectangle(img, (0, h - 40), (w, h), (255, 255, 255), -1)
    cv2.putText(img, f"DEMO: {preset['name']}",
                (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return img


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import cv2  # noqa
    except ImportError:
        print("[ERR] 请先 `pip install opencv-python`", file=sys.stderr)
        return 1

    n_files = 0
    for preset in DISEASE_PRESETS:
        for k in range(args.num_per_class):
            img = _make_image(preset, args.size, seed=42 + n_files)
            f = out_dir / f"{preset['key']}_{k+1:02d}.jpg"
            from xhgan.core.image_io import imwrite_unicode
            imwrite_unicode(f, img, ".jpg")
            n_files += 1
    print(f"==> 已生成 {n_files} 张演示图：{out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

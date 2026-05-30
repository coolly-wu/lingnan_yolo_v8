"""可视化标注：彩色定界框 + 中文标签 + 严重程度色条

依据技术规范 §8.7.1：
  - 半透明彩色矩形（12 类各一种颜色）
  - 标签 [中文病虫害名称] [置信度%]
  - 黄龙病闪烁红框（GUI 实现，渲染时仅画红框）
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .. import config as C
from .inferencer import Detection
from . import severity as sv


# Pillow 字体：尝试系统字体，失败回落默认
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]

_FONT_PATH: str | None = None
for _p in _FONT_CANDIDATES:
    if Path(_p).exists():
        _FONT_PATH = _p
        break


def _get_font(size: int) -> ImageFont.ImageFont:
    if _FONT_PATH:
        try:
            return ImageFont.truetype(_FONT_PATH, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_detections(img_bgr: np.ndarray, detections: list[Detection],
                    summary: dict | None = None) -> np.ndarray:
    """在原图上画检测框 + 标签 + 顶部状态条。返回 BGR 副本。"""
    canvas = img_bgr.copy()
    h, w = canvas.shape[:2]

    # 半透明填充
    overlay = canvas.copy()
    for d in detections:
        x1, y1, x2, y2 = [int(v) for v in d.xyxy]
        cv2.rectangle(overlay, (x1, y1), (x2, y2), d.color_bgr, -1)
    cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0, canvas)

    # 实线边框
    for d in detections:
        x1, y1, x2, y2 = [int(v) for v in d.xyxy]
        thickness = 3 if d.disease.get("fatal") else 2
        cv2.rectangle(canvas, (x1, y1), (x2, y2), d.color_bgr, thickness)

    # 标签需要中文 → 转 PIL
    canvas = _draw_chinese_labels(canvas, detections)

    # 顶部状态条
    if summary is not None:
        canvas = _draw_status_bar(canvas, summary)

    return canvas


def _draw_chinese_labels(img_bgr: np.ndarray, detections: list[Detection]) -> np.ndarray:
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    font = _get_font(18)
    for d in detections:
        x1, y1, x2, y2 = [int(v) for v in d.xyxy]
        text = f"{d.name_cn} {d.conf * 100:.1f}%"
        # 文本框背景
        try:
            tb = draw.textbbox((x1, y1), text, font=font)
            tx1, ty1, tx2, ty2 = tb
        except Exception:
            tx1, ty1, tx2, ty2 = x1, y1, x1 + len(text) * 12, y1 + 22
        tx2 = max(tx2, x1 + 80)
        ty1 = max(0, ty1 - 4 if ty1 - 4 >= 0 else y2)
        bg = tuple(int(v) for v in d.color_bgr[::-1])  # BGR -> RGB
        draw.rectangle([tx1, ty1, tx2, ty1 + (ty2 - ty1) + 4], fill=bg)
        # 高亮致命病害文字
        fg = (255, 255, 255)
        draw.text((tx1 + 2, ty1 + 1), text, fill=fg, font=font)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def _draw_status_bar(img_bgr: np.ndarray, summary: dict) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    bar_h = 56
    new = np.zeros((h + bar_h, w, 3), dtype=np.uint8)
    sev = summary.get("severity", C.SEVERITY_GREEN)
    bar_color = C.SEVERITY_COLORS.get(sev, (60, 60, 60))
    new[:bar_h] = bar_color
    new[bar_h:] = img_bgr

    pil = Image.fromarray(cv2.cvtColor(new, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    font_big = _get_font(22)
    font_small = _get_font(15)
    primary_name = summary.get("primary_name_cn") or "未检出"
    sev_cn = C.SEVERITY_LABELS_CN.get(sev, sev)
    count = summary.get("count", 0)
    conf = summary.get("primary_conf", 0.0)
    area_pct = summary.get("area_ratio", 0.0) * 100
    txt_left = f"主病害：{primary_name}   置信度：{conf * 100:.1f}%"
    txt_right = f"数量：{count}    面积占比：{area_pct:.1f}%    严重程度：{sev_cn}"
    draw.text((10, 6), txt_left, fill=(255, 255, 255), font=font_big)
    draw.text((10, 33), txt_right, fill=(255, 255, 255), font=font_small)
    if summary.get("has_fatal"):
        draw.text((w - 200, 14), "⚠ 检出致命病害", fill=(255, 255, 0), font=font_big)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


__all__ = ["draw_detections"]

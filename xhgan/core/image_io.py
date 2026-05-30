"""图像 I/O 工具：兼容中文路径"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def imread_unicode(path: str | Path) -> Optional[np.ndarray]:
    """读取图像，兼容中文 / Unicode 路径。返回 BGR ndarray，失败返回 None。"""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_unicode(path: str | Path, img: np.ndarray, ext: str = ".jpg",
                    params: list[int] | None = None) -> bool:
    """写入图像，兼容中文路径。"""
    try:
        ok, buf = cv2.imencode(ext, img, params or [])
        if not ok:
            return False
        buf.tofile(str(path))
        return True
    except Exception:
        return False

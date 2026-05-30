"""群聚虫害密集计数

针对红蜘蛛 / 蚜虫 / 木虱 / 黑刺粉虱 等 swarm 类，输出右侧面板用计数信息。
当前实现以 detection 直接计数为主；保留接口以后可接入点状目标聚类。
"""

from __future__ import annotations

from .inferencer import Detection


def swarm_counts(detections: list[Detection]) -> dict[str, int]:
    """按中文名返回 swarm 类的计数。"""
    result: dict[str, int] = {}
    for d in detections:
        if d.disease.get("swarm"):
            result[d.name_cn] = result.get(d.name_cn, 0) + 1
    return result

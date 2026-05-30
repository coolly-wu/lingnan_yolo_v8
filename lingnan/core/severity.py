"""严重程度自动分级 + 群聚虫害计数

依据技术规范 §8.7.2：
  Green (轻度)：病斑面积 < 5% 或 虫体数 < 5
  Amber (中度)：5% ≤ 面积 < 20% 或 5 ≤ 虫体数 < 20
  Red   (重度)：面积 ≥ 20% 或 虫体数 ≥ 20 或 任意黄龙病
"""

from __future__ import annotations

from .. import config as C
from .inferencer import Detection


def aggregate(detections: list[Detection], img_w: int, img_h: int) -> dict:
    """汇总检测结果：主病害、计数、面积占比、严重程度"""
    if not detections:
        return {
            "primary_id": None,
            "primary_name_cn": None,
            "primary_conf": 0.0,
            "count": 0,
            "area_ratio": 0.0,
            "severity": C.SEVERITY_GREEN,
            "has_fatal": False,
            "per_class": {},
        }

    # 按类别聚合
    per_class: dict[int, dict] = {}
    img_area = max(1.0, float(img_w) * float(img_h))
    for d in detections:
        slot = per_class.setdefault(d.cls_id, {
            "cls_id": d.cls_id,
            "name_cn": d.name_cn,
            "count": 0,
            "max_conf": 0.0,
            "area_sum": 0.0,
            "is_fatal": bool(d.disease.get("fatal")),
            "is_swarm": bool(d.disease.get("swarm")),
        })
        slot["count"] += 1
        slot["max_conf"] = max(slot["max_conf"], d.conf)
        slot["area_sum"] += d.area
    for v in per_class.values():
        v["area_ratio"] = min(1.0, v["area_sum"] / img_area)

    # 主病害：优先致命病害，否则按 (count, max_conf) 排序
    fatal_cls = [v for v in per_class.values() if v["is_fatal"]]
    if fatal_cls:
        primary = max(fatal_cls, key=lambda v: v["max_conf"])
    else:
        primary = max(per_class.values(), key=lambda v: (v["count"], v["max_conf"]))

    # 严重程度（基于主病害）
    severity = _severity_for(primary)

    return {
        "primary_id": primary["cls_id"],
        "primary_name_cn": primary["name_cn"],
        "primary_conf": primary["max_conf"],
        "count": primary["count"],
        "area_ratio": primary["area_ratio"],
        "severity": severity,
        "has_fatal": any(v["is_fatal"] for v in per_class.values()),
        "per_class": per_class,
    }


def _severity_for(primary_slot: dict) -> str:
    """单个主病害的严重程度判定"""
    if primary_slot["is_fatal"]:
        return C.SEVERITY_RED
    c = primary_slot["count"]
    a = primary_slot["area_ratio"]
    t = C.SEVERITY_THRESHOLDS
    if primary_slot["is_swarm"]:
        # 虫害以计数为主
        if c >= t["count_red"]:
            return C.SEVERITY_RED
        if c >= t["count_amber"]:
            return C.SEVERITY_AMBER
        return C.SEVERITY_GREEN
    # 病害以面积为主
    if a >= t["area_red"]:
        return C.SEVERITY_RED
    if a >= t["area_amber"]:
        return C.SEVERITY_AMBER
    return C.SEVERITY_GREEN

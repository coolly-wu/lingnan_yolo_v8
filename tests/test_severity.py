"""核心：严重程度分级 12 类测试"""

import pytest

pytestmark = pytest.mark.usefixtures("numpy_stub")


def _make_det(cls_id, conf=0.9, xyxy=(0, 0, 10, 10)):
    from xhgan import config as C
    from xhgan.core.inferencer import Detection
    return Detection(
        cls_id=cls_id, conf=conf,
        xyxy=list(xyxy),
        disease=C.DISEASE_BY_ID[cls_id],
    )


def test_empty_returns_green():
    from xhgan.core.severity import aggregate
    r = aggregate([], 100, 100)
    assert r["severity"] == "Green"
    assert r["primary_id"] is None
    assert r["count"] == 0


def test_one_red_mite_green():
    """1 个红蜘蛛 < 5 -> Green"""
    from xhgan.core.severity import aggregate
    dets = [_make_det(5)]
    r = aggregate(dets, 1000, 1000)
    assert r["severity"] == "Green"
    assert "红蜘蛛" in r["primary_name_cn"]


def test_six_psyllid_amber():
    """6 个木虱 (5~20) -> Amber"""
    from xhgan.core.severity import aggregate
    dets = [_make_det(6) for _ in range(6)]
    r = aggregate(dets, 1000, 1000)
    assert r["severity"] == "Amber"


def test_25_aphids_red():
    """25 个蚜虫 (>20) -> Red"""
    from xhgan.core.severity import aggregate
    dets = [_make_det(8) for _ in range(25)]
    r = aggregate(dets, 1000, 1000)
    assert r["severity"] == "Red"


def test_huanglongbing_always_red():
    """任意黄龙病（致命病害） -> Red"""
    from xhgan.core.severity import aggregate
    dets = [_make_det(0, conf=0.5)]
    r = aggregate(dets, 2000, 2000)
    assert r["severity"] == "Red"
    assert r["has_fatal"] is True


def test_canker_large_area_red():
    """大面积溃疡病 -> 通过 area_ratio Red"""
    from xhgan.core.severity import aggregate
    # 500x500 / 1000x1000 = 25% > 20%
    dets = [_make_det(1, xyxy=(0, 0, 500, 500))]
    r = aggregate(dets, 1000, 1000)
    assert r["severity"] == "Red"


def test_canker_small_area_green():
    from xhgan.core.severity import aggregate
    dets = [_make_det(1, xyxy=(0, 0, 50, 50))]   # 0.25% << 5%
    r = aggregate(dets, 1000, 1000)
    assert r["severity"] == "Green"


def test_primary_is_fatal_when_mixed():
    """HLB + 别的病并存时主病害应为 HLB"""
    from xhgan.core.severity import aggregate
    dets = [_make_det(0)] + [_make_det(1) for _ in range(10)]
    r = aggregate(dets, 1000, 1000)
    assert "黄龙病" in r["primary_name_cn"]
    assert r["has_fatal"]


def test_per_class_counts():
    from xhgan.core.severity import aggregate
    dets = [_make_det(5) for _ in range(3)] + [_make_det(6) for _ in range(2)]
    r = aggregate(dets, 1000, 1000)
    pc = r["per_class"]
    assert pc[5]["count"] == 3
    assert pc[6]["count"] == 2

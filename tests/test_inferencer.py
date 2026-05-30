"""Inferencer 后端选择测试：mock 回落"""

import pytest

pytestmark = pytest.mark.usefixtures("numpy_stub")


def test_mock_backend_when_no_model(tmp_path, monkeypatch):
    """所有候选模型不存在时 -> Mock"""
    import lingnan.config as C
    monkeypatch.setattr(C, "MODEL_CANDIDATES", [tmp_path / "absent.onnx"])

    # 重新 import 让 monkeypatch 生效
    import importlib
    import lingnan.core.inferencer as inf_mod
    importlib.reload(inf_mod)

    inf = inf_mod.Inferencer()
    assert inf.backend_type == "mock"
    assert inf.model_path is None


def test_mock_predict_returns_list(numpy_stub, monkeypatch):
    """Mock 推理至少返回 1 个 detection（受随机性影响，但 [1,6] 必至少 1）"""
    pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    import lingnan.config as C
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        from pathlib import Path
        monkeypatch.setattr(C, "MODEL_CANDIDATES", [Path(d) / "absent.onnx"])
        import importlib
        import lingnan.core.inferencer as inf_mod
        importlib.reload(inf_mod)
        import numpy as np
        inf = inf_mod.Inferencer()
        img = np.zeros((480, 640, 3), dtype="uint8")
        dets = inf.predict(img, conf=0.25, iou=0.45)
        assert isinstance(dets, list)
        assert len(dets) >= 1
        for d_ in dets:
            assert 0 <= d_.cls_id < 12
            assert d_.disease["name_cn"]

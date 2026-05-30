"""device_profile 决策矩阵单元测试"""

import pytest


def _hw(cpu_p=8, ram=16, avx2=True, has_cuda=False, gpu=""):
    """造一个 HardwareProfile"""
    from lingnan.core.device_profile import HardwareProfile
    return HardwareProfile(
        cpu_count_physical=cpu_p,
        cpu_count_logical=cpu_p * 2,
        has_avx2=avx2,
        total_ram_gb=ram,
        available_ram_gb=ram * 0.7,
        has_cuda=has_cuda,
        gpu_name=gpu,
    )


def _setup_models(tmp_path, files: list[str]) -> "pytest.MonkeyPatch":
    """在 tmp_path 创建若干模型文件占位"""
    for f in files:
        (tmp_path / f).write_bytes(b"fake-model")
    return tmp_path


def test_high_end_cpu_no_gpu_picks_fp32(tmp_path, monkeypatch):
    """高配 CPU + 无 GPU + 有 FP32 ONNX → 选 FP32"""
    from lingnan.core import device_profile as dp
    _setup_models(tmp_path, [
        "yolov8s_xh_best.onnx",
        "yolov8s_xh_best_int8.onnx",
    ])
    d = dp.decide_tier(forced=dp.TIER_AUTO,
                        hardware=_hw(cpu_p=8, ram=16, avx2=True, has_cuda=False),
                        models_dir=tmp_path)
    assert d.chosen_tier == dp.TIER_FP32
    assert d.chosen_file.name == "yolov8s_xh_best.onnx"


def test_low_end_cpu_picks_int8(tmp_path):
    """低配 CPU（仅 2 核 / 4G RAM）→ 选 INT8"""
    from lingnan.core import device_profile as dp
    _setup_models(tmp_path, [
        "yolov8s_xh_best.onnx",
        "yolov8s_xh_best_int8.onnx",
    ])
    d = dp.decide_tier(forced=dp.TIER_AUTO,
                        hardware=_hw(cpu_p=2, ram=4, avx2=True, has_cuda=False),
                        models_dir=tmp_path)
    assert d.chosen_tier == dp.TIER_INT8


def test_no_avx2_picks_int8(tmp_path):
    """无 AVX2 → 不应选 FP32（FP32 在无 AVX2 上慢）"""
    from lingnan.core import device_profile as dp
    _setup_models(tmp_path, [
        "yolov8s_xh_best.onnx",
        "yolov8s_xh_best_int8.onnx",
    ])
    d = dp.decide_tier(forced=dp.TIER_AUTO,
                        hardware=_hw(cpu_p=8, ram=16, avx2=False, has_cuda=False),
                        models_dir=tmp_path)
    assert d.chosen_tier == dp.TIER_INT8


def test_has_gpu_picks_pt(tmp_path):
    """有 GPU + 有 PT → 选 PT"""
    from lingnan.core import device_profile as dp
    _setup_models(tmp_path, [
        "yolov8s_xh_best.pt",
        "yolov8s_xh_best_int8.onnx",
    ])
    d = dp.decide_tier(forced=dp.TIER_AUTO,
                        hardware=_hw(has_cuda=True, gpu="RTX 3060"),
                        models_dir=tmp_path)
    assert d.chosen_tier == dp.TIER_PT


def test_no_models_picks_mock(tmp_path):
    """无任何模型 → Mock"""
    from lingnan.core import device_profile as dp
    d = dp.decide_tier(forced=dp.TIER_AUTO,
                        hardware=_hw(),
                        models_dir=tmp_path)
    assert d.chosen_tier == dp.TIER_MOCK
    assert d.chosen_file is None


def test_user_lock_fp32(tmp_path):
    """用户锁定 FP32 → 不管硬件如何都选 FP32"""
    from lingnan.core import device_profile as dp
    _setup_models(tmp_path, ["yolov8s_xh_best.onnx", "yolov8s_xh_best_int8.onnx"])
    d = dp.decide_tier(forced=dp.TIER_FP32,
                        hardware=_hw(cpu_p=2, ram=4),   # 即使低端
                        models_dir=tmp_path)
    assert d.chosen_tier == dp.TIER_FP32
    assert d.auto_picked is False


def test_user_lock_missing_file_degrades(tmp_path):
    """锁定 PT 但 PT 文件缺失 → 自动降级（auto_picked=False 但 chosen 是降级后档位）"""
    from lingnan.core import device_profile as dp
    # 只放 INT8
    _setup_models(tmp_path, ["yolov8s_xh_best_int8.onnx"])
    d = dp.decide_tier(forced=dp.TIER_PT,
                        hardware=_hw(has_cuda=True),
                        models_dir=tmp_path)
    # 没有 .pt，应降级到 INT8 或 FP32
    assert d.chosen_tier == dp.TIER_INT8
    assert d.auto_picked is False   # 标记为非纯自动


def test_lock_mock_works(tmp_path):
    """用户锁定 Mock 应直接 Mock，不需要任何文件"""
    from lingnan.core import device_profile as dp
    _setup_models(tmp_path, ["yolov8s_xh_best_int8.onnx"])  # 即使有
    d = dp.decide_tier(forced=dp.TIER_MOCK,
                        hardware=_hw(),
                        models_dir=tmp_path)
    assert d.chosen_tier == dp.TIER_MOCK


def test_candidates_found_dict(tmp_path):
    """决策时应同时列出每档可用文件供 UI 展示"""
    from lingnan.core import device_profile as dp
    _setup_models(tmp_path, ["yolov8s_xh_best_int8.onnx"])
    d = dp.decide_tier(forced=dp.TIER_AUTO,
                        hardware=_hw(),
                        models_dir=tmp_path)
    assert d.candidates_found[dp.TIER_INT8] is not None
    assert d.candidates_found[dp.TIER_FP32] is None
    assert d.candidates_found[dp.TIER_PT] is None


def test_reason_non_empty(tmp_path):
    """每个决策都应有可读的 reason"""
    from lingnan.core import device_profile as dp
    d = dp.decide_tier(forced=dp.TIER_AUTO,
                        hardware=_hw(),
                        models_dir=tmp_path)
    assert d.reason
    assert len(d.reason) > 5

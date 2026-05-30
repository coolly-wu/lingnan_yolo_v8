"""知识库 + 处方种子完整性测试"""

import pytest


def test_seed_yields_60_rows():
    from xhgan.data import prescriptions_seed as seed
    rows = list(seed.iter_seed_rows())
    assert len(rows) == 60  # 12 类 × 5 物候期


def test_knowledge_base_init_seeds(tmp_path):
    from xhgan.data.knowledge_base import KnowledgeBase
    db = tmp_path / "kb.db"
    kb = KnowledgeBase(db)
    assert kb.count() == 60
    # 重复初始化不应重复种入
    kb2 = KnowledgeBase(db)
    assert kb2.count() == 60


@pytest.mark.parametrize("disease_id", list(range(12)))
@pytest.mark.parametrize("phase_key", [
    "sprout", "flower", "young_fruit", "enlargement", "harvest",
])
def test_every_combo_lookup(tmp_path, disease_id, phase_key):
    """12×5=60 组合每一组都应能查到方案"""
    from xhgan.data.knowledge_base import KnowledgeBase
    kb = KnowledgeBase(tmp_path / "kb.db")
    rx = kb.lookup(disease_id, phase_key)
    assert rx is not None
    assert rx["disease_id"] == disease_id
    assert rx["phenophase_key"] == phase_key
    # 必须有三大块
    assert isinstance(rx["chemical"], list)


def test_chemical_required_fields(tmp_path):
    """技术规范 §8.8.2：化学处方四要素 name/dosage/phi/notes"""
    from xhgan.data.knowledge_base import KnowledgeBase
    kb = KnowledgeBase(tmp_path / "kb.db")
    seen = 0
    for did in range(12):
        for phase in ["sprout", "flower", "young_fruit", "enlargement", "harvest"]:
            rx = kb.lookup(did, phase)
            for chem in rx.get("chemical", []) or []:
                for key in ("name", "dosage", "phi", "notes"):
                    assert key in chem, f"missing {key} in disease={did} phase={phase}"
                    assert chem[key], f"empty {key} in disease={did} phase={phase}"
                seen += 1
    assert seen > 0


def test_hlb_chemical_warning(tmp_path):
    """黄龙病严重情况下文档要求显式提醒砍除"""
    from xhgan.data.knowledge_base import KnowledgeBase
    kb = KnowledgeBase(tmp_path / "kb.db")
    for phase in ["sprout", "young_fruit", "harvest"]:
        rx = kb.lookup(0, phase)
        amp = rx.get("severity_amplifier") or ""
        joined = (rx.get("physical") or "") + amp
        assert "砍除" in joined or "确诊" in joined, \
            f"黄龙病 {phase} 处方未提到砍除/确诊：{joined}"


def test_fallback_to_any_phenophase(tmp_path):
    """未知物候期应 fallback 到任意一条"""
    from xhgan.data.knowledge_base import KnowledgeBase
    kb = KnowledgeBase(tmp_path / "kb.db")
    rx = kb.lookup(0, "nonexistent_phase")
    assert rx is not None
    assert rx["disease_id"] == 0

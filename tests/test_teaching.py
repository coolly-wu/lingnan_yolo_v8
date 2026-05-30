"""教研内容生成核心（teaching）测试 —— 纯函数，无 Qt / 无网络"""

import pytest


def _summary(primary_id=5, name="柑橘红蜘蛛", severity="Amber"):
    return {
        "primary_id": primary_id,
        "primary_name_cn": name,
        "primary_conf": 0.91,
        "count": 12,
        "area_ratio": 0.08,
        "severity": severity,
        "has_fatal": primary_id == 0,
        "per_class": {
            primary_id: {
                "cls_id": primary_id, "name_cn": name, "count": 12,
                "max_conf": 0.91, "area_sum": 100.0, "is_fatal": primary_id == 0,
                "is_swarm": True, "area_ratio": 0.08,
            }
        },
    }


def _rx():
    return {
        "disease_name_cn": "柑橘红蜘蛛",
        "phenophase_name_cn": "生理落果期/幼果期",
        "physical": "悬挂黄板 20 张/亩",
        "biological": "释放捕食螨 1 万头/亩",
        "chemical": [
            {"name": "螺螨酯 240 g/L 悬浮剂", "dosage": "2000~3000 倍液",
             "phi": "21 天", "notes": "请勿与碱性农药混用"},
        ],
        "severity_amplifier": "重度时增加一次轮换用药",
    }


def test_template_fill_case_has_sections():
    from lingnan.core import teaching
    ctx = teaching.build_context(_summary(), 18, "young_fruit",
                                 "生理落果期/幼果期", _rx())
    md = teaching.template_fill(teaching.DOC_CASE, ctx)
    assert "病情概述" in md
    assert "三位一体" in md
    assert "PHI" in md
    assert "21 天" in md
    assert "教学要点" in md


def test_template_fill_case_huanglongbing_warns_cut():
    from lingnan.core import teaching
    ctx = teaching.build_context(_summary(0, "柑橘黄龙病", "Red"), 3,
                                 "young_fruit", "生理落果期/幼果期", _rx())
    md = teaching.template_fill(teaching.DOC_CASE, ctx)
    assert "砍除" in md
    assert "禁止" in md


def test_template_fill_training_has_table():
    from lingnan.core import teaching
    ctx = teaching.build_context(_summary(), 18, "young_fruit",
                                 "生理落果期/幼果期", _rx())
    md = teaching.template_fill(teaching.DOC_TRAINING, ctx)
    assert "观察记录表" in md
    assert "|" in md            # markdown 表格
    assert "安全注意事项" in md
    assert "考核要点" in md


def test_template_fill_no_detection():
    from lingnan.core import teaching
    empty = {
        "primary_id": None, "primary_name_cn": None, "primary_conf": 0.0,
        "count": 0, "area_ratio": 0.0, "severity": "Green",
        "has_fatal": False, "per_class": {},
    }
    ctx = teaching.build_context(empty, 0, "young_fruit",
                                 "生理落果期/幼果期", None)
    md_case = teaching.template_fill(teaching.DOC_CASE, ctx)
    md_train = teaching.template_fill(teaching.DOC_TRAINING, ctx)
    assert md_case.strip()
    assert md_train.strip()


def test_build_prompts_returns_pair():
    from lingnan.core import teaching
    ctx = teaching.build_context(_summary(), 18, "young_fruit",
                                 "生理落果期/幼果期", _rx())
    system, user = teaching.build_prompts(teaching.DOC_CASE, ctx)
    assert system.strip()
    assert user.strip()
    assert "柑橘红蜘蛛" in user


def test_template_fill_handles_missing_chemical_fields():
    from lingnan.core import teaching
    rx = _rx()
    rx["chemical"] = [{"name": "某药剂"}]  # 缺 dosage/phi/notes
    ctx = teaching.build_context(_summary(), 18, "young_fruit",
                                 "生理落果期/幼果期", rx)
    md = teaching.template_fill(teaching.DOC_CASE, ctx)  # 不应 KeyError
    assert "某药剂" in md

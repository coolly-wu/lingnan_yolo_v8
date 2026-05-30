"""台账 + 农户档案测试"""

import pytest


def test_log_insert_query(tmp_path):
    from xhgan.data.log_manager import LogManager
    lm = LogManager(tmp_path / "log.db")
    assert lm.count() == 0
    log_id = lm.insert(
        sample_source="本地导入",
        target_disease="柑橘红蜘蛛",
        confidence=0.85,
        severity_level="Amber",
        count_value=8,
        farmer_name="张三",
        orchard_block="A-12",
        phenophase="挂果期",
        prescription_snapshot=[{"name": "螺螨酯", "phi": "21 天"}],
        image_path="/tmp/a.jpg",
    )
    assert log_id > 0
    assert lm.count() == 1
    rows = lm.query()
    assert len(rows) == 1
    assert rows[0]["target_disease"] == "柑橘红蜘蛛"
    assert "螺螨酯" in rows[0]["prescription_snapshot"]


def test_log_filter_by_disease(tmp_path):
    from xhgan.data.log_manager import LogManager
    lm = LogManager(tmp_path / "log.db")
    lm.insert(sample_source="本地导入", target_disease="柑橘黄龙病",
              confidence=0.9, severity_level="Red")
    lm.insert(sample_source="本地导入", target_disease="柑橘蚜虫",
              confidence=0.7, severity_level="Green")
    rows = lm.query(disease="柑橘黄龙病")
    assert len(rows) == 1
    assert rows[0]["target_disease"] == "柑橘黄龙病"


def test_farmer_crud(tmp_path):
    from xhgan.data.farmer_manager import FarmerManager
    fm = FarmerManager(tmp_path / "fm.db")
    assert fm.count() == 0
    fid = fm.insert(farmer_name="李四", orchard_block="B-1", phone="13800001111")
    assert fid > 0
    rows = fm.list_all()
    assert len(rows) == 1
    assert rows[0]["farmer_name"] == "李四"
    # update
    fm.update(fid, phone="13900002222")
    rows = fm.list_all()
    assert rows[0]["phone"] == "13900002222"
    # delete
    fm.delete(fid)
    assert fm.count() == 0


def test_farmer_unique_constraint(tmp_path):
    """同名 + 同果园应被合并（INSERT OR REPLACE）"""
    from xhgan.data.farmer_manager import FarmerManager
    fm = FarmerManager(tmp_path / "fm.db")
    fm.insert(farmer_name="王五", orchard_block="C-3")
    fm.insert(farmer_name="王五", orchard_block="C-3", phone="13700000000")
    assert fm.count() == 1
    assert fm.list_all()[0]["phone"] == "13700000000"


def test_farmer_reject_empty_name(tmp_path):
    from xhgan.data.farmer_manager import FarmerManager
    fm = FarmerManager(tmp_path / "fm.db")
    with pytest.raises(ValueError):
        fm.insert(farmer_name="", orchard_block="A")


def test_farmer_csv_template(tmp_path):
    from xhgan.data.farmer_manager import CSV_FIELDS, FarmerManager
    fm = FarmerManager(tmp_path / "fm.db")
    template = fm.write_csv_template(tmp_path / "farmers.csv")
    text = template.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0].split(",") == CSV_FIELDS
    assert "张三" in text


def test_farmer_import_csv(tmp_path):
    from xhgan.data.farmer_manager import FarmerManager
    csv_path = tmp_path / "farmers.csv"
    csv_path.write_text(
        "农户姓名,果园区块,联系电话,果园位置,备注\n"
        "张三,A-1,13800000000,廉江市某镇某村,5亩红橙园\n"
        "李四,B-2,13900000000,廉江市另一村,\n",
        encoding="utf-8-sig",
    )
    fm = FarmerManager(tmp_path / "fm.db")
    result = fm.import_csv(csv_path)
    assert result.imported == 2
    assert result.skipped == 0
    rows = fm.list_all()
    assert len(rows) == 2
    assert rows[0]["farmer_name"] == "张三"
    assert rows[0]["phone"] == "13800000000"


def test_farmer_import_csv_missing_required_column(tmp_path):
    from xhgan.data.farmer_manager import FarmerManager
    csv_path = tmp_path / "farmers.csv"
    csv_path.write_text(
        "农户姓名,果园区块,联系电话,备注\n"
        "张三,A-1,13800000000,5亩红橙园\n",
        encoding="utf-8-sig",
    )
    fm = FarmerManager(tmp_path / "fm.db")
    with pytest.raises(ValueError, match="果园位置"):
        fm.import_csv(csv_path)


def test_farmer_import_csv_missing_required_value(tmp_path):
    from xhgan.data.farmer_manager import FarmerManager
    csv_path = tmp_path / "farmers.csv"
    csv_path.write_text(
        "农户姓名,果园区块,联系电话,果园位置,备注\n"
        "张三,A-1,,廉江市某镇某村,5亩红橙园\n"
        "李四,B-2,13900000000,廉江市另一村,\n",
        encoding="utf-8-sig",
    )
    fm = FarmerManager(tmp_path / "fm.db")
    result = fm.import_csv(csv_path)
    assert result.imported == 1
    assert result.skipped == 1
    assert "联系电话" in result.errors[0]
    assert fm.count() == 1


def test_farmer_import_csv_upsert_duplicate(tmp_path):
    from xhgan.data.farmer_manager import FarmerManager
    csv_path = tmp_path / "farmers.csv"
    csv_path.write_text(
        "农户姓名,果园区块,联系电话,果园位置,备注\n"
        "王五,C-3,13700000000,廉江市旧村,旧资料\n"
        "王五,C-3,13600000000,廉江市新村,新资料\n",
        encoding="utf-8-sig",
    )
    fm = FarmerManager(tmp_path / "fm.db")
    result = fm.import_csv(csv_path)
    assert result.imported == 2
    assert fm.count() == 1
    row = fm.list_all()[0]
    assert row["phone"] == "13600000000"
    assert row["location"] == "廉江市新村"

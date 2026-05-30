"""Settings 读写测试"""

import pytest


def test_default_settings():
    from xhgan.settings import Settings
    s = Settings()
    assert s.font_scale == 1.0
    assert 0.05 <= s.default_conf <= 1.0


def test_save_load_roundtrip(tmp_path, monkeypatch):
    import xhgan.settings as ss

    fake_file = tmp_path / "settings.json"
    monkeypatch.setattr(ss, "SETTINGS_FILE", fake_file)

    s = ss.Settings(font_scale=1.4, default_conf=0.5,
                    auto_save_log=False, last_farmer="测试农户")
    ss.save_settings(s)
    assert fake_file.exists()
    s2 = ss.load_settings()
    assert s2.font_scale == 1.4
    assert s2.default_conf == 0.5
    assert s2.auto_save_log is False
    assert s2.last_farmer == "测试农户"


def test_load_missing_returns_default(tmp_path, monkeypatch):
    import xhgan.settings as ss
    monkeypatch.setattr(ss, "SETTINGS_FILE", tmp_path / "absent.json")
    s = ss.load_settings()
    assert s.font_scale == 1.0


def test_load_corrupted_returns_default(tmp_path, monkeypatch):
    import xhgan.settings as ss
    f = tmp_path / "settings.json"
    f.write_text("not a json {", encoding="utf-8")
    monkeypatch.setattr(ss, "SETTINGS_FILE", f)
    s = ss.load_settings()
    assert s.font_scale == 1.0

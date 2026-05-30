"""Settings 读写测试"""

import pytest


def test_default_settings():
    from lingnan.settings import Settings
    s = Settings()
    assert s.font_scale == 1.0
    assert 0.05 <= s.default_conf <= 1.0


def test_save_load_roundtrip(tmp_path, monkeypatch):
    import lingnan.settings as ss

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
    import lingnan.settings as ss
    monkeypatch.setattr(ss, "SETTINGS_FILE", tmp_path / "absent.json")
    s = ss.load_settings()
    assert s.font_scale == 1.0


def test_load_corrupted_returns_default(tmp_path, monkeypatch):
    import lingnan.settings as ss
    f = tmp_path / "settings.json"
    f.write_text("not a json {", encoding="utf-8")
    monkeypatch.setattr(ss, "SETTINGS_FILE", f)
    s = ss.load_settings()
    assert s.font_scale == 1.0


def test_llm_settings_roundtrip(tmp_path, monkeypatch):
    import lingnan.settings as ss
    monkeypatch.setattr(ss, "SETTINGS_FILE", tmp_path / "settings.json")
    s = ss.Settings(llm_enabled=True, llm_mode="cloud",
                    llm_base_url="https://api.deepseek.com/v1",
                    llm_api_key="sk-xxx", llm_model="deepseek-chat")
    ss.save_settings(s)
    s2 = ss.load_settings()
    assert s2.llm_enabled is True
    assert s2.llm_mode == "cloud"
    assert s2.llm_base_url == "https://api.deepseek.com/v1"
    assert s2.llm_api_key == "sk-xxx"
    assert s2.llm_model == "deepseek-chat"


def test_llm_mode_invalid_falls_back():
    from lingnan.settings import Settings
    s = Settings.from_json('{"llm_mode": "bogus"}')
    assert s.llm_mode == "local"


def test_old_settings_json_still_loads():
    # 旧配置文件（无任何 llm_* 键）应按默认加载，向后兼容
    from lingnan.settings import Settings
    s = Settings.from_json('{"font_scale": 1.2, "default_conf": 0.3}')
    assert s.font_scale == 1.2
    assert s.llm_enabled is False
    assert s.llm_mode == "local"
    assert s.llm_base_url == "http://localhost:11434/v1"

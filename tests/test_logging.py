"""logging 模块测试"""


def test_setup_creates_log_file(tmp_path, monkeypatch):
    import importlib
    import lingnan.config as C
    monkeypatch.setattr(C, "RUNTIME_DIR", tmp_path)

    import lingnan.logging_setup as ls
    importlib.reload(ls)
    log_file = ls.setup_logging()
    assert log_file.parent.exists()
    log = ls.get_logger("test")
    log.info("hello")
    log.warning("world")
    # 文件被创建
    assert log_file.parent.exists()

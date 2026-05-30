"""pytest fixtures：临时目录隔离 + numpy stub"""

import sys
import tempfile
import types
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path: Path):
    """提供一个干净的 SQLite 数据库路径"""
    return tmp_path / "test.db"


@pytest.fixture
def numpy_stub(monkeypatch):
    """若 numpy 未安装，提供一个最小 stub 使得 inferencer 导入不挂"""
    try:
        import numpy  # noqa
        return
    except ImportError:
        pass
    np_stub = types.ModuleType("numpy")
    np_stub.ndarray = object
    monkeypatch.setitem(sys.modules, "numpy", np_stub)

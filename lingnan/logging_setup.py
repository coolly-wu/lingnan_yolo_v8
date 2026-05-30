"""统一 logging 配置：写文件 + 控制台

启动应用时调用 setup_logging() 即可。日志写到 runtime_data/logs/lingnan-YYYY-MM-DD.log
"""

from __future__ import annotations

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

from . import config as C


LOG_DIR = C.RUNTIME_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


_setup_done = False


def setup_logging(level: int = logging.INFO) -> Path:
    """配置全局日志。返回当天日志文件路径。"""
    global _setup_done
    log_file = LOG_DIR / f"lingnan-{datetime.now():%Y-%m-%d}.log"
    if _setup_done:
        return log_file

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)

    # 文件 handler（按天滚动，保留 14 天）
    fh = logging.handlers.TimedRotatingFileHandler(
        str(log_file), when="midnight", backupCount=14, encoding="utf-8",
    )
    fh.setFormatter(formatter)
    fh.setLevel(level)
    root.addHandler(fh)

    # 控制台 handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(level)
    root.addHandler(ch)

    _setup_done = True
    logging.getLogger("lingnan").info("=== 应用启动，日志写入 %s ===", log_file)
    return log_file


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

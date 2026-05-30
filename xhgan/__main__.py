"""应用入口"""

from __future__ import annotations

import logging
import os
import sys

from . import config as C
from .core import device_profile as dp
from .core.inferencer import Inferencer
from .logging_setup import setup_logging


def main():
    setup_logging(level=logging.INFO)
    cfg_dir = C.RUNTIME_DIR / "ultralytics"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(cfg_dir))
    os.environ.setdefault("MPLCONFIGDIR", str(cfg_dir / "matplotlib"))

    settings = __import__("lingnan.settings", fromlist=["load_settings"]).load_settings()
    decision = dp.decide_tier(forced=settings.perf_tier)
    inferencer = Inferencer(decision=decision)

    from PyQt5.QtWidgets import QApplication
    from .ui.main_window import MainWindow
    from .ui.fluent import apply_app_font, apply_fluent_theme
    from .ui.style import STYLE_SHEET

    app = QApplication(sys.argv)
    apply_app_font(app)
    apply_fluent_theme()
    app.setStyleSheet(STYLE_SHEET)
    w = MainWindow(inferencer=inferencer, decision=decision)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

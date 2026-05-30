"""About page with Fluent typography."""

from __future__ import annotations

import platform

from PyQt5.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from .. import __app_name__, __version__
from .fluent import (
    BodyLabel,
    CaptionLabel,
    LargeTitleLabel,
    WEIGHT_BOLD,
    fluent_card,
    setFont,
)


class AboutPage(QWidget):
    def __init__(self, model_info: str, kb_count: int, log_count: int):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(18)

        title = LargeTitleLabel(__app_name__)
        setFont(title, 28, WEIGHT_BOLD)
        lay.addWidget(title)
        cap = CaptionLabel(f"版本 v{__version__} · 本地离线智能检测防治工作台")
        cap.setStyleSheet("color:#6B7280;")
        lay.addWidget(cap)

        ability_card, ability_lay = fluent_card("系统能力")
        ability = BodyLabel(
            "12 类廉江红橙高发病虫害本地识别；三位一体绿色防治方案自动推送；"
            "果树物候期联动；UVC 摄像头实时检测；本地 SQLite 台账与 Excel/PDF 导出。"
        )
        ability.setWordWrap(True)
        ability_lay.addWidget(ability)
        lay.addWidget(ability_card)

        model_card, model_lay = fluent_card("当前模型")
        model = BodyLabel(model_info)
        model.setWordWrap(True)
        model.setTextFormat(1)
        model_lay.addWidget(model)
        lay.addWidget(model_card)

        data_card, data_lay = fluent_card("本地数据")
        data = BodyLabel(f"知识库处方条目：{kb_count}\n已记录检测日志：{log_count}")
        data_lay.addWidget(data)
        lay.addWidget(data_card)

        env_card, env_lay = fluent_card("运行环境")
        env = BodyLabel(f"操作系统：{platform.platform()}\nPython：{platform.python_version()}")
        env_lay.addWidget(env)
        lay.addWidget(env_card)
        lay.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

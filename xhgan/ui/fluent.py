"""Fluent Design component aliases and app theme helpers."""

from __future__ import annotations

from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    CheckBox,
    ComboBox,
    DoubleSpinBox,
    FluentIcon,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LargeTitleLabel,
    LineEdit,
    ListWidget,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    SimpleCardWidget,
    SpinBox,
    StrongBodyLabel,
    SubtitleLabel,
    TableWidget,
    TextEdit,
    Theme,
    TitleLabel,
    TransparentPushButton,
    setFont,
    setTheme,
    setThemeColor,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QWidget


FONT_FAMILY = ["Segoe UI", "Microsoft YaHei", "PingFang SC"]
WEIGHT_NORMAL = QFont.Normal
WEIGHT_SEMIBOLD = QFont.DemiBold
WEIGHT_BOLD = QFont.Bold


def apply_fluent_theme() -> None:
    """Apply a light Microsoft Fluent visual baseline."""
    setTheme(Theme.LIGHT)
    setThemeColor("#0F6CBD")


def apply_app_font(widget: QWidget) -> None:
    font = QFont()
    font.setFamilies(FONT_FAMILY)
    font.setPixelSize(14)
    widget.setFont(font)


def page_container(parent: QWidget | None = None) -> QWidget:
    page = QWidget(parent)
    lay = QVBoxLayout(page)
    lay.setContentsMargins(32, 32, 32, 32)
    lay.setSpacing(18)
    return page


def page_layout(page: QWidget) -> QVBoxLayout:
    return page.layout()  # type: ignore[return-value]


def fluent_card(title: str | None = None, caption: str | None = None) -> tuple[SimpleCardWidget, QVBoxLayout]:
    card = SimpleCardWidget()
    lay = QVBoxLayout(card)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(12)
    if title:
        label = SubtitleLabel(title)
        setFont(label, 16, WEIGHT_SEMIBOLD)
        lay.addWidget(label)
    if caption:
        cap = CaptionLabel(caption)
        cap.setStyleSheet("color:#6B7280;")
        setFont(cap, 11, WEIGHT_NORMAL)
        cap.setWordWrap(True)
        lay.addWidget(cap)
    return card, lay


def set_body_font(widget: QWidget) -> None:
    setFont(widget, 14, WEIGHT_NORMAL)


def set_caption_font(widget: QWidget) -> None:
    setFont(widget, 11, WEIGHT_NORMAL)


def make_primary_button(text: str) -> PrimaryPushButton:
    return PrimaryPushButton(text)


def make_secondary_button(text: str) -> PushButton:
    return PushButton(text)

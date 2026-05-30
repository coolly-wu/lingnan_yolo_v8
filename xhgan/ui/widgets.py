"""共用控件：图像显示、处方面板、QPixmap 转换"""

from __future__ import annotations

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from .fluent import (
    BodyLabel,
    CaptionLabel,
    SimpleCardWidget,
    SubtitleLabel,
    TextEdit,
    WEIGHT_BOLD,
    WEIGHT_SEMIBOLD,
    setFont,
)

from .. import config as C


def cv2_to_qpixmap(img_bgr: np.ndarray) -> QPixmap:
    if img_bgr is None or img_bgr.size == 0:
        return QPixmap()
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class ImageView(QLabel):
    """自适应缩放的图像显示控件"""

    def __init__(self, placeholder: str = "（未加载图片）"):
        super().__init__(placeholder)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background:#212121; color:#9E9E9E;"
            "border-radius: 8px;"
        )
        setFont(self, 14)
        self.setMinimumSize(320, 220)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._raw: np.ndarray | None = None

    def set_cv_image(self, img_bgr: np.ndarray | None):
        self._raw = img_bgr
        self._render()

    def clear_image(self):
        self._raw = None
        self.setPixmap(QPixmap())
        self.setText("（未加载图片）")

    def _render(self):
        if self._raw is None:
            return
        pix = cv2_to_qpixmap(self._raw)
        scaled = pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._raw is not None:
            self._render()


class PrescriptionView(QScrollArea):
    """三位一体绿色处方展示"""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self._inner = QWidget()
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(12)
        self.setWidget(self._inner)
        self.clear()

    def clear(self):
        while self._lay.count():
            it = self._lay.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
        hint = CaptionLabel("选择病虫害类别 + 物候期后将展示三位一体绿色处方")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#757575; padding:24px;")
        self._lay.addWidget(hint)
        self._lay.addStretch(1)

    def show_prescription(self, rx: dict | None, severity: str | None = None):
        """rx 来自 KnowledgeBase.lookup()"""
        while self._lay.count():
            it = self._lay.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)

        if rx is None:
            warn = BodyLabel("知识库未匹配到对应物候期防治方案，请联系农业技术顾问。")
            warn.setStyleSheet("color:#C62828; font-weight:bold; padding:24px;")
            warn.setWordWrap(True)
            self._lay.addWidget(warn)
            self._lay.addStretch(1)
            return

        title = SubtitleLabel(
            f"【{rx['disease_name_cn']}】· {rx['phenophase_name_cn']} · "
            f"三位一体绿色防治方案"
        )
        title.setStyleSheet("color:#107C10; padding:6px;")
        setFont(title, 16, WEIGHT_SEMIBOLD)
        title.setWordWrap(True)
        self._lay.addWidget(title)

        if severity == C.SEVERITY_RED:
            tip = QLabel("⚠ 当前严重程度【重度】，请优先执行下方加强措施。")
            tip.setObjectName("severity_red")
            tip.setStyleSheet(
                "background:#FFCDD2; color:#B71C1C; border-radius:6px;"
                "padding:8px 16px; font-weight:bold; font-size:14pt;"
            )
            self._lay.addWidget(tip)

        self._lay.addWidget(_box("A · 物理防治（优先）", rx["physical"], "#2E7D32"))
        self._lay.addWidget(_box("B · 生物防治（安全）", rx["biological"], "#1565C0"))
        self._lay.addWidget(_chemical_box(rx["chemical"]))
        if rx.get("severity_amplifier"):
            self._lay.addWidget(_box(
                "重度场景加强方案", rx["severity_amplifier"], "#C62828",
            ))
        self._lay.addStretch(1)


def _box(title: str, content: str, color: str) -> SimpleCardWidget:
    box = SimpleCardWidget()
    box.setStyleSheet(
        f"SimpleCardWidget {{ border-left:4px solid {color}; }}"
    )
    lay = QVBoxLayout(box)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(8)
    title_label = SubtitleLabel(title)
    title_label.setStyleSheet(f"color:{color};")
    setFont(title_label, 16, WEIGHT_SEMIBOLD)
    lay.addWidget(title_label)
    label = BodyLabel(content or "—")
    label.setWordWrap(True)
    lay.addWidget(label)
    return box


def _chemical_box(chem_list: list[dict]) -> SimpleCardWidget:
    box = SimpleCardWidget()
    box.setStyleSheet(
        "SimpleCardWidget { border-left:4px solid #EF6C00; }"
    )
    lay = QVBoxLayout(box)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(8)
    title = SubtitleLabel("C · 科学化学防治（低毒合规）")
    title.setStyleSheet("color:#EF6C00;")
    setFont(title, 16, WEIGHT_SEMIBOLD)
    lay.addWidget(title)
    if not chem_list:
        lay.addWidget(BodyLabel("无须化学药剂（优先物理 + 生物防治）"))
        return box
    for i, c in enumerate(chem_list, 1):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#FFE0B2;")
        sub = QVBoxLayout()
        sub.setSpacing(2)
        name = SubtitleLabel(f"推荐药剂 {i}：{c.get('name', '—')}")
        name.setStyleSheet("color:#BF360C;")
        setFont(name, 16, WEIGHT_SEMIBOLD)
        dosage = BodyLabel(f"用量：{c.get('dosage', '—')}")
        dosage.setWordWrap(True)
        phi = QLabel(f"⏰ 安全间隔期（PHI）：{c.get('phi', '—')}")
        phi.setStyleSheet(
            "background:#FFF59D; color:#C62828; font-weight:bold;"
            "padding:4px 8px; border-radius:4px; font-size:14pt;"
        )
        notes = CaptionLabel(f"注意事项：{c.get('notes', '—')}")
        notes.setWordWrap(True)
        notes.setStyleSheet("color:#5D4037;")
        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(8, 6, 8, 6)
        wl.setSpacing(4)
        wl.addWidget(name)
        wl.addWidget(dosage)
        wl.addWidget(phi)
        wl.addWidget(notes)
        lay.addWidget(wrapper)
        if i < len(chem_list):
            lay.addWidget(line)
    return box


class SeverityChip(QLabel):
    """严重程度色码胶囊"""

    def __init__(self):
        super().__init__("—")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(40)
        self.setWordWrap(True)
        self.set_severity(None)

    def set_severity(self, sev: str | None):
        if sev is None:
            self.setObjectName("")
            self.setText("严重程度：—")
            self.setStyleSheet(
                "background:#ECEFF1; color:#757575; border-radius:6px;"
                "padding:8px 12px; font-weight:600;"
            )
            return
        cn = C.SEVERITY_LABELS_CN.get(sev, sev)
        self.setText(f"严重程度：{cn}")
        obj = {"Green": "severity_green", "Amber": "severity_amber", "Red": "severity_red"}.get(sev, "")
        self.setObjectName(obj)
        # 强制刷新样式
        self.style().unpolish(self)
        self.style().polish(self)

"""设置页：字体倍率、默认阈值、保存目录、自动保存、性能档"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from .fluent import (
    CaptionLabel,
    LargeTitleLabel,
    LineEdit,
    ComboBox,
    DoubleSpinBox,
    PrimaryPushButton,
    CheckBox,
    TransparentPushButton,
    WEIGHT_BOLD,
    fluent_card,
    setFont,
)

from .. import config as C
from ..core import device_profile as dp
from ..settings import Settings, save_settings


class SettingsPage(QWidget):
    """全局设置编辑页"""

    settings_changed = pyqtSignal(Settings)

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self._build_ui()
        self._fill_from(settings)

    def _build_ui(self):
        # 字体
        font_box, font_lay = fluent_card("字体大小", "调整适老化显示比例。")
        font_form = QFormLayout()
        self.font_combo = ComboBox()
        self.font_combo.addItem("标准 (100%)", userData=1.0)
        self.font_combo.addItem("大 (120%)", userData=1.2)
        self.font_combo.addItem("更大 (140%)", userData=1.4)
        self.font_combo.addItem("最大 (160%)", userData=1.6)
        self.font_combo.addItem("紧凑 (80%)", userData=0.8)
        font_form.addRow("字体倍率：", self.font_combo)
        font_lay.addLayout(font_form)

        # 性能档
        perf_box, perf_lay = fluent_card("性能档位", "根据硬件与模型文件选择推理后端。")
        perf_form = QFormLayout()
        self.perf_combo = ComboBox()
        self.perf_combo.addItem("🤖 自动（依硬件挑选，推荐）", userData=dp.TIER_AUTO)
        self.perf_combo.addItem("🚀 PT · GPU 高精度", userData=dp.TIER_PT)
        self.perf_combo.addItem("🎯 FP32 · CPU 高精度", userData=dp.TIER_FP32)
        self.perf_combo.addItem("⚡ INT8 · CPU 高速度", userData=dp.TIER_INT8)
        self.perf_combo.addItem("🧪 Mock · 仅演示（无模型时）", userData=dp.TIER_MOCK)
        self.perf_combo.currentIndexChanged.connect(self._on_perf_changed)
        perf_form.addRow("当前档位：", self.perf_combo)
        perf_lay.addLayout(perf_form)

        # 探测结果展示
        self.hw_label = QLabel()
        self.hw_label.setWordWrap(True)
        self.hw_label.setStyleSheet(
            "background:#F1F8E9; color:#1B5E20; border:1px solid #C5E1A5;"
            "border-radius:6px; padding:8px 10px; font-size:11pt;"
        )
        perf_lay.addWidget(self.hw_label)

        self.tier_preview_label = QLabel()
        self.tier_preview_label.setWordWrap(True)
        self.tier_preview_label.setStyleSheet(
            "background:#FFF8E1; color:#5D4037; border:1px solid #FFE082;"
            "border-radius:6px; padding:8px 10px; font-size:11pt;"
        )
        perf_lay.addWidget(self.tier_preview_label)

        btn_probe_row = QHBoxLayout()
        self.btn_probe = TransparentPushButton("重新探测硬件")
        self.btn_probe.clicked.connect(self._refresh_hw_info)
        btn_probe_row.addWidget(self.btn_probe)
        btn_probe_row.addStretch(1)
        perf_lay.addLayout(btn_probe_row)

        # 推理阈值
        thr_box, thr_lay = fluent_card("检测默认参数")
        thr_form = QFormLayout()
        self.conf_spin = DoubleSpinBox()
        self.conf_spin.setRange(0.05, 0.95)
        self.conf_spin.setSingleStep(0.05)
        thr_form.addRow("置信度阈值 conf：", self.conf_spin)
        self.iou_spin = DoubleSpinBox()
        self.iou_spin.setRange(0.1, 0.9)
        self.iou_spin.setSingleStep(0.05)
        thr_form.addRow("IoU 阈值：", self.iou_spin)
        self.phase_combo = ComboBox()
        for p in C.PHENOPHASES:
            self.phase_combo.addItem(p["name_cn"], userData=p["key"])
        thr_form.addRow("默认物候期：", self.phase_combo)
        thr_lay.addLayout(thr_form)

        # 保存目录
        save_box, save_lay = fluent_card("默认保存目录")
        sv = QHBoxLayout()
        sv.setSpacing(12)
        self.save_dir_input = LineEdit()
        self.save_dir_input.setPlaceholderText(
            f"留空则使用 {C.EXPORT_DIR}"
        )
        sv.addWidget(self.save_dir_input, 1)
        self.btn_browse = TransparentPushButton("浏览")
        self.btn_browse.clicked.connect(self._on_browse)
        sv.addWidget(self.btn_browse)
        save_lay.addLayout(sv)

        # 行为
        beh_box, beh_lay = fluent_card("行为开关")
        self.cb_auto_save = CheckBox("自动把检测结果写入历史台账")
        self.cb_sound = CheckBox("重度病害弹窗时播放提示音")
        beh_lay.addWidget(self.cb_auto_save)
        beh_lay.addWidget(self.cb_sound)

        # 提示
        hint = QLabel(
            "💡 设置会立即生效（字体倍率需 Tab 切换刷新一次；"
            "性能档位的切换需要重启应用或【加载模型】按钮才会让推理后端真正换档）。"
            f" 持久化到 {C.RUNTIME_DIR / 'settings.json'}"
        )
        hint.setStyleSheet("color:#757575;")
        hint.setWordWrap(True)

        # 按钮
        btns = QHBoxLayout()
        btns.setSpacing(12)
        self.btn_save = PrimaryPushButton("保存设置")
        self.btn_save.clicked.connect(self._on_save)
        btns.addWidget(self.btn_save)
        self.btn_reset = TransparentPushButton("恢复默认")
        self.btn_reset.clicked.connect(self._on_reset)
        btns.addWidget(self.btn_reset)
        btns.addStretch(1)

        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(32, 32, 32, 32)
        content_lay.setSpacing(18)
        title = LargeTitleLabel("设置")
        setFont(title, 28, WEIGHT_BOLD)
        content_lay.addWidget(title)
        cap = CaptionLabel("管理字体、性能档位、默认阈值和保存行为。")
        cap.setStyleSheet("color:#6B7280;")
        content_lay.addWidget(cap)
        content_lay.addWidget(font_box)
        content_lay.addWidget(perf_box)
        content_lay.addWidget(thr_box)
        content_lay.addWidget(save_box)
        content_lay.addWidget(beh_box)
        content_lay.addLayout(btns)
        content_lay.addWidget(hint)
        content_lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(scroll)

        # 初始硬件信息
        self._refresh_hw_info()

    def _fill_from(self, s: Settings):
        # font
        for i in range(self.font_combo.count()):
            if abs(float(self.font_combo.itemData(i)) - s.font_scale) < 1e-3:
                self.font_combo.setCurrentIndex(i)
                break
        # perf tier
        for i in range(self.perf_combo.count()):
            if self.perf_combo.itemData(i) == s.perf_tier:
                self.perf_combo.setCurrentIndex(i)
                break
        self.conf_spin.setValue(s.default_conf)
        self.iou_spin.setValue(s.default_iou)
        for i in range(self.phase_combo.count()):
            if self.phase_combo.itemData(i) == s.default_phenophase:
                self.phase_combo.setCurrentIndex(i)
                break
        self.save_dir_input.setText(s.default_save_dir)
        self.cb_auto_save.setChecked(s.auto_save_log)
        self.cb_sound.setChecked(s.enable_sound)
        # 同步刷新档位预览
        self._refresh_tier_preview()

    def _on_perf_changed(self, _idx: int):
        self._refresh_tier_preview()

    def _refresh_hw_info(self):
        hw = dp.probe_hardware()
        self._hw_cache = hw
        self.hw_label.setText(
            f"<b>当前硬件：</b><br>{hw.summary}<br>"
            f"<span style='color:#5D4037;'>OS：{hw.os_name}</span>"
        )
        self._refresh_tier_preview()

    def _refresh_tier_preview(self):
        if not hasattr(self, "_hw_cache"):
            self._hw_cache = dp.probe_hardware()
        forced = self.perf_combo.currentData()
        decision = dp.decide_tier(forced=forced, hardware=self._hw_cache)
        # 列出每档可用文件
        rows = []
        labels = {
            dp.TIER_PT: "PT",
            dp.TIER_FP32: "FP32",
            dp.TIER_INT8: "INT8",
        }
        for tier in (dp.TIER_PT, dp.TIER_FP32, dp.TIER_INT8):
            p = decision.candidates_found.get(tier)
            mark = "✓" if p else "✗"
            color = "#2E7D32" if p else "#9E9E9E"
            row = f"<span style='color:{color}'>{mark} {labels[tier]}：{p.name if p else '（未找到）'}</span>"
            rows.append(row)
        files_html = "<br>".join(rows)
        # 标注最终选择
        chosen = decision.tier_label_cn
        chosen_file = decision.chosen_file
        chosen_file_html = (
            f"<br><b>选用文件：</b>{chosen_file}" if chosen_file
            else "<br><b>选用文件：</b>—（Mock 模拟器）"
        )
        self.tier_preview_label.setText(
            f"<b>预计选档：</b>{chosen}"
            f"<br><b>原因：</b>{decision.reason}"
            f"{chosen_file_html}<br><br>"
            f"<b>本机模型可用性：</b><br>{files_html}"
        )

    def _on_browse(self):
        d = QFileDialog.getExistingDirectory(self, "选择默认保存目录")
        if d:
            self.save_dir_input.setText(d)

    def _on_save(self):
        s = self.settings
        s.font_scale = float(self.font_combo.currentData())
        s.perf_tier = self.perf_combo.currentData()
        s.default_conf = float(self.conf_spin.value())
        s.default_iou = float(self.iou_spin.value())
        s.default_phenophase = self.phase_combo.currentData()
        s.default_save_dir = self.save_dir_input.text().strip()
        s.auto_save_log = bool(self.cb_auto_save.isChecked())
        s.enable_sound = bool(self.cb_sound.isChecked())
        save_settings(s)
        self.settings_changed.emit(s)
        QMessageBox.information(
            self, "已保存",
            "设置已保存。\n\n性能档位切换：可点【关于】→【📦 加载模型】"
            "或重启应用，让推理后端真正换档。",
        )

    def _on_reset(self):
        self._fill_from(Settings())

"""检测主页：图片导入 → 检测 → 处方推送 → 写入台账"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from .fluent import (
    BodyLabel,
    CaptionLabel,
    InfoBar,
    LargeTitleLabel,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    TransparentPushButton,
    LineEdit,
    ComboBox,
    DoubleSpinBox,
    TextEdit,
    ListWidget,
    ProgressBar,
    WEIGHT_BOLD,
    WEIGHT_SEMIBOLD,
    fluent_card,
    setFont,
)

from .. import config as C
from ..core.image_io import imread_unicode, imwrite_unicode
from ..core.inferencer import Detection, Inferencer
from ..data.farmer_manager import FarmerManager
from ..data.knowledge_base import KnowledgeBase
from ..data.log_manager import LogManager
from ..settings import Settings
from .widgets import ImageView, PrescriptionView, SeverityChip
from .worker import DetectWorker


class DetectionPage(QWidget):
    log_inserted = pyqtSignal(int)  # 通知台账页刷新

    def __init__(self, inferencer: Inferencer, kb: KnowledgeBase,
                 logs: LogManager, farmers: FarmerManager,
                 settings: Settings):
        super().__init__()
        self.inferencer = inferencer
        self.kb = kb
        self.logs = logs
        self.farmers = farmers
        self.settings = settings

        self.image_paths: list[str] = []
        # path -> (annotated_bgr, [Detection,...], summary, elapsed_ms)
        self.results_cache: dict[str, tuple] = {}
        self.worker: DetectWorker | None = None
        self._current_path: str | None = None

        self._build_ui()
        self.apply_settings(settings)
        self.refresh_farmers()

    # ============================================================ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(18)

        title = LargeTitleLabel("智能检测")
        setFont(title, 28, WEIGHT_BOLD)
        root.addWidget(title)
        caption = CaptionLabel("导入廉江红橙图片，离线识别病虫害并生成绿色防治方案。")
        caption.setStyleSheet("color:#6B7280;")
        root.addWidget(caption)

        # ---------- 左：控制面板 ----------
        ctrl_content = QWidget()
        cl = QVBoxLayout(ctrl_content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(18)

        farmer_card, farmer_lay = fluent_card("农户 / 果园", "可选择档案，也可以临时输入。")
        self.farmer_combo = ComboBox()
        self.farmer_combo.setPlaceholderText("选择档案（可空）")
        self.farmer_combo.currentIndexChanged.connect(self._on_farmer_picked)
        farmer_lay.addWidget(self.farmer_combo)
        self.farmer_input = LineEdit()
        self.farmer_input.setPlaceholderText("农户姓名（可空，可手动输入）")
        farmer_lay.addWidget(self.farmer_input)
        self.orchard_input = LineEdit()
        self.orchard_input.setPlaceholderText("果园区块编号（可空）")
        farmer_lay.addWidget(self.orchard_input)
        cl.addWidget(farmer_card)

        phase_card, phase_lay = fluent_card("物候期", "处方会按物候期匹配。")
        self.phase_combo = ComboBox()
        for p in C.PHENOPHASES:
            self.phase_combo.addItem(p["name_cn"], userData=p["key"])
        phase_lay.addWidget(self.phase_combo)
        cl.addWidget(phase_card)

        import_card, import_lay = fluent_card("导入图片", "支持单张、多张或文件夹批量导入。")
        self.btn_open_files = PrimaryPushButton("选择图片")
        self.btn_open_files.clicked.connect(self._on_open_files)
        import_lay.addWidget(self.btn_open_files)

        self.btn_open_dir = TransparentPushButton("选择文件夹")
        self.btn_open_dir.clicked.connect(self._on_open_dir)
        import_lay.addWidget(self.btn_open_dir)

        self.btn_clear = TransparentPushButton("清空列表")
        self.btn_clear.clicked.connect(self._on_clear)
        import_lay.addWidget(self.btn_clear)
        cl.addWidget(import_card)

        detect_card, detect_lay = fluent_card("一键检测", "调整阈值后启动本地模型推理。")
        self.btn_run = PrimaryPushButton("▶ 开始检测")
        self.btn_run.clicked.connect(self._on_run)
        detect_lay.addWidget(self.btn_run)

        detect_lay.addWidget(BodyLabel("置信度阈值 conf"))
        self.spin_conf = DoubleSpinBox()
        self.spin_conf.setRange(0.05, 0.95)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(C.DEFAULT_CONF)
        detect_lay.addWidget(self.spin_conf)
        detect_lay.addWidget(BodyLabel("IoU 阈值"))
        self.spin_iou = DoubleSpinBox()
        self.spin_iou.setRange(0.1, 0.9)
        self.spin_iou.setSingleStep(0.05)
        self.spin_iou.setValue(C.DEFAULT_IOU)
        detect_lay.addWidget(self.spin_iou)

        self.progress = ProgressBar()
        self.progress.setValue(0)
        detect_lay.addWidget(self.progress)

        self.btn_save = TransparentPushButton("保存当前结果")
        self.btn_save.clicked.connect(self._on_save_current)
        detect_lay.addWidget(self.btn_save)
        cl.addWidget(detect_card)
        cl.addStretch(1)

        ctrl = QScrollArea()
        ctrl.setWidgetResizable(True)
        ctrl.setFrameShape(QScrollArea.NoFrame)
        ctrl.setWidget(ctrl_content)

        # ---------- 中：图片列表 ----------
        self.list_widget = ListWidget()
        self.list_widget.currentItemChanged.connect(self._on_select_image)

        # ---------- 右：图像 + 详情 + 处方 ----------
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)
        self.image_view = ImageView()
        rl.addWidget(self.image_view, 3)

        info_row = QHBoxLayout()
        self.severity_chip = SeverityChip()
        info_row.addWidget(self.severity_chip, 1)
        self.timing_label = QLabel("⏱ 推理：— ms")
        self.timing_label.setStyleSheet(
            "background:#ECEFF1; color:#37474F; border-radius:6px;"
            "padding:8px 12px; font-weight:bold; font-size:13pt;"
        )
        info_row.addWidget(self.timing_label, 1)
        rl.addLayout(info_row)

        self.detail = TextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(160)
        detail_title = SubtitleLabel("检测详情")
        setFont(detail_title, 16, WEIGHT_SEMIBOLD)
        rl.addWidget(detail_title)
        rl.addWidget(self.detail)

        rx_title = SubtitleLabel("三位一体绿色防治方案")
        setFont(rx_title, 16, WEIGHT_SEMIBOLD)
        rl.addWidget(rx_title)
        self.rx_view = PrescriptionView()
        rl.addWidget(self.rx_view, 4)

        # ---------- 拼装 ----------
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(ctrl)
        splitter.addWidget(self.list_widget)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([280, 180, 760])
        root.addWidget(splitter, 1)

    # ============================================================ 业务
    def set_inferencer(self, inferencer: Inferencer):
        self.inferencer = inferencer

    def apply_settings(self, s: Settings):
        """读取设置：默认阈值 / 物候期 / 最近一次农户"""
        self.settings = s
        self.spin_conf.setValue(s.default_conf)
        self.spin_iou.setValue(s.default_iou)
        for i in range(self.phase_combo.count()):
            if self.phase_combo.itemData(i) == s.default_phenophase:
                self.phase_combo.setCurrentIndex(i)
                break
        if s.last_farmer:
            self.farmer_input.setText(s.last_farmer)
        if s.last_orchard:
            self.orchard_input.setText(s.last_orchard)

    def refresh_farmers(self):
        """从档案表刷新下拉"""
        current = self.farmer_input.text()
        self.farmer_combo.blockSignals(True)
        self.farmer_combo.clear()
        self.farmer_combo.addItem("", userData=None)
        try:
            for r in self.farmers.list_all():
                label = r["farmer_name"]
                if r.get("orchard_block"):
                    label += f"｜{r['orchard_block']}"
                self.farmer_combo.addItem(label, userData=r)
        except Exception:
            pass
        self.farmer_combo.blockSignals(False)
        if current:
            self.farmer_input.setText(current)

    def _on_farmer_picked(self, idx: int):
        data = self.farmer_combo.itemData(idx)
        if isinstance(data, dict):
            self.farmer_input.setText(data.get("farmer_name", ""))
            self.orchard_input.setText(data.get("orchard_block", ""))

    # ---------- 图片选择 ----------
    def _on_open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择廉江红橙图片", "",
            "图片 (*.jpg *.jpeg *.png *.bmp)",
        )
        if paths:
            self._add_images(paths)

    def _on_open_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if d:
            paths = [
                str(p) for p in Path(d).iterdir()
                if p.suffix.lower() in C.SUPPORTED_IMAGE_EXTS
            ]
            paths.sort()
            if paths:
                self._add_images(paths)
            else:
                InfoBar.warning("提示", "该文件夹下没有支持的图片。", duration=2500, parent=self)

    def _add_images(self, paths: list[str]):
        for p in paths:
            if p in self.image_paths:
                continue
            self.image_paths.append(p)
            self.list_widget.addItem(QListWidgetItem(Path(p).name))
        if self.list_widget.currentRow() < 0 and self.image_paths:
            self.list_widget.setCurrentRow(0)

    def _on_clear(self):
        self.image_paths.clear()
        self.results_cache.clear()
        self.list_widget.clear()
        self.image_view.clear_image()
        self.detail.clear()
        self.rx_view.clear()
        self.severity_chip.set_severity(None)
        self.timing_label.setText("⏱ 推理：— ms")
        self.progress.setValue(0)
        self._current_path = None

    # ---------- 选中切换 ----------
    def _on_select_image(self, cur: QListWidgetItem | None, _prev):
        if cur is None:
            return
        idx = self.list_widget.row(cur)
        if idx < 0 or idx >= len(self.image_paths):
            return
        path = self.image_paths[idx]
        self._current_path = path
        if path in self.results_cache:
            annotated, dets, summary, elapsed = self.results_cache[path]
            self._render_result(path, annotated, dets, summary, elapsed)
        else:
            img = imread_unicode(path)
            if img is None:
                self.image_view.setText(f"无法读取图片: {path}")
                return
            self.image_view.set_cv_image(img)
            self.detail.setPlainText(f"{path}\n（尚未检测）")
            self.rx_view.clear()
            self.severity_chip.set_severity(None)
            self.timing_label.setText("⏱ 推理：— ms")

    # ---------- 推理 ----------
    def _on_run(self):
        if not self.image_paths:
            InfoBar.warning("提示", "请先选择图片。", duration=2500, parent=self)
            return
        if self.worker is not None and self.worker.isRunning():
            InfoBar.warning("提示", "检测正在进行中…", duration=2500, parent=self)
            return
        self.progress.setValue(0)
        self.btn_run.setEnabled(False)
        self.worker = DetectWorker(
            inferencer=self.inferencer,
            image_paths=list(self.image_paths),
            conf=float(self.spin_conf.value()),
            iou=float(self.spin_iou.value()),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.one_done.connect(self._on_one_done)
        self.worker.finished_all.connect(self._on_all_done)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _on_progress(self, cur: int, total: int):
        self.progress.setMaximum(total)
        self.progress.setValue(cur)

    def _on_one_done(self, path: str, annotated, dets: list[Detection],
                     summary: dict, elapsed_ms: float):
        self.results_cache[path] = (annotated, dets, summary, elapsed_ms)
        # 保存标注图到 runtime_data/annotated
        annotated_path = C.ANNOTATED_DIR / f"{Path(path).stem}_det.jpg"
        imwrite_unicode(annotated_path, annotated, ".jpg", [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        # 写台账
        self._save_to_log(path, str(annotated_path), summary, dets)
        # 若当前正在查看这张，刷新
        if self._current_path == path:
            self._render_result(path, annotated, dets, summary, elapsed_ms)

    def _on_all_done(self):
        self.btn_run.setEnabled(True)

    def _on_worker_error(self, msg: str):
        self.btn_run.setEnabled(True)
        InfoBar.warning("检测出错", msg, duration=3500, parent=self)

    # ---------- 渲染结果 ----------
    def _render_result(self, path: str, annotated, dets: list[Detection],
                       summary: dict, elapsed_ms: float):
        self.image_view.set_cv_image(annotated)
        self.severity_chip.set_severity(summary.get("severity"))
        self.timing_label.setText(f"⏱ 推理：{elapsed_ms:.1f} ms")
        self._render_detail(path, dets, summary)
        self._render_prescription(summary)

    def _render_detail(self, path: str, dets: list[Detection], summary: dict):
        lines = [
            f"📄 文件：{path}",
            f"🔢 检出 {len(dets)} 个目标",
            f"🌿 主病害：{summary.get('primary_name_cn') or '—'}"
            f"   置信度：{summary.get('primary_conf', 0) * 100:.1f}%",
            f"📐 面积占比：{summary.get('area_ratio', 0) * 100:.2f}%",
            f"⚠ 严重程度：{C.SEVERITY_LABELS_CN.get(summary.get('severity'), '—')}",
            "",
        ]
        # 每类详细
        per_class = summary.get("per_class", {})
        if per_class:
            lines.append("【分类计数】")
            for v in sorted(per_class.values(), key=lambda x: -x["count"]):
                lines.append(
                    f"  · {v['name_cn']}：{v['count']} 个   "
                    f"max conf={v['max_conf'] * 100:.1f}%   "
                    f"面积占比={v['area_ratio'] * 100:.2f}%"
                )
        self.detail.setPlainText("\n".join(lines))

    def _render_prescription(self, summary: dict):
        pid = summary.get("primary_id")
        if pid is None:
            self.rx_view.clear()
            return
        phase_key = self.phase_combo.currentData()
        rx = self.kb.lookup(pid, phase_key)
        self.rx_view.show_prescription(rx, summary.get("severity"))

    # ---------- 写台账 ----------
    def _save_to_log(self, src_path: str, annotated_path: str,
                     summary: dict, dets: list[Detection]):
        if not self.settings.auto_save_log:
            return
        pid = summary.get("primary_id")
        if pid is None:
            return
        phase_key = self.phase_combo.currentData()
        phase_name = self.phase_combo.currentText()
        rx = self.kb.lookup(pid, phase_key)
        snap = rx["chemical"] if rx else []
        farmer = self.farmer_input.text().strip()
        orchard = self.orchard_input.text().strip()
        # 记下最近一次
        self.settings.last_farmer = farmer
        self.settings.last_orchard = orchard
        log_id = self.logs.insert(
            sample_source="本地导入",
            target_disease=summary.get("primary_name_cn") or "",
            confidence=float(summary.get("primary_conf", 0.0)),
            severity_level=summary.get("severity") or "",
            count_value=int(summary.get("count", 0)),
            farmer_name=farmer,
            orchard_block=orchard,
            phenophase=phase_name,
            prescription_snapshot=snap,
            image_path=src_path,
            annotated_path=annotated_path,
        )
        self.log_inserted.emit(log_id)

    # ---------- 保存当前结果 ----------
    def _on_save_current(self):
        if not self._current_path or self._current_path not in self.results_cache:
            InfoBar.warning("提示", "当前还没有可保存的结果。", duration=2500, parent=self)
            return
        annotated, dets, summary, _ = self.results_cache[self._current_path]
        out_dir = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not out_dir:
            return
        out = Path(out_dir)
        stem = Path(self._current_path).stem
        imwrite_unicode(out / f"{stem}_det.jpg", annotated, ".jpg",
                        [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        txt_lines = [
            f"source:    {self._current_path}",
            f"model:     {self.inferencer.name} ({self.inferencer.backend_type})",
            f"primary:   {summary.get('primary_name_cn')}",
            f"severity:  {summary.get('severity')}",
            f"count:     {len(dets)}",
            "",
        ]
        for d in dets:
            txt_lines.append(
                f"{d.name_cn}\tconf={d.conf:.4f}\tbbox={d.xyxy}"
            )
        (out / f"{stem}_det.txt").write_text("\n".join(txt_lines), encoding="utf-8")
        InfoBar.success("已保存", f"保存至：{out}", duration=2500, parent=self)


def _title(text: str) -> QLabel:
    lb = SubtitleLabel(text)
    setFont(lb, 16, WEIGHT_SEMIBOLD)
    return lb

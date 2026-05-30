"""Public image collection page."""

from __future__ import annotations

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import config as C
from ..core import image_collector as ic
from .fluent import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    InfoBar,
    LargeTitleLabel,
    LineEdit,
    PrimaryPushButton,
    SpinBox,
    SubtitleLabel,
    TextEdit,
    TransparentPushButton,
    WEIGHT_BOLD,
    WEIGHT_SEMIBOLD,
    fluent_card,
    setFont,
)


class CollectionPage(QWidget):
    collection_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.worker: CollectionWorker | None = None
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(18)

        title = LargeTitleLabel("数据采集")
        setFont(title, 28, WEIGHT_BOLD)
        root.addWidget(title)
        cap = CaptionLabel("从搜索引擎公开图片采集样本，按关键词和去重规则收录为 .jpg。")
        cap.setStyleSheet("color:#6B7280;")
        cap.setWordWrap(True)
        root.addWidget(cap)

        search_card, search_lay = fluent_card("采集条件", "输入搜索关键词即可采集，类别在数据标注时再绑定。")
        self.keyword_input = LineEdit()
        self.keyword_input.setPlaceholderText("例如：廉江红橙 黄龙病 叶片")
        search_lay.addWidget(BodyLabel("搜索关键词"))
        search_lay.addWidget(self.keyword_input)

        self.engine_combo = ComboBox()
        self.engine_combo.addItem("Bing + Google + 百度", userData="all")
        self.engine_combo.addItem("Bing", userData="bing")
        self.engine_combo.addItem("Google", userData="google")
        self.engine_combo.addItem("百度", userData="baidu")
        search_lay.addWidget(BodyLabel("搜索引擎"))
        search_lay.addWidget(self.engine_combo)

        root.addWidget(search_card)

        rule_card, rule_lay = fluent_card("收录规则", "候选图片会转为 .jpg，并保存到 raw/search_关键词/。")
        self.target_spin = SpinBox()
        self.target_spin.setRange(1, 1000)
        self.target_spin.setValue(1000)
        rule_lay.addWidget(BodyLabel("每批目标数量"))
        rule_lay.addWidget(self.target_spin)
        root.addWidget(rule_card)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        self.btn_start = PrimaryPushButton("开始采集")
        self.btn_start.clicked.connect(self._on_start)
        action_row.addWidget(self.btn_start)
        self.btn_stop = TransparentPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        action_row.addWidget(self.btn_stop)
        action_row.addStretch(1)
        root.addLayout(action_row)

        stat_card, stat_lay = fluent_card("采集进度")
        self.stat_label = BodyLabel("等待开始")
        self.stat_label.setWordWrap(True)
        stat_lay.addWidget(self.stat_label)
        root.addWidget(stat_card)

        path_card, path_lay = fluent_card("照片保存路径", "采集成功的 .jpg 会按关键词保存到数据集 raw 目录下。")
        self.save_path_label = BodyLabel(str(C.RAW_IMAGE_DIR))
        self.save_path_label.setWordWrap(True)
        self.save_path_label.setStyleSheet(
            "background:#F3F7FB; color:#374151; border-radius:8px; padding:10px;"
        )
        path_lay.addWidget(self.save_path_label)
        root.addWidget(path_card)

        log_title = SubtitleLabel("采集日志")
        setFont(log_title, 16, WEIGHT_SEMIBOLD)
        root.addWidget(log_title)
        self.log = TextEdit()
        self.log.setReadOnly(True)
        root.addWidget(self.log, 1)

        notice = CaptionLabel(
            "公开搜索图片仅建议用于研究、测试、原型验证或辅助样本整理；"
            "正式训练与交付模型应优先使用自采图片、授权数据或公开许可证明确允许的数据集。"
        )
        notice.setWordWrap(True)
        notice.setStyleSheet("color:#6B7280;")
        root.addWidget(notice)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _on_start(self):
        if self.worker is not None and self.worker.isRunning():
            InfoBar.warning("采集中", "当前采集任务仍在运行，请先停止并等待结束。", duration=3000, parent=self)
            return

        keyword = self.keyword_input.text().strip()
        if not keyword:
            InfoBar.warning("缺少关键词", "请输入搜索关键词。", duration=3000, parent=self)
            return

        save_dir = C.RAW_IMAGE_DIR / ic._collection_key(keyword)
        self.save_path_label.setText(str(save_dir))
        worker = CollectionWorker(
            keyword=keyword,
            target_count=int(self.target_spin.value()),
            engine=str(self.engine_combo.currentData() or "all"),
        )
        self.worker = worker
        worker.log_line.connect(self.log.append)
        worker.stats_changed.connect(self._on_stats)
        worker.finished_collect.connect(lambda saved, w=worker: self._on_finished(w, saved))
        worker.finished.connect(worker.deleteLater)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log.append(f"开始采集...\n保存目录：{save_dir}")
        worker.start()

    def _on_stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.btn_start.setEnabled(False)
            self.log.append("已请求停止采集。")

    def _on_stats(self, text: str):
        self.stat_label.setText(text)

    def _on_finished(self, worker: "CollectionWorker", saved: int):
        if worker is not self.worker:
            return
        stopped = worker.was_stopped
        self.worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.collection_finished.emit()
        if stopped:
            InfoBar.warning(
                "采集已停止",
                f"本次已收录 {saved} 张图片，保存路径：{self.save_path_label.text()}",
                duration=5000,
                parent=self,
            )
        else:
            InfoBar.success(
                "采集完成",
                f"本次成功收录 {saved} 张图片，保存路径：{self.save_path_label.text()}",
                duration=5000,
                parent=self,
            )


class CollectionWorker(QThread):
    log_line = pyqtSignal(str)
    stats_changed = pyqtSignal(str)
    finished_collect = pyqtSignal(int)

    def __init__(
        self,
        keyword: str,
        target_count: int,
        engine: str = "all",
    ):
        super().__init__()
        self.keyword = keyword
        self.target_count = target_count
        self.engine = engine
        self._stop = False
        self.was_stopped = False

    def stop(self):
        self._stop = True
        self.was_stopped = True
        self.requestInterruption()

    def run(self):
        stats = ic.CollectionStats()
        try:
            if self._should_stop():
                self.finished_collect.emit(stats.saved)
                return
            candidates = ic.search_images(
                self.keyword,
                limit=max(self.target_count * 3, 100),
                engine=self.engine,
            )
            stats.found = len(candidates)
            self.log_line.emit(f"搜索到候选图片 {len(candidates)} 条。")
            hashes = ic.load_manifest_hashes()
            urls = ic.load_manifest_urls()
            for cand in candidates:
                if self._should_stop() or stats.saved >= self.target_count:
                    break
                result = ic.collect_candidate(
                    cand,
                    keyword=self.keyword,
                    existing_hashes=hashes,
                    existing_urls=urls,
                )
                if result.saved:
                    stats.saved += 1
                    stats.downloaded += 1
                    self.log_line.emit(
                        f"已收录 {stats.saved}/{self.target_count}: "
                        f"{result.local_path}"
                    )
                else:
                    if "重复" in result.reason:
                        stats.duplicate_filtered += 1
                    else:
                        stats.failed += 1
                    self.log_line.emit(f"跳过：{result.reason}")
                self.stats_changed.emit(_stats_text(stats))
            self.finished_collect.emit(stats.saved)
        except Exception as exc:
            self.log_line.emit(f"采集失败：{exc!r}")
            self.finished_collect.emit(stats.saved)

    def _should_stop(self) -> bool:
        return self._stop or self.isInterruptionRequested()


def _stats_text(stats: ic.CollectionStats) -> str:
    return (
        f"候选 {stats.found} · 已收录 {stats.saved} · "
        f"去重过滤 {stats.duplicate_filtered} · 失败 {stats.failed}"
    )

"""Training result visualization page."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import QUrl

from ..core import training_visualizer as tv
from .fluent import (
    BodyLabel,
    CaptionLabel,
    InfoBar,
    LargeTitleLabel,
    LineEdit,
    PrimaryPushButton,
    SubtitleLabel,
    TransparentPushButton,
    WEIGHT_BOLD,
    WEIGHT_SEMIBOLD,
    fluent_card,
    setFont,
)


class TrainingResultPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_run_dir: Path | None = None
        self._image_labels: list[ImagePreview] = []
        self._build_ui()
        self.refresh_results()

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

        title = LargeTitleLabel("训练结果可视化")
        setFont(title, 28, WEIGHT_BOLD)
        root.addWidget(title)
        caption = CaptionLabel("自动展示 YOLOv8 训练曲线、混淆矩阵和验证集预测效果图。")
        caption.setStyleSheet("color:#6B7280;")
        root.addWidget(caption)

        dir_card, dir_lay = fluent_card("结果目录", "默认读取最新一次训练输出，也可以选择本地 YOLOv8 run 目录。")
        self.dir_input = LineEdit()
        self.dir_input.setPlaceholderText("训练结果目录，例如 runtime_data/training_runs/yolov8s_xh")
        dir_lay.addWidget(self.dir_input)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.btn_refresh = PrimaryPushButton("刷新结果")
        self.btn_refresh.clicked.connect(lambda: self.refresh_results())
        row.addWidget(self.btn_refresh)
        self.btn_pick = TransparentPushButton("选择结果目录")
        self.btn_pick.clicked.connect(self._on_pick_dir)
        row.addWidget(self.btn_pick)
        self.btn_open = TransparentPushButton("打开文件夹")
        self.btn_open.clicked.connect(self._on_open_dir)
        row.addWidget(self.btn_open)
        row.addStretch(1)
        dir_lay.addLayout(row)
        self.status_label = BodyLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("background:#F3F7FB; color:#374151; border-radius:8px; padding:10px;")
        dir_lay.addWidget(self.status_label)
        root.addWidget(dir_card)

        summary_card, summary_lay = fluent_card("指标摘要")
        self.summary_label = BodyLabel("暂无训练结果")
        self.summary_label.setWordWrap(True)
        summary_lay.addWidget(self.summary_label)
        root.addWidget(summary_card)

        charts_card, charts_lay = fluent_card("训练曲线", "包含 Loss、Precision/Recall、mAP50/mAP50-95。")
        self.loss_preview = ImagePreview("训练集与验证集损失变化曲线")
        self.loss_analysis = AnalysisLabel()
        self.pr_preview = ImagePreview("精度、召回率变化曲线")
        self.pr_analysis = AnalysisLabel()
        self.map_preview = ImagePreview("mAP50、mAP50-95 指标曲线")
        self.map_analysis = AnalysisLabel()
        charts_lay.addWidget(self.loss_preview)
        charts_lay.addWidget(self.loss_analysis)
        charts_lay.addWidget(self.pr_preview)
        charts_lay.addWidget(self.pr_analysis)
        charts_lay.addWidget(self.map_preview)
        charts_lay.addWidget(self.map_analysis)
        root.addWidget(charts_card)

        matrix_card, matrix_lay = fluent_card("混淆矩阵")
        self.matrix_preview = ImagePreview("混淆矩阵")
        self.matrix_analysis = AnalysisLabel()
        matrix_lay.addWidget(self.matrix_preview)
        matrix_lay.addWidget(self.matrix_analysis)
        root.addWidget(matrix_card)

        pred_card, pred_lay = fluent_card("预测结果展示图", "展示 val_batch*_pred.jpg，点击缩略图可用系统默认程序打开。")
        self.pred_grid = QGridLayout()
        self.pred_grid.setSpacing(12)
        pred_lay.addLayout(self.pred_grid)
        self.pred_analysis = AnalysisLabel()
        pred_lay.addWidget(self.pred_analysis)
        root.addWidget(pred_card)

        overall_card, overall_lay = fluent_card("训练结果总结")
        self.overall_analysis = AnalysisLabel()
        overall_lay.addWidget(self.overall_analysis)
        root.addWidget(overall_card)
        root.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh_results(self, run_dir: str | Path | bool | None = None):
        if isinstance(run_dir, bool):
            run_dir = None
        if run_dir is not None:
            self.current_run_dir = Path(run_dir)
        elif self.dir_input.text().strip():
            self.current_run_dir = Path(self.dir_input.text().strip())
        artifacts = tv.analyze_training_run(self.current_run_dir)
        self.current_run_dir = artifacts.run_dir
        self.dir_input.setText(str(artifacts.run_dir))
        self.status_label.setText(artifacts.message)
        self.summary_label.setText(_summary_text(artifacts.summary))
        self.loss_preview.set_image(_chart_path(artifacts, "loss"))
        self.pr_preview.set_image(_chart_path(artifacts, "precision_recall"))
        self.map_preview.set_image(_chart_path(artifacts, "map"))
        self.matrix_preview.set_image(artifacts.confusion_matrix)
        self._set_predictions(artifacts.predictions)
        self.loss_analysis.setText(artifacts.interpretation.loss)
        self.pr_analysis.setText(artifacts.interpretation.precision_recall)
        self.map_analysis.setText(artifacts.interpretation.map)
        self.matrix_analysis.setText(artifacts.interpretation.confusion_matrix)
        self.pred_analysis.setText(artifacts.interpretation.predictions)
        self.overall_analysis.setText(artifacts.interpretation.overall)
        if artifacts.valid:
            InfoBar.success("结果已刷新", artifacts.message, duration=2200, parent=self)

    def refresh_latest_results(self):
        self.current_run_dir = None
        self.dir_input.clear()
        self.refresh_results()

    def _on_pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择 YOLOv8 训练结果目录", str(self.current_run_dir or ""))
        if path:
            self.refresh_results(path)

    def _on_open_dir(self):
        if self.current_run_dir and self.current_run_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_run_dir)))
        else:
            InfoBar.warning("无法打开", "训练结果目录不存在。", duration=2500, parent=self)

    def _set_predictions(self, paths: list[Path]):
        for label in self._image_labels:
            label.setParent(None)
            label.deleteLater()
        self._image_labels.clear()
        while self.pred_grid.count():
            item = self.pred_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if not paths:
            empty = BodyLabel("暂无预测结果图。")
            empty.setStyleSheet("color:#6B7280;")
            self.pred_grid.addWidget(empty, 0, 0)
            return
        for idx, path in enumerate(paths[:12]):
            preview = ImagePreview(path.name, thumb_height=220)
            preview.set_image(path)
            self._image_labels.append(preview)
            self.pred_grid.addWidget(preview, idx // 2, idx % 2)


class ImagePreview(QWidget):
    def __init__(self, title: str, thumb_height: int = 320):
        super().__init__()
        self.path: Path | None = None
        self.thumb_height = thumb_height
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.title = SubtitleLabel(title)
        setFont(self.title, 16, WEIGHT_SEMIBOLD)
        lay.addWidget(self.title)
        self.image = QLabel("暂无图片")
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumHeight(120)
        self.image.setMaximumHeight(thumb_height)
        self.image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.image.setStyleSheet("background:#F3F4F6; color:#6B7280; border-radius:8px; padding:8px;")
        lay.addWidget(self.image)
        self.caption = CaptionLabel("")
        self.caption.setStyleSheet("color:#6B7280;")
        self.caption.setWordWrap(True)
        lay.addWidget(self.caption)

    def set_image(self, path: Path | None):
        self.path = path
        if not path or not path.exists():
            self.image.setText("暂无图片")
            self.image.setPixmap(QPixmap())
            self.caption.setText("")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image.setText("图片无法加载")
            self.caption.setText(str(path))
            return
        scaled = pixmap.scaledToHeight(self.thumb_height, Qt.SmoothTransformation)
        if scaled.width() > 1100:
            scaled = pixmap.scaled(1100, self.thumb_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image.setPixmap(scaled)
        self.image.setText("")
        self.caption.setText(str(path))

    def mouseDoubleClickEvent(self, _event):
        if self.path and self.path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))


class AnalysisLabel(BodyLabel):
    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setWordWrap(True)
        self.setStyleSheet(
            "background:#F3F7FB; color:#374151; border-radius:8px; padding:10px;"
        )


def _chart_path(artifacts: tv.TrainingArtifacts, key: str) -> Path | None:
    return artifacts.generated_charts.get(key)


def _summary_text(summary: tv.TrainingSummary) -> str:
    if summary.epochs <= 0:
        return "暂无可解析的训练指标。"
    return (
        f"训练轮次：{summary.epochs}\n"
        f"最佳 mAP50：{_fmt(summary.best_map50)}"
        f"{_epoch(summary.best_map50_epoch)}\n"
        f"最佳 mAP50-95：{_fmt(summary.best_map5095)}"
        f"{_epoch(summary.best_map5095_epoch)}\n"
        f"最终 Precision：{_fmt(summary.final_precision)}\n"
        f"最终 Recall：{_fmt(summary.final_recall)}"
    )


def _fmt(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def _epoch(epoch: int | None) -> str:
    return "" if epoch is None else f"（epoch {epoch}）"

"""Model training page unlocked by submitted annotations."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core import dataset_manager as dm
from .. import config as C
from .fluent import (
    BodyLabel,
    CaptionLabel,
    InfoBar,
    LargeTitleLabel,
    LineEdit,
    PrimaryPushButton,
    SubtitleLabel,
    SpinBox,
    TransparentPushButton,
    TextEdit,
    WEIGHT_BOLD,
    WEIGHT_SEMIBOLD,
    fluent_card,
    setFont,
)


class TrainingPage(QWidget):
    training_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.train_worker: TrainWorker | None = None
        self._build_ui()
        self.refresh_state()

    def _build_ui(self):
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

        title = LargeTitleLabel("模型训练")
        setFont(title, 28, WEIGHT_BOLD)
        lay.addWidget(title)
        caption = CaptionLabel("标注数据集提交后，按 YOLOv8s-XH 流程启动本地训练。")
        caption.setStyleSheet("color:#6B7280;")
        lay.addWidget(caption)

        self.state_label = BodyLabel()
        self.state_label.setWordWrap(True)
        self.state_label.setStyleSheet(
            "background:#FFF4CE; color:#8A6A00; border-radius:8px; padding:10px;"
        )
        lay.addWidget(self.state_label)

        dataset_box, dataset_lay = fluent_card("训练数据集", "可使用已提交的项目数据集，也可选择本地 YOLO 数据集 data.yaml。")
        self.dataset_input = LineEdit()
        self.dataset_input.setPlaceholderText("选择或输入 data.yaml 路径")
        self.dataset_input.textChanged.connect(self._on_dataset_path_changed)
        dataset_lay.addWidget(BodyLabel("data.yaml"))
        dataset_lay.addWidget(self.dataset_input)

        dataset_btns = QHBoxLayout()
        dataset_btns.setSpacing(12)
        self.btn_use_submitted = TransparentPushButton("使用已提交数据集")
        self.btn_use_submitted.clicked.connect(self._on_use_submitted_dataset)
        dataset_btns.addWidget(self.btn_use_submitted)

        self.btn_pick_dataset = PrimaryPushButton("选择本地数据集")
        self.btn_pick_dataset.clicked.connect(self._on_pick_local_dataset)
        dataset_btns.addWidget(self.btn_pick_dataset)
        dataset_btns.addStretch(1)
        dataset_lay.addLayout(dataset_btns)
        lay.addWidget(dataset_box)

        config_box, cfg = fluent_card("模型选择", "可使用 yolov8s.pt 预训练权重，或指定本地 .pt 文件。")
        self.model_input = LineEdit()
        self.model_input.setText("yolov8s.pt")
        self.model_input.setPlaceholderText("yolov8s.pt 或本地 .pt 权重路径")
        cfg.addWidget(BodyLabel("初始权重"))
        cfg.addWidget(self.model_input)
        lay.addWidget(config_box)

        train_box, tl = fluent_card("训练参数", "增强策略按技术规范中的田间场景 pipeline 自动注入。")
        self.epochs_spin = SpinBox()
        self.epochs_spin.setRange(1, 1000)
        self.epochs_spin.setValue(300)
        tl.addWidget(BodyLabel("epochs"))
        tl.addWidget(self.epochs_spin)

        self.imgsz_spin = SpinBox()
        self.imgsz_spin.setRange(320, 1280)
        self.imgsz_spin.setSingleStep(32)
        self.imgsz_spin.setValue(640)
        tl.addWidget(BodyLabel("imgsz"))
        tl.addWidget(self.imgsz_spin)

        self.batch_spin = SpinBox()
        self.batch_spin.setRange(1, 128)
        self.batch_spin.setValue(8)
        tl.addWidget(BodyLabel("batch"))
        tl.addWidget(self.batch_spin)

        btns = QHBoxLayout()
        btns.setSpacing(12)
        self.btn_start_train = PrimaryPushButton("开始训练模型")
        self.btn_start_train.clicked.connect(self._on_start_train)
        btns.addWidget(self.btn_start_train)

        self.btn_stop_train = TransparentPushButton("停止训练")
        self.btn_stop_train.clicked.connect(self._on_stop_train)
        self.btn_stop_train.setEnabled(False)
        btns.addWidget(self.btn_stop_train)

        self.btn_refresh = TransparentPushButton("刷新提交状态")
        self.btn_refresh.clicked.connect(self.refresh_state)
        btns.addWidget(self.btn_refresh)
        btns.addStretch(1)
        tl.addLayout(btns)
        lay.addWidget(train_box)

        self.log = TextEdit()
        self.log.setReadOnly(True)
        log_title = SubtitleLabel("训练日志")
        setFont(log_title, 16, WEIGHT_SEMIBOLD)
        lay.addWidget(log_title)
        lay.addWidget(self.log, 1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh_state(self):
        self.submission = dm.load_submission()
        s = self.submission.stats
        self._migrate_legacy_dataset_path()
        if self.submission.submitted:
            if not self.dataset_input.text().strip():
                self.dataset_input.setText(str(self.submission.data_yaml))
            self.state_label.setStyleSheet(
                "background:#DFF6DD; color:#107C10; border-radius:8px; padding:10px;"
            )
            self.state_label.setText(
                f"标注数据集已提交：{self.submission.submitted_at}\n"
                f"train={s.train_images}, val={s.val_images}, test={s.test_images}, "
                f"boxes={s.boxes}\n"
                f"data.yaml：{self.submission.data_yaml}"
            )
        else:
            self.state_label.setStyleSheet(
                "background:#FFF4CE; color:#8A6A00; border-radius:8px; padding:10px;"
            )
            self.state_label.setText(
                f"{self.submission.message}\n"
                "可以先在【数据标注】页提交项目数据集，或在此处选择本地 YOLO 数据集 data.yaml。"
            )
        self._update_start_enabled()

    def _on_start_train(self):
        self.refresh_state()
        data_yaml = self._selected_data_yaml()
        if data_yaml is None:
            InfoBar.warning("无法训练", "请先提交项目数据集，或选择一个有效的本地 data.yaml。", duration=3000, parent=self)
            self.log.append("无法训练：未选择有效 data.yaml，或训练集/验证集为空。")
            return
        validation = dm.validate_training_data_yaml(data_yaml)
        if not validation.valid:
            InfoBar.warning("数据集无效", validation.message, duration=5000, parent=self)
            self.log.append(f"无法训练：{validation.message}")
            return
        dm.write_training_hyp()
        self.train_worker = TrainWorker(
            data_yaml=data_yaml,
            model=self.model_input.text().strip() or "yolov8s.pt",
            epochs=int(self.epochs_spin.value()),
            imgsz=int(self.imgsz_spin.value()),
            batch=int(self.batch_spin.value()),
        )
        self.train_worker.line.connect(self.log.append)
        self.train_worker.finished_ok.connect(self._on_train_finished)
        self.train_worker.error.connect(lambda msg: QMessageBox.critical(self, "训练失败", msg))
        self.btn_start_train.setEnabled(False)
        self.btn_stop_train.setEnabled(True)
        self.log.append(f"开始训练 YOLOv8s-XH...\ndata.yaml：{data_yaml}\n{validation.message}")
        InfoBar.success("训练已启动", "正在运行 YOLOv8s-XH 训练任务。", duration=2200, parent=self)
        self.train_worker.start()

    def _on_stop_train(self):
        if self.train_worker:
            self.train_worker.stop()
            self.log.append("已请求停止训练。")

    def _on_train_finished(self, ok: bool):
        self._update_start_enabled()
        self.btn_stop_train.setEnabled(False)
        self.log.append("训练完成。" if ok else "训练已结束，可能未正常完成。")
        self.training_finished.emit()

    def _on_pick_local_dataset(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择本地 YOLO 数据集 data.yaml",
            "",
            "YOLO 数据集配置 (*.yaml *.yml)",
        )
        if not path:
            return
        self.dataset_input.setText(path)
        self.log.append(f"已选择本地数据集：{path}")
        self._update_start_enabled()

    def _on_use_submitted_dataset(self):
        self.refresh_state()
        if not self.submission.submitted:
            InfoBar.warning("尚未提交", self.submission.message, duration=3000, parent=self)
            return
        self.dataset_input.setText(str(self.submission.data_yaml))
        self.log.append(f"已切换为项目已提交数据集：{self.submission.data_yaml}")
        self._update_start_enabled()

    def _on_dataset_path_changed(self, _text: str):
        self._update_start_enabled()

    def _selected_data_yaml(self) -> Path | None:
        text = self.dataset_input.text().strip()
        if text:
            path = Path(text)
            if path.exists() and path.is_file() and dm.validate_training_data_yaml(path).valid:
                return path
            return None
        if (
            self.submission.submitted
            and self.submission.data_yaml.exists()
            and dm.validate_training_data_yaml(self.submission.data_yaml).valid
        ):
            return self.submission.data_yaml
        return None

    def _update_start_enabled(self):
        running = self.train_worker is not None and self.train_worker.isRunning()
        self.btn_start_train.setEnabled(not running and self._selected_data_yaml() is not None)

    def _migrate_legacy_dataset_path(self):
        text = self.dataset_input.text().strip()
        if "xinhui_citrus_dataset" not in text:
            return
        current = C.DATASET_DIR / "data.yaml"
        if current.exists():
            self.dataset_input.setText(str(current))
            self.log.append(f"已自动切换旧数据集路径为当前项目数据集：{current}")


class TrainWorker(QThread):
    line = pyqtSignal(str)
    finished_ok = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, data_yaml: Path, model: str, epochs: int, imgsz: int, batch: int):
        super().__init__()
        self.data_yaml = data_yaml
        self.model = model
        self.epochs = epochs
        self.imgsz = imgsz
        self.batch = batch
        self.proc = None

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def run(self):
        try:
            self.proc = dm.start_training(
                self.data_yaml,
                model=self.model,
                epochs=self.epochs,
                imgsz=self.imgsz,
                batch=self.batch,
            )
            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                self.line.emit(line.rstrip())
            code = self.proc.wait()
            self.finished_ok.emit(code == 0)
        except Exception as exc:
            self.error.emit(repr(exc))
            self.finished_ok.emit(False)

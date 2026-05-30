"""
YOLOv8 物体检测 - PyQt5 本地界面

功能：
- 加载图片（单张/批量），用 YOLOv8 做物体检测
- 支持官方预训练权重（yolov8n/s/m/l/x.pt，首次运行自动下载）
- 支持加载自定义训练的 .pt 权重
- 可调置信度阈值、IoU 阈值、设备（CPU/GPU）
- 检测结果可视化展示 + 详情列表 + 一键保存
"""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ultralytics import YOLO

OFFICIAL_MODELS = ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt"]
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def cv2_to_qpixmap(img_bgr: np.ndarray) -> QPixmap:
    """OpenCV BGR ndarray -> QPixmap"""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = img_rgb.shape
    qimg = QImage(img_rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class DetectWorker(QThread):
    """后台推理线程，避免阻塞 UI"""

    progress = pyqtSignal(int, int)            # (current, total)
    one_done = pyqtSignal(str, object, list)   # (image_path, annotated_bgr, detections)
    finished_all = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, model, image_paths, conf, iou, device):
        super().__init__()
        self.model = model
        self.image_paths = image_paths
        self.conf = conf
        self.iou = iou
        self.device = device

    def run(self):
        try:
            total = len(self.image_paths)
            for idx, p in enumerate(self.image_paths, 1):
                results = self.model.predict(
                    source=p,
                    conf=self.conf,
                    iou=self.iou,
                    device=self.device,
                    verbose=False,
                )
                r = results[0]
                annotated = r.plot()  # BGR ndarray
                detections = []
                names = r.names
                if r.boxes is not None and len(r.boxes) > 0:
                    for box in r.boxes:
                        cls_id = int(box.cls.item())
                        conf = float(box.conf.item())
                        xyxy = box.xyxy.cpu().numpy().flatten().tolist()
                        detections.append({
                            "class": names.get(cls_id, str(cls_id)),
                            "conf": conf,
                            "xyxy": [round(v, 1) for v in xyxy],
                        })
                self.one_done.emit(p, annotated, detections)
                self.progress.emit(idx, total)
            self.finished_all.emit()
        except Exception as e:
            self.error.emit(repr(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLOv8 物体检测")
        self.resize(1280, 800)

        self.model = None
        self.current_model_path = None
        self.image_paths: list[str] = []
        self.results_cache: dict[str, tuple[np.ndarray, list]] = {}
        self.worker: DetectWorker | None = None

        self._build_ui()
        self._load_model(OFFICIAL_MODELS[0])  # 默认加载 yolov8n

    # ---------- UI ----------
    def _build_ui(self):
        # 左侧：控制面板
        ctrl = QWidget()
        cl = QVBoxLayout(ctrl)

        cl.addWidget(QLabel("<b>模型</b>"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(OFFICIAL_MODELS)
        self.model_combo.currentTextChanged.connect(self._on_official_model_changed)
        cl.addWidget(self.model_combo)

        self.btn_custom_model = QPushButton("加载自定义 .pt 权重…")
        self.btn_custom_model.clicked.connect(self._on_load_custom_model)
        cl.addWidget(self.btn_custom_model)

        self.lbl_model = QLabel("当前: -")
        self.lbl_model.setWordWrap(True)
        cl.addWidget(self.lbl_model)

        cl.addSpacing(10)
        cl.addWidget(QLabel("<b>参数</b>"))

        cl.addWidget(QLabel("置信度阈值 conf"))
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.01, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(0.25)
        cl.addWidget(self.spin_conf)

        cl.addWidget(QLabel("IoU 阈值"))
        self.spin_iou = QDoubleSpinBox()
        self.spin_iou.setRange(0.1, 1.0)
        self.spin_iou.setSingleStep(0.05)
        self.spin_iou.setValue(0.7)
        cl.addWidget(self.spin_iou)

        cl.addWidget(QLabel("设备"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(self._available_devices())
        cl.addWidget(self.device_combo)

        cl.addSpacing(10)
        cl.addWidget(QLabel("<b>图片</b>"))

        self.btn_open_files = QPushButton("选择图片…")
        self.btn_open_files.clicked.connect(self._on_open_files)
        cl.addWidget(self.btn_open_files)

        self.btn_open_dir = QPushButton("选择文件夹…")
        self.btn_open_dir.clicked.connect(self._on_open_dir)
        cl.addWidget(self.btn_open_dir)

        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.clicked.connect(self._on_clear)
        cl.addWidget(self.btn_clear)

        cl.addSpacing(10)
        self.btn_run = QPushButton("▶ 开始检测")
        self.btn_run.setStyleSheet("font-weight:bold; padding:8px;")
        self.btn_run.clicked.connect(self._on_run)
        cl.addWidget(self.btn_run)

        self.btn_save = QPushButton("保存结果…")
        self.btn_save.clicked.connect(self._on_save)
        cl.addWidget(self.btn_save)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        cl.addWidget(self.progress)

        cl.addStretch(1)

        # 中间：图片列表
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_select_image)

        # 右侧：图片预览 + 检测详情
        self.image_label = QLabel("（未加载图片）")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background:#222; color:#aaa;")
        self.image_label.setMinimumSize(640, 480)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(180)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.image_label, 1)
        rl.addWidget(QLabel("<b>检测详情</b>"))
        rl.addWidget(self.detail)

        # 拼装
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(ctrl)
        splitter.addWidget(self.list_widget)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([240, 240, 800])

        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())

    @staticmethod
    def _available_devices() -> list[str]:
        devices = ["cpu"]
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    devices.append(f"cuda:{i}")
        except Exception:
            pass
        return devices

    # ---------- 模型 ----------
    def _load_model(self, path_or_name: str):
        self.statusBar().showMessage(f"加载模型: {path_or_name} …")
        QApplication.processEvents()
        try:
            self.model = YOLO(path_or_name)
            self.current_model_path = path_or_name
            self.lbl_model.setText(f"当前: {path_or_name}")
            self.statusBar().showMessage(f"模型已加载: {path_or_name}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "模型加载失败", str(e))
            self.statusBar().showMessage("模型加载失败", 3000)

    def _on_official_model_changed(self, name: str):
        self._load_model(name)

    def _on_load_custom_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 .pt 权重文件", "", "PyTorch Weights (*.pt)"
        )
        if path:
            self._load_model(path)

    # ---------- 图片选择 ----------
    def _on_open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp *.tif *.tiff)",
        )
        if paths:
            self._add_images(paths)

    def _on_open_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if d:
            paths = [
                str(p) for p in Path(d).iterdir()
                if p.suffix.lower() in SUPPORTED_IMAGE_EXTS
            ]
            paths.sort()
            if paths:
                self._add_images(paths)
            else:
                QMessageBox.information(self, "提示", "该文件夹下没有支持的图片。")

    def _add_images(self, paths: list[str]):
        for p in paths:
            if p in self.image_paths:
                continue
            self.image_paths.append(p)
            self.list_widget.addItem(QListWidgetItem(Path(p).name))
        self.statusBar().showMessage(f"共 {len(self.image_paths)} 张图片", 3000)
        if self.list_widget.currentRow() < 0 and self.image_paths:
            self.list_widget.setCurrentRow(0)

    def _on_clear(self):
        self.image_paths.clear()
        self.results_cache.clear()
        self.list_widget.clear()
        self.image_label.setText("（未加载图片）")
        self.image_label.setPixmap(QPixmap())
        self.detail.clear()
        self.progress.setValue(0)

    # ---------- 选中切换 ----------
    def _on_select_image(self, cur: QListWidgetItem, _prev):
        if cur is None:
            return
        idx = self.list_widget.row(cur)
        if idx < 0 or idx >= len(self.image_paths):
            return
        path = self.image_paths[idx]
        if path in self.results_cache:
            annotated, dets = self.results_cache[path]
            self._show_image(annotated)
            self._show_detail(path, dets)
        else:
            img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                self.image_label.setText(f"无法读取图片: {path}")
                return
            self._show_image(img)
            self.detail.setPlainText(f"{path}\n（尚未检测）")

    def _show_image(self, img_bgr: np.ndarray):
        pix = cv2_to_qpixmap(img_bgr)
        scaled = pix.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def _show_detail(self, path: str, dets: list):
        lines = [f"文件: {path}", f"检测到 {len(dets)} 个目标", ""]
        for i, d in enumerate(dets, 1):
            lines.append(
                f"{i:>3}. {d['class']:<15s}  conf={d['conf']:.3f}  bbox={d['xyxy']}"
            )
        self.detail.setPlainText("\n".join(lines))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cur = self.list_widget.currentItem()
        if cur is not None:
            self._on_select_image(cur, None)

    # ---------- 推理 ----------
    def _on_run(self):
        if self.model is None:
            QMessageBox.warning(self, "提示", "模型未加载。")
            return
        if not self.image_paths:
            QMessageBox.warning(self, "提示", "请先选择图片。")
            return
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "提示", "检测正在进行中…")
            return

        self.progress.setValue(0)
        self.btn_run.setEnabled(False)
        self.worker = DetectWorker(
            model=self.model,
            image_paths=list(self.image_paths),
            conf=self.spin_conf.value(),
            iou=self.spin_iou.value(),
            device=self.device_combo.currentText(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.one_done.connect(self._on_one_done)
        self.worker.finished_all.connect(self._on_all_done)
        self.worker.error.connect(self._on_worker_error)
        self.statusBar().showMessage("检测中…")
        self.worker.start()

    def _on_progress(self, cur: int, total: int):
        self.progress.setMaximum(total)
        self.progress.setValue(cur)

    def _on_one_done(self, path: str, annotated: np.ndarray, dets: list):
        self.results_cache[path] = (annotated, dets)
        # 若当前选中的就是这张，刷新显示
        cur = self.list_widget.currentItem()
        if cur is not None:
            idx = self.list_widget.row(cur)
            if 0 <= idx < len(self.image_paths) and self.image_paths[idx] == path:
                self._show_image(annotated)
                self._show_detail(path, dets)

    def _on_all_done(self):
        self.btn_run.setEnabled(True)
        self.statusBar().showMessage("检测完成", 3000)

    def _on_worker_error(self, msg: str):
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "检测出错", msg)
        self.statusBar().showMessage("检测出错", 3000)

    # ---------- 保存 ----------
    def _on_save(self):
        if not self.results_cache:
            QMessageBox.information(self, "提示", "还没有检测结果可保存。")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not out_dir:
            return
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        n_img, n_txt = 0, 0
        for path, (annotated, dets) in self.results_cache.items():
            stem = Path(path).stem
            img_out = out / f"{stem}_det.jpg"
            # 中文路径用 imencode 写
            ok, buf = cv2.imencode(".jpg", annotated)
            if ok:
                buf.tofile(str(img_out))
                n_img += 1
            txt_out = out / f"{stem}_det.txt"
            with open(txt_out, "w", encoding="utf-8") as f:
                f.write(f"source: {path}\n")
                f.write(f"model: {self.current_model_path}\n")
                f.write(f"count: {len(dets)}\n")
                for d in dets:
                    f.write(
                        f"{d['class']}\tconf={d['conf']:.4f}\tbbox={d['xyxy']}\n"
                    )
            n_txt += 1
        QMessageBox.information(
            self, "已保存",
            f"图片 {n_img} 张，标注文本 {n_txt} 个\n保存至: {out_dir}",
        )


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

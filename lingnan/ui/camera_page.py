"""实时摄像头 / 视频文件检测页

输入源支持：
  · UVC USB 摄像头 / 数字显微镜（默认）
  · 本地视频文件（mp4/avi/mov/mkv）逐帧推理 + 导出带框视频
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from .fluent import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    LargeTitleLabel,
    PrimaryPushButton,
    SubtitleLabel,
    TransparentPushButton,
    SpinBox,
    ProgressBar,
    WEIGHT_BOLD,
    WEIGHT_SEMIBOLD,
    fluent_card,
    setFont,
)

from .. import config as C
from ..core import severity as sv
from ..core.annotator import draw_detections
from ..core.inferencer import Inferencer
from ..core.image_io import imwrite_unicode
from .widgets import ImageView, SeverityChip


log = logging.getLogger(__name__)


SOURCE_CAMERA = "camera"
SOURCE_VIDEO = "video"


class CameraPage(QWidget):
    """摄像头实时 + 视频文件双模式"""

    def __init__(self, inferencer: Inferencer):
        super().__init__()
        self.inferencer = inferencer
        self.cap: cv2.VideoCapture | None = None
        self.writer: cv2.VideoWriter | None = None
        self.source_type: str = SOURCE_CAMERA
        self._video_path: Path | None = None
        self._video_total: int = 0
        self._video_idx: int = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._frame_times: list[float] = []
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(18)
        title = LargeTitleLabel("实时摄像头")
        setFont(title, 28, WEIGHT_BOLD)
        root.addWidget(title)
        caption = CaptionLabel("连接 UVC 摄像头或导入本地视频，逐帧执行本地检测。")
        caption.setStyleSheet("color:#6B7280;")
        root.addWidget(caption)

        control_card, control_lay = fluent_card("输入与控制")
        # ---------- 模式切换 ----------
        src_row = QHBoxLayout()
        src_row.setSpacing(12)
        src_row.addWidget(BodyLabel("输入源"))
        self.src_combo = ComboBox()
        self.src_combo.addItem("📡 USB 摄像头 / 数字显微镜", userData=SOURCE_CAMERA)
        self.src_combo.addItem("🎬 本地视频文件", userData=SOURCE_VIDEO)
        self.src_combo.currentIndexChanged.connect(self._on_source_changed)
        src_row.addWidget(self.src_combo)
        src_row.addStretch(1)

        # ---------- 摄像头参数 ----------
        cam_row = QHBoxLayout()
        cam_row.setSpacing(12)
        cam_row.addWidget(BodyLabel("摄像头编号"))
        self.dev_spin = SpinBox()
        self.dev_spin.setRange(0, 9)
        self.dev_spin.setValue(0)
        cam_row.addWidget(self.dev_spin)
        cam_row.addWidget(BodyLabel("帧率上限"))
        self.fps_spin = SpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(15)
        cam_row.addWidget(self.fps_spin)
        cam_row.addStretch(1)
        self.cam_widget = QWidget()
        self.cam_widget.setLayout(cam_row)

        # ---------- 视频文件参数 ----------
        vid_row = QHBoxLayout()
        self.btn_pick_video = TransparentPushButton("选择视频文件")
        self.btn_pick_video.clicked.connect(self._on_pick_video)
        vid_row.addWidget(self.btn_pick_video)
        self.lbl_video = QLabel("（未选择）")
        self.lbl_video.setStyleSheet("color:#37474F;")
        vid_row.addWidget(self.lbl_video, 1)
        self.cb_export = TransparentPushButton("同时导出带框视频")
        self.cb_export.setCheckable(True)
        self.cb_export.setChecked(True)
        vid_row.addWidget(self.cb_export)
        vid_row.addStretch(1)
        self.vid_widget = QWidget()
        self.vid_widget.setLayout(vid_row)
        self.vid_widget.setVisible(False)

        # ---------- 控制按钮 ----------
        ctl_row = QHBoxLayout()
        self.btn_start = PrimaryPushButton("开始")
        self.btn_start.clicked.connect(self._on_start)
        ctl_row.addWidget(self.btn_start)
        self.btn_stop = TransparentPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        ctl_row.addWidget(self.btn_stop)
        ctl_row.addStretch(1)
        self.severity_chip = SeverityChip()
        ctl_row.addWidget(self.severity_chip)

        # ---------- 信息条 ----------
        info = QHBoxLayout()
        self.fps_label = QLabel("📡 FPS：—")
        self.fps_label.setStyleSheet(
            "background:#ECEFF1; color:#37474F; border-radius:6px;"
            "padding:6px 12px; font-weight:bold;"
        )
        info.addWidget(self.fps_label)
        self.count_label = QLabel("🔢 检出：—")
        self.count_label.setStyleSheet(
            "background:#ECEFF1; color:#37474F; border-radius:6px;"
            "padding:6px 12px; font-weight:bold;"
        )
        info.addWidget(self.count_label)
        info.addStretch(1)
        self.progress = ProgressBar()
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        info.addWidget(self.progress, 1)

        # ---------- 主图 ----------
        self.image_view = ImageView("（点击 ▶ 开始检测）")

        control_lay.addLayout(src_row)
        control_lay.addWidget(self.cam_widget)
        control_lay.addWidget(self.vid_widget)
        control_lay.addLayout(ctl_row)
        control_lay.addLayout(info)
        root.addWidget(control_card)

        image_card, image_lay = fluent_card("实时画面")
        image_lay.addWidget(self.image_view, 1)
        root.addWidget(image_card, 1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ============================================================ 业务
    def set_inferencer(self, inferencer: Inferencer):
        self.inferencer = inferencer

    def _on_source_changed(self, _idx: int):
        self.source_type = self.src_combo.currentData()
        is_video = self.source_type == SOURCE_VIDEO
        self.vid_widget.setVisible(is_video)
        self.cam_widget.setVisible(not is_video)
        self.progress.setVisible(is_video)

    def _on_pick_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频 (*.mp4 *.avi *.mov *.mkv *.flv)",
        )
        if path:
            self._video_path = Path(path)
            self.lbl_video.setText(str(self._video_path.name))

    # ---------- 开始 ----------
    def _on_start(self):
        if self.cap is not None:
            return
        if self.source_type == SOURCE_CAMERA:
            self._start_camera()
        else:
            self._start_video()

    def _start_camera(self):
        idx = self.dev_spin.value()
        backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0
        self.cap = cv2.VideoCapture(idx, backend)
        if not self.cap.isOpened():
            self.cap = None
            QMessageBox.warning(self, "提示", f"无法打开摄像头 #{idx}。")
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        fps = max(1, self.fps_spin.value())
        self.timer.start(max(1, int(1000 / fps)))
        self._frame_times.clear()
        log.info("摄像头 #%d 开启，目标 FPS=%d", idx, fps)

    def _start_video(self):
        if self._video_path is None or not self._video_path.exists():
            QMessageBox.warning(self, "提示", "请先选择视频文件。")
            return
        self.cap = cv2.VideoCapture(str(self._video_path))
        if not self.cap.isOpened():
            self.cap = None
            QMessageBox.warning(self, "提示", "无法打开该视频文件。")
            return
        self._video_total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._video_idx = 0
        src_fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # 视频导出
        if self.cb_export.isChecked():
            out_path = (
                C.EXPORT_DIR / f"{self._video_path.stem}_det.mp4"
            )
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            # 输出尺寸需匹配 annotated 加了顶部状态条后的高度（+56）
            self.writer = cv2.VideoWriter(
                str(out_path), fourcc, src_fps, (w, h + 56)
            )
            log.info("视频导出至 %s", out_path)
        else:
            self.writer = None
        self.progress.setMaximum(max(1, self._video_total))
        self.progress.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.timer.start(1)   # 视频文件尽快推理
        self._frame_times.clear()
        log.info("视频开始：%s, %d 帧 @ %.2f fps",
                 self._video_path, self._video_total, src_fps)

    def _on_stop(self):
        self.timer.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        out_path = None
        if self.writer is not None:
            self.writer.release()
            self.writer = None
            if self.source_type == SOURCE_VIDEO and self._video_path:
                out_path = C.EXPORT_DIR / f"{self._video_path.stem}_det.mp4"
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setValue(0)
        if out_path is not None and out_path.exists():
            QMessageBox.information(
                self, "已完成",
                f"视频处理完成，已导出：\n{out_path}",
            )

    # ---------- 帧 tick ----------
    def _tick(self):
        if self.cap is None:
            return
        ok, frame = self.cap.read()
        if not ok:
            if self.source_type == SOURCE_VIDEO:
                self._on_stop()
            return
        dets = self.inferencer.predict(
            frame, conf=C.DEFAULT_CONF, iou=C.DEFAULT_IOU
        )
        summary = sv.aggregate(dets, frame.shape[1], frame.shape[0])
        annotated = draw_detections(frame, dets, summary)
        self.image_view.set_cv_image(annotated)
        self.severity_chip.set_severity(summary.get("severity"))
        self.count_label.setText(f"🔢 检出：{len(dets)} 个目标")
        if self.writer is not None:
            try:
                self.writer.write(annotated)
            except Exception as e:
                log.warning("写视频失败：%s", e)
        if self.source_type == SOURCE_VIDEO:
            self._video_idx += 1
            self.progress.setValue(self._video_idx)
        # FPS
        now = time.perf_counter()
        self._frame_times.append(now)
        if len(self._frame_times) > 30:
            self._frame_times.pop(0)
        if len(self._frame_times) >= 2:
            fps = (len(self._frame_times) - 1) / (
                self._frame_times[-1] - self._frame_times[0]
            )
            self.fps_label.setText(f"📡 FPS：{fps:.1f}")

    def closeEvent(self, e):
        self._on_stop()
        super().closeEvent(e)

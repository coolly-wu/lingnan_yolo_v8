"""Dataset collection and LabelImg-style annotation page."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
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
    LargeTitleLabel,
    PushButton,
    PrimaryPushButton,
    ComboBox,
    SubtitleLabel,
    TextEdit,
    ListWidget,
    CheckBox,
    TransparentPushButton,
    fluent_card,
    setFont,
    WEIGHT_BOLD,
    WEIGHT_SEMIBOLD,
)

from .. import config as C
from ..core import dataset_manager as dm


class DatasetPage(QWidget):
    dataset_submitted = pyqtSignal()

    def __init__(self):
        super().__init__()
        dm.ensure_dataset()
        self.image_paths: list[Path] = []
        self.annotated_paths: list[Path] = []
        self.current_image: Path | None = None
        self._build_ui()
        self.refresh_images()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(18)

        title = LargeTitleLabel("数据标注")
        setFont(title, 28, WEIGHT_BOLD)
        root.addWidget(title)
        caption = CaptionLabel("导入采集图片，框选病虫害目标，提交后解锁模型训练。")
        caption.setStyleSheet("color:#6B7280;")
        root.addWidget(caption)

        ctrl_content = QWidget()
        cl = QVBoxLayout(ctrl_content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(18)

        prep_card, prep_lay = fluent_card("数据准备", "支持 JPG / PNG / BMP，本地保存到项目数据集目录。")
        self.btn_import_files = PrimaryPushButton("导入图片")
        self.btn_import_files.clicked.connect(self._on_import_files)
        prep_lay.addWidget(self.btn_import_files)

        self.btn_import_dir = TransparentPushButton("导入文件夹")
        self.btn_import_dir.clicked.connect(self._on_import_dir)
        prep_lay.addWidget(self.btn_import_dir)

        self.btn_delete_image = TransparentPushButton("删除当前图片")
        self.btn_delete_image.clicked.connect(self._on_delete_current_image)
        prep_lay.addWidget(self.btn_delete_image)

        self.btn_clear_images = TransparentPushButton("清空全部导入图片")
        self.btn_clear_images.clicked.connect(self._on_clear_imported_images)
        prep_lay.addWidget(self.btn_clear_images)

        self.stats_label = BodyLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet(
            "background:#F3F7FB; color:#374151; border-radius:8px; padding:10px;"
        )
        prep_lay.addWidget(self.stats_label)
        cl.addWidget(prep_card)

        anno_card, anno_lay = fluent_card("标注工具", "选择类别后，在右侧图片上拖拽生成 YOLO 标注框。")
        self.class_combo = ComboBox()
        for d in C.DISEASE_CLASSES:
            self.class_combo.addItem(f"{d['id']} · {d['name_cn']}", userData=d["id"])
        anno_lay.addWidget(self.class_combo)

        self.btn_save_labels = TransparentPushButton("保存当前标注")
        self.btn_save_labels.clicked.connect(self._on_save_labels)
        anno_lay.addWidget(self.btn_save_labels)

        self.btn_delete_box = TransparentPushButton("删除选中框")
        self.btn_delete_box.clicked.connect(self._on_delete_box)
        anno_lay.addWidget(self.btn_delete_box)

        self.btn_clear_boxes = TransparentPushButton("清空当前框")
        self.btn_clear_boxes.clicked.connect(self._on_clear_boxes)
        anno_lay.addWidget(self.btn_clear_boxes)
        cl.addWidget(anno_card)

        annotated_card, annotated_lay = fluent_card("已标注数据", "这里仅显示已经保存标注框的图片，可选中后删除整条样本。")
        self.annotated_list = ListWidget()
        self.annotated_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.annotated_list.setMinimumHeight(140)
        self.annotated_list.setMaximumHeight(220)
        self.annotated_list.currentItemChanged.connect(self._on_select_annotated_image)
        annotated_lay.addWidget(self.annotated_list)

        self.btn_delete_annotated = TransparentPushButton("删除选中已标注数据")
        self.btn_delete_annotated.clicked.connect(self._on_delete_annotated_sample)
        annotated_lay.addWidget(self.btn_delete_annotated)
        cl.addWidget(annotated_card)

        submit_card, submit_lay = fluent_card("提交标注数据集", "提交会生成 train / val / test 目录与 data.yaml。")
        self.include_unannotated = CheckBox("划分时包含未标注图片")
        submit_lay.addWidget(self.include_unannotated)
        self.btn_submit = PrimaryPushButton("提交标注数据集")
        self.btn_submit.clicked.connect(self._on_submit_dataset)
        submit_lay.addWidget(self.btn_submit)
        cl.addWidget(submit_card)

        cl.addStretch(1)

        ctrl = QScrollArea()
        ctrl.setWidgetResizable(True)
        ctrl.setFrameShape(QScrollArea.NoFrame)
        ctrl.setWidget(ctrl_content)

        self.list_widget = ListWidget()
        self.list_widget.currentItemChanged.connect(self._on_select_image)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)
        self.canvas = AnnotationCanvas()
        self.canvas.box_changed.connect(self._on_canvas_changed)
        rl.addWidget(self.canvas, 1)

        self.box_list = ListWidget()
        self.box_list.currentRowChanged.connect(self.canvas.set_selected_index)
        self.box_list.setMaximumHeight(150)
        box_title = SubtitleLabel("标注框")
        setFont(box_title, 16, WEIGHT_SEMIBOLD)
        rl.addWidget(box_title)
        rl.addWidget(self.box_list)

        self.log = TextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(180)
        log_title = SubtitleLabel("标注日志")
        setFont(log_title, 16, WEIGHT_SEMIBOLD)
        rl.addWidget(log_title)
        rl.addWidget(self.log)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(ctrl)
        splitter.addWidget(self.list_widget)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([300, 220, 820])
        root.addWidget(splitter, 1)

    def refresh_images(self):
        self.image_paths = dm.list_raw_images()
        self.annotated_paths = dm.list_annotated_images()

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for p in self.image_paths:
            item = QListWidgetItem(self._display_image_path(p))
            if dm.read_yolo_labels(dm.label_path_for_image(p)):
                item.setText(f"{self._display_image_path(p)}  [已标注]")
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

        self.annotated_list.blockSignals(True)
        self.annotated_list.clear()
        for p in self.annotated_paths:
            self.annotated_list.addItem(QListWidgetItem(self._display_image_path(p)))
        self.annotated_list.blockSignals(False)

        self._refresh_stats()
        if self.image_paths and self.list_widget.currentRow() < 0:
            self.list_widget.setCurrentRow(0)
        if not self.image_paths:
            self.current_image = None
            self.canvas.clear_image()
            self._refresh_box_list()

    def _refresh_stats(self):
        s = dm.stats()
        self.stats_label.setText(
            f"原始图片 {s.raw_images} 张\n"
            f"已标注 {s.annotated_images} 张 / 标注框 {s.boxes} 个\n"
            f"训练集 {s.train_images} · 验证集 {s.val_images} · 测试集 {s.test_images}\n"
            f"目录：{C.DATASET_DIR}"
        )

    def _on_import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "导入采集图片", "", "图片 (*.jpg *.jpeg *.png *.bmp)",
        )
        if paths:
            imported = dm.import_images(paths)
            self.log.append(f"已导入 {len(imported)} 张图片。")
            self.refresh_images()

    def _on_import_dir(self):
        d = QFileDialog.getExistingDirectory(self, "导入图片文件夹")
        if not d:
            return
        paths = [
            p for p in Path(d).iterdir()
            if p.is_file() and p.suffix.lower() in C.SUPPORTED_IMAGE_EXTS
        ]
        imported = dm.import_images(paths)
        self.log.append(f"已从文件夹导入 {len(imported)} 张图片。")
        self.refresh_images()

    def _on_select_image(self, cur: QListWidgetItem | None, _prev):
        if cur is None:
            return
        self._autosave_current()
        idx = self.list_widget.row(cur)
        if idx < 0 or idx >= len(self.image_paths):
            return
        self.current_image = self.image_paths[idx]
        labels = dm.read_yolo_labels(dm.label_path_for_image(self.current_image))
        self.canvas.load_image(self.current_image, labels)
        self._refresh_box_list()

    def _on_select_annotated_image(self, cur: QListWidgetItem | None, _prev):
        if cur is None:
            return
        idx = self.annotated_list.row(cur)
        if idx < 0 or idx >= len(self.annotated_paths):
            return
        try:
            image_idx = self.image_paths.index(self.annotated_paths[idx])
        except ValueError:
            return
        self.list_widget.setCurrentRow(image_idx)

    def _autosave_current(self):
        if self.current_image is None:
            return
        dm.write_yolo_labels(dm.label_path_for_image(self.current_image), self.canvas.boxes)

    def _on_canvas_changed(self):
        self._refresh_box_list()

    def _refresh_box_list(self):
        self.box_list.blockSignals(True)
        self.box_list.clear()
        for i, box in enumerate(self.canvas.boxes, 1):
            disease = C.DISEASE_BY_ID.get(box.class_id, {})
            self.box_list.addItem(
                f"{i}. {disease.get('name_cn', box.class_id)} "
                f"cx={box.cx:.3f} cy={box.cy:.3f} w={box.w:.3f} h={box.h:.3f}"
            )
        self.box_list.blockSignals(False)

    def _on_save_labels(self):
        if self.current_image is None:
            return
        dm.write_yolo_labels(dm.label_path_for_image(self.current_image), self.canvas.boxes)
        self.log.append(f"已保存标注：{self.current_image.name}")
        self.refresh_images()

    def _on_delete_box(self):
        self.canvas.delete_selected()
        self._refresh_box_list()

    def _on_clear_boxes(self):
        self.canvas.set_boxes([])
        self._refresh_box_list()

    def _on_delete_current_image(self):
        if self.current_image is None:
            QMessageBox.warning(self, "请选择图片", "请先在图片列表中选择要删除的图片。")
            return
        image = self.current_image
        reply = QMessageBox.question(
            self,
            "确认删除图片",
            f"确定删除当前导入图片吗？\n\n{self._display_image_path(image)}\n\n"
            "将同时删除该图片的标注文件，以及已提交数据集中的对应副本。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            deleted = dm.delete_raw_sample(image)
        except Exception as exc:
            QMessageBox.warning(self, "删除失败", str(exc))
            self.log.append(f"删除图片失败：{exc}")
            return
        self.current_image = None
        self.canvas.clear_image()
        self._refresh_box_list()
        self.log.append(f"已删除图片：{self._display_image_path(image)}，清理 {len(deleted)} 个文件。")
        self.refresh_images()

    def _on_clear_imported_images(self):
        count = len(self.image_paths)
        if count == 0:
            QMessageBox.warning(self, "暂无图片", "当前没有可清空的导入图片。")
            return
        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确定清空全部 {count} 张导入图片吗？\n\n"
            "将同时删除所有 raw 原图、标注文件、train/val/test 副本，并使已提交数据集状态失效。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            deleted = dm.clear_raw_samples()
        except Exception as exc:
            QMessageBox.warning(self, "清空失败", str(exc))
            self.log.append(f"清空导入图片失败：{exc}")
            return
        self.current_image = None
        self.canvas.clear_image()
        self._refresh_box_list()
        self.log.append(f"已清空全部导入图片 {count} 张，清理 {len(deleted)} 个文件。")
        self.refresh_images()

    def _on_delete_annotated_sample(self):
        selected_rows = sorted(
            {
                self.annotated_list.row(item)
                for item in self.annotated_list.selectedItems()
            }
        )
        targets = [
            self.annotated_paths[row]
            for row in selected_rows
            if 0 <= row < len(self.annotated_paths)
        ]
        if not targets:
            QMessageBox.warning(self, "请选择数据", "请先在已标注数据列表中选择一条或多条样本。")
            return

        preview = "\n".join(self._display_image_path(p) for p in targets[:8])
        if len(targets) > 8:
            preview += f"\n... 等 {len(targets)} 条"
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除选中的 {len(targets)} 条已标注数据吗？\n\n{preview}\n\n"
            "将同时删除原图、标注文件，以及已提交数据集中的对应副本。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        current_path = self.current_image.resolve() if self.current_image is not None else None
        deleted_current = (
            current_path is not None
            and any(current_path == image.resolve() for image in targets)
        )
        if not deleted_current:
            self._autosave_current()

        deleted_files = 0
        deleted_samples = 0
        errors: list[str] = []
        for image in targets:
            try:
                deleted_files += len(dm.delete_annotated_sample(image))
                deleted_samples += 1
            except Exception as exc:
                errors.append(f"{self._display_image_path(image)}：{exc}")

        current_deleted = current_path is not None and not current_path.exists()
        if deleted_current and current_deleted:
            self.current_image = None
            self.canvas.clear_image()
            self._refresh_box_list()

        self.log.append(f"已删除标注数据 {deleted_samples} 条，清理 {deleted_files} 个文件。")
        if errors:
            self.log.append("部分删除失败：\n" + "\n".join(errors))
            QMessageBox.warning(self, "部分删除失败", "\n".join(errors[:5]))
        self.refresh_images()

    def _on_submit_dataset(self):
        self._autosave_current()
        result = dm.submit_dataset(include_unannotated=self.include_unannotated.isChecked())
        if not result.submitted:
            QMessageBox.warning(self, "暂不能提交", result.message)
            self.log.append(result.message)
            self._refresh_stats()
            return
        self.log.append(
            f"{result.message} train={result.stats.train_images}, "
            f"val={result.stats.val_images}, test={result.stats.test_images}"
        )
        self._refresh_stats()
        self.dataset_submitted.emit()

    def _display_image_path(self, path: Path) -> str:
        try:
            return path.relative_to(C.DATASET_DIR / "raw").as_posix()
        except ValueError:
            return path.name


class AnnotationCanvas(QLabel):
    box_changed = pyqtSignal()

    def __init__(self):
        super().__init__("导入图片后在此框选目标")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(420, 260)
        self.setStyleSheet("background:#202020; color:#BDBDBD; border-radius:8px;")
        self.setMouseTracking(True)
        self.pixmap_raw = QPixmap()
        self.image_path: Path | None = None
        self.boxes: list[dm.YoloBox] = []
        self.selected_index = -1
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None

    def load_image(self, path: Path, boxes: list[dm.YoloBox]):
        self.setText("")
        self.image_path = path
        self.pixmap_raw = QPixmap(str(path))
        self.boxes = list(boxes)
        self.selected_index = -1
        self._drag_start = None
        self._drag_current = None
        self.update()

    def clear_image(self):
        self.setText("导入图片后在此框选目标")
        self.pixmap_raw = QPixmap()
        self.image_path = None
        self.boxes = []
        self.selected_index = -1
        self._drag_start = None
        self._drag_current = None
        self.update()

    def set_boxes(self, boxes: list[dm.YoloBox]):
        self.boxes = list(boxes)
        self.selected_index = -1
        self.update()
        self.box_changed.emit()

    def set_selected_index(self, idx: int):
        self.selected_index = idx
        self.update()

    def delete_selected(self):
        if 0 <= self.selected_index < len(self.boxes):
            del self.boxes[self.selected_index]
            self.selected_index = -1
            self.update()
            self.box_changed.emit()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap_raw.isNull():
            return
        painter = QPainter(self)
        target = self._target_rect()
        painter.drawPixmap(target, self.pixmap_raw)

        for i, box in enumerate(self.boxes):
            rect = self._box_to_widget_rect(box, target)
            color = C.DISEASE_BY_ID.get(box.class_id, {}).get("color", (0, 255, 0))
            qcolor = _rgb_tuple_to_qt(color)
            pen = QPen(qcolor, 3 if i == self.selected_index else 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            name = C.DISEASE_BY_ID.get(box.class_id, {}).get("name_cn", str(box.class_id))
            painter.drawText(rect.topLeft() + QPoint(4, -4), name)

        if self._drag_start and self._drag_current:
            painter.setPen(QPen(Qt.yellow, 2, Qt.DashLine))
            painter.drawRect(QRect(self._drag_start, self._drag_current).normalized())

    def mousePressEvent(self, event):
        if self.pixmap_raw.isNull() or event.button() != Qt.LeftButton:
            return
        pos = self._clamp_to_image(event.pos())
        hit = self._hit_test(pos)
        if hit >= 0:
            self.selected_index = hit
            self.update()
            self.box_changed.emit()
            return
        self._drag_start = pos
        self._drag_current = pos
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_start:
            self._drag_current = self._clamp_to_image(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self._drag_start:
            return
        end = self._clamp_to_image(event.pos())
        rect = QRect(self._drag_start, end).normalized()
        self._drag_start = None
        self._drag_current = None
        if rect.width() < 4 or rect.height() < 4:
            self.update()
            return
        box = self._widget_rect_to_box(rect)
        if box:
            parent = self.parent()
            while parent and not isinstance(parent, DatasetPage):
                parent = parent.parent()
            class_id = parent.class_combo.currentData() if isinstance(parent, DatasetPage) else 0
            self.boxes.append(dm.YoloBox(int(class_id), box.cx, box.cy, box.w, box.h))
            self.selected_index = len(self.boxes) - 1
            self.box_changed.emit()
        self.update()

    def _target_rect(self) -> QRect:
        scaled = self.pixmap_raw.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _clamp_to_image(self, p: QPoint) -> QPoint:
        r = self._target_rect()
        return QPoint(
            min(max(p.x(), r.left()), r.right()),
            min(max(p.y(), r.top()), r.bottom()),
        )

    def _hit_test(self, p: QPoint) -> int:
        target = self._target_rect()
        for i in range(len(self.boxes) - 1, -1, -1):
            if self._box_to_widget_rect(self.boxes[i], target).contains(p):
                return i
        return -1

    def _box_to_widget_rect(self, box: dm.YoloBox, target: QRect) -> QRect:
        x = target.left() + (box.cx - box.w / 2) * target.width()
        y = target.top() + (box.cy - box.h / 2) * target.height()
        w = box.w * target.width()
        h = box.h * target.height()
        return QRect(int(x), int(y), int(w), int(h))

    def _widget_rect_to_box(self, rect: QRect) -> dm.YoloBox | None:
        target = self._target_rect()
        if target.width() <= 0 or target.height() <= 0:
            return None
        left = (rect.left() - target.left()) / target.width()
        top = (rect.top() - target.top()) / target.height()
        right = (rect.right() - target.left()) / target.width()
        bottom = (rect.bottom() - target.top()) / target.height()
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        return dm.YoloBox(0, cx, cy, right - left, bottom - top).clamped()


def _title(text: str) -> QLabel:
    lb = SubtitleLabel(text)
    setFont(lb, 16, WEIGHT_SEMIBOLD)
    return lb


def _rgb_tuple_to_qt(color: tuple[int, int, int]):
    from PyQt5.QtGui import QColor

    b, g, r = color
    return QColor(r, g, b)

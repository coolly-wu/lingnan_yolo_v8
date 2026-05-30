"""农户 / 果园档案页"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from .fluent import (
    CaptionLabel,
    LargeTitleLabel,
    LineEdit,
    PrimaryPushButton,
    TransparentPushButton,
    TextEdit,
    TableWidget,
    WEIGHT_BOLD,
    fluent_card,
    setFont,
)

from ..data.farmer_manager import FarmerManager


class FarmerPage(QWidget):
    """档案 CRUD"""

    farmer_changed = pyqtSignal()   # 通知检测页刷新下拉

    def __init__(self, farmers: FarmerManager):
        super().__init__()
        self.farmers = farmers
        self._editing_id: int | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(18)
        title = LargeTitleLabel("农户档案")
        setFont(title, 28, WEIGHT_BOLD)
        root.addWidget(title)
        caption = CaptionLabel("维护农户、果园区块和联系方式，检测时可直接关联台账。")
        caption.setStyleSheet("color:#6B7280;")
        root.addWidget(caption)

        # 左：表格
        self.table = TableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "农户姓名", "果园区块", "电话", "位置", "备注"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.currentItemChanged.connect(self._on_row_select)

        # 右：编辑
        form_box, form_lay = fluent_card("编辑档案")
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        self.in_name = LineEdit()
        self.in_block = LineEdit()
        self.in_phone = LineEdit()
        self.in_location = LineEdit()
        self.in_notes = TextEdit()
        self.in_notes.setMaximumHeight(80)
        form.addRow("农户姓名 *", self.in_name)
        form.addRow("果园区块", self.in_block)
        form.addRow("电话", self.in_phone)
        form.addRow("位置", self.in_location)
        form.addRow("备注", self.in_notes)
        form_lay.addLayout(form)

        btns = QHBoxLayout()
        btns.setSpacing(12)
        self.btn_save = PrimaryPushButton("新增/保存")
        self.btn_save.clicked.connect(self._on_save)
        btns.addWidget(self.btn_save)
        self.btn_clear = TransparentPushButton("新建")
        self.btn_clear.clicked.connect(self._on_clear)
        btns.addWidget(self.btn_clear)
        self.btn_delete = TransparentPushButton("删除")
        self.btn_delete.clicked.connect(self._on_delete)
        btns.addWidget(self.btn_delete)

        csv_btns = QHBoxLayout()
        csv_btns.setSpacing(12)
        self.btn_import_csv = PrimaryPushButton("导入 CSV")
        self.btn_import_csv.clicked.connect(self._on_import_csv)
        csv_btns.addWidget(self.btn_import_csv)
        self.btn_template = TransparentPushButton("下载 CSV 模板")
        self.btn_template.clicked.connect(self._on_export_template)
        csv_btns.addWidget(self.btn_template)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(form_box)
        rl.addLayout(btns)
        rl.addLayout(csv_btns)
        self.stat_label = QLabel("共 0 户档案")
        self.stat_label.setStyleSheet("color:#37474F;")
        rl.addWidget(self.stat_label)
        rl.addStretch(1)

        content = QHBoxLayout()
        content.setSpacing(12)
        table_card, table_lay = fluent_card("档案列表")
        table_lay.addWidget(self.table)
        content.addWidget(table_card, 2)
        content.addWidget(right, 1)
        root.addLayout(content, 1)

    def refresh(self):
        rows = self.farmers.list_all()
        self.table.setRowCount(0)
        for i, r in enumerate(rows):
            self.table.insertRow(i)
            for ci, key in enumerate(
                ["id", "farmer_name", "orchard_block", "phone", "location", "notes"]
            ):
                item = QTableWidgetItem(str(r.get(key, "")))
                self.table.setItem(i, ci, item)
        self.table.resizeColumnsToContents()
        self.stat_label.setText(f"共 {len(rows)} 户档案")

    def _on_row_select(self, cur, _prev):
        if cur is None:
            return
        row = cur.row()
        try:
            self._editing_id = int(self.table.item(row, 0).text())
        except Exception:
            return
        self.in_name.setText(self.table.item(row, 1).text())
        self.in_block.setText(self.table.item(row, 2).text())
        self.in_phone.setText(self.table.item(row, 3).text())
        self.in_location.setText(self.table.item(row, 4).text())
        self.in_notes.setPlainText(self.table.item(row, 5).text())

    def _on_save(self):
        name = self.in_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请填写农户姓名。")
            return
        block = self.in_block.text().strip()
        phone = self.in_phone.text().strip()
        loc = self.in_location.text().strip()
        notes = self.in_notes.toPlainText().strip()
        try:
            if self._editing_id is None:
                self.farmers.insert(farmer_name=name, orchard_block=block,
                                    phone=phone, location=loc, notes=notes)
            else:
                self.farmers.update(self._editing_id,
                                    farmer_name=name, orchard_block=block,
                                    phone=phone, location=loc, notes=notes)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", repr(e))
            return
        self._on_clear()
        self.refresh()
        self.farmer_changed.emit()

    def _on_clear(self):
        self._editing_id = None
        for w in (self.in_name, self.in_block, self.in_phone, self.in_location):
            w.clear()
        self.in_notes.clear()
        self.table.clearSelection()

    def _on_delete(self):
        if self._editing_id is None:
            QMessageBox.information(self, "提示", "请先在左侧选中一行。")
            return
        ans = QMessageBox.question(
            self, "确认删除",
            f"确定删除档案 ID = {self._editing_id} ？",
        )
        if ans != QMessageBox.Yes:
            return
        self.farmers.delete(self._editing_id)
        self._on_clear()
        self.refresh()
        self.farmer_changed.emit()

    def _on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入农户档案 CSV",
            "",
            "CSV 文件 (*.csv);;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            result = self.farmers.import_csv(path)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
            return

        self._on_clear()
        self.refresh()
        self.farmer_changed.emit()

        message = f"成功导入/更新 {result.imported} 户档案，跳过 {result.skipped} 行。"
        if result.errors:
            detail = "\n".join(result.errors[:20])
            if len(result.errors) > 20:
                detail += f"\n……另有 {len(result.errors) - 20} 条错误未显示"
            QMessageBox.warning(self, "导入完成，存在部分异常", message + "\n\n" + detail)
        else:
            QMessageBox.information(self, "导入完成", message)

    def _on_export_template(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存农户档案 CSV 模板",
            "农户档案导入模板.csv",
            "CSV 文件 (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            saved = self.farmers.write_csv_template(path)
        except Exception as e:
            QMessageBox.critical(self, "模板生成失败", str(e))
            return
        QMessageBox.information(
            self,
            "模板已生成",
            f"CSV 模板已保存：\n{saved}\n\n必填列：农户姓名、果园区块、联系电话、果园位置。",
        )

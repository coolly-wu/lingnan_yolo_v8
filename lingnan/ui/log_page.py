"""历史台账页：筛选 + Excel 导出"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFileDialog,
    QGridLayout,
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
    ComboBox,
    PrimaryPushButton,
    TransparentPushButton,
    TableWidget,
    WEIGHT_BOLD,
    fluent_card,
    setFont,
)

from .. import config as C
from ..data.excel_exporter import HAS_OPENPYXL, export_logs
from ..data.log_manager import LogManager
from ..data.pdf_exporter import HAS_REPORTLAB, export_pdf


COLUMNS = [
    ("id", "序号"),
    ("datetime", "检测时间"),
    ("target_disease", "病虫害"),
    ("severity_level", "严重程度"),
    ("count_value", "数量"),
    ("confidence", "置信度"),
    ("phenophase", "物候期"),
    ("farmer_name", "农户"),
    ("orchard_block", "果园"),
    ("sample_source", "来源"),
    ("annotated_path", "标注图"),
]


class LogPage(QWidget):
    def __init__(self, logs: LogManager):
        super().__init__()
        self.logs = logs
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(18)
        title = LargeTitleLabel("历史台账")
        setFont(title, 28, WEIGHT_BOLD)
        root.addWidget(title)
        caption = CaptionLabel("按日期、农户和病虫害筛选本地检测记录，并导出 Excel 或 PDF 报告。")
        caption.setStyleSheet("color:#6B7280;")
        root.addWidget(caption)

        filter_card, filter_lay = fluent_card("筛选条件")
        # 筛选条
        filt = QGridLayout()
        filt.setHorizontalSpacing(12)
        filt.setVerticalSpacing(12)
        filt.addWidget(QLabel("📅 起始日期"))
        self.date_start = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        self.date_start.setFixedWidth(150)
        filt.addWidget(self.date_start, 0, 1)
        filt.addWidget(QLabel("截止日期"))
        self.date_end = QDateEdit(QDate.currentDate())
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        self.date_end.setFixedWidth(150)
        filt.addWidget(self.date_end, 0, 3)

        filt.addWidget(QLabel("农户"), 1, 0)
        self.farmer_input = LineEdit()
        self.farmer_input.setPlaceholderText("（可空）")
        self.farmer_input.setMinimumWidth(130)
        filt.addWidget(self.farmer_input, 1, 1)

        filt.addWidget(QLabel("病虫害"), 1, 2)
        self.disease_combo = ComboBox()
        self.disease_combo.addItem("（全部）", userData="")
        for d in C.DISEASE_CLASSES:
            self.disease_combo.addItem(d["name_cn"], userData=d["name_cn"])
        self.disease_combo.setMinimumWidth(180)
        filt.addWidget(self.disease_combo, 1, 3)

        self.btn_refresh = PrimaryPushButton("查询")
        self.btn_refresh.clicked.connect(self.refresh)
        filt.addWidget(self.btn_refresh, 2, 0, 1, 2)

        self.btn_quick_week = TransparentPushButton("最近一周")
        self.btn_quick_week.clicked.connect(lambda: self._quick(7))
        filt.addWidget(self.btn_quick_week, 2, 2)

        self.btn_quick_month = TransparentPushButton("最近一月")
        self.btn_quick_month.clicked.connect(lambda: self._quick(30))
        filt.addWidget(self.btn_quick_month, 2, 3)

        filt.setColumnStretch(4, 1)
        self.btn_export = TransparentPushButton("导出 Excel")
        self.btn_export.clicked.connect(self._on_export)
        filt.addWidget(self.btn_export, 2, 5)
        self.btn_export_pdf = TransparentPushButton("导出 PDF 报告")
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)
        filt.addWidget(self.btn_export_pdf, 2, 6, 1, 2)

        # 表格
        self.table = TableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)

        self.stat_label = QLabel("共 0 条")
        self.stat_label.setStyleSheet("padding:4px 12px; color:#37474F;")

        filter_lay.addLayout(filt)
        root.addWidget(filter_card)

        table_card, table_lay = fluent_card("检测记录")
        table_lay.addWidget(self.table, 1)
        table_lay.addWidget(self.stat_label)
        root.addWidget(table_card, 1)

    def _quick(self, days: int):
        self.date_start.setDate(QDate.currentDate().addDays(-days))
        self.date_end.setDate(QDate.currentDate())
        self.refresh()

    def refresh(self):
        start = self.date_start.date().toString("yyyy-MM-dd") + " 00:00:00"
        end = self.date_end.date().toString("yyyy-MM-dd") + " 23:59:59"
        farmer = self.farmer_input.text().strip()
        disease = self.disease_combo.currentData() or None
        rows = self.logs.query(
            start=start, end=end,
            farmer=farmer or None, disease=disease,
        )
        self._fill_rows(rows)

    def _fill_rows(self, rows: list[dict]):
        self.table.setRowCount(0)
        for i, r in enumerate(rows):
            self.table.insertRow(i)
            for ci, (key, _) in enumerate(COLUMNS):
                v = r.get(key, "")
                if key == "confidence" and isinstance(v, (int, float)):
                    text = f"{v * 100:.1f}%"
                else:
                    text = str(v) if v is not None else ""
                item = QTableWidgetItem(text)
                if key == "severity_level":
                    sev = r.get("severity_level")
                    color = {
                        "Green": (200, 230, 201),
                        "Amber": (255, 224, 178),
                        "Red":   (255, 205, 210),
                    }.get(sev)
                    if color:
                        from PyQt5.QtGui import QColor
                        item.setBackground(QColor(*color))
                self.table.setItem(i, ci, item)
        self.table.resizeColumnsToContents()
        self.stat_label.setText(f"共 {len(rows)} 条")

    def _on_export(self):
        if not HAS_OPENPYXL:
            QMessageBox.warning(self, "缺少依赖", "请安装 openpyxl：pip install openpyxl")
            return
        start = self.date_start.date().toString("yyyy-MM-dd") + " 00:00:00"
        end = self.date_end.date().toString("yyyy-MM-dd") + " 23:59:59"
        farmer = self.farmer_input.text().strip()
        disease = self.disease_combo.currentData() or None
        rows = self.logs.query(start=start, end=end,
                               farmer=farmer or None, disease=disease)
        if not rows:
            QMessageBox.information(self, "提示", "当前筛选条件下无数据。")
            return
        default_name = f"廉江红橙检测台账_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Excel 报表", str(C.EXPORT_DIR / default_name),
            "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            out = export_logs(rows, Path(path))
        except Exception as e:
            QMessageBox.critical(self, "导出失败", repr(e))
            return
        QMessageBox.information(self, "导出成功",
                                f"已导出 {len(rows)} 条至：\n{out}")

    def _on_export_pdf(self):
        if not HAS_REPORTLAB:
            QMessageBox.warning(
                self, "缺少依赖", "请安装 reportlab：pip install reportlab",
            )
            return
        start = self.date_start.date().toString("yyyy-MM-dd") + " 00:00:00"
        end = self.date_end.date().toString("yyyy-MM-dd") + " 23:59:59"
        farmer = self.farmer_input.text().strip()
        disease = self.disease_combo.currentData() or ""
        rows = self.logs.query(start=start, end=end,
                               farmer=farmer or None, disease=disease or None)
        if not rows:
            QMessageBox.information(self, "提示", "当前筛选条件下无数据。")
            return
        default_name = f"廉江红橙分析报告_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 PDF 报告", str(C.EXPORT_DIR / default_name),
            "PDF (*.pdf)",
        )
        if not path:
            return
        try:
            out = export_pdf(rows, Path(path),
                             start=start, end=end,
                             farmer=farmer, disease=disease)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", repr(e))
            return
        QMessageBox.information(
            self, "导出成功",
            f"已生成 PDF 分析报告：\n{out}",
        )

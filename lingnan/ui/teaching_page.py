"""教学生成页：检测结果 → LLM/模板 生成教研文档 → 教师审核 → 导出

依据技术规范 §8.16.B / FR-G1~G7：
  - 接收检测结果上下文（由 DetectionPage.result_ready 信号送达）
  - 选择文档类型（教学案例 / 实训指导）后生成 Markdown 草稿
  - LLM 启用且配置完整 → 后台线程调用；否则 / 失败 → 模板填充降级
  - 教师审核（勾选）后方可导出 .md / .pdf（FR-G6）
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from .fluent import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LargeTitleLabel,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    TextEdit,
    TransparentPushButton,
    WEIGHT_BOLD,
    fluent_card,
    setFont,
)

from .. import config as C
from ..core import teaching
from ..core.llm_client import LLMClient, LLMConfig
from ..data.knowledge_base import KnowledgeBase
from ..data.markdown_exporter import export_markdown, export_markdown_pdf
from ..settings import Settings
from .teaching_worker import TeachingWorker

log = logging.getLogger(__name__)


class TeachingPage(QWidget):
    def __init__(self, kb: KnowledgeBase, settings: Settings):
        super().__init__()
        self.kb = kb
        self.settings = settings
        self._ctx: dict | None = None
        self._reviewed = False
        self.worker: TeachingWorker | None = None
        self._build_ui()
        self._refresh_material()
        self._set_reviewed(False)

    # ============================================================ UI
    def _build_ui(self):
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(18)

        title = LargeTitleLabel("教学生成")
        setFont(title, 28, WEIGHT_BOLD)
        lay.addWidget(title)
        cap = CaptionLabel(
            "依据最新检测结果与知识库处方，生成《教学案例》或《实训指导意见》草稿，"
            "教师审核后导出。内容仅作教研辅助，须教师确认后用于教学。"
        )
        cap.setStyleSheet("color:#6B7280;")
        cap.setWordWrap(True)
        lay.addWidget(cap)

        # 卡片 1：教学素材
        mat_card, mat_lay = fluent_card("教学素材", "来自【智能检测】页的最新结果。")
        self.material_label = BodyLabel()
        self.material_label.setWordWrap(True)
        mat_lay.addWidget(self.material_label)
        btn_row = QHBoxLayout()
        self.btn_refresh = TransparentPushButton("使用最新检测结果")
        self.btn_refresh.clicked.connect(self._refresh_material)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch(1)
        mat_lay.addLayout(btn_row)
        lay.addWidget(mat_card)

        # 卡片 2：生成方式
        gen_card, gen_lay = fluent_card("生成方式", "选择文档类型后生成草稿。")
        type_row = QHBoxLayout()
        type_row.addWidget(BodyLabel("文档类型："))
        self.type_combo = ComboBox()
        self.type_combo.addItem("岭南红橙实时防害教学案例", userData=teaching.DOC_CASE)
        self.type_combo.addItem("学生农技实训指导意见", userData=teaching.DOC_TRAINING)
        type_row.addWidget(self.type_combo, 1)
        gen_lay.addLayout(type_row)

        self.mode_label = CaptionLabel()
        self.mode_label.setStyleSheet("color:#6B7280;")
        gen_lay.addWidget(self.mode_label)

        self.btn_generate = PrimaryPushButton("生成草稿")
        self.btn_generate.clicked.connect(self._on_generate)
        gen_lay.addWidget(self.btn_generate)
        self.progress = ProgressBar()
        self.progress.setValue(0)
        gen_lay.addWidget(self.progress)
        lay.addWidget(gen_card)

        # 卡片 3：草稿审核与导出
        rev_card, rev_lay = fluent_card("草稿审核与导出", "可直接编辑草稿；审核通过后导出。")
        self.draft = TextEdit()
        self.draft.setPlaceholderText("点击「生成草稿」后在此显示，可编辑…")
        self.draft.setMinimumHeight(280)
        rev_lay.addWidget(self.draft)

        self.cb_reviewed = CheckBox("我已审核，可导出")
        self.cb_reviewed.toggled.connect(self._on_review_toggled)
        rev_lay.addWidget(self.cb_reviewed)

        self.status_label = BodyLabel()
        rev_lay.addWidget(self.status_label)

        exp_row = QHBoxLayout()
        self.btn_export_md = PushButton("导出 Markdown")
        self.btn_export_md.clicked.connect(self._on_export_md)
        exp_row.addWidget(self.btn_export_md)
        self.btn_export_pdf = PushButton("导出 PDF")
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)
        exp_row.addWidget(self.btn_export_pdf)
        exp_row.addStretch(1)
        rev_lay.addLayout(exp_row)
        lay.addWidget(rev_card)
        lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

        self._refresh_mode_label()

    # ============================================================ 槽 / 业务
    def set_context(self, ctx: dict):
        """供 MainWindow 连接 DetectionPage.result_ready。"""
        self._ctx = ctx
        self._refresh_material()

    def apply_settings(self, s: Settings):
        self.settings = s
        self._refresh_mode_label()

    def _refresh_mode_label(self):
        if getattr(self.settings, "llm_enabled", False):
            cfg = LLMConfig.from_settings(self.settings)
            if LLMClient(cfg).is_configured():
                mode_cn = "本地服务" if cfg.mode == "local" else "云端 API"
                self.mode_label.setText(
                    f"当前生成方式：🤖 LLM 智能生成（{mode_cn}：{cfg.model}）"
                )
                return
            self.mode_label.setText("当前生成方式：📝 模板生成（LLM 已启用但配置不完整）")
            return
        self.mode_label.setText("当前生成方式：📝 模板生成（如需 AI 生成请在【设置】启用）")

    def _refresh_material(self):
        ctx = self._ctx
        if not ctx:
            self.material_label.setText(
                "⚠ 暂无检测结果。请先到【智能检测】页完成一次检测，再回到本页生成。"
            )
            return
        pc = "、".join(
            f"{r['name_cn']}×{r['count']}" for r in ctx.get("per_class", [])
        ) or "无明显检出"
        self.material_label.setText(
            f"主病害：{ctx.get('primary_name_cn') or '未检出'}　"
            f"严重程度：{ctx.get('severity_cn', '—')}\n"
            f"物候期：{ctx.get('phase_name_cn', '—')}　"
            f"检出目标：{ctx.get('total_count', 0)} 个\n"
            f"分类：{pc}"
        )

    def _on_generate(self):
        if not self._ctx:
            InfoBar.warning("提示", "暂无检测结果，无法生成。", duration=2500, parent=self)
            return
        doc_type = self.type_combo.currentData()
        self._doc_type = doc_type
        system, user = teaching.build_prompts(doc_type, self._ctx)

        use_llm = getattr(self.settings, "llm_enabled", False)
        if use_llm:
            cfg = LLMConfig.from_settings(self.settings)
            client = LLMClient(cfg)
            if client.is_configured():
                self._start_llm(client, system, user)
                return
        # 模板路径（默认 / LLM 未配置）
        self._set_draft(teaching.template_fill(doc_type, self._ctx))
        InfoBar.success("已生成", "已用模板生成草稿。", duration=2000,
                        position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _start_llm(self, client: LLMClient, system: str, user: str):
        self.btn_generate.setEnabled(False)
        self.progress.setRange(0, 0)  # 不确定进度
        self.worker = TeachingWorker(client, system, user)
        self.worker.finished.connect(self._on_llm_done)
        self.worker.failed.connect(self._on_llm_failed)
        self.worker.start()

    def _end_llm(self):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.btn_generate.setEnabled(True)

    def _on_llm_done(self, md: str):
        self._end_llm()
        self._set_draft(md)
        InfoBar.success("已生成", "LLM 已生成草稿。", duration=2000,
                        position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _on_llm_failed(self, msg: str):
        self._end_llm()
        # 降级模板（FR-G7）
        self._set_draft(teaching.template_fill(self._doc_type, self._ctx))
        InfoBar.warning("LLM 不可用，已用模板生成", msg, duration=4000, parent=self)
        log.warning("LLM 生成失败，降级模板：%s", msg)

    def _set_draft(self, md: str):
        self.draft.setPlainText(md)
        self.cb_reviewed.setChecked(False)
        self._set_reviewed(False)

    def _on_review_toggled(self, checked: bool):
        self._set_reviewed(checked)

    def _set_reviewed(self, reviewed: bool):
        self._reviewed = reviewed
        self.btn_export_md.setEnabled(reviewed)
        self.btn_export_pdf.setEnabled(reviewed)
        if reviewed:
            self.status_label.setText("状态：✅ 已审核（可导出）")
            self.status_label.setStyleSheet("color:#107C10; font-weight:600;")
        else:
            self.status_label.setText("状态：⏳ 待审核（审核后方可导出）")
            self.status_label.setStyleSheet("color:#8A6A00; font-weight:600;")

    # ---------- 导出 ----------
    def _default_name(self, ext: str) -> str:
        doc_type = getattr(self, "_doc_type", teaching.DOC_CASE)
        title = teaching.DOC_TITLES.get(doc_type, "教研文档")
        return f"{title}_{datetime.now():%Y%m%d_%H%M%S}.{ext}"

    def _export_dir(self) -> Path:
        d = (self.settings.default_save_dir or "").strip()
        return Path(d) if d else C.EXPORT_DIR

    def _on_export_md(self):
        if not self._reviewed:
            return
        md = self.draft.toPlainText()
        if not md.strip():
            InfoBar.warning("提示", "草稿为空。", duration=2000, parent=self)
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Markdown",
            str(self._export_dir() / self._default_name("md")),
            "Markdown (*.md)",
        )
        if not path:
            return
        try:
            out = export_markdown(md, Path(path))
        except Exception as e:
            QMessageBox.critical(self, "导出失败", repr(e))
            return
        InfoBar.success("已导出", f"保存至：{out}", duration=2500, parent=self)

    def _on_export_pdf(self):
        if not self._reviewed:
            return
        md = self.draft.toPlainText()
        if not md.strip():
            InfoBar.warning("提示", "草稿为空。", duration=2000, parent=self)
            return
        doc_type = getattr(self, "_doc_type", teaching.DOC_CASE)
        title = teaching.DOC_TITLES.get(doc_type, "")
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 PDF",
            str(self._export_dir() / self._default_name("pdf")),
            "PDF (*.pdf)",
        )
        if not path:
            return
        try:
            out = export_markdown_pdf(md, Path(path), title=title)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", repr(e))
            return
        InfoBar.success("已导出", f"保存至：{out}", duration=2500, parent=self)

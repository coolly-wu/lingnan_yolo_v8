"""通用 Markdown 导出：写 .md 文件 + 渲染为 PDF

用于教研内容生成模块（§8.16.B）导出教师审核后的教学案例 / 实训指导。

- export_markdown：直接写 .md，零三方依赖。
- export_markdown_pdf：基于 reportlab 把 Markdown 文本渲染为 PDF，
  复用 pdf_exporter 已探测好的中文字体（_CHINESE_FONT）。
  仅支持常用子集：# / ## / ### 标题、- / * 无序列表、| 表格、空行、普通段落。

注意：不复用 pdf_exporter.export_pdf（它写死了检测台账字段），仅复用其字体惯例。
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def export_markdown(md_text: str, out_path: Path) -> Path:
    """把 Markdown 文本写入 .md 文件。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md_text, encoding="utf-8")
    log.info("Markdown 已导出：%s", out_path)
    return out_path


def _split_table_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def _is_separator_row(cells: list[str]) -> bool:
    return all(set(c) <= set("-: ") and "-" in c for c in cells) if cells else False


def export_markdown_pdf(md_text: str, out_path: Path, title: str = "") -> Path:
    """把 Markdown 文本渲染为 PDF。需要 reportlab。"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError as e:
        raise RuntimeError(
            "未安装 reportlab，无法导出 PDF：pip install reportlab"
        ) from e

    # 复用 pdf_exporter 在 import 时已探测注册好的中文字体
    from . import pdf_exporter as _pe
    font = getattr(_pe, "_CHINESE_FONT", "Helvetica")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    base = getSampleStyleSheet()
    style_body = ParagraphStyle(
        "Body", parent=base["Normal"], fontName=font, fontSize=11,
        leading=18, spaceAfter=4,
    )
    style_h1 = ParagraphStyle(
        "H1", parent=base["Heading1"], fontName=font, fontSize=20,
        leading=26, spaceBefore=6, spaceAfter=10,
    )
    style_h2 = ParagraphStyle(
        "H2", parent=base["Heading2"], fontName=font, fontSize=15,
        leading=22, spaceBefore=10, spaceAfter=6,
    )
    style_h3 = ParagraphStyle(
        "H3", parent=base["Heading3"], fontName=font, fontSize=13,
        leading=20, spaceBefore=8, spaceAfter=4,
    )
    style_bullet = ParagraphStyle(
        "Bullet", parent=style_body, leftIndent=16, bulletIndent=4,
    )

    def esc(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def inline(t: str) -> str:
        # 极简 **bold** 处理
        out = esc(t)
        while "**" in out:
            out = out.replace("**", "<b>", 1)
            out = out.replace("**", "</b>", 1)
        return out

    story = []
    if title:
        story.append(Paragraph(esc(title), style_h1))
        story.append(Spacer(1, 0.3 * cm))

    lines = md_text.splitlines()
    i = 0
    pending_table: list[list[str]] = []

    def flush_table():
        nonlocal pending_table
        if not pending_table:
            return
        # 丢弃分隔行
        rows = [r for r in pending_table if not _is_separator_row(r)]
        if rows:
            data = [[Paragraph(inline(c), style_body) for c in r] for r in rows]
            tbl = Table(data, hAlign="LEFT")
            tbl.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDBDBD")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F8E9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 0.2 * cm))
        pending_table = []

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            pending_table.append(_split_table_row(stripped))
            continue
        flush_table()
        if not stripped:
            story.append(Spacer(1, 0.15 * cm))
        elif stripped.startswith("### "):
            story.append(Paragraph(inline(stripped[4:]), style_h3))
        elif stripped.startswith("## "):
            story.append(Paragraph(inline(stripped[3:]), style_h2))
        elif stripped.startswith("# "):
            story.append(Paragraph(inline(stripped[2:]), style_h1))
        elif stripped.startswith("> "):
            story.append(Paragraph("<i>" + inline(stripped[2:]) + "</i>", style_body))
        elif stripped[:2] in ("- ", "* "):
            story.append(Paragraph("• " + inline(stripped[2:]), style_bullet))
        else:
            story.append(Paragraph(inline(stripped), style_body))
    flush_table()

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    doc.build(story)
    log.info("PDF 已导出：%s", out_path)
    return out_path

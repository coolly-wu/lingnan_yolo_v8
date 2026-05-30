"""PDF 报告导出：使用 reportlab，生成台账分析报告

包含：
  · 封面（时间范围、统计数）
  · 病虫害类别分布柱状图（ASCII 表 + 文本统计）
  · 严重程度饼状统计（文字）
  · 详细台账表（条目级）
  · 防治建议汇总

注：纯文本/表格实现，不依赖 matplotlib。Windows 上若 reportlab 无可用中文字体，
会回落使用系统 SimSun 或留英文。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Image as RLImage,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


log = logging.getLogger(__name__)


# 注册中文字体（找不到则回退）
_CHINESE_FONT = "Helvetica"


def _register_chinese_font():
    global _CHINESE_FONT
    if not HAS_REPORTLAB:
        return
    candidates = [
        ("C:/Windows/Fonts/msyh.ttc", "MSYH"),
        ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
        ("C:/Windows/Fonts/simsun.ttc", "SimSun"),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "WQYMicroHei"),
        ("/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc", "WQYZenHei"),
        ("/System/Library/Fonts/PingFang.ttc", "PingFang"),
    ]
    for path, name in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                _CHINESE_FONT = name
                return
            except Exception as e:
                log.warning("注册字体 %s 失败：%s", path, e)


_register_chinese_font()


def export_pdf(rows: list[dict], out_path: Path,
               start: str = "", end: str = "",
               farmer: str = "", disease: str = "") -> Path:
    """把若干检测日志导出为 PDF 报告。"""
    if not HAS_REPORTLAB:
        raise RuntimeError(
            "reportlab 未安装，无法导出 PDF。请运行：pip install reportlab"
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="廉江红橙病虫害检测分析报告",
        author="廉江红橙病虫害智能检测防治系统",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCN", parent=styles["Title"],
        fontName=_CHINESE_FONT, fontSize=22, leading=26,
        textColor=colors.HexColor("#1B5E20"),
        alignment=1, spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "H2CN", parent=styles["Heading2"],
        fontName=_CHINESE_FONT, fontSize=14,
        textColor=colors.HexColor("#2E7D32"),
        spaceBefore=12, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyCN", parent=styles["BodyText"],
        fontName=_CHINESE_FONT, fontSize=10, leading=14,
    )
    small_style = ParagraphStyle(
        "SmallCN", parent=body_style,
        fontSize=9, textColor=colors.HexColor("#666666"),
    )

    flow = []

    # 封面
    flow.append(Paragraph("🍊 廉江红橙病虫害检测分析报告", title_style))
    flow.append(Paragraph(
        f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}", body_style,
    ))
    period = f"{start[:10]} ~ {end[:10]}" if start and end else "全部时间"
    filt_text = f"筛选条件：时间 {period}"
    if farmer:
        filt_text += f"，农户 = {farmer}"
    if disease:
        filt_text += f"，病虫害 = {disease}"
    flow.append(Paragraph(filt_text, body_style))
    flow.append(Spacer(1, 12))

    # 总览
    flow.append(Paragraph("一、整体统计", h2_style))
    total = len(rows)
    sev_count = {"Green": 0, "Amber": 0, "Red": 0}
    disease_count: dict[str, int] = {}
    farmer_count: dict[str, int] = {}
    fatal = 0
    for r in rows:
        sev = r.get("severity_level", "")
        if sev in sev_count:
            sev_count[sev] += 1
        d = r.get("target_disease", "")
        if d:
            disease_count[d] = disease_count.get(d, 0) + 1
            if "黄龙病" in d:
                fatal += 1
        f_ = r.get("farmer_name", "") or "（未填写）"
        farmer_count[f_] = farmer_count.get(f_, 0) + 1

    overview_data = [
        ["项目", "数值"],
        ["总检测次数", str(total)],
        ["重度（Red）", str(sev_count["Red"])],
        ["中度（Amber）", str(sev_count["Amber"])],
        ["轻度（Green）", str(sev_count["Green"])],
        ["疑似/确诊黄龙病", str(fatal)],
        ["涉及农户数", str(len(farmer_count))],
        ["涉及病虫害种类", str(len(disease_count))],
    ]
    flow.append(_make_table(overview_data, [6 * cm, 4 * cm]))
    flow.append(Spacer(1, 8))

    # 病虫害分布（文本柱状图）
    flow.append(Paragraph("二、病虫害类别分布", h2_style))
    if disease_count:
        max_v = max(disease_count.values())
        bar_data = [["病虫害", "数量", "占比", "图示"]]
        for d, n in sorted(disease_count.items(), key=lambda x: -x[1]):
            bar_len = int(round((n / max_v) * 30))
            bar = "█" * bar_len
            pct = f"{n / total * 100:.1f}%"
            bar_data.append([d, str(n), pct, bar])
        flow.append(_make_table(
            bar_data,
            [4 * cm, 1.5 * cm, 1.5 * cm, 9 * cm],
            highlight_rows=[i + 1 for i, (d, _) in enumerate(
                sorted(disease_count.items(), key=lambda x: -x[1])
            ) if "黄龙病" in d],
        ))
    else:
        flow.append(Paragraph("（无数据）", body_style))
    flow.append(Spacer(1, 8))

    # 严重程度分布
    flow.append(Paragraph("三、严重程度分布", h2_style))
    sev_data = [
        ["等级", "中文", "数量", "占比"],
        ["Red", "重度", str(sev_count["Red"]),
         f"{sev_count['Red']/max(1,total)*100:.1f}%"],
        ["Amber", "中度", str(sev_count["Amber"]),
         f"{sev_count['Amber']/max(1,total)*100:.1f}%"],
        ["Green", "轻度", str(sev_count["Green"]),
         f"{sev_count['Green']/max(1,total)*100:.1f}%"],
    ]
    flow.append(_make_table(sev_data, [2.5 * cm, 2.5 * cm, 2 * cm, 3 * cm]))
    flow.append(Spacer(1, 8))

    # 农户分布 TOP10
    flow.append(Paragraph("四、农户检测分布（TOP 10）", h2_style))
    top_farmers = sorted(farmer_count.items(), key=lambda x: -x[1])[:10]
    farmer_data = [["农户", "检测次数"]] + [[f_, str(n)] for f_, n in top_farmers]
    flow.append(_make_table(farmer_data, [6 * cm, 3 * cm]))

    flow.append(PageBreak())

    # 详细台账（按时间倒序）
    flow.append(Paragraph("五、详细检测台账", h2_style))
    detail_data = [["时间", "病虫害", "等级", "数量", "置信度", "农户", "果园"]]
    for r in rows[:200]:  # 限制 200 条，避免文档过长
        conf = r.get("confidence", 0)
        if isinstance(conf, (int, float)):
            conf_text = f"{conf*100:.0f}%"
        else:
            conf_text = str(conf)
        detail_data.append([
            (r.get("datetime") or "")[:16],
            r.get("target_disease", "")[:8],
            _sev_cn(r.get("severity_level", "")),
            str(r.get("count_value", 0)),
            conf_text,
            (r.get("farmer_name", "") or "—")[:8],
            (r.get("orchard_block", "") or "—")[:8],
        ])
    flow.append(_make_table(
        detail_data,
        [3.2 * cm, 2.3 * cm, 1.3 * cm, 1.3 * cm, 1.5 * cm, 2.0 * cm, 2.0 * cm],
        font_size=8,
    ))
    if len(rows) > 200:
        flow.append(Paragraph(
            f"（仅展示前 200 条，完整数据 {len(rows)} 条请通过 Excel 导出）",
            small_style,
        ))

    # 防治建议汇总
    flow.append(Spacer(1, 12))
    flow.append(Paragraph("六、防治建议", h2_style))
    suggestions = _build_suggestions(disease_count, sev_count, fatal)
    for line in suggestions:
        flow.append(Paragraph(line, body_style))
        flow.append(Spacer(1, 4))

    # 落款
    flow.append(Spacer(1, 16))
    flow.append(Paragraph(
        "本报告由【廉江红橙病虫害智能检测防治系统】自动生成。"
        "推荐药剂均为国家登记低毒低残留药剂，请严格遵守安全间隔期（PHI）。",
        small_style,
    ))

    doc.build(flow)
    log.info("PDF 报告已导出：%s", out_path)
    return out_path


def _make_table(data: list[list[str]], col_widths: list[float],
                font_size: int = 10,
                highlight_rows: list[int] | None = None) -> Table:
    t = Table(data, colWidths=col_widths)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), _CHINESE_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0BEC5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F1F8E9")]),
    ]
    if highlight_rows:
        for r in highlight_rows:
            style.append((
                "BACKGROUND", (0, r), (-1, r),
                colors.HexColor("#FFCDD2"),
            ))
    t.setStyle(TableStyle(style))
    return t


def _sev_cn(s: str) -> str:
    return {"Green": "轻度", "Amber": "中度", "Red": "重度"}.get(s, s or "—")


def _build_suggestions(disease_count: dict, sev_count: dict, fatal: int) -> list[str]:
    items = []
    if fatal > 0:
        items.append(
            f"⚠ <b>{fatal} 次涉及黄龙病疑似/确诊</b>，请立即按规范砍除病株并就地烧毁，"
            "全园普查木虱（媒介），并向产业园管理单位上报。"
        )
    if sev_count.get("Red", 0) > 0:
        items.append(
            f"🔴 <b>{sev_count['Red']} 次重度病虫害</b>，建议优先安排技术员到园会诊，"
            "执行【物理 + 生物 + 化学】组合方案，并严格遵守 PHI。"
        )
    # TOP 3 病虫害对应建议
    top3 = sorted(disease_count.items(), key=lambda x: -x[1])[:3]
    if top3:
        items.append("📋 TOP 3 高发病虫害需重点关注：")
        for d, n in top3:
            items.append(f"　· {d}（{n} 次）：参见系统知识库对应物候期处方")
    items.append(
        "🌿 全部建议遵循绿色食品农药使用准则（NY/T 393-2020）"
        "与食品中农药最大残留限量国标（GB 2763-2021）。"
    )
    return items

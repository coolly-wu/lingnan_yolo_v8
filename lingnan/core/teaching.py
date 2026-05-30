"""教研内容生成核心（纯函数，无 Qt / 无 LLM 依赖）

依据技术规范 §8.16.B / FR-G1~G7。本模块负责：
  1. build_context() —— 把检测结果（severity.aggregate 的 summary）+ 知识库处方
     归一化为一个可序列化、便于注入提示词与模板填充的 ctx dict。
  2. build_prompts(doc_type, ctx) —— 产出 (system, user) 提示词。
  3. template_fill(doc_type, ctx) —— 纯模板填充生成 Markdown，不依赖任何 LLM，
     是默认路径，也是 LLM 不可用 / 失败时的降级路径（FR-G7）。

两种文档：
  DOC_CASE     《岭南红橙实时防害教学案例》
  DOC_TRAINING 《学生农技实训指导意见》

prompt 与 template 共享同一套章节骨架，保证 LLM 输出与降级输出结构一致，
便于教师审核与导出体验统一。
"""

from __future__ import annotations

from .. import config as C


DOC_CASE = "case"
DOC_TRAINING = "training"

DOC_TITLES = {
    DOC_CASE: "岭南红橙实时防害教学案例",
    DOC_TRAINING: "学生农技实训指导意见",
}


def _fmt_chemical(chem: list) -> list[str]:
    """把化学处方列表渲染成 Markdown 行（每条含 PHI）。"""
    lines: list[str] = []
    for c in chem or []:
        name = c.get("name", "—")
        dosage = c.get("dosage", "—")
        phi = c.get("phi", "—")
        notes = c.get("notes", "")
        line = f"- **{name}**：{dosage}；**安全间隔期 PHI：{phi}**"
        if notes:
            line += f"；注意：{notes}"
        lines.append(line)
    if not lines:
        lines.append("- 本物候期无须化学药剂，以物理 + 生物防治为主。")
    return lines


def build_context(summary: dict, dets_count: int, phase_key: str,
                  phase_name_cn: str, rx: dict | None,
                  farmer: str = "", orchard: str = "") -> dict:
    """归一化检测结果 + 知识库处方为 ctx。

    summary: core.severity.aggregate() 的返回 dict
    dets_count: len(dets)，全部检出目标数（summary['count'] 仅主病害计数）
    rx: KnowledgeBase.lookup() 的返回（可能为 None）
    """
    primary_id = summary.get("primary_id")
    severity = summary.get("severity")
    severity_cn = C.SEVERITY_LABELS_CN.get(severity, "—")

    disease = C.DISEASE_BY_ID.get(primary_id) if primary_id is not None else None
    is_fatal = bool(disease.get("fatal")) if disease else False

    # per_class 明细
    per_class_rows = []
    for v in sorted(summary.get("per_class", {}).values(),
                    key=lambda x: -x.get("count", 0)):
        per_class_rows.append({
            "name_cn": v.get("name_cn", "—"),
            "count": v.get("count", 0),
            "max_conf": v.get("max_conf", 0.0),
            "area_ratio": v.get("area_ratio", 0.0),
        })

    chemical = (rx or {}).get("chemical", []) if rx else []

    return {
        "doc_app_title": C.APP_TITLE,
        "primary_id": primary_id,
        "primary_name_cn": summary.get("primary_name_cn"),
        "primary_conf": summary.get("primary_conf", 0.0),
        "is_fatal": is_fatal,
        "disease_type": (disease or {}).get("type", ""),
        "disease_level": (disease or {}).get("level", ""),
        "total_count": dets_count,
        "primary_count": summary.get("count", 0),
        "area_ratio": summary.get("area_ratio", 0.0),
        "severity": severity,
        "severity_cn": severity_cn,
        "phase_key": phase_key,
        "phase_name_cn": phase_name_cn,
        "per_class": per_class_rows,
        "physical": (rx or {}).get("physical", "") if rx else "",
        "biological": (rx or {}).get("biological", "") if rx else "",
        "chemical": chemical,
        "severity_amplifier": (rx or {}).get("severity_amplifier", "") if rx else "",
        "farmer": farmer,
        "orchard": orchard,
    }


# ------------------------------------------------------------------ 提示词
_SYSTEM_BASE = (
    "你是岭南红橙现代农业产业园的农技教研专家，服务于高职院校农技实训教学。"
    "请根据提供的本地病虫害检测结果与已审核的绿色防治知识库处方，"
    "撰写一份结构清晰、用语规范的中文 Markdown 文档。"
    "必须严格使用给定章节结构；必须突出化学药剂的安全间隔期（PHI）；"
    "推荐药剂仅限国家登记的低毒低残留品种。"
    "若主病害为柑橘黄龙病，必须明确：确诊植株立即砍除并就地烧毁，禁止化学治疗。"
    "内容仅作为教研与实训辅助材料，需教师审核确认后用于教学。"
)

_CASE_OUTLINE = (
    "章节结构（教学案例）：\n"
    "1. 病情概述\n"
    "2. 检测依据（主病害置信度、分类计数明细、物候期）\n"
    "3. 物候期背景\n"
    "4. 三位一体绿色防治（物理 / 生物 / 化学，化学逐条列药剂·稀释·PHI·注意）\n"
    "5. 教学要点与思考题"
)

_TRAINING_OUTLINE = (
    "章节结构（实训指导）：\n"
    "1. 实训目标\n"
    "2. 操作步骤（识别 → 分级 → 选方 → 配药 → 施用）\n"
    "3. 安全注意事项（PHI、低毒低残留用药规范）\n"
    "4. 观察记录表（Markdown 表格）\n"
    "5. 考核要点"
)


def _ctx_brief(ctx: dict) -> str:
    """把 ctx 关键字段拼成给 LLM 的事实清单。"""
    pc = "；".join(
        f"{r['name_cn']}×{r['count']}(conf {r['max_conf']*100:.0f}%)"
        for r in ctx["per_class"]
    ) or "无明显检出"
    chem = "；".join(
        f"{c.get('name','—')}({c.get('dosage','—')},PHI {c.get('phi','—')})"
        for c in ctx["chemical"]
    ) or "无"
    return (
        f"主病害：{ctx['primary_name_cn'] or '未检出'}\n"
        f"主病害置信度：{ctx['primary_conf']*100:.1f}%\n"
        f"危害等级：{ctx['disease_level'] or '—'}；是否致命：{'是' if ctx['is_fatal'] else '否'}\n"
        f"检出目标总数：{ctx['total_count']}\n"
        f"分类计数：{pc}\n"
        f"面积占比：{ctx['area_ratio']*100:.2f}%\n"
        f"严重程度：{ctx['severity_cn']}\n"
        f"物候期：{ctx['phase_name_cn']}\n"
        f"物理防治：{ctx['physical'] or '—'}\n"
        f"生物防治：{ctx['biological'] or '—'}\n"
        f"化学防治：{chem}\n"
        f"重度加强：{ctx['severity_amplifier'] or '—'}\n"
        f"农户/果园：{ctx['farmer'] or '—'} / {ctx['orchard'] or '—'}"
    )


def build_prompts(doc_type: str, ctx: dict) -> tuple[str, str]:
    """返回 (system_prompt, user_prompt)。"""
    outline = _TRAINING_OUTLINE if doc_type == DOC_TRAINING else _CASE_OUTLINE
    title = DOC_TITLES.get(doc_type, DOC_TITLES[DOC_CASE])
    system = _SYSTEM_BASE + "\n\n" + outline
    user = (
        f"请生成《{title}》。文档以 `# {title}` 作为一级标题。\n\n"
        f"【检测与处方事实】\n{_ctx_brief(ctx)}\n\n"
        f"请严格按给定章节结构输出中文 Markdown。"
    )
    return system, user


# ------------------------------------------------------------------ 模板填充（降级 / 默认）
def _per_class_md(ctx: dict) -> list[str]:
    rows = ctx["per_class"]
    if not rows:
        return ["- 未检出明显目标。"]
    lines = []
    for r in rows:
        lines.append(
            f"- {r['name_cn']}：{r['count']} 个，"
            f"最高置信度 {r['max_conf']*100:.1f}%，"
            f"面积占比 {r['area_ratio']*100:.2f}%"
        )
    return lines


def _fatal_warning(ctx: dict) -> list[str]:
    if ctx["is_fatal"] or ctx["primary_name_cn"] == "柑橘黄龙病":
        return [
            "",
            "> ⚠ **黄龙病警示**：确诊植株必须立即砍除并就地烧毁，"
            "**禁止化学治疗**；同时防治木虱传播媒介。",
        ]
    return []


def _template_case(ctx: dict) -> str:
    title = DOC_TITLES[DOC_CASE]
    primary = ctx["primary_name_cn"] or "未检出明显病虫害"
    lines = [
        f"# {title}",
        "",
        f"> 本文档由「{ctx['doc_app_title']}」依据本地检测结果与已审核知识库生成，"
        "仅作教研与实训辅助材料，**须经教师审核确认后用于教学**。",
        "",
        "## 一、病情概述",
        "",
        f"- 主病害：**{primary}**",
        f"- 严重程度：**{ctx['severity_cn']}**",
        f"- 检出目标总数：{ctx['total_count']} 个",
        f"- 面积占比：{ctx['area_ratio']*100:.2f}%",
    ]
    lines += _fatal_warning(ctx)
    lines += [
        "",
        "## 二、检测依据",
        "",
        f"- 主病害置信度：{ctx['primary_conf']*100:.1f}%",
        f"- 危害等级：{ctx['disease_level'] or '—'}",
        "- 分类计数明细：",
    ]
    lines += ["  " + s for s in _per_class_md(ctx)]
    lines += [
        "",
        "## 三、物候期背景",
        "",
        f"- 当前物候期：**{ctx['phase_name_cn']}**",
    ]
    if ctx["severity_amplifier"]:
        lines.append(f"- 该期风险提示：{ctx['severity_amplifier']}")
    lines += [
        "",
        "## 四、三位一体绿色防治",
        "",
        f"**A. 物理防治（优先）**：{ctx['physical'] or '—'}",
        "",
        f"**B. 生物防治（安全）**：{ctx['biological'] or '—'}",
        "",
        "**C. 科学化学防治（合规）**：",
    ]
    lines += _fmt_chemical(ctx["chemical"])
    lines += [
        "",
        "## 五、教学要点与思考题",
        "",
        "**教学要点：**",
        f"- 掌握「{primary}」的关键视觉识别特征与严重程度分级标准。",
        "- 理解三位一体绿色防治「物理优先、生物为辅、化学合规」的原则。",
        "- 牢记化学药剂的安全间隔期（PHI），保障地理标志产品用药安全。",
        "",
        "**思考题：**",
        "1. 该病虫害在不同物候期的防治重点有何差异？",
        "2. 为什么要严格遵守安全间隔期（PHI）？超期采收有何风险？",
        "3. 如何结合田间实际制定一份成本可控的绿色防治方案？",
    ]
    return "\n".join(lines)


def _template_training(ctx: dict) -> str:
    title = DOC_TITLES[DOC_TRAINING]
    primary = ctx["primary_name_cn"] or "未检出明显病虫害"
    lines = [
        f"# {title}",
        "",
        f"> 本文档由「{ctx['doc_app_title']}」依据本地检测结果与已审核知识库生成，"
        "仅作教研与实训辅助材料，**须经教师审核确认后用于教学**。",
        "",
        "## 一、实训目标",
        "",
        f"- 能独立识别「{primary}」并判定严重程度（轻度 / 中度 / 重度）。",
        "- 能依据物候期与知识库，选配三位一体绿色防治方案。",
        "- 能规范配药、施药，并严格执行安全间隔期（PHI）。",
    ]
    lines += _fatal_warning(ctx)
    lines += [
        "",
        "## 二、操作步骤",
        "",
        "1. **识别**：使用本系统对样本拍照 / 导入，确认主病害与分类计数。",
        f"   - 本次主病害：{primary}（置信度 {ctx['primary_conf']*100:.1f}%）。",
        f"2. **分级**：依据计数与面积判定严重程度——本次为 **{ctx['severity_cn']}**。",
        "3. **选方**：按当前物候期"
        f"（{ctx['phase_name_cn']}）查知识库三位一体处方。",
        "4. **配药**：按推荐稀释倍数精确配制，做好个人防护。",
        "5. **施用**：均匀喷施，记录施药日期，倒推安全间隔期确定采收时间。",
        "",
        "## 三、安全注意事项",
        "",
        "- 仅使用国家登记的低毒低残留药剂（NY/T 393、GB 2763）。",
        "- **严格遵守每种药剂的安全间隔期（PHI）**，未到 PHI 不得采收。",
    ]
    for c in ctx["chemical"]:
        lines.append(
            f"  - {c.get('name','—')}：PHI {c.get('phi','—')}"
            + (f"；{c.get('notes')}" if c.get("notes") else "")
        )
    lines += [
        "- 配药、施药全程佩戴口罩与手套，避免高温正午作业。",
        "",
        "## 四、观察记录表",
        "",
        "| 日期 | 物候期 | 病虫害 | 严重程度 | 处置措施 | 观察结果 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
        f"|  | {ctx['phase_name_cn']} | {primary} | {ctx['severity_cn']} |  |  |",
        "|  |  |  |  |  |  |",
        "",
        "## 五、考核要点",
        "",
        "- [ ] 病虫害识别准确（类别与严重程度判定正确）。",
        "- [ ] 防治方案选择合理（三位一体、物候期匹配）。",
        "- [ ] 用药规范，正确说明并执行安全间隔期（PHI）。",
        "- [ ] 实训记录完整、规范。",
    ]
    return "\n".join(lines)


def template_fill(doc_type: str, ctx: dict) -> str:
    """纯模板填充生成 Markdown（无 LLM）。"""
    if doc_type == DOC_TRAINING:
        return _template_training(ctx)
    return _template_case(ctx)

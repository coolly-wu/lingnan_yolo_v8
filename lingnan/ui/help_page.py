"""图文手册 & 诊断信息页

左侧：3 步图文使用手册（QTextBrowser，纯 HTML）
右侧：实时诊断信息（模型 / CPU / 内存 / 日志路径 / 数据库路径 / 知识库/台账条目数）
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from .fluent import (
    BodyLabel,
    CaptionLabel,
    LargeTitleLabel,
    SubtitleLabel,
    TransparentPushButton,
    WEIGHT_BOLD,
    WEIGHT_SEMIBOLD,
    fluent_card,
    setFont,
)

from .. import __app_name__, __version__
from .. import config as C
from ..core import device_profile as dp
from ..core.inferencer import Inferencer
from ..data.knowledge_base import KnowledgeBase
from ..data.log_manager import LogManager
from ..logging_setup import LOG_DIR


log = logging.getLogger(__name__)


HELP_HTML = """
<style>
  body {{ font-family: "Microsoft YaHei","PingFang SC","WenQuanYi Micro Hei",sans-serif; }}
  h1 {{ color:#1B5E20; font-size:22pt; }}
  h2 {{ color:#2E7D32; font-size:16pt; margin-top:18px; }}
  h3 {{ color:#388E3C; font-size:14pt; }}
  p, li {{ font-size:13pt; line-height:1.55; }}
  .step {{ background:#E8F5E9; border-left:6px solid #2E7D32; padding:10px; margin:6px 0; }}
  .warn {{ background:#FFF3E0; border-left:6px solid #FB8C00; padding:10px; margin:6px 0; }}
  .danger {{ background:#FFEBEE; border-left:6px solid #C62828; padding:10px; margin:6px 0; }}
  code {{ background:#ECEFF1; padding:2px 6px; border-radius:4px; }}
  table {{ border-collapse:collapse; }}
  th, td {{ border:1px solid #BDBDBD; padding:6px 10px; }}
  th {{ background:#A5D6A7; color:#1B5E20; }}
</style>

<h1>🍊 {APP_TITLE} · 使用手册</h1>
<p>本系统服务于<b>廉江红橙现代农业产业园</b>，可识别 <b>12 类</b>常见病虫害，
按物候期推送<b>物理 + 生物 + 低毒化学</b>三位一体绿色处方，全程<b>完全离线</b>运行。</p>

<h2>🚀 三步上手</h2>

<div class="step">
<h3>第 1 步　填写农户档案</h3>
<p>切换到 <b>👨‍🌾 农户档案</b> 页，新增本次检测对应的农户姓名与果园编号；
或在 <b>🔍 智能检测</b> 页的农户下拉中选择已有档案。</p>
</div>

<div class="step">
<h3>第 2 步　导入照片，选物候期</h3>
<p>在 <b>🔍 智能检测</b> 页：</p>
<ul>
  <li>点 <b>📷 选择图片</b> 或 <b>📁 选择文件夹</b> 导入待检测照片</li>
  <li>选择当前果树物候期（春梢期 / 开花期 / 幼果期 / 挂果期 / 采收期）</li>
</ul>
</div>

<div class="step">
<h3>第 3 步　一键检测，看处方</h3>
<p>点 <b>▶ 开始检测</b>，下方自动展示：</p>
<ol>
  <li>带框可视化标注图</li>
  <li>严重程度色码（轻度 / 中度 / 重度）</li>
  <li>三位一体绿色处方，<b>含安全间隔期 PHI</b></li>
</ol>
</div>

<h2>📡 实时摄像头 / 视频文件</h2>
<p>在 <b>📡 实时摄像头</b> 页可选两种输入源：</p>
<ul>
  <li><b>USB 摄像头 / 数字显微镜</b>：插入设备后选编号，点 ▶ 开始；用于田间巡检与微距虫害放大</li>
  <li><b>本地视频文件</b>：选 mp4/avi/mov/mkv 文件，可勾选"同时导出带框视频"，系统会逐帧推理并把标注视频保存到 <code>runtime_data/exports/</code></li>
</ul>

<h2>📋 历史台账</h2>
<p><b>📋 历史台账</b> 页支持按时间段 / 农户 / 病虫害类别筛选；右上角可一键：</p>
<ul>
  <li><b>导出 Excel</b>：标准 xlsx，便于继续编辑与归档</li>
  <li><b>导出 PDF 报告</b>：含统计、TOP 病害、防治建议，适合给产业园 / 合作社</li>
</ul>

<h2>⚙ 个性化设置</h2>
<p>在 <b>⚙ 设置</b> 页可调整：</p>
<ul>
  <li>字体倍率（80% ~ 160% 适老化）</li>
  <li>默认置信度阈值 / IoU / 物候期</li>
  <li>默认保存目录</li>
  <li>是否自动写台账、是否播放重度病害提示音</li>
</ul>

<div class="danger">
<h3>⚠ 黄龙病（HLB）特别提示</h3>
<p>一旦系统检出 <b>柑橘黄龙病</b>，请：</p>
<ol>
  <li>立即砍除确诊植株并就地烧毁，<b>禁止</b>化学治疗</li>
  <li>全园普查传播媒介——<b>柑橘木虱</b></li>
  <li>填报产业园管理单位</li>
</ol>
</div>

<div class="warn">
<h3>⏰ 农药安全间隔期（PHI）</h3>
<p>所有化学处方均强制突出 PHI。<b>距离采收不足 PHI 天数严禁喷药</b>，
以保障廉江红橙国家地理标志产品的药用安全。</p>
</div>

<h2>📦 模型放置</h2>
<table>
<tr><th>优先级</th><th>文件</th><th>说明</th></tr>
<tr><td>1</td><td><code>models/yolov8s_xh_best_int8.onnx</code></td><td>推荐：INT8 量化部署版</td></tr>
<tr><td>2</td><td><code>models/yolov8s_xh_best.onnx</code></td><td>FP32 ONNX</td></tr>
<tr><td>3</td><td><code>models/yolov8s_xh_best.pt</code></td><td>Ultralytics 原始权重</td></tr>
<tr><td>4</td><td><code>models/yolov8s.pt</code></td><td>COCO 占位（演示）</td></tr>
<tr><td>5</td><td>(以上都没有)</td><td>MockSimulator（仅 UI 联调）</td></tr>
</table>

<h2>📞 联系</h2>
<p>本系统按《基于特色创新项目的岭南红橙病虫害智能监测与校本教研一体化平台技术规范文档》v3.0 实现。
版本：<b>v{VERSION}</b></p>
""".replace("{APP_TITLE}", C.APP_TITLE).replace("{VERSION}", __version__)


class HelpPage(QWidget):
    """图文手册 + 实时诊断面板"""

    def __init__(self, inferencer: Inferencer, kb: KnowledgeBase,
                 logs: LogManager, decision: "dp.TierDecision | None" = None):
        super().__init__()
        self.inferencer = inferencer
        self.kb = kb
        self.logs = logs
        self.decision = decision

        root = QHBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        # 左：手册
        manual_card, manual_lay = fluent_card("使用手册")
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(HELP_HTML)
        self.browser.setStyleSheet("QTextBrowser { font-size: 13px; }")
        manual_lay.addWidget(self.browser, 1)

        # 右：诊断
        diag_box, diag_lay = fluent_card("诊断信息", "模型、硬件、运行路径与性能状态。")
        self.diag_browser = QTextBrowser()
        self.diag_browser.setOpenExternalLinks(False)
        self.diag_browser.setStyleSheet(
            "QTextBrowser { font-size: 12px; line-height: 1.35; }"
        )
        diag_lay.addWidget(self.diag_browser, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_refresh = TransparentPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(self.btn_refresh)
        self.btn_open_log = TransparentPushButton("打开日志目录")
        self.btn_open_log.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR)))
        )
        btn_row.addWidget(self.btn_open_log)
        self.btn_open_data = TransparentPushButton("打开数据目录")
        self.btn_open_data.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(C.RUNTIME_DIR)))
        )
        btn_row.addWidget(self.btn_open_data)
        btn_row.addStretch(1)
        diag_lay.addLayout(btn_row)

        root.addWidget(manual_card, 3)
        root.addWidget(diag_box, 2)

        # 定时刷新诊断
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()

    def set_inferencer(self, inferencer: Inferencer):
        self.inferencer = inferencer
        self.refresh()

    def set_decision(self, decision: "dp.TierDecision"):
        self.decision = decision
        self.refresh()

    def refresh(self):
        info = self._collect_diag()
        self.diag_browser.setHtml(info)

    def _collect_diag(self) -> str:
        # 内存（不依赖 psutil）
        rss_mb = "?"
        try:
            import psutil  # type: ignore
            rss_mb = f"{psutil.Process().memory_info().rss / 1024 / 1024:.1f} MB"
        except Exception:
            pass
        # 模型
        mp = self.inferencer.model_path
        model_name = mp.name if mp else "MockSimulator"
        model_size = ""
        if mp and mp.exists():
            try:
                model_size = f" ({mp.stat().st_size/1024/1024:.1f} MB)"
            except Exception:
                pass
        # 档位
        tier_html = "—"
        reason_html = ""
        if self.decision is not None:
            badge = self.decision.tier_label_cn
            tier_html = (
                f"<span style='background:#2E7D32;color:white;"
                f"padding:2px 8px;border-radius:4px;'>{badge}</span>"
                f" {'(自动)' if self.decision.auto_picked else '(手动锁定)'}"
            )
            reason_html = self.decision.reason
        # 硬件
        hw = self.decision.hardware if self.decision else None
        hw_html = hw.summary if hw else "—"
        # 当天日志
        today_log = LOG_DIR / f"lingnan-{__import__('datetime').date.today():%Y-%m-%d}.log"
        log_size = ""
        if today_log.exists():
            log_size = f" ({today_log.stat().st_size/1024:.1f} KB)"
        # ONNX Runtime / Torch 可用性
        ort_ver = "—"
        try:
            import onnxruntime as _ort  # noqa
            ort_ver = _ort.__version__
        except Exception:
            pass
        torch_ver = "—"
        try:
            import torch  # noqa
            torch_ver = torch.__version__
        except Exception:
            pass
        # 推理延迟反馈
        latency = self.inferencer.avg_latency_ms
        n_samples = self.inferencer.latency_samples
        if n_samples > 0:
            kpi = "✅ 满足 KPI-04 (≤800ms)" if latency <= 800 else "⚠ 超 KPI-04"
            latency_html = (
                f"{latency:.1f} ms / 张  "
                f"<span style='color:#9E9E9E;'>(近 {n_samples} 次)</span>  "
                f"<b>{kpi}</b>"
            )
        else:
            latency_html = "（暂无样本，跑一次检测后此处会显示均值）"

        rows = [
            ("App", f"{__app_name__} v{__version__}"),
            ("OS", platform.platform()),
            ("Python", platform.python_version()),
            ("CPU 核数", str(os.cpu_count() or "?")),
            ("RAM 占用（进程）", rss_mb),
            ("📦 性能档位", tier_html),
            ("    决策原因", reason_html),
            ("    硬件画像", hw_html),
            ("推理后端", self.inferencer.backend_type),
            ("模型", model_name + model_size),
            ("📡 推理延迟（均值）", latency_html),
            ("ONNX Runtime", ort_ver),
            ("PyTorch", torch_ver),
            ("知识库条目", str(self.kb.count())),
            ("台账日志条目", str(self.logs.count())),
            ("知识库路径", str(C.KNOWLEDGE_DB)),
            ("台账路径", str(C.RUNTIME_LOG_DB)),
            ("日志文件", str(today_log) + log_size),
            ("标注图目录", str(C.ANNOTATED_DIR)),
            ("导出目录", str(C.EXPORT_DIR)),
        ]
        body = (
            "<style>"
            "body, table, td { font-family:'Segoe UI','Microsoft YaHei','PingFang SC';"
            "font-size:12px; line-height:1.35; }"
            "code { font-size:11px; }"
            "</style>"
            "<table style='border-collapse:collapse;font-size:12px;'>"
        )
        for k, v in rows:
            body += (
                f"<tr>"
                f"<td style='background:#F3F7FB;color:#374151;padding:5px 8px;"
                f"border:1px solid #E5EAF3;font-weight:600;white-space:nowrap;'>{k}</td>"
                f"<td style='background:#FFFFFF;padding:5px 8px;"
                f"border:1px solid #E5EAF3;color:#1F2937;'>{_short(v)}</td>"
                f"</tr>"
            )
        body += "</table>"
        body += (
            "<p style='color:#6B7280;font-size:11px;margin-top:8px;'>"
            "每 5 秒自动刷新；档位由【设置 → 性能档位】控制。"
            "如需 RAM 占用准确数值请 <code>pip install psutil</code>。"
            "</p>"
        )
        return body


def _short(s: str, n: int = 80) -> str:
    if "<" in s:  # 含 HTML 不截断
        return s
    if len(s) > n:
        return s[:n] + "…"
    return s


"""主窗口：Fluent 侧边导航 + 页面容器"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from .fluent import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LargeTitleLabel,
    TransparentPushButton,
    apply_app_font,
    fluent_card,
    setFont,
    WEIGHT_BOLD,
)

from .. import __app_name__, __version__
from .. import config as C
from ..core import device_profile as dp
from ..core.inferencer import Inferencer
from ..data.farmer_manager import FarmerManager
from ..data.knowledge_base import KnowledgeBase
from ..data.log_manager import LogManager
from ..settings import Settings, load_settings, save_settings
from .about_page import AboutPage
from .camera_page import CameraPage
from .collection_page import CollectionPage
from .dataset_page import DatasetPage
from .detection_page import DetectionPage
from .farmer_page import FarmerPage
from .help_page import HelpPage
from .log_page import LogPage
from .settings_page import SettingsPage
from .style import STYLE_SHEET
from .training_page import TrainingPage
from .training_result_page import TrainingResultPage


log = logging.getLogger(__name__)


class MainWindow(FluentWindow):
    def __init__(self, inferencer: Inferencer | None = None,
                 decision: "dp.TierDecision | None" = None):
        super().__init__()
        apply_app_font(self)
        self.settings = load_settings()
        self.setWindowTitle(f"{C.APP_TITLE} v{__version__}")
        self.resize(1360, 860)
        self.setMinimumSize(1024, 720)

        # ---------- 业务对象 ----------
        log.info("初始化业务对象…")
        # 按 settings 决策档位
        self.decision = decision or dp.decide_tier(forced=self.settings.perf_tier)
        log.info("档位决策：tier=%s file=%s reason=%s auto=%s",
                 self.decision.chosen_tier,
                 self.decision.chosen_file,
                 self.decision.reason,
                 self.decision.auto_picked)
        self.inferencer = inferencer or Inferencer(decision=self.decision)
        self.kb = KnowledgeBase()
        self.logs = LogManager()
        self.farmers = FarmerManager()
        log.info("推理后端=%s 模型=%s",
                 self.inferencer.backend_type, self.inferencer.model_path)

        self._build_ui()
        self._apply_font_scale(self.settings.font_scale)
        self._refresh_status()

    # ============================================================ UI
    def _build_ui(self):
        self.home_page = self._build_home_page()
        self.detection_page = DetectionPage(
            self.inferencer, self.kb, self.logs, self.farmers, self.settings,
        )
        self.detection_page.setObjectName("detectionPage")
        self.detection_page.log_inserted.connect(self._on_log_inserted)
        self.camera_page = CameraPage(self.inferencer)
        self.camera_page.setObjectName("cameraPage")
        self.collection_page = CollectionPage()
        self.collection_page.setObjectName("collectionPage")
        self.dataset_page = DatasetPage()
        self.dataset_page.setObjectName("datasetPage")
        self.collection_page.collection_finished.connect(self.dataset_page.refresh_images)
        self.training_page = TrainingPage()
        self.training_page.setObjectName("trainingPage")
        self.dataset_page.dataset_submitted.connect(self.training_page.refresh_state)
        self.training_result_page = TrainingResultPage()
        self.training_result_page.setObjectName("trainingResultPage")
        self.training_page.training_finished.connect(self.training_result_page.refresh_latest_results)
        self.log_page = LogPage(self.logs)
        self.log_page.setObjectName("logPage")
        self.farmer_page = FarmerPage(self.farmers)
        self.farmer_page.setObjectName("farmerPage")
        self.farmer_page.farmer_changed.connect(self.detection_page.refresh_farmers)
        self.settings_page = SettingsPage(self.settings)
        self.settings_page.setObjectName("settingsPage")
        self.settings_page.settings_changed.connect(self._on_settings_changed)
        self.help_page = HelpPage(self.inferencer, self.kb, self.logs,
                                   decision=self.decision)
        self.help_page.setObjectName("helpPage")
        self.about_page = AboutPage(
            model_info=self._model_info(),
            kb_count=self.kb.count(),
            log_count=self.logs.count(),
        )
        self.about_page.setObjectName("aboutPage")

        self.addSubInterface(self.home_page, FIF.HOME, "概览")
        self.addSubInterface(self.detection_page, FIF.SEARCH, "智能检测")
        self.addSubInterface(self.camera_page, FIF.CAMERA, "实时摄像头")
        self.addSubInterface(self.collection_page, FIF.DOWNLOAD, "数据采集")
        self.addSubInterface(self.dataset_page, FIF.LABEL, "数据标注")
        self.addSubInterface(self.training_page, FIF.EDUCATION, "模型训练")
        self.addSubInterface(self.training_result_page, FIF.PIE_SINGLE, "训练结果")
        self.addSubInterface(self.log_page, FIF.HISTORY, "历史台账")
        self.addSubInterface(self.farmer_page, FIF.PEOPLE, "农户档案")
        self.addSubInterface(self.settings_page, FIF.SETTING, "设置")
        self.addSubInterface(self.help_page, FIF.HELP, "帮助诊断")
        self.addSubInterface(self.about_page, FIF.INFO, "关于")

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("homePage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(18)

        title = LargeTitleLabel(C.APP_TITLE)
        setFont(title, 28, WEIGHT_BOLD)
        lay.addWidget(title)

        caption = CaptionLabel("离线检测、防治处方、数据标注与模型训练的一体化工作台")
        caption.setStyleSheet("color:#6B7280;")
        lay.addWidget(caption)

        status_card, status_lay = fluent_card("运行状态", "模型与本地数据资源状态")
        row = QHBoxLayout()
        row.setSpacing(12)
        self.model_label = BodyLabel()
        self.model_label.setMinimumWidth(360)
        row.addWidget(self.model_label, 1)
        self.btn_load_model = TransparentPushButton("加载模型")
        self.btn_load_model.clicked.connect(self._on_load_model)
        row.addWidget(self.btn_load_model)
        status_lay.addLayout(row)
        lay.addWidget(status_card)

        stats_card, stats_lay = fluent_card("本地资源", "所有数据均保存在当前项目本地目录")
        self.home_stats_label = BodyLabel()
        self.home_stats_label.setWordWrap(True)
        stats_lay.addWidget(self.home_stats_label)
        lay.addWidget(stats_card)
        lay.addStretch(1)
        return page

    def _model_info(self) -> str:
        if self.inferencer.model_path is None:
            return (
                "<b style='color:#C62828;'>⚠ 未发现专属模型</b>，"
                "当前使用 <b>模拟推理</b>（仅供 UI 联调演示）。<br>"
                "请将训练好的 <code>yolov8s_xh_best_int8.onnx</code> 放入 "
                f"<code>{C.MODELS_DIR}</code> 后重启应用。"
            )
        p = self.inferencer.model_path
        return (
            f"模型：<b>{p.name}</b><br>"
            f"后端：<b>{self.inferencer.backend_type}</b><br>"
            f"路径：<code>{p}</code>"
        )

    def _refresh_status(self):
        mp = self.inferencer.model_path
        tier = self.decision.tier_label_cn
        if mp is None:
            self.model_label.setText(f"⚠ 档位：{tier} · MockSimulator")
            self.model_label.setStyleSheet("color:#8A6A00; font-weight:600;")
        else:
            self.model_label.setText(
                f"📦 档位：{tier} · {mp.name}"
            )
            self.model_label.setStyleSheet("color:#107C10; font-weight:600;")
        if hasattr(self, "home_stats_label"):
            self.home_stats_label.setText(
                f"知识库 {self.kb.count()} 条\n"
                f"检测日志 {self.logs.count()} 条\n"
                f"农户档案 {self.farmers.count()} 户"
            )

    def _apply_font_scale(self, scale: float):
        """重新生成 QSS 应用新的字体大小"""
        app = QApplication.instance()
        if app is None:
            return
        base = int(C.UI_BASE_FONT_PT * scale)
        big = int(C.UI_BIG_BUTTON_FONT_PT * scale)
        title = int(C.UI_TITLE_FONT_PT * scale)
        qss = (
            STYLE_SHEET
            .replace(f"font-size: {C.UI_BASE_FONT_PT}pt", f"font-size: {base}pt")
            .replace(f"font-size: {C.UI_BIG_BUTTON_FONT_PT}pt", f"font-size: {big}pt")
            .replace(f"font-size: {C.UI_TITLE_FONT_PT}pt", f"font-size: {title}pt")
        )
        app.setStyleSheet(qss)

    # ============================================================ 业务
    def _on_load_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模型文件", str(C.MODELS_DIR),
            "模型文件 (*.onnx *.pt)",
        )
        if not path:
            return
        try:
            new_inf = Inferencer(Path(path))
        except Exception as e:
            InfoBar.warning("加载失败", repr(e), duration=3000, parent=self)
            log.error("加载模型失败：%s", e)
            return
        if new_inf.model_path is None:
            InfoBar.warning("提示", "加载失败，回退至 Mock 模拟器。", duration=3000, parent=self)
        self.inferencer = new_inf
        # 更新 decision 为"手动指定"
        from ..core.device_profile import TierDecision, probe_hardware
        suffix = Path(path).suffix.lower()
        if new_inf.model_path is None:
            tier = dp.TIER_MOCK
        elif suffix == ".onnx":
            tier = dp.TIER_INT8 if "int8" in Path(path).name.lower() else dp.TIER_FP32
        else:
            tier = dp.TIER_PT
        self.decision = TierDecision(
            chosen_tier=tier,
            chosen_file=new_inf.model_path,
            reason=f"用户手动加载：{Path(path).name}",
            auto_picked=False,
            hardware=self.decision.hardware,
        )
        self.detection_page.set_inferencer(new_inf)
        self.camera_page.set_inferencer(new_inf)
        self.help_page.set_inferencer(new_inf)
        self.help_page.set_decision(self.decision)
        self._refresh_status()
        InfoBar.success(
            "模型已切换",
            f"{new_inf.name} · {new_inf.backend_type}",
            duration=2200,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self,
        )
        log.info("切换模型 -> %s [%s] tier=%s",
                 new_inf.name, new_inf.backend_type, tier)

    def _on_log_inserted(self, _log_id: int):
        self.log_page.refresh()
        self._refresh_status()

    def _on_settings_changed(self, s: Settings):
        old_tier = self.settings.perf_tier
        self.settings = s
        self._apply_font_scale(s.font_scale)
        self.detection_page.apply_settings(s)
        # 档位变了 → 重新决策并切换推理后端
        if s.perf_tier != old_tier:
            new_decision = dp.decide_tier(forced=s.perf_tier)
            log.info("用户切换档位：%s → %s (file=%s)",
                     old_tier, new_decision.chosen_tier, new_decision.chosen_file)
            self.decision = new_decision
            new_inf = Inferencer(decision=new_decision)
            self.inferencer = new_inf
            self.detection_page.set_inferencer(new_inf)
            self.camera_page.set_inferencer(new_inf)
            self.help_page.set_inferencer(new_inf)
            self.help_page.set_decision(new_decision)
            self._refresh_status()
        log.info("设置已应用：font_scale=%.2f conf=%.2f tier=%s",
                 s.font_scale, s.default_conf, s.perf_tier)

    def closeEvent(self, e):
        # 摄像头优雅关闭
        try:
            self.camera_page.close()
        except Exception:
            pass
        # 保存最近一次农户
        try:
            save_settings(self.settings)
        except Exception:
            pass
        log.info("应用关闭")
        super().closeEvent(e)

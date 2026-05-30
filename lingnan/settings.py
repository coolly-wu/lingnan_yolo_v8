"""用户设置持久化：runtime_data/settings.json

包含字体倍率、默认 conf/iou、默认保存目录、自动保存开关、提示音开关等。
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config as C
from .core import device_profile as dp


SETTINGS_FILE = C.RUNTIME_DIR / "settings.json"
log = logging.getLogger(__name__)


@dataclass
class Settings:
    font_scale: float = 1.0                # 字体缩放（0.8 ~ 1.6）
    default_conf: float = C.DEFAULT_CONF
    default_iou: float = C.DEFAULT_IOU
    default_phenophase: str = "young_fruit"
    default_save_dir: str = ""             # 空则用 runtime_data/exports
    auto_save_log: bool = True             # 是否自动写台账
    enable_sound: bool = False             # 重度病害是否声音提示
    last_farmer: str = ""
    last_orchard: str = ""
    perf_tier: str = "auto"                # auto / pt / fp32 / int8 / mock

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "Settings":
        try:
            d = json.loads(s)
        except Exception:
            return cls()
        s_obj = cls()
        for k, v in d.items():
            if hasattr(s_obj, k):
                setattr(s_obj, k, v)
        if s_obj.perf_tier not in dp.TIER_LABELS_CN:
            s_obj.perf_tier = dp.TIER_AUTO
        if not isinstance(s_obj.default_phenophase, str):
            s_obj.default_phenophase = "young_fruit"
        return s_obj


def load_settings() -> Settings:
    if SETTINGS_FILE.exists():
        try:
            return Settings.from_json(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("settings.json 读取失败，回退默认：%s", e)
    return Settings()


def save_settings(s: Settings) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(s.to_json(), encoding="utf-8")
    log.info("settings.json 已保存：%s", SETTINGS_FILE)

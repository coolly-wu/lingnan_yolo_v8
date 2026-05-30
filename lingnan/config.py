"""全局配置：路径、12 类病虫害定义、物候期、颜色码"""

from __future__ import annotations

from pathlib import Path

# ---------- 项目路径 ----------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
RUNTIME_DIR = PROJECT_ROOT / "runtime_data"
ASSETS_DIR = PROJECT_ROOT / "lingnan" / "assets"

KNOWLEDGE_DB = KNOWLEDGE_DIR / "lianjiang_hongcheng.db"
RUNTIME_LOG_DB = RUNTIME_DIR / "detection_log.db"
ANNOTATED_DIR = RUNTIME_DIR / "annotated"
EXPORT_DIR = RUNTIME_DIR / "exports"
DATASET_DIR = RUNTIME_DIR / "lianjiang_hongcheng_dataset"
RAW_IMAGE_DIR = DATASET_DIR / "raw"
TRAIN_RUNS_DIR = RUNTIME_DIR / "training_runs"

for _d in (
    MODELS_DIR,
    KNOWLEDGE_DIR,
    RUNTIME_DIR,
    ANNOTATED_DIR,
    EXPORT_DIR,
    DATASET_DIR,
    RAW_IMAGE_DIR,
    TRAIN_RUNS_DIR,
):
    _d.mkdir(parents=True, exist_ok=True)

# ---------- 推理模型候选 ----------
# 优先级从高到低；首个存在的会被加载
MODEL_CANDIDATES = [
    MODELS_DIR / "yolov8s_xh_best_int8.onnx",
    MODELS_DIR / "yolov8s_xh_best.onnx",
    MODELS_DIR / "yolov8s_xh_best.pt",
    MODELS_DIR / "yolov8s.pt",
    PROJECT_ROOT / "yolov8s.pt",
    PROJECT_ROOT / "yolov8n.pt",
]

# ---------- 12 类病虫害 ----------
# id 对应模型输出通道；与 knowledge/classes.yaml 一致
DISEASE_CLASSES = [
    {"id": 0,  "key": "huanglongbing",    "name_cn": "柑橘黄龙病",  "name_en": "Citrus Huanglongbing",
     "color": (0, 0, 255),    "blink": True,  "level": "极高",
     "type": "disease", "fatal": True},
    {"id": 1,  "key": "canker",           "name_cn": "柑橘溃疡病",  "name_en": "Citrus Canker",
     "color": (0, 100, 220),  "blink": False, "level": "高",
     "type": "disease", "fatal": False},
    {"id": 2,  "key": "scab",             "name_cn": "柑橘疮痂病",  "name_en": "Citrus Scab",
     "color": (0, 140, 200),  "blink": False, "level": "中",
     "type": "disease", "fatal": False},
    {"id": 3,  "key": "anthracnose",      "name_cn": "柑橘炭疽病",  "name_en": "Citrus Anthracnose",
     "color": (60, 70, 200),  "blink": False, "level": "高",
     "type": "disease", "fatal": False},
    {"id": 4,  "key": "black_spot",       "name_cn": "柑橘黑斑病",  "name_en": "Citrus Black Spot",
     "color": (30, 30, 30),   "blink": False, "level": "中",
     "type": "disease", "fatal": False},
    {"id": 5,  "key": "red_mite",         "name_cn": "柑橘红蜘蛛",  "name_en": "Citrus Red Mite",
     "color": (0, 255, 255),  "blink": False, "level": "高",
     "type": "pest",    "fatal": False,  "swarm": True},
    {"id": 6,  "key": "psyllid",          "name_cn": "柑橘木虱",    "name_en": "Citrus Psyllid",
     "color": (180, 100, 220),"blink": False, "level": "极高",
     "type": "pest",    "fatal": False,  "swarm": True},
    {"id": 7,  "key": "leaf_miner",       "name_cn": "柑橘潜叶蛾",  "name_en": "Citrus Leaf Miner",
     "color": (200, 200, 0),  "blink": False, "level": "中",
     "type": "pest",    "fatal": False},
    {"id": 8,  "key": "aphids",           "name_cn": "柑橘蚜虫",    "name_en": "Citrus Aphids",
     "color": (0, 200, 0),    "blink": False, "level": "中",
     "type": "pest",    "fatal": False,  "swarm": True},
    {"id": 9,  "key": "scale_insects",    "name_cn": "柑橘介壳虫",  "name_en": "Citrus Scale Insects",
     "color": (180, 180, 180),"blink": False, "level": "中",
     "type": "pest",    "fatal": False},
    {"id": 10, "key": "flower_bud_midge", "name_cn": "柑橘花蕾蛆",  "name_en": "Citrus Flower Bud Midge",
     "color": (200, 0, 180),  "blink": False, "level": "中",
     "type": "pest",    "fatal": False},
    {"id": 11, "key": "blackfly",         "name_cn": "柑橘黑刺粉虱","name_en": "Citrus Blackfly",
     "color": (80, 80, 80),   "blink": False, "level": "中",
     "type": "pest",    "fatal": False,  "swarm": True},
]

DISEASE_BY_ID = {d["id"]: d for d in DISEASE_CLASSES}
DISEASE_BY_KEY = {d["key"]: d for d in DISEASE_CLASSES}
DISEASE_BY_NAME_CN = {d["name_cn"]: d for d in DISEASE_CLASSES}

# ---------- 5 个物候期 ----------
PHENOPHASES = [
    {"id": 1, "key": "sprout",     "name_cn": "春梢期/萌芽期"},
    {"id": 2, "key": "flower",     "name_cn": "开花期/谢花期"},
    {"id": 3, "key": "young_fruit","name_cn": "生理落果期/幼果期"},
    {"id": 4, "key": "enlargement","name_cn": "果实膨大期/挂果期"},
    {"id": 5, "key": "harvest",    "name_cn": "采收期/冬剪期"},
]
PHENOPHASE_BY_KEY = {p["key"]: p for p in PHENOPHASES}

# ---------- 严重程度 ----------
SEVERITY_GREEN = "Green"   # 轻度
SEVERITY_AMBER = "Amber"   # 中度
SEVERITY_RED = "Red"       # 重度
SEVERITY_THRESHOLDS = {
    "count_amber": 5,
    "count_red": 20,
    "area_amber": 0.05,
    "area_red": 0.20,
}
SEVERITY_LABELS_CN = {
    SEVERITY_GREEN: "轻度",
    SEVERITY_AMBER: "中度",
    SEVERITY_RED: "重度",
}
SEVERITY_COLORS = {
    SEVERITY_GREEN: (60, 180, 60),
    SEVERITY_AMBER: (40, 160, 230),
    SEVERITY_RED: (40, 40, 220),
}

# ---------- 推理超参 ----------
DEFAULT_CONF = 0.25
DEFAULT_IOU = 0.45
DEFAULT_IMGSZ = 640
MAX_DETECTIONS = 500

# ---------- UI 适老化 ----------
UI_BASE_FONT_PT = 14
UI_BIG_BUTTON_FONT_PT = 18
UI_TITLE_FONT_PT = 22
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

APP_TITLE = "基于特色创新项目的岭南红橙病虫害智能监测与校本教研一体化平台"

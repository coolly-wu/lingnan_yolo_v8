# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **fully offline, zero-network** PyQt5 desktop app for detecting 12 classes of Lingnan red-orange (岭南红橙) citrus pests/diseases with YOLOv8, then pushing phenophase-aware green-control prescriptions. The full implementation lives in the `xhgan/` package; `app.py` and `app_legacy.py` (an older single-file generic YOLOv8 version, kept only as backup) at the root are thin wrappers / legacy. The authoritative spec is [docs/技术规范文档.md](docs/技术规范文档.md) v3.0; domain rules (severity thresholds, PHI, huanglongbing must be destroyed not treated) trace back to it.

Code comments, UI strings, and docs are in Chinese; module/identifier names are English. Match this convention.

## Commands

```bash
# Run the app (needs the .venv with PyQt5 etc.)
python app.py          # or: python -m xhgan  / run.bat (Win) / ./run.sh

# Tests (pytest.ini sets testpaths=tests)
pytest                          # whole suite
pytest tests/test_severity.py -v   # single file
pytest tests/test_severity.py::test_name   # single test

# Generate synthetic demo images for UI bring-up (no real model needed)
python -m tools.gen_demo_images --num_per_class 2   # -> runtime_data/demo/

# Inference perf benchmark (validates KPI-04 鈮?00ms/img CPU, KPI-10 <500MB)
python -m tools.benchmark --num 100

# Model pipeline (see README "璁粌涓撳睘妯″瀷" for full 4-step flow)
python -m tools.train --data <dataset>/data.yaml --epochs 300
python -m tools.export_onnx --weights runs/.../best.pt
python -m tools.quantize_int8 --input ... --output ... --calibration_dir ...

# Package (Windows): produces dist/XHGan/XHGan.exe (+ installer if Inno Setup present)
build.bat              # or: pyinstaller build.spec
```

The venv is `.venv/`. Python **3.11.x** is required (Ultralytics/ONNX wheels).

## Architecture

**Inference backend is auto-selected at startup**, decoupled from the UI. Two layers cooperate:

1. `core/device_profile.py` 鈫?`decide_tier()` probes hardware (CPU cores, AVX2, RAM, CUDA) and, combined with which model files exist, picks one of 4 tiers: `pt` (GPU+PyTorch) > `fp32` (ONNX FP32, strong CPU) > `int8` (ONNX INT8, weak CPU) > `mock`. Returns a `TierDecision`. The user can lock a tier via `settings.perf_tier` (auto/pt/fp32/int8/mock); a locked-but-missing file auto-downgrades and is flagged in `reason`.
2. `core/inferencer.py` 鈫?`Inferencer` takes the `TierDecision` (or a file path) and instantiates one of `_UltralyticsBackend` / `_OnnxRuntimeBackend` / `_MockBackend`, all exposing `predict(img_bgr, conf, iou) -> list[Detection]`. **If no real model file exists, it silently falls back to `_MockBackend`** (random boxes) so the UI always runs.

`config.MODEL_CANDIDATES` is the file priority list; `device_profile.TIER_FILES` maps each tier to its candidate filenames. Real deployment expects `models/yolov8s_xh_best_int8.onnx`. When only a COCO `yolov8s.pt`/`yolov8n.pt` is present, `_UltralyticsBackend` detects it (`is_coco_placeholder`) and remaps a fixed subset of COCO classes onto the 12 pest IDs via `_COCO_TO_XH` 鈥?purely for demo, not real detection.

**The 12 disease classes and 5 phenophases are defined once in `config.py`** (`DISEASE_CLASSES`, `PHENOPHASES`) with `DISEASE_BY_ID/_KEY/_NAME_CN` lookup dicts. Class `id` == model output channel. Everything else (annotator colors, severity, knowledge-base keys, model `.yaml`) keys off these. Changing a class means editing `config.py` first.

**Detection 鈫?result pipeline** (`ui/worker.py` `DetectWorker`, a QThread): for each image 鈫?`inferencer.predict()` 鈫?`core/severity.aggregate()` (Green/Amber/Red from count + area thresholds in `config.SEVERITY_THRESHOLDS`; huanglongbing is always fatal/Red) 鈫?`core/annotator.draw_detections()` (Chinese-labeled boxes). Swarm pests (red_mite/aphids/psyllid/blackfly, flagged `swarm` in config) get auto-counted by `core/counter.py`. Results + the chosen phenophase drive `data/knowledge_base.py` `KnowledgeBase.lookup(disease_id, phenophase)`.

**MainWindow** (`ui/main_window.py`, a `FluentWindow`) owns the singletons 鈥?`Inferencer`, `KnowledgeBase`, `LogManager`, `FarmerManager` 鈥?and wires every page via `addSubInterface`. Pages communicate through Qt signals (e.g. `collection_page.collection_finished 鈫?dataset_page.refresh_images`; `dataset_page.dataset_submitted 鈫?training_page.refresh_state`; `training_page.training_finished 鈫?training_result_page`; `farmer_page.farmer_changed 鈫?detection_page.refresh_farmers`). Switching model/tier at runtime re-creates the `Inferencer` and pushes it to detection/camera/help pages via their `set_inferencer()`.

### Data layer (`xhgan/data/`)
- `knowledge_base.py` 鈥?SQLite at `knowledge/lianjiang_hongcheng.db`, auto-seeded on first run from `prescriptions_seed.py` (60 prescriptions, 12 diseases 脳 5 phenophases) if the table is empty. Each row carries physical/biological/chemical (chemical is JSON with PHI per agent) + severity_amplifier.
- `log_manager.py` (detection ledger, `runtime_data/detection_log.db`), `farmer_manager.py` (orchard/farmer CRUD), `excel_exporter.py` (openpyxl), `pdf_exporter.py` (reportlab, needs a CJK font 鈥?bundled from `C:/Windows/Fonts` by build.spec).

### In-app dataset 鈫?training workflow (`core/` + `ui/`)
Beyond detection, the app has a self-contained model-building loop, each step its own page:
`image_collector.py` (collect candidate images, dedupe by sha256/similarity) 鈫?`dataset_manager.py` (YOLO annotation, train/val/test split, emit `data.yaml`) 鈫?spawns `python -m xhgan.train_yolo` as a **subprocess** (Ultralytics with field-augment hyperparams) 鈫?`training_visualizer.py` parses `results.csv`/charts from the run dir. `train_yolo.publish_trained_weights()` copies `best.pt` into `models/yolov8s_xh_best.pt` so the next app launch auto-loads it.

### Paths & runtime state
All runtime artifacts live under `runtime_data/` (annotated cache, `detection_log.db`, `settings.json`, `exports/`, `logs/`, `lianjiang_hongcheng_dataset/`, `training_runs/`) 鈥?created on import of `config.py`. Logs roll daily (14-day retention) via `logging_setup.py`. `image_io.imread_unicode` exists because OpenCV can't read Chinese/Unicode paths on Windows 鈥?**use it, not `cv2.imread`, for user-supplied image paths.**

## Conventions worth keeping

- **Heavy imports are deferred**: `ultralytics`, `onnxruntime`, `torch`, `cv2` are imported inside functions/`__init__`, not at module top, so the app starts (and tests run) without them. Keep this when touching backends.
- `_BackendBase.predict` is the single contract every backend implements 鈥?add new backends there, don't special-case in `Inferencer`.
- New persisted user prefs go on the `Settings` dataclass in `settings.py` (defaults + `from_json` tolerates missing/corrupt keys). It auto-falls-back to defaults on parse failure 鈥?preserve that.
- Tests use `conftest.py` fixtures (`tmp_db`, `numpy_stub`) and operate on temp dirs; pass explicit `db_path`/`models_dir` to managers rather than touching real `runtime_data/`.

## Domain rules that are not negotiable (from the spec)

- **Huanglongbing (榛勯緳鐥? id 0)** confirmed plants must be cut down and burned; chemical treatment is forbidden. It is marked `fatal: True` and forced to Red severity.
- Prescriptions must surface the **PHI (瀹夊叏闂撮殧鏈?** of every chemical agent. Agents are restricted to nationally-registered low-toxicity ones (NY/T 393-2020, GB 2763-2021).

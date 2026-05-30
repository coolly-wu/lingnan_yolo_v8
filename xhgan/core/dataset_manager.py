"""Dataset helpers for collection, YOLO annotation, splitting and training."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .. import config as C


IMAGE_EXTS = C.SUPPORTED_IMAGE_EXTS


@dataclass(frozen=True)
class YoloBox:
    class_id: int
    cx: float
    cy: float
    w: float
    h: float

    def clamped(self) -> "YoloBox":
        return YoloBox(
            class_id=int(self.class_id),
            cx=_clamp(self.cx),
            cy=_clamp(self.cy),
            w=_clamp(self.w),
            h=_clamp(self.h),
        )


@dataclass(frozen=True)
class DatasetStats:
    raw_images: int
    annotated_images: int
    boxes: int
    train_images: int
    val_images: int
    test_images: int


@dataclass(frozen=True)
class DatasetSubmission:
    submitted: bool
    message: str
    stats: DatasetStats
    data_yaml: Path
    submitted_at: str = ""


@dataclass(frozen=True)
class TrainingDataValidation:
    valid: bool
    message: str
    data_yaml: Path
    train_path: Path | None = None
    val_path: Path | None = None
    train_images: int = 0
    val_images: int = 0


SUBMISSION_FILE = C.DATASET_DIR / "submission.json"


def ensure_dataset(root: Path = C.DATASET_DIR) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "raw").mkdir(exist_ok=True)
    for part in ("train", "val", "test"):
        (root / "images" / part).mkdir(parents=True, exist_ok=True)
        (root / "labels" / part).mkdir(parents=True, exist_ok=True)
    write_classes_yaml(root)
    write_data_yaml(root)
    write_training_hyp(root)


def import_images(paths: list[str | Path], root: Path = C.DATASET_DIR) -> list[Path]:
    """Copy images into dataset/raw, avoiding filename collisions."""
    ensure_dataset(root)
    imported: list[Path] = []
    for src in paths:
        src_path = Path(src)
        if not src_path.is_file() or src_path.suffix.lower() not in IMAGE_EXTS:
            continue
        dst = unique_path(root / "raw" / src_path.name)
        shutil.copy2(src_path, dst)
        imported.append(dst)
    return imported


def list_raw_images(root: Path = C.DATASET_DIR) -> list[Path]:
    ensure_dataset(root)
    return sorted(
        p for p in (root / "raw").rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def list_annotated_images(root: Path = C.DATASET_DIR) -> list[Path]:
    """Return raw images that have at least one YOLO annotation box."""
    return [
        image for image in list_raw_images(root)
        if read_yolo_labels(label_path_for_image(image, root))
    ]


def label_path_for_image(image_path: str | Path, root: Path = C.DATASET_DIR) -> Path:
    image_path = Path(image_path)
    if root / "raw" in image_path.parents:
        return image_path.with_suffix(".txt")
    parts = image_path.parts
    if "images" in parts:
        idx = parts.index("images")
        if idx + 1 < len(parts):
            split = parts[idx + 1]
            return root / "labels" / split / f"{image_path.stem}.txt"
    return image_path.with_suffix(".txt")


def read_yolo_labels(label_path: str | Path) -> list[YoloBox]:
    p = Path(label_path)
    if not p.exists():
        return []
    boxes: list[YoloBox] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            cls, cx, cy, w, h = parts
            boxes.append(YoloBox(int(cls), float(cx), float(cy), float(w), float(h)).clamped())
        except ValueError:
            continue
    return boxes


def write_yolo_labels(label_path: str | Path, boxes: list[YoloBox]) -> None:
    p = Path(label_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for box in boxes:
        b = box.clamped()
        lines.append(f"{b.class_id} {b.cx:.6f} {b.cy:.6f} {b.w:.6f} {b.h:.6f}")
    p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def delete_annotated_sample(image_path: str | Path, root: Path = C.DATASET_DIR) -> list[Path]:
    """Delete an annotated raw image, its label, split copies, and stale submission state."""
    return delete_raw_sample(image_path, root)


def delete_raw_sample(image_path: str | Path, root: Path = C.DATASET_DIR) -> list[Path]:
    """Delete a raw image sample, its optional label, split copies, and stale submission state."""
    ensure_dataset(root)
    root = Path(root).resolve()
    raw_root = (root / "raw").resolve()
    image = Path(image_path).resolve()
    if not _is_relative_to(image, raw_root):
        raise ValueError(f"Refusing to delete a sample outside dataset/raw: {image}")

    deleted: list[Path] = []
    label = label_path_for_image(image, root)
    for target in (image, label):
        if target.exists() and target.is_file():
            target.unlink()
            deleted.append(target)

    for part in ("train", "val", "test"):
        split_image = root / "images" / part / image.name
        split_label = root / "labels" / part / f"{image.stem}.txt"
        for target in (split_image, split_label):
            if target.exists() and target.is_file():
                target.unlink()
                deleted.append(target)

    submission_file = root / "submission.json"
    if submission_file.exists() and submission_file.is_file():
        submission_file.unlink()
        deleted.append(submission_file)

    return deleted


def clear_raw_samples(root: Path = C.DATASET_DIR) -> list[Path]:
    """Delete all imported raw samples and labels, plus split copies and stale submission state."""
    ensure_dataset(root)
    deleted: list[Path] = []
    for image in list_raw_images(root):
        deleted.extend(delete_raw_sample(image, root))
    for part in ("train", "val", "test"):
        for folder in (root / "images" / part, root / "labels" / part):
            folder.mkdir(parents=True, exist_ok=True)
            for child in list(folder.iterdir()):
                resolved = child.resolve()
                folder_root = folder.resolve()
                if folder_root not in resolved.parents and resolved != folder_root:
                    raise RuntimeError(f"拒绝删除数据集目录外文件: {resolved}")
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                deleted.append(child)
    submission_file = root / "submission.json"
    if submission_file.exists() and submission_file.is_file():
        submission_file.unlink()
        deleted.append(submission_file)
    return deleted


def stats(root: Path = C.DATASET_DIR) -> DatasetStats:
    ensure_dataset(root)
    raw = list_raw_images(root)
    annotated = 0
    boxes = 0
    for image in raw:
        labels = read_yolo_labels(label_path_for_image(image, root))
        if labels:
            annotated += 1
            boxes += len(labels)
    split_counts = {}
    for part in ("train", "val", "test"):
        split_counts[part] = len([
            p for p in (root / "images" / part).iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        ])
    return DatasetStats(
        raw_images=len(raw),
        annotated_images=annotated,
        boxes=boxes,
        train_images=split_counts["train"],
        val_images=split_counts["val"],
        test_images=split_counts["test"],
    )


def validate_for_submission(root: Path = C.DATASET_DIR) -> tuple[bool, str, DatasetStats]:
    s = stats(root)
    if s.raw_images == 0:
        return False, "请先导入采集图片。", s
    if s.annotated_images == 0:
        return False, "请至少完成一张图片的目标框标注。", s
    if s.annotated_images < s.raw_images:
        return False, f"还有 {s.raw_images - s.annotated_images} 张图片未标注。", s
    return True, "标注数据集可提交。", s


def submit_dataset(
    root: Path = C.DATASET_DIR,
    include_unannotated: bool = False,
) -> DatasetSubmission:
    ok, message, s = validate_for_submission(root)
    if not ok:
        return DatasetSubmission(False, message, s, root / "data.yaml")

    s = split_dataset(root=root, include_unannotated=include_unannotated)
    if s.train_images == 0 or s.val_images == 0:
        return DatasetSubmission(
            False,
            "数据集划分后训练集或验证集为空，请增加标注图片数量。",
            s,
            root / "data.yaml",
        )
    data_yaml = write_data_yaml(root)
    write_classes_yaml(root)
    write_training_hyp(root)
    from datetime import datetime

    submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "submitted": True,
        "submitted_at": submitted_at,
        "raw_images": s.raw_images,
        "annotated_images": s.annotated_images,
        "boxes": s.boxes,
        "train_images": s.train_images,
        "val_images": s.val_images,
        "test_images": s.test_images,
        "data_yaml": str(data_yaml),
    }
    submission_file = root / "submission.json"
    submission_file.parent.mkdir(parents=True, exist_ok=True)
    submission_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return DatasetSubmission(True, "标注数据集已提交，可开始模型训练。", s, data_yaml, submitted_at)


def load_submission(root: Path = C.DATASET_DIR) -> DatasetSubmission:
    data_yaml = root / "data.yaml"
    s = stats(root)
    submission_file = root / "submission.json"
    if not submission_file.exists():
        return DatasetSubmission(False, "尚未提交标注数据集。", s, data_yaml)
    try:
        payload = json.loads(submission_file.read_text(encoding="utf-8"))
    except Exception:
        return DatasetSubmission(False, "提交状态文件损坏，请重新提交标注数据集。", s, data_yaml)
    required = (
        payload.get("submitted") is True
        and s.train_images > 0
        and s.val_images > 0
        and data_yaml.exists()
    )
    if not required:
        return DatasetSubmission(False, "提交状态已过期，请重新提交标注数据集。", s, data_yaml)
    return DatasetSubmission(
        True,
        "标注数据集已提交，可开始模型训练。",
        s,
        data_yaml,
        str(payload.get("submitted_at", "")),
    )


def validate_training_data_yaml(data_yaml: str | Path) -> TrainingDataValidation:
    """Validate that a YOLO data.yaml points to non-empty train/val image folders."""
    data_yaml = Path(data_yaml)
    if not data_yaml.exists() or not data_yaml.is_file():
        return TrainingDataValidation(False, f"data.yaml 不存在：{data_yaml}", data_yaml)
    try:
        payload = _read_simple_yaml(data_yaml)
    except Exception as exc:
        return TrainingDataValidation(False, f"data.yaml 读取失败：{exc}", data_yaml)

    root = _resolve_yaml_path(data_yaml.parent, payload.get("path", "."))
    train_value = payload.get("train", "")
    val_value = payload.get("val", "")
    if not train_value:
        return TrainingDataValidation(False, "data.yaml 缺少 train 字段。", data_yaml)
    if not val_value:
        return TrainingDataValidation(False, "data.yaml 缺少 val 字段。", data_yaml)

    train_path = _resolve_yaml_path(root, train_value)
    val_path = _resolve_yaml_path(root, val_value)
    train_images = _count_image_files(train_path)
    val_images = _count_image_files(val_path)
    if train_images == 0:
        return TrainingDataValidation(
            False,
            f"训练集没有图片：{train_path}。请先在【数据标注】提交数据集，或选择有效的本地 data.yaml。",
            data_yaml,
            train_path,
            val_path,
            train_images,
            val_images,
        )
    if val_images == 0:
        return TrainingDataValidation(
            False,
            f"验证集没有图片：{val_path}。请先在【数据标注】提交数据集，或选择有效的本地 data.yaml。",
            data_yaml,
            train_path,
            val_path,
            train_images,
            val_images,
        )
    return TrainingDataValidation(
        True,
        f"训练数据集有效：train={train_images} 张，val={val_images} 张。",
        data_yaml,
        train_path,
        val_path,
        train_images,
        val_images,
    )


def split_dataset(
    root: Path = C.DATASET_DIR,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    seed: int = 20260528,
    include_unannotated: bool = False,
) -> DatasetStats:
    """Create YOLO images/labels train-val-test folders from raw images."""
    ensure_dataset(root)
    images = list_raw_images(root)
    if not include_unannotated:
        images = [p for p in images if read_yolo_labels(label_path_for_image(p, root))]
    rng = random.Random(seed)
    images = list(images)
    rng.shuffle(images)

    train_ratio = max(0.0, min(1.0, train_ratio))
    val_ratio = max(0.0, min(1.0 - train_ratio, val_ratio))
    n = len(images)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    if n >= 2 and n_val == 0:
        n_val = 1
    if n >= 3 and n - n_train - n_val == 0:
        n_train = max(1, n_train - 1)
    buckets = {
        "train": images[:n_train],
        "val": images[n_train:n_train + n_val],
        "test": images[n_train + n_val:],
    }

    for part in ("train", "val", "test"):
        _clear_dir(root / "images" / part)
        _clear_dir(root / "labels" / part)
        for src in buckets[part]:
            dst_img = root / "images" / part / src.name
            shutil.copy2(src, dst_img)
            src_label = label_path_for_image(src, root)
            dst_label = root / "labels" / part / f"{src.stem}.txt"
            if src_label.exists():
                shutil.copy2(src_label, dst_label)
            else:
                dst_label.write_text("", encoding="utf-8")
    write_classes_yaml(root)
    write_data_yaml(root)
    return stats(root)


def write_classes_yaml(root: Path = C.DATASET_DIR) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    lines = ["names:"]
    for disease in C.DISEASE_CLASSES:
        lines.append(f"  {disease['id']}: {disease['key']}  # {disease['name_cn']}")
    out = root / "classes.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_data_yaml(root: Path = C.DATASET_DIR) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    lines = [
        f"path: {root.as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
    ]
    for disease in C.DISEASE_CLASSES:
        lines.append(f"  {disease['id']}: {disease['key']}")
    out = root / "data.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_training_hyp(root: Path = C.DATASET_DIR) -> Path:
    """Write the field-scene augmentation profile described in the spec."""
    root.mkdir(parents=True, exist_ok=True)
    hyp = {
        "hsv_h": 0.02,
        "hsv_s": 0.8,
        "hsv_v": 0.5,
        "fliplr": 0.5,
        "flipud": 0.0,
        "degrees": 15.0,
        "translate": 0.15,
        "scale": 0.6,
        "mosaic": 1.0,
        "mixup": 0.15,
        "copy_paste": 0.2,
        "close_mosaic": 10,
    }
    out = root / "xh_field_aug.json"
    out.write_text(json.dumps(hyp, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def build_train_command(
    data_yaml: str | Path,
    model: str | Path = "yolov8s.pt",
    epochs: int = 300,
    imgsz: int = 640,
    batch: int = 8,
    project: str | Path = C.TRAIN_RUNS_DIR,
    name: str = "yolov8s_xh",
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "lingnan.train_yolo",
        "--model",
        str(model),
        "--data",
        str(data_yaml),
        "--epochs",
        str(int(epochs)),
        "--imgsz",
        str(int(imgsz)),
        "--batch",
        str(int(batch)),
        "--project",
        str(project),
        "--name",
        str(name),
    ]


def start_training(
    data_yaml: str | Path,
    model: str | Path = "yolov8s.pt",
    epochs: int = 300,
    imgsz: int = 640,
    batch: int = 8,
    project: str | Path = C.TRAIN_RUNS_DIR,
    name: str = "yolov8s_xh",
) -> subprocess.Popen:
    cmd = build_train_command(data_yaml, model, epochs, imgsz, batch, project, name)
    env = dict(**__import__("os").environ)
    cfg_dir = C.RUNTIME_DIR / "ultralytics"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    env.setdefault("YOLO_CONFIG_DIR", str(cfg_dir))
    return subprocess.Popen(
        cmd,
        cwd=str(C.PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:6]
    for i in range(1, 10000):
        candidate = path.with_name(f"{stem}_{digest}_{i}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法生成唯一文件名: {path}")


def _clear_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    root = path.resolve()
    for child in path.iterdir():
        resolved = child.resolve()
        if root not in resolved.parents and resolved != root:
            raise RuntimeError(f"拒绝删除数据集目录外文件: {resolved}")
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _read_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("'\"")
        if value and not value.startswith("{") and not value.startswith("["):
            data[key.strip()] = value
    return data


def _resolve_yaml_path(base: Path, value: str) -> Path:
    value = str(value).strip().strip("'\"")
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _count_image_files(path: Path) -> int:
    if path.is_file() and path.suffix.lower() == ".txt":
        try:
            return sum(
                1 for line in path.read_text(encoding="utf-8").splitlines()
                if Path(line.strip()).suffix.lower() in IMAGE_EXTS
            )
        except Exception:
            return 0
    if path.is_file():
        return 1 if path.suffix.lower() in IMAGE_EXTS else 0
    if not path.exists():
        return 0
    return len([
        p for p in path.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ])


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))

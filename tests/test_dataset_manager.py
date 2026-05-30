"""Dataset preparation and YOLO annotation helpers."""

from pathlib import Path


def _fake_image(path: Path):
    path.write_bytes(b"fake-jpg")


def test_label_roundtrip(tmp_path):
    from xhgan.core import dataset_manager as dm

    label = tmp_path / "a.txt"
    boxes = [
        dm.YoloBox(0, 0.5, 0.5, 0.2, 0.3),
        dm.YoloBox(5, 1.5, -1.0, 2.0, 0.1),
    ]
    dm.write_yolo_labels(label, boxes)
    loaded = dm.read_yolo_labels(label)
    assert loaded[0] == boxes[0]
    assert loaded[1].cx == 1.0
    assert loaded[1].cy == 0.0
    assert loaded[1].w == 1.0


def test_import_and_split_dataset(tmp_path):
    from xhgan.core import dataset_manager as dm

    src = tmp_path / "src"
    src.mkdir()
    for i in range(10):
        _fake_image(src / f"{i}.jpg")

    imported = dm.import_images(list(src.iterdir()), root=tmp_path / "dataset")
    assert len(imported) == 10
    for image in imported:
        dm.write_yolo_labels(
            dm.label_path_for_image(image, tmp_path / "dataset"),
            [dm.YoloBox(0, 0.5, 0.5, 0.2, 0.2)],
        )

    s = dm.split_dataset(root=tmp_path / "dataset", seed=1)
    assert s.raw_images == 10
    assert s.annotated_images == 10
    assert s.train_images == 7
    assert s.val_images == 2
    assert s.test_images == 1
    assert (tmp_path / "dataset" / "data.yaml").exists()
    assert (tmp_path / "dataset" / "classes.yaml").exists()


def test_training_command_contains_field_aug(tmp_path):
    from xhgan.core import dataset_manager as dm

    cmd = dm.build_train_command(tmp_path / "data.yaml", epochs=12, imgsz=768, batch=4)
    assert cmd[1:3] == ["-m", "xhgan.train_yolo"]
    joined = " ".join(cmd)
    assert "--epochs 12" in joined
    assert "--imgsz 768" in joined
    assert "--batch 4" in joined


def test_validate_training_data_yaml_requires_train_and_val_images(tmp_path):
    from xhgan.core import dataset_manager as dm

    root = tmp_path / "dataset"
    (root / "images" / "train").mkdir(parents=True)
    (root / "images" / "val").mkdir(parents=True)
    data_yaml = root / "data.yaml"
    data_yaml.write_text(
        f"path: {root.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: test\n",
        encoding="utf-8",
    )

    invalid = dm.validate_training_data_yaml(data_yaml)
    assert invalid.valid is False
    assert "训练集没有图片" in invalid.message

    _fake_image(root / "images" / "train" / "a.jpg")
    invalid_val = dm.validate_training_data_yaml(data_yaml)
    assert invalid_val.valid is False
    assert "验证集没有图片" in invalid_val.message

    _fake_image(root / "images" / "val" / "b.jpg")
    valid = dm.validate_training_data_yaml(data_yaml)
    assert valid.valid is True
    assert valid.train_images == 1
    assert valid.val_images == 1


def test_publish_trained_weights_to_models_dir(tmp_path):
    from xhgan.train_yolo import publish_trained_weights

    run_dir = tmp_path / "runs" / "yolov8s_xh"
    weights = run_dir / "weights"
    weights.mkdir(parents=True)
    (weights / "best.pt").write_bytes(b"best-weight")
    (weights / "last.pt").write_bytes(b"last-weight")

    copied = publish_trained_weights(run_dir, tmp_path / "models")

    assert copied == [
        tmp_path / "models" / "best.pt",
        tmp_path / "models" / "yolov8s_xh_best.pt",
        tmp_path / "models" / "yolov8s_xh_last.pt",
    ]
    assert (tmp_path / "models" / "best.pt").read_bytes() == b"best-weight"
    assert (tmp_path / "models" / "yolov8s_xh_best.pt").read_bytes() == b"best-weight"
    assert (tmp_path / "models" / "yolov8s_xh_last.pt").read_bytes() == b"last-weight"


def test_submission_required_before_training(tmp_path):
    from xhgan.core import dataset_manager as dm

    root = tmp_path / "dataset"
    dm.ensure_dataset(root)
    sub = dm.load_submission(root)
    assert sub.submitted is False

    src = tmp_path / "src"
    src.mkdir()
    for i in range(4):
        _fake_image(src / f"{i}.jpg")
    imported = dm.import_images(list(src.iterdir()), root=root)
    for image in imported:
        dm.write_yolo_labels(
            dm.label_path_for_image(image, root),
            [dm.YoloBox(0, 0.5, 0.5, 0.2, 0.2)],
        )

    submitted = dm.submit_dataset(root)
    assert submitted.submitted is True
    assert submitted.stats.train_images > 0
    assert submitted.stats.val_images > 0

    loaded = dm.load_submission(root)
    assert loaded.submitted is True
    assert loaded.data_yaml.exists()


def test_delete_annotated_sample_removes_raw_label_and_split_copies(tmp_path):
    from xhgan.core import dataset_manager as dm

    root = tmp_path / "dataset"
    raw_class = root / "raw" / "red_mite"
    raw_class.mkdir(parents=True)

    target = raw_class / "target.jpg"
    other = raw_class / "other.jpg"
    _fake_image(target)
    _fake_image(other)
    dm.write_yolo_labels(
        dm.label_path_for_image(target, root),
        [dm.YoloBox(0, 0.5, 0.5, 0.2, 0.2)],
    )
    dm.write_yolo_labels(
        dm.label_path_for_image(other, root),
        [dm.YoloBox(1, 0.5, 0.5, 0.2, 0.2)],
    )

    for part in ("train", "val", "test"):
        image_dir = root / "images" / part
        label_dir = root / "labels" / part
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        _fake_image(image_dir / "target.jpg")
        (label_dir / "target.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (root / "submission.json").write_text('{"submitted": true}', encoding="utf-8")

    deleted = dm.delete_annotated_sample(target, root)

    assert target not in dm.list_raw_images(root)
    assert not target.exists()
    assert not (raw_class / "target.txt").exists()
    for part in ("train", "val", "test"):
        assert not (root / "images" / part / "target.jpg").exists()
        assert not (root / "labels" / part / "target.txt").exists()
    assert not (root / "submission.json").exists()
    assert other.exists()
    assert (raw_class / "other.txt").exists()
    assert len(deleted) == 9


def test_delete_raw_sample_removes_unannotated_image_and_split_copies(tmp_path):
    from xhgan.core import dataset_manager as dm

    root = tmp_path / "dataset"
    raw = root / "raw"
    raw.mkdir(parents=True)
    target = raw / "target.jpg"
    _fake_image(target)
    for part in ("train", "val", "test"):
        image_dir = root / "images" / part
        label_dir = root / "labels" / part
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        _fake_image(image_dir / "target.jpg")
        (label_dir / "target.txt").write_text("", encoding="utf-8")
    (root / "submission.json").write_text('{"submitted": true}', encoding="utf-8")

    deleted = dm.delete_raw_sample(target, root)

    assert not target.exists()
    assert not (root / "submission.json").exists()
    for part in ("train", "val", "test"):
        assert not (root / "images" / part / "target.jpg").exists()
        assert not (root / "labels" / part / "target.txt").exists()
    assert len(deleted) == 8


def test_clear_raw_samples_removes_all_imported_images_and_labels(tmp_path):
    from xhgan.core import dataset_manager as dm

    root = tmp_path / "dataset"
    raw_class = root / "raw" / "huanglongbing"
    raw_class.mkdir(parents=True)
    for name in ("a.jpg", "b.jpg"):
        image = raw_class / name
        _fake_image(image)
        dm.write_yolo_labels(
            dm.label_path_for_image(image, root),
            [dm.YoloBox(0, 0.5, 0.5, 0.2, 0.2)],
        )
    dm.split_dataset(root)
    (root / "submission.json").write_text('{"submitted": true}', encoding="utf-8")

    deleted = dm.clear_raw_samples(root)

    assert dm.list_raw_images(root) == []
    assert not list(raw_class.glob("*.txt"))
    assert not (root / "submission.json").exists()
    for part in ("train", "val", "test"):
        assert not list((root / "images" / part).glob("*"))
        assert not list((root / "labels" / part).glob("*"))
    assert deleted

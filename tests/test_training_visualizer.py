"""Training result visualization helpers."""

from pathlib import Path


def test_analyze_training_run_generates_visualizations(tmp_path):
    from xhgan.core import training_visualizer as tv

    run = tmp_path / "runs" / "yolov8s_xh"
    run.mkdir(parents=True)
    (run / "results.csv").write_text(
        "\n".join([
            "epoch,train/box_loss,train/cls_loss,train/dfl_loss,val/box_loss,val/cls_loss,val/dfl_loss,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B)",
            "1,1.2,1.4,0.9,1.3,1.5,1.0,0.50,0.40,0.45,0.30",
            "2,0.8,1.0,0.7,0.9,1.1,0.8,0.70,0.65,0.68,0.50",
            "3,0.6,0.8,0.5,0.7,0.9,0.6,0.80,0.75,0.82,0.62",
        ]),
        encoding="utf-8",
    )
    (run / "confusion_matrix.png").write_bytes(b"fake")
    (run / "val_batch0_pred.jpg").write_bytes(b"fake")

    artifacts = tv.analyze_training_run(run)

    assert artifacts.valid is True
    assert artifacts.summary.epochs == 3
    assert artifacts.summary.best_map50 == 0.82
    assert artifacts.summary.best_map50_epoch == 3
    assert artifacts.summary.final_precision == 0.80
    assert artifacts.confusion_matrix == run / "confusion_matrix.png"
    assert artifacts.predictions == [run / "val_batch0_pred.jpg"]
    assert artifacts.generated_charts["loss"].exists()
    assert artifacts.generated_charts["precision_recall"].exists()
    assert artifacts.generated_charts["map"].exists()
    assert "训练总损失" in artifacts.interpretation.loss
    assert "最终 Precision" in artifacts.interpretation.precision_recall
    assert "最佳 mAP50" in artifacts.interpretation.map
    assert "混淆矩阵" in artifacts.interpretation.confusion_matrix
    assert "预测结果图" in artifacts.interpretation.predictions
    assert "总体判断" in artifacts.interpretation.overall


def test_analyze_training_run_handles_missing_directory(tmp_path):
    from xhgan.core import training_visualizer as tv

    artifacts = tv.analyze_training_run(tmp_path / "missing")

    assert artifacts.valid is False
    assert "暂无训练结果目录" in artifacts.message

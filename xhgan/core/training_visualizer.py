"""Training result parsing and visualization helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .. import config as C


@dataclass(frozen=True)
class TrainingSummary:
    best_map50: float | None = None
    best_map50_epoch: int | None = None
    best_map5095: float | None = None
    best_map5095_epoch: int | None = None
    final_precision: float | None = None
    final_recall: float | None = None
    epochs: int = 0


@dataclass(frozen=True)
class TrainingInterpretation:
    loss: str = "暂无 Loss 曲线数据。"
    precision_recall: str = "暂无 Precision / Recall 曲线数据。"
    map: str = "暂无 mAP 曲线数据。"
    confusion_matrix: str = "暂无混淆矩阵。"
    predictions: str = "暂无预测结果展示图。"
    overall: str = "暂无可总结的训练结果。"


@dataclass(frozen=True)
class TrainingArtifacts:
    run_dir: Path
    valid: bool
    message: str
    summary: TrainingSummary = field(default_factory=TrainingSummary)
    interpretation: TrainingInterpretation = field(default_factory=TrainingInterpretation)
    generated_charts: dict[str, Path] = field(default_factory=dict)
    builtin_charts: dict[str, Path] = field(default_factory=dict)
    confusion_matrix: Path | None = None
    predictions: list[Path] = field(default_factory=list)
    labels: list[Path] = field(default_factory=list)
    result_csv: Path | None = None


def latest_run_dir(project: Path = C.TRAIN_RUNS_DIR) -> Path:
    project.mkdir(parents=True, exist_ok=True)
    candidates = [p for p in project.iterdir() if p.is_dir()]
    if not candidates:
        return project / "yolov8s_xh"
    return max(candidates, key=lambda p: p.stat().st_mtime)


def analyze_training_run(run_dir: str | Path | None = None) -> TrainingArtifacts:
    run_dir = Path(run_dir) if run_dir else latest_run_dir()
    if not run_dir.exists():
        return TrainingArtifacts(run_dir, False, "暂无训练结果目录。")

    result_csv = run_dir / "results.csv"
    rows = _read_results_csv(result_csv)
    summary = _summary_from_rows(rows)
    interpretation = _interpret_training(rows, summary, run_dir)
    charts = generate_visualizations(run_dir, rows) if rows else {}
    builtin = _collect_builtin_charts(run_dir)
    confusion = _first_existing(
        run_dir / "confusion_matrix_normalized.png",
        run_dir / "confusion_matrix.png",
    )
    predictions = sorted(run_dir.glob("val_batch*_pred.jpg"))
    labels = sorted(run_dir.glob("val_batch*_labels.jpg"))

    valid = bool(rows or builtin or confusion or predictions)
    if rows:
        message = "训练结果已加载。"
    elif valid:
        message = "训练结果不完整：未找到 results.csv，仅展示已有图片。"
    else:
        message = "该目录不是有效 YOLOv8 训练结果目录。"
    return TrainingArtifacts(
        run_dir=run_dir,
        valid=valid,
        message=message,
        summary=summary,
        interpretation=interpretation,
        generated_charts=charts,
        builtin_charts=builtin,
        confusion_matrix=confusion,
        predictions=predictions,
        labels=labels,
        result_csv=result_csv if result_csv.exists() else None,
    )


def generate_visualizations(run_dir: str | Path, rows: list[dict[str, float]]) -> dict[str, Path]:
    if not rows:
        return {}
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    _configure_plot_fonts(plt)

    run_dir = Path(run_dir)
    out_dir = run_dir / "visualizations"
    out_dir.mkdir(parents=True, exist_ok=True)
    epochs = _series(rows, "epoch") or list(range(1, len(rows) + 1))
    charts: dict[str, Path] = {}

    loss_path = out_dir / "loss_curves.png"
    _plot_lines(
        plt,
        loss_path,
        epochs,
        rows,
        [
            ("train/box_loss", "train box"),
            ("train/cls_loss", "train cls"),
            ("train/dfl_loss", "train dfl"),
            ("val/box_loss", "val box"),
            ("val/cls_loss", "val cls"),
            ("val/dfl_loss", "val dfl"),
        ],
        "训练集与验证集损失变化曲线",
        "Loss",
    )
    charts["loss"] = loss_path

    pr_path = out_dir / "precision_recall_curves.png"
    _plot_lines(
        plt,
        pr_path,
        epochs,
        rows,
        [
            ("metrics/precision(B)", "Precision"),
            ("metrics/recall(B)", "Recall"),
        ],
        "精度、召回率变化曲线",
        "Score",
    )
    charts["precision_recall"] = pr_path

    map_path = out_dir / "map_curves.png"
    _plot_lines(
        plt,
        map_path,
        epochs,
        rows,
        [
            ("metrics/mAP50(B)", "mAP50"),
            ("metrics/mAP50-95(B)", "mAP50-95"),
        ],
        "mAP50、mAP50-95 指标曲线",
        "mAP",
    )
    charts["map"] = map_path
    return charts


def _read_results_csv(path: Path) -> list[dict[str, float]]:
    if not path.exists():
        return []
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row: dict[str, float] = {}
            for key, value in raw.items():
                key = (key or "").strip()
                if not key:
                    continue
                try:
                    row[key] = float(str(value).strip())
                except ValueError:
                    continue
            if row:
                rows.append(row)
    return rows


def _summary_from_rows(rows: list[dict[str, float]]) -> TrainingSummary:
    if not rows:
        return TrainingSummary()
    map50 = _series(rows, "metrics/mAP50(B)")
    map5095 = _series(rows, "metrics/mAP50-95(B)")
    precision = _series(rows, "metrics/precision(B)")
    recall = _series(rows, "metrics/recall(B)")
    best_map50, best_map50_epoch = _best_value_epoch(map50)
    best_map5095, best_map5095_epoch = _best_value_epoch(map5095)
    return TrainingSummary(
        best_map50=best_map50,
        best_map50_epoch=best_map50_epoch,
        best_map5095=best_map5095,
        best_map5095_epoch=best_map5095_epoch,
        final_precision=precision[-1] if precision else None,
        final_recall=recall[-1] if recall else None,
        epochs=len(rows),
    )


def _interpret_training(
    rows: list[dict[str, float]],
    summary: TrainingSummary,
    run_dir: Path,
) -> TrainingInterpretation:
    if not rows:
        confusion = "存在混淆矩阵图片，可人工检查对角线是否集中、非对角线误分是否明显。" if _first_existing(run_dir / "confusion_matrix_normalized.png", run_dir / "confusion_matrix.png") else "暂无混淆矩阵。"
        predictions = "存在预测结果图，可人工核对漏检、误检和框定位质量。" if list(run_dir.glob("val_batch*_pred.jpg")) else "暂无预测结果展示图。"
        return TrainingInterpretation(confusion_matrix=confusion, predictions=predictions)

    train_loss = _sum_series(rows, ["train/box_loss", "train/cls_loss", "train/dfl_loss"])
    val_loss = _sum_series(rows, ["val/box_loss", "val/cls_loss", "val/dfl_loss"])
    precision = _series(rows, "metrics/precision(B)")
    recall = _series(rows, "metrics/recall(B)")
    map50 = _series(rows, "metrics/mAP50(B)")
    map5095 = _series(rows, "metrics/mAP50-95(B)")

    loss_text = _loss_interpretation(train_loss, val_loss)
    pr_text = _precision_recall_interpretation(precision, recall)
    map_text = _map_interpretation(map50, map5095, summary)
    confusion_text = (
        "混淆矩阵用于查看各类别之间的误分关系。理想情况是主对角线颜色最深；如果某两类在非对角线位置颜色明显，说明这两类视觉特征接近，需要补充样本或细化标注。"
        if _first_existing(run_dir / "confusion_matrix_normalized.png", run_dir / "confusion_matrix.png")
        else "暂无混淆矩阵图片。训练正常完成后，Ultralytics 通常会生成 confusion_matrix.png。"
    )
    predictions_text = (
        "预测结果图用于人工复核模型落框质量。重点检查：病斑是否框全、微小虫害是否漏检、健康区域是否误检、密集目标是否重复框选。"
        if list(run_dir.glob("val_batch*_pred.jpg"))
        else "暂无预测结果展示图。训练验证阶段正常执行后，通常会生成 val_batch*_pred.jpg。"
    )
    overall = _overall_interpretation(summary, train_loss, val_loss, precision, recall)
    return TrainingInterpretation(
        loss=loss_text,
        precision_recall=pr_text,
        map=map_text,
        confusion_matrix=confusion_text,
        predictions=predictions_text,
        overall=overall,
    )


def _loss_interpretation(train_loss: list[float], val_loss: list[float]) -> str:
    if not train_loss or not val_loss:
        return "Loss 数据不完整，无法判断训练集与验证集收敛关系。"
    train_drop = _relative_drop(train_loss)
    val_drop = _relative_drop(val_loss)
    gap = val_loss[-1] - train_loss[-1]
    text = (
        f"训练总损失从 {_fmt_float(train_loss[0])} 降至 {_fmt_float(train_loss[-1])}，"
        f"下降约 {train_drop:.1%}；验证总损失从 {_fmt_float(val_loss[0])} 降至 {_fmt_float(val_loss[-1])}，"
        f"下降约 {val_drop:.1%}。"
    )
    if train_drop > 0.25 and val_drop > 0.15 and gap <= max(0.5, train_loss[-1] * 0.6):
        return text + "两条曲线整体同步下降，说明模型基本收敛，当前过拟合风险较低。"
    if train_drop > 0.25 and (val_drop < 0.05 or gap > max(0.8, train_loss[-1])):
        return text + "训练损失下降但验证损失改善有限，存在过拟合或验证集分布不一致风险，建议增加数据增强、补充验证样本或启用早停。"
    if train_drop < 0.1 and val_drop < 0.1:
        return text + "损失下降不明显，模型可能尚未充分学习，建议检查标签质量、学习率、训练轮次和类别样本量。"
    return text + "曲线有一定改善，建议结合 mAP 和预测图进一步判断模型质量。"


def _precision_recall_interpretation(precision: list[float], recall: list[float]) -> str:
    if not precision or not recall:
        return "Precision / Recall 数据不完整，无法判断误检与漏检平衡。"
    p = precision[-1]
    r = recall[-1]
    text = f"最终 Precision 为 {_fmt_float(p)}，Recall 为 {_fmt_float(r)}。"
    if p >= 0.85 and r >= 0.85:
        return text + "精度和召回率均较高，误检与漏检控制较均衡。"
    if p >= 0.85 and r < 0.75:
        return text + "精度较高但召回偏低，模型较保守，可能漏检小目标或早期病斑；可适当降低置信度阈值并补充难例样本。"
    if p < 0.75 and r >= 0.85:
        return text + "召回较高但精度偏低，模型倾向多报，需重点检查误检类别、健康负样本和相似症状样本。"
    if abs(p - r) > 0.15:
        return text + "两项指标差距较大，建议结合 PR 曲线重新选择部署置信度阈值。"
    return text + "指标仍有提升空间，建议优先检查类别样本均衡性和标注一致性。"


def _map_interpretation(map50: list[float], map5095: list[float], summary: TrainingSummary) -> str:
    if not map50 or not map5095:
        return "mAP 数据不完整，无法判断综合检测质量。"
    gap = map50[-1] - map5095[-1]
    text = (
        f"最佳 mAP50 为 {_fmt_float(summary.best_map50)}{_epoch_text(summary.best_map50_epoch)}，"
        f"最佳 mAP50-95 为 {_fmt_float(summary.best_map5095)}{_epoch_text(summary.best_map5095_epoch)}。"
    )
    if summary.best_map50 is not None and summary.best_map50 >= 0.9 and summary.best_map5095 is not None and summary.best_map5095 >= 0.65:
        return text + "综合识别能力较好，且较高 IoU 下仍保持一定精度，说明框定位质量可接受。"
    if gap > 0.35:
        return text + "mAP50 与 mAP50-95 差距较大，说明能识别目标但框定位还不够精细，建议提高标注边界一致性并增加高质量近景样本。"
    if summary.best_map50 is not None and summary.best_map50 < 0.75:
        return text + "mAP50 偏低，模型尚不适合直接部署，建议检查类别映射、标签质量和数据量。"
    return text + "指标处于可继续优化阶段，建议结合混淆矩阵定位薄弱类别。"


def _overall_interpretation(
    summary: TrainingSummary,
    train_loss: list[float],
    val_loss: list[float],
    precision: list[float],
    recall: list[float],
) -> str:
    points: list[str] = []
    if summary.best_map50 is not None:
        if summary.best_map50 >= 0.9:
            points.append("mAP50 达到较高水平")
        elif summary.best_map50 >= 0.75:
            points.append("mAP50 具备继续调优基础")
        else:
            points.append("mAP50 偏低，暂不建议部署")
    if precision and recall:
        if precision[-1] >= 0.85 and recall[-1] >= 0.85:
            points.append("误检与漏检控制较均衡")
        elif precision[-1] < recall[-1]:
            points.append("需要重点降低误检")
        else:
            points.append("需要重点降低漏检")
    if train_loss and val_loss:
        if val_loss[-1] - train_loss[-1] > max(0.8, train_loss[-1]):
            points.append("存在过拟合风险")
        else:
            points.append("训练/验证损失差距可控")
    if not points:
        return "训练结果信息不足，建议确认 results.csv、混淆矩阵和验证预测图是否完整生成。"
    return "总体判断：" + "；".join(points) + "。建议最终结合混淆矩阵和预测展示图人工复核薄弱类别后，再决定是否发布为正式检测模型。"


def _plot_lines(plt, out: Path, epochs: list[float], rows: list[dict[str, float]],
                columns: list[tuple[str, str]], title: str, ylabel: str) -> None:
    plt.figure(figsize=(9.6, 5.4), dpi=140)
    plotted = False
    for column, label in columns:
        values = _series(rows, column)
        if not values:
            continue
        plt.plot(epochs[:len(values)], values, linewidth=2, label=label)
        plotted = True
    plt.title(title)
    plt.xlabel("Epoch")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.25)
    if plotted:
        plt.legend()
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def _collect_builtin_charts(run_dir: Path) -> dict[str, Path]:
    names = {
        "results": "results.png",
        "pr": "PR_curve.png",
        "precision": "P_curve.png",
        "recall": "R_curve.png",
        "f1": "F1_curve.png",
    }
    return {key: run_dir / name for key, name in names.items() if (run_dir / name).exists()}


def _configure_plot_fonts(plt) -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "PingFang SC",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def _series(rows: list[dict[str, float]], key: str) -> list[float]:
    return [row[key] for row in rows if key in row]


def _sum_series(rows: list[dict[str, float]], keys: list[str]) -> list[float]:
    values: list[float] = []
    for row in rows:
        parts = [row[key] for key in keys if key in row]
        if parts:
            values.append(sum(parts))
    return values


def _relative_drop(values: list[float]) -> float:
    if not values or values[0] == 0:
        return 0.0
    return (values[0] - values[-1]) / abs(values[0])


def _best_value_epoch(values: list[float]) -> tuple[float | None, int | None]:
    if not values:
        return None, None
    best = max(values)
    return best, values.index(best) + 1


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _fmt_float(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def _epoch_text(epoch: int | None) -> str:
    return "" if epoch is None else f"（epoch {epoch}）"

"""推理性能基准测试

针对当前 Inferencer 后端做：
  · N 张图片连续推理，平均/中位/p95 耗时
  · 内存增长（需 psutil）

对应技术规范 KPI-04~07 验收。

用法：
    python -m tools.benchmark --images runtime_data/demo --num 100
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="推理性能基准")
    p.add_argument("--images", required=False,
                   help="图片目录（默认从 demo 目录拿；若没有就生成噪点图）")
    p.add_argument("--num", type=int, default=100, help="迭代次数")
    p.add_argument("--warmup", type=int, default=5, help="预热次数")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--iou", type=float, default=0.45)
    p.add_argument("--model", default=None, help="模型路径（默认按规则自动）")
    return p.parse_args(argv)


def _load_images(directory: Path | None, n: int, imgsz: int):
    import numpy as np
    from lingnan.core.image_io import imread_unicode

    if directory is None or not directory.exists():
        print(f"[!] 图片目录不存在或未指定，使用随机噪点图替代")
        return [np.random.randint(0, 255, (imgsz, imgsz, 3), dtype="uint8")
                for _ in range(n)]
    files = sorted(
        [p for p in directory.rglob("*") if p.suffix.lower() in
         {".jpg", ".jpeg", ".png", ".bmp"}]
    )
    if not files:
        print(f"[!] {directory} 下无图片，使用随机噪点图替代")
        return [np.random.randint(0, 255, (imgsz, imgsz, 3), dtype="uint8")
                for _ in range(n)]
    out = []
    while len(out) < n:
        for f in files:
            img = imread_unicode(f)
            if img is None:
                continue
            out.append(img)
            if len(out) >= n:
                break
    return out


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sys.path.insert(0, str(PROJECT_ROOT))

    from lingnan.core.inferencer import Inferencer

    inf = Inferencer(Path(args.model) if args.model else None)
    print(f"==> 推理后端: {inf.backend_type}   模型: {inf.name}")

    imgs = _load_images(Path(args.images) if args.images else None,
                        args.num + args.warmup, args.imgsz)
    print(f"==> 准备 {len(imgs)} 张图片，包含 {args.warmup} 张预热")

    # 预热
    for img in imgs[: args.warmup]:
        inf.predict(img, args.conf, args.iou)

    # 计时
    times_ms: list[float] = []
    try:
        import psutil
        proc = psutil.Process()
        rss0 = proc.memory_info().rss
    except Exception:
        proc = None
        rss0 = 0

    for img in imgs[args.warmup:]:
        t0 = time.perf_counter()
        inf.predict(img, args.conf, args.iou)
        times_ms.append((time.perf_counter() - t0) * 1000.0)

    rss1 = proc.memory_info().rss if proc is not None else 0
    delta_mb = (rss1 - rss0) / 1024 / 1024 if proc is not None else 0

    times_ms.sort()
    p50 = statistics.median(times_ms)
    p95 = times_ms[int(len(times_ms) * 0.95)]
    avg = statistics.mean(times_ms)
    mn = min(times_ms)
    mx = max(times_ms)

    print()
    print("======== 推理性能基准 ========")
    print(f"  样本数        : {args.num}")
    print(f"  最小延迟      : {mn:8.2f} ms")
    print(f"  最大延迟      : {mx:8.2f} ms")
    print(f"  平均延迟      : {avg:8.2f} ms")
    print(f"  P50 延迟      : {p50:8.2f} ms")
    print(f"  P95 延迟      : {p95:8.2f} ms")
    print(f"  吞吐量        : {1000.0/avg:8.2f} fps")
    if proc is not None:
        print(f"  内存增长      : {delta_mb:8.2f} MB")
    print()
    print("KPI 校验（依据技术规范 §1.4）:")
    print(f"  KPI-04 单图 CPU 推理 ≤ 800 ms       --> {'✓ PASS' if avg <= 800 else '✗ FAIL'}  (实测 {avg:.1f} ms)")
    if proc is not None:
        print(f"  KPI-10 连续推理内存 < 500 MB      --> {'✓ PASS' if delta_mb < 500 else '✗ FAIL'}  (实测 {delta_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

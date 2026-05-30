"""后台推理 Worker：单线程逐张推理，回传 annotated + detections + summary"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from ..core import severity as sv
from ..core.annotator import draw_detections
from ..core.image_io import imread_unicode
from ..core.inferencer import Detection, Inferencer


class DetectWorker(QThread):
    progress = pyqtSignal(int, int)                    # (cur, total)
    one_done = pyqtSignal(str, object, list, dict, float)  # (path, annotated_bgr, detections, summary, elapsed_ms)
    finished_all = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, inferencer: Inferencer, image_paths: list[str],
                 conf: float, iou: float):
        super().__init__()
        self.inferencer = inferencer
        self.image_paths = image_paths
        self.conf = conf
        self.iou = iou
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            total = len(self.image_paths)
            for idx, p in enumerate(self.image_paths, 1):
                if self._stop:
                    break
                img = imread_unicode(p)
                if img is None:
                    self.error.emit(f"无法读取图片: {p}")
                    continue
                t0 = time.perf_counter()
                dets: list[Detection] = self.inferencer.predict(img, self.conf, self.iou)
                summary = sv.aggregate(dets, img.shape[1], img.shape[0])
                annotated = draw_detections(img, dets, summary)
                elapsed = (time.perf_counter() - t0) * 1000.0
                self.inferencer.record_latency(elapsed)
                self.one_done.emit(p, annotated, dets, summary, elapsed)
                self.progress.emit(idx, total)
            self.finished_all.emit()
        except Exception as e:
            self.error.emit(repr(e))

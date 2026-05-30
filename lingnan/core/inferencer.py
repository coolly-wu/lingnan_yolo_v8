"""推理引擎：自动选择后端

后端优先级（按 config.MODEL_CANDIDATES 顺序首个找到的为准）：
    1. yolov8s_xh_best_int8.onnx  (ONNX Runtime INT8)
    2. yolov8s_xh_best.onnx       (ONNX Runtime FP32)
    3. yolov8s_xh_best.pt         (Ultralytics)
    4. yolov8s.pt / yolov8n.pt    (COCO 占位 + 类别映射)

若以上文件都不存在 → 走 MockInferencer（随机模拟，用于纯 UI 联调）

对外统一接口：
    Inferencer.predict(img_bgr) -> Detection 列表

Detection 字段：
    cls_id        模型原始类 id
    disease       12 类映射后的病虫害 dict（来自 config.DISEASE_BY_ID）
                   如果是 COCO 占位映射到 12 类
    conf          置信度
    xyxy          [x1, y1, x2, y2] 像素坐标
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .. import config as C

_ULTRALYTICS_CFG_DIR = C.RUNTIME_DIR / "ultralytics"
_ULTRALYTICS_CFG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_ULTRALYTICS_CFG_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(_ULTRALYTICS_CFG_DIR / "matplotlib"))


# --------- COCO -> 12 类 占位映射 ----------
# 当未提供专属模型时，把 COCO 部分类临时映射到 12 类用于演示
# 这只是占位，真实部署须替换为 yolov8s_xh 训练后的模型
_COCO_TO_XH = {
    "person":     0,   # huanglongbing  (仅占位)
    "bus":        1,   # canker
    "car":        2,   # scab
    "truck":      3,   # anthracnose
    "bicycle":    4,   # black_spot
    "bird":       5,   # red_mite
    "cat":        6,   # psyllid
    "dog":        7,   # leaf_miner
    "bottle":     8,   # aphids
    "cup":        9,   # scale_insects
    "chair":     10,   # flower_bud_midge
    "tv":        11,   # blackfly
}


@dataclass
class Detection:
    cls_id: int                # 12 类病虫害 id (0~11)
    conf: float
    xyxy: list[float]
    disease: dict = field(default_factory=dict)

    @property
    def name_cn(self) -> str:
        return self.disease.get("name_cn", "?")

    @property
    def color_bgr(self) -> tuple[int, int, int]:
        return tuple(self.disease.get("color", (0, 255, 0)))  # type: ignore

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.xyxy
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


# ---------------------------------------------------------------- 后端基类
class _BackendBase:
    name: str = "base"
    backend_type: str = "none"

    def predict(self, img_bgr: np.ndarray, conf: float, iou: float) -> list[Detection]:
        raise NotImplementedError


# ---------------------------------------------------------------- Ultralytics 后端
class _UltralyticsBackend(_BackendBase):
    backend_type = "ultralytics"

    def __init__(self, model_path: Path):
        from ultralytics import YOLO  # 延迟导入
        cfg_dir = C.RUNTIME_DIR / "ultralytics"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(cfg_dir))
        os.environ.setdefault("MPLCONFIGDIR", str(cfg_dir / "matplotlib"))
        self.model = YOLO(str(model_path))
        self.name = model_path.name
        self.model_path = model_path
        self.names = self.model.names if hasattr(self.model, "names") else {}
        # 判断是否为占位 COCO 模型（类名包含 'person' 等）
        self.is_coco_placeholder = (
            isinstance(self.names, dict)
            and "person" in self.names.values()
        )

    def predict(self, img_bgr: np.ndarray, conf: float, iou: float) -> list[Detection]:
        results = self.model.predict(
            source=img_bgr,
            conf=conf,
            iou=iou,
            verbose=False,
            imgsz=C.DEFAULT_IMGSZ,
            max_det=C.MAX_DETECTIONS,
        )
        if not results:
            return []
        r = results[0]
        dets: list[Detection] = []
        if r.boxes is None or len(r.boxes) == 0:
            return dets
        for box in r.boxes:
            cls_id = int(box.cls.item())
            cf = float(box.conf.item())
            xyxy = box.xyxy.cpu().numpy().flatten().tolist()
            cls_name = self.names.get(cls_id, str(cls_id)) if isinstance(self.names, dict) else str(cls_id)
            # 映射
            if self.is_coco_placeholder:
                if cls_name not in _COCO_TO_XH:
                    continue
                xh_id = _COCO_TO_XH[cls_name]
            else:
                xh_id = cls_id
                if xh_id not in C.DISEASE_BY_ID:
                    continue
            disease = C.DISEASE_BY_ID[xh_id]
            dets.append(Detection(
                cls_id=xh_id,
                conf=cf,
                xyxy=[round(v, 2) for v in xyxy],
                disease=disease,
            ))
        return dets


# ---------------------------------------------------------------- ONNX Runtime 后端
class _OnnxRuntimeBackend(_BackendBase):
    backend_type = "onnxruntime"

    def __init__(self, model_path: Path):
        import onnxruntime as ort  # 延迟导入
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        providers = ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(model_path), so, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        ishape = self.session.get_inputs()[0].shape
        self.input_h = int(ishape[2]) if isinstance(ishape[2], int) else C.DEFAULT_IMGSZ
        self.input_w = int(ishape[3]) if isinstance(ishape[3], int) else C.DEFAULT_IMGSZ
        self.name = model_path.name
        self.model_path = model_path

    @staticmethod
    def _letterbox(img: np.ndarray, new_size: tuple[int, int]) -> tuple[np.ndarray, float, tuple[int, int]]:
        import cv2
        nh, nw = new_size
        h, w = img.shape[:2]
        r = min(nw / w, nh / h)
        rw, rh = int(round(w * r)), int(round(h * r))
        resized = cv2.resize(img, (rw, rh), interpolation=cv2.INTER_LINEAR)
        pad_w, pad_h = nw - rw, nh - rh
        top, left = pad_h // 2, pad_w // 2
        out = np.full((nh, nw, 3), 114, dtype=np.uint8)
        out[top:top + rh, left:left + rw] = resized
        return out, r, (left, top)

    @staticmethod
    def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> list[int]:
        if boxes.size == 0:
            return []
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep: list[int] = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            if order.size == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
            inds = np.where(iou <= iou_thr)[0]
            order = order[inds + 1]
        return keep

    def predict(self, img_bgr: np.ndarray, conf: float, iou: float) -> list[Detection]:
        import cv2
        h0, w0 = img_bgr.shape[:2]
        lb, r, (dx, dy) = self._letterbox(img_bgr, (self.input_h, self.input_w))
        rgb = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        chw = rgb.transpose(2, 0, 1)[None]  # 1x3xHxW
        out = self.session.run(None, {self.input_name: chw})[0]
        # YOLOv8 ONNX 输出形状：(1, 4 + num_classes, N)；转置至 (N, 4+num_classes)
        if out.ndim == 3:
            out = out[0]
        if out.shape[0] < out.shape[1]:
            out = out.T  # -> (N, 4+nc)
        nc = out.shape[1] - 4
        boxes = out[:, :4]                            # xywh (center)
        cls_scores = out[:, 4:4 + nc]
        cls_ids = cls_scores.argmax(axis=1)
        scores = cls_scores.max(axis=1)
        keep = scores > conf
        boxes, cls_ids, scores = boxes[keep], cls_ids[keep], scores[keep]
        if boxes.size == 0:
            return []
        # xywh -> xyxy
        xy = boxes[:, :2]
        wh = boxes[:, 2:4]
        xyxy = np.concatenate([xy - wh / 2.0, xy + wh / 2.0], axis=1)
        # letterbox 逆变换
        xyxy[:, [0, 2]] -= dx
        xyxy[:, [1, 3]] -= dy
        xyxy /= r
        xyxy[:, [0, 2]] = xyxy[:, [0, 2]].clip(0, w0 - 1)
        xyxy[:, [1, 3]] = xyxy[:, [1, 3]].clip(0, h0 - 1)
        # 逐类 NMS
        dets: list[Detection] = []
        for c in np.unique(cls_ids):
            mask = cls_ids == c
            kept = self._nms(xyxy[mask], scores[mask], iou)
            sub_boxes = xyxy[mask][kept]
            sub_scores = scores[mask][kept]
            cid = int(c)
            if cid not in C.DISEASE_BY_ID:
                continue
            disease = C.DISEASE_BY_ID[cid]
            for b, s in zip(sub_boxes, sub_scores):
                dets.append(Detection(
                    cls_id=cid,
                    conf=float(s),
                    xyxy=[round(float(v), 2) for v in b.tolist()],
                    disease=disease,
                ))
        dets.sort(key=lambda d: d.conf, reverse=True)
        return dets[: C.MAX_DETECTIONS]


# ---------------------------------------------------------------- Mock 后端
class _MockBackend(_BackendBase):
    """无任何模型可用时的演示后端：在图像内生成 1~6 个随机病虫害框。"""
    backend_type = "mock"

    def __init__(self):
        self.name = "MockSimulator(无真实模型)"
        self.model_path = None

    def predict(self, img_bgr: np.ndarray, conf: float, iou: float) -> list[Detection]:
        h, w = img_bgr.shape[:2]
        n = random.randint(1, 6)
        dets: list[Detection] = []
        for _ in range(n):
            cls_id = random.randint(0, len(C.DISEASE_CLASSES) - 1)
            disease = C.DISEASE_BY_ID[cls_id]
            bw = random.randint(int(w * 0.05), int(w * 0.3))
            bh = random.randint(int(h * 0.05), int(h * 0.3))
            x1 = random.randint(0, max(1, w - bw - 1))
            y1 = random.randint(0, max(1, h - bh - 1))
            score = random.uniform(max(conf, 0.4), 0.99)
            dets.append(Detection(
                cls_id=cls_id,
                conf=score,
                xyxy=[float(x1), float(y1), float(x1 + bw), float(y1 + bh)],
                disease=disease,
            ))
        # 群聚虫害额外多生成几个小框
        if any(d.disease.get("swarm") for d in dets):
            base = next(d for d in dets if d.disease.get("swarm"))
            for _ in range(random.randint(4, 15)):
                bw = random.randint(8, 30)
                bh = random.randint(8, 30)
                x1 = random.randint(0, max(1, w - bw - 1))
                y1 = random.randint(0, max(1, h - bh - 1))
                dets.append(Detection(
                    cls_id=base.cls_id,
                    conf=random.uniform(max(conf, 0.4), 0.95),
                    xyxy=[float(x1), float(y1), float(x1 + bw), float(y1 + bh)],
                    disease=base.disease,
                ))
        return dets


# ---------------------------------------------------------------- 对外 Inferencer
class Inferencer:
    """统一推理入口，按档位决策结果挑选后端

    使用方式：
        inf = Inferencer()                              # 完全自动
        inf = Inferencer(model_path=Path("xxx.onnx"))   # 强制指定文件
        inf = Inferencer(decision=tier_decision)        # 用预先计算的 TierDecision
    """

    def __init__(self, model_path: Path | None = None,
                 decision: "object | None" = None):
        self.backend: _BackendBase
        self.model_path: Path | None = None
        self.decision = decision   # type: ignore[assignment]
        # 推理延迟历史（最近 50 次，毫秒）
        self._latencies: list[float] = []

        if decision is not None and getattr(decision, "chosen_file", None):
            # 用 decision 指定的文件
            self._init_backend(decision.chosen_file)   # type: ignore[attr-defined]
        elif decision is not None and getattr(decision, "chosen_tier", None) == "mock":
            self.backend = _MockBackend()
            self.model_path = None
        else:
            self._init_backend(model_path)

    def _init_backend(self, model_path: Path | None):
        candidates = [model_path] if model_path else []
        candidates.extend(C.MODEL_CANDIDATES)
        for p in candidates:
            if p is None:
                continue
            p = Path(p)
            if not p.exists():
                continue
            try:
                if p.suffix.lower() == ".onnx":
                    self.backend = _OnnxRuntimeBackend(p)
                else:
                    self.backend = _UltralyticsBackend(p)
                self.model_path = p
                return
            except Exception as e:
                print(f"[Inferencer] 加载 {p.name} 失败: {e!r}")
                continue
        # 全部失败 → 走 Mock
        self.backend = _MockBackend()
        self.model_path = None

    @property
    def name(self) -> str:
        return self.backend.name

    @property
    def backend_type(self) -> str:
        return self.backend.backend_type

    @property
    def avg_latency_ms(self) -> float:
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)

    @property
    def latency_samples(self) -> int:
        return len(self._latencies)

    def record_latency(self, ms: float):
        """供 UI worker 调用，记录推理耗时"""
        self._latencies.append(ms)
        if len(self._latencies) > 50:
            self._latencies.pop(0)

    def predict(self, img_bgr: np.ndarray, conf: float = C.DEFAULT_CONF,
                iou: float = C.DEFAULT_IOU) -> list[Detection]:
        if img_bgr is None or img_bgr.size == 0:
            return []
        return self.backend.predict(img_bgr, conf, iou)

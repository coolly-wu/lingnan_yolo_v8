"""设备性能矩阵预设：硬件探测 + 4 档模型档位决策

四档定义（性能由高到低）：
  - PT      (PyTorch)：GPU/CUDA 可用，跑 .pt 直接最快最准
  - FP32    (ONNX FP32 in CPU)：中高端 CPU + 充足内存 + 无 GPU
  - INT8    (ONNX INT8 in CPU)：低端 CPU 或内存紧张
  - MOCK    模拟器：所有真实模型都不存在时的兜底

决策依据（按优先级，技术规范 §3.2 NFR-03 / §7.3 性能预算）：
  1. GPU 可用 + 有 .pt 文件               → PT
  2. AVX2 + 内存 ≥ 6G + 物理核 ≥ 4        → FP32（精度优先）
  3. 否则若有 INT8                        → INT8（速度优先）
  4. 任何模型都没有                       → MOCK

用户可以：
  · 不动 → 系统每次启动自动选
  · 在【设置】里把 perf_tier 锁定为某一档（auto / pt / fp32 / int8 / mock）
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .. import config as C


log = logging.getLogger(__name__)


# ---------- 档位常量 ----------
TIER_AUTO = "auto"
TIER_PT = "pt"
TIER_FP32 = "fp32"
TIER_INT8 = "int8"
TIER_MOCK = "mock"

TIER_LABELS_CN = {
    TIER_AUTO: "自动（推荐）",
    TIER_PT:   "PT · GPU 高精度",
    TIER_FP32: "FP32 · CPU 高精度",
    TIER_INT8: "INT8 · CPU 高速度",
    TIER_MOCK: "Mock · 仅演示",
}
TIER_ORDER = [TIER_PT, TIER_FP32, TIER_INT8, TIER_MOCK]


# 每档对应候选文件名（按优先级排前的优先）
TIER_FILES: dict[str, list[str]] = {
    TIER_PT:   ["yolov8s_xh_best.pt", "yolov8s.pt", "yolov8n.pt"],
    TIER_FP32: ["yolov8s_xh_best.onnx"],
    TIER_INT8: ["yolov8s_xh_best_int8.onnx"],
}


# ---------- 硬件探测 ----------
@dataclass
class HardwareProfile:
    cpu_brand: str = "?"
    cpu_arch: str = "?"
    cpu_count_logical: int = 1
    cpu_count_physical: int = 1
    has_avx2: bool = False
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    has_cuda: bool = False
    gpu_name: str = ""
    os_name: str = ""

    @property
    def summary(self) -> str:
        gpu = f"GPU: {self.gpu_name}" if self.has_cuda else "GPU: 无"
        return (
            f"{self.cpu_brand} · {self.cpu_count_physical}核/{self.cpu_count_logical}线程"
            f" · AVX2={'是' if self.has_avx2 else '否'}"
            f" · RAM {self.total_ram_gb:.1f}G "
            f"(可用 {self.available_ram_gb:.1f}G) · {gpu}"
        )


def probe_hardware() -> HardwareProfile:
    p = HardwareProfile()
    p.os_name = platform.platform()
    p.cpu_arch = platform.machine()
    p.cpu_brand = platform.processor() or platform.machine()
    p.cpu_count_logical = os.cpu_count() or 1

    # 物理核数
    try:
        import psutil  # type: ignore
        p.cpu_count_physical = psutil.cpu_count(logical=False) or p.cpu_count_logical
        mem = psutil.virtual_memory()
        p.total_ram_gb = mem.total / 1024 ** 3
        p.available_ram_gb = mem.available / 1024 ** 3
    except Exception:
        p.cpu_count_physical = p.cpu_count_logical
        # 从 /proc/meminfo 或 Win API 读 fallback
        p.total_ram_gb, p.available_ram_gb = _ram_fallback()

    # AVX2 探测
    p.has_avx2 = _detect_avx2()

    # GPU 探测（不要因为 torch 未装就报错）
    p.has_cuda, p.gpu_name = _detect_cuda()

    log.info("硬件探测：%s", p.summary)
    return p


def _ram_fallback() -> tuple[float, float]:
    """psutil 不可用时的兜底"""
    try:
        if platform.system() == "Linux":
            data = Path("/proc/meminfo").read_text()
            total = available = 0.0
            for line in data.splitlines():
                if line.startswith("MemTotal:"):
                    total = float(line.split()[1]) / 1024 / 1024
                elif line.startswith("MemAvailable:"):
                    available = float(line.split()[1]) / 1024 / 1024
            return total, available
        elif platform.system() == "Windows":
            import ctypes
            class MEMSTAT(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            ms = MEMSTAT()
            ms.dwLength = ctypes.sizeof(MEMSTAT)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return ms.ullTotalPhys / 1024 ** 3, ms.ullAvailPhys / 1024 ** 3
    except Exception:
        pass
    return 0.0, 0.0


def _detect_avx2() -> bool:
    """探测 CPU 是否支持 AVX2 指令集"""
    # 方式 1：cpuinfo（pypi）若装了最准
    try:
        import cpuinfo  # type: ignore
        flags = cpuinfo.get_cpu_info().get("flags", []) or []
        return "avx2" in flags
    except Exception:
        pass
    # 方式 2：Linux /proc/cpuinfo
    if platform.system() == "Linux":
        try:
            data = Path("/proc/cpuinfo").read_text()
            return " avx2 " in (" " + data + " ").lower()
        except Exception:
            pass
    # 方式 3：通过 numpy 看 CPU features（间接但常用）
    try:
        import numpy as _np  # type: ignore
        # numpy ≥1.22 提供 __cpu_features__
        feats = getattr(_np, "__cpu_features__", None)
        if feats and feats.get("AVX2"):
            return True
    except Exception:
        pass
    # 方式 4：通过 ONNX Runtime 的可用 providers 推断（间接）
    # （略，避免引入硬依赖）
    # 方式 5：保守判断——CPU 代号包含明显高代号
    brand = (platform.processor() or "").lower()
    # Ryzen / EPYC 全系支持 AVX2
    if "ryzen" in brand or "epyc" in brand:
        return True
    # Intel 第 4 代起 (Haswell 2013) 支持 AVX2
    if "intel" in brand:
        import re
        m = re.search(r"i\d-(\d{4,5})", brand)
        if m:
            n = int(m.group(1))
            return n >= 4000
        # Intel Family 6 Model >= 60 是 Haswell+
        m = re.search(r"model (\d+)", brand)
        if m:
            return int(m.group(1)) >= 60
    return False


def _detect_cuda() -> tuple[bool, str]:
    """探测 NVIDIA GPU + CUDA 是否可用"""
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            return True, name
    except Exception:
        pass
    # 兜底：看是否有 nvidia-smi
    if shutil.which("nvidia-smi"):
        return True, "NVIDIA GPU (nvidia-smi 检测到，未启用 PyTorch CUDA)"
    return False, ""


# ---------- 档位决策 ----------
@dataclass
class TierDecision:
    chosen_tier: str = TIER_MOCK
    chosen_file: Optional[Path] = None
    reason: str = ""
    auto_picked: bool = True   # True=系统自动选，False=用户手动锁
    hardware: HardwareProfile = field(default_factory=HardwareProfile)
    candidates_found: dict[str, Optional[Path]] = field(default_factory=dict)

    @property
    def tier_label_cn(self) -> str:
        return TIER_LABELS_CN.get(self.chosen_tier, self.chosen_tier)


def find_first_existing(
    filenames: list[str],
    models_dir: Path,
    include_project_root: bool = True,
) -> Optional[Path]:
    for name in filenames:
        p = models_dir / name
        if p.exists():
            return p
        if include_project_root:
            # 也找根目录（一些用户会直接放根）
            p2 = C.PROJECT_ROOT / name
            if p2.exists():
                return p2
    return None


def decide_tier(forced: str = TIER_AUTO,
                hardware: Optional[HardwareProfile] = None,
                models_dir: Optional[Path] = None) -> TierDecision:
    """根据硬件 + 用户偏好 + 文件可用性 决策最终档位

    forced: settings.perf_tier 值
            - TIER_AUTO：自动选最优
            - TIER_PT/FP32/INT8/MOCK：尝试锁定，若文件缺失自动降级并标记
    """
    if forced not in TIER_LABELS_CN:
        forced = TIER_AUTO
    hardware = hardware or probe_hardware()
    include_project_root = models_dir is None
    models_dir = models_dir or C.MODELS_DIR

    # 找出每档对应的可用文件
    candidates: dict[str, Optional[Path]] = {}
    for tier in (TIER_PT, TIER_FP32, TIER_INT8):
        candidates[tier] = find_first_existing(
            TIER_FILES[tier], models_dir, include_project_root=include_project_root
        )

    decision = TierDecision(hardware=hardware, candidates_found=candidates)

    # 1) 用户锁定
    if forced != TIER_AUTO:
        decision.auto_picked = False
        if forced == TIER_MOCK:
            decision.chosen_tier = TIER_MOCK
            decision.reason = "用户在设置中锁定为 Mock 演示档"
            return decision
        if forced in candidates and candidates[forced] is not None:
            decision.chosen_tier = forced
            decision.chosen_file = candidates[forced]
            decision.reason = f"用户在设置中锁定为 {TIER_LABELS_CN[forced]}"
            return decision
        # 锁定但文件缺失 → 自动降级
        log.warning("用户锁定 %s 但模型文件缺失，自动降级", forced)
        decision.reason = (
            f"用户锁定 {TIER_LABELS_CN[forced]}，但模型文件缺失 → 自动降级"
        )
        # 落入 auto 决策（保持 auto_picked=False 标记，加上 reason 提示）
        return _auto_decide(decision, candidates, hardware)

    # 2) auto 自动决策
    decision.auto_picked = True
    return _auto_decide(decision, candidates, hardware)


def _auto_decide(decision: TierDecision,
                 candidates: dict[str, Optional[Path]],
                 hw: HardwareProfile) -> TierDecision:
    """根据硬件 + 文件可用性自动选档"""
    pt = candidates.get(TIER_PT)
    fp32 = candidates.get(TIER_FP32)
    int8 = candidates.get(TIER_INT8)

    # 规则 1：有 GPU + 有 PT
    if hw.has_cuda and pt is not None:
        decision.chosen_tier = TIER_PT
        decision.chosen_file = pt
        decision.reason = f"检测到 GPU（{hw.gpu_name}），优先 PyTorch 后端"
        if not decision.reason.startswith("用户"):
            pass
        return decision

    # 规则 2：高配 CPU 且有 FP32
    is_powerful_cpu = (
        hw.has_avx2
        and hw.cpu_count_physical >= 4
        and hw.total_ram_gb >= 6.0
    )
    if is_powerful_cpu and fp32 is not None:
        decision.chosen_tier = TIER_FP32
        decision.chosen_file = fp32
        decision.reason = (
            f"中高端 CPU（{hw.cpu_count_physical}核 / RAM {hw.total_ram_gb:.1f}G / AVX2），"
            "选 ONNX FP32 兼顾精度"
        )
        return decision

    # 规则 3：有 INT8 文件 → INT8（低端 CPU 首选）
    if int8 is not None:
        decision.chosen_tier = TIER_INT8
        decision.chosen_file = int8
        decision.reason = (
            "选 ONNX INT8：在低端 CPU 上速度 ↑2~3×、体积 ↓4×"
            if not is_powerful_cpu
            else "INT8 是当前唯一可用的部署模型"
        )
        return decision

    # 规则 4：FP32 没匹配上但有 PT → 退到 PT（CPU 推理）
    if fp32 is not None:
        decision.chosen_tier = TIER_FP32
        decision.chosen_file = fp32
        decision.reason = "选 ONNX FP32（INT8 不存在）"
        return decision
    if pt is not None:
        decision.chosen_tier = TIER_PT
        decision.chosen_file = pt
        decision.reason = "选 PyTorch（无 ONNX 模型，CPU 推理较慢但可用）"
        return decision

    # 规则 5：什么都没有
    decision.chosen_tier = TIER_MOCK
    decision.chosen_file = None
    decision.reason = "未发现任何可用模型 → Mock 演示模式（请将训练好的模型放入 models/）"
    return decision

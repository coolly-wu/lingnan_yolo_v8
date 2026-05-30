# 基于特色创新项目的岭南红橙病虫害智能监测与校本教研一体化平台

依据 [docs/技术规范文档.md](docs/技术规范文档.md) v3.0 实现的**完全本地化、零网络依赖**桌面应用。

## ✨ 核心能力

- **12 类岭南红橙高发病虫害**本地识别（黄龙病、溃疡病、疮痂病、炭疽病、黑斑病、红蜘蛛、木虱、潜叶蛾、蚜虫、介壳虫、花蕾蛆、黑刺粉虱）
- **三位一体绿色防治方案**（物理 + 生物 + 低毒化学）按物候期联动推送，强制突出 **安全间隔期（PHI）**
- **5 个物候期**联动：春梢期 / 开花期 / 幼果期 / 挂果期 / 采收期
- **严重程度自动分级**：Green / Amber / Red
- **群聚虫害自动计数**（红蜘蛛 / 蚜虫 / 木虱 / 黑刺粉虱）
- **UVC USB 摄像头 / 数字显微镜**实时检测
- **本地视频文件**逐帧检测 + 一键导出带框视频
- **本地 SQLite 台账** + 一键 **Excel 报表导出**（无需 MS Office）
- **PDF 分析报告**导出（统计 + TOP 病害 + 防治建议）
- **农户/果园档案管理**：CRUD + 下拉选择
- **个性化设置**：字体倍率、默认阈值、保存目录、提示音
- **诊断面板**：实时显示模型、内存、知识库条目、日志路径
- **完整工具链**：训练 / ONNX 导出 / INT8 量化 / 性能基准 / 演示图生成
- **PyInstaller 一键打包** + Inno Setup 安装向导
- **完全离线**，所有图像与台账保存在本地，零外传

## 📂 项目结构

```
yolov8_gui/
├── app.py                          # 启动入口
├── app_legacy.py                   # 原通用 YOLOv8 单文件版本（备份）
├── requirements.txt
├── build.spec / build.bat / installer.iss   # 打包配置
├── run.bat / run.sh                # 启动脚本
├── pytest.ini
├── docs/
│   ├── 技术规范文档.md             # v3.0 主规范
│   └── 可行性研究报告.md           # v3.0
├── models/                         # 把训练好的 yolov8s_xh_best_int8.onnx 放这里
├── knowledge/                      # 自动生成 lianjiang_hongcheng.db（60 条防治方案）
├── runtime_data/                   # 标注图缓存 + 检测日志库 + Excel/PDF 导出 + 日志
├── lingnan/                          # 主包
│   ├── config.py                   # 12 类病虫害 + 5 物候期 + 阈值常量
│   ├── settings.py                 # 用户设置 settings.json
│   ├── logging_setup.py            # 日志配置
│   ├── core/
│   │   ├── inferencer.py           # 多后端推理（ONNX / Ultralytics / Mock）
│   │   ├── annotator.py            # 彩色定界框 + 中文标签
│   │   ├── severity.py             # 严重程度三级分级
│   │   ├── counter.py              # 群聚虫害计数
│   │   └── image_io.py             # 中文路径兼容 I/O
│   ├── data/
│   │   ├── knowledge_base.py       # SQLite 知识库
│   │   ├── prescriptions_seed.py   # 60 条防治方案种子
│   │   ├── log_manager.py          # 检测日志台账
│   │   ├── farmer_manager.py       # 农户档案
│   │   ├── excel_exporter.py       # openpyxl 报表
│   │   └── pdf_exporter.py         # reportlab 分析报告
│   └── ui/
│       ├── main_window.py          # 主窗口 + Tab 容器
│       ├── detection_page.py       # 智能检测页
│       ├── camera_page.py          # 实时摄像头 + 视频文件
│       ├── log_page.py             # 历史台账（Excel + PDF）
│       ├── farmer_page.py          # 农户/果园档案
│       ├── settings_page.py        # 设置页
│       ├── help_page.py            # 图文手册 + 实时诊断
│       ├── about_page.py           # 关于
│       ├── widgets.py              # 共用控件
│       ├── worker.py               # 后台推理线程
│       └── style.py                # 适老化 QSS 样式
├── tools/                          # 工程化脚本
│   ├── yolov8s_xh.yaml             # 12 类 + P2 小目标 head 架构
│   ├── train.py                    # 一键训练
│   ├── export_onnx.py              # 一键导 ONNX
│   ├── quantize_int8.py            # INT8 静态量化
│   ├── benchmark.py                # 推理性能基准
│   └── gen_demo_images.py          # 12 类合成演示图
└── tests/                          # pytest 测试套
    ├── conftest.py
    ├── test_severity.py
    ├── test_knowledge_base.py
    ├── test_log_manager.py
    ├── test_excel_exporter.py
    ├── test_settings.py
    ├── test_inferencer.py
    └── test_logging.py
```

## 🚀 快速开始

### 1. 创建 Python 3.11 虚拟环境

```bash
# Windows
py -3.11 -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 启动应用

```bash
python app.py
# 或： python -m lingnan
# Windows 双击： run.bat
# Linux/macOS： ./run.sh
```

### 4. 生成演示图（可选，便于首次联调）

```bash
python -m tools.gen_demo_images --num_per_class 2
# 产物：runtime_data/demo/*.jpg
```

## 🧠 模型加载策略

系统启动时按 [lingnan/config.py](lingnan/config.py) 的 `MODEL_CANDIDATES` 顺序自动挑选：

| 优先级 | 文件位置 | 说明 |
| ---: | :--- | :--- |
| 1 | `models/yolov8s_xh_best_int8.onnx` | **推荐**：量化部署版 |
| 2 | `models/yolov8s_xh_best.onnx` | FP32 ONNX |
| 3 | `models/yolov8s_xh_best.pt` | Ultralytics PyTorch |
| 4 | `models/yolov8s.pt` / `models/yolov8n.pt` | COCO 占位（演示用，自动做 12 类映射） |
| 5 | 无任何文件 | **MockSimulator**：随机生成 12 类检测框，便于 UI 联调 |

## 🌾 训练专属模型（4 步流水线）

参见技术规范 §5。本工程提供完整工具链：

```bash
# 1) 准备数据集（参见技术规范 §2）
#    lianjiang_hongcheng_dataset/
#      ├── images/{train,val,test}/*.jpg
#      ├── labels/{train,val,test}/*.txt
#      └── data.yaml

# 2) 训练 yolov8s_xh（P2 小目标 head + 田间专项增强）
python -m tools.train --data lianjiang_hongcheng_dataset/data.yaml --epochs 300

# 3) 导出 ONNX
python -m tools.export_onnx --weights runs/detect/yolov8s_xh/weights/best.pt

# 4) INT8 静态量化（速度 ↑2~3×，体积 ↓4×）
python -m tools.quantize_int8 \
    --input  models/yolov8s_xh_best.onnx \
    --output models/yolov8s_xh_best_int8.onnx \
    --calibration_dir lianjiang_hongcheng_dataset/images/val \
    --num_samples 500

# 部署完成！下次启动应用就会自动加载 INT8 模型
```

## 📊 性能基准

```bash
python -m tools.benchmark --num 100
```

会输出：

- 平均 / P50 / P95 / 最大 / 最小延迟
- 内存增长（需 `psutil`）
- KPI-04（CPU 单图 ≤ 800 ms）/ KPI-10（内存 < 500 MB）自动校验

## 🧪 单元测试

```bash
pip install pytest
pytest

# 或直接跑某一模块
pytest tests/test_severity.py -v
```

覆盖：
- `test_severity` ：12 类 × 严重程度分级（含黄龙病致命标记 / 面积分级）
- `test_knowledge_base` ：60 组合查询 + 化学处方四字段完整性
- `test_log_manager` ：台账 / 档案 CRUD + 校验
- `test_excel_exporter` ：xlsx 文件结构
- `test_settings` ：JSON 持久化 / 默认值 / 损坏文件回退
- `test_inferencer` ：Mock 后端回落
- `test_logging` ：滚动日志

## 📋 使用流程（3 步上手）

1. **第 1 步** 在【👨‍🌾 农户档案】页录入农户/果园（或跳过）
2. **第 2 步** 在【🔍 智能检测】页选物候期 → 导入图片 → 点【▶ 开始检测】
3. **第 3 步** 右侧自动展示带框图、严重程度、三位一体绿色处方

检测日志自动写入 `runtime_data/detection_log.db`，可在【📋 历史台账】页：
- 按时间 / 农户 / 病虫害类别筛选
- 导出 **Excel**（带颜色 + 冻结表头）
- 导出 **PDF 分析报告**（封面 + 统计 + TOP 病害 + 防治建议）

## 📦 打包分发

### Windows 一键打包

```bash
# 1) 安装 pyinstaller
pip install pyinstaller

# 2) （可选）安装 Inno Setup 6 用于生成安装向导
#    下载：https://jrsoftware.org/isdl.php

# 3) 双击 build.bat
build.bat
```

产物：
- `dist/XHGan/XHGan.exe`（绿色版文件夹）
- `dist/XHGan_Setup_x64.exe`（若已安装 Inno Setup）

### 手动打包

```bash
pyinstaller build.spec
```

## ⚙ 个性化设置（保存到 settings.json）

进入【⚙ 设置】Tab，可调：

| 项 | 说明 |
| :--- | :--- |
| 字体倍率 | 80% ~ 160%，适老化 |
| 默认 conf / IoU | 检测默认阈值 |
| 默认物候期 | 启动时自动选 |
| 默认保存目录 | 留空用 `runtime_data/exports` |
| 自动写台账 | 关掉则每次只显示不入库 |
| 提示音 | 重度病害时弹声 |

## 📜 关键文档

| 文档 | 说明 |
| :--- | :--- |
| [docs/技术规范文档.md](docs/技术规范文档.md) | 主规范（九阶段流程） |
| [docs/可行性研究报告.md](docs/可行性研究报告.md) | 立项依据（五维评估） |
| [基于特色创新项目的岭南红橙病虫害智能监测与校本教研一体化平台技术规范文档.md](基于特色创新项目的岭南红橙病虫害智能监测与校本教研一体化平台技术规范文档.md) | 原始蓝本 |

## ⚠ 合规提示

- 知识库中推荐药剂均为国家登记低毒低残留药剂（依据 NY/T 393-2020 与 GB 2763-2021），仅供产业园参考；最终用药须遵循当地农业农村部门最新指导。
- 严守每种药剂的 **安全间隔期（PHI）**，从源头保障岭南红橙国家地理标志产品的药用安全。
- **黄龙病**确诊植株必须立即砍除并就地烧毁，**禁止**化学治疗。

## 📝 许可证

- 代码：本项目内部使用
- Ultralytics YOLOv8：AGPL-3.0（学术 / 公益使用；商业化需购买授权）
- PyQt5：GPL v3（商业化建议替换为 PySide6 LGPL）
- ONNX Runtime / OpenCV / SQLite / reportlab / openpyxl / Pillow：均为宽松开源协议



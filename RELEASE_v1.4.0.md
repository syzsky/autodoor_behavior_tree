# AutoDoor Behavior Tree v1.4.0 — YOLO 训练器

## 版本信息

- **版本**: v1.4.0
- **构建时间**: 2026-05-14
- **新增功能**: YOLO 自动截图训练模块

## 新增模块: modules/yolo_trainer/

YOLO 自动截图训练模块，集成窗口绑定、实时预览、自动截图采集、智能标注、模型训练功能。

### 文件结构

```
modules/yolo_trainer/
├── __init__.py                     # 包入口
├── bt_nodes.py                     # 行为树节点 (YOLOCaptureNode / YOLOTrainNode / YOLOPredictNode / YOLOAutoAnnotateNode)
├── gui_tab.py                      # GUI 标签页 (窗口绑定、实时预览、采集控制、训练面板)
├── capture/
│   ├── __init__.py
│   ├── window_capture.py          # 窗口绑定捕获 (Win32 API / X11 / scrot)
│   └── screen_stream.py           # 实时画面流 (独立线程、帧率控制)
├── training/
│   ├── __init__.py
│   └── trainer.py                 # 训练器核心 (AutoScreenshotCollector / SmartAnnotator / YOLOTrainer)
├── annotation/
│   └── smart_labeler.py           # 智能标注 (预训练模型辅助 + 主动学习)
└── utils/
    ├── __init__.py
    ├── config.py                  # 配置管理 (JSON 保存/加载)
    ├── visualizer.py              # 可视化 (检测结果绘制 / 训练曲线)
    └── dataset_utils.py           # 数据集工具 (划分 / 分析 / COCO&YOLO导出)
```

### 依赖

```
ultralytics>=8.2.0
torch>=2.0.0
torchvision>=0.15.0
```

## 打包方法 (Windows)

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 生成构建信息

```bash
python generate_build_info.py
```

### 3. PyInstaller 打包

```bash
pyinstaller autodoor_bt.spec
```

输出目录: `dist/autodoor-behavior-tree-1.4.0-normal/`

### 4. 便携版打包

将 dist 目录下的文件压缩为 zip:

```bash
cd dist
powershell Compress-Archive -Path "autodoor-behavior-tree-1.4.0-normal/*" -DestinationPath "../autodoor-behavior-tree-v1.4.0-portable.zip"
```

## 使用方法

### 作为行为树节点

```python
from modules.yolo_trainer.bt_nodes import register_yolo_nodes
from bt_core.registry import NodeRegistry

registry = NodeRegistry()
register_yolo_nodes(registry)
```

### 独立使用

```python
from modules.yolo_trainer.training import YOLOTrainer, TrainingConfig

config = TrainingConfig()
config.classes = ["enemy", "item", "npc"]
config.model_size = "n"
config.epochs = 50

trainer = YOLOTrainer(config)
trainer.prepare_dataset()
results = trainer.train()
```

### GUI 集成

```python
from modules.yolo_trainer.gui_tab import YOLOTrainerTab

tab = YOLOTrainerTab(parent_frame, app)
tab.pack(fill="both", expand=True)
```

## 行为树节点说明

| 节点 | 类型 | 功能 |
|------|------|------|
| `YOLOCaptureNode` | Action | 窗口截图采集，参数：window_title, save_dir, max_samples, capture_interval |
| `YOLOTrainNode` | Action | YOLO 模型训练，参数：dataset_path, classes, model_size, epochs |
| `YOLOPredictNode` | Action | 推理检测，参数：model_path, window_title, confidence, target_class |
| `YOLOAutoAnnotateNode` | Action | 自动标注，参数：image_dir, model_path, target_classes, confidence_threshold |

## 更新日志

### v1.4.0 (2026-05-14)

- ✨ 新增 YOLO 自动截图训练模块
- ✨ 窗口绑定实时画面预览
- ✨ 自动截图采集与数据集管理
- ✨ 智能标注（预训练模型辅助）
- ✨ YOLO 模型训练与监控
- ✨ 4 个新行为树节点
- ✨ GUI 训练器标签页

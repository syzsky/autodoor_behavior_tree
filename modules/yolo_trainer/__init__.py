"""
YOLO 自动截图训练模块
=====================
功能：
  1. 窗口绑定实时画面捕获（增强：缩放、平移、画中画、录制）
  2. 自动截图与智能标注
  3. YOLO 模型训练与优化（自动 HPO、迁移学习、模型对比）
  4. 行为树节点集成
  5. 运行时依赖自动安装（exe 启动时自动下载依赖和模型）
"""

__version__ = "1.5.0"
__author__ = "AutoDoor"

# 核心模块
from .capture.window_capture import WindowCapture
from .capture.screen_stream import ScreenStream
from .capture.live_view import LiveView, ViewConfig
from .training.trainer import YOLOTrainer
from .training.smart_train import SmartTrainer, SmartTrainingConfig, ModelComparator, DataQualityAnalyzer
from .annotation.auto_annotator import AutoAnnotator
from .annotation.smart_labeler import SmartLabeler

# 运行时依赖自动安装
from .runtime_setup import RuntimeSetup, quick_setup, ensure_model

__all__ = [
    # 捕获
    "WindowCapture",
    "ScreenStream",
    "LiveView",
    "ViewConfig",
    # 训练
    "YOLOTrainer",
    "SmartTrainer",
    "SmartTrainingConfig",
    "ModelComparator",
    "DataQualityAnalyzer",
    # 标注
    "AutoAnnotator",
    "SmartLabeler",
    # 运行时安装
    "RuntimeSetup",
    "quick_setup",
    "ensure_model",
]

"""
YOLO 自动截图训练模块
=====================
功能：
  1. 窗口绑定实时画面捕获
  2. 自动截图与智能标注
  3. YOLO 模型训练与优化
  4. 行为树节点集成
"""

__version__ = "1.0.0"
__author__ = "AutoDoor"

from .capture.window_capture import WindowCapture
from .capture.screen_stream import ScreenStream
from .training.trainer import YOLOTrainer
from .annotation.auto_annotator import AutoAnnotator
from .annotation.smart_labeler import SmartLabeler

__all__ = [
    "WindowCapture",
    "ScreenStream",
    "YOLOTrainer",
    "AutoAnnotator",
    "SmartLabeler",
]

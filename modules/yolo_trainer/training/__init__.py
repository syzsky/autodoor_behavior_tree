"""训练模块"""
from .trainer import (
    TrainingConfig,
    BoundingBox,
    DatasetManager,
    AutoScreenshotCollector,
    SmartAnnotator,
    YOLOTrainer,
)

__all__ = [
    "TrainingConfig",
    "BoundingBox",
    "DatasetManager",
    "AutoScreenshotCollector",
    "SmartAnnotator",
    "YOLOTrainer",
]

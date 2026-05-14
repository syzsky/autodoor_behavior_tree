"""
配置管理模块
============
支持 JSON/YAML 格式的配置保存与加载
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

from ..training.trainer import TrainingConfig


class ConfigManager:
    """训练配置管理器"""

    def __init__(self, config_dir: str = "./config"):
        self._config_dir = Path(config_dir)
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def save(self, config: TrainingConfig, name: str = "default") -> str:
        """保存配置到 JSON 文件"""
        path = self._config_dir / f"{name}.json"
        
        data = {
            "dataset_name": config.dataset_name,
            "dataset_root": config.dataset_root,
            "train_ratio": config.train_ratio,
            "val_ratio": config.val_ratio,
            "test_ratio": config.test_ratio,
            "capture_interval": config.capture_interval,
            "max_samples": config.max_samples,
            "image_size": list(config.image_size),
            "augmentation": config.augmentation,
            "flip_horizontal": config.flip_horizontal,
            "flip_vertical": config.flip_vertical,
            "rotation_range": config.rotation_range,
            "brightness_range": config.brightness_range,
            "contrast_range": config.contrast_range,
            "noise_level": config.noise_level,
            "model_size": config.model_size,
            "epochs": config.epochs,
            "batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
            "patience": config.patience,
            "use_pretrained": config.use_pretrained,
            "confidence_threshold": config.confidence_threshold,
            "iou_threshold": config.iou_threshold,
            "classes": config.classes,
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(path)

    def load(self, name: str = "default") -> Optional[TrainingConfig]:
        """从 JSON 文件加载配置"""
        path = self._config_dir / f"{name}.json"
        if not path.exists():
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        config = TrainingConfig()
        for key, value in data.items():
            if hasattr(config, key):
                if key == "image_size":
                    setattr(config, key, tuple(value))
                else:
                    setattr(config, key, value)
        
        return config

    def list_configs(self) -> list:
        """列出所有保存的配置"""
        configs = []
        for p in self._config_dir.glob("*.json"):
            configs.append(p.stem)
        return configs

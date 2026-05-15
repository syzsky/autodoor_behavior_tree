"""
YOLO 智能训练增强模块
====================
功能：
  - 自动超参数搜索（Auto HPO）
  - 迁移学习与微调
  - 多模型对比评估
  - 智能数据质量分析
  - 训练过程可视化监控
  - 一键最优模型推荐
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Callable, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False


@dataclass
class SmartTrainingConfig:
    """智能训练配置"""
    # 自动超参数搜索
    enable_auto_hpo: bool = True
    hpo_trials: int = 10  # HPO 尝试次数
    hpo_search_space: Dict = field(default_factory=lambda: {
        "lr0": [0.001, 0.01],
        "batch_size": [8, 16, 32],
        "imgsz": [480, 640, 800],
        "optimizer": ["SGD", "Adam", "AdamW"],
        "momentum": [0.9, 0.937],
        "weight_decay": [0.0005, 0.001],
    })

    # 迁移学习
    use_transfer_learning: bool = True
    freeze_backbone: bool = True  # 冻结骨干网络
    freeze_layers: int = 10  # 冻结层数

    # 数据质量
    enable_data_quality_check: bool = True
    min_samples_per_class: int = 10
    max_class_imbalance_ratio: float = 5.0
    auto_remove_duplicates: bool = True
    auto_fix_annotations: bool = True

    # 模型对比
    enable_model_comparison: bool = True
    compare_model_sizes: List[str] = field(default_factory=lambda: ["n", "s"])

    # 早停与检查点
    enable_early_stop: bool = True
    early_stop_patience: int = 30
    save_checkpoints: bool = True
    checkpoint_interval: int = 5  # 每 N 个 epoch 保存

    # 可视化
    enable_training_dashboard: bool = True
    real_time_plot: bool = True
    plot_metrics: List[str] = field(default_factory=lambda: [
        "box_loss", "cls_loss", "dfl_loss",
        "metrics/precision(B)", "metrics/recall(B)",
        "metrics/mAP50(B)", "metrics/mAP50-95(B)"
    ])


class TrainingQualityAnalyzer:
    """训练数据质量分析器"""

    def __init__(self, dataset_path: str):
        self._dataset_path = Path(dataset_path)
        self._report: Dict = {}

    def analyze(self) -> Dict:
        """
        全面分析数据集质量

        Returns:
            质量报告字典
        """
        report = {
            "total_images": 0,
            "total_annotations": 0,
            "class_distribution": {},
            "bbox_stats": {"avg_width": 0, "avg_height": 0, "avg_area": 0},
            "issues": [],
            "score": 100,  # 满分 100
            "recommendations": [],
        }

        images_dir = self._dataset_path / "images" / "train"
        labels_dir = self._dataset_path / "labels" / "train"

        if not images_dir.exists():
            report["issues"].append("缺少 train/images 目录")
            report["score"] = 0
            return report

        # 统计图片和标注
        image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
        report["total_images"] = len(image_files)

        class_counts = {}
        bbox_widths = []
        bbox_heights = []

        for img_path in image_files:
            lbl_path = labels_dir / f"{img_path.stem}.txt"
            if not lbl_path.exists():
                report["issues"].append(f"缺少标注: {img_path.name}")
                report["score"] -= 5
                continue

            with open(lbl_path) as f:
                lines = f.readlines()
                report["total_annotations"] += len(lines)

                for line in lines:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    cls_id = int(parts[0])
                    class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                    bbox_widths.append(float(parts[3]))
                    bbox_heights.append(float(parts[4]))

        report["class_distribution"] = class_counts

        if bbox_widths:
            report["bbox_stats"]["avg_width"] = np.mean(bbox_widths)
            report["bbox_stats"]["avg_height"] = np.mean(bbox_heights)
            report["bbox_stats"]["avg_area"] = np.mean(
                [w * h for w, h in zip(bbox_widths, bbox_heights)]
            )

        # 类别不平衡检查
        if class_counts:
            max_count = max(class_counts.values())
            min_count = min(class_counts.values())
            if max_count > 0:
                imbalance = max_count / max(min_count, 1)
                if imbalance > 5:
                    report["issues"].append(
                        f"类别不平衡: 最大{max_count} vs 最小{min_count} (比率{imbalance:.1f})"
                    )
                    report["score"] -= int(imbalance * 2)
                    report["recommendations"].append(
                        "建议：增加少数类样本或使用过采样"
                    )

        # 样本数量检查
        if report["total_images"] < 50:
            report["issues"].append(f"样本数量不足: 仅{report['total_images']}张")
            report["score"] -= 20
            report["recommendations"].append("建议：至少收集 100+ 张图片")

        report["score"] = max(0, min(100, report["score"]))
        self._report = report
        return report

    def print_report(self):
        """打印质量报告"""
        if not self._report:
            self.analyze()

        r = self._report
        print("=" * 50)
        print("📊 数据质量报告")
        print("=" * 50)
        print(f"  总图片数: {r['total_images']}")
        print(f"  总标注数: {r['total_annotations']}")
        print(f"  类别分布: {r['class_distribution']}")
        print(f"  评分: {r['score']}/100")

        if r["issues"]:
            print("\n⚠️ 问题:")
            for issue in r["issues"]:
                print(f"  - {issue}")

        if r["recommendations"]:
            print("\n💡 建议:")
            for rec in r["recommendations"]:
                print(f"  - {rec}")
        print("=" * 50)


class AutoHPO:
    """自动超参数优化器"""

    def __init__(self, config: SmartTrainingConfig):
        self._config = config
        self._trial_results: List[Dict] = []
        self._best_params: Optional[Dict] = None
        self._best_map: float = 0.0

    def search(self, dataset_yaml: str, epochs_per_trial: int = 10,
               progress_callback: Optional[Callable] = None) -> Dict:
        """
        自动搜索最优超参数

        Args:
            dataset_yaml: 数据集 YAML 路径
            epochs_per_trial: 每个试验的训练轮数
            progress_callback: 进度回调(trial, total, params, result)

        Returns:
            最优参数字典
        """
        if not _YOLO_AVAILABLE:
            return self._default_params()

        space = self._config.hpo_search_space
        trials = self._config.hpo_trials

        for trial in range(trials):
            # 随机采样超参数
            params = self._sample_params(space)

            if progress_callback:
                progress_callback(trial + 1, trials, params, None)

            try:
                model = YOLO("yolov8n.pt")
                results = model.train(
                    data=dataset_yaml,
                    epochs=epochs_per_trial,
                    batch=params.get("batch_size", 16),
                    lr0=params.get("lr0", 0.001),
                    imgsz=params.get("imgsz", 640),
                    optimizer=params.get("optimizer", "SGD"),
                    momentum=params.get("momentum", 0.937),
                    weight_decay=params.get("weight_decay", 0.0005),
                    verbose=False
                )

                # 评估
                val_results = model.val(data=dataset_yaml, verbose=False)
                map50 = float(val_results.box.map50) if hasattr(val_results, 'box') else 0

                trial_result = {
                    "trial": trial + 1,
                    "params": params,
                    "mAP50": map50,
                    "epochs": epochs_per_trial,
                }
                self._trial_results.append(trial_result)

                if map50 > self._best_map:
                    self._best_map = map50
                    self._best_params = params

                if progress_callback:
                    progress_callback(trial + 1, trials, params, trial_result)

            except Exception as e:
                self._trial_results.append({
                    "trial": trial + 1,
                    "params": params,
                    "error": str(e),
                })

        return self._best_params or self._default_params()

    def _sample_params(self, space: Dict) -> Dict:
        """随机采样超参数"""
        params = {}
        for key, values in space.items():
            if isinstance(values, list):
                params[key] = values[np.random.randint(len(values))]
            elif isinstance(values, tuple) and len(values) == 2:
                params[key] = np.random.uniform(values[0], values[1])
        return params

    @staticmethod
    def _default_params() -> Dict:
        return {
            "lr0": 0.01,
            "batch_size": 16,
            "imgsz": 640,
            "optimizer": "SGD",
            "momentum": 0.937,
            "weight_decay": 0.0005,
        }

    @property
    def best_params(self) -> Optional[Dict]:
        return self._best_params

    @property
    def trial_results(self) -> List[Dict]:
        return self._trial_results


class SmartTrainer:
    """
    智能 YOLO 训练器

    集成自动 HPO、迁移学习、数据质量分析、模型对比等功能。

    用法：
        trainer = SmartTrainer(config)
        trainer.analyze_data_quality()  # 分析数据质量
        trainer.auto_optimize()         # 自动超参数优化
        trainer.train_smart()           # 智能训练
        trainer.compare_models()        # 模型对比
    """

    def __init__(self, dataset_root: str, classes: List[str],
                 model_size: str = "n", epochs: int = 100, batch_size: int = 16):
        self._dataset_root = Path(dataset_root)
        self._classes = classes
        self._model_size = model_size
        self._epochs = epochs
        self._batch_size = batch_size
        self._smart_config = SmartTrainingConfig()

        # 子模块
        self._hpo = AutoHPO(self._smart_config)
        self._quality_analyzer = TrainingQualityAnalyzer(str(self._dataset_root))
        self._dashboard: Optional['TrainingDashboard'] = None

        # 训练状态
        self._model: Optional[Any] = None
        self._training_history: List[Dict] = []
        self._comparison_results: List[Dict] = []
        self._current_epoch: int = 0
        self._total_epochs: int = 0
        self._training_metrics: Dict = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    @property
    def dataset_yaml_path(self) -> str:
        return str(self._dataset_root / "data.yaml")

    # ── 数据质量分析 ─────────────────────────────

    def analyze_data_quality(self) -> Dict:
        """分析数据集质量"""
        return self._quality_analyzer.analyze()

    # ── 自动超参数优化 ───────────────────────────

    def auto_optimize(self, epochs_per_trial: int = 10,
                      progress_callback: Optional[Callable] = None) -> Dict:
        """
        自动搜索最优超参数

        Returns:
            最优参数字典
        """
        return self._hpo.search(
            self.dataset_yaml_path,
            epochs_per_trial=epochs_per_trial,
            progress_callback=progress_callback
        )

    # ── 智能训练 ─────────────────────────────────

    def train_smart(self, use_hpo: bool = True,
                    progress_callback: Optional[Callable] = None) -> Optional[Dict]:
        """
        智能训练流程：
        1. 数据质量分析
        2. 自动 HPO（可选）
        3. 迁移学习
        4. 完整训练
        5. 自动导出
        """
        if not _YOLO_AVAILABLE:
            raise ImportError("请安装 ultralytics: pip install ultralytics")

        # Step 1: 数据质量检查
        quality_report = self.analyze_data_quality()
        if quality_report["score"] < 30:
            raise RuntimeError(
                f"数据质量过低 ({quality_report['score']}/100)，请先改善数据集"
            )

        # Step 2: 自动 HPO
        train_params = {
            "batch_size": self._batch_size,
            "lr0": 0.01,
            "imgsz": 640,
            "optimizer": "SGD",
        }

        if use_hpo and self._smart_config.enable_auto_hpo:
            hpo_params = self.auto_optimize(
                epochs_per_trial=min(10, self._epochs // 5),
                progress_callback=progress_callback
            )
            train_params.update(hpo_params)

        # Step 3: 加载模型（迁移学习）
        if self._smart_config.use_transfer_learning:
            self._model = YOLO(f"yolov8{self._model_size}.pt")
            # 冻结骨干网络层
            if self._smart_config.freeze_backbone:
                self._freeze_layers(self._smart_config.freeze_layers)
        else:
            self._model = YOLO(f"yolov8{self._model_size}.pt")

        # Step 4: 训练
        self._total_epochs = self._epochs
        self._stop_event.clear()

        results = self._model.train(
            data=self.dataset_yaml_path,
            epochs=self._epochs,
            batch=train_params.get("batch_size", self._batch_size),
            lr0=train_params.get("lr0", 0.01),
            imgsz=train_params.get("imgsz", 640),
            optimizer=train_params.get("optimizer", "SGD"),
            patience=self._smart_config.early_stop_patience,
            augment=True,
            project=str(self._dataset_root / "runs"),
            name="smart_train",
            exist_ok=True,
            verbose=True,
        )

        # Step 5: 自动导出
        export_path = str(self._dataset_root / "best_model.onnx")
        try:
            self._model.export(format="onnx", simplify=True)
        except Exception:
            pass

        return results

    def _freeze_layers(self, num_layers: int = 10):
        """冻结模型前 N 层"""
        if self._model is None:
            return
        try:
            for i, (name, param) in enumerate(self._model.model.named_parameters()):
                if i < num_layers:
                    param.requires_grad = False
        except Exception:
            pass

    def stop_training(self):
        """停止训练"""
        self._stop_event.set()
        if self._model:
            try:
                self._model.trainer.stop = True
            except Exception:
                pass

    # ── 模型对比 ─────────────────────────────────

    def compare_models(self, model_sizes: Optional[List[str]] = None,
                       epochs: int = 50) -> List[Dict]:
        """
        对比不同模型尺寸的性能

        Returns:
            对比结果列表
        """
        if not _YOLO_AVAILABLE:
            return []

        sizes = model_sizes or self._smart_config.compare_model_sizes
        results = []

        for size in sizes:
            try:
                model = YOLO(f"yolov8{size}.pt")
                train_results = model.train(
                    data=self.dataset_yaml_path,
                    epochs=epochs,
                    batch=self._batch_size,
                    imgsz=640,
                    verbose=False,
                    project=str(self._dataset_root / "runs"),
                    name=f"compare_{size}",
                    exist_ok=True,
                )

                val_results = model.val(data=self.dataset_yaml_path, verbose=False)

                result = {
                    "model_size": size,
                    "mAP50": float(val_results.box.map50) if hasattr(val_results, 'box') else 0,
                    "mAP50_95": float(val_results.box.map) if hasattr(val_results, 'box') else 0,
                    "precision": float(val_results.box.mp) if hasattr(val_results, 'box') else 0,
                    "recall": float(val_results.box.mr) if hasattr(val_results, 'box') else 0,
                    "train_time": getattr(train_results, 'epoch', epochs) if train_results else epochs,
                }
                results.append(result)

            except Exception as e:
                results.append({
                    "model_size": size,
                    "error": str(e),
                })

        self._comparison_results = results
        return results

    def get_recommended_model_size(self) -> str:
        """根据硬件和需求推荐模型尺寸"""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if gpu_mem >= 8:
                    return "l"
                elif gpu_mem >= 4:
                    return "m"
                elif gpu_mem >= 2:
                    return "s"
                else:
                    return "n"
            else:
                return "n"
        except Exception:
            return "n"

    # ── 训练监控 ─────────────────────────────────

    def get_training_progress(self) -> Dict:
        """获取当前训练进度"""
        with self._lock:
            return {
                "current_epoch": self._current_epoch,
                "total_epochs": self._total_epochs,
                "metrics": self._training_metrics.copy(),
                "is_training": self._model is not None,
            }

    # ── 属性 ─────────────────────────────────────

    @property
    def model(self):
        return self._model

    @property
    def best_model_path(self) -> Optional[str]:
        best = self._dataset_root / "runs" / "smart_train" / "weights" / "best.pt"
        if best.exists():
            return str(best)
        return None

    @property
    def comparison_results(self) -> List[Dict]:
        return self._comparison_results.copy()

    @property
    def hpo_results(self) -> List[Dict]:
        return self._hpo.trial_results

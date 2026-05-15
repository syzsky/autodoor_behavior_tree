"""
智能标注模块
============
功能：
  - 半自动标注（预训练模型 + 人工修正）
  - 主动学习（选择最有价值的样本标注）
  - 标注质量检查
  - 标注进度追踪
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

import cv2
import numpy as np

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False


@dataclass
class AnnotationStats:
    """标注统计"""
    total_images: int = 0
    annotated_images: int = 0
    total_boxes: int = 0
    class_distribution: Dict[int, int] = field(default_factory=dict)
    avg_boxes_per_image: float = 0.0
    annotation_time_seconds: float = 0.0
    
    @property
    def progress(self) -> float:
        if self.total_images == 0:
            return 0.0
        return self.annotated_images / self.total_images * 100

    def to_dict(self) -> dict:
        return {
            "total_images": self.total_images,
            "annotated_images": self.annotated_images,
            "total_boxes": self.total_boxes,
            "class_distribution": self.class_distribution,
            "avg_boxes_per_image": self.avg_boxes_per_image,
            "progress": f"{self.progress:.1f}%",
            "annotation_time": f"{self.annotation_time_seconds:.1f}s"
        }


class AnnotationQualityChecker:
    """标注质量检查器"""

    @staticmethod
    def check_dataset(image_dir: str, label_dir: str,
                      classes: List[str]) -> Dict[str, List[str]]:
        """
        检查数据集标注质量
        
        Returns:
            {问题类型: [问题描述]}
        """
        issues = {
            "missing_labels": [],
            "empty_labels": [],
            "invalid_boxes": [],
            "class_mismatch": [],
            "duplicate_boxes": [],
            "small_objects": [],
        }
        
        image_dir = Path(image_dir)
        label_dir = Path(label_dir)
        
        for img_path in image_dir.iterdir():
            if img_path.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp'}:
                continue
            
            lbl_path = label_dir / f"{img_path.stem}.txt"
            
            # 检查标注文件是否存在
            if not lbl_path.exists():
                issues["missing_labels"].append(str(img_path))
                continue
            
            # 读取标注
            with open(lbl_path, 'r') as f:
                lines = f.readlines()
            
            if not lines:
                issues["empty_labels"].append(str(img_path))
                continue
            
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            img_h, img_w = img.shape[:2]
            
            boxes = []
            for line in lines:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                
                cls_id = int(parts[0])
                xc, yc, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                
                # 检查类别 ID 是否有效
                if cls_id < 0 or cls_id >= len(classes):
                    issues["class_mismatch"].append(
                        f"{img_path.name}: 无效类别 {cls_id}")
                
                # 检查边界框是否有效
                if w <= 0 or h <= 0 or xc < 0 or xc > 1 or yc < 0 or yc > 1:
                    issues["invalid_boxes"].append(
                        f"{img_path.name}: 无效框 {xc:.3f} {yc:.3f} {w:.3f} {h:.3f}")
                
                # 检查过小目标
                if w * img_w < 5 or h * img_h < 5:
                    issues["small_objects"].append(
                        f"{img_path.name}: 极小目标 {w*img_w:.0f}x{h*img_h:.0f}px")
                
                boxes.append((cls_id, xc, yc, w, h))
            
            # 检查重复框
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    _, xc1, yc1, w1, h1 = boxes[i]
                    _, xc2, yc2, w2, h2 = boxes[j]
                    iou = AnnotationQualityChecker._compute_iou(
                        (xc1, yc1, w1, h1), (xc2, yc2, w2, h2))
                    if iou > 0.9:
                        issues["duplicate_boxes"].append(
                            f"{img_path.name}: 重复框 #{i} 和 #{j} (IoU={iou:.2f})")
        
        return issues

    @staticmethod
    def _compute_iou(box1: Tuple[float, float, float, float],
                      box2: Tuple[float, float, float, float]) -> float:
        """计算两个归一化框的 IoU"""
        xc1, yc1, w1, h1 = box1
        xc2, yc2, w2, h2 = box2
        
        x1_min, x1_max = xc1 - w1/2, xc1 + w1/2
        y1_min, y1_max = yc1 - h1/2, yc1 + h1/2
        x2_min, x2_max = xc2 - w2/2, xc2 + w2/2
        y2_min, y2_max = yc2 - h2/2, yc2 + h2/2
        
        inter_x = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
        inter_y = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
        inter = inter_x * inter_y
        
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - inter
        
        return inter / union if union > 0 else 0


class ActiveLearningSelector:
    """
    主动学习样本选择器
    
    选择最有价值的未标注样本进行标注，
    减少标注工作量同时最大化模型提升。
    """

    def __init__(self, model=None, strategy: str = "uncertainty"):
        """
        Args:
            model: YOLO 模型
            strategy: 选择策略
                - "uncertainty": 不确定性最高（置信度接近阈值的样本）
                - "diversity": 多样性最大（特征空间覆盖最广）
                - "random": 随机选择
        """
        self._model = model
        self._strategy = strategy
        self._features: List[np.ndarray] = []
        self._image_paths: List[str] = []

    def set_model(self, model):
        """设置模型"""
        self._model = model

    def select_samples(self, unlabeled_images: List[str],
                       n_samples: int = 50) -> List[str]:
        """
        选择最有价值的样本
        
        Args:
            unlabeled_images: 未标注图片路径列表
            n_samples: 选择数量
            
        Returns:
            选中的图片路径列表
        """
        if self._strategy == "random":
            return self._select_random(unlabeled_images, n_samples)
        elif self._strategy == "uncertainty":
            return self._select_uncertainty(unlabeled_images, n_samples)
        elif self._strategy == "diversity":
            return self._select_diversity(unlabeled_images, n_samples)
        else:
            return self._select_random(unlabeled_images, n_samples)

    def _select_random(self, images: List[str], n: int) -> List[str]:
        """随机选择"""
        if len(images) <= n:
            return images
        import random
        return random.sample(images, n)

    def _select_uncertainty(self, images: List[str], n: int) -> List[str]:
        """
        不确定性选择：
        选择模型预测置信度最接近阈值的样本
        （这些样本对模型来说最"困惑"）
        """
        if not _YOLO_AVAILABLE or self._model is None:
            return self._select_random(images, n)
        
        uncertainties = []
        
        for img_path in images:
            img = cv2.imread(img_path)
            if img is None:
                continue
            
            results = self._model(img, verbose=False)
            if results and results[0].boxes is not None:
                confs = results[0].boxes.conf.cpu().numpy()
                if len(confs) > 0:
                    # 计算不确定性：置信度越接近 0.5 越不确定
                    uncertainty = np.mean(np.abs(confs - 0.5))
                    uncertainties.append((img_path, uncertainty))
                else:
                    uncertainties.append((img_path, 1.0))  # 无检测 = 高不确定性
            else:
                uncertainties.append((img_path, 1.0))
        
        # 按不确定性排序，选最高的
        uncertainties.sort(key=lambda x: x[1], reverse=True)
        return [path for path, _ in uncertainties[:n]]

    def _select_diversity(self, images: List[str], n: int) -> List[str]:
        """
        多样性选择：
        使用图像特征选择覆盖最广的样本
        """
        import random
        
        if len(images) <= n:
            return images
        
        # 提取缩略图特征
        features = []
        valid_paths = []
        
        for img_path in images:
            img = cv2.imread(img_path)
            if img is None:
                continue
            # 缩放到固定大小并展平作为简单特征
            thumb = cv2.resize(img, (64, 64))
            feat = thumb.flatten().astype(np.float32) / 255.0
            features.append(feat)
            valid_paths.append(img_path)
        
        if len(features) <= n:
            return valid_paths
        
        # K-means 中心点选择
        features_arr = np.array(features)
        
        # 简化版：随机初始化中心，迭代选择最远点
        selected_indices = [random.randint(0, len(features) - 1)]
        
        for _ in range(n - 1):
            # 计算每个点到已选中心的距离
            dists = np.full(len(features), float('inf'))
            for sel_idx in selected_indices:
                diff = features_arr - features_arr[sel_idx]
                dist = np.sum(diff ** 2, axis=1)
                dists = np.minimum(dists, dist)
            
            # 选距离最远的点
            next_idx = int(np.argmax(dists))
            selected_indices.append(next_idx)
        
        return [valid_paths[i] for i in selected_indices]


class AnnotationPipeline:
    """
    标注流水线
    
    整合自动标注、质量检查、主动学习的完整标注流程。
    
    用法：
        pipeline = AnnotationPipeline(config)
        pipeline.setup("./raw_images")
        pipeline.auto_annotate_all()
        pipeline.check_quality()
        pipeline.select_next_batch(n=50)
    """

    def __init__(self, config):
        self._config = config
        self._annotator = SmartAnnotator(config)
        self._quality_checker = AnnotationQualityChecker()
        self._active_learner = ActiveLearningSelector()
        self._stats = AnnotationStats()
        self._raw_dir: Optional[Path] = None
        self._labeled_dir: Optional[Path] = None
        self._start_time = time.time()

    def setup(self, raw_images_dir: str, output_dir: Optional[str] = None):
        """
        设置标注流水线
        
        Args:
            raw_images_dir: 原始图片目录
            output_dir: 输出目录（默认使用 config.dataset_path）
        """
        self._raw_dir = Path(raw_images_dir)
        
        if output_dir:
            self._labeled_dir = Path(output_dir)
        else:
            self._labeled_dir = self._config.dataset_path
        
        # 统计
        images = list(self._raw_dir.glob("*.jpg")) + list(self._raw_dir.glob("*.png"))
        self._stats.total_images = len(images)

    def auto_annotate_all(self, target_classes: Optional[List[str]] = None) -> Dict[str, int]:
        """
        自动标注所有图片
        
        Returns:
            标注统计
        """
        if self._raw_dir is None:
            raise RuntimeError("请先调用 setup()")
        
        self._annotator.load_pretrained_model()
        
        image_dir = str(self._raw_dir)
        label_dir = str(self._labeled_dir / "labels" / "train")
        
        stats = self._annotator.batch_annotate(image_dir, label_dir, target_classes)
        
        # 更新统计
        self._stats.annotated_images = len(stats)
        self._stats.total_boxes = sum(stats.values())
        if self._stats.annotated_images > 0:
            self._stats.avg_boxes_per_image = self._stats.total_boxes / self._stats.annotated_images
        self._stats.annotation_time_seconds = time.time() - self._start_time
        
        return stats

    def check_quality(self) -> Dict[str, List[str]]:
        """检查标注质量"""
        image_dir = str(self._raw_dir)
        label_dir = str(self._labeled_dir / "labels" / "train")
        return self._quality_checker.check_dataset(
            image_dir, label_dir, self._config.classes)

    def select_next_batch(self, n: int = 50) -> List[str]:
        """选择下一批需要标注的样本"""
        raw_images = [str(p) for p in self._raw_dir.glob("*.jpg")]
        raw_images += [str(p) for p in self._raw_dir.glob("*.png")]
        
        # 过滤已标注的
        labeled = set()
        label_dir = self._labeled_dir / "labels" / "train"
        if label_dir.exists():
            for lbl in label_dir.glob("*.txt"):
                labeled.add(lbl.stem)
        
        unlabeled = [p for p in raw_images if Path(p).stem not in labeled]
        
        return self._active_learner.select_samples(unlabeled, n)

    @property
    def stats(self) -> AnnotationStats:
        return self._stats

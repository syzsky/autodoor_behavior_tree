"""
YOLO 自动截图训练模块
=====================
功能：
  - 自动截图采集
  - 智能标注（基于预训练模型辅助标注）
  - 数据集管理
  - YOLO 模型训练
  - 训练监控与可视化
"""

import os
import json
import time
import shutil
import random
import threading
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field, asdict

import cv2
import numpy as np

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False


@dataclass
class TrainingConfig:
    """训练配置"""
    # 数据集
    dataset_name: str = "yolo_dataset"
    dataset_root: str = "./data/yolo_datasets"
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    test_ratio: float = 0.1
    
    # 截图采集
    capture_interval: float = 0.5  # 截图间隔（秒）
    max_samples: int = 1000  # 最大样本数
    image_size: Tuple[int, int] = (640, 640)  # 输入尺寸
    
    # 数据增强
    augmentation: bool = True
    flip_horizontal: bool = True
    flip_vertical: bool = False
    rotation_range: float = 10.0
    brightness_range: float = 0.2
    contrast_range: float = 0.2
    noise_level: int = 10
    
    # 训练参数
    model_size: str = "n"  # n, s, m, l, x
    epochs: int = 100
    batch_size: int = 16
    learning_rate: float = 0.001
    patience: int = 20  # 早停耐心值
    
    # 智能标注
    use_pretrained: bool = True  # 使用预训练模型辅助标注
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.45
    
    # 类别
    classes: List[str] = field(default_factory=lambda: [])
    
    @property
    def dataset_path(self) -> Path:
        return Path(self.dataset_root) / self.dataset_name
    
    @property
    def images_dir(self) -> Path:
        return self.dataset_path / "images"
    
    @property
    def labels_dir(self) -> Path:
        return self.dataset_path / "labels"


@dataclass
class BoundingBox:
    """边界框"""
    class_id: int
    x_center: float  # 归一化中心 x
    y_center: float  # 归一化中心 y
    width: float     # 归一化宽度
    height: float    # 归一化高度
    confidence: float = 1.0
    
    def to_yolo_line(self) -> str:
        return f"{self.class_id} {self.x_center:.6f} {self.y_center:.6f} {self.width:.6f} {self.height:.6f}"
    
    @staticmethod
    def from_yolo_line(line: str) -> 'BoundingBox':
        parts = line.strip().split()
        return BoundingBox(
            class_id=int(parts[0]),
            x_center=float(parts[1]),
            y_center=float(parts[2]),
            width=float(parts[3]),
            height=float(parts[4])
        )
    
    def to_pixels(self, img_w: int, img_h: int) -> Tuple[int, int, int, int]:
        """转换为像素坐标 (x1, y1, x2, y2)"""
        x1 = int((self.x_center - self.width / 2) * img_w)
        y1 = int((self.y_center - self.height / 2) * img_h)
        x2 = int((self.x_center + self.width / 2) * img_w)
        y2 = int((self.y_center + self.height / 2) * img_h)
        return x1, y1, x2, y2


class AutoScreenshotCollector:
    """
    自动截图采集器
    
    用法：
        collector = AutoScreenshotCollector(capture, config)
        collector.start()
        # ... 等待采集 ...
        collector.stop()
        print(f"采集了 {collector.count} 张图片")
    """

    def __init__(self, capture, config: TrainingConfig):
        self._capture = capture
        self._config = config
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._count = 0
        self._lock = threading.Lock()
        self._save_dir: Optional[Path] = None
        
    @property
    def count(self) -> int:
        return self._count

    def setup_directory(self, split: str = "train") -> Path:
        """创建保存目录"""
        save_dir = self._config.images_dir / split
        save_dir.mkdir(parents=True, exist_ok=True)
        self._save_dir = save_dir
        return save_dir

    def start(self, split: str = "train"):
        """开始自动截图"""
        if self._running:
            return
        self.setup_directory(split)
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止截图"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    def capture_single(self, save_path: Optional[str] = None,
                       prefix: str = "img") -> Optional[str]:
        """
        截取单张图片
        
        Returns:
            保存路径，失败返回 None
        """
        frame = self._capture.capture()
        if frame is None:
            return None

        if save_path is None:
            if self._save_dir is None:
                self.setup_directory()
            timestamp = int(time.time() * 1000)
            filename = f"{prefix}_{timestamp}_{self._count:06d}.jpg"
            save_path = str(self._save_dir / filename)

        cv2.imwrite(save_path, frame)
        with self._lock:
            self._count += 1
        return save_path

    def _capture_loop(self):
        """截图循环"""
        while self._running and self._count < self._config.max_samples:
            self.capture_single()
            time.sleep(self._config.capture_interval)


class SmartAnnotator:
    """
    智能标注器
    
    使用预训练 YOLO 模型辅助自动标注，
    支持人工修正和半自动标注流程。
    """

    def __init__(self, config: TrainingConfig):
        self._config = config
        self._model: Optional[any] = None
        self._pretrained_model: Optional[any] = None
        
    def load_pretrained_model(self, model_path: Optional[str] = None):
        """加载预训练模型用于辅助标注"""
        if not _YOLO_AVAILABLE:
            return
        
        if model_path and os.path.exists(model_path):
            self._pretrained_model = YOLO(model_path)
        elif self._config.use_pretrained:
            # 使用 YOLOv8 预训练模型
            size = self._config.model_size
            self._pretrained_model = YOLO(f"yolov8{size}.pt")

    def auto_annotate(self, image_path: str,
                      target_classes: Optional[List[str]] = None) -> List[BoundingBox]:
        """
        自动标注单张图片
        
        Args:
            image_path: 图片路径
            target_classes: 目标类别列表（None 则标注所有检测到的）
            
        Returns:
            检测到的边界框列表
        """
        if not self._pretrained_model:
            return []
        
        results = self._pretrained_model(image_path, verbose=False)
        boxes = []
        
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                cls_name = result.names[cls_id]
                
                # 过滤目标类别
                if target_classes and cls_name not in target_classes:
                    continue
                
                conf = float(box.conf[0])
                if conf < self._config.confidence_threshold:
                    continue
                
                # 转换为归一化坐标
                img_h, img_w = result.orig_shape
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x_center = ((x1 + x2) / 2) / img_w
                y_center = ((y1 + y2) / 2) / img_h
                width = (x2 - x1) / img_w
                height = (y2 - y1) / img_h
                
                # 映射到自定义类别
                if target_classes:
                    mapped_cls = target_classes.index(cls_name) if cls_name in target_classes else cls_id
                else:
                    mapped_cls = cls_id
                
                boxes.append(BoundingBox(
                    class_id=mapped_cls,
                    x_center=x_center,
                    y_center=y_center,
                    width=width,
                    height=height,
                    confidence=conf
                ))
        
        return boxes

    def batch_annotate(self, image_dir: str, label_dir: str,
                       target_classes: Optional[List[str]] = None) -> Dict[str, int]:
        """
        批量自动标注
        
        Returns:
            {图片路径: 标注数量} 的字典
        """
        image_dir = Path(image_dir)
        label_dir = Path(label_dir)
        label_dir.mkdir(parents=True, exist_ok=True)
        
        stats = {}
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        
        for img_path in image_dir.iterdir():
            if img_path.suffix.lower() not in image_extensions:
                continue
            
            boxes = self.auto_annotate(str(img_path), target_classes)
            
            # 保存标注文件
            label_path = label_dir / f"{img_path.stem}.txt"
            with open(label_path, 'w') as f:
                for box in boxes:
                    f.write(box.to_yolo_line() + '\n')
            
            stats[str(img_path)] = len(boxes)
        
        return stats

    def save_annotations(self, image_path: str, boxes: List[BoundingBox]):
        """保存标注到文件"""
        p = Path(image_path)
        label_path = self._config.labels_dir / p.parent.name / f"{p.stem}.txt"
        label_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(label_path, 'w') as f:
            for box in boxes:
                f.write(box.to_yolo_line() + '\n')


class DataAugmentor:
    """数据增强器"""

    @staticmethod
    def augment(image: np.ndarray, config: TrainingConfig) -> List[Tuple[np.ndarray, str]]:
        """
        对图片进行数据增强
        
        Returns:
            [(增强后的图片, 后缀名), ...]
        """
        augmented = []
        
        if config.flip_horizontal:
            augmented.append((cv2.flip(image, 1), "_flip_h"))
        
        if config.flip_vertical:
            augmented.append((cv2.flip(image, 0), "_flip_v"))
        
        if config.rotation_range > 0:
            angle = random.uniform(-config.rotation_range, config.rotation_range)
            h, w = image.shape[:2]
            M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
            rotated = cv2.warpAffine(image, M, (w, h))
            augmented.append((rotated, f"_rot{angle:.0f}"))
        
        if config.brightness_range > 0:
            factor = 1.0 + random.uniform(-config.brightness_range, config.brightness_range)
            bright = np.clip(image * factor, 0, 255).astype(np.uint8)
            augmented.append((bright, "_bright"))
        
        if config.contrast_range > 0:
            factor = 1.0 + random.uniform(-config.contrast_range, config.contrast_range)
            mean = image.mean()
            contrast = np.clip((image - mean) * factor + mean, 0, 255).astype(np.uint8)
            augmented.append((contrast, "_contrast"))
        
        if config.noise_level > 0:
            noise = np.random.randint(0, config.noise_level, image.shape, dtype=np.uint8)
            noisy = cv2.add(image, noise)
            augmented.append((noisy, "_noise"))
        
        return augmented


class YOLOTrainer:
    """
    YOLO 训练器
    
    用法：
        trainer = YOLOTrainer(config)
        trainer.prepare_dataset()
        trainer.train()
        trainer.export(format="onnx")
    """

    def __init__(self, config: TrainingConfig):
        self._config = config
        self._model: Optional[any] = None
        self._results: Optional[Dict] = None
        self._is_training = False
        self._progress_callback = None
        
    @property
    def is_training(self) -> bool:
        return self._is_training

    @property
    def results(self) -> Optional[Dict]:
        return self._results

    def set_progress_callback(self, callback):
        """设置训练进度回调"""
        self._progress_callback = callback

    # ── 数据集准备 ─────────────────────────────────

    def prepare_dataset(self) -> bool:
        """
        准备 YOLO 格式数据集
        
        目录结构：
            dataset/
            ├── images/
            │   ├── train/
            │   ├── val/
            │   └── test/
            ├── labels/
            │   ├── train/
            │   ├── val/
            │   └── test/
            └── data.yaml
        """
        cfg = self._config
        
        # 创建目录
        for split in ['train', 'val', 'test']:
            (cfg.images_dir / split).mkdir(parents=True, exist_ok=True)
            (cfg.labels_dir / split).mkdir(parents=True, exist_ok=True)
        
        # 生成 data.yaml
        yaml_content = self._generate_data_yaml()
        yaml_path = cfg.dataset_path / "data.yaml"
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        
        return True

    def split_dataset(self, source_images_dir: str, source_labels_dir: str):
        """
        将源数据按比例划分为 train/val/test
        """
        cfg = self._config
        img_dir = Path(source_images_dir)
        lbl_dir = Path(source_labels_dir)
        
        images = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
        random.shuffle(images)
        
        n = len(images)
        n_train = int(n * cfg.train_ratio)
        n_val = int(n * cfg.val_ratio)
        
        splits = {
            'train': images[:n_train],
            'val': images[n_train:n_train + n_val],
            'test': images[n_train + n_val:]
        }
        
        for split_name, split_images in splits.items():
            for img_path in split_images:
                # 复制图片
                dst_img = cfg.images_dir / split_name / img_path.name
                shutil.copy2(str(img_path), str(dst_img))
                
                # 复制标注
                lbl_path = lbl_dir / f"{img_path.stem}.txt"
                if lbl_path.exists():
                    dst_lbl = cfg.labels_dir / split_name / lbl_path.name
                    shutil.copy2(str(lbl_path), str(dst_lbl))

    def _generate_data_yaml(self) -> str:
        """生成 YOLO 数据集配置文件"""
        cfg = self._config
        root = str(cfg.dataset_path.absolute())
        
        lines = [
            f"path: {root}",
            f"train: images/train",
            f"val: images/val",
            f"test: images/test",
            "",
            "names:"
        ]
        
        for i, cls_name in enumerate(cfg.classes):
            lines.append(f"  {i}: {cls_name}")
        
        return '\n'.join(lines) + '\n'

    # ── 训练 ──────────────────────────────────────

    def load_model(self, model_path: Optional[str] = None):
        """加载模型"""
        if not _YOLO_AVAILABLE:
            raise ImportError("请安装 ultralytics: pip install ultralytics")
        
        if model_path and os.path.exists(model_path):
            self._model = YOLO(model_path)
        else:
            size = self._config.model_size
            self._model = YOLO(f"yolov8{size}.pt")

    def train(self, resume: bool = False) -> Optional[Dict]:
        """
        开始训练
        
        Args:
            resume: 是否从上次中断处继续
            
        Returns:
            训练结果字典
        """
        if not _YOLO_AVAILABLE:
            raise ImportError("请安装 ultralytics: pip install ultralytics")
        
        if self._model is None:
            self.load_model()
        
        cfg = self._config
        yaml_path = str(cfg.dataset_path / "data.yaml")
        
        self._is_training = True
        try:
            results = self._model.train(
                data=yaml_path,
                epochs=cfg.epochs,
                batch=cfg.batch_size,
                lr0=cfg.learning_rate,
                patience=cfg.patience,
                imgsz=cfg.image_size[0],
                augment=cfg.augmentation,
                project=str(cfg.dataset_path / "runs"),
                name="train",
                exist_ok=True,
                resume=resume,
                verbose=True
            )
            self._results = results
            return results
        finally:
            self._is_training = False

    def validate(self) -> Optional[Dict]:
        """验证模型"""
        if self._model is None:
            return None
        cfg = self._config
        yaml_path = str(cfg.dataset_path / "data.yaml")
        return self._model.val(data=yaml_path)

    def predict(self, image: np.ndarray, conf: float = 0.5) -> List[BoundingBox]:
        """推理预测"""
        if self._model is None:
            return []
        
        results = self._model(image, conf=conf, verbose=False)
        boxes = []
        
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf_val = float(box.conf[0])
                img_h, img_w = result.orig_shape
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                boxes.append(BoundingBox(
                    class_id=cls_id,
                    x_center=((x1 + x2) / 2) / img_w,
                    y_center=((y1 + y2) / 2) / img_h,
                    width=(x2 - x1) / img_w,
                    height=(y2 - y1) / img_h,
                    confidence=conf_val
                ))
        
        return boxes

    def export(self, format: str = "onnx", **kwargs) -> str:
        """
        导出模型
        
        Args:
            format: 导出格式 (onnx, engine, openvino, coreml, etc.)
        """
        if self._model is None:
            raise RuntimeError("请先加载或训练模型")
        return self._model.export(format=format, **kwargs)

    def get_best_model_path(self) -> Optional[str]:
        """获取最佳模型路径"""
        cfg = self._config
        best_path = cfg.dataset_path / "runs" / "train" / "weights" / "best.pt"
        if best_path.exists():
            return str(best_path)
        return None

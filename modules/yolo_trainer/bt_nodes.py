"""
YOLO 行为树节点
===============
将 YOLO 训练器集成到行为树系统中

新增节点：
  - YOLOCaptureNode: 窗口截图采集节点
  - YOLOTrainNode: YOLO 训练节点
  - YOLOPredictNode: YOLO 推理检测节点
  - YOLOAutoAnnotateNode: 自动标注节点
"""

import os
import time
import threading
from typing import Optional, Dict, Any

import numpy as np

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

# 行为树核心导入
from bt_core.nodes import ActionNode, ConditionNode, NodeStatus
from bt_core.blackboard import Blackboard


class YOLOCaptureNode(ActionNode):
    """
    行为树节点：窗口截图采集
    
    参数：
        window_title: 窗口标题（模糊匹配）
        save_dir: 保存目录
        max_samples: 最大采集数量
        capture_interval: 截图间隔（秒）
        output_key: 黑板输出键（保存最新截图路径）
    
    用法（行为树中）：
        YOLOCaptureNode:
            window_title: "原神"
            save_dir: "./data/raw"
            max_samples: 500
            capture_interval: 0.5
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.window_title = kwargs.get("window_title", "")
        self.save_dir = kwargs.get("save_dir", "./data/yolo_raw")
        self.max_samples = kwargs.get("max_samples", 500)
        self.capture_interval = kwargs.get("capture_interval", 0.5)
        self.output_key = kwargs.get("output_key", "yolo_last_capture")
        
        self._capture = None
        self._collector = None
        self._count = 0
        self._running = False
        self._thread = None

    def _tick_internal(self) -> NodeStatus:
        if not _CV2_AVAILABLE:
            self._set_error("OpenCV 未安装")
            return NodeStatus.FAILURE

        # 初始化
        if self._capture is None:
            try:
                from ..capture.window_capture import WindowCapture
                from ..training.trainer import AutoScreenshotCollector, TrainingConfig
                
                self._capture = WindowCapture()
                if not self._capture.bind_window(title_contains=self.window_title):
                    self._set_error(f"未找到窗口: {self.window_title}")
                    return NodeStatus.FAILURE
                
                config = TrainingConfig()
                config.max_samples = self.max_samples
                config.capture_interval = self.capture_interval
                
                self._collector = AutoScreenshotCollector(self._capture, config)
            except Exception as e:
                self._set_error(f"初始化失败: {e}")
                return NodeStatus.FAILURE

        # 开始采集
        if not self._running:
            self._running = True
            self._collector.start()
            return NodeStatus.RUNNING

        # 检查进度
        self._count = self._collector.count
        
        # 写入黑板
        if self.blackboard:
            self.blackboard.set("yolo_capture_count", self._count)
            self.blackboard.set("yolo_capture_progress",
                              self._count / self.max_samples * 100)

        # 完成
        if self._count >= self.max_samples:
            self._collector.stop()
            self._running = False
            self._set_status(f"采集完成: {self._count} 张")
            return NodeStatus.SUCCESS

        # 更新状态
        self._set_status(f"采集中: {self._count}/{self.max_samples}")
        return NodeStatus.RUNNING

    def _reset(self):
        super()._reset()
        if self._collector and self._running:
            self._collector.stop()
        self._running = False


class YOLOTrainNode(ActionNode):
    """
    行为树节点：YOLO 模型训练
    
    参数：
        dataset_path: 数据集路径
        classes: 类别列表
        model_size: 模型大小 (n/s/m/l/x)
        epochs: 训练轮数
        batch_size: 批次大小
        output_key: 黑板输出键（保存最佳模型路径）
    
    用法：
        YOLOTrainNode:
            dataset_path: "./data/yolo_datasets/my_dataset"
            classes: ["enemy", "item", "npc"]
            model_size: "n"
            epochs: 50
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dataset_path = kwargs.get("dataset_path", "./data/yolo_datasets/default")
        self.classes = kwargs.get("classes", [])
        self.model_size = kwargs.get("model_size", "n")
        self.epochs = kwargs.get("epochs", 50)
        self.batch_size = kwargs.get("batch_size", 16)
        self.output_key = kwargs.get("output_key", "yolo_best_model")
        
        self._trainer = None
        self._training_thread = None
        self._is_training = False
        self._results = None

    def _tick_internal(self) -> NodeStatus:
        # 初始化训练器
        if self._trainer is None:
            try:
                from ..training.trainer import YOLOTrainer, TrainingConfig
                
                config = TrainingConfig()
                config.dataset_path = self.dataset_path
                config.classes = self.classes
                config.model_size = self.model_size
                config.epochs = self.epochs
                config.batch_size = self.batch_size
                
                self._trainer = YOLOTrainer(config)
                
                # 准备数据集
                if not os.path.exists(os.path.join(self.dataset_path, "data.yaml")):
                    self._trainer.prepare_dataset()
                    
            except Exception as e:
                self._set_error(f"初始化失败: {e}")
                return NodeStatus.FAILURE

        # 开始训练
        if not self._is_training:
            self._is_training = True
            
            def _train():
                try:
                    self._results = self._trainer.train()
                except Exception as e:
                    self._set_error(f"训练失败: {e}")
                finally:
                    self._is_training = False
            
            self._training_thread = threading.Thread(target=_train, daemon=True)
            self._training_thread.start()
            
            self._set_status("训练中...")
            return NodeStatus.RUNNING

        # 训练中
        if self._is_training:
            # 更新黑板
            if self._trainer and self._trainer.results:
                summary = self._trainer.results
                if self.blackboard:
                    self.blackboard.set("yolo_training_progress", summary)
            return NodeStatus.RUNNING

        # 训练完成
        if self._results:
            best_path = self._trainer.get_best_model_path()
            if best_path and self.blackboard:
                self.blackboard.set(self.output_key, best_path)
            self._set_status(f"训练完成，模型: {best_path}")
            return NodeStatus.SUCCESS
        
        return NodeStatus.FAILURE

    def _reset(self):
        super()._reset()
        self._is_training = False


class YOLOPredictNode(ActionNode):
    """
    行为树节点：YOLO 推理检测
    
    参数：
        model_path: 模型路径
        window_title: 窗口标题（空则使用上次截图）
        confidence: 置信度阈值
        target_class: 目标类别（空则检测所有）
        output_key: 黑板输出键（保存检测结果）
    
    用法：
        YOLOPredictNode:
            model_path: "./data/runs/train/weights/best.pt"
            window_title: "原神"
            confidence: 0.5
            target_class: "enemy"
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs.get("model_path", "")
        self.window_title = kwargs.get("window_title", "")
        self.confidence = kwargs.get("confidence", 0.5)
        self.target_class = kwargs.get("target_class", "")
        self.output_key = kwargs.get("output_key", "yolo_detections")
        
        self._model = None
        self._capture = None

    def _tick_internal(self) -> NodeStatus:
        try:
            from ultralytics import YOLO
            from ..capture.window_capture import WindowCapture
        except ImportError as e:
            self._set_error(f"依赖缺失: {e}")
            return NodeStatus.FAILURE

        # 加载模型
        if self._model is None:
            if not os.path.exists(self.model_path):
                self._set_error(f"模型不存在: {self.model_path}")
                return NodeStatus.FAILURE
            self._model = YOLO(self.model_path)

        # 获取画面
        frame = None
        
        # 从黑板获取帧
        if self.blackboard:
            frame = self.blackboard.get("yolo_current_frame")
        
        # 从窗口捕获
        if frame is None and self.window_title:
            if self._capture is None:
                self._capture = WindowCapture()
            if self._capture.bind_window(title_contains=self.window_title):
                frame = self._capture.capture()
        
        if frame is None:
            self._set_error("无法获取画面")
            return NodeStatus.FAILURE

        # 推理
        results = self._model(frame, conf=self.confidence, verbose=False)
        
        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                cls_name = result.names[cls_id]
                
                # 过滤目标类别
                if self.target_class and cls_name != self.target_class:
                    continue
                
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                detections.append({
                    "class": cls_name,
                    "class_id": cls_id,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "center": [(x1+x2)/2, (y1+y2)/2],
                })
        
        # 写入黑板
        if self.blackboard:
            self.blackboard.set(self.output_key, detections)
            self.blackboard.set(f"{self.output_key}_count", len(detections))
        
        self._set_status(f"检测到 {len(detections)} 个目标")
        
        # 根据是否有检测结果返回状态
        if self.target_class:
            return NodeStatus.SUCCESS if detections else NodeStatus.FAILURE
        return NodeStatus.SUCCESS

    def _reset(self):
        super()._reset()


class YOLOAutoAnnotateNode(ActionNode):
    """
    行为树节点：自动标注
    
    参数：
        image_dir: 图片目录
        model_path: 预训练模型路径（空则使用默认）
        target_classes: 目标类别列表
        confidence_threshold: 置信度阈值
        output_key: 黑板输出键
    
    用法：
        YOLOAutoAnnotateNode:
            image_dir: "./data/raw"
            model_path: "yolov8n.pt"
            target_classes: ["person", "car"]
            confidence_threshold: 0.5
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.image_dir = kwargs.get("image_dir", "./data/raw")
        self.model_path = kwargs.get("model_path", "")
        self.target_classes = kwargs.get("target_classes", [])
        self.confidence_threshold = kwargs.get("confidence_threshold", 0.5)
        self.output_key = kwargs.get("output_key", "yolo_annotation_stats")
        
        self._annotator = None
        self._done = False

    def _tick_internal(self) -> NodeStatus:
        if self._done:
            return NodeStatus.SUCCESS

        try:
            from ..training.trainer import SmartAnnotator, TrainingConfig
            
            config = TrainingConfig()
            config.confidence_threshold = self.confidence_threshold
            
            self._annotator = SmartAnnotator(config)
            
            if self.model_path:
                self._annotator.load_pretrained_model(self.model_path)
            else:
                self._annotator.load_pretrained_model()
            
            stats = self._annotator.batch_annotate(
                self.image_dir, "", self.target_classes)
            
            # 写入黑板
            if self.blackboard:
                total_boxes = sum(stats.values())
                self.blackboard.set(self.output_key, {
                    "annotated_images": len(stats),
                    "total_boxes": total_boxes,
                    "details": stats
                })
            
            self._set_status(f"标注完成: {len(stats)} 张, {total_boxes} 个框")
            self._done = True
            return NodeStatus.SUCCESS
            
        except Exception as e:
            self._set_error(f"标注失败: {e}")
            return NodeStatus.FAILURE

    def _reset(self):
        super()._reset()
        self._done = False


# ── 节点注册便捷函数 ─────────────────────────────

def register_yolo_nodes(registry):
    """
    将所有 YOLO 节点注册到行为树注册表
    
    Args:
        registry: bt_core.registry.NodeRegistry 实例
    """
    if registry is None:
        return
    
    nodes = [
        ("yolo_capture", YOLOCaptureNode, "YOLO截图采集"),
        ("yolo_train", YOLOTrainNode, "YOLO模型训练"),
        ("yolo_predict", YOLOPredictNode, "YOLO推理检测"),
        ("yolo_auto_annotate", YOLOAutoAnnotateNode, "YOLO自动标注"),
    ]
    
    for type_name, node_class, description in nodes:
        registry.register(type_name, node_class, description)

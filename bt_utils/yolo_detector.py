"""
YOLO 目标检测器

基于 ultralytics YOLO 模型的目标检测封装。
支持 YOLOv8/v11 等模型，按类别过滤，置信度阈值控制。
"""
from typing import Tuple, Optional, List, Dict, Any
import os


class YOLODetector:
    """YOLO 目标检测器（单例模式，延迟加载）"""

    _instance = None
    _model = None
    _model_path = None

    @classmethod
    def get_instance(cls) -> "YOLODetector":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        """检查 YOLO 是否可用"""
        try:
            import ultralytics
            return True
        except ImportError:
            return False

    def load_model(self, model_path: str) -> bool:
        """加载 YOLO 模型

        Args:
            model_path: 模型文件路径 (.pt)

        Returns:
            是否加载成功
        """
        if self._model is not None and self._model_path == model_path:
            return True

        if not os.path.exists(model_path):
            return False

        try:
            from ultralytics import YOLO
            self._model = YOLO(model_path)
            self._model_path = model_path
            return True
        except Exception:
            return False

    def detect(self, image, conf: float = 0.5, classes: List[int] = None,
               max_det: int = 10) -> List[Dict[str, Any]]:
        """执行目标检测

        Args:
            image: PIL.Image 或 numpy array 图像
            conf: 置信度阈值
            classes: 过滤的目标类别 ID 列表，None 表示不过滤
            max_det: 最大检测数

        Returns:
            检测结果列表，每项包含:
            - class_id: int, 类别 ID
            - class_name: str, 类别名称
            - confidence: float, 置信度
            - bbox: (x1, y1, x2, y2), 边界框
            - center: (cx, cy), 中心点坐标
        """
        if self._model is None:
            return []

        results = self._model(image, conf=conf, max_det=max_det, verbose=False)
        detections = []

        for result in results:
            if result.boxes is None:
                continue

            boxes = result.boxes
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf_val = float(boxes.conf[i].item())

                if classes is not None and cls_id not in classes:
                    continue

                xyxy = boxes.xyxy[i].tolist()
                x1, y1, x2, y2 = xyxy
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                class_name = self._model.names.get(cls_id, str(cls_id)) if hasattr(self._model, 'names') else str(cls_id)

                detections.append({
                    "class_id": cls_id,
                    "class_name": class_name,
                    "confidence": conf_val,
                    "bbox": (x1, y1, x2, y2),
                    "center": (cx, cy),
                })

        # 按置信度降序排列
        detections.sort(key=lambda d: d["confidence"], reverse=True)
        return detections

    def detect_first(self, image, conf: float = 0.5,
                     classes: List[int] = None) -> Optional[Dict[str, Any]]:
        """执行检测，只返回置信度最高的结果

        Args:
            image: PIL.Image 或 numpy array
            conf: 置信度阈值
            classes: 过滤的类别 ID 列表

        Returns:
            单个检测结果字典，或 None
        """
        detections = self.detect(image, conf=conf, classes=classes, max_det=1)
        return detections[0] if detections else None

    @staticmethod
    def get_available_models() -> List[str]:
        """扫描项目 models 目录下可用的 .pt 文件"""
        models = []
        search_dirs = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "models"),
            os.path.join(os.getcwd(), "models"),
        ]
        for d in search_dirs:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".pt"):
                        models.append(os.path.join(d, f))
        return models

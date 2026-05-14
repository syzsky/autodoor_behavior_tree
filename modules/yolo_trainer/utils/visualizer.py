"""
可视化模块
==========
- DetectionVisualizer: 检测结果可视化
- TrainingMonitor: 训练过程监控
"""

import time
import threading
from typing import Optional, List, Tuple, Dict
from collections import deque

import cv2
import numpy as np

from ..training.trainer import BoundingBox


class DetectionVisualizer:
    """检测结果可视化器"""

    # 预定义颜色表 (BGR)
    COLORS = [
        (0, 255, 0),    # 绿
        (255, 0, 0),    # 蓝
        (0, 0, 255),    # 红
        (255, 255, 0),  # 青
        (255, 0, 255),  # 紫
        (0, 255, 255),  # 黄
        (128, 255, 0),  # 浅绿
        (255, 128, 0),  # 橙
        (128, 0, 255),  # 粉
        (0, 128, 255),  # 浅蓝
    ]

    def __init__(self, classes: List[str] = None, font_scale: float = 0.6,
                 thickness: int = 2, show_confidence: bool = True):
        self._classes = classes or []
        self._font_scale = font_scale
        self._thickness = thickness
        self._show_confidence = show_confidence

    def set_classes(self, classes: List[str]):
        """设置类别名称"""
        self._classes = classes

    def draw_detections(self, image: np.ndarray,
                        boxes: List[BoundingBox]) -> np.ndarray:
        """
        在图片上绘制检测结果
        
        Args:
            image: 原始图片 (BGR)
            boxes: 检测框列表
            
        Returns:
            绘制后的图片
        """
        result = image.copy()
        h, w = result.shape[:2]
        
        for box in boxes:
            # 获取颜色
            color = self.COLORS[box.class_id % len(self.COLORS)]
            
            # 转换为像素坐标
            x1, y1, x2, y2 = box.to_pixels(w, h)
            
            # 绘制边界框
            cv2.rectangle(result, (x1, y1), (x2, y2), color, self._thickness)
            
            # 绘制标签
            label = self._get_label(box)
            if label:
                (tw, th), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, self._font_scale, 1)
                
                # 标签背景
                cv2.rectangle(result, (x1, y1 - th - baseline - 4),
                             (x1 + tw, y1), color, -1)
                cv2.putText(result, label, (x1, y1 - baseline - 2),
                           cv2.FONT_HERSHEY_SIMPLEX, self._font_scale,
                           (255, 255, 255), 1, cv2.LINE_AA)
        
        return result

    def draw_roi(self, image: np.ndarray, x: int, y: int,
                 w: int, h: int, label: str = "ROI") -> np.ndarray:
        """绘制感兴趣区域"""
        result = image.copy()
        cv2.rectangle(result, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.putText(result, label, (x, y - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        return result

    def draw_fps(self, image: np.ndarray, fps: float) -> np.ndarray:
        """绘制 FPS"""
        result = image.copy()
        text = f"FPS: {fps:.1f}"
        cv2.putText(result, text, (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return result

    def draw_info(self, image: np.ndarray, info: Dict[str, str]) -> np.ndarray:
        """绘制信息面板"""
        result = image.copy()
        y_offset = 50
        for key, value in info.items():
            text = f"{key}: {value}"
            cv2.putText(result, text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            y_offset += 20
        return result

    def _get_label(self, box: BoundingBox) -> str:
        """生成标签文本"""
        if box.class_id < len(self._classes):
            name = self._classes[box.class_id]
        else:
            name = f"cls_{box.class_id}"
        
        if self._show_confidence:
            return f"{name} {box.confidence:.2f}"
        return name


class TrainingMonitor:
    """
    训练过程监控器
    
    记录和可视化训练指标
    """

    def __init__(self, max_history: int = 1000):
        self._max_history = max_history
        self._metrics: Dict[str, deque] = {}
        self._epoch_times: deque = deque(maxlen=max_history)
        self._start_time = time.time()
        self._current_epoch = 0
        self._lock = threading.Lock()

    def log_metric(self, name: str, value: float, epoch: int = 0):
        """记录指标"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = deque(maxlen=self._max_history)
            self._metrics[name].append((epoch, value, time.time()))

    def log_epoch(self, epoch: int, metrics: Dict[str, float],
                  epoch_time: float = 0):
        """记录一个 epoch 的结果"""
        with self._lock:
            self._current_epoch = epoch
            self._epoch_times.append(epoch_time)
            for name, value in metrics.items():
                self.log_metric(name, value, epoch)

    def get_metric(self, name: str) -> List[Tuple[int, float, float]]:
        """获取指标历史"""
        with self._lock:
            if name in self._metrics:
                return list(self._metrics[name])
            return []

    def get_latest(self, name: str) -> Optional[float]:
        """获取最新值"""
        history = self.get_metric(name)
        if history:
            return history[-1][1]
        return None

    def get_summary(self) -> Dict[str, Any]:
        """获取训练摘要"""
        with self._lock:
            summary = {
                "current_epoch": self._current_epoch,
                "total_time": time.time() - self._start_time,
                "metrics": {}
            }
            for name, values in self._metrics.items():
                if values:
                    vals = [v[1] for v in values]
                    summary["metrics"][name] = {
                        "latest": vals[-1],
                        "best": max(vals) if "accuracy" in name or "mAP" in name else min(vals),
                        "history_length": len(vals)
                    }
            return summary

    def plot_metric(self, name: str, size: Tuple[int, int] = (640, 320),
                    bg_color: Tuple[int, int, int] = (30, 30, 30)) -> np.ndarray:
        """
        绘制指标曲线图
        
        Returns:
            曲线图 (numpy BGR)
        """
        history = self.get_metric(name)
        if not history:
            return np.zeros((size[1], size[0], 3), dtype=np.uint8)
        
        canvas = np.full((size[1], size[0], 3), bg_color, dtype=np.uint8)
        
        epochs = [h[0] for h in history]
        values = [h[1] for h in history]
        
        if len(values) < 2:
            return canvas
        
        # 归一化到画布
        min_v, max_v = min(values), max(values)
        if max_v == min_v:
            max_v = min_v + 1
        
        pad = 40
        graph_w = size[0] - pad * 2
        graph_h = size[1] - pad * 2
        
        points = []
        for i, v in enumerate(values):
            x = pad + int(i / max(1, len(values) - 1) * graph_w)
            y = pad + int((1 - (v - min_v) / (max_v - min_v)) * graph_h)
            points.append((x, y))
        
        # 绘制曲线
        for i in range(1, len(points)):
            cv2.line(canvas, points[i-1], points[i], (0, 200, 100), 2)
        
        # 绘制点
        for pt in points[::max(1, len(points)//20)]:
            cv2.circle(canvas, pt, 3, (0, 200, 100), -1)
        
        # 标题和标签
        latest = values[-1]
        cv2.putText(canvas, f"{name}: {latest:.4f}", (pad, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(canvas, f"min: {min_v:.4f}", (pad, size[1] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        cv2.putText(canvas, f"max: {max_v:.4f}", (size[0] - pad - 80, size[1] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        
        return canvas

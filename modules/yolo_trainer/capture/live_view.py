"""
YOLO 实时画面组件
=================
功能：
  - 绑定窗口实时预览（画中画模式）
  - 画面缩放与平移
  - 实时标注叠加显示
  - 录制视频
  - 截图标记
  - FPS 与性能监控
"""

import threading
import time
from typing import Optional, Callable, Tuple, List
from pathlib import Path
from dataclasses import dataclass, field

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


@dataclass
class ViewConfig:
    """画面配置"""
    # 显示
    max_width: int = 960
    max_height: int = 540
    show_fps: bool = True
    show_info: bool = True
    show_crosshair: bool = False
    
    # 录制
    record_fps: int = 15
    record_codec: str = "mp4v"
    
    # 标注叠加
    show_annotations: bool = True
    annotation_color: Tuple[int, int, int] = (0, 255, 0)
    annotation_thickness: int = 2
    
    # 画中画
    pip_enabled: bool = False
    pip_position: str = "bottom-right"  # top-left, top-right, bottom-left, bottom-right
    pip_scale: float = 0.25


class LiveView:
    """
    实时画面组件
    
    用法：
        view = LiveView(capture, config)
        view.on_frame = my_callback
        view.start()
        # ...
        view.stop()
    """

    def __init__(self, capture, config: Optional[ViewConfig] = None):
        self._capture = capture
        self._config = config or ViewConfig()
        
        # 流控制
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._fps_limit = 30
        
        # 录制
        self._recording = False
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._record_path: Optional[str] = None
        
        # 性能监控
        self._actual_fps = 0.0
        self._frame_count = 0
        self._start_time = 0.0
        
        # 回调
        self.on_frame: Optional[Callable] = None
        self.on_fps_update: Optional[Callable[[float], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # 缩放/平移
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        
        # 截图
        self._screenshot_dir = Path("./data/screenshots")
        self._screenshot_count = 0
        
        # 标注叠加数据
        self._overlay_boxes: List[dict] = []
        self._overlay_lock = threading.Lock()

    @property
    def actual_fps(self) -> float:
        return self._actual_fps

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def zoom_level(self) -> float:
        return self._zoom_level

    # ── 控制 ─────────────────────────────────────

    def start(self, fps_limit: int = 30):
        """开始实时画面"""
        if self._running:
            return
        self._fps_limit = fps_limit
        self._running = True
        self._start_time = time.time()
        self._frame_count = 0
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止实时画面"""
        self._running = False
        self._stop_recording()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    def pause(self):
        """暂停（不销毁线程）"""
        self._running = False

    def resume(self):
        """恢复"""
        if not self._thread or not self._thread.is_alive():
            self.start(self._fps_limit)
        else:
            self._running = True

    # ── 缩放与平移 ─────────────────────────────

    def zoom_in(self, factor: float = 1.2):
        """放大"""
        self._zoom_level = min(self._zoom_level * factor, 5.0)

    def zoom_out(self, factor: float = 1.2):
        """缩小"""
        self._zoom_level = max(self._zoom_level / factor, 0.5)

    def zoom_reset(self):
        """重置缩放"""
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0

    def pan(self, dx: int, dy: int):
        """平移"""
        self._pan_x += dx
        self._pan_y += dy

    # ── 录制 ─────────────────────────────────────

    def start_recording(self, save_path: Optional[str] = None,
                        fps: int = 15) -> str:
        """
        开始录制视频

        Args:
            save_path: 保存路径（默认自动生成）
            fps: 录制帧率

        Returns:
            录制文件路径
        """
        if save_path is None:
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            save_path = str(self._screenshot_dir / f"recording_{timestamp}.mp4")

        self._record_path = save_path
        self._recording = True
        return save_path

    def stop_recording(self) -> Optional[str]:
        """
        停止录制

        Returns:
            录制文件路径
        """
        self._stop_recording()
        return self._record_path

    def _stop_recording(self):
        if self._video_writer:
            self._video_writer.release()
            self._video_writer = None
        self._recording = False

    # ── 截图 ─────────────────────────────────────

    def take_screenshot(self, save_path: Optional[str] = None,
                        with_overlay: bool = True) -> Optional[str]:
        """
        截取当前帧

        Args:
            save_path: 保存路径
            with_overlay: 是否包含叠加信息

        Returns:
            保存路径
        """
        frame = self._capture.capture() if self._capture else None
        if frame is None:
            return None

        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

        if save_path is None:
            timestamp = int(time.time() * 1000)
            save_path = str(self._screenshot_dir / f"screenshot_{timestamp}.jpg")

        if with_overlay:
            frame = self._apply_overlay(frame)

        cv2.imwrite(save_path, frame)
        self._screenshot_count += 1
        return save_path

    # ── 标注叠加 ─────────────────────────────────

    def set_overlay_boxes(self, boxes: List[dict]):
        """
        设置叠加的标注框

        Args:
            boxes: [{"class_id": int, "x_center": float, "y_center": float,
                     "width": float, "height": float, "confidence": float,
                     "class_name": str, "color": (b,g,r)}, ...]
        """
        with self._overlay_lock:
            self._overlay_boxes = boxes

    def clear_overlay(self):
        """清除叠加"""
        with self._overlay_lock:
            self._overlay_boxes = []

    # ── 核心循环 ─────────────────────────────────

    def _stream_loop(self):
        """流主循环"""
        frame_interval = 1.0 / max(self._fps_limit, 1)
        fps_update_interval = 0.5  # 每 0.5 秒更新一次 FPS
        last_fps_update = time.time()
        fps_frame_count = 0

        while self._running:
            loop_start = time.time()

            try:
                frame = self._capture.capture() if self._capture else None
                if frame is None:
                    time.sleep(0.01)
                    continue

                self._frame_count += 1
                fps_frame_count += 1

                # 缩放处理
                processed = self._apply_zoom(frame)

                # 叠加标注
                with self._overlay_lock:
                    if self._overlay_boxes and self._config.show_annotations:
                        processed = self._draw_annotations(processed)

                # FPS 和信息叠加
                if self._config.show_fps or self._config.show_info:
                    processed = self._draw_hud(processed)

                # 画中画
                if self._config.pip_enabled:
                    processed = self._apply_pip(processed, frame)

                # 录制
                if self._recording and self._video_writer is None:
                    h, w = processed.shape[:2]
                    self._video_writer = cv2.VideoWriter(
                        self._record_path,
                        cv2.VideoWriter_fourcc(*self._config.record_codec),
                        self._config.record_fps,
                        (w, h)
                    )

                if self._recording and self._video_writer:
                    self._video_writer.write(processed)

                # 回调
                if self.on_frame:
                    try:
                        self.on_frame(processed)
                    except Exception:
                        pass

                # FPS 更新
                now = time.time()
                if now - last_fps_update >= fps_update_interval:
                    self._actual_fps = fps_frame_count / (now - last_fps_update)
                    fps_frame_count = 0
                    last_fps_update = now
                    if self.on_fps_update:
                        try:
                            self.on_fps_update(self._actual_fps)
                        except Exception:
                            pass

            except Exception as e:
                if self.on_error:
                    try:
                        self.on_error(e)
                    except Exception:
                        pass

            # 帧率控制
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _apply_zoom(self, frame: np.ndarray) -> np.ndarray:
        """应用缩放和平移"""
        if self._zoom_level == 1.0 and self._pan_x == 0 and self._pan_y == 0:
            return frame

        h, w = frame.shape[:2]
        
        # 缩放
        if self._zoom_level != 1.0:
            new_w = int(w * self._zoom_level)
            new_h = int(h * self._zoom_level)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # 平移裁剪
        if self._pan_x != 0 or self._pan_y != 0:
            ch, cw = frame.shape[:2]
            x1 = max(0, min(self._pan_x, cw - w))
            y1 = max(0, min(self._pan_y, ch - h))
            x2 = min(x1 + w, cw)
            y2 = min(y1 + h, ch)
            frame = frame[y1:y2, x1:x2]

        # 限制最大尺寸
        max_w = self._config.max_width
        max_h = self._config.max_height
        fh, fw = frame.shape[:2]
        scale = min(max_w / max(fw, 1), max_h / max(fh, 1), 1.0)
        if scale < 1.0:
            frame = cv2.resize(frame, (int(fw * scale), int(fh * scale)))

        return frame

    def _draw_annotations(self, frame: np.ndarray) -> np.ndarray:
        """绘制标注框叠加"""
        h, w = frame.shape[:2]
        result = frame.copy()

        for box in self._overlay_boxes:
            cls_id = box.get("class_id", 0)
            cx = box.get("x_center", 0.5)
            cy = box.get("y_center", 0.5)
            bw = box.get("width", 0.1)
            bh = box.get("height", 0.1)
            conf = box.get("confidence", 1.0)
            cls_name = box.get("class_name", f"cls{cls_id}")
            color = box.get("color", self._config.annotation_color)

            # 转换为像素坐标
            x1 = int((cx - bw / 2) * w)
            y1 = int((cy - bh / 2) * h)
            x2 = int((cx + bw / 2) * w)
            y2 = int((cy + bh / 2) * h)

            # 画框
            cv2.rectangle(result, (x1, y1), (x2, y2), color,
                         self._config.annotation_thickness)

            # 标签
            label = f"{cls_name} {conf:.2f}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            cv2.rectangle(result, (x1, y1 - th - baseline - 4),
                         (x1 + tw + 4, y1), color, -1)
            cv2.putText(result, label, (x1 + 2, y1 - baseline - 2),
                       font, font_scale, (255, 255, 255), thickness)

        return result

    def _draw_hud(self, frame: np.ndarray) -> np.ndarray:
        """绘制 HUD（抬头显示）信息"""
        result = frame.copy()
        h, w = result.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        y_offset = 20

        if self._config.show_fps:
            fps_text = f"FPS: {self._actual_fps:.1f}"
            cv2.putText(result, fps_text, (10, y_offset),
                       font, font_scale, (0, 255, 0), thickness)
            y_offset += 20

        if self._config.show_info:
            zoom_text = f"Zoom: {self._zoom_level:.1f}x"
            cv2.putText(result, zoom_text, (10, y_offset),
                       font, font_scale, (0, 255, 0), thickness)
            y_offset += 20

            if self._capture and hasattr(self._capture, 'window_info') and self._capture.window_info:
                info = self._capture.window_info
                win_text = f"Window: {info.title} ({info.width}x{info.height})"
                cv2.putText(result, win_text, (10, y_offset),
                           font, font_scale, (255, 255, 0), thickness)
                y_offset += 20

        # 录制指示
        if self._recording:
            # 闪烁红点
            if int(time.time() * 2) % 2 == 0:
                cv2.circle(result, (w - 20, 20), 8, (0, 0, 255), -1)
            cv2.putText(result, "REC", (w - 80, 25),
                       font, font_scale, (0, 0, 255), thickness)

        # 十字准星
        if self._config.show_crosshair:
            cx, cy = w // 2, h // 2
            cv2.line(result, (cx - 20, cy), (cx + 20, cy), (0, 255, 255), 1)
            cv2.line(result, (cx, cy - 20), (cx, cy + 20), (0, 255, 255), 1)

        return result

    def _apply_pip(self, main_frame: np.ndarray,
                   original_frame: np.ndarray) -> np.ndarray:
        """应用画中画"""
        result = main_frame.copy()
        h, w = result.shape[:2]

        # 缩小的原始画面
        pip_w = int(w * self._config.pip_scale)
        pip_h = int(h * self._config.pip_scale)
        pip = cv2.resize(original_frame, (pip_w, pip_h))

        # 边框
        pip_bordered = cv2.copyMakeBorder(
            pip, 2, 2, 2, 2,
            cv2.BORDER_CONSTANT, value=(0, 255, 0)
        )
        ph, pw = pip_bordered.shape[:2]

        # 位置
        margin = 10
        positions = {
            "top-left": (margin, margin),
            "top-right": (w - pw - margin, margin),
            "bottom-left": (margin, h - ph - margin),
            "bottom-right": (w - pw - margin, h - ph - margin),
        }
        px, py = positions.get(self._config.pip_position,
                               positions["bottom-right"])

        # 叠加
        roi = result[py:py + ph, px:px + pw]
        mask = pip_bordered[:, :, 0] >= 0  # 简单叠加
        roi[pip_bordered > 0] = pip_bordered[pip_bordered > 0]
        result[py:py + ph, px:px + pw] = roi

        return result

    # ── 清理 ─────────────────────────────────────

    def destroy(self):
        """清理资源"""
        self.stop()
        self._overlay_boxes.clear()

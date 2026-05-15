"""
实时画面流模块
==============
支持：
  - 独立线程捕获
  - 帧率控制
  - 帧缓冲队列
  - 暂停/恢复/停止
"""

import time
import threading
from collections import deque
from typing import Optional, Callable

import numpy as np


class ScreenStream:
    """
    实时画面流
    
    用法：
        stream = ScreenStream(capture, fps_limit=30)
        stream.on_frame = lambda frame: process(frame)
        stream.start()
        # ...
        stream.stop()
    """

    def __init__(self, capture, fps_limit: int = 30,
                 buffer_size: int = 2):
        self._capture = capture
        self._fps_limit = fps_limit
        self._frame_interval = 1.0 / fps_limit if fps_limit > 0 else 0
        self._buffer = deque(maxlen=buffer_size)
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._paused = threading.Event()
        self._paused.set()  # 默认不暂停
        self._lock = threading.Lock()
        
        # 回调
        self.on_frame: Optional[Callable[[np.ndarray], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # 统计
        self.frame_count = 0
        self.actual_fps = 0.0
        self._fps_timer = time.time()
        self._fps_counter = 0

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    @property
    def is_paused(self) -> bool:
        return not self._paused.is_set()

    def start(self):
        """启动画面流"""
        if self._running.is_set():
            return
        self._running.set()
        self._paused.set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止画面流"""
        self._running.clear()
        self._paused.set()  # 确保线程能退出
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

    def pause(self):
        """暂停捕获"""
        self._paused.clear()

    def resume(self):
        """恢复捕获"""
        self._paused.set()

    def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """从缓冲获取最新帧"""
        try:
            return self._buffer[-1]
        except IndexError:
            return None

    def _loop(self):
        """捕获循环"""
        while self._running.is_set():
            # 等待暂停解除
            self._paused.wait()
            if not self._running.is_set():
                break

            start = time.time()
            
            try:
                frame = self._capture.capture()
                if frame is not None:
                    with self._lock:
                        self._buffer.append(frame)
                    self.frame_count += 1
                    self._fps_counter += 1
                    
                    # 计算实际帧率
                    now = time.time()
                    if now - self._fps_timer >= 1.0:
                        self.actual_fps = self._fps_counter / (now - self._fps_timer)
                        self._fps_counter = 0
                        self._fps_timer = now
                    
                    # 回调
                    if self.on_frame:
                        self.on_frame(frame)
            except Exception as e:
                if self.on_error:
                    self.on_error(e)

            # 帧率控制
            if self._frame_interval > 0:
                elapsed = time.time() - start
                sleep_time = self._frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

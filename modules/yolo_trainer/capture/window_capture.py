"""
窗口绑定实时画面捕获模块
========================
支持：
  - 通过窗口标题/类名绑定目标窗口
  - 实时画面流（ScreenStream）
  - 多显示器支持
  - 窗口尺寸变化自动适配
"""

import time
import threading
from typing import Optional, Tuple, Callable, List
from dataclasses import dataclass, field

import cv2
import numpy as np

try:
    import win32gui
    import win32ui
    import win32con
    import win32api
    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False

try:
    import mss
    _MSS_AVAILABLE = True
except ImportError:
    _MSS_AVAILABLE = False


@dataclass
class WindowInfo:
    """窗口信息"""
    hwnd: int
    title: str
    class_name: str
    rect: Tuple[int, int, int, int]  # left, top, right, bottom
    width: int = 0
    height: int = 0

    def __post_init__(self):
        self.width = self.rect[2] - self.rect[0]
        self.height = self.rect[3] - self.rect[1]

    @property
    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0


class WindowCapture:
    """
    窗口画面捕获器
    
    用法：
        capture = WindowCapture()
        capture.bind_window("原神")
        frame = capture.capture()
        
        # 或使用回调实时处理
        capture.start_stream(lambda frame: process(frame))
    """

    def __init__(self, use_mss_fallback: bool = True):
        self._target: Optional[WindowInfo] = None
        self._use_mss_fallback = use_mss_fallback
        self._lock = threading.Lock()
        self._sct = mss.mss() if _MSS_AVAILABLE else None
        self._frame_count = 0
        self._last_frame: Optional[np.ndarray] = None
        self._fps = 0.0
        self._last_time = time.time()
        
    @property
    def is_bound(self) -> bool:
        return self._target is not None

    @property
    def window_info(self) -> Optional[WindowInfo]:
        return self._target

    @property
    def fps(self) -> float:
        return self._fps

    # ── 窗口枚举与绑定 ──────────────────────────────

    @staticmethod
    def enum_windows() -> List[WindowInfo]:
        """枚举所有可见窗口"""
        windows = []
        if not _WIN32_AVAILABLE:
            return windows

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            try:
                rect = win32gui.GetWindowRect(hwnd)
                cls = win32gui.GetClassName(hwnd)
                windows.append(WindowInfo(hwnd=hwnd, title=title, class_name=cls, rect=rect))
            except Exception:
                pass

        win32gui.EnumWindows(callback, None)
        return windows

    @staticmethod
    def find_window(title_contains: str = "", class_name: str = "") -> Optional[WindowInfo]:
        """按标题或类名查找窗口"""
        for w in WindowCapture.enum_windows():
            if title_contains and title_contains.lower() in w.title.lower():
                return w
            if class_name and class_name.lower() in w.class_name.lower():
                return w
        return None

    def bind_window(self, title_contains: str = "", hwnd: int = 0,
                    class_name: str = "") -> bool:
        """
        绑定目标窗口
        
        Args:
            title_contains: 窗口标题包含的字符串
            hwnd: 直接指定窗口句柄
            class_name: 窗口类名
            
        Returns:
            是否绑定成功
        """
        if hwnd > 0:
            try:
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                self._target = WindowInfo(hwnd=hwnd, title=title,
                                          class_name=cls, rect=rect)
                return self._target.is_valid
            except Exception:
                return False

        if title_contains or class_name:
            w = self.find_window(title_contains, class_name)
            if w:
                self._target = w
                return True

        return False

    def refresh_window(self) -> bool:
        """刷新窗口信息（尺寸可能已变化）"""
        if not self._target:
            return False
        try:
            rect = win32gui.GetWindowRect(self._target.hwnd)
            self._target = WindowInfo(
                hwnd=self._target.hwnd,
                title=self._target.title,
                class_name=self._target.class_name,
                rect=rect
            )
            return self._target.is_valid
        except Exception:
            return False

    # ── 画面捕获 ──────────────────────────────────

    def capture(self) -> Optional[np.ndarray]:
        """
        捕获当前窗口画面
        
        Returns:
            BGR格式的numpy数组，失败返回None
        """
        if not self._target:
            return None

        # 优先使用 win32 API
        if _WIN32_AVAILABLE:
            frame = self._capture_win32()
            if frame is not None:
                return frame

        # 回退到 mss
        if self._use_mss_fallback and self._sct:
            return self._capture_mss()

        return None

    def _capture_win32(self) -> Optional[np.ndarray]:
        """使用 win32 API 捕获"""
        try:
            hwnd = self._target.hwnd
            if not win32gui.IsWindow(hwnd):
                return None

            # 获取窗口DC
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            width = self._target.width
            height = self._target.height

            if width <= 0 or height <= 0:
                win32gui.ReleaseDC(hwnd, hwnd_dc)
                return None

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)

            # 使用 PrintWindow 捕获（支持后台窗口）
            result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
            if not result:
                # 回退到 BitBlt
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0),
                               win32con.SRCCOPY)

            # 转换为 numpy 数组
            bmp_info = bitmap.GetInfo()
            bmp_str = bitmap.GetBitmapBits(True)
            img = np.frombuffer(bmp_str, dtype=np.uint8)
            img = img.reshape((bmp_info['bmHeight'], bmp_info['bmWidth'], 4))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # 清理
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

            # 更新统计
            self._update_stats(img)
            return img

        except Exception as e:
            return None

    def _capture_mss(self) -> Optional[np.ndarray]:
        """使用 mss 捕获（回退方案）"""
        try:
            rect = self._target.rect
            monitor = {
                "left": rect[0],
                "top": rect[1],
                "width": rect[2] - rect[0],
                "height": rect[3] - rect[1]
            }
            if monitor["width"] <= 0 or monitor["height"] <= 0:
                return None

            screenshot = self._sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            self._update_stats(img)
            return img
        except Exception:
            return None

    def _update_stats(self, frame: np.ndarray):
        """更新帧统计"""
        self._last_frame = frame
        self._frame_count += 1
        now = time.time()
        dt = now - self._last_time
        if dt >= 1.0:
            self._fps = self._frame_count / dt
            self._frame_count = 0
            self._last_time = now

    # ── 实时画面流 ─────────────────────────────────

    def start_stream(self, callback: Callable[[np.ndarray], None],
                     fps_limit: int = 30,
                     on_error: Optional[Callable[[Exception], None]] = None):
        """
        启动实时画面流
        
        Args:
            callback: 每帧回调
            fps_limit: 帧率限制
            on_error: 错误回调
        """
        stream = ScreenStream(self, fps_limit=fps_limit)
        stream.on_frame = callback
        stream.on_error = on_error
        stream.start()
        return stream

    # ── 区域截图 ───────────────────────────────────

    def capture_region(self, x: int, y: int, w: int, h: int) -> Optional[np.ndarray]:
        """捕获窗口内的指定区域"""
        frame = self.capture()
        if frame is None:
            return None
        frame_h, frame_w = frame.shape[:2]
        x = max(0, min(x, frame_w - 1))
        y = max(0, min(y, frame_h - 1))
        w = min(w, frame_w - x)
        h = min(h, frame_h - y)
        return frame[y:y+h, x:x+w]

    def __del__(self):
        if self._sct:
            self._sct.close()

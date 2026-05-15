"""画面捕获模块"""
from .window_capture import WindowCapture, WindowInfo
from .screen_stream import ScreenStream
from .live_view import LiveView, ViewConfig

__all__ = ["WindowCapture", "WindowInfo", "ScreenStream", "LiveView", "ViewConfig"]

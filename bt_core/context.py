from typing import Callable, Optional, Tuple
import os
import time

from .blackboard import Blackboard


class ExecutionContext:
    """执行上下文

    封装行为树执行过程中的运行时依赖，包括黑板系统、
    截图管理器、输入控制器和OCR管理器等。

    Attributes:
        blackboard: 黑板系统实例
        elapsed_time: 已执行时间（秒）
        tick_count: tick执行次数
        project_root: 项目根目录
    """

    def __init__(self, project_root: str = None):
        self.blackboard = Blackboard()
        self.elapsed_time: float = 0.0
        self.tick_count: int = 0
        self.project_root = project_root or os.getcwd()
        self._is_running = True
        self._is_paused = False
        self._on_node_status: Optional[Callable] = None
        self._screenshot_manager = None
        self._input_controller = None
        self._ocr_manager = None
        self._alarm_player = None
        self._path_resolver = None
        self._stats_collector = None
        self._bound_window: Optional[int] = None
        self._previous_foreground_window: Optional[int] = None
    
    def set_stats_collector(self, collector):
        """设置统计收集器
        
        Args:
            collector: 统计收集器实例
        """
        self._stats_collector = collector
    
    def record_node_stats(self, node_id: str, node_type: str, node_name: str,
                          status: str, duration_ms: float):
        """记录节点执行统计
        
        Args:
            node_id: 节点ID
            node_type: 节点类型
            node_name: 节点名称
            status: 执行状态
            duration_ms: 执行时长（毫秒）
        """
        if self._stats_collector:
            self._stats_collector.record_node(node_id, node_type, node_name, status, duration_ms)
    
    def check_running(self) -> bool:
        if self._is_paused:
            self._wait_if_paused()
        return self._is_running
    
    def _wait_if_paused(self, check_interval: float = 0.1) -> None:
        while self._is_paused and self._is_running:
            time.sleep(check_interval)

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """是否暂停"""
        return self._is_paused

    def notify_node_status(self, node_id: str, status: str) -> None:
        """通知节点状态变化

        Args:
            node_id: 节点ID
            status: 状态字符串
        """
        if self._on_node_status:
            try:
                from bt_utils.ui_dispatcher import UIUpdateDispatcher
                dispatcher = UIUpdateDispatcher()
                dispatcher.dispatch_node_status(node_id, status, self._on_node_status)
            except ImportError:
                self._on_node_status(node_id, status)

    def get_screenshot(self, region: tuple = None):
        """获取屏幕截图

        Args:
            region: 截图区域 (left, top, right, bottom)，窗口相对坐标

        Returns:
            PIL.Image 截图对象
        """
        if self._bound_window:
            from bt_utils.window_capture import WindowCapture
            if region:
                return WindowCapture.capture_window_region(self._bound_window, region)
            return WindowCapture.capture_window(self._bound_window)

        if self._screenshot_manager is None:
            from bt_utils.screenshot import ScreenshotManager
            self._screenshot_manager = ScreenshotManager()

        if region:
            return self._screenshot_manager.get_region_screenshot(region)
        return self._screenshot_manager.get_full_screenshot()

    def execute_key_press(self, key: str, action: str = "press", duration: int = 0) -> None:
        """执行按键操作

        Args:
            key: 按键名称
            action: 动作类型 (press/down/up)
            duration: 按住时长（毫秒）
        """
        if self._input_controller is None:
            from bt_utils.input_controller_factory import InputController
            self._input_controller = InputController()

        self._input_controller.key_press(key, action, duration)

    def execute_mouse_click(self, button: str = "left", position: tuple = None,
                           action: str = "press", duration: int = 0) -> None:
        """执行鼠标点击（全局自动坐标转换）

        Args:
            button: 鼠标按钮 (left/right/middle)
            position: 点击位置 (x, y) - 窗口相对坐标或屏幕绝对坐标
            action: 动作类型 (press/down/up)
            duration: 按住时长（毫秒）
        """
        if self._input_controller is None:
            from bt_utils.input_controller_factory import InputController
            self._input_controller = InputController()

        if position and self._bound_window:
            position = self.convert_to_screen_coords(position)

        self._input_controller.mouse_click(button, position, action, duration)

    def execute_mouse_move(self, position: tuple, relative: bool = False, smooth: bool = False) -> None:
        """执行鼠标移动（全局自动坐标转换）

        Args:
            position: 目标位置 (x, y) - 窗口相对坐标或屏幕绝对坐标
            relative: 是否相对移动
            smooth: 是否平滑移动
        """
        if self._input_controller is None:
            from bt_utils.input_controller_factory import InputController
            self._input_controller = InputController()

        if position and self._bound_window and not relative:
            position = self.convert_to_screen_coords(position)

        self._input_controller.mouse_move(position, relative, smooth=smooth)

    def get_mouse_position(self) -> Optional[Tuple[int, int]]:
        """获取当前鼠标位置

        Returns:
            当前鼠标位置 (x, y)，如果无法获取则返回 None
        """
        if self._input_controller is None:
            from bt_utils.input_controller_factory import InputController
            self._input_controller = InputController()

        return self._input_controller.get_position()

    def execute_mouse_scroll(self, amount: int, position: tuple = None) -> None:
        """执行鼠标滚轮滚动

        Args:
            amount: 滚动量（正数向上，负数向下）
            position: 滚动位置 (x, y)
        """
        if self._input_controller is None:
            from bt_utils.input_controller_factory import InputController
            self._input_controller = InputController()

        self._input_controller.mouse_scroll(amount, position)

    def perform_ocr(self, image, keywords: str, language: str = "eng", 
                    region: Tuple[int, int, int, int] = None) -> tuple:
        """执行OCR识别

        Args:
            image: PIL.Image 图像
            keywords: 关键词（逗号分隔）
            language: OCR语言
            region: 截图区域 (left, top, right, bottom)，用于坐标转换

        Returns:
            (是否找到, 位置, 所有识别文本) 元组
        """
        if self._ocr_manager is None:
            from bt_utils.ocr_manager import OCRManager
            self._ocr_manager = OCRManager()

        return self._ocr_manager.recognize(image, keywords, language, region=region)
    
    def resolve_path(self, relative_path: str) -> str:
        """解析相对路径为绝对路径
        
        Args:
            relative_path: 相对路径（以 ./ 开头）
        
        Returns:
            绝对路径
        """
        if self._path_resolver is None:
            from bt_utils.path_resolver import PathResolver
            self._path_resolver = PathResolver(self.project_root)
        
        if relative_path.startswith("./"):
            return self._path_resolver.to_absolute(relative_path)
        return relative_path

    def bind_window(self, hwnd: int) -> None:
        self._bound_window = hwnd

    def get_bound_window(self) -> Optional[int]:
        return self._bound_window

    def convert_to_screen_coords(self, region: tuple) -> tuple:
        if self._bound_window is None:
            return region
        from bt_utils.coordinate import CoordinateConverter
        if len(region) == 2:
            result = CoordinateConverter.client_to_absolute(region[0], region[1], self._bound_window)
            return result if result else region
        return CoordinateConverter.window_region_to_screen(region, self._bound_window)

    def smart_switch_to_bound_window(self) -> bool:
        if self._bound_window is None:
            return False
        from bt_utils.window_manager import WindowManager
        self._previous_foreground_window = WindowManager.get_foreground_window()
        return WindowManager.set_foreground_window(self._bound_window)

    def smart_restore_foreground_window(self) -> bool:
        if self._previous_foreground_window is None:
            return False
        from bt_utils.window_manager import WindowManager
        result = WindowManager.set_foreground_window(self._previous_foreground_window)
        self._previous_foreground_window = None
        return result

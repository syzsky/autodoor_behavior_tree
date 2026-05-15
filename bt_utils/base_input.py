from abc import ABC, abstractmethod
from typing import Tuple


class BaseInputController(ABC):
    """输入控制器基类

    定义输入控制器的标准接口。
    所有输入控制器实现必须继承此类。
    """

    @abstractmethod
    def key_press(self, key: str, action: str = "press", duration: int = 0) -> None:
        """按键操作

        Args:
            key: 按键名称
            action: 动作类型 (press/down/up)
            duration: 按住时长（毫秒）
        """
        pass

    @abstractmethod
    def key_down(self, key: str) -> None:
        """按下按键

        Args:
            key: 按键名称
        """
        pass

    @abstractmethod
    def key_up(self, key: str) -> None:
        """释放按键

        Args:
            key: 按键名称
        """
        pass

    @abstractmethod
    def mouse_click(self, button: str = "left", position: Tuple[int, int] = None,
                   action: str = "press", duration: int = 0) -> None:
        """鼠标点击

        Args:
            button: 鼠标按钮 (left/right/middle)
            position: 点击位置 (x, y)
            action: 动作类型 (press/down/up)
            duration: 按住时长（毫秒）
        """
        pass

    @abstractmethod
    def mouse_down(self, button: str = "left") -> None:
        """按下鼠标

        Args:
            button: 鼠标按钮
        """
        pass

    @abstractmethod
    def mouse_up(self, button: str = "left") -> None:
        """释放鼠标

        Args:
            button: 鼠标按钮
        """
        pass

    @abstractmethod
    def mouse_move(self, position: Tuple[int, int], relative: bool = False) -> None:
        """移动鼠标

        Args:
            position: 目标位置 (x, y)
            relative: 是否相对移动
        """
        pass

    @abstractmethod
    def mouse_scroll(self, amount: int, position: Tuple[int, int] = None) -> None:
        """鼠标滚轮

        Args:
            amount: 滚动量
            position: 滚动位置
        """
        pass

    def smooth_move(self, position: Tuple[int, int], relative: bool = False,
                    duration: float = 0.3) -> None:
        """平滑移动鼠标（默认实现，子类可覆盖）

        Args:
            position: 目标位置 (x, y)
            relative: 是否相对移动
            duration: 移动时长（秒）
        """
        self.mouse_move(position, relative)

    def move_to(self, x: int, y: int, smooth: bool = False, duration: float = 0.3) -> None:
        """移动鼠标到指定位置

        Args:
            x: X坐标
            y: Y坐标
            smooth: 是否平滑移动
            duration: 平滑移动时长
        """
        if smooth:
            self.smooth_move((x, y), relative=False, duration=duration)
        else:
            self.mouse_move((x, y), relative=False)

    def get_position(self) -> Tuple[int, int]:
        """获取当前鼠标位置

        Returns:
            当前鼠标位置 (x, y)
        """
        try:
            import pyautogui
            return pyautogui.position()
        except Exception:
            return (0, 0)

    @classmethod
    def is_simulating(cls) -> bool:
        """检查当前是否正在执行模拟操作

        Returns:
            是否正在执行模拟操作
        """
        return False

    @classmethod
    def release_all(cls) -> None:
        """释放所有按下的按键和鼠标按钮"""
        pass

    def get_name(self) -> str:
        """获取控制器名称

        Returns:
            控制器名称
        """
        return self.__class__.__name__

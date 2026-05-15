"""
输入控制器
========
封装键盘鼠标操作，适配不同输入方式（win32api / DD驱动）
"""

import time
from typing import Optional


class InputController:
    """
    输入控制器
    
    用法：
        input_ctrl = InputController(mode="win32")
        input_ctrl.click(500, 300)
        input_ctrl.press_key("f5")
        input_ctrl.type_text("100")
    """

    def __init__(self, mode: str = "win32"):
        self._mode = mode
        self._backend = None
        self._init_backend()

    def _init_backend(self):
        """初始化后端"""
        if self._mode == "win32":
            try:
                import win32api
                import win32con
                self._backend = "win32"
                self._win32api = win32api
                self._win32con = win32con
            except ImportError:
                self._backend = "fallback"
        elif self._mode == "dd":
            try:
                from bt_utils.dd_input import DDInput
                self._backend = "dd"
                self._dd = DDInput()
            except ImportError:
                self._backend = "fallback"
        else:
            self._backend = "fallback"

    def click(self, x: int, y: int, button: str = "left"):
        """鼠标点击"""
        if self._backend == "win32":
            self._win32api.SetCursorPos((x, y))
            if button == "left":
                self._win32api.mouse_event(self._win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                self._win32api.mouse_event(self._win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            else:
                self._win32api.mouse_event(self._win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                self._win32api.mouse_event(self._win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        elif self._backend == "dd":
            self._dd.move(x, y)
            time.sleep(0.05)
            self._dd.left_click()
        else:
            # fallback - just log
            pass

    def right_click(self, x: int, y: int):
        """右键点击"""
        self.click(x, y, button="right")

    def press_key(self, key: str):
        """按键"""
        key_map = {
            "f5": (0x74, "VK_F5"),
            "f6": (0x75, "VK_F6"),
            "enter": (0x0D, "VK_RETURN"),
            "escape": (0x1B, "VK_ESCAPE"),
            "backspace": (0x08, "VK_BACK"),
            "space": (0x20, "VK_SPACE"),
            "b": (0x42, "VK_B"),
            "v": (0x56, "VK_V"),
        }

        key_lower = key.lower()
        if key_lower in key_map:
            vk_code = key_map[key_lower][0]
        elif len(key_lower) == 1:
            vk_code = ord(key_lower.upper())
        else:
            # 多字符键名回退：尝试取首字符
            vk_code = ord(key_lower[0].upper()) if key_lower else 0

        if self._backend == "win32":
            self._win32api.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.05)
            self._win32api.keybd_event(vk_code, 0, self._win32con.KEYEVENTF_KEYUP, 0)
        elif self._backend == "dd":
            self._dd.key_press(key_lower)
        else:
            pass

    def scroll(self, clicks: int):
        """滚轮"""
        if self._backend == "win32":
            self._win32api.mouse_event(self._win32con.MOUSEEVENTF_WHEEL, 0, 0, clicks * 120, 0)

    def type_text(self, text: str):
        """输入文本"""
        for char in text:
            if self._backend == "win32":
                vk = ord(char.upper())
                shift_needed = char.isupper() or char in "~!@#$%^&*()_+{}|:\"<>?"
                if shift_needed:
                    self._win32api.keybd_event(0x10, 0, 0, 0)  # Shift down
                self._win32api.keybd_event(vk, 0, 0, 0)
                time.sleep(0.02)
                self._win32api.keybd_event(vk, 0, self._win32con.KEYEVENTF_KEYUP, 0)
                if shift_needed:
                    self._win32api.keybd_event(0x10, 0, self._win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.02)
            time.sleep(0.05)
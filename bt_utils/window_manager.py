import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, List

user32 = ctypes.windll.user32


class WindowManager:
    @staticmethod
    def enum_all_windows() -> List[Tuple[int, str]]:
        results = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_windows_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    if title:
                        results.append((hwnd, title))
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return results

    @staticmethod
    def find_window_by_title(keyword: str) -> Optional[int]:
        windows = WindowManager.enum_all_windows()
        for hwnd, title in windows:
            if keyword.lower() in title.lower():
                return hwnd
        return None

    @staticmethod
    def find_window_by_pid(pid: int) -> Optional[int]:
        """通过进程ID查找窗口
        
        Args:
            pid: 进程ID
            
        Returns:
            Optional[int]: 窗口句柄，未找到返回 None
        """
        results = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_windows_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                if window_pid.value == pid:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buffer, length + 1)
                        if buffer.value:
                            results.append(hwnd)
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        
        if results:
            return results[0]
        return None

    @staticmethod
    def get_window_pid(hwnd: int) -> Optional[int]:
        """获取窗口的进程ID
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            Optional[int]: 进程ID，获取失败返回 None
        """
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value if pid.value else None
        except Exception:
            return None

    @staticmethod
    def find_window_smart(pid: Optional[int], title_keyword: str) -> Tuple[Optional[int], str]:
        """智能查找窗口：优先PID，其次关键字
        
        Args:
            pid: 进程ID（可选）
            title_keyword: 窗口标题关键字
            
        Returns:
            Tuple[Optional[int], str]: (窗口句柄, 查找方式说明)
            查找方式说明: "pid" / "title" / "not_found"
        """
        if pid:
            hwnd = WindowManager.find_window_by_pid(pid)
            if hwnd:
                return hwnd, "pid"
        
        if title_keyword:
            hwnd = WindowManager.find_window_by_title(title_keyword)
            if hwnd:
                return hwnd, "title"
        
        return None, "not_found"

    @staticmethod
    def get_window_title(hwnd: int) -> str:
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                return buffer.value
            return ""
        except Exception:
            return ""

    @staticmethod
    def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
        return None

    @staticmethod
    def is_foreground_window(hwnd: int) -> bool:
        try:
            return user32.GetForegroundWindow() == hwnd
        except Exception:
            return False

    @staticmethod
    def get_foreground_window() -> Optional[int]:
        try:
            return user32.GetForegroundWindow()
        except Exception:
            return None

    @staticmethod
    def set_foreground_window(hwnd: int) -> bool:
        return WindowManager.switch_to_window(hwnd)

    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        try:
            return bool(user32.IsWindow(hwnd))
        except Exception:
            return False

    @staticmethod
    def save_foreground_window() -> int:
        return user32.GetForegroundWindow()

    @staticmethod
    def switch_to_window(hwnd: int) -> bool:
        try:
            SW_RESTORE = 9
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001

            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)

            user32.SetWindowPos(
                hwnd, HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE
            )

            user32.SetForegroundWindow(hwnd)

            user32.SetWindowPos(
                hwnd, HWND_NOTOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE
            )

            return True
        except Exception:
            return False

    @staticmethod
    def restore_window(saved_hwnd: int) -> bool:
        try:
            VK_MENU = 0x12
            VK_TAB = 0x09
            KEYEVENTF_KEYUP = 0x0002

            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_TAB, 0, 0, 0)
            user32.keybd_event(VK_TAB, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            if WindowManager.is_window_valid(saved_hwnd):
                user32.SetForegroundWindow(saved_hwnd)

            return True
        except Exception:
            return False

# tests/conftest.py
"""pytest 共享 fixtures"""
import asyncio
import os
import sys
import pytest
from unittest.mock import MagicMock

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Mock customtkinter — 需要返回真正的 class 类型（而非 MagicMock 实例），
# 否则 `class Foo(ctk.CTkFrame)` 会因 issubclass() 失败而报错。
# ---------------------------------------------------------------------------
class _MockCTkWidget:
    """所有 CTk 控件的 mock 基类，提供常用方法使其可被实例化。"""

    def __init__(self, *args, **kwargs):
        self._children = []

    def configure(self, *args, **kwargs):
        pass

    def cget(self, *args, **kwargs):
        return ""

    def pack(self, *args, **kwargs):
        pass

    def pack_forget(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):
        pass

    def grid_forget(self, *args, **kwargs):
        pass

    def place(self, *args, **kwargs):
        pass

    def winfo_children(self):
        return self._children

    def winfo_width(self):
        return 800

    def winfo_height(self):
        return 600

    def destroy(self):
        pass

    def after(self, ms, func=None, *args):
        if func:
            func(*args)

    def after_cancel(self, *args):
        pass

    def bind(self, *args, **kwargs):
        pass

    def unbind(self, *args, **kwargs):
        pass

    def update(self):
        pass

    def update_idletasks(self):
        pass


class _MockCTkModule:
    """Mock customtkinter 模块：动态生成可继承的类。"""

    set_appearance_mode = staticmethod(lambda *a, **k: None)
    set_default_color_theme = staticmethod(lambda *a, **k: None)
    CTk = type("CTk", (_MockCTkWidget,), {})

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        # 动态创建一个可继承的真实类
        return type(name, (_MockCTkWidget,), {})


# ---------------------------------------------------------------------------
# Mock tkinter — 同样需要返回真正的 class 类型
# ---------------------------------------------------------------------------
class _MockTkWidget:
    """tkinter 控件 mock 基类。"""

    def __init__(self, *args, **kwargs):
        pass

    def create_rectangle(self, *args, **kwargs):
        return 0

    def create_oval(self, *args, **kwargs):
        return 0

    def create_line(self, *args, **kwargs):
        return 0

    def create_text(self, *args, **kwargs):
        return 0

    def create_image(self, *args, **kwargs):
        return 0

    def create_window(self, *args, **kwargs):
        return 0

    def create_polygon(self, *args, **kwargs):
        return 0

    def delete(self, *args):
        pass

    def coords(self, *args):
        return (0, 0)

    def itemconfig(self, *args, **kwargs):
        pass

    def addtag(self, *args, **kwargs):
        pass

    def dtag(self, *args, **kwargs):
        pass

    def find_all(self):
        return []

    def find_withtag(self, *args):
        return []

    def gettags(self, *args):
        return ()

    def move(self, *args):
        pass

    def scale(self, *args):
        pass

    def pack(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):
        pass

    def bind(self, *args, **kwargs):
        pass

    def configure(self, *args, **kwargs):
        pass

    def winfo_width(self):
        return 800

    def winfo_height(self):
        return 600

    def winfo_children(self):
        return []

    def destroy(self):
        pass

    def update(self):
        pass

    def update_idletasks(self):
        pass


class _MockTkModule:
    """Mock tkinter 模块。"""

    class Canvas(_MockTkWidget):
        pass

    class Frame(_MockTkWidget):
        pass

    class Label(_MockTkWidget):
        pass

    class Button(_MockTkWidget):
        pass

    class Entry(_MockTkWidget):
        pass

    class StringVar:
        def __init__(self, *a, **k):
            self._value = ""

        def get(self):
            return self._value

        def set(self, v):
            self._value = v

        def trace(self, *a, **k):
            pass

    class IntVar:
        def __init__(self, *a, **k):
            self._value = 0

        def get(self):
            return self._value

        def set(self, v):
            self._value = v

        def trace(self, *a, **k):
            pass

    class BooleanVar:
        def __init__(self, *a, **k):
            self._value = False

        def get(self):
            return self._value

        def set(self, v):
            self._value = v

        def trace(self, *a, **k):
            pass

    class DoubleVar:
        def __init__(self, *a, **k):
            self._value = 0.0

        def get(self):
            return self._value

        def set(self, v):
            self._value = v

        def trace(self, *a, **k):
            pass

    BOTH = "both"
    X = "x"
    Y = "y"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    NONE = "none"
    NORMAL = "normal"
    DISABLED = "disabled"
    ACTIVE = "active"
    END = "end"
    INSERT = "insert"
    SEL = "sel"
    SEL_FIRST = "sel.first"
    SEL_LAST = "sel.last"
    N = "n"
    S = "s"
    E = "e"
    W = "w"
    CENTER = "center"
    NW = "nw"
    NE = "ne"
    SW = "sw"
    SE = "se"

    @staticmethod
    def Tk():
        return _MockTkWidget()

    def __getattr__(self, name):
        """未明确模拟的子模块（messagebox, filedialog 等）返回 MagicMock。"""
        if name.startswith("__"):
            raise AttributeError(name)
        return MagicMock()


class _MockTtkModule:
    """Mock tkinter.ttk 模块。"""

    class Frame(_MockTkWidget):
        pass

    class Label(_MockTkWidget):
        pass

    class Button(_MockTkWidget):
        pass

    class Entry(_MockTkWidget):
        pass

    class Combobox(_MockTkWidget):
        def __getitem__(self, key):
            return ""

        def __setitem__(self, key, value):
            pass

    class Notebook(_MockTkWidget):
        def add(self, *a, **k):
            pass

        def select(self, *a):
            return 0

        def tab(self, *a, **k):
            return {}

    class Style:
        def configure(self, *a, **k):
            pass

        def theme_use(self, *a):
            return "default"

        def theme_create(self, *a, **k):
            pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return MagicMock()


# ---------------------------------------------------------------------------
# 安装 mocks
# ---------------------------------------------------------------------------
_MOCK_MODULES = {
    "tkinter": _MockTkModule(),
    "tkinter.ttk": _MockTtkModule(),
    "tkinter.filedialog": MagicMock(),
    "tkinter.messagebox": MagicMock(),
    "tkinter.colorchooser": MagicMock(),
    "tkinter.font": MagicMock(),
    "tkinter.simpledialog": MagicMock(),
    "customtkinter": _MockCTkModule(),
    "rapidocr": MagicMock(),
    "PIL": MagicMock(),
    "PIL.Image": MagicMock(),
    "PIL.ImageTk": MagicMock(),
    "PIL.ImageDraw": MagicMock(),
    "PIL.ImageFont": MagicMock(),
    "pynput": MagicMock(),
    "pynput.mouse": MagicMock(),
    "pynput.keyboard": MagicMock(),
    "screeninfo": MagicMock(),
    "mss": MagicMock(),
    "pygetwindow": MagicMock(),
    "win32gui": MagicMock(),
    "win32con": MagicMock(),
    "win32api": MagicMock(),
    "win32process": MagicMock(),
    "psutil": MagicMock(),
    "imagehash": MagicMock(),
}

for _mod_name, _mock_obj in _MOCK_MODULES.items():
    if _mod_name not in sys.modules:
        try:
            __import__(_mod_name)
        except ImportError:
            sys.modules[_mod_name] = _mock_obj


@pytest.fixture
def message_bus():
    """提供隔离的 MessageBus 实例，自动清理单例和 event loop"""
    from bt_bus.message_bus import MessageBus

    MessageBus.reset_instance()
    bus = MessageBus()
    bus.start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bus.set_event_loop(loop)

    yield bus

    # 清理
    try:
        bus.stop()
    except Exception:
        pass
    try:
        loop.close()
    except Exception:
        pass
    asyncio.set_event_loop(None)
    MessageBus.reset_instance()

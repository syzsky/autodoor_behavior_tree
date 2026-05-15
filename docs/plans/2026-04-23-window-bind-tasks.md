# 窗口绑定功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 AutoDoor 行为树系统实现窗口绑定功能，支持全局窗口绑定、下拉框选择窗口、相对坐标自动转换、后台监控和前台操作。

**Architecture:** 采用 ExecutionContext 集中处理窗口管理和坐标转换的方式实现。只要开始节点绑定了窗口，所有涉及坐标的操作都自动进行相对坐标和绝对坐标的转换。节点无需关心坐标转换，全部由 ExecutionContext 自动处理。

**Tech Stack:** Python 3.10+, pywin32 (win32gui, win32ui, win32con, win32api), ctypes, PIL

---

## Task 1: 创建 WindowManager 工具类

**Files:**
- Create: `bt_utils/window_manager.py`

**Step 1: 创建 WindowManager 类框架**

```python
"""
窗口管理器工具类

提供窗口枚举、切换、恢复等功能
"""
import win32gui
import win32con
import win32api
from typing import Optional, Tuple, List


class WindowManager:
    """窗口管理器
    
    提供窗口枚举、切换、恢复等功能
    移植自 autodoor/utils/quick_switch.py
    """
    
    @staticmethod
    def enum_all_windows() -> List[Tuple[int, str]]:
        """枚举系统中所有可见窗口
        
        Returns:
            List[Tuple[int, str]]: [(hwnd, title), ...] 窗口句柄和标题列表
        """
        results = []
        
        def enum_windows_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    results.append((hwnd, title))
            return True
        
        win32gui.EnumWindows(enum_windows_callback, None)
        return results
    
    @staticmethod
    def find_window_by_title(keyword: str) -> Optional[int]:
        """通过标题关键字查找窗口
        
        Args:
            keyword: 窗口标题关键字
        
        Returns:
            窗口句柄，如果未找到返回 None
        """
        windows = WindowManager.enum_all_windows()
        for hwnd, title in windows:
            if keyword.lower() in title.lower():
                return hwnd
        return None
    
    @staticmethod
    def get_window_title(hwnd: int) -> str:
        """获取窗口标题
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            窗口标题
        """
        try:
            return win32gui.GetWindowText(hwnd)
        except Exception:
            return ""
    
    @staticmethod
    def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口矩形区域
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            (left, top, right, bottom) 矩形，如果失败返回 None
        """
        try:
            return win32gui.GetWindowRect(hwnd)
        except Exception:
            return None
    
    @staticmethod
    def is_foreground_window(hwnd: int) -> bool:
        """检查窗口是否是前台窗口
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            是否是前台窗口
        """
        try:
            return win32gui.GetForegroundWindow() == hwnd
        except Exception:
            return False
    
    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        """检查窗口是否有效
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            窗口是否有效
        """
        try:
            return bool(win32gui.IsWindow(hwnd))
        except Exception:
            return False
    
    @staticmethod
    def save_foreground_window() -> int:
        """保存当前前台窗口
        
        Returns:
            当前前台窗口句柄
        """
        return win32gui.GetForegroundWindow()
    
    @staticmethod
    def switch_to_window(hwnd: int) -> bool:
        """切换到目标窗口
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            是否成功
        """
        try:
            # 如果窗口最小化，恢复窗口
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            # 设置为最顶层
            win32gui.SetWindowPos(
                hwnd, 
                win32con.HWND_TOPMOST, 
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            
            # 激活窗口
            win32gui.SetForegroundWindow(hwnd)
            
            # 取消最顶层状态
            win32gui.SetWindowPos(
                hwnd, 
                win32con.HWND_NOTOPMOST, 
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def restore_window(saved_hwnd: int) -> bool:
        """恢复原窗口
        
        Args:
            saved_hwnd: 保存的窗口句柄
        
        Returns:
            是否成功
        """
        try:
            # 使用 Alt+Tab 模拟用户操作
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
            win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            # 激活原窗口
            if WindowManager.is_window_valid(saved_hwnd):
                win32gui.SetForegroundWindow(saved_hwnd)
            
            return True
        except Exception:
            return False
```

**Step 2: 提交 WindowManager 工具类**

```bash
git add bt_utils/window_manager.py
git commit -m "feat: add WindowManager utility class for window management"
```

---

## Task 2: 创建 WindowCoordinate 工具类

**Files:**
- Create: `bt_utils/window_coordinate.py`

**Step 1: 创建 WindowCoordinate 类**

```python
"""
窗口坐标转换工具类

提供屏幕坐标和窗口相对坐标之间的转换功能
"""
import win32gui
from typing import Tuple


class WindowCoordinate:
    """窗口坐标系统工具类
    
    移植自 autodoor/utils/coordinate.py
    """
    
    @staticmethod
    def screen_to_window(screen_x: int, screen_y: int, hwnd: int) -> Tuple[int, int]:
        """屏幕绝对坐标转窗口相对坐标
        
        Args:
            screen_x: 屏幕X坐标
            screen_y: 屏幕Y坐标
            hwnd: 窗口句柄
        
        Returns:
            (window_x, window_y) 窗口相对坐标
        """
        try:
            rect = win32gui.GetWindowRect(hwnd)
            return (screen_x - rect[0], screen_y - rect[1])
        except Exception:
            return (0, 0)
    
    @staticmethod
    def window_to_screen(rel_x: int, rel_y: int, hwnd: int) -> Tuple[int, int]:
        """窗口相对坐标转屏幕绝对坐标
        
        Args:
            rel_x: 窗口相对X坐标
            rel_y: 窗口相对Y坐标
            hwnd: 窗口句柄
        
        Returns:
            (screen_x, screen_y) 屏幕绝对坐标
        """
        try:
            rect = win32gui.GetWindowRect(hwnd)
            return (rel_x + rect[0], rel_y + rect[1])
        except Exception:
            return (0, 0)
    
    @staticmethod
    def screen_region_to_window(screen_region: tuple, hwnd: int) -> tuple:
        """屏幕绝对区域转窗口相对区域
        
        Args:
            screen_region: (x1, y1, x2, y2) 屏幕绝对区域
            hwnd: 窗口句柄
        
        Returns:
            (x1, y1, x2, y2) 窗口相对区域
        """
        try:
            rect = win32gui.GetWindowRect(hwnd)
            return (
                screen_region[0] - rect[0],
                screen_region[1] - rect[1],
                screen_region[2] - rect[0],
                screen_region[3] - rect[1]
            )
        except Exception:
            return (0, 0, 0, 0)
    
    @staticmethod
    def window_region_to_screen(window_region: tuple, hwnd: int) -> tuple:
        """窗口相对区域转屏幕绝对区域
        
        Args:
            window_region: (x1, y1, x2, y2) 窗口相对区域
            hwnd: 窗口句柄
        
        Returns:
            (x1, y1, x2, y2) 屏幕绝对区域
        """
        try:
            rect = win32gui.GetWindowRect(hwnd)
            return (
                window_region[0] + rect[0],
                window_region[1] + rect[1],
                window_region[2] + rect[0],
                window_region[3] + rect[1]
            )
        except Exception:
            return (0, 0, 0, 0)
```

**Step 2: 提交 WindowCoordinate 工具类**

```bash
git add bt_utils/window_coordinate.py
git commit -m "feat: add WindowCoordinate utility class for coordinate conversion"
```

---

## Task 3: 创建 WindowCapture 工具类

**Files:**
- Create: `bt_utils/window_capture.py`

**Step 1: 创建 WindowCapture 类**

```python
"""
窗口截图工具类

提供后台截图功能（使用 PrintWindow API）
"""
import win32gui
import win32ui
import win32con
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple
from PIL import Image


class WindowCapture:
    """窗口截图工具类
    
    移植自 autodoor/utils/window_capture.py
    使用 PrintWindow API 实现后台截图
    """
    
    @staticmethod
    def capture_window(hwnd: int) -> Optional[Image.Image]:
        """后台截图 - 使用 PrintWindow API
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            PIL.Image: 截图图像，失败返回 None
        """
        try:
            # 获取窗口客户区大小
            rect = win32gui.GetClientRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            if width <= 0 or height <= 0:
                return None
            
            # 创建设备上下文
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            
            # 创建位图
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)
            
            # 使用 PrintWindow API 截图
            # PW_CLIENTONLY = 2，只截取客户区
            result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
            
            if result == 0:
                # PrintWindow 失败，清理资源
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)
                return None
            
            # 转换为 PIL.Image
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )
            
            # 清理资源
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)
            
            return img
            
        except Exception:
            return None
    
    @staticmethod
    def capture_window_region(hwnd: int, region: Tuple[int, int, int, int]) -> Optional[Image.Image]:
        """后台截图指定区域
        
        Args:
            hwnd: 窗口句柄
            region: (x1, y1, x2, y2) 区域坐标（窗口相对坐标）
        
        Returns:
            PIL.Image: 区域截图，失败返回 None
        """
        full_image = WindowCapture.capture_window(hwnd)
        if full_image is None:
            return None
        
        # 裁剪区域
        try:
            return full_image.crop((region[0], region[1], region[2], region[3]))
        except Exception:
            return None
```

**Step 2: 提交 WindowCapture 工具类**

```bash
git add bt_utils/window_capture.py
git commit -m "feat: add WindowCapture utility class for background screenshot"
```

---

## Task 4: 扩展 ExecutionContext

**Files:**
- Modify: `bt_core/context.py`

**Step 1: 在 ExecutionContext 中添加窗口管理属性**

在 `__init__` 方法中添加：

```python
# 窗口管理属性
self._bound_window: Optional[int] = None
self._saved_foreground_window: Optional[int] = None
self._window_manager = None
self._window_capture = None
self._window_coordinate = None
```

**Step 2: 添加窗口管理方法**

```python
def bind_window(self, hwnd: int) -> None:
    """绑定窗口"""
    self._bound_window = hwnd

def get_bound_window(self) -> Optional[int]:
    """获取绑定的窗口句柄"""
    return self._bound_window
```

**Step 3: 添加后台截图方法**

```python
def capture_bound_window(self, region: tuple = None) -> Optional[Image.Image]:
    """后台截图绑定的窗口"""
    if self._bound_window is None:
        return None
    
    if self._window_capture is None:
        from bt_utils.window_capture import WindowCapture
        self._window_capture = WindowCapture()
    
    if region:
        return self._window_capture.capture_window_region(self._bound_window, region)
    return self._window_capture.capture_window(self._bound_window)
```

**Step 4: 添加坐标转换方法**

```python
def convert_to_screen_coords(self, region: tuple) -> tuple:
    """将窗口相对坐标转换为屏幕绝对坐标"""
    if self._bound_window is None:
        return region
    
    if self._window_coordinate is None:
        from bt_utils.window_coordinate import WindowCoordinate
        self._window_coordinate = WindowCoordinate()
    
    return self._window_coordinate.window_region_to_screen(region, self._bound_window)

def convert_to_window_coords(self, region: tuple) -> tuple:
    """将屏幕绝对坐标转换为窗口相对坐标"""
    if self._bound_window is None:
        return region
    
    if self._window_coordinate is None:
        from bt_utils.window_coordinate import WindowCoordinate
        self._window_coordinate = WindowCoordinate()
    
    return self._window_coordinate.screen_region_to_window(region, self._bound_window)
```

**Step 5: 添加智能窗口切换方法**

```python
def smart_switch_to_bound_window(self) -> bool:
    """智能切换到绑定的窗口"""
    if self._window_manager is None:
        from bt_utils.window_manager import WindowManager
        self._window_manager = WindowManager()
    
    if self._bound_window is None:
        return False
    
    # 检查目标窗口是否已经是前台窗口
    if self._window_manager.is_foreground_window(self._bound_window):
        return True
    
    # 保存当前前台窗口
    self._saved_foreground_window = self._window_manager.save_foreground_window()
    
    # 切换到目标窗口
    return self._window_manager.switch_to_window(self._bound_window)

def smart_restore_foreground_window(self) -> bool:
    """智能恢复原窗口"""
    if self._window_manager is None or self._saved_foreground_window is None:
        return False
    
    # 如果原窗口就是目标窗口，无需恢复
    if self._saved_foreground_window == self._bound_window:
        return True
    
    # 恢复原窗口
    return self._window_manager.restore_window(self._saved_foreground_window)
```

**Step 6: 修改 execute_mouse_click 方法**

在现有方法中添加坐标转换逻辑：

```python
def execute_mouse_click(self, button: str, position: tuple, action: str, duration: int):
    """执行鼠标点击（全局自动坐标转换）"""
    # 全局自动转换：如果绑定了窗口，将相对坐标转换为绝对坐标
    if self._bound_window and position:
        position = self.convert_to_screen_coords(position)
    
    # 执行点击（原有逻辑）
    self._input_controller.click(position[0], position[1], button)
```

**Step 7: 修改 execute_mouse_move 方法**

在现有方法中添加坐标转换逻辑：

```python
def execute_mouse_move(self, position: tuple, smooth: bool = False):
    """执行鼠标移动（全局自动坐标转换）"""
    # 全局自动转换：如果绑定了窗口，将相对坐标转换为绝对坐标
    if self._bound_window and position:
        position = self.convert_to_screen_coords(position)
    
    # 执行移动（原有逻辑）
    self._input_controller.move_to(position[0], position[1], smooth)
```

**Step 8: 修改 get_screenshot 方法**

在现有方法中添加后台截图逻辑：

```python
def get_screenshot(self, region: tuple = None):
    """获取截图（全局自动坐标转换）"""
    # 全局自动转换：如果绑定了窗口，使用后台截图
    if self._bound_window and region:
        # 使用后台截图（region 是窗口相对坐标）
        return self.capture_bound_window(region)
    
    # 使用屏幕截图（原有逻辑）
    return self._screenshot_manager.capture_region(region)
```

**Step 9: 提交 ExecutionContext 扩展**

```bash
git add bt_core/context.py
git commit -m "feat: extend ExecutionContext with window management and auto coordinate conversion"
```

---

## Task 5: 扩展 StartNode

**Files:**
- Modify: `bt_core/nodes.py`

**Step 1: 在 StartNode 中添加窗口绑定属性**

在 `__init__` 方法中添加：

```python
# 窗口绑定属性
self.bind_window = self.config.get_bool("bind_window", False)
self.window_title = self.config.get("window_title", "")
```

**Step 2: 修改 tick 方法**

```python
def tick(self, context: ExecutionContext) -> NodeStatus:
    # 绑定窗口到上下文
    if self.bind_window and self.window_title:
        self._bind_window_to_context(context)
    
    # 执行子节点（原有逻辑）
    return super().tick(context)
```

**Step 3: 添加 _bind_window_to_context 方法**

```python
def _bind_window_to_context(self, context: ExecutionContext) -> None:
    """绑定窗口到上下文"""
    from bt_utils.window_manager import WindowManager
    
    # 通过标题查找窗口
    hwnd = WindowManager.find_window_by_title(self.window_title)
    
    if hwnd:
        context.bind_window(hwnd)
```

**Step 4: 修改 to_dict 方法**

```python
def to_dict(self) -> Dict[str, Any]:
    data = super().to_dict()
    data["config"]["bind_window"] = self.bind_window
    data["config"]["window_title"] = self.window_title
    return data
```

**Step 5: 提交 StartNode 扩展**

```bash
git add bt_core/nodes.py
git commit -m "feat: extend StartNode with window binding properties"
```

---

## Task 6: 扩展 ActionNode

**Files:**
- Modify: `bt_core/nodes.py`

**Step 1: 修改 ActionNode 的 tick 方法**

```python
def tick(self, context: ExecutionContext) -> NodeStatus:
    # 检查是否绑定了窗口
    bound_window = context.get_bound_window()
    
    if bound_window:
        # 智能切换到目标窗口
        context.smart_switch_to_bound_window()
        
        try:
            # 执行动作
            # 注意：坐标转换由 ExecutionContext 全局自动处理
            status = self._execute_action(context)
        finally:
            # 智能恢复原窗口
            context.smart_restore_foreground_window()
        
        return status
    
    # 直接执行动作（原有逻辑）
    return self._execute_action(context)
```

**Step 2: 提交 ActionNode 扩展**

```bash
git add bt_core/nodes.py
git commit -m "feat: extend ActionNode with smart window switching"
```

---

## Task 7: 扩展属性面板

**Files:**
- Modify: `bt_gui/bt_editor/property.py`

**Step 1: 添加 WindowSelectField 类**

```python
class WindowSelectField:
    """窗口选择字段（下拉框）"""
    
    def __init__(self, master, label: str, key: str, value: str = "", on_change=None):
        self.master = master
        self.label = label
        self.key = key
        self.on_change = on_change
        self._window_titles = []
        self._window_hwnds = {}
        
        self._create_widget()
        self.set_value(value)
    
    def _create_widget(self):
        # 创建框架
        self.frame = customtkinter.CTkFrame(self.master)
        self.frame.pack(fill="x", padx=5, pady=2)
        
        # 标签
        label = customtkinter.CTkLabel(self.frame, text=self.label, width=80, anchor="w")
        label.pack(side="left", padx=5)
        
        # 下拉框
        self._refresh_window_list()
        self.combobox = customtkinter.CTkComboBox(
            self.frame, 
            values=self._window_titles,
            width=200,
            command=self._on_select
        )
        self.combobox.pack(side="left", padx=5, fill="x", expand=True)
        
        # 刷新按钮
        refresh_btn = customtkinter.CTkButton(
            self.frame, text="刷新", width=50,
            command=self._refresh_window_list
        )
        refresh_btn.pack(side="left", padx=5)
    
    def _refresh_window_list(self):
        """刷新窗口列表"""
        from bt_utils.window_manager import WindowManager
        windows = WindowManager.enum_all_windows()
        self._window_titles = [title for hwnd, title in windows]
        self._window_hwnds = {title: hwnd for hwnd, title in windows}
        
        if hasattr(self, 'combobox'):
            self.combobox.configure(values=self._window_titles)
    
    def _on_select(self, choice):
        """选择窗口"""
        if self.on_change:
            self.on_change(self.key, choice)
    
    def get_value(self) -> str:
        return self.combobox.get()
    
    def set_value(self, value: str):
        if value and hasattr(self, 'combobox'):
            self.combobox.set(value)
```

**Step 2: 修改 RegionField 的 _select_region 方法**

在现有的 `_select_region` 方法中添加坐标转换逻辑：

```python
def _select_region(self):
    """选择区域"""
    # 获取当前绑定的窗口
    bound_window = self._get_bound_window()
    
    # 显示放大镜并等待用户选择区域
    region = self._do_select_region()  # 返回屏幕绝对坐标
    
    if region:
        # 如果绑定了窗口，转换为窗口相对坐标
        if bound_window:
            from bt_utils.window_coordinate import WindowCoordinate
            region = WindowCoordinate.screen_region_to_window(region, bound_window)
        
        # 更新显示
        self.set_value(region)
        if self.on_change:
            self.on_change(self.key, region)

def _get_bound_window(self) -> Optional[int]:
    """获取当前绑定的窗口"""
    # 从编辑器获取开始节点的窗口绑定
    editor = self._get_editor()
    if editor:
        start_node = editor.get_start_node()
        if start_node and start_node.bind_window and start_node.window_title:
            from bt_utils.window_manager import WindowManager
            return WindowManager.find_window_by_title(start_node.window_title)
    return None
```

**Step 3: 提交属性面板扩展**

```bash
git add bt_gui/bt_editor/property.py
git commit -m "feat: extend property panel with window selector and relative coordinate capture"
```

---

## Task 8: 添加依赖项

**Files:**
- Modify: `requirements.txt`

**Step 1: 添加 pywin32 依赖**

```
pywin32>=305
```

**Step 2: 提交依赖更新**

```bash
git add requirements.txt
git commit -m "feat: add pywin32 dependency for window management"
```

---

## Task 9: 更新节点面板配置

**Files:**
- Modify: `bt_gui/bt_editor/constants.py`

**Step 1: 在 NODE_TYPES 中添加窗口绑定相关配置**

确保 StartNode 的配置包含窗口绑定属性：

```python
NODE_TYPES = {
    # ... 现有节点 ...
    
    "StartNode": {
        "name": "开始",
        "category": "composite",
        "color": "#4CAF50",
        "description": "行为树的开始节点",
        "properties": [
            # ... 现有属性 ...
            {"key": "bind_window", "label": "绑定窗口", "type": "bool", "default": False},
            {"key": "window_title", "label": "窗口标题", "type": "window_select", "default": ""},
        ]
    },
}
```

**Step 2: 提交节点面板配置**

```bash
git add bt_gui/bt_editor/constants.py
git commit -m "feat: add window binding properties to StartNode configuration"
```

---

## Task 10: 最终测试与提交

**Step 1: 运行测试**

```bash
python -m pytest tests/ -v
```

**Step 2: 检查代码风格**

```bash
python -m flake8 bt_utils/window_manager.py bt_utils/window_coordinate.py bt_utils/window_capture.py bt_core/context.py bt_core/nodes.py bt_gui/bt_editor/property.py
```

**Step 3: 最终提交**

```bash
git add .
git commit -m "feat: complete window binding feature with global auto coordinate conversion"
```

---

## 执行选择

**计划已完成并保存到 `docs/plans/2026-04-23-window-bind-tasks.md`。两种执行方式：**

**1. Subagent-Driven（当前会话）** - 我在当前会话中逐个任务分派子代理执行，任务间进行代码审查，快速迭代

**2. Parallel Session（独立会话）** - 打开新会话使用 executing-plans 技能，批量执行并设置检查点

**您选择哪种方式？**

# 窗口绑定功能设计文档（最终版 v2）

## 1 概述

### 1.1 背景

当前 AutoDoor 行为树系统使用绝对屏幕坐标进行操作，存在以下局限性：
- 窗口移动后，坐标失效，需要重新配置
- 无法支持后台监控窗口状态
- 无法实现多窗口自动化场景

### 1.2 目标

参考 autodoor 项目的后台监控功能，实现：
1. **全局窗口绑定**：在开始节点设置窗口绑定，所有节点共享
2. **下拉框选择窗口**：通过下拉框选择系统中的所有窗口
3. **相对坐标采集**：绑定窗口后，坐标采集自动记录相对坐标
4. **后台监控**：条件节点可以在后台检测窗口状态（使用 PrintWindow API）
5. **前台操作**：动作节点执行前自动切换窗口，执行后自动恢复原窗口
6. **智能切换**：如果目标窗口已是前台窗口，则不进行切换操作

### 1.3 设计原则

- **简单易用**：全局窗口绑定，用户只需配置一次
- **自动转换**：坐标采集自动记录相对坐标，执行时自动转换
- **智能优化**：检测目标窗口是否已是前台窗口，避免不必要的切换

---

## 2 核心技术

### 2.1 窗口枚举

**核心代码：**

```python
def enum_all_windows() -> List[Tuple[int, str]]:
    """枚举系统中所有可见窗口
    
    Returns:
        List[Tuple[int, str]]: [(hwnd, title), ...] 窗口句柄和标题列表
    """
    results = []
    
    def enum_windows_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:  # 只返回有标题的窗口
                results.append((hwnd, title))
        return True
    
    win32gui.EnumWindows(enum_windows_callback, None)
    return results
```

### 2.2 相对坐标转换

**核心代码：**

```python
class WindowCoordinate:
    """窗口坐标系统工具类"""
    
    @staticmethod
    def screen_to_window(screen_x: int, screen_y: int, hwnd: int) -> Tuple[int, int]:
        """屏幕绝对坐标转窗口相对坐标"""
        rect = win32gui.GetWindowRect(hwnd)
        return (screen_x - rect[0], screen_y - rect[1])
    
    @staticmethod
    def window_to_screen(rel_x: int, rel_y: int, hwnd: int) -> Tuple[int, int]:
        """窗口相对坐标转屏幕绝对坐标"""
        rect = win32gui.GetWindowRect(hwnd)
        return (rel_x + rect[0], rel_y + rect[1])
    
    @staticmethod
    def screen_region_to_window(screen_region: tuple, hwnd: int) -> tuple:
        """屏幕绝对区域转窗口相对区域"""
        rect = win32gui.GetWindowRect(hwnd)
        return (
            screen_region[0] - rect[0],
            screen_region[1] - rect[1],
            screen_region[2] - rect[0],
            screen_region[3] - rect[1]
        )
    
    @staticmethod
    def window_region_to_screen(window_region: tuple, hwnd: int) -> tuple:
        """窗口相对区域转屏幕绝对区域"""
        rect = win32gui.GetWindowRect(hwnd)
        return (
            window_region[0] + rect[0],
            window_region[1] + rect[1],
            window_region[2] + rect[0],
            window_region[3] + rect[1]
        )
```

### 2.3 后台截图（PrintWindow API）

**来源：** autodoor/utils/window_capture.py

**核心代码：**

```python
def capture_window(hwnd: int) -> Optional[Image.Image]:
    """后台截图 - 使用PrintWindow API"""
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)
    
    # 关键：使用 PrintWindow API
    result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
    
    # 转换为 PIL.Image
    img = Image.frombuffer('RGB', (width, height), bmpstr, 'raw', 'BGRX', 0, 1)
    return img
```

### 2.4 智能窗口切换

**核心代码：**

```python
def smart_switch_to_window(hwnd: int) -> bool:
    """智能切换到目标窗口"""
    # 检查目标窗口是否已经是前台窗口
    fg_hwnd = win32gui.GetForegroundWindow()
    if hwnd == fg_hwnd:
        # 目标窗口已经是前台窗口，无需切换
        return True
    
    # 保存当前前台窗口
    saved_hwnd = fg_hwnd
    
    # 切换到目标窗口
    switch_to_window(hwnd)
    
    return True
```

---

## 3 架构设计

### 3.1 模块划分

```
新增/修改模块：
├── bt_utils/
│   ├── window_manager.py          # 窗口管理器（枚举、切换、恢复）
│   ├── window_capture.py          # 后台截图（PrintWindow API）
│   └── window_coordinate.py       # 窗口坐标转换
├── bt_core/
│   ├── context.py                 # 扩展：添加窗口管理功能
│   └── nodes.py                   # 扩展：StartNode 添加窗口绑定属性
├── bt_gui/
│   └── bt_editor/
│       └── property.py            # 扩展：支持窗口下拉框和相对坐标采集
└── bt_nodes/
    ├── actions/                   # 所有动作节点自动处理窗口切换
    └── conditions/                # 所有条件节点自动使用后台截图
```

### 3.2 类图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          WindowManager                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ + enum_all_windows() -> List[Tuple[int, str]]                                │
│ + find_window_by_title(keyword) -> hwnd                                      │
│ + get_window_title(hwnd) -> str                                              │
│ + get_window_rect(hwnd) -> Tuple[int, int, int, int]                        │
│ + is_foreground_window(hwnd) -> bool                                         │
│ + save_foreground_window() -> hwnd                                           │
│ + switch_to_window(hwnd) -> bool                                             │
│ + restore_window(saved_hwnd) -> bool                                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          WindowCoordinate                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ + screen_to_window(x, y, hwnd) -> Tuple[int, int]                           │
│ + window_to_screen(x, y, hwnd) -> Tuple[int, int]                           │
│ + screen_region_to_window(region, hwnd) -> tuple                            │
│ + window_region_to_screen(region, hwnd) -> tuple                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          WindowCapture                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ + capture_window(hwnd) -> Image.Image                                        │
│ + capture_window_region(hwnd, region) -> Image.Image                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          ExecutionContext (扩展)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ - _bound_window: Optional[int]                                               │
│ - _saved_foreground_window: Optional[int]                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ + bind_window(hwnd) -> None                                                  │
│ + get_bound_window() -> Optional[int]                                        │
│ + capture_bound_window(region) -> Optional[Image.Image]                      │
│ + convert_to_screen_coords(region) -> tuple                                  │
│ + smart_switch_to_bound_window() -> bool                                     │
│ + smart_restore_foreground_window() -> bool                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          StartNode (扩展)                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ + bind_window: bool                                                          │
│ + window_title: str                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ + tick(context) -> NodeStatus                                                │
│ + _bind_window_to_context(context) -> None                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4 详细设计

### 4.1 WindowManager 工具类

**文件位置：** `bt_utils/window_manager.py`

**功能：**
- 窗口枚举（枚举系统中所有可见窗口）
- 窗口查找（通过标题查找）
- 窗口信息获取（标题、位置、大小）
- 窗口状态检测（是否前台窗口）
- 窗口切换（置顶、恢复）

**关键方法：**

```python
class WindowManager:
    """窗口管理器"""
    
    # 窗口枚举
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
                if title:  # 只返回有标题的窗口
                    results.append((hwnd, title))
            return True
        
        win32gui.EnumWindows(enum_windows_callback, None)
        return results
    
    # 窗口查找
    @staticmethod
    def find_window_by_title(keyword: str) -> Optional[int]:
        """通过标题关键字查找窗口"""
        
    # 窗口信息
    @staticmethod
    def get_window_title(hwnd: int) -> str:
        """获取窗口标题"""
        
    @staticmethod
    def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口矩形区域"""
    
    # 窗口状态检测
    @staticmethod
    def is_foreground_window(hwnd: int) -> bool:
        """检查窗口是否是前台窗口"""
        return win32gui.GetForegroundWindow() == hwnd
    
    # 窗口切换
    @staticmethod
    def save_foreground_window() -> int:
        """保存当前前台窗口"""
        return win32gui.GetForegroundWindow()
        
    @staticmethod
    def switch_to_window(hwnd: int) -> bool:
        """切换到目标窗口"""
        
    @staticmethod
    def restore_window(saved_hwnd: int) -> bool:
        """恢复原窗口"""
```

### 4.2 WindowCoordinate 工具类

**文件位置：** `bt_utils/window_coordinate.py`

**功能：**
- 坐标转换（屏幕坐标 ↔ 窗口相对坐标）

**关键方法：**

```python
class WindowCoordinate:
    """窗口坐标系统工具类
    
    移植自 autodoor/utils/coordinate.py
    """
    
    @staticmethod
    def screen_to_window(screen_x: int, screen_y: int, hwnd: int) -> Tuple[int, int]:
        """屏幕绝对坐标转窗口相对坐标"""
        rect = win32gui.GetWindowRect(hwnd)
        return (screen_x - rect[0], screen_y - rect[1])
    
    @staticmethod
    def window_to_screen(rel_x: int, rel_y: int, hwnd: int) -> Tuple[int, int]:
        """窗口相对坐标转屏幕绝对坐标"""
        rect = win32gui.GetWindowRect(hwnd)
        return (rel_x + rect[0], rel_y + rect[1])
    
    @staticmethod
    def screen_region_to_window(screen_region: tuple, hwnd: int) -> tuple:
        """屏幕绝对区域转窗口相对区域"""
        rect = win32gui.GetWindowRect(hwnd)
        return (
            screen_region[0] - rect[0],
            screen_region[1] - rect[1],
            screen_region[2] - rect[0],
            screen_region[3] - rect[1]
        )
    
    @staticmethod
    def window_region_to_screen(window_region: tuple, hwnd: int) -> tuple:
        """窗口相对区域转屏幕绝对区域"""
        rect = win32gui.GetWindowRect(hwnd)
        return (
            window_region[0] + rect[0],
            window_region[1] + rect[1],
            window_region[2] + rect[0],
            window_region[3] + rect[1]
        )
```

### 4.3 ExecutionContext 扩展

**文件位置：** `bt_core/context.py`

**核心设计决策：全局坐标自动转换**

**设计原则：**
- **只要开始节点绑定了窗口，所有涉及坐标的操作都自动进行相对坐标和绝对坐标的转换**
- 这是全局行为，不是节点选择
- 节点无需关心坐标转换，全部由 ExecutionContext 自动处理

**三个关键环节：**

| 环节 | 说明 | 处理位置 |
|------|------|----------|
| **采集坐标** | 用户在属性面板选择区域/位置时，自动记录相对坐标 | 属性面板 |
| **获取坐标** | 节点从黑板或其他地方获取坐标时，是相对坐标 | 节点内部 |
| **执行坐标** | 执行鼠标操作或截图时，自动将相对坐标转换为绝对坐标 | ExecutionContext |

**坐标转换流程：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           全局坐标自动转换流程                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 开始节点绑定窗口                                                          │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │ context.bind_window(hwnd)                                         │   │
│     │ → 全局生效，所有后续操作自动进行坐标转换                              │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  2. 用户采集坐标（属性面板）                                                   │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │ 用户选择区域 → 获取屏幕绝对坐标                                      │   │
│     │              ↓                                                    │   │
│     │ 检测是否绑定了窗口？                                                │   │
│     │   ├─ 是 → 转换为窗口相对坐标并保存                                   │   │
│     │   └─ 否 → 直接保存屏幕绝对坐标                                       │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  3. 节点获取坐标（节点内部）                                                   │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │ 节点从配置或黑板获取坐标                                             │   │
│     │ → 如果绑定了窗口，坐标是窗口相对坐标                                  │   │
│     │ → 如果没有绑定窗口，坐标是屏幕绝对坐标                                │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  4. 执行坐标操作（ExecutionContext）                                          │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │ 执行鼠标点击/移动/截图时：                                           │   │
│     │   ├─ 如果绑定了窗口 → 自动将相对坐标转换为绝对坐标                    │   │
│     │   └─ 如果没有绑定窗口 → 直接使用绝对坐标                              │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**新增属性：**

```python
class ExecutionContext:
    def __init__(self, project_root: str = None):
        # ... 现有属性 ...
        
        # 新增窗口管理属性
        self._bound_window: Optional[int] = None
        self._saved_foreground_window: Optional[int] = None
        self._window_manager = None
        self._window_capture = None
        self._window_coordinate = None
```

**新增方法：**

```python
class ExecutionContext:
    # 窗口管理
    def bind_window(self, hwnd: int) -> None:
        """绑定窗口"""
        self._bound_window = hwnd
        
    def get_bound_window(self) -> Optional[int]:
        """获取绑定的窗口句柄"""
        return self._bound_window
    
    # 后台截图
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
    
    # 坐标转换
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
    
    # 智能窗口切换
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

**修改现有方法（全局自动坐标转换）：**

```python
class ExecutionContext:
    # 修改鼠标点击方法
    def execute_mouse_click(self, button: str, position: tuple, action: str, duration: int):
        """执行鼠标点击（全局自动坐标转换）"""
        # 全局自动转换：如果绑定了窗口，将相对坐标转换为绝对坐标
        if self._bound_window and position:
            position = self.convert_to_screen_coords(position)
        
        # 执行点击
        self._input_controller.click(position[0], position[1], button)
    
    # 修改鼠标移动方法
    def execute_mouse_move(self, position: tuple, smooth: bool = False):
        """执行鼠标移动（全局自动坐标转换）"""
        # 全局自动转换：如果绑定了窗口，将相对坐标转换为绝对坐标
        if self._bound_window and position:
            position = self.convert_to_screen_coords(position)
        
        # 执行移动
        self._input_controller.move_to(position[0], position[1], smooth)
    
    # 修改截图方法
    def get_screenshot(self, region: tuple = None):
        """获取截图（全局自动坐标转换）"""
        # 全局自动转换：如果绑定了窗口，使用后台截图
        if self._bound_window and region:
            # 使用后台截图（region 是窗口相对坐标）
            return self.capture_bound_window(region)
        
        # 使用屏幕截图
        return self._screenshot_manager.capture_region(region)
```

**全局自动转换的优势：**

| 优势 | 说明 |
|------|------|
| 全局生效 | 只要开始节点绑定了窗口，所有操作自动转换，无需节点选择 |
| 节点无感知 | 节点完全不需要关心坐标转换，全部由 ExecutionContext 处理 |
| 代码集中 | 坐标转换逻辑集中在 ExecutionContext 中，易于维护 |
| 自动支持所有节点 | 现有的和新增的节点自动支持相对坐标，无需额外处理 |
| 向后兼容 | 不绑定窗口时，行为与现在完全一致 |
| 职责合理 | ExecutionContext 本来就负责执行上下文，处理坐标转换是合理的职责 |

**支持的节点类型（全部自动转换）：**

| 节点类型 | 自动转换内容 | 转换时机 |
|----------|-------------|----------|
| 鼠标点击节点 | 点击位置（position） | 执行点击时 |
| 鼠标移动节点 | 移动位置（position） | 执行移动时 |
| OCR检测节点 | 检测区域（region） | 获取截图时 |
| 图片检测节点 | 检测区域（region） | 获取截图时 |
| 颜色检测节点 | 检测区域（region） | 获取截图时 |
| 文本提取节点 | 提取区域（region） | 获取截图时 |
| 文本输入节点 | 输入位置（position） | 执行点击时 |

### 4.4 StartNode 扩展

**文件位置：** `bt_core/nodes.py`

**新增属性：**

```python
class StartNode(CompositeNode):
    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        
        # 新增窗口绑定属性
        self.bind_window = self.config.get_bool("bind_window", False)
        self.window_title = self.config.get("window_title", "")
```

**新增方法：**

```python
class StartNode(CompositeNode):
    def tick(self, context: ExecutionContext) -> NodeStatus:
        # 绑定窗口到上下文
        if self.bind_window and self.window_title:
            self._bind_window_to_context(context)
        
        # 执行子节点
        return super().tick(context)
    
    def _bind_window_to_context(self, context: ExecutionContext) -> None:
        """绑定窗口到上下文"""
        from bt_utils.window_manager import WindowManager
        
        # 通过标题查找窗口
        hwnd = WindowManager.find_window_by_title(self.window_title)
        
        if hwnd:
            context.bind_window(hwnd)
```

### 4.5 属性面板扩展

**文件位置：** `bt_gui/bt_editor/property.py`

**新增字段类型：**

```python
class WindowSelectField:
    """窗口选择字段（下拉框）"""
    
    def __init__(self, master, label: str, key: str, value: str = "", on_change=None):
        self.master = master
        self.label = label
        self.key = key
        self.on_change = on_change
        
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

**修改坐标采集逻辑：**

```python
class RegionField:
    """区域选择字段"""
    
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

### 4.6 ConditionNode 扩展

**文件位置：** `bt_core/nodes.py`

**说明：** 由于 ExecutionContext.get_screenshot() 已经实现了全局自动坐标转换，ConditionNode 完全不需要修改。

**现有方法（无需修改）：**

```python
class ConditionNode(Node):
    def _get_region_image(self, context):
        """获取区域图像"""
        # ExecutionContext.get_screenshot() 会自动处理：
        # 1. 如果绑定了窗口，使用后台截图（region 是窗口相对坐标）
        # 2. 如果没有绑定窗口，使用屏幕截图（region 是屏幕绝对坐标）
        # 节点无需关心坐标转换，全部自动处理
        return context.get_screenshot(self.region)
```

### 4.7 ActionNode 扩展

**文件位置：** `bt_core/nodes.py`

**说明：** ActionNode 需要添加窗口切换逻辑，但不需要处理坐标转换（ExecutionContext 已经实现了全局自动转换）。

**修改方法：**

```python
class ActionNode(Node):
    def tick(self, context: ExecutionContext) -> NodeStatus:
        # 检查是否绑定了窗口
        bound_window = context.get_bound_window()
        
        if bound_window:
            # 智能切换到目标窗口
            context.smart_switch_to_bound_window()
            
            try:
                # 执行动作
                # 注意：坐标转换由 ExecutionContext 全局自动处理
                # 节点无需关心坐标是相对坐标还是绝对坐标
                status = self._execute_action(context)
            finally:
                # 智能恢复原窗口
                context.smart_restore_foreground_window()
            
            return status
        
        # 直接执行动作
        return self._execute_action(context)
```

**鼠标点击节点（无需修改）：**

```python
class MouseClickNode(ActionNode):
    def _execute_action(self, context):
        # 获取点击位置（如果绑定了窗口，这是窗口相对坐标）
        position = self._get_position(context)
        
        # 执行点击
        # 注意：ExecutionContext.execute_mouse_click() 会全局自动转换坐标
        # 如果绑定了窗口，自动将相对坐标转换为绝对坐标
        # 如果没有绑定窗口，直接使用绝对坐标
        context.execute_mouse_click(self.button, position, self.action, self.duration)
        
        return NodeStatus.SUCCESS
```

**说明：** 所有需要坐标的节点（鼠标点击、鼠标移动、文本输入等）都不需要修改，因为 ExecutionContext 已经实现了全局自动坐标转换。节点完全不需要关心坐标是相对坐标还是绝对坐标。

---

## 5 使用示例

### 5.1 后台监控游戏窗口

```
开始节点（全局窗口绑定）
  - bind_window: True
  - window_title: "游戏窗口" (从下拉框选择)
  │
  ├─ OCR检测节点（自动使用后台截图）
  │   - region: (100, 100, 300, 200) (窗口相对坐标)
  │   - keywords: "开始游戏"
  │   └─ 鼠标点击节点（自动切换窗口）
  │       - position: (200, 150) (窗口相对坐标)
  │
  └─ OCR检测节点（自动使用后台截图）
      - region: (400, 100, 600, 200) (窗口相对坐标)
      - keywords: "确认"
      └─ 鼠标点击节点（自动切换窗口）
          - position: (500, 150) (窗口相对坐标)
```

**执行流程：**
1. 开始节点绑定游戏窗口到上下文
2. 用户在属性面板选择区域时，自动记录窗口相对坐标
3. OCR检测节点使用后台截图检测游戏窗口中的文字
4. 检测到"开始游戏"后，执行子节点
5. 鼠标点击节点执行前：
   - 检查游戏窗口是否已是前台窗口
   - 如果不是，保存当前前台窗口，切换到游戏窗口
   - 将窗口相对坐标转换为屏幕绝对坐标
   - 执行点击操作
   - 恢复原窗口（如果之前切换了）

---

## 6 实现计划

### 6.1 第一阶段：移植核心代码

| 任务 | 内容 | 说明 |
|------|------|------|
| Task 1 | 创建 WindowManager 工具类 | 窗口枚举、切换、恢复 |
| Task 2 | 创建 WindowCoordinate 工具类 | 坐标转换 |
| Task 3 | 创建 WindowCapture 工具类 | 后台截图（PrintWindow API） |
| Task 4 | 扩展 ExecutionContext | 窗口管理功能、全局自动坐标转换 |

### 6.2 第二阶段：扩展节点

| 任务 | 内容 | 说明 |
|------|------|------|
| Task 5 | 扩展 StartNode | 添加窗口绑定属性（bind_window、window_title） |
| Task 6 | 扩展 ActionNode | 添加智能窗口切换逻辑（无需处理坐标转换） |
| Task 7 | 扩展属性面板 | 窗口下拉框选择、相对坐标采集 |

**说明：**
- **ConditionNode 无需修改**：ExecutionContext.get_screenshot() 已经实现了全局自动坐标转换和后台截图
- **ActionNode 只需添加窗口切换逻辑**：坐标转换已由 ExecutionContext 自动处理
- **所有需要坐标的节点无需修改**：鼠标点击、鼠标移动、文本输入等节点完全不需要关心坐标转换

### 6.3 第三阶段：测试与文档

| 任务 | 内容 |
|------|------|
| Task 8 | 编写单元测试 |
| Task 9 | 编写集成测试 |
| Task 10 | 更新文档 |

---

## 7 依赖库

```python
# Windows API
import win32gui
import win32ui
import win32con
import win32api
import ctypes

# 图像处理
from PIL import Image

# 类型提示
from typing import Optional, Tuple, List
```

**requirements.txt 新增：**
```
pywin32>=305
```

---

## 8 风险评估

### 8.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| PrintWindow API 兼容性 | 中 | 某些应用可能不支持，提供回退方案 |
| 窗口切换失败 | 中 | 使用 SetWindowPos 设置最顶层，提高成功率 |
| 窗口权限问题 | 低 | 提供错误提示，建议以管理员运行 |
| 窗口关闭后句柄失效 | 中 | 执行前检查窗口是否有效 |

### 8.2 用户体验风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 窗口选择交互复杂 | 低 | 提供下拉框选择，简单直观 |
| 相对坐标概念理解困难 | 低 | 自动转换，用户无需关心细节 |
| 窗口切换闪烁 | 低 | 智能检测避免不必要的切换 |

---

## 9 总结

本设计文档基于 autodoor 项目的后台监控功能，设计了简化的窗口绑定方案。

**核心特性：**

| 特性 | 说明 |
|------|------|
| **全局窗口绑定** | 在开始节点设置，所有节点共享 |
| **下拉框选择窗口** | 通过下拉框选择系统中的所有窗口 |
| **相对坐标采集** | 绑定窗口后，坐标采集自动记录相对坐标 |
| **全局坐标自动转换** | 只要开始节点绑定了窗口，所有涉及坐标的操作都自动进行相对坐标和绝对坐标的转换 |
| **后台监控** | 条件节点自动使用后台截图（PrintWindow API） |
| **前台操作** | 动作节点自动切换窗口，执行后恢复原窗口 |
| **智能切换** | 检测目标窗口是否已是前台窗口，避免不必要的切换 |

**核心优势：**

| 优势 | 说明 |
|------|------|
| 操作简单 | 用户只需在下拉框中选择窗口 |
| 全局自动转换 | 坐标采集自动记录相对坐标，执行时自动转换，节点无需关心 |
| 智能优化 | 避免不必要的窗口切换，减少闪烁 |
| 代码复用 | 直接移植 autodoor 的成熟代码 |
| 节点无感知 | 所有节点完全不需要关心坐标转换，全部由 ExecutionContext 自动处理 |

**实现要点：**

1. **ExecutionContext 是核心**：所有窗口管理和坐标转换逻辑都集中在 ExecutionContext 中
2. **节点无需修改**：除了 ActionNode 需要添加窗口切换逻辑外，其他节点完全不需要修改
3. **属性面板是关键**：需要修改属性面板，实现窗口下拉框选择和相对坐标采集

# 行为树系统三大功能改造实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现坐标偏移功能、放大镜功能、随机范围功能三大改造

**Architecture:** 
- 坐标偏移：在 ConditionNode 基类添加偏移参数，各条件节点自动继承
- 放大镜：创建独立的 MagnifierWindow 组件，集成到各选择字段
- 随机范围：创建工具函数，修改各动作节点和装饰器逻辑

**Tech Stack:** Python 3.x, Tkinter, customtkinter, PIL

---

## 改造概览

### 功能一：坐标偏移功能
- 修改 `bt_core/nodes.py` 的 ConditionNode 基类
- 修改 `bt_nodes/conditions/` 下所有条件节点
- 修改 `bt_gui/bt_editor/property.py` 添加偏移配置字段
- 偏移测量工具已存在于 `bt_utils/offset_tool.py`

### 功能二：放大镜功能
- 创建 `bt_utils/magnifier.py` 放大镜组件
- 修改 `bt_gui/bt_editor/property.py` 集成放大镜到各字段

### 功能三：随机范围功能
- 创建 `bt_utils/helpers.py` 随机值计算工具函数
- 修改 `bt_nodes/actions/` 下各动作节点
- 修改 `bt_core/nodes.py` 装饰器逻辑
- 修改 `bt_gui/bt_editor/property.py` 添加随机范围字段

---

## Task 1: 创建随机值计算工具函数

**Files:**
- Create: `bt_utils/helpers.py`

**Step 1: 创建 helpers.py 文件**

```python
# bt_utils/helpers.py

import random
from typing import Union


def get_random_value(
    base_value: Union[int, float],
    random_range: Union[int, float] = 0,
    min_value: Union[int, float, None] = None
) -> Union[int, float]:
    """
    计算随机值
    
    Args:
        base_value: 基础值
        random_range: 随机范围（±值），默认为0（不随机）
        min_value: 最小值限制，默认为None（自动为0）
    
    Returns:
        随机后的值
    """
    if random_range <= 0:
        return base_value
    
    min_val = base_value - random_range
    max_val = base_value + random_range
    
    if min_value is not None:
        min_val = max(min_value, min_val)
    else:
        min_val = max(0, min_val)
    
    if isinstance(base_value, int):
        return random.randint(int(min_val), int(max_val))
    else:
        return random.uniform(min_val, max_val)


def get_random_duration(base_duration: int, random_range: int = 0) -> int:
    """
    计算随机时长（专用函数，确保时长不为负数）
    
    Args:
        base_duration: 基础时长(ms)
        random_range: 随机范围(±ms)
    
    Returns:
        随机后的时长(ms)
    """
    return get_random_value(base_duration, random_range, min_value=0)


def get_random_interval(base_interval: int, random_range: int = 0) -> int:
    """
    计算随机间隔（专用函数，确保间隔不为负数）
    
    Args:
        base_interval: 基础间隔(ms)
        random_range: 随机范围(±ms)
    
    Returns:
        随机后的间隔(ms)
    """
    return get_random_value(base_interval, random_range, min_value=0)
```

**Step 2: 验证文件创建成功**

Run: `python -c "from bt_utils.helpers import get_random_value, get_random_duration, get_random_interval; print('OK')"`

---

## Task 2: 创建放大镜组件

**Files:**
- Create: `bt_utils/magnifier.py`

**Step 1: 创建 magnifier.py 文件**

```python
# bt_utils/magnifier.py

import tkinter as tk
from PIL import Image, ImageGrab, ImageTk
from typing import Optional, Tuple


class MagnifierWindow:
    """放大镜窗口组件"""
    
    def __init__(
        self,
        zoom_factor: int = 4,
        size: int = 150,
        show_crosshair: bool = True,
        show_color_info: bool = True
    ):
        """
        初始化放大镜
        
        Args:
            zoom_factor: 放大倍数（默认4倍）
            size: 放大镜窗口大小（默认150x150像素）
            show_crosshair: 是否显示十字准线
            show_color_info: 是否显示颜色信息
        """
        self.zoom_factor = zoom_factor
        self.size = size
        self.show_crosshair = show_crosshair
        self.show_color_info = show_color_info
        
        self.window: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
        self.info_label: Optional[tk.Label] = None
        self.last_screenshot: Optional[Image.Image] = None
        self.photo = None
        
    def show(self, x: int, y: int):
        """
        在指定位置显示放大镜
        
        Args:
            x: 鼠标X坐标
            y: 鼠标Y坐标
        """
        if self.window is not None:
            return
        
        self.window = tk.Toplevel()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        
        canvas_size = self.size
        info_height = 60 if self.show_color_info else 0
        
        self.window.geometry(f"{canvas_size}x{canvas_size + info_height}")
        
        self.canvas = tk.Canvas(
            self.window,
            width=canvas_size,
            height=canvas_size,
            bg="#000000",
            highlightthickness=0
        )
        self.canvas.pack()
        
        if self.show_color_info:
            self.info_label = tk.Label(
                self.window,
                text="",
                font=("Consolas", 9),
                bg="#2b2b2b",
                fg="#ffffff",
                anchor="w",
                padx=5
            )
            self.info_label.pack(fill="x")
        
        self.update(x, y)
    
    def update(self, x: int, y: int):
        """
        更新放大镜显示内容
        
        Args:
            x: 鼠标X坐标
            y: 鼠标Y坐标
        """
        if self.window is None or self.canvas is None:
            return
        
        window_x = x + 20
        window_y = y + 20
        
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        if window_x + self.size > screen_width:
            window_x = x - self.size - 20
        if window_y + self.size > screen_height:
            window_y = y - self.size - 20
        
        self.window.geometry(f"+{window_x}+{window_y}")
        
        capture_size = self.size // self.zoom_factor
        half_capture = capture_size // 2
        
        left = x - half_capture
        top = y - half_capture
        right = x + half_capture
        bottom = y + half_capture
        
        screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
        self.last_screenshot = screenshot
        
        enlarged = screenshot.resize(
            (self.size, self.size),
            Image.Resampling.NEAREST
        )
        
        self.photo = ImageTk.PhotoImage(enlarged)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        
        if self.show_crosshair:
            center = self.size // 2
            self.canvas.create_line(
                center, 0, center, self.size,
                fill="#ff0000", width=1, dash=(2, 2)
            )
            self.canvas.create_line(
                0, center, self.size, center,
                fill="#ff0000", width=1, dash=(2, 2)
            )
        
        if self.show_color_info and self.info_label:
            pixel = screenshot.getpixel((half_capture, half_capture))
            if isinstance(pixel, int):
                r, g, b = pixel, pixel, pixel
            elif len(pixel) == 4:
                r, g, b, a = pixel
            else:
                r, g, b = pixel[:3]
            
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            
            info_text = f"坐标: ({x}, {y})\n颜色: {hex_color}  RGB({r}, {g}, {b})"
            self.info_label.config(text=info_text)
    
    def hide(self):
        """隐藏放大镜窗口"""
        if self.window is not None:
            self.window.destroy()
            self.window = None
            self.canvas = None
            self.info_label = None
            self.last_screenshot = None
            self.photo = None
```

**Step 2: 验证文件创建成功**

Run: `python -c "from bt_utils.magnifier import MagnifierWindow; print('OK')"`

---

## Task 3: 修改 ConditionNode 基类添加坐标偏移功能

**Files:**
- Modify: `bt_core/nodes.py:502-649`

**Step 1: 在 ConditionNode.__init__ 中添加偏移参数**

在 `bt_core/nodes.py` 的 `ConditionNode.__init__` 方法中，在 `self.position_key = ...` 之后添加：

```python
        # 坐标偏移参数
        self.offset_x = self.config.get_int("offset_x", 0)
        self.offset_y = self.config.get_int("offset_y", 0)
        self.offset_mode = self.config.get("offset_mode", "relative")
```

**Step 2: 添加 _apply_offset 方法**

在 `ConditionNode` 类中，在 `_parse_color` 方法之后添加：

```python
    def _apply_offset(self, position: tuple) -> tuple:
        """应用坐标偏移
        
        Args:
            position: 原始位置 (x, y)
            
        Returns:
            tuple: 偏移后的位置
        """
        if position is None:
            return None
        
        if self.offset_mode == "relative":
            return (position[0] + self.offset_x, position[1] + self.offset_y)
        else:  # absolute
            return (self.offset_x, self.offset_y)
    
    def _save_position(self, context, position: tuple):
        """保存位置到黑板（应用偏移）
        
        Args:
            context: 执行上下文
            position: 原始位置
        """
        if position and self.save_position:
            final_position = self._apply_offset(position)
            context.blackboard.set(self.position_key, final_position)
```

**Step 3: 验证修改**

Run: `python -c "from bt_core.nodes import ConditionNode; print('OK')"`

---

## Task 4: 修改 OCRConditionNode 使用坐标偏移

**Files:**
- Modify: `bt_nodes/conditions/ocr.py:32-33`

**Step 1: 修改 _check_condition 方法中的位置保存**

将：
```python
            if found:
                context.blackboard.set(self.position_key, position)
```

改为：
```python
            if found:
                self._save_position(context, position)
```

**Step 2: 在 to_dict 方法中添加偏移参数**

在 `to_dict` 方法中，在 `data["config"]["position_key"] = self.position_key` 之后添加：

```python
        data["config"]["offset_x"] = self.offset_x
        data["config"]["offset_y"] = self.offset_y
        data["config"]["offset_mode"] = self.offset_mode
```

---

## Task 5: 修改 ColorConditionNode 使用坐标偏移

**Files:**
- Modify: `bt_nodes/conditions/color.py:29-31`

**Step 1: 修改 _check_condition 方法中的位置保存**

将：
```python
            if found and position and match_count >= self.min_pixels:
                if self.region:
                    position = (position[0] + self.region[0], position[1] + self.region[1])
                context.blackboard.set(self.position_key, position)
```

改为：
```python
            if found and position and match_count >= self.min_pixels:
                if self.region:
                    position = (position[0] + self.region[0], position[1] + self.region[1])
                self._save_position(context, position)
```

**Step 2: 在 to_dict 方法中添加偏移参数**

在 `to_dict` 方法末尾添加：

```python
        data["config"]["offset_x"] = self.offset_x
        data["config"]["offset_y"] = self.offset_y
        data["config"]["offset_mode"] = self.offset_mode
```

---

## Task 6: 修改 ImageConditionNode 使用坐标偏移

**Files:**
- Modify: `bt_nodes/conditions/image.py`

**Step 1: 读取文件查看结构**

Run: `cat bt_nodes/conditions/image.py`

**Step 2: 修改位置保存逻辑**

找到 `context.blackboard.set(self.position_key, position)` 并改为 `self._save_position(context, position)`

**Step 3: 在 to_dict 方法中添加偏移参数**

---

## Task 7: 修改 NumberConditionNode 使用坐标偏移

**Files:**
- Modify: `bt_nodes/conditions/number.py`

**Step 1: 读取文件查看结构**

Run: `cat bt_nodes/conditions/number.py`

**Step 2: 修改位置保存逻辑**

找到 `context.blackboard.set(self.position_key, position)` 并改为 `self._save_position(context, position)`

**Step 3: 在 to_dict 方法中添加偏移参数**

---

## Task 8: 修改 KeyPressNode 添加随机范围功能

**Files:**
- Modify: `bt_nodes/actions/keyboard.py`

**Step 1: 在 __init__ 中添加随机参数**

在 `self.duration = self.config.get_int("duration", 0)` 之后添加：

```python
        self.duration_random = self.config.get_int("duration_random", 0)
```

**Step 2: 修改 _execute_action 方法**

在文件开头添加导入：
```python
from bt_utils.helpers import get_random_duration
```

将 `context.execute_key_press(self.key, self.action, self.duration)` 改为：

```python
        actual_duration = get_random_duration(self.duration, self.duration_random)
        context.execute_key_press(self.key, self.action, actual_duration)
```

**Step 3: 修改 to_dict 方法**

在 `data["config"]["duration"] = self.duration` 之后添加：

```python
        data["config"]["duration_random"] = self.duration_random
```

**Step 4: 修改 from_dict 方法**

在 `node.duration = config.get_int("duration", 0)` 之后添加：

```python
        node.duration_random = config.get_int("duration_random", 0)
```

---

## Task 9: 修改 MouseClickNode 添加随机范围功能

**Files:**
- Modify: `bt_nodes/actions/mouse.py`

**Step 1: 在 __init__ 中添加随机参数**

在 `self.click_interval = self.config.get_int("click_interval", 100)` 之后添加：

```python
        self.duration_random = self.config.get_int("duration_random", 0)
        self.click_interval_random = self.config.get_int("click_interval_random", 0)
```

**Step 2: 添加导入**

在文件开头添加：
```python
from bt_utils.helpers import get_random_duration, get_random_interval
```

**Step 3: 修改 _non_blocking_finite_click 方法**

在调用 `context.execute_mouse_click` 之前添加：

```python
        actual_duration = get_random_duration(self.duration, self.duration_random)
        actual_interval = get_random_interval(self.click_interval, self.click_interval_random)
```

并修改相应的调用使用这些随机值。

**Step 4: 修改 to_dict 方法**

添加：
```python
        data["config"]["duration_random"] = self.duration_random
        data["config"]["click_interval_random"] = self.click_interval_random
```

**Step 5: 修改 from_dict 方法**

添加：
```python
        node.duration_random = config.get_int("duration_random", 0)
        node.click_interval_random = config.get_int("click_interval_random", 0)
```

---

## Task 10: 修改 MouseMoveNode 添加随机范围功能

**Files:**
- Modify: `bt_nodes/actions/mouse.py:162-311`

**Step 1: 在 __init__ 中添加随机参数**

在 `self.drag_duration = self.config.get_int("drag_duration", 0)` 之后添加：

```python
        self.drag_duration_random = self.config.get_int("drag_duration_random", 0)
```

**Step 2: 修改 _execute_drag 方法**

在方法开头计算随机时长：
```python
        actual_drag_duration = get_random_duration(self.drag_duration, self.drag_duration_random)
```

并在后续使用 `actual_drag_duration` 替代 `self.drag_duration`。

**Step 3: 修改 to_dict 方法**

添加：
```python
        data["config"]["drag_duration_random"] = self.drag_duration_random
```

**Step 4: 修改 from_dict 方法**

添加：
```python
        node.drag_duration_random = config.get_int("drag_duration_random", 0)
```

---

## Task 11: 修改 DelayNode 添加随机范围功能

**Files:**
- Modify: `bt_nodes/actions/delay.py`

**Step 1: 在 __init__ 中添加随机参数**

在 `self.duration_ms = self.config.get_int("duration_ms", 1000)` 之后添加：

```python
        self.duration_ms_random = self.config.get_int("duration_ms_random", 0)
        self._actual_duration = None
```

**Step 2: 添加导入**

```python
from bt_utils.helpers import get_random_duration
```

**Step 3: 修改 _execute_action 方法**

将：
```python
    def _execute_action(self, context) -> NodeStatus:
        if self._delay_start_time is None:
            self._delay_start_time = time.time()

        elapsed = (time.time() - self._delay_start_time) * 1000

        if elapsed >= self.duration_ms:
```

改为：
```python
    def _execute_action(self, context) -> NodeStatus:
        if self._delay_start_time is None:
            self._actual_duration = get_random_duration(self.duration_ms, self.duration_ms_random)
            self._delay_start_time = time.time()

        elapsed = (time.time() - self._delay_start_time) * 1000

        if elapsed >= self._actual_duration:
```

**Step 4: 修改 reset 方法**

添加：
```python
        self._actual_duration = None
```

**Step 5: 修改 to_dict 方法**

添加：
```python
        data["config"]["duration_ms_random"] = self.duration_ms_random
```

**Step 6: 修改 from_dict 方法**

添加：
```python
        node.duration_ms_random = config.get_int("duration_ms_random", 0)
```

---

## Task 12: 修改 Node 基类装饰器添加随机范围功能

**Files:**
- Modify: `bt_core/nodes.py:88-99`

**Step 1: 添加导入**

在文件开头添加：
```python
from bt_utils.helpers import get_random_interval
```

**Step 2: 修改 _execute_with_decorators 方法中的重复间隔逻辑**

将：
```python
                repeat_interval_ms = self.config.repeat_interval_ms
                if repeat_interval_ms > 0:
                    import time
                    time.sleep(repeat_interval_ms / 1000)
```

改为：
```python
                repeat_interval_ms = self.config.repeat_interval_ms
                repeat_interval_ms_random = self.config.get("repeat_interval_ms_random", 0)
                if repeat_interval_ms > 0 or repeat_interval_ms_random > 0:
                    import time
                    actual_interval = get_random_interval(repeat_interval_ms, repeat_interval_ms_random)
                    if actual_interval > 0:
                        time.sleep(actual_interval / 1000)
```

---

## Task 13: 修改 SequenceNode 添加子节点间隔随机功能

**Files:**
- Modify: `bt_core/nodes.py:235-309`

**Step 1: 在 __init__ 中添加随机参数**

在 `self.child_interval = self.config.get_int("childinterval", 0)` 之后添加：

```python
        self.child_interval_random = self.config.get_int("childinterval_random", 0)
```

**Step 2: 修改 _tick_internal 方法**

在子节点间隔检查处添加随机逻辑。

---

## Task 14: 修改 SelectorNode 添加子节点间隔随机功能

**Files:**
- Modify: `bt_core/nodes.py:311-372`

**Step 1: 在 __init__ 中添加随机参数**

在 `self.child_interval = self.config.get_int("childinterval", 0)` 之后添加：

```python
        self.child_interval_random = self.config.get_int("childinterval_random", 0)
```

**Step 2: 修改 _tick_internal 方法**

在子节点间隔检查处添加随机逻辑。

---

## Task 15: 更新属性面板字段定义 - 条件节点偏移配置

**Files:**
- Modify: `bt_gui/bt_editor/property.py:12-135`

**Step 1: 定义偏移字段**

在 `NODE_CONFIG_SCHEMAS` 之前添加：

```python
OFFSET_FIELDS = [
    {"key": "offset_x", "label": "X偏移", "type": "number", "default": 0, "width": 60},
    {"key": "offset_y", "label": "Y偏移", "type": "number", "default": 0, "width": 60},
    {"key": "offset_mode", "label": "偏移模式", "type": "select", 
     "options": ["relative", "absolute"], "default": "relative"},
]
```

**Step 2: 为各条件节点添加偏移字段**

在 `OCRConditionNode`、`ImageConditionNode`、`ColorConditionNode`、`NumberConditionNode` 的配置中添加偏移字段。

---

## Task 16: 更新属性面板字段定义 - 动作节点随机范围配置

**Files:**
- Modify: `bt_gui/bt_editor/property.py`

**Step 1: 为 KeyPressNode 添加随机字段**

在 `duration` 字段之后添加：
```python
        {"key": "duration_random", "label": "时长随机范围(±ms)", "type": "number", "min": 0, "default": 0},
```

**Step 2: 为 MouseClickNode 添加随机字段**

在 `duration` 和 `click_interval` 字段之后分别添加随机范围字段。

**Step 3: 为 MouseMoveNode 添加随机字段**

在 `drag_duration` 字段之后添加随机范围字段。

**Step 4: 为 DelayNode 添加随机字段**

在 `duration_ms` 字段之后添加随机范围字段。

---

## Task 17: 更新装饰器字段定义 - 随机范围配置

**Files:**
- Modify: `bt_gui/bt_editor/property.py:117-135`

**Step 1: 修改 ACTION_DECORATOR_FIELDS**

在 `repeat_interval_ms` 之后添加：
```python
    {"key": "repeat_interval_ms_random", "label": "重复间隔随机范围(±ms)", "type": "number", "min": 0, "default": 0},
```

**Step 2: 修改 COMPOSITE_DECORATOR_FIELDS**

在 `repeat_interval_ms` 之后添加：
```python
    {"key": "repeat_interval_ms_random", "label": "重复间隔随机范围(±ms)", "type": "number", "min": 0, "default": 0},
```

---

## Task 18: 更新复合节点字段定义 - 子节点间隔随机配置

**Files:**
- Modify: `bt_gui/bt_editor/property.py:105-115`

**Step 1: 修改 SequenceNode 配置**

在 `childinterval` 之后添加：
```python
        {"key": "childinterval_random", "label": "子节点间隔随机范围(±ms)", "type": "number", "min": 0, "default": 0},
```

**Step 2: 修改 SelectorNode 配置**

同样添加 `childinterval_random` 字段。

---

## Task 19: 集成放大镜到 RegionField

**Files:**
- Modify: `bt_gui/bt_editor/property.py`

**Step 1: 找到 RegionField 类的 _start_selection 方法**

**Step 2: 添加导入**

在文件开头添加：
```python
from bt_utils.magnifier import MagnifierWindow
```

**Step 3: 在 _start_selection 方法中集成放大镜**

创建 MagnifierWindow 实例，在鼠标移动事件中更新放大镜，在鼠标按下和抬起时隐藏放大镜。

---

## Task 20: 集成放大镜到 ScreenshotField

**Files:**
- Modify: `bt_gui/bt_editor/property.py`

**Step 1: 找到 ScreenshotField 类**

**Step 2: 在选择方法中集成放大镜**

与 RegionField 类似的集成方式。

---

## Task 21: 集成放大镜到 PositionField

**Files:**
- Modify: `bt_gui/bt_editor/property.py`

**Step 1: 找到 PositionField 类的 _pick_position 方法**

**Step 2: 在方法中集成放大镜**

创建 MagnifierWindow 实例，在鼠标移动时更新，点击时隐藏。

---

## Task 22: 创建偏移字段组件

**Files:**
- Modify: `bt_gui/bt_editor/property.py`

**Step 1: 创建 OffsetField 类**

创建一个包含 X偏移、Y偏移、偏移模式和测量按钮的组合字段组件。

**Step 2: 集成偏移测量工具**

在测量按钮点击时调用 `OffsetMeasurementDialog`。

---

## Task 23: 测试坐标偏移功能

**Step 1: 创建测试行为树**

创建一个包含 OCR 检测节点和鼠标点击节点的测试行为树。

**Step 2: 配置偏移参数**

设置 X偏移和 Y偏移值。

**Step 3: 运行测试**

验证点击位置是否正确偏移。

---

## Task 24: 测试放大镜功能

**Step 1: 启动应用程序**

**Step 2: 测试区域选择**

点击选择区域按钮，验证放大镜是否正确显示。

**Step 3: 测试位置选择**

点击选择位置按钮，验证放大镜是否正确显示。

---

## Task 25: 测试随机范围功能

**Step 1: 创建测试行为树**

创建包含各动作节点的测试行为树。

**Step 2: 配置随机参数**

为各时长和间隔参数设置随机范围。

**Step 3: 多次运行测试**

验证每次执行的时长和间隔是否在随机范围内。

---

## Task 26: 向后兼容性测试

**Step 1: 加载旧版本行为树文件**

加载不包含新参数的旧版本行为树文件。

**Step 2: 验证默认值**

验证所有新参数使用默认值。

**Step 3: 保存并重新加载**

验证保存后文件包含新参数。

---

## Task 27: 最终验证和文档更新

**Step 1: 运行完整测试**

运行所有功能测试，确保无错误。

**Step 2: 更新用户手册**

在用户手册中添加新功能说明。

**Step 3: 提交代码**

```bash
git add .
git commit -m "feat: 实现坐标偏移、放大镜、随机范围三大功能"
```

---

## 实施顺序建议

1. **第一阶段（基础设施）**
   - Task 1: 创建随机值计算工具函数
   - Task 2: 创建放大镜组件

2. **第二阶段（坐标偏移功能）**
   - Task 3-7: 修改条件节点

3. **第三阶段（随机范围功能）**
   - Task 8-14: 修改动作节点和装饰器

4. **第四阶段（GUI更新）**
   - Task 15-22: 更新属性面板

5. **第五阶段（测试验证）**
   - Task 23-27: 测试和文档

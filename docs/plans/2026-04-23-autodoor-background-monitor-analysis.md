# autodoor 项目后台监控功能完整分析

## 1 功能概述

autodoor 项目的后台监控功能允许用户在后台监控多个窗口，当检测到特定条件时，自动切换到目标窗口执行操作，然后恢复原窗口。

**核心特性：**
- 后台截图：使用 PrintWindow API，窗口可以在后台最小化
- 多窗口监控：支持同时监控多个窗口
- 自动切换：检测到条件后自动切换窗口执行操作
- 自动恢复：操作完成后自动恢复原窗口
- 分辨率自适应：使用比例坐标，支持窗口大小变化

---

## 2 核心技术实现

### 2.1 后台截图（PrintWindow API）

**文件位置：** `utils/window_capture.py`

**核心函数：**

```python
def capture_window(hwnd: int) -> Optional[Image.Image]:
    """
    后台截图 - 使用PrintWindow API
    
    Args:
        hwnd: 窗口句柄
    
    Returns:
        PIL.Image: 截图图像，失败返回None
    """
    # 使用 PrintWindow API 实现后台截图
    # 关键代码：
    result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
    # 参数 2 表示 PW_CLIENTONLY，只截取客户区
```

**技术要点：**
1. 使用 `PrintWindow` API，而不是 `BitBlt`
2. 窗口可以在后台最小化，不影响截图
3. 只截取客户区，不包含标题栏和边框
4. 返回 PIL.Image 对象，方便后续处理

**区域截图：**

```python
def capture_window_region(hwnd: int, region: tuple) -> Optional[Image.Image]:
    """
    后台截图指定区域
    
    Args:
        hwnd: 窗口句柄
        region: 区域坐标 (x1, y1, x2, y2)，窗口相对坐标
    
    Returns:
        PIL.Image: 区域截图，失败返回None
    """
    full_image = capture_window(hwnd)
    if full_image is None:
        return None
    
    # 裁剪区域
    return full_image.crop((x1, y1, x2, y2))
```

---

### 2.2 窗口切换（QuickSwitchBackend）

**文件位置：** `utils/quick_switch.py`

**核心类：**

```python
class QuickSwitchBackend:
    """快速窗口切换后台操作实现"""
    
    def __init__(self, app=None):
        self.hwnd: Optional[int] = None
        self._original_fg_window: Optional[int] = None
    
    def _save_foreground_window(self) -> None:
        """保存当前前台窗口"""
        self._original_fg_window = win32gui.GetForegroundWindow()
    
    def _switch_to_target(self) -> bool:
        """切换到目标窗口"""
        # 1. 确保窗口可见
        if win32gui.IsIconic(self.hwnd):
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
        
        # 2. 设置为最顶层
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                             win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        
        # 3. 激活窗口
        win32gui.SetForegroundWindow(self.hwnd)
        
        # 4. 取消最顶层状态
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
                             win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        
        return True
    
    def _restore_foreground_window(self) -> None:
        """恢复原来的前台窗口"""
        # 使用 Alt+Tab 模拟用户操作
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # Alt键按下
        win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)   # Tab键按下
        win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        
        # 激活原窗口
        win32gui.SetForegroundWindow(self._original_fg_window)
```

**技术要点：**
1. 使用 `SetWindowPos` 设置窗口为最顶层
2. 使用 `SetForegroundWindow` 激活窗口
3. 使用 Alt+Tab 模拟用户操作，提高成功率
4. 操作完成后取消最顶层状态

---

### 2.3 坐标系统

**文件位置：** `utils/coordinate.py`

**核心类：**

```python
class RelativeCoordinate:
    """相对比例坐标系统"""
    
    @staticmethod
    def pixel_to_ratio(region: tuple, window_size: tuple) -> Optional[tuple]:
        """像素坐标转比例坐标"""
        x1, y1, x2, y2 = region
        win_w, win_h = window_size
        return (x1 / win_w, y1 / win_h, x2 / win_w, y2 / win_h)
    
    @staticmethod
    def ratio_to_pixel(ratio_region: tuple, window_size: tuple) -> Optional[tuple]:
        """比例坐标转像素坐标"""
        rx1, ry1, rx2, ry2 = ratio_region
        win_w, win_h = window_size
        return (int(rx1 * win_w), int(ry1 * win_h), int(rx2 * win_w), int(ry2 * win_h))


class WindowCoordinate:
    """窗口坐标系统工具类"""
    
    @staticmethod
    def screen_to_window(screen_x: int, screen_y: int, hwnd: int) -> Optional[Tuple[int, int]]:
        """屏幕绝对坐标转窗口相对坐标"""
        rect = win32gui.GetWindowRect(hwnd)
        return (screen_x - rect[0], screen_y - rect[1])
    
    @staticmethod
    def window_to_screen(rel_x: int, rel_y: int, hwnd: int) -> Optional[Tuple[int, int]]:
        """窗口相对坐标转屏幕绝对坐标"""
        rect = win32gui.GetWindowRect(hwnd)
        return (rel_x + rect[0], rel_y + rect[1])
```

**技术要点：**
1. **相对比例坐标**：使用 0.0-1.0 的比例坐标，支持窗口大小变化
2. **窗口相对坐标**：相对于窗口客户区左上角的坐标
3. **屏幕绝对坐标**：相对于屏幕左上角的坐标

---

### 2.4 后台监控管理器

**文件位置：** `modules/background.py`

**核心类：**

```python
class BackgroundMonitor:
    """单个后台监控组"""
    
    def __init__(self, app, group_index: int = 0):
        self.hwnd = None                    # 窗口句柄
        self.region = None                  # 监控区域（像素坐标）
        self.region_ratio = None            # 监控区域（比例坐标）
        self.recognition_type = "ocr"       # 识别类型
        self.interval = 5.0                 # 检测间隔
        self.pause = 180                    # 触发后暂停时间
    
    def _monitor_loop(self) -> None:
        """监控主循环"""
        while self.is_running:
            # 1. 获取当前区域（支持分辨率自适应）
            region = self._get_current_region()
            
            # 2. 后台截图
            image = self._capture_region(region)
            
            # 3. 执行识别
            matched, click_position = self._recognize(image)
            
            # 4. 如果匹配，触发动作
            if matched:
                self._trigger_action(click_position)
            
            # 5. 等待下一次检测
            time.sleep(self.interval)
    
    def _capture_region(self, region: tuple):
        """截取监控区域"""
        return capture_window_region(self.hwnd, region)
    
    def _trigger_action(self, click_position=None) -> None:
        """触发动作"""
        quick_switch = QuickSwitchBackend(self.app)
        quick_switch.set_hwnd(self.hwnd)
        
        # 1. 保存当前前台窗口
        quick_switch._save_foreground_window()
        
        # 2. 切换到目标窗口
        switch_success = quick_switch._switch_to_target()
        
        if switch_success:
            # 3. 执行点击操作
            if self.trigger_click and click_position:
                rect = get_window_rect(self.hwnd)
                abs_x = rect[0] + click_position[0]
                abs_y = rect[1] + click_position[1]
                self.app.input_controller.click(abs_x, abs_y)
            
            # 4. 执行按键操作
            if self.trigger_key:
                self.app.input_controller.key_down(self.trigger_key)
                time.sleep(hold_delay)
                self.app.input_controller.key_up(self.trigger_key)
            
            # 5. 恢复原窗口
            quick_switch._restore_foreground_window()
```

**技术要点：**
1. **独立线程**：每个监控组在独立线程中运行
2. **分辨率自适应**：使用比例坐标，支持窗口大小变化
3. **后台截图**：使用 PrintWindow API，窗口可以在后台最小化
4. **自动切换**：检测到条件后自动切换窗口执行操作
5. **自动恢复**：操作完成后自动恢复原窗口

---

## 3 完整执行流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           后台监控完整执行流程                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 初始化阶段                                                                │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │ 用户绑定目标窗口 → find_window_by_title() → 获取 hwnd             │   │
│     │ 用户选择监控区域 → pixel_to_ratio() → 保存比例坐标                 │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  2. 监控循环阶段                                                              │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │ while is_running:                                                 │   │
│     │     # 获取当前区域（分辨率自适应）                                   │   │
│     │     region = ratio_to_pixel(region_ratio, window_size)            │   │
│     │                                                                   │   │
│     │     # 后台截图                                                     │   │
│     │     image = capture_window_region(hwnd, region)                   │   │
│     │                                                                   │   │
│     │     # 执行识别                                                     │   │
│     │     matched, position = recognize(image)                          │   │
│     │                                                                   │   │
│     │     # 如果匹配，触发动作                                            │   │
│     │     if matched:                                                   │   │
│     │         trigger_action(position)                                  │   │
│     │                                                                   │   │
│     │     # 等待下一次检测                                               │   │
│     │     sleep(interval)                                               │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  3. 触发动作阶段                                                              │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │ # 保存当前前台窗口                                                 │   │
│     │ original_hwnd = GetForegroundWindow()                             │   │
│     │                                                                   │   │
│     │ # 切换到目标窗口                                                   │   │
│     │ SetWindowPos(hwnd, HWND_TOPMOST)                                  │   │
│     │ SetForegroundWindow(hwnd)                                         │   │
│     │ SetWindowPos(hwnd, HWND_NOTOPMOST)                                │   │
│     │                                                                   │   │
│     │ # 执行操作                                                         │   │
│     │ click(abs_x, abs_y)  # 转换为屏幕绝对坐标                          │   │
│     │ key_press(key)                                                   │   │
│     │                                                                   │   │
│     │ # 恢复原窗口                                                       │   │
│     │ Alt+Tab 模拟                                                      │   │
│     │ SetForegroundWindow(original_hwnd)                                │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4 关键技术细节

### 4.1 PrintWindow API

**优点：**
- 窗口可以在后台最小化
- 不影响前台工作
- 性能较好

**缺点：**
- 某些应用可能不支持（如某些游戏）
- 截图可能不包含某些特效

**使用场景：**
- 后台监控
- 多窗口操作
- 自动化测试

### 4.2 窗口切换

**关键技术：**
1. `SetWindowPos(hwnd, HWND_TOPMOST)` - 设置为最顶层
2. `SetForegroundWindow(hwnd)` - 激活窗口
3. `SetWindowPos(hwnd, HWND_NOTOPMOST)` - 取消最顶层

**注意事项：**
- Windows 限制非前台进程调用 `SetForegroundWindow`
- 使用 `SetWindowPos` 设置最顶层可以绕过限制
- 操作完成后必须取消最顶层状态

### 4.3 坐标转换

**三种坐标系统：**
1. **屏幕绝对坐标**：相对于屏幕左上角
2. **窗口相对坐标**：相对于窗口客户区左上角
3. **比例坐标**：0.0-1.0 的比例值

**转换公式：**
```
屏幕坐标 = 窗口坐标 + 窗口左上角坐标
窗口坐标 = 屏幕坐标 - 窗口左上角坐标
比例坐标 = 窗口坐标 / 窗口尺寸
窗口坐标 = 比例坐标 * 窗口尺寸
```

---

## 5 依赖库

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

---

## 6 总结

autodoor 项目的后台监控功能是一个完整的解决方案，包含：

1. **后台截图**：使用 PrintWindow API，窗口可以在后台最小化
2. **窗口切换**：使用 SetWindowPos + SetForegroundWindow，确保窗口切换成功
3. **坐标系统**：支持三种坐标系统，支持分辨率自适应
4. **监控管理**：支持多窗口、多监控组，独立线程运行

**核心优势：**
- 用户可以在后台监控多个窗口
- 不影响前台工作
- 支持分辨率自适应
- 自动切换和恢复窗口

**适用场景：**
- 游戏自动化
- 多窗口监控
- 后台任务处理
- 自动化测试

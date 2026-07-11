# 脚本节点与普通节点按键操作延迟深度分析

> 分析日期：2026-07-09
> 分析范围：ScriptNode（脚本运行节点）与 KeyPressNode / MouseClickNode（普通按键/点击节点）在按键操作时序上的差异
> 核心问题：脚本运行时实际操作间隔远大于记录的 delay 时长；连续按下同一按键的间隔远大于普通点击节点连续点击 2 次的间隔

---

## 1 问题复现与现象

### 1.1 现象一：脚本回放时操作间隔比记录的 delay 更长

录制脚本时，用户两次按键之间的间隔（例如 50ms）被 pynput 捕获并写入脚本：

```
KeyDown "space", 1
Delay 50
KeyUp "space", 1
```

回放时，实际从 KeyDown 到 KeyUp 的间隔远超 50ms，通常多出 200ms 以上。

### 1.2 现象二：脚本连续按同一按键的间隔远大于普通点击节点连点 2 次

- **脚本方式**：脚本中连续两次按下同一按键，中间间隔远超预期
- **普通节点方式**：MouseClickNode 配置 `click_count=2`，两次点击间隔接近配置的 `click_interval`

---

## 2 架构对比分析

### 2.1 普通节点执行架构（KeyPressNode / MouseClickNode）

普通节点运行在**行为树引擎的 tick 循环**中，采用**非阻塞（Non-blocking）**执行模式：

```
BehaviorTreeEngine._run_loop()          # 独立线程，10ms tick 间隔
  └── root_node.tick(context)           # 每个 tick 调用一次
        └── ActionNode.tick(context)
              └── _execute_action(context)
                    └── context.execute_key_press(key, action, duration)
                          └── InputControllerManager.get_keyboard_engine()
                                └── PyAutoGUIInput.key_press(key, action, duration)
                                      └── pyautogui.press(key) / keyDown(key) / keyUp(key)
```

**关键特征：**

| 特征 | 说明 | 代码位置 |
|------|------|----------|
| 执行线程 | 引擎守护线程（与 ScriptNode 的独立线程不同） | [engine.py:212](file:///d:/workspace/autodoor_behavior_tree/bt_core/engine.py#L212) |
| tick 间隔 | 10ms（`self._tick_interval = 0.01`） | [engine.py:26](file:///d:/workspace/autodoor_behavior_tree/bt_core/engine.py#L26) |
| 阻塞行为 | 动作执行本身是同步的，但等待间隔是非阻塞的 | 见下方说明 |
| 状态管理 | 通过返回 `NodeStatus.RUNNING` 实现非阻塞等待 | [keyboard.py:93](file:///d:/workspace/autodoor_behavior_tree/bt_nodes/actions/keyboard.py#L93) |
| 输入调用 | `context.execute_key_press()` → `InputControllerManager` → `engine.key_press()` | [context.py:221](file:///d:/workspace/autodoor_behavior_tree/bt_core/context.py#L221) |

**MouseClickNode 非阻塞等待机制（核心差异）：**

```python
# bt_nodes/actions/mouse.py:93-139  _non_blocking_finite_click()
# 1. 执行点击（同步，包含 pyautogui.PAUSE）
context.execute_mouse_click(button, position, action, self._actual_duration)
# 2. 记录完成时间（在 PAUSE 结束之后）
self._last_click_time = time.time() * 1000
# 3. 返回 RUNNING，让引擎继续 tick
return NodeStatus.RUNNING

# 下一个 tick：
# 4. 检查是否到达间隔（非阻塞）
elapsed = current_time - self._last_click_time
if elapsed < self._actual_interval:
    return NodeStatus.RUNNING  # 未到时间，继续等待
# 5. 到达间隔，执行下一次点击
```

**关键点：** `_last_click_time` 在 `execute_mouse_click` 返回后记录，即**包含了 pyautogui.PAUSE 的时间**。因此 `click_interval` 的等待与 PAUSE 是**串行但可重叠**的——如果 PAUSE 本身已经超过 click_interval，则下一次点击立即执行。

### 2.2 脚本节点执行架构（ScriptNode + ScriptExecutor）

脚本节点启动一个**独立线程**，采用**阻塞（Blocking）**执行模式：

```
ScriptNode._execute_action(context)     # 在引擎线程中调用
  └── ScriptExecutor.run_script(content, loop)
        └── threading.Thread(target=execute)  # 新建独立线程
              └── for command in commands:     # 顺序遍历命令
                    └── _execute_command(command, pressed_keys)
                          ├── keydown:  self.input_controller.key_down(key)   # 直接调用，不经 context
                          ├── keyup:    self.input_controller.key_up(key)
                          ├── delay:    time.sleep(delay_time)                 # 阻塞等待
                          └── moveto:   self.input_controller.move_to(x, y)
```

**关键特征：**

| 特征 | 说明 | 代码位置 |
|------|------|----------|
| 执行线程 | **独立线程**（`threading.Thread` 或 `ThreadPoolExecutor`） | [script_executor.py:115](file:///d:/workspace/autodoor_behavior_tree/bt_utils/script_executor.py#L115) |
| 阻塞行为 | **全部阻塞**——命令顺序执行，`Delay` 用 `time.sleep` | [script_executor.py:271-277](file:///d:/workspace/autodoor_behavior_tree/bt_utils/script_executor.py#L271) |
| 输入调用 | `self.input_controller.key_down(key)` ——**直接调用 InputController，绕过 context** | [script_executor.py:250](file:///d:/workspace/autodoor_behavior_tree/bt_utils/script_executor.py#L250) |
| InputController 实例 | **独立创建**（`InputController()`），与普通节点的 `InputControllerManager` 实例不同 | [script_executor.py:76-79](file:///d:/workspace/autodoor_behavior_tree/bt_utils/script_executor.py#L76) |
| 与引擎通信 | ScriptNode 每个 tick 检查 `executor.is_running`，自身返回 RUNNING | [script.py:91-99](file:///d:/workspace/autodoor_behavior_tree/bt_nodes/actions/script.py#L91) |

**Delay 命令实现（阻塞式）：**

```python
# bt_utils/script_executor.py:271-277
elif command["type"] == "delay":
    delay_time = command["time"] / 1000
    elapsed = 0
    while elapsed < delay_time and self.is_running:
        sleep_time = min(0.1, delay_time - elapsed)  # 100ms 分段
        time.sleep(sleep_time)
        elapsed += sleep_time
```

### 2.3 架构差异总结

| 维度 | 普通节点（KeyPressNode/MouseClickNode） | 脚本节点（ScriptNode + ScriptExecutor） |
|------|---------------------------------------|---------------------------------------|
| **执行线程** | 引擎守护线程 | 独立线程 |
| **执行模式** | 非阻塞（RUNNING 状态 + tick 轮询） | 阻塞（顺序执行 + time.sleep） |
| **输入调用路径** | `context.execute_key_press()` → `InputControllerManager` → engine | `InputController.key_down()` 直接调用 |
| **delay 实现** | 通过 `time.time()` 比较实现非阻塞等待 | `time.sleep()` 阻塞等待 |
| **pyautogui.PAUSE** | 每次 `execute_key_press/mouse_click` 后触发 | 每次 `key_down/key_up` 后触发 |
| **间隔等待与 PAUSE 关系** | 串行但可重叠（PAUSE 消耗后检查间隔） | 完全串行叠加（PAUSE + sleep 顺序累加） |

---

## 3 根因分析

### 3.1 根因一：pyautogui.PAUSE 默认延迟（最主要原因）

**pyautogui 的 PAUSE 机制：**

PyAutoGUI 在每个公开函数（`keyDown`、`keyUp`、`press`、`mouseDown`、`mouseUp`、`click` 等）调用结束后，会自动执行 `time.sleep(pyautogui.PAUSE)`。默认值为 **0.1 秒（100ms）**。

```python
# pyautogui 内部机制（简化示意）
def keyDown(key):
    # ... 实际按键操作 ...
    time.sleep(pause)   # pause 默认 0.1s

def keyUp(key):
    # ... 实际按键操作 ...
    time.sleep(pause)   # pause 默认 0.1s
```

**代码证据——TextInputNode 已修复此问题但仅限自身：**

```python
# bt_nodes/actions/text_input.py:144-145
original_pause = pyautogui.PAUSE
pyautogui.PAUSE = 0    # TextInputNode 显式禁用 PAUSE
try:
    # ... 文本输入操作 ...
finally:
    pyautogui.PAUSE = original_pause
```

**但 PyAutoGUIInput 类（普通节点和脚本节点共用）未禁用 PAUSE：**

```python
# bt_utils/input_controller_factory.py:54-61
class PyAutoGUIInput(BaseInputController):
    def __init__(self, app=None):
        # ...
        import pyautogui
        pyautogui.FAILSAFE = False
        # ❌ 缺少：pyautogui.PAUSE = 0
```

**录制与回放的时间模型不一致：**

| 阶段 | 使用的库 | 是否有 PAUSE |
|------|---------|-------------|
| 录制 | pynput（`keyboard.Listener` / `mouse.Listener`） | **无** PAUSE |
| 回放（脚本） | pyautogui（`keyDown` / `keyUp`） | **有** PAUSE（100ms/次） |
| 回放（普通节点） | pyautogui（`press` / `keyDown` / `keyUp`） | **有** PAUSE（100ms/次） |

录制时 pynput 只是监听事件，不产生任何延迟；回放时 pyautogui 每次调用都附加 100ms 延迟。这导致**回放始终比录制慢**。

### 3.2 根因二：阻塞 vs 非阻塞执行模式导致间隔叠加方式不同

**普通 MouseClickNode 连续点击 2 次（click_count=2）：**

```
时间轴：
t=0ms     Click 1 开始
          └─ pyautogui.click() → mouseDown + 100ms PAUSE + mouseUp + 100ms PAUSE
t≈200ms   Click 1 结束，记录 _last_click_time = t≈200ms
          返回 RUNNING

t=210ms   下一个 tick（10ms 后）
          检查 elapsed = 210 - 200 = 10ms < click_interval(100ms)
          返回 RUNNING

t=300ms   tick，elapsed = 300 - 200 = 100ms >= click_interval(100ms)
          Click 2 开始 → 同样约 200ms
t≈500ms   Click 2 结束

总耗时：约 500ms（两次点击间隔约 300ms，但 PAUSE 已包含在第一次点击内）
```

**脚本连续按下同一按键 2 次：**

假设录制内容为：
```
KeyDown "space", 1
Delay 30
KeyUp "space", 1
Delay 50
KeyDown "space", 1
Delay 30
KeyUp "space", 1
```

```
时间轴：
t=0ms     KeyDown 1 → pyautogui.keyDown() + 100ms PAUSE
t≈100ms   Delay 30 → time.sleep(30ms)
t≈130ms   KeyUp 1 → pyautogui.keyUp() + 100ms PAUSE
t≈230ms   Delay 50 → time.sleep(50ms)
t≈280ms   KeyDown 2 → pyautogui.keyDown() + 100ms PAUSE
t≈380ms   Delay 30 → time.sleep(30ms)
t≈410ms   KeyUp 2 → pyautogui.keyUp() + 100ms PAUSE
t≈510ms   完成

总耗时：约 510ms
两次 KeyDown 间隔：280ms（100ms PAUSE + 30ms delay + 100ms PAUSE + 50ms delay）
```

**对比结论：**

| 场景 | 两次操作起点间隔 | 总耗时 |
|------|-----------------|--------|
| MouseClickNode click_count=2, interval=100ms | 约 300ms | 约 500ms |
| 脚本连续 2 次按键（含录制延迟 80ms） | 约 280ms | 约 510ms |

表面上看间隔接近，但**实际体感差异远大于此**，原因如下文根因三所述。

### 3.3 根因三：脚本操作粒度更细，PAUSE 触发次数更多

**这是"连续按同一按键远比普通点击连点 2 次更长"的核心原因。**

| 操作类型 | pyautogui 调用次数 | PAUSE 触发次数 | 额外延迟 |
|---------|-------------------|---------------|---------|
| KeyPressNode（action=press, duration=0）×2 | `pyautogui.press()` × 2 | 每次内部 keyDown+keyUp 各 1 次 = **4 次** | 400ms |
| MouseClickNode click_count=2（action=press, duration=0） | `pyautogui.click()` × 2 | 每次内部 mouseDown+mouseUp 各 1 次 = **4 次** | 400ms |
| **脚本连续按键 2 次**（KeyDown+KeyUp × 2） | `pyautogui.keyDown()` × 2 + `pyautogui.keyUp()` × 2 | **4 次** | 400ms |

PAUSE 次数相同，但**脚本额外叠加了录制延迟**（Delay 命令），而普通节点的 `click_interval` 与 PAUSE 是**重叠计算**的：

```
普通节点：  [Click1 + PAUSE≈200ms] → 检查interval(已消耗) → [Click2 + PAUSE≈200ms]
脚本节点：  [KeyDown1 + PAUSE 100ms] → [Delay 30ms] → [KeyUp1 + PAUSE 100ms] → [Delay 50ms] → [KeyDown2 + PAUSE 100ms] → ...
                                        ↑ 额外叠加                    ↑ 额外叠加
```

**普通节点的 click_interval 在 PAUSE 之后检查，如果 PAUSE 已消耗完间隔则无需等待；脚本的 Delay 在两个 PAUSE 之间独立 sleep，完全叠加。**

### 3.4 根因四：脚本独立线程的额外开销

脚本运行在独立线程中，与引擎线程存在以下竞争：

1. **GIL 竞争**：Python GIL 导致线程切换开销，每次 `time.sleep` 唤醒后需要重新获取 GIL
2. **ScriptNode 轮询开销**：引擎每 10ms tick 时，ScriptNode 检查 `executor.is_running`（涉及锁操作）
3. **InputController 实例独立**：脚本创建自己的 `InputController()` 实例，与 `InputControllerManager` 的缓存实例独立，可能导致重复初始化

```python
# bt_utils/script_executor.py:74-79
@property
def input_controller(self):
    if self._input_controller is None:
        from .input_controller_factory import InputController
        self._input_controller = InputController()   # 独立实例
    return self._input_controller
```

### 3.5 根因五：脚本绕过 ExecutionContext 的统一调用路径

脚本直接调用 `input_controller.key_down(key)`，而普通节点通过 `context.execute_key_press()` 调用。两者的差异：

| 方面 | context.execute_key_press() | input_controller.key_down() |
|------|---------------------------|---------------------------|
| 输入引擎选择 | 通过 `InputControllerManager`，支持后台模式 hwnd 注入 | 直接使用 `InputController`，**不支持后台模式** |
| 截图缓存清理 | 调用后 `self._screenshot_cache.clear()` | **不清理** |
| 坐标转换 | 支持（鼠标操作） | 不支持 |
| 窗口切换 | ActionNode 基类统一处理 | 脚本节点 `SKIP_WINDOW_SWITCH = True`，跳过 |

脚本绕过 context 虽然不直接导致延迟，但破坏了架构一致性，使得后续优化难以统一应用。

---

## 4 详细时序对比

### 4.1 单次按键操作时序对比

**普通 KeyPressNode（action=press, duration=0）：**

```
t=0      Engine tick
t=0      KeyPressNode._execute_action()
t=0      context.execute_key_press(key, "press", 0)
t=0      pyautogui.press(key)
t=0        └─ keyDown(key)        # 实际按键
t=0        └─ time.sleep(0.1)     # PAUSE #1
t≈100      └─ keyUp(key)          # 实际按键
t≈100      └─ time.sleep(0.1)     # PAUSE #2
t≈200    返回 SUCCESS
t≈200    Engine._stop_event.wait(0.01)  # tick 间隔
t≈210    下一个 tick（执行下一个节点）

单次按键总耗时：约 200ms
```

**脚本单次按键（KeyDown + Delay + KeyUp）：**

```
t=0      KeyDown "space", 1
t=0      pyautogui.keyDown(key)
t=0        └─ time.sleep(0.1)     # PAUSE #1
t≈100   Delay 30
t≈100     └─ time.sleep(0.03)     # 录制延迟
t≈130   KeyUp "space", 1
t≈130   pyautogui.keyUp(key)
t≈130     └─ time.sleep(0.1)      # PAUSE #2
t≈230   完成

单次按键总耗时：约 230ms（比普通节点多 30ms 录制延迟）
```

### 4.2 连续两次按键时序对比

**普通方式：两个 KeyPressNode 在 SequenceNode 中（childinterval=0）**

```
t=0      Tick: KeyPressNode1 执行 → pyautogui.press() ≈ 200ms → SUCCESS
t≈200    同一 Tick 继续（SequenceNode while 循环）：KeyPressNode2 执行 → ≈ 200ms → SUCCESS
t≈400    Tick 结束

两次按键总耗时：约 400ms
两次按键起点间隔：约 200ms（即第一个 press 的耗时）
```

**普通方式：MouseClickNode click_count=2, click_interval=100**

```
t=0      Tick: Click 1 → pyautogui.click() ≈ 200ms → RUNNING（_last_click_time≈200）
t≈210    Tick: elapsed=10 < 100 → RUNNING
...
t≈300    Tick: elapsed=100 >= 100 → Click 2 → ≈ 200ms → SUCCESS

两次点击总耗时：约 500ms
两次点击起点间隔：约 300ms（PAUSE 200ms + interval 100ms）
```

**脚本方式：连续两次按键（含录制延迟）**

```
t=0      KeyDown1 + 100ms PAUSE
t≈100    Delay 30ms
t≈130    KeyUp1 + 100ms PAUSE
t≈230    Delay 50ms
t≈280    KeyDown2 + 100ms PAUSE
t≈380    Delay 30ms
t≈410    KeyUp2 + 100ms PAUSE
t≈510    完成

两次按键总耗时：约 510ms
两次 KeyDown 起点间隔：约 280ms（100 + 30 + 100 + 50）
```

### 4.3 时序对比总结

| 场景 | 总耗时 | 两次操作起点间隔 | 额外延迟来源 |
|------|--------|-----------------|------------|
| 两个 KeyPressNode（Sequence） | ~400ms | ~200ms | 4×PAUSE |
| MouseClickNode click_count=2 | ~500ms | ~300ms | 4×PAUSE（interval 与 PAUSE 部分重叠） |
| 脚本连续 2 次按键 | ~510ms | ~280ms | 4×PAUSE + 录制延迟(80ms) |

> 注：以上为 PyAutoGUI 引擎的理论值。实际 PAUSE 可能因 pyautogui 版本不同而有所差异（`press()` 内部是否对 `keyDown`/`keyUp` 单独应用 PAUSE 取决于版本）。但核心结论不变：**脚本路径叠加了录制延迟，而普通节点的间隔可与 PAUSE 重叠**。

---

## 5 优化建议

### 5.1 短期优化（低风险，立即可做）

#### 优化一：在 PyAutoGUIInput 中禁用 pyautogui.PAUSE（最高优先级）

**问题：** `PyAutoGUIInput` 类初始化时未设置 `pyautogui.PAUSE = 0`，导致每次 pyautogui 调用附加 100ms 延迟。

**修复位置：** [input_controller_factory.py:54-61](file:///d:/workspace/autodoor_behavior_tree/bt_utils/input_controller_factory.py#L54)

```python
class PyAutoGUIInput(BaseInputController):
    def __init__(self, app=None):
        self._available = True
        self.app = app
        self._simulate_lock = threading.Lock()
        self._simulating = False
        
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0    # ✅ 新增：禁用全局 PAUSE，延迟由节点/脚本自行控制
```

**预期效果：**
- 单次 pyautogui 调用减少 100ms
- 脚本回放速度大幅提升，接近录制时序
- 普通节点执行速度也同步提升

**风险评估：**
- 低风险。`pyautogui.PAUSE` 的设计初衷是防止操作过快，但本系统已有 DelayNode、click_interval、childinterval 等显式延迟控制机制
- TextInputNode 已经禁用 PAUSE 且运行正常，证明此方案可行
- 需要回归测试所有使用 pyautogui 的节点

#### 优化二：脚本 Delay 命令使用更细粒度的 sleep

**问题：** 当前 Delay 使用 100ms 分段 sleep，对短延迟（<100ms）无影响，但对停止响应有延迟。

**修复位置：** [script_executor.py:271-277](file:///d:/workspace/autodoor_behavior_tree/bt_utils/script_executor.py#L271)

```python
elif command["type"] == "delay":
    delay_time = command["time"] / 1000
    elapsed = 0
    # 优化：使用 10ms 分段，提升停止响应速度
    while elapsed < delay_time and self.is_running:
        sleep_time = min(0.01, delay_time - elapsed)  # 100ms → 10ms
        time.sleep(sleep_time)
        elapsed += sleep_time
```

**预期效果：** 停止脚本时响应延迟从最长 100ms 降至最长 10ms。

### 5.2 中期优化（中等风险，建议规划）

#### 优化三：ScriptExecutor 使用 InputControllerManager 统一输入管理

**问题：** ScriptExecutor 创建独立的 `InputController()` 实例，绕过 `InputControllerManager`，导致：
1. 后台模式（bg）不可用
2. 与普通节点的输入引擎配置可能不一致
3. 无法享受 InputControllerManager 的缓存

**修复方向：** ScriptExecutor 应通过 ExecutionContext 获取输入引擎，而非自行创建。

```python
# bt_utils/script_executor.py
class ScriptExecutor:
    def __init__(self, max_workers: int = 4, context=None):
        # ...
        self._context = context  # 接收 ExecutionContext
    
    @property
    def input_controller(self):
        if self._context is not None:
            # 优先使用 context 的输入管理器
            manager = self._context._get_input_manager()
            # 根据操作类型获取对应引擎
            return manager
        # 降级：独立创建
        if self._input_controller is None:
            from .input_controller_factory import InputController
            self._input_controller = InputController()
        return self._input_controller
```

#### 优化四：脚本 keydown/keyup 命令支持合并为 press 语义

**问题：** 脚本将一次按键拆分为 KeyDown + KeyUp 两个独立命令，各自触发 pyautogui PAUSE。

**修复方向：** 在 `_parse_script` 阶段或 `_execute_command` 阶段，识别相邻的 KeyDown+Delay+KeyUp 模式，合并为单次 `key_press(action="press")` 调用。

```python
def _execute_command(self, command: dict, pressed_keys: set) -> None:
    if command["type"] == "keydown":
        key = command["key"]
        for _ in range(command["count"]):
            if key not in pressed_keys:
                # 优化：使用 key_press 而非 key_down，减少 PAUSE 次数
                # （需配合优化一禁用 PAUSE 后效果更佳）
                self.input_controller.key_down(key)
                pressed_keys.add(key)
```

> 注：此优化在禁用 PAUSE（优化一）后收益减小，但仍有架构统一价值。

#### 优化五：脚本执行引入非阻塞模式

**问题：** 脚本全阻塞执行，Delay 期间无法被引擎中断（只能靠 100ms 分段检查 `is_running`）。

**修复方向：** 将 ScriptExecutor 改造为基于事件驱动的非阻塞模式，与引擎 tick 对齐：

```python
# 概念设计：将脚本命令改为状态机式执行
class ScriptCommandExecutor:
    def tick(self, context) -> bool:
        """每个 tick 调用，返回是否完成"""
        if self._current_command is None:
            self._next_command()
        
        if self._current_command.type == "delay":
            if self._delay_start is None:
                self._delay_start = time.time()
            elapsed = (time.time() - self._delay_start) * 1000
            if elapsed < self._current_command.time:
                return False  # 未完成
            self._next_command()
        elif self._current_command.type == "keydown":
            context.execute_key_press(self._current_command.key, "down", 0)
            self._next_command()
        # ...
        return self._current_command is None
```

**预期效果：**
- 脚本执行与引擎 tick 对齐，停止/暂停响应即时
- 脚本通过 context 调用输入，支持后台模式、坐标转换等
- 架构统一，降低维护成本

### 5.3 长期优化（高价值，建议纳入路线图）

#### 优化六：统一录制与回放的时间模型

**问题根因：** 录制使用 pynput（无 PAUSE），回放使用 pyautogui（有 PAUSE），时间模型不一致。

**方案：**
1. 录制时记录"净操作时间"（去除 pyautogui PAUSE 影响）
2. 回放时基于"净操作时间"重建时序，PAUSE 由系统统一管理（禁用后由显式 Delay 控制）
3. 引入时间戳对齐机制，确保回放时序与录制时序一致

#### 优化七：ScriptNode 与 ScriptExecutor 架构重构

将 ScriptExecutor 从独立线程阻塞模型重构为引擎 tick 驱动模型：

```
当前架构：
  Engine Thread ──tick──> ScriptNode (检查 is_running) ──> return RUNNING
  Script Thread ──block──> keyDown → sleep → keyUp → sleep → ...

目标架构：
  Engine Thread ──tick──> ScriptNode.tick()
                            └── ScriptCommandExecutor.tick(context)
                                  ├── 执行当前命令（非阻塞）
                                  ├── 管理命令指针
                                  └── 返回 RUNNING / SUCCESS
```

**收益：**
- 消除独立线程的 GIL 竞争
- 统一输入调用路径（通过 context）
- 即时响应停止/暂停
- 支持后台模式、坐标转换等高级特性
- 代码与普通节点架构一致，降低维护成本

---

## 6 验证方案

### 6.1 验证 pyautogui.PAUSE 影响

```python
# 测试脚本：测量 PAUSE 影响
import pyautogui
import time

# 默认 PAUSE=0.1
start = time.time()
pyautogui.keyDown('space')
t1 = time.time()
pyautogui.keyUp('space')
t2 = time.time()
print(f"PAUSE=0.1: keyDown={t1-start:.3f}s, keyUp={t2-t1:.3f}s, total={t2-start:.3f}s")

# 禁用 PAUSE
pyautogui.PAUSE = 0
start = time.time()
pyautogui.keyDown('space')
t1 = time.time()
pyautogui.keyUp('space')
t2 = time.time()
print(f"PAUSE=0:   keyDown={t1-start:.3f}s, keyUp={t2-t1:.3f}s, total={t2-start:.3f}s")
```

**预期结果：** PAUSE=0.1 时每次调用约多 100ms。

### 6.2 验证脚本回放延迟

1. 录制一段固定时序的脚本（KeyDown → Delay 50 → KeyUp → Delay 100 → KeyDown → Delay 50 → KeyUp）
2. 回放并使用高精度计时器记录实际时序
3. 对比录制时序与回放时序的差异
4. 应用优化一（禁用 PAUSE）后重新验证

### 6.3 回归测试

应用优化后需验证：
- [ ] KeyPressNode 各 action 模式（press/down/up）正常
- [ ] MouseClickNode 各 click_count 和 click_interval 组合正常
- [ ] MouseMoveNode 移动/拖拽正常
- [ ] ScriptNode 脚本回放时序与录制接近
- [ ] DD 引擎模式不受影响（DD 无 PAUSE 机制）
- [ ] 后台模式（bg）不受影响

---

## 7 结论

### 7.1 核心结论

| 问题 | 根因 | 影响程度 |
|------|------|---------|
| 脚本回放间隔比记录的 delay 更长 | **pyautogui.PAUSE 默认 100ms**，录制用 pynput 无此延迟，回放用 pyautogui 每次调用附加 100ms | 🔴 主要原因，每次操作多 100-200ms |
| 连续按同一按键间隔远大于普通点击连点 2 次 | **脚本的录制延迟与 PAUSE 串行叠加**，而普通节点的 click_interval 在 PAUSE 之后检查可重叠 | 🟠 次要原因，叠加效应使差距放大 |
| 脚本整体执行偏慢 | **独立线程阻塞执行 + 绕过 context + 独立 InputController 实例** | 🟡 架构问题，影响一致性和可维护性 |

### 7.2 优化优先级

| 优先级 | 优化项 | 预期收益 | 风险 |
|--------|-------|---------|------|
| P0 | 禁用 pyautogui.PAUSE（优化一） | 单次操作减少 100-200ms，脚本回放接近录制时序 | 低（TextInputNode 已验证） |
| P1 | Delay 分段细化至 10ms（优化二） | 停止响应从 100ms 降至 10ms | 极低 |
| P2 | ScriptExecutor 使用 context 输入（优化三） | 支持后台模式，统一架构 | 中（需重构输入调用路径） |
| P3 | 脚本非阻塞改造（优化五/七） | 即时停止/暂停，架构统一 | 中高（需重构 ScriptExecutor） |

### 7.3 建议实施路径

1. **立即实施优化一**（禁用 PAUSE）——这是投入产出比最高的优化，一行代码解决核心问题
2. **同步实施优化二**（Delay 细化）——低风险提升停止响应
3. **规划优化三~七**——纳入后续迭代，逐步统一脚本与普通节点的执行架构

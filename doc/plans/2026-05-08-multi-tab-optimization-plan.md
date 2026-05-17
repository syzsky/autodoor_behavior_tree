# 多行为树并行功能优化方案

> 生成日期：2026-05-08
> 基于代码审查报告中的5个遗留问题

---

## 问题1：ScriptNode 全局执行器池隔离

### 问题描述

`ScriptNode.clear_executor_pool()` 是类方法，会清除所有 ScriptNode 实例的执行器池。当停止一个 Tab 的行为树时，`engine.stop()` 调用 `clear_executor_pool()`，会导致其他正在运行的 Tab 中的脚本节点也被强制停止。

### 影响范围

- `bt_nodes/actions/script.py` — `_executor_pool` 是类变量，`clear_executor_pool()` 是类方法
- `bt_core/engine.py` — `stop()` 方法中调用了 `ScriptNode.clear_executor_pool()`

### 优化方案

将执行器池从类级别改为实例级别，每个 `BehaviorTreeEngine` 持有独立的执行器池。

#### 修改文件：`bt_nodes/actions/script.py`

```python
# 改前（类级别）
class ScriptNode:
    _executor_pool: Dict[str, ScriptExecutor] = {}
    _pool_lock = threading.Lock()

# 改后（实例级别）
class ScriptNode:
    _global_pool_lock = threading.Lock()
    
    def __init__(self, ...):
        ...
        self._local_executor: Optional[ScriptExecutor] = None
    
    @property
    def executor(self) -> ScriptExecutor:
        if self._local_executor is None or not self._local_executor.is_running:
            self._local_executor = ScriptExecutor()
        return self._local_executor
    
    def stop_executor(self):
        """停止当前节点的执行器（实例级别）"""
        if self._local_executor and self._local_executor.is_running:
            try:
                self._local_executor.stop_script()
            except Exception:
                pass
            self._local_executor = None
    
    @classmethod
    def clear_executor_pool(cls) -> None:
        """保留兼容性，但改为空操作或仅清理全局残留"""
        pass
```

#### 修改文件：`bt_core/engine.py`

```python
def stop(self):
    ...
    # 改前：ScriptNode.clear_executor_pool()
    # 改后：遍历当前引擎的所有节点，逐个停止
    self._stop_all_script_nodes()

def _stop_all_script_nodes(self):
    """停止当前引擎中所有 ScriptNode 的执行器"""
    from bt_nodes.actions.script import ScriptNode
    if self._root_node:
        for node in self._iter_all_nodes(self._root_node):
            if isinstance(node, ScriptNode):
                node.stop_executor()

def _iter_all_nodes(self, node):
    """遍历所有节点"""
    yield node
    if hasattr(node, 'children'):
        for child in node.children:
            yield from self._iter_all_nodes(child)
```

### 验证方法

1. 打开两个 Tab，各自加载包含脚本节点的行为树
2. 同时运行两个 Tab
3. 停止其中一个 Tab
4. 验证另一个 Tab 的脚本节点仍在正常执行

---

## 问题2：LogManager 全局状态隔离

### 问题描述

`LogManager` 是单例，`set_stopped(True)` 和 `clear_success_failure_entries()` 是全局操作。停止一个 Tab 时调用这些方法，会影响其他正在运行的 Tab 的日志输出——其他 Tab 的成功/失败日志会被抑制。

### 影响范围

- `bt_utils/log_manager.py` — `_stopped` 是实例变量，但 LogManager 是单例
- `bt_gui/bt_editor/editor.py` — `_handle_tab_stop` 和 `_stop_running` 中调用 `set_stopped(True)`

### 优化方案

将 `_stopped` 标志从全局改为按 Tab 管理，使用集合记录已停止的 Tab。

#### 修改文件：`bt_utils/log_manager.py`

```python
class LogManager:
    def __init__(self):
        ...
        self._stopped = False
        self._stopped_tabs: set = set()  # 新增：按 Tab 记录停止状态
    
    def set_stopped(self, stopped: bool, tab_name: str = None) -> None:
        if tab_name:
            if stopped:
                self._stopped_tabs.add(tab_name)
            else:
                self._stopped_tabs.discard(tab_name)
            # 只有所有 Tab 都停止时才设置全局停止
            self._stopped = len(self._stopped_tabs) > 0
        else:
            self._stopped = stopped
            if stopped:
                self._stopped_tabs.clear()  # 全局停止时清空 Tab 级别
    
    def is_tab_stopped(self, tab_name: str) -> bool:
        """检查指定 Tab 是否处于停止状态"""
        return tab_name in self._stopped_tabs
    
    def _should_suppress_log(self, entry: LogEntry) -> bool:
        """判断是否应抑制该日志"""
        if entry.tab_name and entry.tab_name in self._stopped_tabs:
            return True
        if self._stopped and not entry.tab_name:
            return True
        return False
```

#### 修改文件：`bt_gui/bt_editor/editor.py`

```python
def _handle_tab_run(self, tab_id: str):
    ...
    LogManager.instance().set_stopped(False, tab_name=instance.name)
    ...

def _handle_tab_stop(self, tab_id: str):
    ...
    LogManager.instance().set_stopped(True, tab_name=instance.name)
    # 不再调用 clear_success_failure_entries()，改为只清除该 Tab 的日志
    LogManager.instance().clear_tab_entries(instance.name)
    ...
```

### 验证方法

1. 打开两个 Tab，同时运行
2. 停止其中一个 Tab
3. 验证另一个 Tab 的日志仍然正常输出成功/失败信息

---

## 问题3：CrashRecovery 多 Tab 支持

### 问题描述

`CrashRecoveryHandler` 通过 `get_data_func` 回调获取崩溃数据，当前只保存单个活动 Tab 的数据。多 Tab 场景下，非活动 Tab 的数据在崩溃时丢失。

### 影响范围

- `bt_utils/crash_recovery.py` — `_get_data_func` 只返回单个数据
- `bt_gui/bt_editor/editor.py` — 初始化 CrashRecovery 时传入的回调函数

### 优化方案

修改 `CrashRecoveryHandler` 支持多数据源，崩溃时保存所有 Tab 的数据。

#### 修改文件：`bt_utils/crash_recovery.py`

```python
class CrashRecoveryHandler:
    def __init__(
        self,
        get_data_func: Callable[[], Dict[str, Any]] = None,
        get_all_tabs_func: Callable[[], List[Dict[str, Any]]] = None,  # 新增
        recovery_dir: str = "data/recovery",
        log_func: Optional[Callable[[str], None]] = None
    ):
        self._get_data_func = get_data_func
        self._get_all_tabs_func = get_all_tabs_func  # 新增
        ...
    
    def _save_crash_recovery(self, ...):
        data = {}
        
        # 保存活动 Tab 数据（兼容旧接口）
        if self._get_data_func:
            data = self._get_data_func()
        
        # 保存所有 Tab 数据
        if self._get_all_tabs_func:
            all_tabs = self._get_all_tabs_func()
            if all_tabs:
                data["all_tabs"] = all_tabs
        
        if not data:
            return None
        
        # ... 保存到文件 ...
```

#### 修改文件：`bt_gui/bt_editor/editor.py`

```python
def _init_crash_recovery(self):
    def get_data():
        ...
    
    def get_all_tabs_data():
        tabs = []
        for tab_id, instance in self.tab_manager._trees.items():
            tabs.append({
                "tab_id": tab_id,
                "name": instance.name,
                "file_path": instance.file_path,
                "project_root": instance.project_root,
                "modified": instance.modified,
                "tree_data": instance.canvas.get_tree_data() if instance.canvas else None,
                "is_active": self.tab_manager.active_tab_id == tab_id
            })
        return tabs
    
    self._crash_recovery_handler = CrashRecoveryHandler(
        get_data_func=get_data,
        get_all_tabs_func=get_all_tabs_data,
        ...
    )
```

#### 修改文件：`bt_gui/app.py`

在 `_restore_last_file` 中增加崩溃恢复检测：

```python
def _restore_from_crash(self, crash_data):
    """从崩溃数据恢复所有 Tab"""
    all_tabs = crash_data.get("all_tabs", [])
    if all_tabs:
        for tab_info in all_tabs:
            # 恢复每个 Tab
            ...
    else:
        # 兼容旧格式，恢复单个文件
        ...
```

### 验证方法

1. 打开多个 Tab，修改内容但不保存
2. 模拟崩溃（kill 进程）
3. 重新启动应用
4. 验证所有 Tab 的数据都被恢复

---

## 问题4：gui_tab_manager.py 中 start_tab/stop_tab 方法标记

### 问题描述

`GuiTabManager.start_tab()` 直接调用 `instance.engine.start(instance.context)`，但没有反序列化树数据。如果被外部调用，会导致运行空树（root_node 为 None）。`stop_tab()` 也有类似问题，缺少完整的停止逻辑（日志、输入释放等）。

### 影响范围

- `bt_gui/bt_editor/gui_tab_manager.py` — `start_tab`/`stop_tab` 方法
- 外部模块可能误调用这些方法

### 优化方案

将 `start_tab`/`stop_tab` 标记为内部方法，并添加警告注释。同时修正实现，使其不再直接操作引擎，而是通过回调委托给 Editor。

#### 修改文件：`bt_gui/bt_editor/gui_tab_manager.py`

```python
class GuiTabManager(MultiTreeManager):
    def __init__(self, shared_blackboard: bool = False):
        super().__init__(shared_blackboard)
        ...
        # 新增：运行/停止委托回调
        self.on_tab_start_request: Optional[Callable[[str], bool]] = None
        self.on_tab_stop_request: Optional[Callable[[str], bool]] = None
    
    def start_tab(self, tab_id: str) -> bool:
        """请求启动指定 Tab 的行为树
        
        ⚠️ 内部方法：不应由外部直接调用
        启动行为树需要反序列化树数据、创建引擎等复杂操作，
        此方法委托给 Editor 的 on_tab_start_request 回调处理。
        """
        if self.on_tab_start_request:
            return self.on_tab_start_request(tab_id)
        
        # 兼容回退：直接启动（不推荐，可能运行空树）
        instance = self._trees.get(tab_id)
        if not instance or instance.status == "running":
            return False
        instance.engine.start(instance.context)
        self.update_tab_status(tab_id, True)
        return True
    
    def stop_tab(self, tab_id: str) -> bool:
        """请求停止指定 Tab 的行为树
        
        ⚠️ 内部方法：不应由外部直接调用
        停止行为树需要日志记录、输入释放等操作，
        此方法委托给 Editor 的 on_tab_stop_request 回调处理。
        """
        if self.on_tab_stop_request:
            return self.on_tab_stop_request(tab_id)
        
        # 兼容回退：直接停止（不推荐，缺少完整停止逻辑）
        instance = self._trees.get(tab_id)
        if not instance or instance.status != "running":
            return False
        instance.engine.stop()
        self.update_tab_status(tab_id, False)
        return True
```

#### 修改文件：`bt_gui/bt_editor/editor.py`

```python
# 在创建 tab_manager 后设置委托回调
self.tab_manager.on_tab_start_request = self._handle_tab_run
self.tab_manager.on_tab_stop_request = self._handle_tab_stop
```

### 验证方法

1. 确认 `start_tab`/`stop_tab` 通过委托回调正确工作
2. 确认直接调用 `start_tab` 时走兼容回退路径不会崩溃

---

## 问题5：Tab ID 生成策略优化

### 问题描述

当前 Tab ID 使用 `f"tab_{len(self.tab_manager._trees) + 1}"` 生成，关闭 Tab 后重新创建可能产生重复 ID。例如：创建 tab_1、tab_2，关闭 tab_1 后再创建，新 Tab 也是 tab_2，与现有 tab_2 冲突。

### 影响范围

- `bt_gui/bt_editor/editor.py` — `_create_new_tab` 方法中的 tab_id 生成

### 优化方案

使用递增计数器生成唯一 Tab ID，计数器只增不减，确保 ID 全局唯一。

#### 修改文件：`bt_gui/bt_editor/editor.py`

```python
class BehaviorTreeEditor(ctk.CTkFrame):
    _tab_counter = 0  # 类级别递增计数器
    
    def _create_new_tab(self, name: str, project_root: str = None,
                        file_path: str = None) -> str:
        BehaviorTreeEditor._tab_counter += 1
        tab_id = f"tab_{BehaviorTreeEditor._tab_counter}"
        
        # ... 其余逻辑不变 ...
```

#### 修改文件：`bt_gui/bt_editor/gui_tab_manager.py`

添加 ID 唯一性校验：

```python
def add_tab(self, tab_id: str, instance: TreeInstance) -> TreeInstance:
    with self._tab_lock:
        if tab_id in self._trees:
            raise ValueError(f"Tab ID '{tab_id}' 已存在，请使用唯一 ID")
        
        instance.tab_id = tab_id
        self._trees[tab_id] = instance
        ...
```

### 验证方法

1. 创建 Tab → 关闭 Tab → 再创建 Tab
2. 验证新 Tab 的 ID 不与已有 Tab 重复
3. 验证多次创建/关闭后 ID 持续递增

---

## 实施优先级

| 优先级 | 问题 | 影响程度 | 实施复杂度 |
|--------|------|---------|-----------|
| P0 | 问题5：Tab ID 重复 | 高（可能导致数据错乱） | 低 |
| P1 | 问题1：ScriptNode 执行器池隔离 | 中（多 Tab 并行时互相影响） | 中 |
| P1 | 问题2：LogManager 全局状态隔离 | 中（多 Tab 并行时日志丢失） | 中 |
| P2 | 问题4：start_tab/stop_tab 标记 | 低（当前无外部调用） | 低 |
| P2 | 问题3：CrashRecovery 多 Tab 支持 | 低（崩溃场景较少） | 中 |

## 实施建议

1. **问题5** 可立即修复，改动最小，风险最低
2. **问题1 和问题2** 建议一起实施，两者都涉及从全局状态改为按 Tab 隔离
3. **问题4** 可在问题1/2实施时顺带完成
4. **问题3** 可作为后续迭代，优先级较低

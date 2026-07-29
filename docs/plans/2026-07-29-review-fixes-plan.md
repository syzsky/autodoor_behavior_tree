# 审查问题修复实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复消息总线与外部系统集成、插件系统及 CLI 工具审查中发现的 17 个问题（4 高 + 13 中优先级）

**Architecture:** 分层修复 — Phase 0 提交现有变更，Tier 1 按模块分组修复 4 个高优先级问题，Tier 2 按主题分组修复 13 个中优先级问题。每个 Step 遵循 TDD 流程。

**Tech Stack:** Python 3.10+, threading (RLock), asyncio (Queue), subprocess, pytest, argparse

**设计文档:** [2026-07-29-review-fixes-design.md](./2026-07-29-review-fixes-design.md)

---

## Phase 0: 提交现有未提交变更

**Files:**
- 全部 git status 中已修改/未跟踪的文件

**Step 1: 审查当前未提交变更**

Run: `git status`
Expected: 列出所有修改和未跟踪文件

**Step 2: 按逻辑分组提交**

```bash
# 提交 1: 插件系统增强
git add bt_plugins/loader.py bt_plugins/builtin/example/main.py bt_gui/plugin_panel.py bt_gui/app.py cli.py tests/test_plugin_loader.py
git commit -m "feat: plugin system enhancements (loader, GUI panel, CLI integration)"

# 提交 2: GUI 主题与样式调整
git add bt_gui/bt_editor/constants.py bt_gui/bt_editor/palette.py bt_gui/bt_editor/property.py bt_gui/theme.py bt_gui/settings_tab.py
git commit -m "style: GUI theme and editor refinements"

# 提交 3: 调度器与 CLI 命令
git add bt_cli/scheduler.py bt_cli/commands/schedule.py
git commit -m "feat: scheduler and schedule CLI command updates"

# 提交 4: 文档与计划
git add docs/cli-manual.md docs/plugin-guide.md docs/reports/ docs/plans/2026-07-28-plugin-system-and-cli-design.md docs/plans/2026-07-28-plugin-system-and-cli.md docs/plans/2026-07-28-plugin-system-enhancement-plan.md docs/plans/2026-07-29-review-fixes-plan.md
git commit -m "docs: add plugin guide, CLI manual, review reports, and plans"

# 提交 5: 插件示例与测试
git add plugins/ tests/test_cli_commands.py tests/test_plugin_integration.py tests/test_plugin_panel_ui.py tests/test_scheduler.py
git commit -m "test: add plugin examples and integration tests"

# 提交 6: 删除调试日志
git rm debug_log_20260727_122228.txt
git commit -m "chore: remove debug log file"
```

**Step 3: 验证工作区干净**

Run: `git status`
Expected: `nothing to commit, working tree clean`

---

## Tier 1: 高优先级修复

### Task 1: remote.py 数据解析修复（B1, B2, R1）

**Files:**
- Modify: `bt_cli/commands/remote.py`
- Modify: `bt_servers/rest_server.py:110-112`
- Test: `tests/test_remote_commands.py`

**Step 1: 编写失败测试**

```python
# tests/test_remote_commands.py
"""remote 命令数据解析测试"""
import json
from unittest.mock import patch, MagicMock


def test_do_status_parses_version():
    """测试 status 命令正确解析 version 字段"""
    from bt_cli.commands.remote import _do_status
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "version": "1.0.0"}
    with patch("requests.get", return_value=mock_resp):
        _do_status("http://localhost:8080", {}, MagicMock())


def test_do_trees_parses_wrapped_list():
    """测试 trees 命令正确解析 {"trees": [...]} 包装结构"""
    from bt_cli.commands.remote import _do_trees
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "trees": [
            {"tree_id": "tree1", "status": "running"},
            {"tree_id": "tree2", "status": "stopped"},
        ]
    }
    with patch("requests.get", return_value=mock_resp):
        _do_trees("http://localhost:8080", {}, MagicMock())


def test_do_nodes_parses_wrapped_list():
    """测试 nodes 命令正确解析 {"nodes": [...]} 包装结构"""
    from bt_cli.commands.remote import _do_nodes
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "nodes": [
            {"node_id": "n1", "node_type": "SequenceNode", "name": "root", "status": "idle"}
        ]
    }
    args = MagicMock()
    args.tree_id = "tree1"
    with patch("requests.get", return_value=mock_resp):
        _do_nodes("http://localhost:8080", {}, args)


def test_do_trees_empty_list():
    """测试 trees 命令空列表处理"""
    from bt_cli.commands.remote import _do_trees
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"trees": []}
    with patch("requests.get", return_value=mock_resp):
        _do_trees("http://localhost:8080", {}, MagicMock())
```

**Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_remote_commands.py -v`
Expected: FAIL — `_do_trees` 遍历字典而非列表，`_do_nodes` 同样

**Step 3: 修复 remote.py**

```python
# bt_cli/commands/remote.py — 修改 _do_status, _do_trees, _do_nodes

def _do_status(base_url, headers, args):
    """查询远程状态"""
    import requests
    resp = requests.get(f"{base_url}/api/v1/health", headers=headers, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"服务状态: {data.get('status', 'unknown')}")
        print(f"版本: {data.get('version', 'N/A')}")
    else:
        print(f"查询失败: {resp.status_code}")


def _do_trees(base_url, headers, args):
    """列出远程行为树"""
    import requests
    resp = requests.get(f"{base_url}/api/v1/trees", headers=headers, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        trees = data.get("trees", []) if isinstance(data, dict) else data
        if not trees:
            print("无行为树")
            return
        print(f"行为树列表 ({len(trees)} 个):")
        for tree in trees:
            tree_id = tree.get("tree_id", "N/A")
            status = tree.get("status", "unknown")
            print(f"  - {tree_id}: {status}")
    else:
        print(f"查询失败: {resp.status_code}")


def _do_nodes(base_url, headers, args):
    """查询远程节点"""
    import requests
    if not args.tree_id:
        print("错误: 需要 --tree-id")
        sys.exit(1)
    resp = requests.get(f"{base_url}/api/v1/trees/{args.tree_id}/nodes", headers=headers, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        nodes = data.get("nodes", []) if isinstance(data, dict) else data
        print(f"节点列表 ({len(nodes)} 个):")
        for node in nodes:
            node_id = node.get("node_id", "N/A")
            node_type = node.get("node_type", "N/A")
            name = node.get("name", "")
            status = node.get("status", "unknown")
            print(f"  - [{node_type}] {name} ({node_id}): {status}")
    else:
        print(f"查询失败: {resp.status_code}")
```

**Step 4: 在 rest_server.py health 端点添加 version 字段**

```python
# bt_servers/rest_server.py — 修改 health 端点
@self.app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
```

**Step 5: 运行测试验证通过**

Run: `python -m pytest tests/test_remote_commands.py -v`
Expected: PASS

**Step 6: 回归测试**

Run: `python -m pytest tests/test_rest_server.py tests/test_remote_commands.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add bt_cli/commands/remote.py bt_servers/rest_server.py tests/test_remote_commands.py
git commit -m "fix: correct data parsing in remote CLI commands and add version to health endpoint"
```

---

### Task 2: PluginLoader 线程安全（A1）

**Files:**
- Modify: `bt_plugins/loader.py`
- Test: `tests/test_plugin_loader_threadsafe.py`

**Step 1: 编写失败测试**

```python
# tests/test_plugin_loader_threadsafe.py
"""PluginLoader 线程安全测试"""
import threading
import os
import tempfile
import json
from unittest.mock import MagicMock


def test_concurrent_load_and_start():
    """测试并发 load_plugin + start_plugin 无竞态"""
    from bt_plugins.loader import PluginLoader
    from bt_plugins.base import PluginContext

    context = PluginContext()
    loader = PluginLoader(context)

    # 创建多个模拟插件目录
    errors = []
    def load_and_start(plugin_name):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                plugin_dir = os.path.join(tmpdir, plugin_name)
                os.makedirs(plugin_dir)
                manifest = {
                    "name": plugin_name,
                    "display_name": plugin_name,
                    "version": "1.0.0",
                    "author": "test",
                    "description": "test plugin",
                    "entry": "main.py",
                    "class": "TestPlugin",
                }
                with open(os.path.join(plugin_dir, "plugin.json"), "w") as f:
                    json.dump(manifest, f)
                with open(os.path.join(plugin_dir, "main.py"), "w") as f:
                    f.write("""
from bt_plugins.base import BasePlugin
class TestPlugin(BasePlugin):
    pass
""")
                loader.load_plugin(plugin_dir)
                loader.start_plugin(plugin_name)
        except Exception as e:
            errors.append(str(e))

    threads = []
    for i in range(5):
        t = threading.Thread(target=load_and_start, args=(f"plugin_{i}",))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"并发错误: {errors}"
    assert len(loader.list_plugins()) == 5


def test_concurrent_list_during_modify():
    """测试在修改过程中并发查询"""
    from bt_plugins.loader import PluginLoader
    from bt_plugins.base import PluginContext

    context = PluginContext()
    loader = PluginLoader(context)

    errors = []
    def list_repeatedly():
        try:
            for _ in range(100):
                loader.list_plugins()
                loader.is_started("nonexistent")
        except Exception as e:
            errors.append(str(e))

    def modify_repeatedly():
        try:
            for _ in range(100):
                loader.unload_plugin("nonexistent")
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=list_repeatedly)
    t2 = threading.Thread(target=modify_repeatedly)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"并发查询错误: {errors}"
```

**Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_plugin_loader_threadsafe.py -v`
Expected: 可能 FAIL 或随机错误（竞态条件）

**Step 3: 在 PluginLoader 中添加线程安全锁**

在 `bt_plugins/loader.py` 中：
- `__init__` 添加 `self._lock = threading.RLock()`
- 所有公共方法用 `with self._lock:` 包裹

具体修改：

```python
# bt_plugins/loader.py — __init__ 中添加
import threading

class PluginLoader:
    def __init__(self, context: PluginContext):
        self._context = context
        self._lock = threading.RLock()  # 新增
        self._plugins: Dict[str, BasePlugin] = {}
        # ... 其余不变

    # 每个公共方法添加 with self._lock:
    def load_plugin(self, plugin_dir: str) -> bool:
        with self._lock:
            # ... 原有实现

    def unload_plugin(self, name: str) -> None:
        with self._lock:
            # ... 原有实现

    def start_plugin(self, name: str) -> bool:
        with self._lock:
            # ... 原有实现

    def stop_plugin(self, name: str) -> None:
        with self._lock:
            # ... 原有实现

    def start_all(self) -> None:
        with self._lock:
            # ... 原有实现

    def stop_all(self) -> None:
        with self._lock:
            # ... 原有实现

    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        with self._lock:
            return self._plugin_infos.get(name)

    def list_plugins(self) -> List[PluginInfo]:
        with self._lock:
            return list(self._plugin_infos.values())

    def is_started(self, name: str) -> bool:
        with self._lock:
            plugin = self._plugins.get(name)
            return plugin is not None and plugin._started

    def get_registered_display_info(self) -> Dict[str, dict]:
        with self._lock:
            return dict(self._registered_display_info)

    def get_registered_schemas(self) -> Dict[str, list]:
        with self._lock:
            return dict(self._registered_schemas)

    def get_plugin_config_schema(self, name: str) -> dict:
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin:
                return {}
            try:
                return plugin.get_config_schema() or {}
            except Exception as e:
                print(f"[PluginLoader] 获取插件配置 schema 失败 {name}: {e}")
                return {}
```

**Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_plugin_loader_threadsafe.py -v`
Expected: PASS

**Step 5: 回归测试**

Run: `python -m pytest tests/ -v --tb=short -k "plugin"`
Expected: PASS

**Step 6: Commit**

```bash
git add bt_plugins/loader.py tests/test_plugin_loader_threadsafe.py
git commit -m "fix: add thread safety to PluginLoader with RLock"
```

---

### Task 3: Windows 守护进程兼容性（R2）

**Files:**
- Modify: `bt_cli/commands/daemon.py`
- Test: `tests/test_daemon_platform.py`

**Step 1: 编写失败测试**

```python
# tests/test_daemon_platform.py
"""daemon 命令平台兼容性测试"""
import os
import json
import tempfile
from unittest.mock import patch, MagicMock


def test_stop_daemon_on_windows():
    """测试 Windows 上停止守护进程使用 taskkill"""
    from bt_cli.commands import daemon

    with tempfile.TemporaryDirectory() as tmpdir:
        pid_file = os.path.join(tmpdir, "daemon.pid")
        with open(pid_file, "w") as f:
            f.write("12345")

        with patch.object(daemon, "DAEMON_PID_FILE", pid_file), \
             patch("platform.system", return_value="Windows"), \
             patch("subprocess.call", return_value=0) as mock_call:
            daemon._stop_daemon()
            mock_call.assert_called_once_with(["taskkill", "/PID", "12345", "/F"])


def test_stop_daemon_on_linux():
    """测试 Linux 上停止守护进程使用 SIGTERM"""
    from bt_cli.commands import daemon

    with tempfile.TemporaryDirectory() as tmpdir:
        pid_file = os.path.join(tmpdir, "daemon.pid")
        with open(pid_file, "w") as f:
            f.write("12345")

        with patch.object(daemon, "DAEMON_PID_FILE", pid_file), \
             patch("platform.system", return_value="Linux"), \
             patch("os.kill") as mock_kill:
            daemon._stop_daemon()
            mock_kill.assert_called_once()
```

**Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_daemon_platform.py -v`
Expected: FAIL — 当前代码直接使用 `os.kill(pid, signal.SIGTERM)`

**Step 3: 修复 daemon.py**

```python
# bt_cli/commands/daemon.py — 修改 _stop_daemon 函数

def _stop_daemon():
    """停止守护进程"""
    if not os.path.isfile(DAEMON_PID_FILE):
        print("守护进程未运行")
        return

    try:
        with open(DAEMON_PID_FILE, "r") as f:
            pid = int(f.read().strip())

        import platform
        if platform.system() == "Windows":
            import subprocess
            subprocess.call(["taskkill", "/PID", str(pid), "/F"])
        else:
            os.kill(pid, signal.SIGTERM)

        os.remove(DAEMON_PID_FILE)
        if os.path.isfile(DAEMON_STATUS_FILE):
            os.remove(DAEMON_STATUS_FILE)
        print(f"守护进程已停止 (PID: {pid})")
    except ProcessLookupError:
        print("守护进程进程不存在，清理 PID 文件")
        os.remove(DAEMON_PID_FILE)
    except Exception as e:
        print(f"停止失败: {e}")
```

**Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_daemon_platform.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bt_cli/commands/daemon.py tests/test_daemon_platform.py
git commit -m "fix: add Windows compatibility for daemon stop command"
```

---

### Task 4: SSE 无界队列 OOM 修复（A2）

**Files:**
- Modify: `bt_bus/message_bus.py:131-167`
- Modify: `bt_servers/rest_server.py:271`
- Test: `tests/test_sse_queue_bounds.py`

**Step 1: 创建 conftest.py 中的 message_bus fixture**

```python
# tests/conftest.py
"""pytest 共享 fixtures"""
import asyncio
import pytest


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
```

**Step 2: 编写失败测试**

```python
# tests/test_sse_queue_bounds.py
"""SSE 队列上限测试"""


def test_subscribe_async_with_maxsize(message_bus):
    """测试 subscribe_async 支持 maxsize 参数"""
    queue, sub_id = message_bus.subscribe_async("test.topic", maxsize=5)
    assert queue.maxsize == 5
    message_bus.unsubscribe_async(sub_id)


def test_queue_drops_old_when_full(message_bus):
    """测试队列满时丢弃旧消息"""
    queue, sub_id = message_bus.subscribe_async("test.topic", maxsize=3)

    # 不运行 event loop，消息走 put_nowait 路径
    for i in range(5):
        message_bus.publish("test.topic", {"index": i})

    # 队列应仅保留最后 3 条
    assert queue.qsize() <= 3
    message_bus.unsubscribe_async(sub_id)
```

**Step 3: 运行测试验证失败**

Run: `python -m pytest tests/test_sse_queue_bounds.py -v`
Expected: FAIL — `subscribe_async` 不接受 `maxsize` 参数

**Step 4: 修复 message_bus.py**

```python
# bt_bus/message_bus.py — 修改 subscribe_async 和 _push_to_single_async_queue

def subscribe_async(self, topic_pattern: str, maxsize: int = 1000) -> tuple:
    """异步订阅主题，返回 (asyncio.Queue, subscription_id)

    Args:
        topic_pattern: 主题模式
        maxsize: 队列最大容量，满时丢弃最旧消息（默认 1000）
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)

    def callback(msg: Message):
        self._push_to_single_async_queue(queue, msg)

    sub_id = self.subscribe(topic_pattern, callback)

    with self._async_queue_lock:
        self._async_queues.append((topic_pattern, queue, sub_id))

    return queue, sub_id


def _push_to_single_async_queue(self, queue: asyncio.Queue, msg: Message) -> None:
    """推送消息到单个异步队列"""
    try:
        with self._bus_lock:
            loop = self._event_loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                queue.put(msg), loop
            )
        else:
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                # 队列满，丢弃最旧消息后放入新消息
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait(msg)
                from bt_utils.log_manager import LogManager
                LogManager.debug_print("[MessageBus] Async queue full, dropped oldest message")
    except Exception as e:
        from bt_utils.log_manager import LogManager
        LogManager.debug_print(f"[MessageBus] Failed to push to async queue: {e}")
```

**Step 5: 修改 rest_server.py SSE 端点**

```python
# bt_servers/rest_server.py — 修改 event_stream 中的 subscribe_async 调用
queue, sub_id = self._bus.subscribe_async("bt.**.event.**", maxsize=500)
```

**Step 6: 运行测试验证通过**

Run: `python -m pytest tests/test_sse_queue_bounds.py -v`
Expected: PASS

**Step 7: 回归测试**

Run: `python -m pytest tests/test_message_bus.py tests/test_sse.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add bt_bus/message_bus.py bt_servers/rest_server.py tests/test_sse_queue_bounds.py tests/conftest.py
git commit -m "fix: add maxsize to async queue to prevent OOM in SSE"
```

---

## Tier 2: 中优先级修复

### Task 5: 线程安全主题（A3, A4, P1）

**Files:**
- Modify: `bt_bus/message_bus.py:24-42`
- Modify: `bt_adapters/http_adapter.py:53-69`
- Modify: `bt_services/registry.py:38-54`
- Test: `tests/test_thread_safety_fixes.py`

**Step 1: 编写失败测试**

```python
# tests/test_thread_safety_fixes.py
"""线程安全修复测试"""
import threading
from unittest.mock import MagicMock


def test_message_bus_init_thread_safe():
    """测试 MessageBus 并发初始化不产生半初始化实例"""
    from bt_bus.message_bus import MessageBus
    MessageBus.reset_instance()

    instances = []
    errors = []

    def create_instance():
        try:
            bus = MessageBus()
            # 立即访问多个属性，检测半初始化
            _ = bus._subscribers
            _ = bus._async_queues
            _ = bus._dead_letter_queue
            _ = bus._bus_lock
            _ = bus._stats
            instances.append(bus)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=create_instance) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 无并发错误
    assert not errors, f"并发初始化错误: {errors}"
    # 所有实例应为同一对象
    assert len(instances) == 20
    assert all(inst is instances[0] for inst in instances)
    # 实例应已完全初始化
    assert instances[0]._initialized is True

    MessageBus.reset_instance()


def test_service_registry_no_lock_during_start_stop():
    """测试 ServiceRegistry start_all/stop_all 不持锁调用服务方法"""
    from bt_services.registry import ServiceRegistry

    registry = ServiceRegistry()
    mock_svc = MagicMock()
    mock_svc.get_name.return_value = "test"
    registry.register("test", mock_svc)

    # 记录 start 调用时的锁状态
    lock_held_during_start = []
    original_start = mock_svc.start
    def check_lock_start():
        lock_held_during_start.append(registry._lock._is_owned())
    mock_svc.start.side_effect = check_lock_start

    registry.start_all()

    # start 不应在持锁状态下调用
    assert not any(lock_held_during_start), "Service start called while holding registry lock"


def test_http_adapter_call_thread_safe():
    """测试 HTTPAdapter 并发 call 不产生竞态"""
    from bt_adapters.http_adapter import HTTPAdapter
    from bt_adapters.config import AdapterConfig

    adapter = HTTPAdapter(AdapterConfig())
    adapter.start()

    errors = []
    def make_call():
        try:
            # mock session.request 避免真实网络请求
            adapter._session.request = MagicMock(return_value=MagicMock(
                status_code=200, text="{}", headers={}
            ))
            adapter.call("GET", "http://example.com/test")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=make_call) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"HTTPAdapter 并发错误: {errors}"
    adapter.stop()
```

**Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_thread_safety_fixes.py -v`
Expected: `test_service_registry_no_lock_during_start_stop` FAIL

**Step 3: 修复 message_bus.py 初始化竞态（A3）— 原子化单例**

将所有初始化集中在 `__new__` 的锁内完成，`__init__` 变为 no-op：

```python
# bt_bus/message_bus.py — 替换 __new__ 和 __init__
import threading
from bt_bus.dead_letter import DeadLetterQueue
from bt_bus.middleware import ValidationMiddleware
# ... 其他导入 ...


class MessageBus:
    _instance = None
    _instance_lock = threading.RLock()

    def __new__(cls):
        # 双重检查锁
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    # 在锁内完成所有属性初始化（原子性）
                    instance._subscribers = {}
                    instance._subscriber_id_counter = 0
                    instance._async_queues = []
                    instance._bus_lock = threading.RLock()
                    instance._async_queue_lock = threading.RLock()
                    instance._event_loop = None
                    instance._running = False
                    # 先创建死信队列，再创建中间件（中间件依赖死信队列）
                    instance._dead_letter_queue = DeadLetterQueue()
                    instance._stats = BusStats()
                    instance._middleware_chain = ValidationMiddleware(
                        dead_letter_queue=instance._dead_letter_queue
                    )
                    instance._initialized = True  # 最后标记
                    cls._instance = instance       # 暴露实例（最后一步）
        return cls._instance

    def __init__(self):
        # no-op：所有初始化在 __new__ 中完成
        # Python 语义保证 __init__ 每次 MessageBus() 都会调用，
        # 但实例已完全初始化，无需重复
        pass

    @classmethod
    def reset_instance(cls):
        """重置单例（测试用），清理前先 stop()"""
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance.stop()
                except Exception:
                    pass
            cls._instance = None
```

**关键点：**
1. `cls._instance = instance` 是锁内最后一步，确保其他线程拿到实例时所有属性已就绪
2. `__init__` 变为 no-op，避免重复初始化的复杂性
3. `reset_instance` 新增 `stop()` 调用，避免资源泄漏
4. 死信队列在中间件之前创建，确保中间件能引用

**Step 4: 修复 http_adapter.py 竞态（A4）**

```python
# bt_adapters/http_adapter.py — 修改 call 方法
def call(self, method, url, headers=None, body=None,
         timeout_ms=None, retry_count=None, retry_interval_ms=None):
    import requests

    if timeout_ms is None:
        timeout_ms = self._config.read_timeout * 1000
    if retry_count is None:
        retry_count = self._config.max_retries
    if retry_interval_ms is None:
        retry_interval_ms = self._config.retry_backoff_ms

    # 线程安全的 session 初始化
    with self._lock:
        if self._session is None:
            self.start()

    # 准备请求体（锁外执行，不阻塞其他线程）
    json_body = None
    data_body = None
    if body is not None:
        if isinstance(body, (dict, list)):
            json_body = body
        else:
            data_body = body

    timeout_s = timeout_ms / 1000.0
    last_exc = None

    for attempt in range(retry_count + 1):
        try:
            start = time.time()
            resp = self._session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_body,
                data=data_body,
                timeout=timeout_s
            )
            elapsed_ms = (time.time() - start) * 1000
            return HTTPResponse(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                elapsed_ms=elapsed_ms
            )
        except requests.RequestException as e:
            last_exc = e
            if attempt < retry_count:
                time.sleep(retry_interval_ms / 1000.0)

    raise last_exc if last_exc else RuntimeError("HTTP request failed")
```

**Step 5: 修复 registry.py 持锁执行（P1）**

```python
# bt_services/registry.py — 修改 start_all 和 stop_all
def start_all(self) -> None:
    """启动所有服务"""
    with self._lock:
        services = list(self._services.items())
    for name, svc in services:
        try:
            svc.start()
        except Exception as e:
            print(f"[ServiceRegistry] start failed for {name}: {e}")

def stop_all(self) -> None:
    """停止所有服务"""
    with self._lock:
        services = list(self._services.items())
    for name, svc in services:
        try:
            svc.stop()
        except Exception as e:
            print(f"[ServiceRegistry] stop failed for {name}: {e}")
```

**Step 6: 运行测试验证通过**

Run: `python -m pytest tests/test_thread_safety_fixes.py -v`
Expected: PASS

**Step 7: 回归测试**

Run: `python -m pytest tests/test_message_bus.py tests/test_adapter_manager.py tests/test_service_registry.py tests/test_http_adapter.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add bt_bus/message_bus.py bt_adapters/http_adapter.py bt_services/registry.py tests/test_thread_safety_fixes.py
git commit -m "fix: resolve thread safety issues in MessageBus init, HTTPAdapter, and ServiceRegistry"
```

---

### Task 6: 逻辑修复主题（B3, B4, B6）

**Files:**
- Modify: `bt_bus/message_bus.py:79-93`
- Modify: `bt_bus/middleware.py:31-37`
- Modify: `bt_adapters/adapter_manager.py`
- Modify: `bt_plugins/loader.py:305-360`
- Test: `tests/test_logic_fixes.py`

**Step 1: 编写失败测试**

```python
# tests/test_logic_fixes.py
"""逻辑修复测试"""
from unittest.mock import MagicMock


def test_deliver_depth_limit(message_bus):
    """测试 _deliver 递归深度限制（通过公共 publish API 触发）"""
    from bt_bus.message import Message

    call_count = [0]

    def recursive_callback(msg):
        call_count[0] += 1
        # 回复会触发递归发布
        return Message.create(
            msg.headers.get("reply_to", "test.deep"),
            "reply",
            headers={"reply_to": msg.headers.get("reply_to", "test.deep")}
        )

    message_bus.subscribe("test.deep", recursive_callback)

    # 设置 reply_to 触发递归
    message_bus.publish("test.deep", "start", headers={"reply_to": "test.deep"})

    # 递归应被限制（MAX_DELIVER_DEPTH=5），不应无限循环
    assert call_count[0] <= 10, f"递归深度过大: {call_count[0]}"
    assert call_count[0] >= 1, "回调未被调用"


def test_validation_middleware_records_dead_letter():
    """测试 ValidationMiddleware 验证失败时记录死信"""
    from bt_bus.middleware import ValidationMiddleware
    from bt_bus.message import Message
    from bt_bus.dead_letter import DeadLetterQueue

    # 使用真实 DeadLetterQueue 而非 mock，验证集成
    dlq = DeadLetterQueue()
    middleware = ValidationMiddleware(dead_letter_queue=dlq)

    # 空 topic 消息
    msg = Message.create("", {"data": "test"})
    result = middleware.process(msg, lambda m: m)

    # 验证：返回 None（消息被拦截）
    assert result is None
    # 验证：死信队列记录了该消息
    assert len(dlq.items()) == 1
    assert dlq.items()[0].reason == "VALIDATION_FAILED_EMPTY_TOPIC"


def test_validation_middleware_passes_valid_message():
    """测试 ValidationMiddleware 放行有效消息"""
    from bt_bus.middleware import ValidationMiddleware
    from bt_bus.message import Message

    middleware = ValidationMiddleware(dead_letter_queue=None)
    msg = Message.create("valid.topic", {"data": "test"})

    called = [False]
    def next_handler(m):
        called[0] = True
        return m

    result = middleware.process(msg, next_handler)

    assert result is msg
    assert called[0] is True


def test_adapter_manager_unregister():
    """测试 AdapterManager unregister_adapter 方法"""
    from bt_adapters.adapter_manager import AdapterManager
    from bt_adapters.base import BaseAdapter, AdapterLevel, AdapterStatus

    AdapterManager.reset_instance()
    manager = AdapterManager()

    class TestAdapter(BaseAdapter):
        @classmethod
        def get_adapter_level(cls): return AdapterLevel.LOCAL
        @classmethod
        def is_available(cls): return True
        def start(self): pass
        def stop(self): pass
        def get_name(self): return "test"
        def get_status(self): return AdapterStatus(running=False, name="test", level=AdapterLevel.LOCAL)

    manager.register_adapter("test", TestAdapter)
    adapter = manager.get_adapter("test")
    assert adapter is not None

    # 注销
    manager.unregister_adapter("test")
    adapter = manager.get_adapter("test")
    assert adapter is None

    AdapterManager.reset_instance()
```

**Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_logic_fixes.py -v`
Expected: `test_adapter_manager_unregister` FAIL（无 `unregister_adapter` 方法）

**Step 3: 修复 message_bus.py _deliver 递归限制（B3）**

```python
# bt_bus/message_bus.py — 修改 _deliver 方法

MAX_DELIVER_DEPTH = 5  # 添加类常量

def _deliver(self, sub, msg: Message) -> None:
    try:
        depth = msg.headers.get("_deliver_depth", 0)
        if depth >= self.MAX_DELIVER_DEPTH:
            from bt_utils.log_manager import LogManager
            LogManager.debug_print(f"[MessageBus] Deliver depth limit reached: {depth}")
            self._dead_letter_queue.add(msg, reason="MAX_DEPTH_EXCEEDED")
            return

        response = sub.callback(msg)
        self._stats.record_deliver(msg.topic)
        if response is not None and isinstance(response, Message):
            reply_to = msg.headers.get("reply_to")
            if reply_to:
                response.topic = reply_to
                response.headers["_deliver_depth"] = depth + 1
                self.publish(reply_to, response.data,
                             headers=response.headers,
                             source="responder")
    except Exception as e:
        from bt_utils.log_manager import LogManager
        LogManager.debug_print(f"[MessageBus] Subscriber exception: {e}")
        self._dead_letter_queue.add(msg, reason="SUBSCRIBER_EXCEPTION")
```

**Step 4: 修复 middleware.py ValidationMiddleware 死信记录（B4）**

注意：死信队列的注入在 Task 5 Step 3 的 `MessageBus.__new__` 中已完成（`ValidationMiddleware(dead_letter_queue=instance._dead_letter_queue)`）。本步骤只需修改 `ValidationMiddleware` 自身：

```python
# bt_bus/middleware.py — 修改 ValidationMiddleware
class ValidationMiddleware(Middleware):
    """消息验证中间件，验证失败时记录死信"""

    def __init__(self, dead_letter_queue=None):
        self._dlq = dead_letter_queue

    def process(self, message: Message, next_handler: Callable) -> Optional[Message]:
        # 验证 topic
        if not message.topic:
            self._record_dead_letter(message, "VALIDATION_FAILED_EMPTY_TOPIC")
            return None
        # 验证 data
        if message.data is None:
            self._record_dead_letter(message, "VALIDATION_FAILED_NULL_DATA")
            return None
        # 验证通过，传递给下一个处理器
        return next_handler(message)

    def _record_dead_letter(self, message: Message, reason: str) -> None:
        """记录死信，无死信队列时仅记录日志"""
        from bt_utils.log_manager import LogManager
        LogManager.debug_print(
            f"[ValidationMiddleware] Message rejected: {reason}, topic={message.topic}"
        )
        if self._dlq is not None:
            try:
                self._dlq.add(message, reason=reason)
            except Exception as e:
                LogManager.debug_print(
                    f"[ValidationMiddleware] Failed to record dead letter: {e}"
                )
```

**Step 5: 修复 adapter_manager.py 添加 unregister_adapter（B6）**

```python
# bt_adapters/adapter_manager.py — 添加 unregister_adapter 方法

def unregister_adapter(self, name: str) -> None:
    """注销适配器类型和实例"""
    with self._adapters_lock:
        self._adapters.pop(name, None)
        self._adapter_classes.pop(name, None)
```

**Step 6: 修复 loader.py stop_plugin 调用 unregister_adapter**

```python
# bt_plugins/loader.py — 在 stop_plugin 的注销适配器部分添加
# 注销适配器
try:
    adapter_names = [an for an, pn in self._registered_adapters.items() if pn == name]
    am = self._context._adapter_manager
    for an in adapter_names:
        if am is not None and hasattr(am, 'unregister_adapter'):
            am.unregister_adapter(an)
        self._registered_adapters.pop(an, None)
except Exception as e:
    print(f"[PluginLoader] 清理适配器记录失败 {name}: {e}")
```

**Step 7: 运行测试验证通过**

Run: `python -m pytest tests/test_logic_fixes.py -v`
Expected: PASS

**Step 8: 回归测试**

Run: `python -m pytest tests/test_message_bus.py tests/test_middleware.py tests/test_adapter_manager.py tests/test_dead_letter.py -v`
Expected: PASS

**Step 9: Commit**

```bash
git add bt_bus/message_bus.py bt_bus/middleware.py bt_adapters/adapter_manager.py bt_plugins/loader.py tests/test_logic_fixes.py
git commit -m "fix: add deliver depth limit, validation dead letter recording, and adapter unregister"
```

---

### Task 7: CLI 增强主题（C1, R3, R5, E1, E2）

**Files:**
- Create: `bt_cli/errors.py`
- Modify: `cli.py`
- Modify: `bt_cli/commands/plugin.py`
- Modify: `bt_cli/commands/run.py`
- Modify: `bt_cli/scheduler.py`
- Test: `tests/test_cli_enhancements.py`

**Step 1: 编写失败测试**

```python
# tests/test_cli_enhancements.py
"""CLI 增强功能测试"""
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock


def test_plugin_unload_command_exists():
    """测试 plugin unload 子命令存在"""
    import cli
    parser = cli.main.__wrapped__ if hasattr(cli.main, '__wrapped__') else None
    # 直接检查 cli.py 中是否注册了 unload subparser
    import inspect
    source = inspect.getsource(cli)
    assert "unload" in source, "cli.py 中未找到 unload 子命令"


def test_errors_module_exists():
    """测试 bt_cli/errors.py 模块存在"""
    from bt_cli.errors import exit_with_code, EXIT_FILE_NOT_FOUND, EXIT_PLUGIN_ERROR
    assert EXIT_FILE_NOT_FOUND == 3
    assert EXIT_PLUGIN_ERROR == 6


def test_schedule_add_validates_file():
    """测试 schedule add 验证文件存在"""
    from bt_cli.scheduler import Scheduler
    scheduler = Scheduler()
    # 不存在的文件应返回空字符串或抛出异常
    result = scheduler.add_task("test", "/nonexistent/file.json", interval="30s")
    # 应返回空字符串表示失败
    assert result == "" or result is None


def test_scheduler_execute_returns_status():
    """测试调度器执行任务记录状态"""
    from bt_cli.scheduler import ScheduleTask, Scheduler
    scheduler = Scheduler()
    task = ScheduleTask("test_id", "test", "/nonexistent/file.json", interval="30s")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        scheduler._execute_task(task)
        assert hasattr(task, 'last_run_status')
```

**Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_cli_enhancements.py -v`
Expected: FAIL

**Step 3: 创建 bt_cli/errors.py（E1）**

```python
# bt_cli/errors.py
"""CLI 标准退出码和错误处理"""
import sys

EXIT_SUCCESS = 0
EXIT_GENERIC_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_FILE_NOT_FOUND = 3
EXIT_DEPENDENCY_MISSING = 4
EXIT_AUTH_FAILED = 5
EXIT_PLUGIN_ERROR = 6
EXIT_INTERRUPTED = 130


def exit_with_code(code: int, message: str = ""):
    """以指定退出码退出，可选打印消息"""
    if message:
        print(message)
    sys.exit(code)
```

**Step 4: 在 cli.py 添加 plugin unload 子命令（C1）**

```python
# cli.py — 在 plugin 子命令部分添加
plugin_unload = plugin_sub.add_parser("unload", help="卸载插件")
plugin_unload.add_argument("name")
```

在 `bt_cli/commands/plugin.py` 添加：

```python
# bt_cli/commands/plugin.py — 在 cmd_plugin 中添加
elif action == "unload":
    _unload_plugin(loader, args)


def _unload_plugin(loader, args):
    """卸载插件"""
    if args.name not in [p.name for p in loader.list_plugins()]:
        print(f"未找到插件: {args.name}")
        sys.exit(1)
    loader.unload_plugin(args.name)
    print(f"插件已卸载: {args.name}")
```

**Step 5: 修复 run.py 配置落盘（R3）**

```python
# bt_cli/commands/run.py — 在 _run_headless 中添加 save_settings
def _run_headless(args):
    from bt_core.headless import HeadlessRunner
    from config.settings_manager import get_settings_manager

    settings = get_settings_manager()

    if args.bus:
        settings.set("message_bus.enabled", True)
    if args.rest:
        settings.set("rest_server.enabled", True)
        settings.set("rest_server.host", args.rest_host)
        settings.set("rest_server.port", args.rest_port)
    if args.ws:
        settings.set("websocket_server.enabled", True)
        settings.set("websocket_server.host", args.ws_host)
        settings.set("websocket_server.port", args.ws_port)
    if args.plugins:
        settings.set("plugins.enabled", True)

    # 落盘保存配置
    settings.save_settings()

    # ... 其余不变
```

**Step 6: 修复 scheduler.py 文件验证（R5）和执行反馈（E2）**

```python
# bt_cli/scheduler.py — 修改 add_task
def add_task(self, name: str, tree_file: str, cron=None, interval=None,
             once=None, headless=True) -> str:
    """添加定时任务"""
    import uuid
    if not os.path.isfile(tree_file):
        print(f"[Scheduler] 行为树文件不存在: {tree_file}")
        return ""
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task = ScheduleTask(
        task_id=task_id, name=name or tree_file, tree_file=tree_file,
        cron=cron, interval=interval, once=once, headless=headless
    )
    self._tasks[task_id] = task
    self._save()
    return task_id
```

```python
# bt_cli/scheduler.py — 修改 _execute_task 和 ScheduleTask
class ScheduleTask:
    def __init__(self, ...):
        # ... 原有属性 ...
        self.last_run_status = None  # 新增

    def to_dict(self):
        return {
            # ... 原有字段 ...
            "last_run_status": self.last_run_status,
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(...)
        # ... 原有赋值 ...
        task.last_run_status = data.get("last_run_status")
        return task


def _execute_task(self, task: ScheduleTask):
    """执行任务"""
    import subprocess
    print(f"[Scheduler] 执行任务: {task.name} ({task.tree_file})")
    task.last_run = datetime.now().isoformat()
    task.run_count += 1

    try:
        cmd = ["python", "cli.py", "run", task.tree_file]
        if task.headless:
            cmd.append("--headless")
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        task.last_run_status = "success" if result.returncode == 0 else f"failed({result.returncode})"
    except subprocess.TimeoutExpired:
        task.last_run_status = "timeout"
    except Exception as e:
        task.last_run_status = f"error({e})"

    self._save()
```

**Step 7: 运行测试验证通过**

Run: `python -m pytest tests/test_cli_enhancements.py -v`
Expected: PASS

**Step 8: 回归测试**

Run: `python -m pytest tests/test_cli_commands.py tests/test_scheduler.py tests/test_plugin_loader.py -v`
Expected: PASS

**Step 9: Commit**

```bash
git add bt_cli/errors.py cli.py bt_cli/commands/plugin.py bt_cli/commands/run.py bt_cli/scheduler.py tests/test_cli_enhancements.py
git commit -m "feat: add plugin unload command, config persistence, file validation, and unified error codes"
```

---

### Task 8: 文档同步主题（D1, D2）

**Files:**
- Modify: `docs/plugin-guide.md`
- Modify: `docs/cli-manual.md`

**Step 1: 修复 plugin-guide.md 卸载按钮描述（D1）**

在 `docs/plugin-guide.md` 中找到第 96 行附近的"卸载"描述，修改为：

```markdown
#### 步骤 6：停止插件

- 点击「停止」按钮停止插件（节点从面板移除）
- 如需完全卸载插件，使用 CLI 命令：`autodoor-bt plugin unload <plugin_name>`
```

**Step 2: 修复 cli-manual.md 退出码表（D2）**

在 `docs/cli-manual.md` 的退出码章节，更新为：

```markdown
| 退出码 | 常量 | 说明 | 状态 |
|--------|------|------|------|
| 0 | EXIT_SUCCESS | 成功 | 已实现 |
| 1 | EXIT_GENERIC_ERROR | 通用错误 | 已实现 |
| 2 | EXIT_CONFIG_ERROR | 配置错误 | 预留 |
| 3 | EXIT_FILE_NOT_FOUND | 文件未找到 | 已实现 |
| 4 | EXIT_DEPENDENCY_MISSING | 依赖缺失 | 已实现 |
| 5 | EXIT_AUTH_FAILED | 认证失败 | 预留 |
| 6 | EXIT_PLUGIN_ERROR | 插件错误 | 预留 |
| 130 | EXIT_INTERRUPTED | 用户中断（Ctrl+C） | 已实现 |
```

在 `docs/cli-manual.md` 的 plugin 命令章节，添加 `unload` 子命令文档：

```markdown
##### plugin unload — 卸载插件

卸载已加载的插件，清理注册的节点和适配器。

```bash
autodoor-bt plugin unload <name>
```

**参数:**
- `name`: 插件名称

**示例:**
```bash
autodoor-bt plugin unload file_processor
```
```

**Step 3: Commit**

```bash
git add docs/plugin-guide.md docs/cli-manual.md
git commit -m "docs: sync plugin guide and CLI manual with actual implementation"
```

---

## 完成验证

**Step 1: 全量回归测试**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部通过（原有 312 + 新增测试）

**Step 2: 验证修复覆盖**

确认以下问题已修复：
- [ ] B1/B2/R1: remote.py 数据解析
- [ ] A1: PluginLoader 线程安全
- [ ] R2: Windows 守护进程兼容
- [ ] A2: SSE 队列上限
- [ ] A3: MessageBus 初始化竞态
- [ ] A4: HTTPAdapter 竞态
- [ ] P1: ServiceRegistry 持锁
- [ ] B3: _deliver 递归限制
- [ ] B4: ValidationMiddleware 死信
- [ ] B6: AdapterManager unregister
- [ ] C1: plugin unload 命令
- [ ] R3: run 配置落盘
- [ ] R5: schedule 文件验证
- [ ] E1: 统一错误处理
- [ ] E2: schedule 执行反馈
- [ ] D1: plugin-guide 卸载描述
- [ ] D2: cli-manual 退出码表

**Step 3: 最终 Commit**

```bash
git add -A
git commit -m "test: add regression tests for all 16 review fixes"
```

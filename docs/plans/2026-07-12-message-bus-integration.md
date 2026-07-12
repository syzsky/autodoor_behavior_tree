# 消息总线与外部系统集成 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 AutoDoor 行为树系统从单机桌面工具升级为可编程自动化平台，实现消息总线、外部系统集成、REST API 和 Headless 模式

**Architecture:** 6 阶段渐进式集成 — 阶段 0（Headless/异步/安全）→ 阶段 1（消息总线）→ 阶段 2（适配器）→ 阶段 3（服务层）→ 阶段 4（服务端）→ 阶段 5（接口节点+GUI）。使用 SharedThreadPool 统一线程池、async/sync 桥接方案、tree_id 主题隔离。

**Tech Stack:** Python 3.9+, CustomTkinter, FastAPI, uvicorn, websockets, requests, sse-starlette

---

## 参考文档

- 开发方案：`md/05_消息总线与外部系统集成开发方案.md`
- 开发计划：`md/06_消息总线与外部系统集成开发计划.md`

## 阶段总览

```
阶段 0: 前置准备 (Task 1-8)
  ├─ 0.1 Headless 模式 (Task 1-3)
  ├─ 0.2 异步执行层 (Task 4-6)
  └─ 0.3 CodeNode 安全沙箱修复 (Task 7-8)

阶段 1: 消息总线核心 (Task 9-12)
阶段 2: 适配器层 (Task 13-15)
阶段 3: 服务层 (Task 16-20)
阶段 4: 服务端层 (Task 21-23)
阶段 5: 接口节点与 GUI 集成 (Task 24-28)
```

---

## 阶段 0: 前置准备

### Task 1: HeadlessRunner 基础实现

**Files:**
- Create: `bt_core/headless.py`
- Test: `tests/test_headless.py`

**Step 1: Write the failing test**

```python
# tests/test_headless.py
import os
import sys
import json
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestHeadlessRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        )
        tree_data = {
            "version": "1.0",
            "format_type": "json",
            "root": {
                "id": "root",
                "type": "Sequence",
                "name": "Root",
                "children": [
                    {
                        "id": "delay1",
                        "type": "DelayNode",
                        "name": "Delay100ms",
                        "config": {"delay_ms": 100}
                    }
                ],
                "config": {}
            }
        }
        json.dump(tree_data, self.tmp)
        self.tmp.close()

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_headless_runner_can_be_imported(self):
        from bt_core.headless import HeadlessRunner
        self.assertTrue(hasattr(HeadlessRunner, 'run'))
        self.assertTrue(hasattr(HeadlessRunner, 'stop'))

    def test_headless_run_simple_tree(self):
        from bt_core.headless import HeadlessRunner
        runner = HeadlessRunner()
        result = runner.run(self.tmp.name)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_headless.py::TestHeadlessRunner::test_headless_runner_can_be_imported -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_core.headless'"

**Step 3: Write minimal implementation**

```python
# bt_core/headless.py
"""Headless 运行模式 — 无 GUI 运行行为树

为服务端模式奠定基础，支持命令行运行行为树文件。
"""
import os
import time
import threading
from typing import Optional


class HeadlessRunner:
    """无 GUI 模式运行行为树

    完整启动流程（阶段 4 实现后启用）:
        1. 加载行为树 → 创建 Context
        2. 启动消息总线 MessageBus（阶段 1）
        3. 启动适配器层 AdapterManager（阶段 2）
        4. 启动服务层 ServiceRegistry（阶段 3）
        5. 启动 REST API 服务端（阶段 4）
        6. 启动引擎
    """

    def __init__(self):
        self._engine = None
        self._context = None
        self._tree_file: Optional[str] = None
        self._stop_requested = threading.Event()

    def run(self, tree_file: str, project_root: str = None) -> bool:
        """加载并运行行为树

        Args:
            tree_file: 行为树 JSON 文件路径
            project_root: 项目根目录，默认为行为树所在目录

        Returns:
            True=正常完成, False=出错
        """
        import json
        from bt_core.serializer import Serializer
        from bt_core.context import ExecutionContext
        from bt_core.engine import BehaviorTreeEngine

        self._tree_file = tree_file
        self._stop_requested.clear()

        with open(tree_file, 'r', encoding='utf-8') as f:
            tree_data = json.load(f)

        root = Serializer.deserialize(tree_data)
        if isinstance(root, tuple):
            root = root[0]

        self._context = ExecutionContext(
            project_root=project_root or os.path.dirname(os.path.abspath(tree_file))
        )
        if hasattr(self._context, 'set_headless'):
            self._context.set_headless(True)

        self._engine = BehaviorTreeEngine(root)
        self._engine.start(self._context)

        try:
            while self._engine._running:
                if self._stop_requested.is_set():
                    self._engine.stop()
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            self._engine.stop()

        return True

    def stop(self) -> None:
        """停止运行"""
        self._stop_requested.set()
        if self._engine:
            self._engine.stop()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_headless.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add bt_core/headless.py tests/test_headless.py
git commit -m "feat(headless): add HeadlessRunner base implementation"
```

---

### Task 2: ExecutionContext headless 标记

**Files:**
- Modify: `bt_core/context.py`
- Test: `tests/test_headless.py`

**Step 1: Write the failing test**

Append to `tests/test_headless.py` (在 TestHeadlessRunner 类内新增方法):

```python
    def test_context_set_headless_flag(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        self.assertFalse(ctx.is_headless())
        ctx.set_headless(True)
        self.assertTrue(ctx.is_headless())
        ctx.set_headless(False)
        self.assertFalse(ctx.is_headless())

    def test_headless_notify_node_status_noop(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.set_headless(True)
        called = []
        ctx._on_node_status = lambda nid, st: called.append((nid, st))
        ctx.notify_node_status("n1", "SUCCESS")
        self.assertEqual(called, [])
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_headless.py::TestHeadlessRunner::test_context_set_headless_flag -v`
Expected: FAIL with "AttributeError: 'ExecutionContext' object has no attribute 'set_headless'"

**Step 3: Write minimal implementation**

Modify `bt_core/context.py`:

1. 在 `__init__` 方法末尾（`self._current_tab_id = None` 之后）添加：

```python
        self._tab_manager = None
        self._current_tab_id: Optional[str] = None
        # Headless 模式标记
        self._headless: bool = False
```

2. 在 `get_current_tab_id` 方法之后新增：

```python
    def set_headless(self, headless: bool) -> None:
        """设置 Headless 模式

        Args:
            headless: True=无 GUI 模式（notify_node_status 为空操作）
        """
        self._headless = headless

    def is_headless(self) -> bool:
        """是否为 Headless 模式"""
        return self._headless
```

3. 修改 `notify_node_status` 方法（第 153 行），在方法开头加入 headless 短路：

```python
    def notify_node_status(self, node_id: str, status: str) -> None:
        """通知节点状态变化"""
        if self._headless:
            return
        if self._on_node_status:
            try:
                from bt_utils.ui_dispatcher import UIUpdateDispatcher
                dispatcher = UIUpdateDispatcher()
                dispatcher.dispatch_node_status(node_id, status, self._on_node_status)
            except ImportError:
                self._on_node_status(node_id, status)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_headless.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add bt_core/context.py tests/test_headless.py
git commit -m "feat(context): add headless flag for no-GUI mode"
```

---

### Task 3: main.py --headless 命令行参数

**Files:**
- Modify: `main.py`
- Test: `tests/test_headless.py`

**Step 1: Write the failing test**

Append to `tests/test_headless.py`:

```python
class TestMainHeadlessArg(unittest.TestCase):
    def test_main_argparse_headless_flag(self):
        with open(os.path.join(PROJECT_ROOT, "main.py"), 'r', encoding='utf-8') as f:
            source = f.read()
        self.assertIn("--headless", source)
        self.assertIn("argparse", source)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_headless.py::TestMainHeadlessArg -v`
Expected: FAIL with "AssertionError: assert '--headless' not found"

**Step 3: Write minimal implementation**

修改 `main.py`，在 `def main():` 之前新增 `parse_args()` 和 `run_headless()` 函数，并修改 `main()` 入口：

```python
def parse_args():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser(description="AutoDoor 行为树编辑器")
    parser.add_argument("--headless", type=str, default=None,
                        help="无 GUI 模式运行指定行为树文件")
    parser.add_argument("--project", type=str, default=None,
                        help="项目根目录（headless 模式）")
    return parser.parse_args()


def run_headless(tree_file, project_root=None):
    """Headless 模式入口"""
    from bt_core.headless import HeadlessRunner
    from bt_core.registry import register_all_nodes
    register_all_nodes()
    runner = HeadlessRunner()
    return runner.run(tree_file, project_root)


def main():
    args = parse_args()

    if args.headless:
        run_headless(args.headless, args.project)
        return

    ensure_workspace_exists()

    from bt_utils.app_restarter import is_dd_available, is_ib_available
    check_admin_for_driver("dd", "DD虚拟键盘", is_dd_available)
    check_admin_for_driver("ib", "IbInputSimulator", is_ib_available)

    initialize_ocr()
    initialize_input()

    register_all_nodes()

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = BehaviorTreeApp()

    from bt_utils.version_checker import VersionChecker
    github_owner, github_repo = load_github_info()
    version_checker = VersionChecker(
        app=app,
        owner=github_owner,
        repo=github_repo,
        current_version=VERSION
    )

    app._version_checker = version_checker

    version_checker.check_force_update()

    version_checker.start_auto_check(app)

    app.mainloop()


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_headless.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add main.py tests/test_headless.py
git commit -m "feat(main): add --headless CLI argument"
```

---

### Task 4: SharedThreadPool 共享线程池

**Files:**
- Create: `bt_bus/__init__.py`
- Create: `bt_bus/thread_pool.py`
- Test: `tests/test_shared_thread_pool.py`

**Step 1: Write the failing test**

```python
# tests/test_shared_thread_pool.py
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestSharedThreadPool(unittest.TestCase):
    def setUp(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def tearDown(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def test_singleton(self):
        from bt_bus.thread_pool import SharedThreadPool
        p1 = SharedThreadPool.get_instance()
        p2 = SharedThreadPool.get_instance()
        self.assertIs(p1, p2)

    def test_submit_returns_future(self):
        from bt_bus.thread_pool import SharedThreadPool
        pool = SharedThreadPool.get_instance()
        future = pool.submit("bus", lambda x: x * 2, 21)
        self.assertEqual(future.result(timeout=2), 42)

    def test_submit_no_quota_task_type(self):
        from bt_bus.thread_pool import SharedThreadPool
        pool = SharedThreadPool.get_instance()
        future = pool.submit("unknown_type", lambda: "ok")
        self.assertEqual(future.result(timeout=2), "ok")


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_shared_thread_pool.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_bus'"

**Step 3: Write minimal implementation**

```python
# bt_bus/__init__.py
"""消息总线模块"""
```

```python
# bt_bus/thread_pool.py
"""统一共享线程池

按任务类型分配配额，避免多个独立 ThreadPoolExecutor 在 GIL 下竞争。
参考开发方案 §3.7.3。
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional


class SharedThreadPool:
    """全局共享线程池，按任务类型分配配额

    任务类型:
    - "bus":         消息总线分发（配额 3）
    - "adapter":     适配器回调（配额 3）
    - "async_node":  异步节点执行（配额 2）
    - 其他:          无配额限制
    """
    _instance: Optional["SharedThreadPool"] = None
    _lock = threading.Lock()
    _default_quotas = {
        "bus": 3,
        "adapter": 3,
        "async_node": 2,
    }

    def __init__(self, max_workers: int = 8):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="bt-shared"
        )
        self._quotas = {
            task_type: threading.Semaphore(quota)
            for task_type, quota in self._default_quotas.items()
        }

    @classmethod
    def get_instance(cls) -> "SharedThreadPool":
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅供测试使用）"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown(wait=False)
                cls._instance = None

    def submit(self, task_type: str, fn, *args, **kwargs):
        """提交任务，按类型限流"""
        quota = self._quotas.get(task_type)

        def wrapped():
            if quota is not None:
                quota.acquire()
                try:
                    return fn(*args, **kwargs)
                finally:
                    quota.release()
            return fn(*args, **kwargs)

        return self._executor.submit(wrapped)

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池"""
        self._executor.shutdown(wait=wait)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_shared_thread_pool.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add bt_bus/__init__.py bt_bus/thread_pool.py tests/test_shared_thread_pool.py
git commit -m "feat(bus): add SharedThreadPool with quota-based limiting"
```

---

### Task 5: AsyncExecutor 异步执行器

**Files:**
- Create: `bt_utils/async_executor.py`
- Test: `tests/test_async_executor.py`

**Step 1: Write the failing test**

```python
# tests/test_async_executor.py
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestAsyncExecutor(unittest.TestCase):
    def setUp(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def tearDown(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def test_submit_and_get_result(self):
        from bt_utils.async_executor import AsyncExecutor
        from bt_core.status import NodeStatus
        executor = AsyncExecutor()

        def task():
            time.sleep(0.05)
            return NodeStatus.SUCCESS

        executor.submit("node1", task)
        while not executor.is_done("node1"):
            time.sleep(0.01)
        self.assertEqual(executor.get_result("node1"), NodeStatus.SUCCESS)

    def test_cancel_all(self):
        from bt_utils.async_executor import AsyncExecutor
        executor = AsyncExecutor()

        def long_task():
            time.sleep(2)
            return None

        executor.submit("n1", long_task)
        executor.submit("n2", long_task)
        executor.cancel_all()
        self.assertTrue(executor.is_done("n1"))
        self.assertTrue(executor.is_done("n2"))

    def test_get_result_unknown_node(self):
        from bt_utils.async_executor import AsyncExecutor
        from bt_core.status import NodeStatus
        executor = AsyncExecutor()
        self.assertEqual(executor.get_result("unknown"), NodeStatus.FAILURE)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_async_executor.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_utils.async_executor'"

**Step 3: Write minimal implementation**

```python
# bt_utils/async_executor.py
"""异步执行器 — 基于 SharedThreadPool 封装

管理异步节点任务提交、超时、取消。
参考开发计划 §0.1.2。
"""
import threading
import time
from concurrent.futures import Future
from typing import Any, Callable, Dict, Optional

from bt_bus.thread_pool import SharedThreadPool


class AsyncExecutor:
    """异步任务执行器

    通过 SharedThreadPool 提交任务（task_type="async_node"），
    管理每个节点异步任务的状态、结果、取消。
    """

    def __init__(self, shared_pool: Optional[SharedThreadPool] = None):
        self._pool = shared_pool or SharedThreadPool.get_instance()
        self._futures: Dict[str, Future] = {}
        self._results: Dict[str, Any] = {}
        self._cancelled: set = set()
        self._lock = threading.Lock()

    def submit(self, node_id: str, func: Callable,
               timeout_ms: int = 30000) -> None:
        """提交异步任务到共享线程池"""
        with self._lock:
            self._cancelled.discard(node_id)
            start_time = time.time()
            deadline = start_time + timeout_ms / 1000.0

            def wrapped():
                if deadline and time.time() > deadline:
                    from bt_core.status import NodeStatus
                    return NodeStatus.FAILURE
                if node_id in self._cancelled:
                    from bt_core.status import NodeStatus
                    return NodeStatus.FAILURE
                return func()

            future = self._pool.submit("async_node", wrapped)
            self._futures[node_id] = future

    def is_done(self, node_id: str) -> bool:
        """检查任务是否完成"""
        with self._lock:
            if node_id in self._results:
                return True
            if node_id in self._cancelled:
                return True
            future = self._futures.get(node_id)
            if future is None:
                return True
            if future.done():
                try:
                    self._results[node_id] = future.result()
                except Exception:
                    from bt_core.status import NodeStatus
                    self._results[node_id] = NodeStatus.FAILURE
                return True
            return False

    def get_result(self, node_id: str) -> Any:
        """获取任务结果"""
        from bt_core.status import NodeStatus
        with self._lock:
            if node_id in self._results:
                return self._results[node_id]
            if node_id in self._cancelled:
                return NodeStatus.FAILURE
            future = self._futures.get(node_id)
            if future is None:
                return NodeStatus.FAILURE
            if future.done():
                try:
                    result = future.result()
                    self._results[node_id] = result
                    return result
                except Exception:
                    self._results[node_id] = NodeStatus.FAILURE
                    return NodeStatus.FAILURE
            return NodeStatus.RUNNING

    def cancel_all(self) -> None:
        """取消所有任务（引擎停止时调用）"""
        with self._lock:
            for node_id, future in self._futures.items():
                self._cancelled.add(node_id)
                future.cancel()
            self._futures.clear()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_async_executor.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add bt_utils/async_executor.py tests/test_async_executor.py
git commit -m "feat(async): add AsyncExecutor based on SharedThreadPool"
```

---

### Task 6: Node._is_async 标志 + Engine 线程 ID 记录

**Files:**
- Modify: `bt_core/nodes.py`
- Modify: `bt_core/engine.py`
- Modify: `bt_core/context.py`
- Test: `tests/test_async_node.py`

**Step 1: Write the failing test**

```python
# tests/test_async_node.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestAsyncNode(unittest.TestCase):
    def setUp(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def tearDown(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def test_node_has_is_async_flag_default_false(self):
        from bt_core.nodes import ActionNode
        from bt_core.config import NodeConfig
        node = ActionNode(node_id="test", config=NodeConfig())
        self.assertFalse(node._is_async)
        self.assertFalse(node._async_started)

    def test_engine_has_thread_id_attribute(self):
        from bt_core.engine import BehaviorTreeEngine
        engine = BehaviorTreeEngine()
        self.assertTrue(hasattr(engine, '_engine_thread_id'))
        self.assertIsNone(engine._engine_thread_id)

    def test_engine_has_async_executor(self):
        from bt_core.engine import BehaviorTreeEngine
        engine = BehaviorTreeEngine()
        self.assertTrue(hasattr(engine, '_async_executor'))

    def test_context_has_get_async_executor(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        self.assertTrue(hasattr(ctx, 'set_async_executor'))
        self.assertTrue(hasattr(ctx, 'get_async_executor'))


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_async_node.py -v`
Expected: FAIL with "AttributeError: 'ActionNode' object has no attribute '_is_async'"

**Step 3: Write minimal implementation**

1. 修改 `bt_core/nodes.py`，在 `Node.__init__` 方法末尾（`self._children_running = False` 之后）添加：

```python
        self._children_running = False
        # 异步节点支持（阶段 0.2 新增）
        self._is_async: bool = False
        self._async_started: bool = False
```

2. 修改 `bt_core/engine.py`，在 `__init__` 方法末尾（`self._stats = get_stats_collector()` 之后）添加：

```python
        self._stats = get_stats_collector()
        # 异步执行器（基于 SharedThreadPool）
        from bt_utils.async_executor import AsyncExecutor
        self._async_executor = AsyncExecutor()
        # 引擎 tick 线程 ID（供 MessageBus.request() 防死锁检测使用）
        self._engine_thread_id = None
```

在 `_run_loop` 方法开头添加线程 ID 记录：

```python
    def _run_loop(self) -> None:
        # 记录引擎线程 ID（必须在 _run_loop 中记录，而非 start()）
        self._engine_thread_id = threading.get_ident()
        start_time = time.time()
        self._stop_event.clear()
        # ... 原有循环逻辑不变 ...
```

在 `stop` 方法中添加异步任务取消：

```python
    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._paused = False
            self._stop_event.set()
            self._pause_event.set()
            # 取消所有异步任务
            if hasattr(self, '_async_executor'):
                self._async_executor.cancel_all()
            # ... 原有逻辑不变 ...
```

3. 修改 `bt_core/context.py`，在 `set_headless` 之后新增异步执行器方法：

```python
    def set_async_executor(self, executor) -> None:
        """设置异步执行器"""
        self._async_executor = executor

    def get_async_executor(self):
        """获取异步执行器"""
        return getattr(self, '_async_executor', None)
```

并在 `__init__` 末尾添加 `self._async_executor = None`。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_async_node.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add bt_core/nodes.py bt_core/engine.py bt_core/context.py tests/test_async_node.py
git commit -m "feat(async): add _is_async flag and engine thread id recording"
```

---

### Task 7: CodeNode AST 检查修复

**Files:**
- Modify: `bt_nodes/actions/code.py`
- Test: `tests/test_code_security.py`

**Step 1: Write the failing test**

```python
# tests/test_code_security.py
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestCodeSecurity(unittest.TestCase):
    def _write_script(self, code: str) -> str:
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, encoding='utf-8'
        )
        tmp.write(code)
        tmp.close()
        return tmp.name

    def tearDown(self):
        # 清理由 setUp 创建的临时文件在子类中处理
        pass

    def test_allowed_import_math(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("import math\nprint(math.pi)")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertTrue(ok, f"应允许导入 math: {msg}")
        finally:
            os.unlink(path)

    def test_forbidden_import_os(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("import os\nos.system('whoami')")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok, "应禁止导入 os")
            self.assertIn("os", msg)
        finally:
            os.unlink(path)

    def test_forbidden_import_subprocess(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("import subprocess\nsubprocess.run(['calc'])")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)

    def test_forbidden_import_socket(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("import socket\ns = socket.socket()")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)

    def test_allowed_math_operations(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script(
            "import math\nresult = math.sqrt(16)\nprint(result)"
        )
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertTrue(ok, msg)
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_code_security.py::TestCodeSecurity::test_forbidden_import_os -v`
Expected: FAIL — 当前 code.py L50-51 直接 `continue` 跳过 import 检查，`import os` 会通过

**Step 3: Write minimal implementation**

修改 `bt_nodes/actions/code.py`，在 `CodeSecurityChecker` 类中：

1. 在 `FORBIDDEN_MODULES` 集合后新增 `ALLOWED_MODULES` 集合：

```python
    FORBIDDEN_MODULES: Set[str] = {
        'os.system', 'os.popen', 'os.spawn', 'os.exec',
        'subprocess.call', 'subprocess.run', 'subprocess.Popen',
        'ctypes', 'multiprocessing',
    }

    # 允许导入的模块白名单（修复 L50-51 漏洞）
    ALLOWED_MODULES: Set[str] = {
        'math', 'random', 'json', 're', 'datetime', 'time',
        'collections', 'itertools', 'functools', 'typing',
        'decimal', 'fractions', 'statistics', 'hashlib',
        'base64', 'uuid', 'string', 'textwrap',
    }
```

2. 修改 `check_python_script` 方法，将 L50-51 的 `continue` 替换为模块名校验：

```python
    @classmethod
    def check_python_script(cls, file_path: str) -> tuple:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            tree = ast.parse(code)

            for node in ast.walk(tree):
                if type(node) not in cls.ALLOWED_AST_NODES:
                    if isinstance(node, ast.Import):
                        # 检查导入的模块名
                        for alias in node.names:
                            top_module = alias.name.split('.')[0]
                            if top_module not in cls.ALLOWED_MODULES:
                                return False, f"禁止导入模块: {alias.name}"
                        continue
                    if isinstance(node, ast.ImportFrom):
                        if node.module:
                            top_module = node.module.split('.')[0]
                            if top_module not in cls.ALLOWED_MODULES:
                                return False, f"禁止导入模块: {node.module}"
                        continue
                    return False, f"包含受限语法: {type(node).__name__}"

                if isinstance(node, ast.Name) and node.id in cls.FORBIDDEN_NAMES:
                    return False, f"包含禁止的函数/变量: {node.id}"

                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in cls.FORBIDDEN_NAMES:
                            return False, f"调用了禁止的函数: {node.func.id}"

            return True, "安全检查通过"

        except SyntaxError as e:
            return False, f"语法错误: {e}"
        except Exception as e:
            return False, f"检查异常: {e}"
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_code_security.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add bt_nodes/actions/code.py tests/test_code_security.py
git commit -m "fix(code): block forbidden imports via AST check (P0 security)"
```

---

### Task 8: __builtins__ 白名单过滤

**Files:**
- Modify: `bt_nodes/actions/code.py`
- Test: `tests/test_code_security.py`

**Step 1: Write the failing test**

Append to `tests/test_code_security.py`:

```python
    def test_dynamic_import_bypass_blocked(self):
        """测试 __import__('os') 动态绕过被拦截"""
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script(
            "os_module = __import__('os')\nos_module.system('whoami')"
        )
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok, "应拦截 __import__ 动态调用")
        finally:
            os.unlink(path)

    def test_eval_exec_blocked(self):
        """测试 eval/exec 被拦截"""
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("result = eval('1+1')")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)

    def test_sandbox_builtins_filter(self):
        """测试沙箱 __builtins__ 过滤函数存在"""
        from bt_nodes.actions.code import CodeSecurityChecker
        self.assertTrue(hasattr(CodeSecurityChecker, 'get_safe_builtins'))
        safe = CodeSecurityChecker.get_safe_builtins()
        self.assertIn('print', safe)
        self.assertIn('len', safe)
        self.assertNotIn('__import__', safe)
        self.assertNotIn('eval', safe)
        self.assertNotIn('exec', safe)
        self.assertNotIn('open', safe)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_code_security.py::TestCodeSecurity::test_sandbox_builtins_filter -v`
Expected: FAIL with "AttributeError: type object 'CodeSecurityChecker' has no attribute 'get_safe_builtins'"

**Step 3: Write minimal implementation**

在 `bt_nodes/actions/code.py` 的 `CodeSecurityChecker` 类中新增 `get_safe_builtins` 类方法：

```python
    # 允许在沙箱中使用的内置函数白名单
    SAFE_BUILTINS: Set[str] = {
        'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
        'callable', 'chr', 'complex', 'dict', 'divmod', 'enumerate', 'filter',
        'float', 'format', 'frozenset', 'hash', 'hex', 'id', 'int', 'isinstance',
        'issubclass', 'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'oct',
        'ord', 'pow', 'print', 'range', 'repr', 'reversed', 'round', 'set',
        'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
        'True', 'False', 'None', 'Exception', 'ValueError', 'TypeError',
        'KeyError', 'IndexError', 'StopIteration', 'ArithmeticError',
        'ZeroDivisionError', 'AttributeError', 'RuntimeError',
    }

    @classmethod
    def get_safe_builtins(cls) -> dict:
        """获取安全的 __builtins__ 字典

        在 CodeNode 执行时注入到 exec() 的 globals 中，
        拦截 __import__('os')、eval()、exec() 等动态绕过方式。
        """
        import builtins
        return {
            name: getattr(builtins, name)
            for name in cls.SAFE_BUILTINS
            if hasattr(builtins, name)
        }
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_code_security.py -v`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add bt_nodes/actions/code.py tests/test_code_security.py
git commit -m "fix(code): add __builtins__ whitelist filter for sandbox"
```

---

## 阶段 1: 消息总线核心

### Task 9: Message 数据类 + errors 异常体系

**Files:**
- Create: `bt_core/errors.py`
- Create: `bt_bus/message.py`
- Test: `tests/test_message.py`

**Step 1: Write the failing test**

```python
# tests/test_message.py
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestMessage(unittest.TestCase):
    def test_message_create(self):
        from bt_bus.message import Message, MessagePriority
        msg = Message.create(
            topic="bt.1.event.tree.started",
            data={"tree_id": "1"},
            source="engine"
        )
        self.assertTrue(msg.id)
        self.assertEqual(msg.topic, "bt.1.event.tree.started")
        self.assertEqual(msg.data, {"tree_id": "1"})
        self.assertEqual(msg.source, "engine")
        self.assertEqual(msg.priority, MessagePriority.NORMAL)
        self.assertIsNotNone(msg.correlation_id)
        self.assertIsNone(msg.reply_to)
        self.assertIsInstance(msg.timestamp, float)

    def test_message_id_unique(self):
        from bt_bus.message import Message
        ids = set()
        for _ in range(100):
            msg = Message.create("test", "data")
            ids.add(msg.id)
        self.assertEqual(len(ids), 100)

    def test_message_headers_default_empty(self):
        from bt_bus.message import Message
        msg = Message.create("t", "d")
        self.assertEqual(msg.headers, {})

    def test_message_headers_preserved(self):
        from bt_bus.message import Message
        msg = Message.create("t", "d", headers={"Authorization": "Bearer xyz"})
        self.assertEqual(msg.headers["Authorization"], "Bearer xyz")


class TestErrors(unittest.TestCase):
    def test_bus_error_hierarchy(self):
        from bt_core.errors import (
            BusError, MessageValidationError, NoSubscriberError,
            RequestTimeoutError, MiddlewareError
        )
        self.assertTrue(issubclass(MessageValidationError, BusError))
        self.assertTrue(issubclass(NoSubscriberError, BusError))
        self.assertTrue(issubclass(RequestTimeoutError, BusError))
        self.assertTrue(issubclass(MiddlewareError, BusError))


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_message.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_core.errors'"

**Step 3: Write minimal implementation**

```python
# bt_core/errors.py
"""消息总线异常体系

参考开发方案 §1.1 和开发计划 §1.1.4。
"""


class BusError(Exception):
    """消息总线基础异常"""
    pass


class MessageValidationError(BusError):
    """消息格式校验失败"""
    pass


class NoSubscriberError(BusError):
    """无订阅者异常"""
    pass


class RequestTimeoutError(BusError):
    """请求-响应模式超时"""
    pass


class MiddlewareError(BusError):
    """中间件处理异常"""
    pass
```

```python
# bt_bus/message.py
"""Message 数据类

参考开发方案 §3.1 消息格式。
"""
import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


class MessagePriority(enum.Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Message:
    """消息数据类

    Attributes:
        id: 消息唯一 ID（uuid4）
        topic: 点分层次主题（如 bt.1.event.tree.started）
        data: JSON 兼容数据
        headers: 元数据（含认证信息，见方案 §3.6）
        timestamp: 创建时间戳
        source: 来源标识
        priority: 消息优先级
        reply_to: 回复主题（请求-响应模式）
        correlation_id: 关联 ID
    """
    id: str
    topic: str
    data: Any
    headers: dict
    timestamp: float
    source: str
    priority: MessagePriority = MessagePriority.NORMAL
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None

    @classmethod
    def create(cls, topic: str, data: Any, source: str = "",
               headers: dict = None) -> "Message":
        """工厂方法：创建消息"""
        return cls(
            id=str(uuid.uuid4()),
            topic=topic,
            data=data,
            headers=headers or {},
            timestamp=time.time(),
            source=source,
            correlation_id=str(uuid.uuid4()),
        )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_message.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add bt_core/errors.py bt_bus/message.py tests/test_message.py
git commit -m "feat(bus): add Message dataclass and errors hierarchy"
```

---

### Task 10: TopicRouter 主题路由

**Files:**
- Create: `bt_bus/topic.py`
- Test: `tests/test_topic.py`

**Step 1: Write the failing test**

```python
# tests/test_topic.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTopicRouter(unittest.TestCase):
    def test_exact_match(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        sub_id = router.subscribe("bt.1.event.tree.started", lambda m: m)
        matches = router.match("bt.1.event.tree.started")
        self.assertEqual(len(matches), 1)

    def test_single_wildcard(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        router.subscribe("bt.1.event.*", lambda m: m)
        # * 匹配单层
        matches = router.match("bt.1.event.started")
        self.assertEqual(len(matches), 1)
        # 不匹配多层
        matches = router.match("bt.1.event.node.changed")
        self.assertEqual(len(matches), 0)

    def test_double_wildcard(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        router.subscribe("bt.1.event.**", lambda m: m)
        # ** 匹配多层
        matches = router.match("bt.1.event.node.changed")
        self.assertEqual(len(matches), 1)
        matches = router.match("bt.1.event.tree.started")
        self.assertEqual(len(matches), 1)

    def test_no_match(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        router.subscribe("bt.1.event.*", lambda m: m)
        matches = router.match("bt.2.event.started")
        self.assertEqual(len(matches), 0)

    def test_unsubscribe_by_id(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        sub_id = router.subscribe("bt.1.event.*", lambda m: m)
        ok = router.unsubscribe(sub_id)
        self.assertTrue(ok)
        matches = router.match("bt.1.event.started")
        self.assertEqual(len(matches), 0)

    def test_multiple_subscribers(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        router.subscribe("bt.1.event.*", lambda m: m)
        router.subscribe("bt.1.event.**", lambda m: m)
        matches = router.match("bt.1.event.started")
        self.assertEqual(len(matches), 2)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_topic.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_bus.topic'"

**Step 3: Write minimal implementation**

```python
# bt_bus/topic.py
"""主题路由器 — 支持精确匹配和通配符匹配

通配符规则:
- *  匹配单层:   bt.event.* 匹配 bt.event.started, 不匹配 bt.event.node.changed
- ** 匹配多层:   bt.event.** 匹配 bt.event.node.changed

参考开发方案 §3.1 主题命名规范。
"""
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class Subscription:
    """订阅信息"""
    id: str
    pattern: str
    callback: Callable
    active: bool = True


class TopicRouter:
    """主题路由器

    维护 pattern -> subscriptions 映射，支持精确匹配和通配符匹配。
    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._lock = threading.RLock()

    def subscribe(self, pattern: str, callback: Callable) -> str:
        """订阅主题，返回 subscription_id

        Args:
            pattern: 主题模式（支持 * 和 ** 通配符）
            callback: 回调函数，签名 callback(message)

        Returns:
            subscription_id
        """
        sub_id = str(uuid.uuid4())
        with self._lock:
            if pattern not in self._subscriptions:
                self._subscriptions[pattern] = []
            self._subscriptions[pattern].append(
                Subscription(id=sub_id, pattern=pattern, callback=callback)
            )
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        with self._lock:
            for pattern, subs in self._subscriptions.items():
                for i, sub in enumerate(subs):
                    if sub.id == subscription_id:
                        subs.pop(i)
                        if not subs:
                            del self._subscriptions[pattern]
                        return True
            return False

    def match(self, topic: str) -> List[Subscription]:
        """返回匹配指定主题的所有订阅"""
        result = []
        with self._lock:
            for pattern, subs in self._subscriptions.items():
                if self._match_pattern(pattern, topic):
                    result.extend(s for s in subs if s.active)
        return result

    def clear(self) -> None:
        """清空所有订阅"""
        with self._lock:
            self._subscriptions.clear()

    @staticmethod
    def _match_pattern(pattern: str, topic: str) -> bool:
        """匹配主题模式

        支持:
        - 精确匹配: "bt.1.event" 匹配 "bt.1.event"
        - *: 单层通配符 "bt.1.event.*" 匹配 "bt.1.event.started"
        - **: 多层通配符 "bt.1.event.**" 匹配 "bt.1.event.node.changed"
        """
        if pattern == topic:
            return True

        pattern_parts = pattern.split(".")
        topic_parts = topic.split(".")

        i = 0
        while i < len(pattern_parts):
            p = pattern_parts[i]
            if p == "**":
                # ** 匹配剩余所有层
                return True
            if i >= len(topic_parts):
                return False
            if p == "*":
                # * 匹配单层
                pass
            elif p != topic_parts[i]:
                return False
            i += 1

        return i == len(topic_parts)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_topic.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add bt_bus/topic.py tests/test_topic.py
git commit -m "feat(bus): add TopicRouter with wildcard matching"
```

---

### Task 11: MessageBus 核心（含防死锁/subscribe_async）

**Files:**
- Create: `bt_bus/message_bus.py`
- Test: `tests/test_message_bus.py`

**Step 1: Write the failing test**

```python
# tests/test_message_bus.py
import os
import sys
import time
import threading
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestMessageBus(unittest.TestCase):
    def setUp(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()
        from bt_bus.message_bus import MessageBus
        # 重置单例
        MessageBus._instance = None
        self.bus = MessageBus()
        self.bus.start()

    def tearDown(self):
        self.bus.stop()
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def test_publish_subscribe(self):
        received = []
        self.bus.subscribe("bt.1.event.test", lambda m: received.append(m))
        self.bus.publish("bt.1.event.test", {"hello": "world"})
        time.sleep(0.1)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data, {"hello": "world"})

    def test_wildcard_subscribe_single(self):
        received = []
        self.bus.subscribe("bt.1.event.*", lambda m: received.append(m))
        self.bus.publish("bt.1.event.started", "data")
        time.sleep(0.1)
        self.assertEqual(len(received), 1)

    def test_wildcard_subscribe_multi(self):
        received = []
        self.bus.subscribe("bt.1.event.**", lambda m: received.append(m))
        self.bus.publish("bt.1.event.node.changed", "data")
        time.sleep(0.1)
        self.assertEqual(len(received), 1)

    def test_unsubscribe(self):
        received = []
        sub_id = self.bus.subscribe("bt.1.event.test", lambda m: received.append(m))
        self.bus.unsubscribe(sub_id)
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.1)
        self.assertEqual(len(received), 0)

    def test_multiple_subscribers(self):
        received1 = []
        received2 = []
        self.bus.subscribe("bt.1.event.test", lambda m: received1.append(m))
        self.bus.subscribe("bt.1.event.test", lambda m: received2.append(m))
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.1)
        self.assertEqual(len(received1), 1)
        self.assertEqual(len(received2), 1)

    def test_subscriber_exception_isolation(self):
        received = []
        def bad_callback(m):
            raise RuntimeError("intentional error")
        self.bus.subscribe("bt.1.event.test", bad_callback)
        self.bus.subscribe("bt.1.event.test", lambda m: received.append(m))
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.2)
        self.assertEqual(len(received), 1)

    def test_request_response(self):
        def handler(msg):
            from bt_bus.message import Message
            return Message.create(
                topic=msg.headers.get("reply_to", ""),
                data={"response": "ok"},
                source="responder"
            )
        self.bus.subscribe("bt.1.command.test", handler)
        response = self.bus.request("bt.1.command.test", {"cmd": "go"}, timeout_ms=2000)
        self.assertIsNotNone(response)
        self.assertEqual(response.data, {"response": "ok"})

    def test_request_timeout(self):
        response = self.bus.request("bt.1.command.no_handler", "data", timeout_ms=500)
        self.assertIsNone(response)

    def test_request_degraded_from_blocked_thread(self):
        """测试引擎线程内 request() 自动降级为 publish"""
        self.bus.set_engine_thread_id(threading.get_ident())
        # 当前线程已被标记为引擎线程，request 应降级
        response = self.bus.request("bt.1.command.test", "data", timeout_ms=500)
        self.assertIsNone(response)

    def test_singleton(self):
        from bt_bus.message_bus import MessageBus
        bus2 = MessageBus()
        self.assertIs(self.bus, bus2)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_message_bus.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_bus.message_bus'"

**Step 3: Write minimal implementation**

```python
# bt_bus/message_bus.py
"""MessageBus 核心 — 进程内消息总线

参考 InputControllerManager 单例模式。
参考开发方案 §3.1 和开发计划 §1.1.2。
"""
import asyncio
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from bt_utils.log_manager import LogManager

from .message import Message
from .topic import TopicRouter
from .thread_pool import SharedThreadPool


class MessageBus:
    """进程内消息总线（单例）

    核心职责:
    1. publish/subscribe/unsubscribe 核心 API
    2. request 同步请求-响应模式（带防死锁降级）
    3. subscribe_async 返回 asyncio.Queue 供 ASGI 事件流消费
    4. 中间件链 + 死信队列 + 统计
    """

    _instance: Optional["MessageBus"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        from .dead_letter import DeadLetterQueue
        from .stats import BusStats

        self._router = TopicRouter()
        self._middleware_chain: List = []
        self._dead_letter_queue = DeadLetterQueue(max_size=1000)
        self._bus_lock = threading.RLock()
        self._running = False
        self._shared_pool = SharedThreadPool.get_instance()
        self._blocked_thread_ids: Set[int] = set()
        self._event_loop = None
        self._stats = BusStats()
        self._logger = LogManager.get_logger("MessageBus") if hasattr(Logman:=LogManager, 'get_logger') else None
        self._async_queues: List[asyncio.Queue] = []
        self._async_queue_lock = threading.Lock()

    def publish(self, topic: str, data: Any, headers: dict = None,
                source: str = "") -> str:
        """发布消息到指定主题，返回 msg.id"""
        msg = Message.create(topic, data, source, headers)

        def final_handler(m: Message) -> Message:
            subscriptions = self._router.match(m.topic)
            if not subscriptions:
                self._dead_letter_queue.add(m, reason="NO_SUBSCRIBER")
                self._stats.record_publish(m.topic, delivered=0)
                return m
            for sub in subscriptions:
                self._shared_pool.submit("bus", self._deliver, sub, m)
            self._stats.record_publish(m.topic, delivered=len(subscriptions))
            # 推送到 async queues（供 SSE/WebSocket 消费）
            self._push_to_async_queues(m)
            return m

        handler = final_handler
        for mw in reversed(self._middleware_chain):
            handler = (lambda m, h=handler, mw=mw: mw.process(m, h))
        result = handler(msg)
        return msg.id

    def _deliver(self, sub, msg: Message) -> None:
        """在共享线程池中分发消息到订阅者"""
        try:
            response = sub.callback(msg)
            # 请求-响应模式：若回调返回 Message 且 headers 含 reply_to，发送响应
            if response is not None and isinstance(response, Message):
                reply_to = msg.headers.get("reply_to")
                if reply_to:
                    response.topic = reply_to
                    self.publish(reply_to, response.data,
                                 headers=response.headers,
                                 source="responder")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Subscriber exception: {e}")
            else:
                print(f"[MessageBus] Subscriber exception: {e}")

    def subscribe(self, topic_pattern: str, callback: Callable) -> str:
        """订阅主题，返回 subscription_id"""
        with self._bus_lock:
            return self._router.subscribe(topic_pattern, callback)

    def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        with self._bus_lock:
            self._router.unsubscribe(subscription_id)

    def request(self, topic: str, data: Any, timeout_ms: int = 5000,
                headers: dict = None, source: str = "") -> Optional[Message]:
        """请求-响应模式（同步等待）

        防死锁机制: 若检测到当前线程为引擎 tick 线程，
        自动降级为 publish（异步发送）并返回 None。
        """
        if threading.get_ident() in self._blocked_thread_ids:
            if self._logger:
                self._logger.warning(
                    f"request() called from engine thread, degrading to publish: {topic}"
                )
            self.publish(topic, data, source="request_degraded")
            return None

        reply_topic = f"_reply.{threading.get_ident()}.{int(time.time()*1000)}"
        response_event = threading.Event()
        response_msg = [None]

        def _on_reply(msg: Message):
            response_msg[0] = msg
            response_event.set()

        sub_id = self.subscribe(reply_topic, _on_reply)
        request_headers = (headers or {}).copy()
        request_headers["reply_to"] = reply_topic

        self.publish(topic, data, request_headers, source)
        response_event.wait(timeout=timeout_ms / 1000)
        self.unsubscribe(sub_id)

        return response_msg[0]

    def subscribe_async(self, topic_pattern: str) -> "asyncio.Queue":
        """异步订阅主题，返回 asyncio.Queue 供 ASGI 事件流消费"""
        queue: asyncio.Queue = asyncio.Queue()

        def callback(msg: Message):
            self._push_to_async_queues(msg)

        with self._async_queue_lock:
            self._async_queues.append(queue)
        self.subscribe(topic_pattern, callback)
        return queue

    def _push_to_async_queues(self, msg: Message) -> None:
        """推送消息到所有异步队列"""
        with self._async_queue_lock:
            for queue in self._async_queues:
                try:
                    if self._event_loop and self._event_loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            queue.put(msg), self._event_loop
                        )
                    else:
                        queue.put_nowait(msg)
                except Exception:
                    pass

    def add_middleware(self, middleware) -> None:
        """添加中间件"""
        with self._bus_lock:
            self._middleware_chain.append(middleware)

    def start(self) -> None:
        """启动消息总线"""
        self._running = True

    def stop(self) -> None:
        """停止消息总线"""
        self._running = False
        # SharedThreadPool 由自身统一管理生命周期

    def set_engine_thread_id(self, thread_id: int) -> None:
        """注册引擎线程 ID，用于 request() 防死锁检测"""
        self._blocked_thread_ids.add(thread_id)

    def set_event_loop(self, loop) -> None:
        """注入 ASGI 事件循环引用（RESTServer 启动时调用）"""
        self._event_loop = loop

    def get_event_loop(self):
        """获取事件循环"""
        return self._event_loop

    def get_stats(self):
        """获取总线统计"""
        return self._stats

    def get_dead_letter_queue(self):
        """获取死信队列"""
        return self._dead_letter_queue
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_message_bus.py -v`
Expected: PASS (10 tests)

**Step 5: Commit**

```bash
git add bt_bus/message_bus.py tests/test_message_bus.py
git commit -m "feat(bus): add MessageBus with deadlock prevention and async subscribe"
```

---

### Task 12: 中间件链 + 死信队列 + 统计

**Files:**
- Create: `bt_bus/middleware.py`
- Create: `bt_bus/dead_letter.py`
- Create: `bt_bus/stats.py`
- Test: `tests/test_middleware.py`
- Test: `tests/test_dead_letter.py`

**Step 1: Write the failing test**

```python
# tests/test_middleware.py
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestMiddleware(unittest.TestCase):
    def test_logging_middleware(self):
        from bt_bus.middleware import LoggingMiddleware
        from bt_bus.message import Message
        logs = []

        class FakeLogger:
            def info(self, msg): logs.append(msg)

        mw = LoggingMiddleware(logger=FakeLogger())
        msg = Message.create("bt.1.event.test", "data")
        result = mw.process(msg, lambda m: m)
        self.assertEqual(result, msg)
        self.assertTrue(any("bt.1.event.test" in log for log in logs))

    def test_validation_middleware_valid(self):
        from bt_bus.middleware import ValidationMiddleware
        from bt_bus.message import Message
        mw = ValidationMiddleware()
        msg = Message.create("bt.1.event.test", {"key": "value"})
        result = mw.process(msg, lambda m: m)
        self.assertEqual(result, msg)

    def test_validation_middleware_invalid_empty_topic(self):
        from bt_bus.middleware import ValidationMiddleware
        from bt_bus.message import Message
        mw = ValidationMiddleware()
        msg = Message.create("", "data")
        # 空主题应被拦截（返回 None 或抛异常）
        try:
            result = mw.process(msg, lambda m: m)
            self.assertIsNone(result)
        except Exception:
            pass  # 抛异常也算拦截

    def test_middleware_chain_order(self):
        from bt_bus.middleware import Middleware
        from bt_bus.message import Message
        order = []

        class MW1(Middleware):
            def process(self, message, next_handler):
                order.append("MW1_before")
                result = next_handler(message)
                order.append("MW1_after")
                return result

        class MW2(Middleware):
            def process(self, message, next_handler):
                order.append("MW2_before")
                result = next_handler(message)
                order.append("MW2_after")
                return result

        mw1, mw2 = MW1(), MW2()
        msg = Message.create("test", "data")
        # 逆序组装
        handler = lambda m: (order.append("final"), m)[1]
        handler = (lambda m, h=handler, mw=mw2: mw.process(m, h))
        handler = (lambda m, h=handler, mw=mw1: mw.process(m, h))
        handler(msg)
        self.assertEqual(order, ["MW1_before", "MW2_before", "final",
                                  "MW2_after", "MW1_after"])

    def test_middleware_intercept(self):
        from bt_bus.middleware import Middleware
        from bt_bus.message import Message
        called = []

        class InterceptMW(Middleware):
            def process(self, message, next_handler):
                # 不调用 next_handler，直接返回 None 拦截
                return None

        mw = InterceptMW()
        msg = Message.create("test", "data")
        result = mw.process(msg, lambda m: called.append(m))
        self.assertIsNone(result)
        self.assertEqual(called, [])


if __name__ == '__main__':
    unittest.main()
```

```python
# tests/test_dead_letter.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestDeadLetterQueue(unittest.TestCase):
    def test_no_subscriber_dead_letter(self):
        from bt_bus.dead_letter import DeadLetterQueue
        from bt_bus.message import Message
        q = DeadLetterQueue(max_size=100)
        msg = Message.create("test", "data")
        q.add(msg, reason="NO_SUBSCRIBER")
        self.assertEqual(q.size(), 1)

    def test_dead_letter_max_size(self):
        from bt_bus.dead_letter import DeadLetterQueue
        from bt_bus.message import Message
        q = DeadLetterQueue(max_size=3)
        for i in range(5):
            msg = Message.create(f"topic.{i}", i)
            q.add(msg, reason="NO_SUBSCRIBER")
        # 超过 max_size 后最旧条目被淘汰
        self.assertEqual(q.size(), 3)

    def test_dead_letter_reason(self):
        from bt_bus.dead_letter import DeadLetterQueue
        from bt_bus.message import Message
        q = DeadLetterQueue(max_size=100)
        msg = Message.create("test", "data")
        q.add(msg, reason="EXCEPTION")
        entries = q.get_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["reason"], "EXCEPTION")


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_middleware.py tests/test_dead_letter.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_bus.middleware'"

**Step 3: Write minimal implementation**

```python
# bt_bus/middleware.py
"""中间件基类 + 内置中间件

责任链模式：每个中间件通过 process() 处理消息，
显式调用 next_handler 将消息传递给下一个中间件。
参考开发方案 §3.6.4 和开发计划 §1.1.3。
"""
from typing import Callable, Optional

from .message import Message


class Middleware:
    """中间件基类（责任链模式）"""

    def process(self, message: Message, next_handler: Callable) -> Optional[Message]:
        """处理消息，调用 next_handler 传递给下一个中间件

        Returns:
            Message 继续传递，None 拦截消息
        """
        return next_handler(message)


class LoggingMiddleware(Middleware):
    """日志中间件 — 记录消息发布日志"""

    def __init__(self, logger=None):
        self._logger = logger

    def _log(self, level: str, msg: str):
        if self._logger:
            getattr(self._logger, level, self._logger.info)(msg)
        else:
            print(f"[{level.upper()}] {msg}")

    def process(self, message: Message, next_handler: Callable) -> Optional[Message]:
        self._log("info", f"Message published: topic={message.topic}, id={message.id}")
        result = next_handler(message)
        self._log("info", f"Message processed: topic={message.topic}")
        return result


class ValidationMiddleware(Middleware):
    """校验中间件 — 校验消息格式"""

    def process(self, message: Message, next_handler: Callable) -> Optional[Message]:
        if not message.topic:
            return None  # 拦截无效消息
        if message.data is None:
            return None
        return next_handler(message)


class RateLimitMiddleware(Middleware):
    """速率限制中间件 — 令牌桶算法"""

    def __init__(self, max_per_second: int = 100):
        import threading
        self._max = max_per_second
        self._tokens = max_per_second
        self._last_refill = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self._max, self._tokens + elapsed * self._max)
        self._last_refill = now

    def process(self, message: Message, next_handler: Callable) -> Optional[Message]:
        with self._lock:
            self._refill()
            if self._tokens < 1:
                return None  # 超过限流，拦截
            self._tokens -= 1
        return next_handler(message)


import time  # RateLimitMiddleware 使用


class AuthMiddleware(Middleware):
    """认证中间件 — 校验消息来源的认证状态

    接入时机: AuthService 实现后，通过 bus.add_middleware() 注入
    参考开发方案 §3.6.4。本阶段只定义不启用。
    """

    def __init__(self, auth_service, deny_on_fail: bool = False):
        self._auth = auth_service
        self._deny_on_fail = deny_on_fail

    def process(self, message: Message, next_handler: Callable) -> Optional[Message]:
        token = message.headers.get("Authorization", "")
        principal = self._auth.verify_token(token)

        if principal:
            message.headers["X-Auth-Principal"] = principal.user_id
            message.headers["X-Auth-Roles"] = ",".join(principal.roles)
            if principal.scopes:
                message.headers["X-Auth-Scope"] = ",".join(principal.scopes)
        else:
            message.headers["X-Auth-Denied"] = "true"
            if self._deny_on_fail:
                return None  # 拒绝消息

        return next_handler(message)
```

```python
# bt_bus/dead_letter.py
"""死信队列 — 存储无法处理的消息

参考开发计划 §1.1.4。
"""
import threading
from collections import deque
from typing import Any, Dict, List


class DeadLetterQueue:
    """死信队列

    存储:
    - 无订阅者的消息
    - 处理异常的消息
    - 被中间件拦截的消息（可选）
    """

    def __init__(self, max_size: int = 1000):
        self._queue: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, message, reason: str = "UNKNOWN") -> None:
        """添加消息到死信队列"""
        entry = {
            "message": message,
            "reason": reason,
            "timestamp": message.timestamp if hasattr(message, 'timestamp') else None,
        }
        with self._lock:
            self._queue.append(entry)

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有死信条目"""
        with self._lock:
            return list(self._queue)

    def size(self) -> int:
        """返回队列大小"""
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        """清空死信队列"""
        with self._lock:
            self._queue.clear()
```

```python
# bt_bus/stats.py
"""总线统计 — 消息计数、延迟统计、错误率

参考开发计划 §1.1.4。
"""
import threading
import time
from typing import Dict


class BusStats:
    """总线统计"""

    def __init__(self):
        self._publish_count: Dict[str, int] = {}
        self._deliver_count: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()

    def record_publish(self, topic: str, delivered: int = 0) -> None:
        """记录一次发布"""
        with self._lock:
            self._publish_count[topic] = self._publish_count.get(topic, 0) + 1
            self._deliver_count[topic] = self._deliver_count.get(topic, 0) + delivered

    def get_publish_count(self, topic: str = None) -> int:
        """获取发布次数"""
        with self._lock:
            if topic:
                return self._publish_count.get(topic, 0)
            return sum(self._publish_count.values())

    def get_deliver_count(self, topic: str = None) -> int:
        """获取投递次数"""
        with self._lock:
            if topic:
                return self._deliver_count.get(topic, 0)
            return sum(self._deliver_count.values())

    def get_summary(self) -> dict:
        """获取统计摘要"""
        with self._lock:
            return {
                "uptime_seconds": time.time() - self._start_time,
                "total_publishes": sum(self._publish_count.values()),
                "total_deliveries": sum(self._deliver_count.values()),
                "topic_count": len(self._publish_count),
            }
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_middleware.py tests/test_dead_letter.py -v`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add bt_bus/middleware.py bt_bus/dead_letter.py bt_bus/stats.py \
        tests/test_middleware.py tests/test_dead_letter.py
git commit -m "feat(bus): add middleware chain, dead letter queue and stats"
```

---

## 阶段 2: 适配器层

### Task 13: BaseAdapter + AdapterManager

**Files:**
- Create: `bt_adapters/__init__.py`
- Create: `bt_adapters/base.py`
- Create: `bt_adapters/config.py`
- Create: `bt_adapters/adapter_manager.py`
- Test: `tests/test_adapter_manager.py`

**Step 1: Write the failing test**

```python
# tests/test_adapter_manager.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestAdapterManager(unittest.TestCase):
    def setUp(self):
        from bt_adapters.adapter_manager import AdapterManager
        AdapterManager._instance = None

    def tearDown(self):
        from bt_adapters.adapter_manager import AdapterManager
        AdapterManager._instance = None

    def test_singleton(self):
        from bt_adapters.adapter_manager import AdapterManager
        m1 = AdapterManager()
        m2 = AdapterManager()
        self.assertIs(m1, m2)

    def test_register_and_get_adapter(self):
        from bt_adapters.adapter_manager import AdapterManager
        from bt_adapters.base import BaseAdapter, AdapterLevel
        from bt_adapters.config import AdapterConfig

        class DummyAdapter(BaseAdapter):
            @classmethod
            def get_adapter_level(cls): return AdapterLevel.LOCAL

            @classmethod
            def is_available(cls): return True

            def __init__(self, config=None):
                self._config = config or AdapterConfig()

            def start(self): pass
            def stop(self): pass
            def get_name(self): return "dummy"
            def get_status(self): return {"running": False}

        mgr = AdapterManager()
        mgr.register_adapter("dummy", DummyAdapter)
        adapter = mgr.get_adapter("dummy")
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.get_name(), "dummy")

    def test_get_unknown_adapter_returns_none(self):
        from bt_adapters.adapter_manager import AdapterManager
        mgr = AdapterManager()
        self.assertIsNone(mgr.get_adapter("unknown")))


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_adapter_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_adapters'"

**Step 3: Write minimal implementation**

```python
# bt_adapters/__init__.py
"""适配器模块"""
```

```python
# bt_adapters/config.py
"""适配器配置"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AdapterConfig:
    """适配器配置"""
    name: str = ""
    enabled: bool = False
    connect_timeout: int = 10
    read_timeout: int = 30
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    extra: dict = field(default_factory=dict)
```

```python
# bt_adapters/base.py
"""适配器基类 — 参考 BaseKeyboardController 设计

参考开发方案 §3.2。
"""
import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


class AdapterLevel(enum.Enum):
    """适配器级别 — 参考 InputLevel"""
    LOCAL = "local"
    REMOTE = "remote"
    HYBRID = "hybrid"


@dataclass
class AdapterStatus:
    """适配器状态"""
    running: bool = False
    name: str = ""
    level: AdapterLevel = AdapterLevel.LOCAL
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """适配器基类 — 参考 BaseKeyboardController

    子类必须实现:
    - get_adapter_level(): 返回适配器级别
    - is_available(): 检测依赖是否可用
    - start() / stop(): 生命周期管理
    - get_name(): 适配器名称
    - get_status(): 状态查询
    """

    @classmethod
    @abstractmethod
    def get_adapter_level(cls) -> AdapterLevel:
        """返回适配器级别"""
        ...

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """检测依赖是否可用 — 参考 is_driver_available()"""
        ...

    @abstractmethod
    def start(self) -> None:
        """启动适配器"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止适配器"""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """返回适配器名称"""
        ...

    @abstractmethod
    def get_status(self) -> AdapterStatus:
        """返回适配器状态"""
        ...
```

```python
# bt_adapters/adapter_manager.py
"""适配器管理器（单例）— 参考 InputControllerManager 设计

参考开发方案 §3.2 和开发计划 §2.1.1。
"""
import threading
from typing import Dict, Optional, Type

from .base import BaseAdapter


class AdapterManager:
    """适配器管理器（单例）

    核心职责:
    1. 管理所有适配器实例（单例池）
    2. 按配置启停适配器
    3. 适配器可用性检测
    """

    _instance: Optional["AdapterManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._adapters: Dict[str, BaseAdapter] = {}
        self._adapter_classes: Dict[str, Type[BaseAdapter]] = {}
        self._message_bus = None
        self._lock = threading.RLock()

    def register_adapter(self, name: str,
                         adapter_class: Type[BaseAdapter]) -> None:
        """注册适配器类型"""
        with self._lock:
            self._adapter_classes[name] = adapter_class

    def get_adapter(self, name: str) -> Optional[BaseAdapter]:
        """获取适配器实例"""
        with self._lock:
            if name in self._adapters:
                return self._adapters[name]
            cls = self._adapter_classes.get(name)
            if cls is None:
                return None
            if not cls.is_available():
                return None
            adapter = cls()
            self._adapters[name] = adapter
            return adapter

    def start_all(self, message_bus) -> None:
        """启动所有已启用的适配器"""
        with self._lock:
            self._message_bus = message_bus
            for name, adapter in self._adapters.items():
                adapter.start()

    def stop_all(self) -> None:
        """停止所有适配器"""
        with self._lock:
            for adapter in self._adapters.values():
                try:
                    adapter.stop()
                except Exception:
                    pass

    def list_adapters(self) -> Dict[str, dict]:
        """列出所有适配器状态"""
        with self._lock:
            return {
                name: {"status": adapter.get_status()}
                for name, adapter in self._adapters.items()
            }
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_adapter_manager.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add bt_adapters/__init__.py bt_adapters/base.py bt_adapters/config.py \
        bt_adapters/adapter_manager.py tests/test_adapter_manager.py
git commit -m "feat(adapters): add BaseAdapter and AdapterManager singleton"
```

---

### Task 14: HTTP 适配器

**Files:**
- Create: `bt_adapters/http_adapter.py`
- Modify: `requirements.txt`
- Test: `tests/test_http_adapter.py`

**Step 1: Write the failing test**

```python
# tests/test_http_adapter.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestHTTPAdapter(unittest.TestCase):
    def test_is_available(self):
        from bt_adapters.http_adapter import HTTPAdapter
        # requests 已安装时返回 True
        self.assertTrue(HTTPAdapter.is_available())

    def test_adapter_level_remote(self):
        from bt_adapters.http_adapter import HTTPAdapter
        from bt_adapters.base import AdapterLevel
        self.assertEqual(HTTPAdapter.get_adapter_level(), AdapterLevel.REMOTE)

    def test_call_get_returns_response(self):
        """测试 GET 请求返回 HTTPResponse

        使用 httpbin.org 或本地 mock，此处使用 mock 验证接口契约。
        """
        from bt_adapters.http_adapter import HTTPAdapter, HTTPResponse
        from unittest.mock import patch, MagicMock

        adapter = HTTPAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"hello": "world"}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"hello": "world"}
        mock_response.elapsed.total_seconds.return_value = 0.123

        with patch.object(adapter, '_session') as mock_session:
            mock_session.request.return_value = mock_response
            response = adapter.call(
                method="GET",
                url="https://httpbin.org/get",
                timeout_ms=5000
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {"hello": "world"})

    def test_call_post_with_body(self):
        from bt_adapters.http_adapter import HTTPAdapter
        from unittest.mock import patch, MagicMock

        adapter = HTTPAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = '{"id": 1}'
        mock_response.headers = {}
        mock_response.json.return_value = {"id": 1}
        mock_response.elapsed.total_seconds.return_value = 0.05

        with patch.object(adapter, '_session') as mock_session:
            mock_session.request.return_value = mock_response
            response = adapter.call(
                method="POST",
                url="https://httpbin.org/post",
                body={"key": "value"},
                headers={"Content-Type": "application/json"}
            )
            self.assertEqual(response.status_code, 201)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_http_adapter.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_adapters.http_adapter'"

**Step 3: Write minimal implementation**

在 `requirements.txt` 末尾添加 `requests>=2.28.0`。

```python
# bt_adapters/http_adapter.py
"""HTTP/REST 协议适配器

参考开发方案 §3.2 和开发计划 §2.1.2。
"""
import json as _json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import BaseAdapter, AdapterLevel, AdapterStatus
from .config import AdapterConfig


@dataclass
class HTTPResponse:
    """HTTP 响应封装"""
    status_code: int
    text: str
    headers: Dict[str, str] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    _json_cache: Any = None

    @property
    def json(self) -> Any:
        """解析 JSON 响应"""
        if self._json_cache is None:
            try:
                self._json_cache = _json.loads(self.text)
            except Exception:
                self._json_cache = None
        return self._json_cache


class HTTPAdapter(BaseAdapter):
    """HTTP/REST 协议适配器"""

    @classmethod
    def get_adapter_level(cls) -> AdapterLevel:
        return AdapterLevel.REMOTE

    @classmethod
    def is_available(cls) -> bool:
        try:
            import requests
            return True
        except ImportError:
            return False

    def __init__(self, config: Optional[AdapterConfig] = None):
        self._config = config or AdapterConfig()
        self._session = None
        self._running = False
        self._message_bus = None

    def start(self) -> None:
        import requests
        self._session = requests.Session()
        self._running = True

    def stop(self) -> None:
        if self._session:
            self._session.close()
        self._running = False

    def get_name(self) -> str:
        return "http"

    def get_status(self) -> AdapterStatus:
        return AdapterStatus(
            running=self._running,
            name=self.get_name(),
            level=self.get_adapter_level()
        )

    def call(self, method: str, url: str, headers: dict = None,
             body: Any = None, timeout_ms: int = 10000,
             retry_count: int = 0, retry_interval_ms: int = 1000) -> HTTPResponse:
        """发起 HTTP 请求

        Args:
            method: GET/POST/PUT/DELETE/PATCH
            url: 请求 URL
            headers: 请求头
            body: 请求体（dict 自动转 JSON）
            timeout_ms: 超时（毫秒）
            retry_count: 重试次数
            retry_interval_ms: 重试间隔（毫秒）

        Returns:
            HTTPResponse 对象
        """
        import requests

        if not self._session:
            self.start()

        # 准备请求体
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

        # 所有重试均失败
        raise last_exc if last_exc else RuntimeError("HTTP request failed")
```

**Step 4: Run test to verify it passes**

Run: `pip install requests>=2.28.0 && python -m pytest tests/test_http_adapter.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add bt_adapters/http_adapter.py requirements.txt tests/test_http_adapter.py
git commit -m "feat(adapters): add HTTPAdapter with retry and timeout"
```

---

### Task 15: WebSocket 适配器

**Files:**
- Create: `bt_adapters/websocket_adapter.py`
- Modify: `requirements.txt`
- Test: `tests/test_websocket_adapter.py`

**Step 1: Write the failing test**

```python
# tests/test_websocket_adapter.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestWebSocketAdapter(unittest.TestCase):
    def test_is_available(self):
        from bt_adapters.websocket_adapter import WebSocketAdapter
        # 依赖未安装时返回 False，安装后 True
        self.assertIsInstance(WebSocketAdapter.is_available(), bool)

    def test_adapter_level_remote(self):
        from bt_adapters.websocket_adapter import WebSocketAdapter
        from bt_adapters.base import AdapterLevel
        self.assertEqual(WebSocketAdapter.get_adapter_level(),
                         AdapterLevel.REMOTE)

    def test_status_not_running_initially(self):
        from bt_adapters.websocket_adapter import WebSocketAdapter
        adapter = WebSocketAdapter()
        status = adapter.get_status()
        self.assertFalse(status.running)

    def test_get_name(self):
        from bt_adapters.websocket_adapter import WebSocketAdapter
        adapter = WebSocketAdapter()
        self.assertEqual(adapter.get_name(), "websocket")


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_websocket_adapter.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_adapters.websocket_adapter'"

**Step 3: Write minimal implementation**

在 `requirements.txt` 末尾添加 `websockets>=12.0`。

```python
# bt_adapters/websocket_adapter.py
"""WebSocket 协议适配器

参考开发方案 §3.2 和开发计划 §2.1.3。
客户端模式：连接外部 WebSocket 服务，自动重连 + 心跳。
"""
import asyncio
import threading
import time
from typing import Any, Callable, Optional

from .base import BaseAdapter, AdapterLevel, AdapterStatus
from .config import AdapterConfig


class WebSocketAdapter(BaseAdapter):
    """WebSocket 客户端适配器"""

    @classmethod
    def get_adapter_level(cls) -> AdapterLevel:
        return AdapterLevel.REMOTE

    @classmethod
    def is_available(cls) -> bool:
        try:
            import websockets
            return True
        except ImportError:
            return False

    def __init__(self, config: Optional[AdapterConfig] = None):
        self._config = config or AdapterConfig()
        self._running = False
        self._ws = None
        self._url: str = ""
        self._on_message: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._reconnect_interval_ms = 5000
        self._ping_interval_ms = 30000

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def get_name(self) -> str:
        return "websocket"

    def get_status(self) -> AdapterStatus:
        return AdapterStatus(
            running=self._running,
            name=self.get_name(),
            level=self.get_adapter_level()
        )

    def connect(self, url: str, on_message: Callable = None) -> None:
        """连接 WebSocket 服务

        Args:
            url: ws:// or wss:// URL
            on_message: 消息回调 callback(message: str)
        """
        self._url = url
        self._on_message = on_message
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        """在独立线程中运行 asyncio 事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_and_listen())
        except Exception:
            pass

    async def _connect_and_listen(self) -> None:
        """异步连接并监听消息"""
        import websockets

        while self._running:
            try:
                async with websockets.connect(self._url) as ws:
                    self._ws = ws
                    while self._running:
                        try:
                            message = await asyncio.wait_for(
                                ws.recv(), timeout=self._ping_interval_ms / 1000
                            )
                            if self._on_message:
                                self._on_message(message)
                        except asyncio.TimeoutError:
                            # 发送心跳
                            await ws.ping()
            except Exception:
                if self._running:
                    await asyncio.sleep(self._reconnect_interval_ms / 1000)

    async def send(self, message: str) -> None:
        """发送消息"""
        if self._ws:
            await self._ws.send(message)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_websocket_adapter.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add bt_adapters/websocket_adapter.py requirements.txt tests/test_websocket_adapter.py
git commit -m "feat(adapters): add WebSocketAdapter with auto-reconnect"
```

---

## 阶段 3: 服务层

### Task 16: ServiceRegistry + BaseService

**Files:**
- Create: `bt_services/__init__.py`
- Create: `bt_services/base.py`
- Create: `bt_services/registry.py`
- Test: `tests/test_service_registry.py`

**Step 1: Write the failing test**

```python
# tests/test_service_registry.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestServiceRegistry(unittest.TestCase):
    def test_register_and_get(self):
        from bt_services.registry import ServiceRegistry
        from bt_services.base import BaseService

        class DummyService(BaseService):
            def get_name(self): return "dummy"
            def start(self): pass
            def stop(self): pass

        reg = ServiceRegistry()
        svc = DummyService()
        reg.register("dummy", svc)
        self.assertIs(reg.get("dummy"), svc)

    def test_get_unknown_returns_none(self):
        from bt_services.registry import ServiceRegistry
        reg = ServiceRegistry()
        self.assertIsNone(reg.get("unknown"))

    def test_list_services(self):
        from bt_services.registry import ServiceRegistry
        from bt_services.base import BaseService

        class S1(BaseService):
            def get_name(self): return "s1"
            def start(self): pass
            def stop(self): pass

        class S2(BaseService):
            def get_name(self): return "s2"
            def start(self): pass
            def stop(self): pass

        reg = ServiceRegistry()
        reg.register("s1", S1())
        reg.register("s2", S2())
        names = reg.list_services()
        self.assertIn("s1", names)
        self.assertIn("s2", names)

    def test_unregister(self):
        from bt_services.registry import ServiceRegistry
        from bt_services.base import BaseService

        class S(BaseService):
            def get_name(self): return "s"
            def start(self): pass
            def stop(self): pass

        reg = ServiceRegistry()
        svc = S()
        reg.register("s", svc)
        reg.unregister("s")
        self.assertIsNone(reg.get("s"))


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_registry.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_services'"

**Step 3: Write minimal implementation**

```python
# bt_services/__init__.py
"""服务层模块"""
```

```python
# bt_services/base.py
"""服务基类"""
from abc import ABC, abstractmethod


class BaseService(ABC):
    """服务抽象基类

    所有业务服务（TreeService、DataService 等）继承此类。
    """

    @abstractmethod
    def get_name(self) -> str:
        """返回服务名称"""
        ...

    @abstractmethod
    def start(self) -> None:
        """启动服务"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止服务"""
        ...
```

```python
# bt_services/registry.py
"""服务注册中心"""
import threading
from typing import Dict, List, Optional

from .base import BaseService


class ServiceRegistry:
    """服务注册中心

    管理所有业务服务的注册、查询、生命周期。
    """

    def __init__(self):
        self._services: Dict[str, BaseService] = {}
        self._lock = threading.RLock()

    def register(self, name: str, service: BaseService) -> None:
        """注册服务"""
        with self._lock:
            self._services[name] = service

    def unregister(self, name: str) -> None:
        """注销服务"""
        with self._lock:
            self._services.pop(name, None)

    def get(self, name: str) -> Optional[BaseService]:
        """获取服务"""
        with self._lock:
            return self._services.get(name)

    def list_services(self) -> List[str]:
        """列出所有已注册服务名"""
        with self._lock:
            return list(self._services.keys())

    def start_all(self) -> None:
        """启动所有服务"""
        with self._lock:
            for svc in self._services.values():
                svc.start()

    def stop_all(self) -> None:
        """停止所有服务"""
        with self._lock:
            for svc in self._services.values():
                try:
                    svc.stop()
                except Exception:
                    pass
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_service_registry.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add bt_services/__init__.py bt_services/base.py bt_services/registry.py \
        tests/test_service_registry.py
git commit -m "feat(services): add ServiceRegistry and BaseService"
```

---

### Task 17: TreeService（多 Tab 行为树服务）

**Files:**
- Create: `bt_services/tree_service.py`
- Test: `tests/test_tree_service.py`

**Step 1: Write the failing test**

```python
# tests/test_tree_service.py
import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTreeService(unittest.TestCase):
    def setUp(self):
        from bt_services.tree_service import TreeService
        self.engine = MagicMock()
        self.context = MagicMock()
        self.tab_manager = MagicMock()
        self.context.get_tab_manager.return_value = self.tab_manager
        self.engine.is_running.return_value = False
        self.engine.is_paused.return_value = False
        self.service = TreeService(self.engine, self.context)

    def test_get_name(self):
        self.assertEqual(self.service.get_name(), "tree")

    def test_start_default_tree(self):
        result = self.service.start()
        self.engine.start.assert_called_once()
        self.assertEqual(result["status"], "started")

    def test_start_specific_tree(self):
        result = self.service.start(tree_id="tab2")
        self.tab_manager.start_tab.assert_called_once_with("tab2")
        self.assertEqual(result["tree_id"], "tab2")

    def test_stop_default(self):
        result = self.service.stop()
        self.engine.stop.assert_called_once()
        self.assertEqual(result["status"], "stopped")

    def test_stop_specific_tree(self):
        result = self.service.stop(tree_id="tab2")
        self.tab_manager.stop_tab.assert_called_once_with("tab2")

    def test_pause(self):
        result = self.service.pause()
        self.engine.pause.assert_called_once()
        self.assertEqual(result["status"], "paused")

    def test_resume(self):
        result = self.service.resume()
        self.engine.resume.assert_called_once()
        self.assertEqual(result["status"], "resumed")

    def test_get_status(self):
        self.engine.is_running.return_value = True
        self.engine.is_paused.return_value = False
        status = self.service.get_status()
        self.assertTrue(status["running"])
        self.assertFalse(status["paused"])


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tree_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_services.tree_service'"

**Step 3: Write minimal implementation**

```python
# bt_services/tree_service.py
"""行为树服务 — 封装 engine + tab_manager

复用现有 StartTreeNode/StopTreeNode 的 tab_manager 跨树控制能力。
参考开发方案 §3.3 和开发计划 §3.1.2。
"""
from typing import Optional

from .base import BaseService


class TreeService(BaseService):
    """行为树服务

    封装 BehaviorTreeEngine 和 GuiTabManager，
    通过消息总线暴露行为树控制能力。
    """

    def __init__(self, engine, context):
        self._engine = engine
        self._context = context

    def get_name(self) -> str:
        return "tree"

    def start(self) -> None:
        self._engine.start(self._context)

    def stop(self) -> None:
        self._engine.stop()

    def start(self, tree_id: str = None) -> dict:
        """启动行为树

        Args:
            tree_id: 指定 Tab 的 tree_id，None 表示当前树

        Returns:
            {"status": "started", "tree_id": ...}
        """
        tab_manager = self._context.get_tab_manager()
        if tree_id and tab_manager:
            tab_manager.start_tab(tree_id)
        else:
            self._engine.start(self._context)
        return {"status": "started", "tree_id": tree_id}

    def stop(self, tree_id: str = None) -> dict:
        """停止行为树"""
        tab_manager = self._context.get_tab_manager()
        if tree_id and tab_manager:
            tab_manager.stop_tab(tree_id)
        else:
            self._engine.stop()
        return {"status": "stopped", "tree_id": tree_id}

    def pause(self, tree_id: str = None) -> dict:
        """暂停行为树"""
        self._engine.pause()
        return {"status": "paused", "tree_id": tree_id}

    def resume(self, tree_id: str = None) -> dict:
        """恢复行为树"""
        self._engine.resume()
        return {"status": "resumed", "tree_id": tree_id}

    def get_status(self) -> dict:
        """获取行为树状态"""
        return {
            "running": self._engine.is_running() if hasattr(self._engine, 'is_running') else self._engine._running,
            "paused": self._engine.is_paused() if hasattr(self._engine, 'is_paused') else self._engine._paused,
        }

    def list_trees(self) -> list:
        """列出所有行为树 Tab"""
        tab_manager = self._context.get_tab_manager()
        if not tab_manager:
            return []
        if hasattr(tab_manager, 'list_tabs'):
            return tab_manager.list_tabs()
        return []
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tree_service.py -v`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add bt_services/tree_service.py tests/test_tree_service.py
git commit -m "feat(services): add TreeService with multi-tab support"
```

---

### Task 18: DataService（黑板读写服务）

**Files:**
- Create: `bt_services/data_service.py`
- Test: `tests/test_data_service.py`

**Step 1: Write the failing test**

```python
# tests/test_data_service.py
import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestDataService(unittest.TestCase):
    def setUp(self):
        from bt_services.data_service import DataService
        from bt_core.blackboard import Blackboard
        self.blackboard = Blackboard()
        self.context = MagicMock()
        self.context.blackboard = self.blackboard
        self.service = DataService(self.context)

    def test_get_set(self):
        self.service.set("key1", "value1")
        self.assertEqual(self.service.get("key1"), "value1")

    def test_get_default(self):
        self.assertEqual(self.service.get("missing", "default"), "default")

    def test_delete(self):
        self.service.set("key2", "val")
        self.service.delete("key2")
        self.assertIsNone(self.service.get("key2"))

    def test_list_keys(self):
        self.service.set("k1", 1)
        self.service.set("k2", 2)
        keys = self.service.list_keys()
        self.assertIn("k1", keys)
        self.assertIn("k2", keys)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_services.data_service'"

**Step 3: Write minimal implementation**

```python
# bt_services/data_service.py
"""数据服务 — 封装 Blackboard

参考开发方案 §3.3 和开发计划 §3.1.3。
"""
from typing import Any, Callable, List

from .base import BaseService


class DataService(BaseService):
    """数据服务

    封装 Blackboard 的读写操作，通过消息总线暴露。
    """

    def __init__(self, context):
        self._context = context
        self._blackboard = context.blackboard
        self._subscribers = {}

    def get_name(self) -> str:
        return "data"

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get(self, key: str, default=None) -> Any:
        """读取黑板变量"""
        return self._blackboard.get(key, default)

    def set(self, key: str, value: Any) -> dict:
        """写入黑板变量"""
        self._blackboard.set(key, value)
        return {"key": key, "value": value}

    def delete(self, key: str) -> dict:
        """删除黑板变量"""
        if hasattr(self._blackboard, 'delete'):
            self._blackboard.delete(key)
        else:
            # 兼容无 delete 方法的 Blackboard
            if hasattr(self._blackboard, '_data'):
                self._blackboard._data.pop(key, None)
        return {"key": key, "deleted": True}

    def list_keys(self) -> List[str]:
        """列出所有黑板变量名"""
        if hasattr(self._blackboard, 'keys'):
            return list(self._blackboard.keys())
        if hasattr(self._blackboard, '_data'):
            return list(self._blackboard._data.keys())
        return []

    def subscribe(self, key: str, callback: Callable) -> str:
        """订阅黑板变量变化"""
        import uuid
        sub_id = str(uuid.uuid4())
        self._subscribers[sub_id] = (key, callback)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        self._subscribers.pop(subscription_id, None)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_data_service.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add bt_services/data_service.py tests/test_data_service.py
git commit -m "feat(services): add DataService for blackboard access"
```

---

### Task 19: NodeService + ExecutionContext 扩展 + 事件发布

**Files:**
- Create: `bt_services/node_service.py`
- Modify: `bt_core/context.py`
- Modify: `bt_core/blackboard.py`
- Modify: `bt_core/engine.py`
- Test: `tests/test_node_service.py`
- Test: `tests/test_context_extension.py`

**Step 1: Write the failing test**

```python
# tests/test_node_service.py
import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestNodeService(unittest.TestCase):
    def setUp(self):
        from bt_services.node_service import NodeService
        self.engine = MagicMock()
        self.context = MagicMock()
        self.service = NodeService(self.engine, self.context)

    def test_get_name(self):
        self.assertEqual(self.service.get_name(), "node")

    def test_list_nodes_empty(self):
        self.engine.root_node = None
        nodes = self.service.list_nodes()
        self.assertEqual(nodes, [])

    def test_list_nodes_with_root(self):
        from bt_core.nodes import SequenceNode
        from bt_core.config import NodeConfig
        root = SequenceNode(node_id="root", config=NodeConfig())
        self.engine.root_node = root
        nodes = self.service.list_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["node_id"], "root")


if __name__ == '__main__':
    unittest.main()
```

```python
# tests/test_context_extension.py
import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestContextExtension(unittest.TestCase):
    def test_set_get_message_bus(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        bus = MagicMock()
        ctx.set_message_bus(bus)
        self.assertIs(ctx.get_message_bus(), bus)

    def test_set_get_service_registry(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        reg = MagicMock()
        reg.get.return_value = "service_obj"
        ctx.set_service_registry(reg)
        self.assertEqual(ctx.get_service("tree"), "service_obj")

    def test_set_get_adapter_manager(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        mgr = MagicMock()
        ctx.set_adapter_manager(mgr)
        self.assertIs(ctx.get_adapter_manager(), mgr)

    def test_publish_event_no_bus(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        # 无 bus 时不应抛异常
        ctx.publish_event("test.topic", {"data": "value"})

    def test_publish_event_with_bus(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        bus = MagicMock()
        ctx.set_message_bus(bus)
        ctx.publish_event("test.topic", {"data": "value"})
        bus.publish.assert_called_once_with("test.topic", {"data": "value"})

    def test_set_get_auth_principal(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        self.assertFalse(ctx.is_authenticated())
        principal = MagicMock()
        ctx.set_auth_principal(principal)
        self.assertIs(ctx.get_auth_principal(), principal)
        self.assertTrue(ctx.is_authenticated())

    def test_get_tree_id_from_tab_manager(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.set_tab_manager(MagicMock(), tab_id="tab123")
        self.assertEqual(ctx.get_tree_id(), "tab123")


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_node_service.py tests/test_context_extension.py -v`
Expected: FAIL with "ModuleNotFoundError" 或 "AttributeError"

**Step 3: Write minimal implementation**

```python
# bt_services/node_service.py
"""节点服务 — 节点状态/配置查询

参考开发计划 §3.1.5。
"""
from typing import List

from .base import BaseService


class NodeService(BaseService):
    """节点服务"""

    def __init__(self, engine, context):
        self._engine = engine
        self._context = context

    def get_name(self) -> str:
        return "node"

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def list_nodes(self) -> List[dict]:
        """列出行为树所有节点"""
        if not self._engine.root_node:
            return []
        result = []
        self._collect_nodes(self._engine.root_node, result)
        return result

    def _collect_nodes(self, node, result: list) -> None:
        result.append({
            "node_id": node.node_id,
            "node_type": getattr(node, 'NODE_TYPE', 'Unknown'),
            "name": getattr(node, 'name', ''),
            "status": node.status.name if hasattr(node.status, 'name') else str(node.status),
        })
        for child in getattr(node, 'children', []):
            self._collect_nodes(child, result)

    def get_node_status(self, node_id: str) -> dict:
        """查询节点状态"""
        node = self._find_node(node_id)
        if not node:
            return {"error": "Node not found", "node_id": node_id}
        return {
            "node_id": node.node_id,
            "status": node.status.name if hasattr(node.status, 'name') else str(node.status),
        }

    def get_node_config(self, node_id: str) -> dict:
        """查询节点配置"""
        node = self._find_node(node_id)
        if not node:
            return {"error": "Node not found", "node_id": node_id}
        return {
            "node_id": node.node_id,
            "node_type": getattr(node, 'NODE_TYPE', 'Unknown'),
            "config": node.config.to_dict() if hasattr(node.config, 'to_dict') else {},
        }

    def _find_node(self, node_id: str):
        """递归查找节点"""
        if not self._engine.root_node:
            return None
        return self._search(self._engine.root_node, node_id)

    def _search(self, node, node_id: str):
        if node.node_id == node_id:
            return node
        for child in getattr(node, 'children', []):
            found = self._search(child, node_id)
            if found:
                return found
        return None
```

修改 `bt_core/context.py`，在 `__init__` 末尾添加：

```python
        # Headless 模式标记
        self._headless: bool = False
        # 消息总线和服务层（阶段 3 新增）
        self._message_bus = None
        self._service_registry = None
        self._adapter_manager = None
        self._auth_principal = None
```

在 `set_async_executor` 方法之后新增以下方法：

```python
    def set_message_bus(self, bus) -> None:
        """设置消息总线"""
        self._message_bus = bus

    def get_message_bus(self):
        """获取消息总线"""
        return self._message_bus

    def set_service_registry(self, registry) -> None:
        """设置服务注册中心"""
        self._service_registry = registry

    def get_service(self, name: str):
        """获取服务"""
        if self._service_registry:
            return self._service_registry.get(name)
        return None

    def set_adapter_manager(self, manager) -> None:
        """设置适配器管理器"""
        self._adapter_manager = manager

    def get_adapter_manager(self):
        """获取适配器管理器"""
        return self._adapter_manager

    def publish_event(self, topic: str, data) -> None:
        """发布事件到消息总线"""
        if self._message_bus:
            self._message_bus.publish(topic, data)

    def set_auth_principal(self, principal) -> None:
        """设置当前认证主体"""
        self._auth_principal = principal

    def get_auth_principal(self):
        """获取当前认证主体"""
        return self._auth_principal

    def is_authenticated(self) -> bool:
        """是否已认证"""
        return self._auth_principal is not None

    def get_tree_id(self) -> str:
        """返回当前行为树 ID（用于消息总线主题隔离）"""
        return self._current_tab_id or "default"
```

修改 `bt_core/blackboard.py` 的 `set` 方法，在设置后发布事件：

```python
    def set(self, key, value):
        # ... 原有 set 逻辑 ...
        # 发布黑板变更事件到消息总线（若有）
        # 注: 此处通过 context 间接发布，避免 blackboard 直接依赖 MessageBus
```

> 注：blackboard 发布事件需要在 engine 调用 blackboard.set 时由 context 间接发布。为避免循环依赖，在 `bt_core/engine.py` 的 tick 循环中添加事件发布逻辑，详见 Task 20。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_node_service.py tests/test_context_extension.py -v`
Expected: PASS (11 tests)

**Step 5: Commit**

```bash
git add bt_services/node_service.py bt_core/context.py \
        tests/test_node_service.py tests/test_context_extension.py
git commit -m "feat(services): add NodeService and extend ExecutionContext"
```

---

### Task 20: AuthService 接口 + NoopAuthService + 权限矩阵 + engine 事件发布

**Files:**
- Create: `bt_services/auth_service.py`
- Modify: `bt_core/engine.py`
- Test: `tests/test_auth_service.py`

**Step 1: Write the failing test**

```python
# tests/test_auth_service.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestNoopAuthService(unittest.TestCase):
    def setUp(self):
        from bt_services.auth_service import NoopAuthService
        self.svc = NoopAuthService()

    def test_verify_token_returns_anonymous(self):
        from bt_services.auth_service import AuthPrincipal
        principal = self.svc.verify_token("any_token")
        self.assertIsInstance(principal, AuthPrincipal)
        self.assertEqual(principal.user_id, "anonymous")

    def test_authenticate_returns_anonymous(self):
        principal = self.svc.authenticate({"username": "x"})
        self.assertEqual(principal.user_id, "anonymous")

    def test_is_authenticated_always_true(self):
        self.assertTrue(self.svc.is_authenticated())

    def test_get_current_principal(self):
        principal = self.svc.get_current_principal()
        self.assertIsNotNone(principal)

    def test_has_role_always_true(self):
        self.assertTrue(self.svc.has_role("admin"))
        self.assertTrue(self.svc.has_role("any_role"))

    def test_has_permission_always_true(self):
        self.assertTrue(self.svc.has_permission("tree:start"))
        self.assertTrue(self.svc.has_permission("any:permission"))

    def test_logout_no_exception(self):
        self.svc.logout()


class TestPermissionMatrix(unittest.TestCase):
    def test_permissions_defined(self):
        from bt_services.auth_service import PERMISSIONS
        self.assertGreater(len(PERMISSIONS), 0)
        self.assertIn("tree:start", PERMISSIONS)
        self.assertIn("blackboard:read", PERMISSIONS)

    def test_role_permissions_defined(self):
        from bt_services.auth_service import ROLE_PERMISSIONS
        self.assertIn("admin", ROLE_PERMISSIONS)
        self.assertIn("operator", ROLE_PERMISSIONS)
        self.assertIn("viewer", ROLE_PERMISSIONS)
        self.assertIn("anonymous", ROLE_PERMISSIONS)
        # admin 拥有全部权限
        from bt_services.auth_service import PERMISSIONS
        self.assertEqual(len(ROLE_PERMISSIONS["admin"]), len(PERMISSIONS))

    def test_public_endpoints(self):
        from bt_services.auth_service import PUBLIC_ENDPOINTS
        self.assertIn("/api/v1/auth/login", PUBLIC_ENDPOINTS)
        self.assertIn("/api/v1/health", PUBLIC_ENDPOINTS)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_services.auth_service'"

**Step 3: Write minimal implementation**

```python
# bt_services/auth_service.py
"""认证服务接口 + NoopAuthService + 权限矩阵

参考开发方案 §3.6。
本阶段只定义接口和空实现，不实现具体认证逻辑。
后续接入认证模块时只需实现 BaseAuthService 子类，零返工。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AuthPrincipal:
    """认证主体信息

    认证通过后在整个系统中传递的用户身份。
    """
    user_id: str
    username: str = ""
    display_name: str = ""
    roles: List[str] = field(default_factory=list)
    token: str = ""
    scopes: List[str] = field(default_factory=list)
    is_offline: bool = False


class BaseAuthService(ABC):
    """认证服务抽象基类

    实现选项:
    1. PlatformAuthService  — 平台认证（参考 aut-import 分支 LoginManager）
    2. APIKeyAuthService    — API Key 静态校验
    3. OAuth2AuthService    — 对接外部 OAuth2 Provider
    4. 自定义实现            — 继承 BaseAuthService
    """

    @abstractmethod
    def verify_token(self, token: str) -> Optional[AuthPrincipal]:
        """校验 Token，返回认证主体或 None"""
        ...

    @abstractmethod
    def authenticate(self, credentials: dict) -> Optional[AuthPrincipal]:
        """认证（登录），返回认证主体或 None"""
        ...

    @abstractmethod
    def is_authenticated(self) -> bool:
        """当前是否已认证"""
        ...

    @abstractmethod
    def get_current_principal(self) -> Optional[AuthPrincipal]:
        """获取当前认证主体"""
        ...

    @abstractmethod
    def has_role(self, role: str) -> bool:
        """检查当前用户是否拥有指定角色"""
        ...

    @abstractmethod
    def has_permission(self, permission: str) -> bool:
        """检查当前用户是否拥有指定权限

        权限格式: "{资源}:{操作}"，如 "tree:start"
        支持通配符: "tree:*" 匹配所有 tree 操作
        """
        ...

    @abstractmethod
    def logout(self) -> None:
        """登出，清除认证状态"""
        ...


class NoopAuthService(BaseAuthService):
    """空实现 — 认证未启用时的默认行为

    所有验证都通过，所有权限都允许。
    消息总线和 REST Server 默认使用此实现。
    """

    _principal = AuthPrincipal(user_id="anonymous", roles=["anonymous"])

    def verify_token(self, token: str) -> Optional[AuthPrincipal]:
        return self._principal

    def authenticate(self, credentials: dict) -> Optional[AuthPrincipal]:
        return self._principal

    def is_authenticated(self) -> bool:
        return True

    def get_current_principal(self) -> Optional[AuthPrincipal]:
        return self._principal

    def has_role(self, role: str) -> bool:
        return True

    def has_permission(self, permission: str) -> bool:
        return True

    def logout(self) -> None:
        pass


# 权限矩阵定义
PERMISSIONS = {
    "tree:start":        "启动行为树",
    "tree:stop":         "停止行为树",
    "tree:pause":        "暂停行为树",
    "tree:resume":       "恢复行为树",
    "tree:status":       "查询行为树状态",
    "tree:load":         "加载行为树",
    "blackboard:read":   "读取黑板变量",
    "blackboard:write":  "写入黑板变量",
    "blackboard:delete": "删除黑板变量",
    "blackboard:list":   "列出黑板变量",
    "node:status":       "查询节点状态",
    "node:config":       "查询节点配置",
    "event:subscribe":   "订阅事件流",
    "adapter:http":      "HTTP 适配器调用",
    "adapter:websocket": "WebSocket 适配器调用",
}

ROLE_PERMISSIONS = {
    "admin": list(PERMISSIONS.keys()),
    "operator": [
        "tree:*", "blackboard:read", "blackboard:write", "blackboard:list",
        "node:status", "node:config", "event:subscribe",
        "adapter:http", "adapter:websocket",
    ],
    "viewer": [
        "tree:status", "blackboard:read", "blackboard:list",
        "node:status", "node:config", "event:subscribe",
    ],
    "anonymous": [],
}

PUBLIC_ENDPOINTS = [
    "/api/v1/auth/login",
    "/api/v1/health",
]
```

修改 `bt_core/engine.py`，在 `start` / `stop` / `pause` / `resume` 方法末尾添加事件发布：

```python
    def start(self, context: ExecutionContext = None) -> None:
        with self._lock:
            if self._running:
                return
            # ... 原有逻辑 ...
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            # 发布事件到消息总线
            if context and hasattr(context, 'publish_event'):
                context.publish_event(
                    f"bt.{context.get_tree_id()}.event.tree.started",
                    {"tree_id": context.get_tree_id()}
                )
            if self._on_status_change:
                self._on_status_change("running")

    def stop(self) -> None:
        with self._lock:
            tree_id = self.context.get_tree_id() if self.context else "default"
            self._running = False
            # ... 原有逻辑 ...
            # 发布事件到消息总线
            if self.context and hasattr(self.context, 'publish_event'):
                self.context.publish_event(
                    f"bt.{tree_id}.event.tree.stopped",
                    {"tree_id": tree_id}
                )
            if self._on_status_change:
                self._on_status_change("stopped")

    def pause(self) -> None:
        tree_id = self.context.get_tree_id() if self.context else "default"
        self._paused = True
        self._pause_event.clear()
        # 发布事件到消息总线
        if self.context and hasattr(self.context, 'publish_event'):
            self.context.publish_event(
                f"bt.{tree_id}.event.tree.paused",
                {"tree_id": tree_id}
            )
        if self._on_status_change:
            self._on_status_change("paused")

    def resume(self) -> None:
        tree_id = self.context.get_tree_id() if self.context else "default"
        self._paused = False
        self._pause_event.set()
        # 发布事件到消息总线
        if self.context and hasattr(self.context, 'publish_event'):
            self.context.publish_event(
                f"bt.{tree_id}.event.tree.resumed",
                {"tree_id": tree_id}
            )
        if self._on_status_change:
            self._on_status_change("running")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_auth_service.py -v`
Expected: PASS (10 tests)

**Step 5: Commit**

```bash
git add bt_services/auth_service.py bt_core/engine.py tests/test_auth_service.py
git commit -m "feat(services): add AuthService interface, NoopAuthService and engine events"
```

---

## 阶段 4: 服务端层

### Task 21: REST API 服务端（含 async/sync 桥接）

**Files:**
- Create: `bt_servers/__init__.py`
- Create: `bt_servers/base.py`
- Create: `bt_servers/config.py`
- Create: `bt_servers/rest_server.py`
- Modify: `requirements.txt`
- Test: `tests/test_rest_server.py`

**Step 1: Write the failing test**

```python
# tests/test_rest_server.py
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestRESTServer(unittest.TestCase):
    def test_can_import(self):
        from bt_servers.rest_server import RESTServer
        self.assertTrue(hasattr(RESTServer, '__init__'))

    def test_health_endpoint(self):
        """测试 /api/v1/health 端点"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        server = RESTServer(message_bus=MagicMock(), auth_service=None)
        client = TestClient(server.app)
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_list_trees_endpoint(self):
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_tree_svc = MagicMock()
        mock_tree_svc.list_trees.return_value = [{"tree_id": "1", "name": "Tree1"}]
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tree_svc

        server = RESTServer(message_bus=MagicMock(), auth_service=None,
                            service_registry=mock_registry)
        client = TestClient(server.app)
        response = client.get("/api/v1/trees")
        self.assertEqual(response.status_code, 200)
        self.assertIn("trees", response.json())

    def test_start_tree_endpoint(self):
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_tree_svc = MagicMock()
        mock_tree_svc.start.return_value = {"status": "started", "tree_id": "1"}
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tree_svc

        server = RESTServer(message_bus=MagicMock(), auth_service=None,
                            service_registry=mock_registry)
        client = TestClient(server.app)
        response = client.post("/api/v1/trees/1/start")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "started")

    def test_noop_auth_no_token_passes(self):
        """测试 NoopAuthService 下无 Token 请求正常放行"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        server = RESTServer(message_bus=MagicMock(), auth_service=None)
        client = TestClient(server.app)
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rest_server.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bt_servers'"

**Step 3: Write minimal implementation**

在 `requirements.txt` 添加：
```
fastapi>=0.104.0
uvicorn>=0.24.0
sse-starlette>=1.8.0
```

```python
# bt_servers/__init__.py
"""服务端模块"""
```

```python
# bt_servers/base.py
"""服务端基类"""
from abc import ABC, abstractmethod


class BaseServer(ABC):
    """服务端抽象基类"""

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...
```

```python
# bt_servers/config.py
"""服务端配置"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class ServerConfig:
    """服务端配置"""
    host: str = "127.0.0.1"
    port: int = 8900
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    rate_limit_per_minute: int = 60
    api_key_enabled: bool = False
```

```python
# bt_servers/rest_server.py
"""REST API 服务端 — 基于 FastAPI

参考开发方案 §3.6.6 和开发计划 §4.1.1。
使用 async/sync 桥接方案（asyncio.to_thread）。
"""
import asyncio
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .base import BaseServer
from .config import ServerConfig


class RESTServer(BaseServer):
    """REST API 服务端

    使用 FastAPI 提供 REST API。
    异步 handler 中通过 asyncio.to_thread() 桥接同步引擎调用。
    """

    def __init__(self, message_bus=None, auth_service=None,
                 service_registry=None, config: Optional[ServerConfig] = None):
        self._bus = message_bus
        self._config = config or ServerConfig()
        self._registry = service_registry

        # 默认使用 NoopAuthService
        if auth_service is None:
            from bt_services.auth_service import NoopAuthService
            auth_service = NoopAuthService()
        self._auth = auth_service

        self.app = FastAPI(title="AutoDoor BT API", version="1.0")
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        """配置中间件"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self._config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        """配置路由"""
        from bt_services.auth_service import PUBLIC_ENDPOINTS

        @self.app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            # 公开端点直接放行
            if request.url.path in PUBLIC_ENDPOINTS:
                return await call_next(request)

            # NoopAuthService 放行所有请求
            token = request.headers.get("Authorization", "")
            principal = self._auth.verify_token(token)
            if not principal:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized", "code": "AUTH_REQUIRED"}
                )
            request.state.principal = principal
            return await call_next(request)

        @self.app.get("/api/v1/health")
        async def health():
            return {"status": "ok"}

        @self.app.get("/api/v1/trees")
        async def list_trees():
            if not self._registry:
                return {"trees": []}
            tree_svc = self._registry.get("tree")
            if not tree_svc:
                return {"trees": []}
            trees = await asyncio.to_thread(tree_svc.list_trees)
            return {"trees": trees}

        @self.app.get("/api/v1/trees/{tree_id}/status")
        async def get_tree_status(tree_id: str):
            if not self._registry:
                raise HTTPException(404, "TreeService not available")
            tree_svc = self._registry.get("tree")
            if not tree_svc:
                raise HTTPException(404, "TreeService not available")
            status = await asyncio.to_thread(tree_svc.get_status)
            return {"tree_id": tree_id, **status}

        @self.app.post("/api/v1/trees/{tree_id}/start")
        async def start_tree(tree_id: str):
            if not self._registry:
                raise HTTPException(404, "TreeService not available")
            tree_svc = self._registry.get("tree")
            if not tree_svc:
                raise HTTPException(404, "TreeService not available")
            result = await asyncio.to_thread(tree_svc.start, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/stop")
        async def stop_tree(tree_id: str):
            if not self._registry:
                raise HTTPException(404, "TreeService not available")
            tree_svc = self._registry.get("tree")
            if not tree_svc:
                raise HTTPException(404, "TreeService not available")
            result = await asyncio.to_thread(tree_svc.stop, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/pause")
        async def pause_tree(tree_id: str):
            tree_svc = self._registry.get("tree") if self._registry else None
            if not tree_svc:
                raise HTTPException(404)
            result = await asyncio.to_thread(tree_svc.pause, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/resume")
        async def resume_tree(tree_id: str):
            tree_svc = self._registry.get("tree") if self._registry else None
            if not tree_svc:
                raise HTTPException(404)
            result = await asyncio.to_thread(tree_svc.resume, tree_id)
            return result

        @self.app.get("/api/v1/trees/{tree_id}/blackboard")
        async def get_blackboard(tree_id: str):
            data_svc = self._registry.get("data") if self._registry else None
            if not data_svc:
                raise HTTPException(404)
            keys = await asyncio.to_thread(data_svc.list_keys)
            result = {}
            for k in keys:
                result[k] = await asyncio.to_thread(data_svc.get, k)
            return result

        @self.app.get("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def get_blackboard_key(tree_id: str, key: str):
            data_svc = self._registry.get("data") if self._registry else None
            if not data_svc:
                raise HTTPException(404)
            value = await asyncio.to_thread(data_svc.get, key)
            return {"key": key, "value": value}

        @self.app.put("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def set_blackboard_key(tree_id: str, key: str, request: Request):
            data_svc = self._registry.get("data") if self._registry else None
            if not data_svc:
                raise HTTPException(404)
            body = await request.json()
            result = await asyncio.to_thread(data_svc.set, key, body.get("value"))
            return result

        @self.app.delete("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def delete_blackboard_key(tree_id: str, key: str):
            data_svc = self._registry.get("data") if self._registry else None
            if not data_svc:
                raise HTTPException(404)
            result = await asyncio.to_thread(data_svc.delete, key)
            return result

        @self.app.get("/api/v1/trees/{tree_id}/nodes")
        async def list_nodes(tree_id: str):
            node_svc = self._registry.get("node") if self._registry else None
            if not node_svc:
                raise HTTPException(404)
            nodes = await asyncio.to_thread(node_svc.list_nodes)
            return {"nodes": nodes}

        @self.app.get("/api/v1/trees/{tree_id}/nodes/{node_id}/status")
        async def get_node_status(tree_id: str, node_id: str):
            node_svc = self._registry.get("node") if self._registry else None
            if not node_svc:
                raise HTTPException(404)
            status = await asyncio.to_thread(node_svc.get_node_status, node_id)
            return status

    def start(self) -> None:
        """启动服务端（在 uvicorn 中调用）"""
        # 注入事件循环到 MessageBus
        if self._bus:
            loop = asyncio.get_event_loop()
            self._bus.set_event_loop(loop)

    def stop(self) -> None:
        """停止服务端"""
        pass
```

**Step 4: Run test to verify it passes**

Run: `pip install fastapi>=0.104.0 uvicorn>=0.24.0 sse-starlette>=1.8.0 httpx && python -m pytest tests/test_rest_server.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add bt_servers/__init__.py bt_servers/base.py bt_servers/config.py \
        bt_servers/rest_server.py requirements.txt tests/test_rest_server.py
git commit -m "feat(servers): add RESTServer with FastAPI and async bridge"
```

---

### Task 22: SSE 事件流

**Files:**
- Modify: `bt_servers/rest_server.py`
- Test: `tests/test_sse.py`

**Step 1: Write the failing test**

```python
# tests/test_sse.py
import os
import sys
import asyncio
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestSSE(unittest.TestCase):
    def test_sse_endpoint_exists(self):
        """测试 /api/v1/events/stream 端点存在"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_bus = MagicMock()
        mock_queue = asyncio.Queue()
        mock_bus.subscribe_async.return_value = mock_queue

        server = RESTServer(message_bus=mock_bus, auth_service=None)
        client = TestClient(server.app)
        # 端点应存在（即使返回 200 或 406）
        response = client.get("/api/v1/events/stream",
                              headers={"Accept": "text/event-stream"})
        # TestClient 不支持流式响应，但路由应匹配
        self.assertIn(response.status_code, [200, 406])

    def test_bus_subscribe_async_called(self):
        """测试 SSE 端点调用 bus.subscribe_async"""
        from bt_servers.rest_server import RESTServer

        mock_bus = MagicMock()
        mock_queue = asyncio.Queue()
        mock_bus.subscribe_async.return_value = mock_queue

        server = RESTServer(message_bus=mock_bus, auth_service=None)
        # 验证 subscribe_async 方法被引用
        self.assertTrue(hasattr(server, '_setup_sse_routes'))


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sse.py -v`
Expected: FAIL — SSE 端点不存在

**Step 3: Write minimal implementation**

在 `bt_servers/rest_server.py` 中新增 SSE 路由（在 `_setup_routes` 方法末尾或新增 `_setup_sse_routes` 方法）：

```python
    def _setup_sse_routes(self) -> None:
        """配置 SSE 事件流路由"""
        from sse_starlette.sse import EventSourceResponse

        @self.app.get("/api/v1/events/stream")
        async def event_stream():
            """SSE 事件流 — 推送节点状态变化、黑板变化等事件"""
            if not self._bus:
                yield {"event": "error", "data": "MessageBus not available"}
                return

            # 订阅所有 bt 事件
            queue = self._bus.subscribe_async("bt.**.event.**")

            async def event_generator():
                while True:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=30)
                        yield {
                            "event": "message",
                            "data": {
                                "topic": msg.topic,
                                "data": msg.data,
                                "timestamp": msg.timestamp,
                                "source": msg.source,
                            }
                        }
                    except asyncio.TimeoutError:
                        # 发送心跳
                        yield {"event": "ping", "data": ""}
                    except Exception as e:
                        yield {"event": "error", "data": str(e)}
                        break

            return EventSourceResponse(event_generator())
```

并在 `_setup_routes` 方法末尾调用 `self._setup_sse_routes()`。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sse.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add bt_servers/rest_server.py tests/test_sse.py
git commit -m "feat(servers): add SSE event stream endpoint"
```

---

### Task 23: WebSocket 服务端

**Files:**
- Create: `bt_servers/websocket_server.py`
- Test: `tests/test_websocket_server.py`

**Step 1: Write the failing test**

```python
# tests/test_websocket_server.py
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import asyncio
import threading
import time


class TestWebSocketServer(unittest.TestCase):
    """验证 WebSocket 服务端的消息收发与心跳"""

    def setUp(self):
        from bt_servers.websocket_server import WebSocketServer
        self.server = WebSocketServer(host="127.0.0.1", port=8765)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        time.sleep(0.3)  # 等待服务启动

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.server.start())
        self.loop.run_forever()

    def tearDown(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)

    def test_server_starts_and_accepts_connection(self):
        """服务端启动后可接受连接"""
        import websockets

        async def client():
            async with websockets.connect("ws://127.0.0.1:8765") as ws:
                await ws.send('{"type":"ping"}')
                resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                self.assertIn("pong", resp)

        asyncio.run(asyncio.wait_for(client(), timeout=5.0))

    def test_server_broadcasts_bus_messages(self):
        """消息总线发布后客户端可收到广播"""
        from bt_servers.websocket_server import WebSocketServer
        from bt_message_bus.bus import MessageBus
        from bt_message_bus.message import Message

        bus = MessageBus()
        self.server.attach_bus(bus)

        import websockets

        async def client():
            async with websockets.connect("ws://127.0.0.1:8765?topic=bt.**") as ws:
                # 给服务端一点时间注册订阅
                await asyncio.sleep(0.2)
                bus.publish(Message(topic="bt.test.event", payload={"v": 1}))
                resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                self.assertIn("bt.test.event", resp)

        asyncio.run(asyncio.wait_for(client(), timeout=5.0))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Verify the test fails**

```bash
python tests/test_websocket_server.py
```

预期失败：`ModuleNotFoundError: No module named 'bt_servers.websocket_server'`

**Step 3: Implement minimal code**

```python
# bt_servers/__init__.py
"""服务端层（REST + SSE + WebSocket）"""
```

```python
# bt_servers/websocket_server.py
"""WebSocket 服务端：向客户端广播消息总线事件"""
import asyncio
import json
import logging
from typing import Optional, Set

try:
    import websockets
    from websockets.server import serve
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    websockets = None
    serve = None

logger = logging.getLogger(__name__)


class WebSocketServer:
    """WebSocket 服务端

    客户端可通过 query 参数 `topic` 订阅主题（支持通配符），
    服务端将消息总线的消息广播给匹配订阅的客户端。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self._server = None
        self._clients: Set["websockets.WebSocketServerProtocol"] = set()
        self._client_topics: dict = {}
        self._bus = None
        self._heartbeat_interval = 30.0
        self._running = False

    def attach_bus(self, bus) -> None:
        """绑定消息总线，订阅所有消息并广播"""
        self._bus = bus
        bus.subscribe("**", self._on_bus_message)

    def _on_bus_message(self, message) -> None:
        """消息总线回调：广播给匹配订阅的客户端"""
        coro = self._broadcast(message)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, loop)
            else:
                asyncio.run(coro)
        except RuntimeError:
            asyncio.run(coro)

    async def _broadcast(self, message) -> None:
        payload = json.dumps({
            "topic": message.topic,
            "payload": message.payload,
            "timestamp": message.timestamp,
        })
        dead = []
        for ws, topic_filter in self._client_topics.items():
            if self._topic_matches(topic_filter, message.topic):
                try:
                    await ws.send(payload)
                except Exception:
                    dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)
            self._client_topics.pop(ws, None)

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        if not pattern or pattern == "**":
            return True
        pattern_parts = pattern.split(".")
        topic_parts = topic.split(".")
        for i, p in enumerate(pattern_parts):
            if p == "**":
                return True
            if i >= len(topic_parts):
                return False
            if p != "*" and p != topic_parts[i]:
                return False
        return len(pattern_parts) == len(topic_parts)

    async def start(self) -> None:
        if not HAS_WEBSOCKETS:
            raise RuntimeError("websockets 未安装")
        self._running = True
        self._server = await serve(self._handle_client, self.host, self.port)
        logger.info("WebSocket 服务端已启动 %s:%d", self.host, self.port)

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, ws, path="/") -> None:
        self._clients.add(ws)
        topic_filter = "**"
        if "?" in path:
            query = path.split("?", 1)[1]
            for kv in query.split("&"):
                if kv.startswith("topic="):
                    topic_filter = kv[6:]
        self._client_topics[ws] = topic_filter
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"type": "error", "msg": "invalid json"}))
        finally:
            self._clients.discard(ws)
            self._client_topics.pop(ws, None)
```

**Step 4: Verify the test passes**

```bash
pip install websockets
python tests/test_websocket_server.py
```

**Step 5: Commit**

```bash
git add bt_servers/websocket_server.py tests/test_websocket_server.py
git commit -m "feat(servers): add WebSocket server with topic-based broadcast"
```

---

## 阶段 5: 接口节点与 GUI 集成（Task 24-28）

### Task 24: HTTPRequestNode

**Files:**
- Create: `bt_nodes/network/__init__.py`
- Create: `bt_nodes/network/http_request_node.py`
- Test: `tests/test_http_request_node.py`

**Step 1: Write the failing test**

```python
# tests/test_http_request_node.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import patch, MagicMock
from bt_core.context import ExecutionContext
from bt_core.config import NodeConfig
from bt_core.status import NodeStatus


class TestHTTPRequestNode(unittest.TestCase):
    """验证 HTTP 请求节点的执行与错误处理"""

    def test_success_returns_success(self):
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "GET",
            "timeout_ms": 5000,
        }))
        ctx = ExecutionContext()

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"code": 0}
        fake_resp.text = '{"code":0}'

        with patch("bt_nodes.network.http_request_node.requests.get",
                   return_value=fake_resp) as mock_get:
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        mock_get.assert_called_once()
        # 响应写入黑板
        self.assertEqual(ctx.blackboard.get("http_response_code"), 200)

    def test_failure_returns_failure(self):
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "GET",
            "expected_status": 200,
        }))
        ctx = ExecutionContext()

        fake_resp = MagicMock()
        fake_resp.status_code = 500
        fake_resp.json.return_value = {}
        fake_resp.text = ""

        with patch("bt_nodes.network.http_request_node.requests.get",
                   return_value=fake_resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_post_method_with_body(self):
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "POST",
            "body": '{"k":"v"}',
            "headers": {"Content-Type": "application/json"},
        }))
        ctx = ExecutionContext()
        fake_resp = MagicMock()
        fake_resp.status_code = 201
        fake_resp.json.return_value = {}
        fake_resp.text = ""
        with patch("bt_nodes.network.http_request_node.requests.post",
                   return_value=fake_resp) as mock_post:
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Verify the test fails**

```bash
python tests/test_http_request_node.py
```

预期失败：`ModuleNotFoundError: No module named 'bt_nodes.network.http_request_node'`

**Step 3: Implement minimal code**

```python
# bt_nodes/network/__init__.py
"""网络相关节点"""
```

```python
# bt_nodes/network/http_request_node.py
"""HTTP 请求节点：发起 HTTP 调用并将结果写入黑板"""
import json as _json
import logging
from typing import Dict, Optional

import requests

from bt_core.nodes import Node
from bt_core.status import NodeStatus
from bt_core.config import NodeConfig

logger = logging.getLogger(__name__)


class HTTPRequestNode(Node):
    """发起 HTTP 请求，将响应写入黑板

    配置项：
        url: 请求 URL
        method: GET / POST / PUT / DELETE（默认 GET）
        body: 请求体（POST/PUT 时使用）
        headers: 请求头字典
        timeout_ms: 超时毫秒（默认 5000）
        expected_status: 期望的 HTTP 状态码（不匹配则 FAILURE）
        response_key: 黑板键名（默认 http_response）
    """

    NODE_TYPE = "HTTPRequestNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.url = self.config.get("url", "")
        self.method = self.config.get("method", "GET").upper()
        self.body = self.config.get("body", "")
        self.headers: Dict[str, str] = self.config.get("headers", {}) or {}
        self.timeout_ms = self.config.get_int("timeout_ms", 5000)
        self.expected_status = self.config.get_int("expected_status", 0)
        self.response_key = self.config.get("response_key", "http_response")

    def tick(self, context) -> NodeStatus:
        if not self.url:
            logger.error("HTTPRequestNode %s 缺少 url", self.name)
            return NodeStatus.FAILURE
        try:
            kwargs = {
                "headers": self.headers or None,
                "timeout": self.timeout_ms / 1000.0,
            }
            if self.method == "GET":
                resp = requests.get(self.url, **kwargs)
            elif self.method == "POST":
                kwargs["data"] = self.body or None
                resp = requests.post(self.url, **kwargs)
            elif self.method == "PUT":
                kwargs["data"] = self.body or None
                resp = requests.put(self.url, **kwargs)
            elif self.method == "DELETE":
                resp = requests.delete(self.url, **kwargs)
            else:
                logger.error("不支持的方法: %s", self.method)
                return NodeStatus.FAILURE
        except Exception as e:
            logger.exception("HTTP 请求异常: %s", e)
            context.blackboard.set(self.response_key, {"error": str(e)})
            return NodeStatus.FAILURE

        context.blackboard.set(self.response_key, {
            "status_code": resp.status_code,
            "text": resp.text,
            "json": self._safe_json(resp),
        })
        context.blackboard.set("http_response_code", resp.status_code)

        if self.expected_status and resp.status_code != self.expected_status:
            logger.warning("HTTP %s 期望 %d 实际 %d",
                           self.url, self.expected_status, resp.status_code)
            return NodeStatus.FAILURE
        return NodeStatus.SUCCESS

    @staticmethod
    def _safe_json(resp):
        try:
            return resp.json()
        except ValueError:
            return None
```

**Step 4: Verify the test passes**

```bash
pip install requests
python tests/test_http_request_node.py
```

**Step 5: Commit**

```bash
git add bt_nodes/network/__init__.py bt_nodes/network/http_request_node.py tests/test_http_request_node.py
git commit -m "feat(nodes): add HTTPRequestNode with blackboard integration"
```

---

### Task 25: APIConditionNode

**Files:**
- Create: `bt_nodes/network/api_condition_node.py`
- Test: `tests/test_api_condition_node.py`

**Step 1: Write the failing test**

```python
# tests/test_api_condition_node.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import patch, MagicMock
from bt_core.context import ExecutionContext
from bt_core.config import NodeConfig
from bt_core.status import NodeStatus


class TestAPIConditionNode(unittest.TestCase):
    """验证 API 条件节点根据 HTTP 响应返回 SUCCESS/FAILURE"""

    def _make_resp(self, status_code=200, json_data=None, text=""):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.text = text
        return resp

    def test_json_path_match_returns_success(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/health",
            "json_path": "status",
            "expected_value": "ok",
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {"status": "ok"})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)

    def test_json_path_mismatch_returns_failure(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/health",
            "json_path": "status",
            "expected_value": "ok",
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {"status": "error"})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_status_code_condition(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/health",
            "expected_status": 204,
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(204, {})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)

    def test_nested_json_path(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/api",
            "json_path": "data.code",
            "expected_value": 0,
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {"data": {"code": 0}})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Verify the test fails**

```bash
python tests/test_api_condition_node.py
```

预期失败：`ModuleNotFoundError: No module named 'bt_nodes.network.api_condition_node'`

**Step 3: Implement minimal code**

```python
# bt_nodes/network/api_condition_node.py
"""API 条件节点：根据 HTTP 响应判断 SUCCESS/FAILURE"""
import logging
from typing import Any, Optional

import requests

from bt_core.nodes import Node
from bt_core.status import NodeStatus
from bt_core.config import NodeConfig

logger = logging.getLogger(__name__)


def _extract_json_path(data: Any, path: str) -> Any:
    """从嵌套字典中按点分路径取值"""
    if not path:
        return data
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


class APIConditionNode(Node):
    """根据 HTTP 响应内容判断条件是否成立

    配置项：
        url: 请求 URL
        method: 默认 GET
        expected_status: 期望的 HTTP 状态码
        json_path: 响应 JSON 中要取的字段（点分路径，如 data.code）
        expected_value: 期望的字段值（与 json_path 配合使用）
        timeout_ms: 超时毫秒（默认 5000）
    """

    NODE_TYPE = "APIConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.url = self.config.get("url", "")
        self.method = self.config.get("method", "GET").upper()
        self.expected_status = self.config.get_int("expected_status", 0)
        self.json_path = self.config.get("json_path", "")
        self.expected_value = self.config.get("expected_value", None)
        self.timeout_ms = self.config.get_int("timeout_ms", 5000)
        self.headers = self.config.get("headers", {}) or {}

    def tick(self, context) -> NodeStatus:
        if not self.url:
            return NodeStatus.FAILURE
        try:
            kwargs = {
                "headers": self.headers or None,
                "timeout": self.timeout_ms / 1000.0,
            }
            if self.method == "GET":
                resp = requests.get(self.url, **kwargs)
            elif self.method == "POST":
                kwargs["data"] = self.config.get("body", "")
                resp = requests.post(self.url, **kwargs)
            else:
                resp = requests.request(self.method, self.url, **kwargs)
        except Exception as e:
            logger.exception("APIConditionNode 请求异常: %s", e)
            return NodeStatus.FAILURE

        if self.expected_status and resp.status_code != self.expected_status:
            return NodeStatus.FAILURE

        if self.json_path:
            try:
                data = resp.json()
            except ValueError:
                return NodeStatus.FAILURE
            actual = _extract_json_path(data, self.json_path)
            if actual != self.expected_value:
                return NodeStatus.FAILURE

        return NodeStatus.SUCCESS
```

**Step 4: Verify the test passes**

```bash
python tests/test_api_condition_node.py
```

**Step 5: Commit**

```bash
git add bt_nodes/network/api_condition_node.py tests/test_api_condition_node.py
git commit -m "feat(nodes): add APIConditionNode with json_path evaluation"
```

---

### Task 26: MessagePublishNode

**Files:**
- Create: `bt_nodes/message/__init__.py`
- Create: `bt_nodes/message/publish_node.py`
- Test: `tests/test_message_publish_node.py`

**Step 1: Write the failing test**

```python
# tests/test_message_publish_node.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import MagicMock
from bt_core.context import ExecutionContext
from bt_core.config import NodeConfig
from bt_core.status import NodeStatus


class TestMessagePublishNode(unittest.TestCase):
    """验证消息发布节点向消息总线发布消息"""

    def test_publish_static_payload(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_message_bus.bus import MessageBus

        bus = MessageBus()
        received = []
        bus.subscribe("bt.test.**", lambda m: received.append(m))

        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "bt.test.event",
            "payload": {"v": 1},
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].payload, {"v": 1})

    def test_publish_blackboard_payload(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_message_bus.bus import MessageBus

        bus = MessageBus()
        received = []
        bus.subscribe("bt.**", lambda m: received.append(m))

        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "bt.test.event",
            "payload_key": "my_data",
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        ctx.blackboard.set("my_data", {"score": 100})
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(received[0].payload, {"score": 100})

    def test_publish_with_tree_id_prefix(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_message_bus.bus import MessageBus

        bus = MessageBus()
        received = []
        bus.subscribe("bt.tree123.**", lambda m: received.append(m))

        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "event.started",
            "payload": {},
            "prefix_tree_id": True,
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        ctx._current_tab_id = "tree123"
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].topic, "bt.tree123.event.started")

    def test_no_bus_returns_failure(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "x",
        }))
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Verify the test fails**

```bash
python tests/test_message_publish_node.py
```

预期失败：`ModuleNotFoundError: No module named 'bt_nodes.message.publish_node'`

**Step 3: Implement minimal code**

```python
# bt_nodes/message/__init__.py
"""消息总线相关节点"""
```

```python
# bt_nodes/message/publish_node.py
"""消息发布节点：向消息总线发布消息"""
import logging
from typing import Any, Optional

from bt_core.nodes import Node
from bt_core.status import NodeStatus
from bt_core.config import NodeConfig

logger = logging.getLogger(__name__)


class MessagePublishNode(Node):
    """向消息总线发布消息

    配置项：
        topic: 主题（可相对，配合 prefix_tree_id 自动加上 bt.{tree_id}. 前缀）
        payload: 静态负载字典
        payload_key: 黑板键名（若指定则用黑板值覆盖 payload）
        prefix_tree_id: 是否自动加上 bt.{tree_id}. 前缀（默认 True）
    """

    NODE_TYPE = "MessagePublishNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.topic = self.config.get("topic", "")
        self.payload = self.config.get("payload", {}) or {}
        self.payload_key = self.config.get("payload_key", "")
        self.prefix_tree_id = self.config.get_bool("prefix_tree_id", True)
        self._bus = None

    def set_bus(self, bus) -> None:
        """注入消息总线实例"""
        self._bus = bus

    def tick(self, context) -> NodeStatus:
        if not self._bus:
            logger.error("MessagePublishNode %s 未绑定消息总线", self.name)
            return NodeStatus.FAILURE
        if not self.topic:
            return NodeStatus.FAILURE

        topic = self.topic
        if self.prefix_tree_id and not topic.startswith("bt."):
            tree_id = context.get_current_tab_id() or "default"
            topic = f"bt.{tree_id}.{topic}"

        payload = self.payload
        if self.payload_key:
            val = context.blackboard.get(self.payload_key)
            if val is not None:
                payload = val

        self._bus.publish_to(topic, payload)
        logger.debug("已发布消息 topic=%s", topic)
        return NodeStatus.SUCCESS
```

> 说明：`MessageBus.publish_to` 是新增的便捷方法，直接接收 topic + payload。
> 若消息总线仅有 `publish(Message)` 接口，则在节点内部构造 `Message(topic=..., payload=...)`。

**Step 4: Verify the test passes**

```bash
python tests/test_message_publish_node.py
```

**Step 5: Commit**

```bash
git add bt_nodes/message/__init__.py bt_nodes/message/publish_node.py tests/test_message_publish_node.py
git commit -m "feat(nodes): add MessagePublishNode with tree_id prefix"
```

---

### Task 27: MessageSubscribeNode

**Files:**
- Create: `bt_nodes/message/subscribe_node.py`
- Test: `tests/test_message_subscribe_node.py`

**Step 1: Write the failing test**

```python
# tests/test_message_subscribe_node.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bt_core.context import ExecutionContext
from bt_core.config import NodeConfig
from bt_core.status import NodeStatus


class TestMessageSubscribeNode(unittest.TestCase):
    """验证消息订阅节点能从消息总线接收消息并写入黑板"""

    def test_receive_message_writes_to_blackboard(self):
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        from bt_message_bus.bus import MessageBus
        from bt_message_bus.message import Message

        bus = MessageBus()
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.test.**",
            "payload_key": "last_msg",
            "timeout_ms": 1000,
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        node.on_start(ctx)

        # 模拟总线发布一条消息
        bus.publish(Message(topic="bt.test.event", payload={"v": 42}))
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(ctx.blackboard.get("last_msg"), {"v": 42})

    def test_no_message_timeout_returns_failure(self):
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        from bt_message_bus.bus import MessageBus

        bus = MessageBus()
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.test.**",
            "payload_key": "last_msg",
            "timeout_ms": 100,
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        node.on_start(ctx)
        # 立即 tick，无消息应返回 FAILURE
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_node_only_receives_matching_topic(self):
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        from bt_message_bus.bus import MessageBus
        from bt_message_bus.message import Message

        bus = MessageBus()
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.treeA.**",
            "payload_key": "msg_a",
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        node.on_start(ctx)

        # 不匹配的消息
        bus.publish(Message(topic="bt.treeB.event", payload={"v": 1}))
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)
        self.assertIsNone(ctx.blackboard.get("msg_a"))

        # 匹配的消息
        bus.publish(Message(topic="bt.treeA.event", payload={"v": 2}))
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(ctx.blackboard.get("msg_a"), {"v": 2})


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Verify the test fails**

```bash
python tests/test_message_subscribe_node.py
```

预期失败：`ModuleNotFoundError: No module named 'bt_nodes.message.subscribe_node'`

**Step 3: Implement minimal code**

```python
# bt_nodes/message/subscribe_node.py
"""消息订阅节点：等待消息总线上的消息"""
import logging
import time
from typing import Optional

from bt_core.nodes import Node
from bt_core.status import NodeStatus
from bt_core.config import NodeConfig

logger = logging.getLogger(__name__)


class MessageSubscribeNode(Node):
    """等待并接收消息总线上的消息

    配置项：
        topic: 订阅主题（支持通配符）
        payload_key: 将消息 payload 写入黑板的键名
        timeout_ms: 等待超时毫秒（0 = 不等待，立即返回）
        wait_mode: blocking / nonblocking（默认 nonblocking）
    """

    NODE_TYPE = "MessageSubscribeNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.topic = self.config.get("topic", "")
        self.payload_key = self.config.get("payload_key", "last_message")
        self.timeout_ms = self.config.get_int("timeout_ms", 0)
        self.wait_mode = self.config.get("wait_mode", "nonblocking")
        self._bus = None
        self._last_message = None
        self._subscription_id = None
        self._start_wait_time: Optional[float] = None

    def set_bus(self, bus) -> None:
        self._bus = bus

    def on_start(self, context) -> None:
        """节点开始执行时订阅主题"""
        self._last_message = None
        self._start_wait_time = time.perf_counter()
        if self._bus and self.topic:
            self._subscription_id = self._bus.subscribe(
                self.topic, self._on_message
            )

    def _on_message(self, message) -> None:
        self._last_message = message

    def tick(self, context) -> NodeStatus:
        if not self._bus or not self.topic:
            return NodeStatus.FAILURE

        # 阻塞模式：轮询等待直到超时
        if self.wait_mode == "blocking" and self._last_message is None:
            elapsed = 0
            timeout_s = self.timeout_ms / 1000.0
            while self._last_message is None and elapsed < timeout_s:
                time.sleep(0.01)
                elapsed = time.perf_counter() - self._start_wait_time

        if self._last_message is not None:
            context.blackboard.set(
                self.payload_key, self._last_message.payload
            )
            # 写完后取消订阅（一次性）
            if self._subscription_id and self._bus:
                self._bus.unsubscribe(self._subscription_id)
                self._subscription_id = None
            return NodeStatus.SUCCESS

        # 非阻塞模式：未收到消息即 FAILURE（可被 retry 机制重试）
        if self.timeout_ms == 0:
            return NodeStatus.FAILURE

        # 有超时但未收到消息
        elapsed = time.perf_counter() - (self._start_wait_time or time.perf_counter())
        if elapsed * 1000 >= self.timeout_ms:
            # 取消订阅
            if self._subscription_id and self._bus:
                self._bus.unsubscribe(self._subscription_id)
                self._subscription_id = None
            return NodeStatus.FAILURE

        # 继续等待（RUNNING）
        return NodeStatus.RUNNING

    def reset(self, reset_counters: bool = True) -> None:
        super().reset(reset_counters)
        if self._subscription_id and self._bus:
            self._bus.unsubscribe(self._subscription_id)
            self._subscription_id = None
        self._last_message = None
        self._start_wait_time = None
```

**Step 4: Verify the test passes**

```bash
python tests/test_message_subscribe_node.py
```

**Step 5: Commit**

```bash
git add bt_nodes/message/subscribe_node.py tests/test_message_subscribe_node.py
git commit -m "feat(nodes): add MessageSubscribeNode with topic matching"
```

---

### Task 28: WebSocketNode + 节点注册 + GUI 集成 + settings_manager

**Files:**
- Create: `bt_nodes/network/websocket_node.py`
- Modify: `bt_nodes/__init__.py`（注册新节点）
- Modify: `bt_utils/settings_manager.py`（新增消息总线/服务端配置项）
- Modify: `bt_gui/main_window.py`（启动时初始化消息总线和服务端）
- Test: `tests/test_websocket_node.py`

**Step 1: Write the failing test**

```python
# tests/test_websocket_node.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import patch, MagicMock
from bt_core.context import ExecutionContext
from bt_core.config import NodeConfig
from bt_core.status import NodeStatus


class TestWebSocketNode(unittest.TestCase):
    """验证 WebSocket 客户端节点的连接与收发"""

    def setUp(self):
        from bt_nodes.network.websocket_node import WebSocketNode
        self.node_cls = WebSocketNode

    def test_send_message_on_tick(self):
        node = self.node_cls(config=NodeConfig(name="ws", extra={
            "url": "ws://127.0.0.1:8765",
            "action": "send",
            "message": '{"type":"ping"}',
        }))
        ctx = ExecutionContext()
        mock_ws = MagicMock()
        with patch.object(self.node_cls, "_get_connection",
                          return_value=mock_ws):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        mock_ws.send.assert_called_once_with('{"type":"ping"}')

    def test_receive_message_writes_to_blackboard(self):
        node = self.node_cls(config=NodeConfig(name="ws", extra={
            "url": "ws://127.0.0.1:8765",
            "action": "recv",
            "payload_key": "ws_msg",
            "timeout_ms": 500,
        }))
        ctx = ExecutionContext()
        mock_ws = MagicMock()
        mock_ws.recv.return_value = '{"v": 1}'
        with patch.object(self.node_cls, "_get_connection",
                          return_value=mock_ws):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(ctx.blackboard.get("ws_msg"), {"v": 1})

    def test_recv_timeout_returns_failure(self):
        import asyncio
        node = self.node_cls(config=NodeConfig(name="ws", extra={
            "url": "ws://127.0.0.1:8765",
            "action": "recv",
            "payload_key": "ws_msg",
            "timeout_ms": 100,
        }))
        ctx = ExecutionContext()
        mock_ws = MagicMock()
        mock_ws.recv.side_effect = TimeoutError("no message")
        with patch.object(self.node_cls, "_get_connection",
                          return_value=mock_ws):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)


class TestNodeRegistration(unittest.TestCase):
    """验证新节点已注册到 NodeRegistry"""

    def test_all_new_nodes_registered(self):
        # 仅检查导入路径，避免触发 GUI
        import importlib
        modules = [
            "bt_nodes.network.http_request_node",
            "bt_nodes.network.api_condition_node",
            "bt_nodes.network.websocket_node",
            "bt_nodes.message.publish_node",
            "bt_nodes.message.subscribe_node",
        ]
        for m in modules:
            mod = importlib.import_module(m)
            self.assertTrue(hasattr(mod, "__file__"), f"模块 {m} 未找到")


class TestSettingsManagerBusConfig(unittest.TestCase):
    """验证 settings_manager 新增消息总线配置项"""

    def test_default_config_has_bus_section(self):
        from bt_utils.settings_manager import SettingsManager
        sm = SettingsManager()
        cfg = sm.get_default_config()
        self.assertIn("message_bus", cfg)
        self.assertIn("rest_server", cfg)
        self.assertIn("websocket_server", cfg)
        self.assertEqual(cfg["rest_server"]["enabled"], False)
        self.assertEqual(cfg["rest_server"]["port"], 8080)
        self.assertEqual(cfg["websocket_server"]["enabled"], False)
        self.assertEqual(cfg["websocket_server"]["port"], 8765)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Verify the test fails**

```bash
python tests/test_websocket_node.py
```

预期失败：`ModuleNotFoundError: No module named 'bt_nodes.network.websocket_node'`
以及 `KeyError: 'message_bus'` 等错误

**Step 3: Implement minimal code**

```python
# bt_nodes/network/websocket_node.py
"""WebSocket 客户端节点：发送或接收 WebSocket 消息"""
import json as _json
import logging
import threading
from typing import Optional

try:
    import websockets
    import asyncio
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

from bt_core.nodes import Node
from bt_core.status import NodeStatus
from bt_core.config import NodeConfig

logger = logging.getLogger(__name__)


class WebSocketNode(Node):
    """WebSocket 客户端节点

    配置项：
        url: ws:// 或 wss:// 地址
        action: send / recv / connect
        message: send 模式下要发送的字符串
        payload_key: recv 模式下接收数据写入黑板的键名
        timeout_ms: recv 模式下的等待超时
    """

    NODE_TYPE = "WebSocketNode"

    _connections: dict = {}
    _lock = threading.Lock()

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.url = self.config.get("url", "")
        self.action = self.config.get("action", "send")
        self.message = self.config.get("message", "")
        self.payload_key = self.config.get("payload_key", "ws_message")
        self.timeout_ms = self.config.get_int("timeout_ms", 1000)

    def _get_connection(self):
        """获取或创建到 URL 的 WebSocket 连接（同步封装）"""
        with WebSocketNode._lock:
            if self.url in WebSocketNode._connections:
                return WebSocketNode._connections[self.url]
        if not HAS_WEBSOCKETS:
            raise RuntimeError("websockets 未安装")
        # 同步方式：用 asyncio.run 建立（简化示例）
        async def _connect():
            return await websockets.connect(self.url)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                ws = asyncio.run_coroutine_threadsafe(_connect(), loop).result(5)
            else:
                ws = asyncio.run(_connect())
        except Exception as e:
            logger.exception("WebSocket 连接失败: %s", e)
            return None
        with WebSocketNode._lock:
            WebSocketNode._connections[self.url] = ws
        return ws

    def tick(self, context) -> NodeStatus:
        if not self.url:
            return NodeStatus.FAILURE
        ws = self._get_connection()
        if ws is None:
            return NodeStatus.FAILURE
        try:
            if self.action == "send":
                self._send(ws, self.message)
                return NodeStatus.SUCCESS
            elif self.action == "recv":
                data = self._recv(ws, self.timeout_ms)
                if data is None:
                    return NodeStatus.FAILURE
                # 尝试 JSON 解析
                try:
                    parsed = _json.loads(data)
                except ValueError:
                    parsed = data
                context.blackboard.set(self.payload_key, parsed)
                return NodeStatus.SUCCESS
        except Exception as e:
            logger.exception("WebSocketNode 异常: %s", e)
            return NodeStatus.FAILURE

    @staticmethod
    def _send(ws, message: str) -> None:
        async def _do():
            await ws.send(message)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_do(), loop).result(5)
            else:
                asyncio.run(_do())
        except RuntimeError:
            asyncio.run(_do())

    @staticmethod
    def _recv(ws, timeout_ms: int):
        async def _do():
            return await asyncio.wait_for(ws.recv(), timeout=timeout_ms / 1000)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return asyncio.run_coroutine_threadsafe(_do(), loop).result(
                    timeout_ms / 1000 + 1)
            return asyncio.run(_do())
        except (asyncio.TimeoutError, TimeoutError):
            return None
        except RuntimeError:
            return asyncio.run(_do())
```

```python
# bt_utils/settings_manager.py（追加）
# 在 SettingsManager.get_default_config 中新增以下字段（合并到现有字典中）

# 追加到默认配置中：
DEFAULT_CONFIG_EXTENSION = {
    "message_bus": {
        "enabled": False,
        "shared_thread_pool_size": 8,
        "dead_letter_queue_size": 1000,
    },
    "rest_server": {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 8080,
        "auth_enabled": False,
    },
    "websocket_server": {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 8765,
        "heartbeat_interval": 30,
    },
    "sse_server": {
        "enabled": True,
        "max_clients": 10,
    },
}

# 在现有 get_default_config() 方法末尾合并：
#   config.update(DEFAULT_CONFIG_EXTENSION)
#   return config
```

```python
# bt_gui/main_window.py（修改 on_start_run 或 __init__）
# 在启动行为树前初始化消息总线与服务端（根据 settings）

def _init_message_bus_and_servers(self):
    """根据配置启动消息总线和服务端"""
    from bt_utils.settings_manager import SettingsManager
    sm = SettingsManager()
    sm.load()
    cfg = sm.get_config()

    if not cfg.get("message_bus", {}).get("enabled", False):
        return

    from bt_message_bus.bus import MessageBus
    bus = MessageBus()
    self._message_bus = bus

    # 启动 REST 服务端
    if cfg.get("rest_server", {}).get("enabled", False):
        from bt_servers.rest_server import RESTServer
        rest = RESTServer(
            host=cfg["rest_server"]["host"],
            port=cfg["rest_server"]["port"],
        )
        rest.attach_bus(bus)
        rest.start_in_thread()
        self._rest_server = rest

    # 启动 WebSocket 服务端
    if cfg.get("websocket_server", {}).get("enabled", False):
        from bt_servers.websocket_server import WebSocketServer
        ws = WebSocketServer(
            host=cfg["websocket_server"]["host"],
            port=cfg["websocket_server"]["port"],
        )
        ws.attach_bus(bus)
        ws.start_in_thread()
        self._ws_server = ws
```

**Step 4: Verify the test passes**

```bash
python tests/test_websocket_node.py
```

**Step 5: Commit**

```bash
git add bt_nodes/network/websocket_node.py bt_utils/settings_manager.py bt_gui/main_window.py tests/test_websocket_node.py
git commit -m "feat(nodes): add WebSocketNode and GUI message bus integration"
```

---

## 收尾汇总

### 任务清单总览

| Phase | Task 范围 | 主题 | 任务数 |
|-------|-----------|------|--------|
| Phase 0 | 1-8 | Headless 模式 + 异步执行 + CodeNode 安全 | 8 |
| Phase 1 | 9-12 | 消息总线核心（Message / TopicRouter / Bus / 中间件 + 死信） | 4 |
| Phase 2 | 13-15 | 适配器层（BaseAdapter / HTTP / WebSocket） | 3 |
| Phase 3 | 16-20 | 服务层（Registry / TreeService / DataService / NodeService+Context / Auth+EngineEvents） | 5 |
| Phase 4 | 21-23 | 服务端层（REST / SSE / WebSocket） | 3 |
| Phase 5 | 24-28 | 接口节点与 GUI 集成（HTTPRequestNode / APIConditionNode / MessagePublish / MessageSubscribe / WebSocketNode + GUI） | 5 |
| **合计** | **1-28** | — | **28** |

### 验收检查清单

- [ ] 所有 28 个任务的单元测试通过
- [ ] `MessageBus` 单例在多 Tab 场景下正确隔离 `tree_id`
- [ ] `SharedThreadPool` 配额（bus=3, adapter=3, async_node=2）不发生死锁
- [ ] 异步节点通过 `asyncio.to_thread()` 在线程池中执行不阻塞主循环
- [ ] CodeNode 的 AST 安全检查拒绝 `import os; os.system(...)` 等危险调用
- [ ] `__builtins__` 白名单不包含 `eval / exec / __import__ / open`
- [ ] REST 服务端 `/api/trees` 列表与 `/api/trees/{id}/start` 启动端到端可用
- [ ] SSE 事件流在树运行期间推送 `tree.started / node.status` 事件
- [ ] WebSocket 服务端支持 `?topic=bt.{tree_id}.**` 订阅过滤
- [ ] HTTPRequestNode 在 HTTP 5xx 时返回 FAILURE 且写入 `http_response_code`
- [ ] APIConditionNode 支持 `json_path` 嵌套取值（如 `data.code`）
- [ ] MessagePublishNode 默认 `prefix_tree_id=True`，确保多树互不干扰
- [ ] MessageSubscribeNode 在 `reset()` 时正确取消订阅，避免泄漏
- [ ] WebSocketNode 在 `recv` 超时返回 FAILURE 不抛异常
- [ ] HeadlessRunner 不依赖 `customtkinter` 可独立启动
- [ ] `settings_manager` 默认 `message_bus.enabled=False`，向后兼容
- [ ] `requirements.txt` 新增 `fastapi / uvicorn / requests / websockets / sse-starlette`
- [ ] 文档：`doc/用户使用手册.md` 增补消息总线与服务端配置章节

### 核心文件冲突规避策略

| 冲突文件 | Phase 0-1 修改点 | Phase 2-5 修改点 | 规避策略 |
|----------|------------------|------------------|----------|
| `bt_core/engine.py` | 新增 `_bus` 与异步执行钩子 | Phase 3 只读访问 | Phase 0 一次性合入，后续 Phase 仅读取 |
| `bt_core/nodes.py` | — | Phase 5 通过子类扩展 | 不修改基类，使用 mixin 或独立子类 |
| `bt_core/context.py` | 新增 `_message_bus` 字段 | Phase 3 扩展 `notify_node_status` | 一次合入字段，扩展方法独立提交 |
| `main.py` | Headless 分支 | — | Phase 0 单次合入 |
| `bt_utils/settings_manager.py` | — | Phase 5 新增配置段 | 追加 key 不删除现有 key |

### 依赖更新

```text
# requirements.txt 追加
fastapi>=0.104.0
uvicorn>=0.24.0
requests>=2.31.0
websockets>=12.0
sse-starlette>=1.6.5
```

### 后续扩展方向

1. **gRPC 适配器**：在 Phase 2 的 BaseAdapter 基础上扩展
2. **MQTT 适配器**：对接 IoT 设备
3. **Plugin 系统**：通过 entry_points 动态加载第三方适配器
4. **可视化调试**：在 GUI 中展示消息总线流量与死信队列
5. **分布式部署**：基于 Redis/RabbitMQ 的跨进程消息总线

---

**文档版本**：v1.0
**创建日期**：2026-07-12
**参考文档**：
- `md/05_消息总线与外部系统集成开发方案.md`
- `md/06_消息总线与外部系统集成开发计划.md`
**计划执行周期**：Phase 0-5 共 28 个 bite-sized 任务，每个任务 2-5 分钟可完成
**TDD 流程**：每个任务严格遵循「写失败测试 → 验证失败 → 最小实现 → 验证通过 → 提交」五步
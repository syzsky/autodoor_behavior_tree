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
            self._results.pop(node_id, None)  # clear stale result
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
        """取消所有任务（引擎停止时调用）

        注意: future.cancel() 无法中断正在执行的任务，仅能取消尚未开始的任务。
        正在执行的任务会继续运行到完成，但其结果会被标记为 FAILURE。
        """
        with self._lock:
            for node_id, future in self._futures.items():
                self._cancelled.add(node_id)
                future.cancel()
            self._futures.clear()

    def clear(self) -> None:
        """Clear all state (for long-running engines to prevent memory leak)"""
        with self._lock:
            self._futures.clear()
            self._results.clear()
            self._cancelled.clear()

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

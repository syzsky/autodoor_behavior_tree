"""死信队列 — 存储无法处理的消息"""
import threading
from collections import deque
from typing import Any, Dict, List


class DeadLetterQueue:
    def __init__(self, max_size: int = 1000):
        self._queue: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, message, reason: str = "UNKNOWN") -> None:
        entry = {
            "message": message,
            "reason": reason,
            "timestamp": message.timestamp if hasattr(message, 'timestamp') else None,
        }
        with self._lock:
            self._queue.append(entry)

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._queue)

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

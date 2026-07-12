"""总线统计 — 消息发布与投递计数"""
import threading
import time
from typing import Dict


class BusStats:
    def __init__(self):
        self._publish_count: Dict[str, int] = {}
        self._deliver_count: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()

    def record_publish(self, topic: str, delivered: int = 0) -> None:
        with self._lock:
            self._publish_count[topic] = self._publish_count.get(topic, 0) + 1
            self._deliver_count[topic] = self._deliver_count.get(topic, 0) + delivered

    def record_deliver(self, topic: str) -> None:
        with self._lock:
            self._deliver_count[topic] = self._deliver_count.get(topic, 0) + 1

    def get_publish_count(self, topic: str = None) -> int:
        with self._lock:
            if topic:
                return self._publish_count.get(topic, 0)
            return sum(self._publish_count.values())

    def get_deliver_count(self, topic: str = None) -> int:
        with self._lock:
            if topic:
                return self._deliver_count.get(topic, 0)
            return sum(self._deliver_count.values())

    def get_summary(self) -> dict:
        with self._lock:
            return {
                "uptime_seconds": time.time() - self._start_time,
                "total_publishes": sum(self._publish_count.values()),
                "total_deliveries": sum(self._deliver_count.values()),
                "topic_count": len(self._publish_count),
            }

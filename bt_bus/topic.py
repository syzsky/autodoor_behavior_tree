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

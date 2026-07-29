"""MessageBus 核心 — 进程内消息总线"""
import asyncio
import threading
import uuid
from typing import Any, Callable, List, Optional, Set

from .message import Message
from .topic import TopicRouter
from .thread_pool import SharedThreadPool


class MessageBus:
    MAX_DELIVER_DEPTH = 5  # 递归发布深度上限，防止无限循环

    _instance: Optional["MessageBus"] = None
    _instance_lock = threading.RLock()

    def __new__(cls):
        # 双重检查锁 — 原子化单例
        # 所有属性初始化在锁内完成，cls._instance 赋值作为最后一步，
        # 确保其他线程拿到实例时所有属性已就绪，避免半初始化暴露
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    from .dead_letter import DeadLetterQueue
                    from .stats import BusStats
                    from .middleware import ValidationMiddleware

                    instance = super().__new__(cls)
                    # 在锁内完成所有属性初始化（原子性）
                    instance._router = TopicRouter()
                    instance._dead_letter_queue = DeadLetterQueue(max_size=1000)
                    # 默认中间件链包含 ValidationMiddleware，注入死信队列引用 (B4)
                    instance._middleware_chain: List = [
                        ValidationMiddleware(dead_letter_queue=instance._dead_letter_queue)
                    ]
                    instance._bus_lock = threading.RLock()
                    instance._running = False
                    instance._shared_pool = SharedThreadPool.get_instance()
                    instance._blocked_thread_ids: Set[int] = set()
                    instance._event_loop = None
                    instance._stats = BusStats()
                    instance._async_queues: List[tuple] = []  # (pattern, queue, subscription_id)
                    instance._async_queue_lock = threading.RLock()
                    instance._initialized = True  # 最后标记
                    cls._instance = instance        # 暴露实例（最后一步）
        return cls._instance

    def __init__(self):
        # no-op：所有初始化在 __new__ 中完成
        # Python 语义保证 __init__ 每次 MessageBus() 都会调用，
        # 但实例已完全初始化，无需重复
        pass

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（停止旧实例并清除引用）

        在 GUI 启动或测试中需要全新 MessageBus 时调用。
        """
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance.stop()
                except Exception:
                    pass
                cls._instance = None

    def publish(self, topic: str, data: Any, headers: dict = None,
                source: str = "") -> str:
        msg = Message.create(topic, data, source, headers)

        def final_handler(m: Message) -> Message:
            subscriptions = self._router.match(m.topic)
            if not subscriptions:
                self._dead_letter_queue.add(m, reason="NO_SUBSCRIBER")
                self._stats.record_publish(m.topic)
                return m
            for sub in subscriptions:
                self._shared_pool.submit("bus", self._deliver, sub, m)
            self._stats.record_publish(m.topic)
            return m

        handler = final_handler
        for mw in reversed(list(self._middleware_chain)):
            handler = (lambda m, h=handler, mw=mw: mw.process(m, h))
        result = handler(msg)
        return msg.id

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

    def subscribe(self, topic_pattern: str, callback: Callable) -> str:
        with self._bus_lock:
            return self._router.subscribe(topic_pattern, callback)

    def unsubscribe(self, subscription_id: str) -> None:
        with self._bus_lock:
            self._router.unsubscribe(subscription_id)

    def request(self, topic: str, data: Any, timeout_ms: int = 5000,
                headers: dict = None, source: str = "") -> Optional[Message]:
        with self._bus_lock:
            is_blocked = threading.get_ident() in self._blocked_thread_ids
        if is_blocked:
            from bt_utils.log_manager import LogManager
            LogManager.debug_print(f"[MessageBus] request() called from engine thread, degrading to publish: {topic}")
            self.publish(topic, data, headers=headers, source=source or "request_degraded")
            return None

        reply_topic = f"_reply.{uuid.uuid4().hex}"
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

    def subscribe_async(self, topic_pattern: str, maxsize: int = 1000) -> tuple:
        """异步订阅主题，返回 (asyncio.Queue, subscription_id)

        Args:
            topic_pattern: 主题模式
            maxsize: 队列最大容量，满时丢弃最旧消息（默认 1000）
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)

        def callback(msg: Message):
            # Push to this specific queue only
            self._push_to_single_async_queue(queue, msg)

        sub_id = self.subscribe(topic_pattern, callback)

        with self._async_queue_lock:
            self._async_queues.append((topic_pattern, queue, sub_id))

        return queue, sub_id

    def unsubscribe_async(self, sub_id: str) -> None:
        """取消异步订阅"""
        with self._async_queue_lock:
            self._async_queues = [
                (p, q, s) for (p, q, s) in self._async_queues if s != sub_id
            ]
        self.unsubscribe(sub_id)

    def _push_to_single_async_queue(self, queue: asyncio.Queue, msg: Message) -> None:
        """推送消息到单个异步队列，满时丢弃最旧消息"""
        try:
            with self._bus_lock:
                loop = self._event_loop

            if loop and loop.is_running():
                # 生产路径：通过 call_soon_threadsafe 在事件循环线程中执行
                # 使用 put_nowait 而非 put 协程，避免满时阻塞等待
                def _safe_put():
                    try:
                        queue.put_nowait(msg)
                    except asyncio.QueueFull:
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        queue.put_nowait(msg)
                        from bt_utils.log_manager import LogManager
                        LogManager.debug_print("[MessageBus] Async queue full, dropped oldest message")

                loop.call_soon_threadsafe(_safe_put)
            else:
                # 测试路径：直接 put_nowait
                try:
                    queue.put_nowait(msg)
                except asyncio.QueueFull:
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

    def add_middleware(self, middleware) -> None:
        with self._bus_lock:
            self._middleware_chain.append(middleware)

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def set_engine_thread_id(self, thread_id: int) -> None:
        with self._bus_lock:
            self._blocked_thread_ids.add(thread_id)

    def set_event_loop(self, loop) -> None:
        with self._bus_lock:
            self._event_loop = loop

    def get_event_loop(self):
        with self._bus_lock:
            return self._event_loop

    def get_stats(self):
        return self._stats

    def get_dead_letter_queue(self):
        return self._dead_letter_queue

"""MessageBus 核心 — 进程内消息总线"""
import asyncio
import threading
import time
from typing import Any, Callable, List, Optional, Set

from .message import Message
from .topic import TopicRouter
from .thread_pool import SharedThreadPool


class MessageBus:
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
        self._async_queues: List[asyncio.Queue] = []
        self._async_queue_lock = threading.Lock()

    def publish(self, topic: str, data: Any, headers: dict = None,
                source: str = "") -> str:
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
            self._push_to_async_queues(m)
            return m

        handler = final_handler
        for mw in reversed(self._middleware_chain):
            handler = (lambda m, h=handler, mw=mw: mw.process(m, h))
        result = handler(msg)
        return msg.id

    def _deliver(self, sub, msg: Message) -> None:
        try:
            response = sub.callback(msg)
            if response is not None and isinstance(response, Message):
                reply_to = msg.headers.get("reply_to")
                if reply_to:
                    response.topic = reply_to
                    self.publish(reply_to, response.data,
                                 headers=response.headers,
                                 source="responder")
        except Exception as e:
            print(f"[MessageBus] Subscriber exception: {e}")

    def subscribe(self, topic_pattern: str, callback: Callable) -> str:
        with self._bus_lock:
            return self._router.subscribe(topic_pattern, callback)

    def unsubscribe(self, subscription_id: str) -> None:
        with self._bus_lock:
            self._router.unsubscribe(subscription_id)

    def request(self, topic: str, data: Any, timeout_ms: int = 5000,
                headers: dict = None, source: str = "") -> Optional[Message]:
        if threading.get_ident() in self._blocked_thread_ids:
            print(f"[MessageBus] request() called from engine thread, degrading to publish: {topic}")
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
        queue: asyncio.Queue = asyncio.Queue()
        with self._async_queue_lock:
            self._async_queues.append(queue)
        # Subscribe with a callback that does nothing (messages pushed via _push_to_async_queues)
        self.subscribe(topic_pattern, lambda m: None)
        return queue

    def _push_to_async_queues(self, msg: Message) -> None:
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
        with self._bus_lock:
            self._middleware_chain.append(middleware)

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def set_engine_thread_id(self, thread_id: int) -> None:
        self._blocked_thread_ids.add(thread_id)

    def set_event_loop(self, loop) -> None:
        self._event_loop = loop

    def get_event_loop(self):
        return self._event_loop

    def get_stats(self):
        return self._stats

    def get_dead_letter_queue(self):
        return self._dead_letter_queue

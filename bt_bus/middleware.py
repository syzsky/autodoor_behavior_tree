"""中间件基类 + 内置中间件（责任链模式）"""
import time
import threading
from typing import Callable, Optional

from .message import Message


class Middleware:
    def process(self, message: Message, next_handler: Callable) -> Optional[Message]:
        return next_handler(message)


class LoggingMiddleware(Middleware):
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
    def process(self, message: Message, next_handler: Callable) -> Optional[Message]:
        if not message.topic:
            return None
        if message.data is None:
            return None
        return next_handler(message)


class RateLimitMiddleware(Middleware):
    def __init__(self, max_per_second: int = 100):
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
                return None
            self._tokens -= 1
        return next_handler(message)


class AuthMiddleware(Middleware):
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
                return None
        return next_handler(message)

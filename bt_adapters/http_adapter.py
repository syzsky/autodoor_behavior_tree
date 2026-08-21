"""HTTP/REST 协议适配器

参考开发方案 §3.2 和开发计划 §2.1.2。
"""
import json as _json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import BaseAdapter, AdapterLevel, AdapterStatus
from .config import AdapterConfig


_JSON_UNSET = object()


@dataclass
class HTTPResponse:
    """HTTP 响应封装"""
    status_code: int
    text: str
    headers: Dict[str, str] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    _json_cache: Any = field(default=_JSON_UNSET, repr=False)

    @property
    def json(self) -> Any:
        """解析 JSON 响应"""
        if self._json_cache is _JSON_UNSET:
            try:
                self._json_cache = _json.loads(self.text) if self.text else None
            except _json.JSONDecodeError:
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
        self._lock = threading.Lock()

    def start(self) -> None:
        import requests
        self._session = requests.Session()
        self._running = True

    def stop(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
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
             body: Any = None, timeout_ms: Optional[int] = None,
             retry_count: Optional[int] = None,
             retry_interval_ms: Optional[int] = None) -> HTTPResponse:
        """发起 HTTP 请求

        Args:
            method: GET/POST/PUT/DELETE/PATCH
            url: 请求 URL
            headers: 请求头
            body: 请求体（dict 自动转 JSON）
            timeout_ms: 超时（毫秒），None 时回退到 config.read_timeout
            retry_count: 重试次数，None 时回退到 config.max_retries
            retry_interval_ms: 重试间隔（毫秒），None 时回退到 config.retry_backoff_ms

        Returns:
            HTTPResponse 对象
        """
        import requests

        if timeout_ms is None:
            timeout_ms = self._config.read_timeout * 1000
        if retry_count is None:
            retry_count = self._config.max_retries
        if retry_interval_ms is None:
            retry_interval_ms = self._config.retry_backoff_ms

        if self._session is None:
            with self._lock:
                if self._session is None:
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

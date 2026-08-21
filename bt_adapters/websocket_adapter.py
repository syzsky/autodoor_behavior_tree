"""WebSocket 协议适配器

参考开发方案 §3.2 和开发计划 §2.1.3。
客户端模式：连接外部 WebSocket 服务，自动重连 + 心跳。
"""
import asyncio
import threading
from typing import Callable, Optional

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
        self._ws = None  # 清理 ws 引用，避免后续 send() 误用已关闭连接
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

        Raises:
            RuntimeError: 已存在活动连接，需先调用 stop()
        """
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("WebSocketAdapter already connected, call stop() first")
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
        except Exception as e:
            print(f"[WebSocketAdapter] run_loop error: {e}")
        finally:
            self._loop.close()

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
            except (OSError, asyncio.TimeoutError, ConnectionError,
                    websockets.WebSocketException) as e:
                if self._running:
                    print(f"[WebSocketAdapter] connection error: {e}")
                    self._ws = None  # 重置 ws 引用，避免使用已失效的连接
                    await asyncio.sleep(self._reconnect_interval_ms / 1000)

    async def send(self, message: str) -> None:
        """发送消息

        Raises:
            RuntimeError: WebSocket 未连接
        """
        if self._ws is None:
            raise RuntimeError("WebSocket not connected")
        await self._ws.send(message)

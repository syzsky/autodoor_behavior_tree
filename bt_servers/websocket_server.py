"""WebSocket 服务端：向客户端广播消息总线事件"""
import asyncio
import json
import logging
from typing import Set

try:
    from websockets.asyncio.server import serve
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    serve = None

logger = logging.getLogger(__name__)


class WebSocketServer:
    """WebSocket 服务端

    客户端可通过 query 参数 `topic` 订阅主题（支持通配符），
    服务端将消息总线的消息广播给匹配订阅的客户端。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765, auth_service=None):
        self.host = host
        self.port = port
        self._server = None
        self._clients: Set = set()
        self._client_topics: dict = {}
        self._bus = None
        self._heartbeat_interval = 30.0
        self._running = False
        self._loop = None
        self._auth = auth_service

    def attach_bus(self, bus) -> None:
        """绑定消息总线，订阅所有消息并广播"""
        self._bus = bus
        bus.subscribe("**", self._on_bus_message)

    def _on_bus_message(self, message) -> None:
        """消息总线回调：广播给匹配订阅的客户端"""
        if not self._loop or not self._loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(message), self._loop)

    async def _broadcast(self, message) -> None:
        payload = json.dumps({
            "topic": message.topic,
            "data": message.data,
            "timestamp": message.timestamp,
            "source": message.source,
        })
        # Collect (ws, send_task) for clients that match the topic
        matching = [
            (ws, ws.send(payload))
            for ws, topic_filter in self._client_topics.items()
            if self._topic_matches(topic_filter, message.topic)
        ]
        if not matching:
            return
        # Send in parallel, collecting exceptions
        results = await asyncio.gather(
            *[task for (_, task) in matching],
            return_exceptions=True
        )
        # Remove dead clients
        dead = [
            ws for (ws, _), result in zip(matching, results)
            if isinstance(result, Exception)
        ]
        for ws in dead:
            self._clients.discard(ws)
            self._client_topics.pop(ws, None)

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        if not pattern or pattern == "**":
            return True
        pattern_parts = pattern.split(".")
        topic_parts = topic.split(".")
        for i, p in enumerate(pattern_parts):
            if p == "**":
                return True
            if i >= len(topic_parts):
                return False
            if p != "*" and p != topic_parts[i]:
                return False
        return len(pattern_parts) == len(topic_parts)

    async def start(self) -> None:
        if not HAS_WEBSOCKETS:
            raise RuntimeError("websockets 未安装")
        self._running = True
        self._loop = asyncio.get_running_loop()
        self._server = await serve(self._handle_client, self.host, self.port)
        logger.info("WebSocket 服务端已启动 %s:%d", self.host, self.port)

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        # Clear client tracking (prevents stale references if restarted)
        self._clients.clear()
        self._client_topics.clear()

    async def _handle_client(self, ws) -> None:
        """处理客户端连接（websockets 16+ API: 1 arg, path via ws.request.path)"""
        # websockets 16+: path is in ws.request.path
        path = getattr(getattr(ws, 'request', None), 'path', '/') or '/'
        topic_filter = "**"
        token = None
        if "?" in path:
            query = path.split("?", 1)[1]
            for kv in query.split("&"):
                if kv.startswith("topic="):
                    topic_filter = kv[6:]
                elif kv.startswith("token="):
                    token = kv[6:]

        if self._auth and not self._auth.verify_token(token):
            await ws.send(json.dumps({"type": "error", "msg": "unauthorized"}))
            await ws.close(code=1008, reason="Unauthorized")
            return

        self._clients.add(ws)
        self._client_topics[ws] = topic_filter
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"type": "error", "msg": "invalid json"}))
        finally:
            self._clients.discard(ws)
            self._client_topics.pop(ws, None)

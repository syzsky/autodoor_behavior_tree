import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import asyncio
import threading
import time


class TestWebSocketServer(unittest.TestCase):
    """验证 WebSocket 服务端的消息收发与心跳"""

    def setUp(self):
        from bt_servers.websocket_server import WebSocketServer
        self.server = WebSocketServer(host="127.0.0.1", port=8765)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        time.sleep(0.3)  # 等待服务启动

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.server.start())
        self.loop.run_forever()

    def tearDown(self):
        # 先在事件循环中优雅关闭服务端，释放端口，再停止循环
        async def _shutdown():
            await self.server.stop()
        fut = asyncio.run_coroutine_threadsafe(_shutdown(), self.loop)
        try:
            fut.result(timeout=2)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)
        self.loop.close()

    def test_server_starts_and_accepts_connection(self):
        """服务端启动后可接受连接"""
        import websockets

        async def client():
            async with websockets.connect("ws://127.0.0.1:8765") as ws:
                await ws.send('{"type":"ping"}')
                resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                self.assertIn("pong", resp)

        asyncio.run(asyncio.wait_for(client(), timeout=5.0))

    def test_server_broadcasts_bus_messages(self):
        """消息总线发布后客户端可收到广播"""
        from bt_bus.message_bus import MessageBus
        from bt_bus.thread_pool import SharedThreadPool

        # Reset singletons
        SharedThreadPool.reset_instance()
        MessageBus._instance = None
        bus = MessageBus()
        bus.start()
        try:
            self.server.attach_bus(bus)

            import websockets

            async def client():
                async with websockets.connect("ws://127.0.0.1:8765?topic=bt.**") as ws:
                    # 给服务端一点时间注册订阅
                    await asyncio.sleep(0.2)
                    bus.publish("bt.test.event", {"v": 1})
                    resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    self.assertIn("bt.test.event", resp)

            asyncio.run(asyncio.wait_for(client(), timeout=5.0))
        finally:
            bus.stop()
            SharedThreadPool.reset_instance()


if __name__ == "__main__":
    unittest.main()

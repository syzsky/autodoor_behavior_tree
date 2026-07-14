# tests/test_context_bus_integration.py
"""B-2: 验证 ExecutionContext 消息总线注入链路。

测试链路：context.set_message_bus() → context.get_message_bus()
        + blackboard 被注入 bus → blackboard.set() 发布事件。

不启动真实 uvicorn/websockets 服务，仅验证 context 注入逻辑。
"""
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestContextBusIntegration(unittest.TestCase):
    """验证 context 的 message_bus 注入链路（含 blackboard 联动）"""

    def setUp(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()
        from bt_bus.message_bus import MessageBus
        MessageBus._instance = None
        self.bus = MessageBus()
        self.bus.start()

    def tearDown(self):
        self.bus.stop()
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def _wait_for(self, received, timeout=1.0):
        """轮询等待消息到达，最多等待 timeout 秒"""
        elapsed = 0.0
        while not received and elapsed < timeout:
            time.sleep(0.02)
            elapsed += 0.02

    def test_get_message_bus_returns_none_by_default(self):
        """未注入时 get_message_bus() 返回 None（降级行为）"""
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        self.assertIsNone(ctx.get_message_bus())

    def test_set_message_bus_returns_same_instance(self):
        """set_message_bus() 后 get_message_bus() 返回正确实例"""
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.set_message_bus(self.bus)
        self.assertIs(ctx.get_message_bus(), self.bus)

    def test_set_message_bus_injects_into_blackboard(self):
        """set_message_bus() 后 blackboard.set() 发布事件到 bus"""
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.set_message_bus(self.bus)

        received = []
        self.bus.subscribe("bt.default.data.blackboard.changed",
                           lambda m: received.append(m))

        ctx.blackboard.set("foo", "bar")

        self._wait_for(received)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["key"], "foo")
        self.assertEqual(received[0].data["new_value"], "bar")

    def test_set_message_bus_uses_context_tree_id(self):
        """注入 blackboard 时使用 context 的 tree_id（来自 tab_id）"""
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.set_tab_manager(None, tab_id="tab_abc")
        ctx.set_message_bus(self.bus)

        received = []
        self.bus.subscribe("bt.tab_abc.data.blackboard.changed",
                           lambda m: received.append(m))

        ctx.blackboard.set("x", 1)

        self._wait_for(received)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].topic, "bt.tab_abc.data.blackboard.changed")

    def test_set_message_bus_none_degrades_gracefully(self):
        """set_message_bus(None) 后 blackboard.set() 不报错（降级）"""
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.set_message_bus(self.bus)
        # 清除引用，降级为本地模式
        ctx.set_message_bus(None)

        self.assertIsNone(ctx.get_message_bus())
        # blackboard.set() 不应抛异常
        ctx.blackboard.set("k", "v")
        self.assertEqual(ctx.blackboard.get("k"), "v")

    def test_set_message_bus_none_blackboard_no_publish(self):
        """set_message_bus(None) 后 blackboard 不再向 bus 发布事件"""
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.set_message_bus(self.bus)
        ctx.set_message_bus(None)

        received = []
        self.bus.subscribe("bt.default.data.blackboard.changed",
                           lambda m: received.append(m))

        ctx.blackboard.set("no_pub", 1)
        self._wait_for(received, timeout=0.3)
        self.assertEqual(len(received), 0)


if __name__ == '__main__':
    unittest.main()

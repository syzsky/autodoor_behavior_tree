# tests/test_message_publish_node.py
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bt_core.context import ExecutionContext
from bt_core.config import NodeConfig
from bt_core.status import NodeStatus


class TestMessagePublishNode(unittest.TestCase):
    """验证消息发布节点向消息总线发布消息"""

    def setUp(self):
        """每个测试前重置 MessageBus 和 SharedThreadPool 单例"""
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

    def _wait_for_message(self, received, timeout=1.0):
        """轮询等待消息到达，最多等待 timeout 秒"""
        elapsed = 0.0
        while not received and elapsed < timeout:
            time.sleep(0.02)
            elapsed += 0.02

    def test_publish_static_payload(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_bus.message_bus import MessageBus

        bus = MessageBus()
        received = []
        bus.subscribe("bt.test.**", lambda m: received.append(m))

        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "bt.test.event",
            "payload": {"v": 1},
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self._wait_for_message(received)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data, {"v": 1})  # data 字段，非 payload

    def test_publish_blackboard_payload(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_bus.message_bus import MessageBus

        bus = MessageBus()
        received = []
        bus.subscribe("bt.**", lambda m: received.append(m))

        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "bt.test.event",
            "payload_key": "my_data",
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        ctx.blackboard.set("my_data", {"score": 100})
        status = node.tick(ctx)
        self._wait_for_message(received)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data, {"score": 100})  # data 字段

    def test_publish_with_tree_id_prefix(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_bus.message_bus import MessageBus

        bus = MessageBus()
        received = []
        bus.subscribe("bt.tree123.**", lambda m: received.append(m))

        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "event.started",
            "payload": {},
            "prefix_tree_id": True,
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        ctx._current_tab_id = "tree123"
        status = node.tick(ctx)
        self._wait_for_message(received)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].topic, "bt.tree123.event.started")

    def test_no_bus_returns_failure(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "x",
        }))
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_empty_topic_returns_failure(self):
        """topic 为空时返回 FAILURE"""
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_bus.message_bus import MessageBus
        bus = MessageBus()
        node = MessagePublishNode(config=NodeConfig(name="pub", extra={}))
        node.set_bus(bus)
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_context_message_bus_injection(self):
        """未调用 set_bus 但 context 注入了 message_bus 时应正常发布"""
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_bus.message_bus import MessageBus

        bus = MessageBus()
        received = []
        bus.subscribe("bt.test.**", lambda m: received.append(m))

        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "bt.test.event",
            "payload": {"via": "context"},
        }))
        # 不调用 node.set_bus(bus)，仅通过 context 注入
        ctx = ExecutionContext()
        ctx.set_message_bus(bus)
        status = node.tick(ctx)
        self._wait_for_message(received)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data, {"via": "context"})

    def test_payload_key_not_found_returns_success_with_static(self):
        """payload_key 不存在时回退到静态 payload 并返回 SUCCESS"""
        from bt_nodes.message.publish_node import MessagePublishNode
        from bt_bus.message_bus import MessageBus
        bus = MessageBus()
        received = []
        bus.subscribe("bt.test.**", lambda m: received.append(m))
        node = MessagePublishNode(config=NodeConfig(name="pub", extra={
            "topic": "bt.test.event",
            "payload": {"fallback": True},
            "payload_key": "nonexistent",
        }))
        node.set_bus(bus)
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self._wait_for_message(received)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data, {"fallback": True})


if __name__ == "__main__":
    unittest.main()

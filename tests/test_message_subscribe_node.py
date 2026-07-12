# tests/test_message_subscribe_node.py
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


class TestMessageSubscribeNode(unittest.TestCase):
    """验证消息订阅节点能从消息总线接收消息并写入黑板"""

    def setUp(self):
        from bt_bus.message_bus import MessageBus
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()
        MessageBus._instance = None
        self.bus = MessageBus()
        self.bus.start()

    def tearDown(self):
        self.bus.stop()
        from bt_bus.message_bus import MessageBus
        from bt_bus.thread_pool import SharedThreadPool
        MessageBus._instance = None
        SharedThreadPool.reset_instance()

    def _wait_for_message(self, node, timeout=1.0):
        """轮询等待消息到达"""
        elapsed = 0.0
        while node._last_message is None and elapsed < timeout:
            time.sleep(0.02)
            elapsed += 0.02

    def test_receive_message_writes_to_blackboard(self):
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.test.**",
            "payload_key": "last_msg",
            "timeout_ms": 1000,
        }))
        node.set_bus(self.bus)
        ctx = ExecutionContext()
        node.on_start(ctx)

        # 模拟总线发布一条消息
        self.bus.publish("bt.test.event", {"v": 42})
        self._wait_for_message(node)
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(ctx.blackboard.get("last_msg"), {"v": 42})

    def test_no_message_timeout_returns_failure(self):
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.test.**",
            "payload_key": "last_msg",
            "timeout_ms": 100,
        }))
        node.set_bus(self.bus)
        ctx = ExecutionContext()
        node.on_start(ctx)
        # 立即 tick，无消息应返回 FAILURE
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_node_only_receives_matching_topic(self):
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.treeA.**",
            "payload_key": "msg_a",
        }))
        node.set_bus(self.bus)
        ctx = ExecutionContext()
        node.on_start(ctx)

        # 不匹配的消息
        self.bus.publish("bt.treeB.event", {"v": 1})
        time.sleep(0.1)  # 等待异步投递
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)
        self.assertIsNone(ctx.blackboard.get("msg_a"))

        # 匹配的消息
        self.bus.publish("bt.treeA.event", {"v": 2})
        self._wait_for_message(node)
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(ctx.blackboard.get("msg_a"), {"v": 2})


if __name__ == "__main__":
    unittest.main()

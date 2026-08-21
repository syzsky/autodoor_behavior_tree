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

    def test_nonblocking_no_message_returns_failure(self):
        """非阻塞模式下未收到消息立即返回 FAILURE，且应取消订阅避免泄漏"""
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.test.**",
            "payload_key": "last_msg",
        }))
        node.set_bus(self.bus)
        ctx = ExecutionContext()
        node.on_start(ctx)
        # 立即 tick，无消息应返回 FAILURE
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)
        # Important #1: 非阻塞 FAILURE 路径应取消订阅，避免订阅泄漏
        self.assertIsNone(node._subscription_id)

    def test_nonblocking_failure_unsubscribes_so_no_further_messages(self):
        """非阻塞 FAILURE 后再 publish 不应触发回调（订阅已取消）"""
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.test.**",
            "payload_key": "last_msg",
        }))
        node.set_bus(self.bus)
        ctx = ExecutionContext()
        node.on_start(ctx)
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

        # 取消订阅后再发布消息，不应被接收
        self.bus.publish("bt.test.event", {"v": 999})
        time.sleep(0.1)
        self.assertIsNone(node._last_message)

    def test_reset_unsubscribes_when_bus_injected_via_context(self):
        """bus 通过 context 注入时，reset() 应能取消订阅（Important #2）"""
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.test.**",
            "payload_key": "last_msg",
        }))
        # 不调用 node.set_bus()，仅通过 context 注入
        ctx = ExecutionContext()
        ctx.set_message_bus(self.bus)
        node.on_start(ctx)
        # 触发懒订阅
        self.assertIsNotNone(node._subscription_id)
        # bus 应被缓存到 self._bus，使 reset() 能取消订阅
        self.assertIsNotNone(node._bus)
        node.reset()
        self.assertIsNone(node._subscription_id)

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
        # 确认不匹配的消息未被接收
        self.assertIsNone(node._last_message)
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)
        self.assertIsNone(ctx.blackboard.get("msg_a"))

        # 重新订阅（前次 FAILURE 已取消订阅）
        node.on_start(ctx)
        # 匹配的消息
        self.bus.publish("bt.treeA.event", {"v": 2})
        self._wait_for_message(node)
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(ctx.blackboard.get("msg_a"), {"v": 2})

    def test_blocking_mode_returns_running_then_success(self):
        """blocking 模式首次 tick 返回 RUNNING，消息到达后 SUCCESS"""
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(
            name="sub", timeout_ms=2000,
            extra={
                "topic": "bt.test.**",
                "payload_key": "last_msg",
                "wait_mode": "blocking",
            }))
        node.set_bus(self.bus)
        ctx = ExecutionContext()
        node.on_start(ctx)

        # 首次 tick，无消息应返回 RUNNING
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.RUNNING)

        # 发布消息
        self.bus.publish("bt.test.event", {"v": 1})
        self._wait_for_message(node)

        # 再次 tick，应返回 SUCCESS
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(ctx.blackboard.get("last_msg"), {"v": 1})

    def test_blocking_mode_timeout_returns_failure(self):
        """blocking 模式超时后返回 FAILURE"""
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(
            name="sub", timeout_ms=100,
            extra={
                "topic": "bt.test.**",
                "payload_key": "last_msg",
                "wait_mode": "blocking",
            }))
        node.set_bus(self.bus)
        ctx = ExecutionContext()
        node.on_start(ctx)

        # 首次 tick 返回 RUNNING
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.RUNNING)

        # 等待超时
        time.sleep(0.15)

        # 超时后 tick 返回 FAILURE
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_blocking_mode_no_timeout_returns_failure(self):
        """blocking 模式 timeout_ms=0 时立即返回 FAILURE"""
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        node = MessageSubscribeNode(config=NodeConfig(name="sub", extra={
            "topic": "bt.test.**",
            "payload_key": "last_msg",
            "timeout_ms": 0,
            "wait_mode": "blocking",
        }))
        node.set_bus(self.bus)
        ctx = ExecutionContext()
        node.on_start(ctx)

        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)


if __name__ == "__main__":
    unittest.main()

# tests/test_blackboard_events.py
"""B-1: 验证 Blackboard.set() 向 MessageBus 发布黑板变更事件。"""
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestBlackboardEvents(unittest.TestCase):
    """验证 Blackboard.set() 向 MessageBus 发布事件"""

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

    def _wait_for(self, received, timeout=1.0):
        """轮询等待消息到达，最多等待 timeout 秒"""
        elapsed = 0.0
        while not received and elapsed < timeout:
            time.sleep(0.02)
            elapsed += 0.02

    def test_set_publishes_blackboard_changed_event(self):
        """set() 后 bus 收到 bt.{tree_id}.data.blackboard.changed 事件"""
        from bt_core.blackboard import Blackboard
        bb = Blackboard()
        bb.set_message_bus(self.bus, tree_id="tree1")

        received = []
        self.bus.subscribe("bt.tree1.data.blackboard.changed",
                           lambda m: received.append(m))

        bb.set("foo", 123)

        self._wait_for(received)
        self.assertEqual(len(received), 1)
        msg = received[0]
        self.assertEqual(msg.topic, "bt.tree1.data.blackboard.changed")
        self.assertEqual(msg.source, "blackboard")
        self.assertEqual(msg.data["key"], "foo")
        self.assertEqual(msg.data["new_value"], 123)
        self.assertIsNone(msg.data["old_value"])

    def test_set_publishes_old_and_new_value_on_update(self):
        """更新已有键时 payload 包含正确的 old_value 与 new_value"""
        from bt_core.blackboard import Blackboard
        bb = Blackboard()
        bb.set_message_bus(self.bus, tree_id="t2")
        bb.set("counter", 1)

        received = []
        self.bus.subscribe("bt.t2.data.blackboard.changed",
                           lambda m: received.append(m))

        bb.set("counter", 2)

        self._wait_for(received)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["old_value"], 1)
        self.assertEqual(received[0].data["new_value"], 2)
        self.assertEqual(received[0].data["key"], "counter")

    def test_set_without_bus_does_not_raise(self):
        """无 bus 注入时 set() 不报错（向后兼容）"""
        from bt_core.blackboard import Blackboard
        bb = Blackboard()
        # 未调用 set_message_bus，_bus 为 None
        bb.set("key", "value")
        self.assertEqual(bb.get("key"), "value")

    def test_set_without_bus_preserves_subscriber_notification(self):
        """无 bus 时本地 subscriber 通知仍正常工作"""
        from bt_core.blackboard import Blackboard
        bb = Blackboard()
        notified = []
        bb.subscribe("k", lambda old, new: notified.append((old, new)))
        bb.set("k", "v")
        self.assertEqual(notified, [(None, "v")])

    def test_default_tree_id_is_default(self):
        """未指定 tree_id 时使用 'default' 作为主题段"""
        from bt_core.blackboard import Blackboard
        bb = Blackboard()
        bb.set_message_bus(self.bus)  # 不传 tree_id

        received = []
        self.bus.subscribe("bt.default.data.blackboard.changed",
                           lambda m: received.append(m))

        bb.set("x", 1)

        self._wait_for(received)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].topic, "bt.default.data.blackboard.changed")


if __name__ == '__main__':
    unittest.main()

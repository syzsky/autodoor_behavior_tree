import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestMessage(unittest.TestCase):
    def test_message_create(self):
        from bt_bus.message import Message, MessagePriority
        msg = Message.create(
            topic="bt.1.event.tree.started",
            data={"tree_id": "1"},
            source="engine"
        )
        self.assertTrue(msg.id)
        self.assertEqual(msg.topic, "bt.1.event.tree.started")
        self.assertEqual(msg.data, {"tree_id": "1"})
        self.assertEqual(msg.source, "engine")
        self.assertEqual(msg.priority, MessagePriority.NORMAL)
        self.assertIsNotNone(msg.correlation_id)
        self.assertIsNone(msg.reply_to)
        self.assertIsInstance(msg.timestamp, float)

    def test_message_id_unique(self):
        from bt_bus.message import Message
        ids = set()
        for _ in range(100):
            msg = Message.create("test", "data")
            ids.add(msg.id)
        self.assertEqual(len(ids), 100)

    def test_message_headers_default_empty(self):
        from bt_bus.message import Message
        msg = Message.create("t", "d")
        self.assertEqual(msg.headers, {})

    def test_message_headers_preserved(self):
        from bt_bus.message import Message
        msg = Message.create("t", "d", headers={"Authorization": "Bearer xyz"})
        self.assertEqual(msg.headers["Authorization"], "Bearer xyz")


class TestErrors(unittest.TestCase):
    def test_bus_error_hierarchy(self):
        from bt_core.errors import (
            BusError, MessageValidationError, NoSubscriberError,
            RequestTimeoutError, MiddlewareError
        )
        self.assertTrue(issubclass(MessageValidationError, BusError))
        self.assertTrue(issubclass(NoSubscriberError, BusError))
        self.assertTrue(issubclass(RequestTimeoutError, BusError))
        self.assertTrue(issubclass(MiddlewareError, BusError))


if __name__ == '__main__':
    unittest.main()

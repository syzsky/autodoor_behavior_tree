import os
import sys
import time
import threading
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestMessageBus(unittest.TestCase):
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

    def test_publish_subscribe(self):
        received = []
        self.bus.subscribe("bt.1.event.test", lambda m: received.append(m))
        self.bus.publish("bt.1.event.test", {"hello": "world"})
        time.sleep(0.1)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data, {"hello": "world"})

    def test_wildcard_subscribe_single(self):
        received = []
        self.bus.subscribe("bt.1.event.*", lambda m: received.append(m))
        self.bus.publish("bt.1.event.started", "data")
        time.sleep(0.1)
        self.assertEqual(len(received), 1)

    def test_wildcard_subscribe_multi(self):
        received = []
        self.bus.subscribe("bt.1.event.**", lambda m: received.append(m))
        self.bus.publish("bt.1.event.node.changed", "data")
        time.sleep(0.1)
        self.assertEqual(len(received), 1)

    def test_unsubscribe(self):
        received = []
        sub_id = self.bus.subscribe("bt.1.event.test", lambda m: received.append(m))
        self.bus.unsubscribe(sub_id)
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.1)
        self.assertEqual(len(received), 0)

    def test_multiple_subscribers(self):
        received1 = []
        received2 = []
        self.bus.subscribe("bt.1.event.test", lambda m: received1.append(m))
        self.bus.subscribe("bt.1.event.test", lambda m: received2.append(m))
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.1)
        self.assertEqual(len(received1), 1)
        self.assertEqual(len(received2), 1)

    def test_subscriber_exception_isolation(self):
        received = []
        def bad_callback(m):
            raise RuntimeError("intentional error")
        self.bus.subscribe("bt.1.event.test", bad_callback)
        self.bus.subscribe("bt.1.event.test", lambda m: received.append(m))
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.2)
        self.assertEqual(len(received), 1)

    def test_request_response(self):
        def handler(msg):
            from bt_bus.message import Message
            return Message.create(
                topic=msg.headers.get("reply_to", ""),
                data={"response": "ok"},
                source="responder"
            )
        self.bus.subscribe("bt.1.command.test", handler)
        response = self.bus.request("bt.1.command.test", {"cmd": "go"}, timeout_ms=2000)
        self.assertIsNotNone(response)
        self.assertEqual(response.data, {"response": "ok"})

    def test_request_timeout(self):
        response = self.bus.request("bt.1.command.no_handler", "data", timeout_ms=500)
        self.assertIsNone(response)

    def test_request_degraded_from_blocked_thread(self):
        self.bus.set_engine_thread_id(threading.get_ident())
        response = self.bus.request("bt.1.command.test", "data", timeout_ms=500)
        self.assertIsNone(response)

    def test_singleton(self):
        from bt_bus.message_bus import MessageBus
        bus2 = MessageBus()
        self.assertIs(self.bus, bus2)


if __name__ == '__main__':
    unittest.main()

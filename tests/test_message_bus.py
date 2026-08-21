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

    def test_subscriber_exception_added_to_dead_letter_queue(self):
        """订阅者抛异常时，消息应进入死信队列，reason=SUBSCRIBER_EXCEPTION"""
        def bad_callback(m):
            raise RuntimeError("intentional error")
        self.bus.subscribe("bt.1.event.test", bad_callback)
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.2)
        dlq = self.bus.get_dead_letter_queue()
        entries = dlq.get_all()
        subscriber_exc_entries = [
            e for e in entries if e["reason"] == "SUBSCRIBER_EXCEPTION"
        ]
        self.assertEqual(len(subscriber_exc_entries), 1)
        self.assertEqual(subscriber_exc_entries[0]["message"].data, "data")

    def test_deliver_count_only_counts_successful_deliveries(self):
        """deliver 统计只记录成功投递的数量

        语义：record_publish(topic) 只递增 publish_count；
        record_deliver(topic) 在每次成功投递时递增 deliver_count。
        回调抛异常时 record_deliver 不会被调用。
        """
        def bad_callback(m):
            raise RuntimeError("intentional error")
        self.bus.subscribe("bt.1.event.test", bad_callback)
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.2)
        stats = self.bus.get_stats()
        # 发布计数应为 1
        self.assertEqual(stats.get_publish_count("bt.1.event.test"), 1)
        # 投递失败时 deliver_count 应为 0
        self.assertEqual(stats.get_deliver_count("bt.1.event.test"), 0)

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

    def test_subscribe_async_basic(self):
        """Test subscribe_async returns a queue"""
        import asyncio
        queue, sub_id = self.bus.subscribe_async("bt.1.event.test")
        self.assertIsInstance(queue, asyncio.Queue)
        self.assertTrue(sub_id)

    def test_subscribe_async_receives_message(self):
        """Test subscribe_async queue receives messages"""
        import asyncio
        queue, sub_id = self.bus.subscribe_async("bt.1.event.test")
        self.bus.publish("bt.1.event.test", {"data": "hello"})
        time.sleep(0.1)
        self.assertFalse(queue.empty())
        msg = queue.get_nowait()
        self.assertEqual(msg.data, {"data": "hello"})
        self.bus.unsubscribe_async(sub_id)

    def test_subscribe_async_pattern_filter(self):
        """Test subscribe_async filters by topic pattern"""
        import asyncio
        queue_a, sub_a = self.bus.subscribe_async("bt.1.event.topicA.*")
        queue_b, sub_b = self.bus.subscribe_async("bt.1.event.topicB.*")

        # Publish to topicA - only queue_a should receive
        self.bus.publish("bt.1.event.topicA.started", "data_a")
        time.sleep(0.1)

        self.assertFalse(queue_a.empty())
        self.assertTrue(queue_b.empty())

        msg = queue_a.get_nowait()
        self.assertEqual(msg.data, "data_a")

        self.bus.unsubscribe_async(sub_a)
        self.bus.unsubscribe_async(sub_b)

    def test_unsubscribe_async(self):
        """Test unsubscribe_async cleans up"""
        import asyncio
        queue, sub_id = self.bus.subscribe_async("bt.1.event.test")
        self.bus.unsubscribe_async(sub_id)
        self.bus.publish("bt.1.event.test", "data")
        time.sleep(0.1)
        self.assertTrue(queue.empty())

    def test_publish_and_deliver_count_separate_semantics(self):
        """publish_count 和 deliver_count 语义分离

        publish_count: 每次 publish() 递增 1（在 publish 时同步记录）
        deliver_count: 每次成功投递递增 1（在 _deliver 中异步记录）
        两者独立计数，不存在双重计数。
        """
        # 订阅 3 个订阅者
        for _ in range(3):
            self.bus.subscribe("bt.stats.test", lambda m: None)

        self.bus.publish("bt.stats.test", "data")
        time.sleep(0.3)  # 等待异步投递完成

        stats = self.bus.get_stats()
        # publish_count 应为 1
        self.assertEqual(stats.get_publish_count("bt.stats.test"), 1)
        # deliver_count 应为 3（3 个订阅者都成功投递，无双重计数）
        self.assertEqual(stats.get_deliver_count("bt.stats.test"), 3)


if __name__ == '__main__':
    unittest.main()

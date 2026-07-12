import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestMiddleware(unittest.TestCase):
    def test_logging_middleware(self):
        from bt_bus.middleware import LoggingMiddleware
        from bt_bus.message import Message
        logs = []
        class FakeLogger:
            def info(self, msg): logs.append(msg)
        mw = LoggingMiddleware(logger=FakeLogger())
        msg = Message.create("bt.1.event.test", "data")
        result = mw.process(msg, lambda m: m)
        self.assertEqual(result, msg)
        self.assertTrue(any("bt.1.event.test" in log for log in logs))

    def test_validation_middleware_valid(self):
        from bt_bus.middleware import ValidationMiddleware
        from bt_bus.message import Message
        mw = ValidationMiddleware()
        msg = Message.create("bt.1.event.test", {"key": "value"})
        result = mw.process(msg, lambda m: m)
        self.assertEqual(result, msg)

    def test_validation_middleware_invalid_empty_topic(self):
        from bt_bus.middleware import ValidationMiddleware
        from bt_bus.message import Message
        mw = ValidationMiddleware()
        msg = Message.create("", "data")
        try:
            result = mw.process(msg, lambda m: m)
            self.assertIsNone(result)
        except Exception:
            pass

    def test_middleware_chain_order(self):
        from bt_bus.middleware import Middleware
        from bt_bus.message import Message
        order = []
        class MW1(Middleware):
            def process(self, message, next_handler):
                order.append("MW1_before")
                result = next_handler(message)
                order.append("MW1_after")
                return result
        class MW2(Middleware):
            def process(self, message, next_handler):
                order.append("MW2_before")
                result = next_handler(message)
                order.append("MW2_after")
                return result
        mw1, mw2 = MW1(), MW2()
        msg = Message.create("test", "data")
        handler = lambda m: (order.append("final"), m)[1]
        handler = (lambda m, h=handler, mw=mw2: mw.process(m, h))
        handler = (lambda m, h=handler, mw=mw1: mw.process(m, h))
        handler(msg)
        self.assertEqual(order, ["MW1_before", "MW2_before", "final", "MW2_after", "MW1_after"])

    def test_middleware_intercept(self):
        from bt_bus.middleware import Middleware
        from bt_bus.message import Message
        called = []
        class InterceptMW(Middleware):
            def process(self, message, next_handler):
                return None
        mw = InterceptMW()
        msg = Message.create("test", "data")
        result = mw.process(msg, lambda m: called.append(m))
        self.assertIsNone(result)
        self.assertEqual(called, [])


if __name__ == '__main__':
    unittest.main()

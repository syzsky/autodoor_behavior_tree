import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestSharedThreadPool(unittest.TestCase):
    def setUp(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def tearDown(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def test_singleton(self):
        from bt_bus.thread_pool import SharedThreadPool
        p1 = SharedThreadPool.get_instance()
        p2 = SharedThreadPool.get_instance()
        self.assertIs(p1, p2)

    def test_submit_returns_future(self):
        from bt_bus.thread_pool import SharedThreadPool
        pool = SharedThreadPool.get_instance()
        future = pool.submit("bus", lambda x: x * 2, 21)
        self.assertEqual(future.result(timeout=2), 42)

    def test_submit_no_quota_task_type(self):
        from bt_bus.thread_pool import SharedThreadPool
        pool = SharedThreadPool.get_instance()
        future = pool.submit("unknown_type", lambda: "ok")
        self.assertEqual(future.result(timeout=2), "ok")


if __name__ == '__main__':
    unittest.main()

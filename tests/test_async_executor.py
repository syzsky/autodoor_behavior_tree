import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestAsyncExecutor(unittest.TestCase):
    def setUp(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def tearDown(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def test_submit_and_get_result(self):
        from bt_utils.async_executor import AsyncExecutor
        from bt_core.status import NodeStatus
        executor = AsyncExecutor()

        def task():
            time.sleep(0.05)
            return NodeStatus.SUCCESS

        executor.submit("node1", task)
        while not executor.is_done("node1"):
            time.sleep(0.01)
        self.assertEqual(executor.get_result("node1"), NodeStatus.SUCCESS)

    def test_cancel_all(self):
        from bt_utils.async_executor import AsyncExecutor
        executor = AsyncExecutor()

        def long_task():
            time.sleep(2)
            return None

        executor.submit("n1", long_task)
        executor.submit("n2", long_task)
        executor.cancel_all()
        self.assertTrue(executor.is_done("n1"))
        self.assertTrue(executor.is_done("n2"))

    def test_get_result_unknown_node(self):
        from bt_utils.async_executor import AsyncExecutor
        from bt_core.status import NodeStatus
        executor = AsyncExecutor()
        self.assertEqual(executor.get_result("unknown"), NodeStatus.FAILURE)

    def test_resubmit_clears_stale_result(self):
        """Regression test: re-submitting same node_id should clear stale result"""
        from bt_utils.async_executor import AsyncExecutor
        from bt_core.status import NodeStatus
        executor = AsyncExecutor()

        # First submission - completes quickly
        executor.submit("n1", lambda: NodeStatus.SUCCESS)
        while not executor.is_done("n1"):
            time.sleep(0.01)
        self.assertEqual(executor.get_result("n1"), NodeStatus.SUCCESS)

        # Second submission - should not return stale SUCCESS
        def long_task():
            time.sleep(0.1)
            return NodeStatus.FAILURE

        executor.submit("n1", long_task)
        # Immediately after submit, should NOT be done (task still running)
        # Note: there's a small race window, so we check is_done returns False at least once
        # Actually, just verify the result is eventually FAILURE (not stale SUCCESS)
        attempts = 0
        while not executor.is_done("n1"):
            time.sleep(0.01)
            attempts += 1
            if attempts > 50:  # 0.5s timeout
                break
        self.assertEqual(executor.get_result("n1"), NodeStatus.FAILURE)


if __name__ == '__main__':
    unittest.main()

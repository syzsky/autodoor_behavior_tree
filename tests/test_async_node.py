import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestAsyncNode(unittest.TestCase):
    def setUp(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def tearDown(self):
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()

    def test_node_has_is_async_flag_default_false(self):
        from bt_core.nodes import ActionNode
        from bt_core.config import NodeConfig

        class _ConcreteActionNode(ActionNode):
            def _execute_action(self, context):
                pass

        node = _ConcreteActionNode(node_id="test", config=NodeConfig())
        self.assertFalse(node._is_async)
        self.assertFalse(node._async_started)

    def test_engine_has_thread_id_attribute(self):
        from bt_core.engine import BehaviorTreeEngine
        engine = BehaviorTreeEngine()
        self.assertTrue(hasattr(engine, '_engine_thread_id'))
        self.assertIsNone(engine._engine_thread_id)

    def test_engine_has_async_executor(self):
        from bt_core.engine import BehaviorTreeEngine
        engine = BehaviorTreeEngine()
        self.assertTrue(hasattr(engine, '_async_executor'))

    def test_context_has_get_async_executor(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        self.assertTrue(hasattr(ctx, 'set_async_executor'))
        self.assertTrue(hasattr(ctx, 'get_async_executor'))

    def test_async_node_tick_submits_task_and_returns_running(self):
        from bt_core.nodes import ActionNode
        from bt_core.config import NodeConfig
        from bt_core.context import ExecutionContext
        from bt_utils.async_executor import AsyncExecutor
        from bt_core.status import NodeStatus

        class _AsyncTestNode(ActionNode):
            def __init__(self, node_id=None, config=None):
                super().__init__(node_id, config)
                self._is_async = True
                self.execute_count = 0

            def _execute_action(self, context):
                self.execute_count += 1
                time.sleep(0.1)
                return NodeStatus.SUCCESS

        node = _AsyncTestNode(node_id="async_test", config=NodeConfig())
        ctx = ExecutionContext()
        executor = AsyncExecutor()
        ctx.set_async_executor(executor)

        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.RUNNING)
        self.assertTrue(node._async_started)

        while not executor.is_done("async_test"):
            time.sleep(0.01)

        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(node.execute_count, 1)
        self.assertFalse(node._async_started)

    def test_async_node_tick_without_executor_degrades_to_sync(self):
        from bt_core.nodes import ActionNode
        from bt_core.config import NodeConfig
        from bt_core.context import ExecutionContext
        from bt_core.status import NodeStatus

        class _AsyncTestNode(ActionNode):
            def __init__(self, node_id=None, config=None):
                super().__init__(node_id, config)
                self._is_async = True

            def _execute_action(self, context):
                return NodeStatus.SUCCESS

        node = _AsyncTestNode(node_id="async_test", config=NodeConfig())
        ctx = ExecutionContext()

        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)

    def test_http_request_node_is_async(self):
        from bt_nodes.network.http_request_node import HTTPRequestNode
        from bt_core.config import NodeConfig

        node = HTTPRequestNode(node_id="http_test", config=NodeConfig())
        self.assertTrue(node._is_async)

    def test_async_node_reset_clears_async_state(self):
        from bt_core.nodes import ActionNode
        from bt_core.config import NodeConfig
        from bt_core.context import ExecutionContext
        from bt_utils.async_executor import AsyncExecutor
        from bt_core.status import NodeStatus

        class _AsyncTestNode(ActionNode):
            def __init__(self, node_id=None, config=None):
                super().__init__(node_id, config)
                self._is_async = True

            def _execute_action(self, context):
                return NodeStatus.SUCCESS

        node = _AsyncTestNode(node_id="async_test", config=NodeConfig())
        ctx = ExecutionContext()
        executor = AsyncExecutor()
        ctx.set_async_executor(executor)

        node._async_started = True
        node.status = NodeStatus.RUNNING

        node.reset()

        self.assertFalse(node._async_started)
        self.assertEqual(node.status, NodeStatus.SUCCESS)


if __name__ == '__main__':
    unittest.main()

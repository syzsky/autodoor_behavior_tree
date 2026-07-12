import os
import sys
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

        # ActionNode is abstract (_execute_action); create a concrete subclass for testing
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


if __name__ == '__main__':
    unittest.main()

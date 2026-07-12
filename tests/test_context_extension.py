import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestContextExtension(unittest.TestCase):
    def test_set_get_message_bus(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        bus = MagicMock()
        ctx.set_message_bus(bus)
        self.assertIs(ctx.get_message_bus(), bus)

    def test_set_get_service_registry(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        reg = MagicMock()
        reg.get.return_value = "service_obj"
        ctx.set_service_registry(reg)
        self.assertEqual(ctx.get_service("tree"), "service_obj")

    def test_set_get_adapter_manager(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        mgr = MagicMock()
        ctx.set_adapter_manager(mgr)
        self.assertIs(ctx.get_adapter_manager(), mgr)

    def test_publish_event_no_bus(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        # 无 bus 时不应抛异常
        ctx.publish_event("test.topic", {"data": "value"})

    def test_publish_event_with_bus(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        bus = MagicMock()
        ctx.set_message_bus(bus)
        ctx.publish_event("test.topic", {"data": "value"})
        bus.publish.assert_called_once_with("test.topic", {"data": "value"})

    def test_set_get_auth_principal(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        self.assertFalse(ctx.is_authenticated())
        principal = MagicMock()
        ctx.set_auth_principal(principal)
        self.assertIs(ctx.get_auth_principal(), principal)
        self.assertTrue(ctx.is_authenticated())

    def test_get_tree_id_from_tab_manager(self):
        from bt_core.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.set_tab_manager(MagicMock(), tab_id="tab123")
        self.assertEqual(ctx.get_tree_id(), "tab123")


if __name__ == '__main__':
    unittest.main()

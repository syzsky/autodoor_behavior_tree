# tests/test_adapter_manager.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestAdapterManager(unittest.TestCase):
    def setUp(self):
        from bt_adapters.adapter_manager import AdapterManager
        AdapterManager.reset_instance()

    def tearDown(self):
        from bt_adapters.adapter_manager import AdapterManager
        AdapterManager.reset_instance()

    def test_singleton(self):
        from bt_adapters.adapter_manager import AdapterManager
        m1 = AdapterManager()
        m2 = AdapterManager()
        self.assertIs(m1, m2)

    def test_register_and_get_adapter(self):
        from bt_adapters.adapter_manager import AdapterManager
        from bt_adapters.base import BaseAdapter, AdapterLevel, AdapterStatus
        from bt_adapters.config import AdapterConfig

        class DummyAdapter(BaseAdapter):
            @classmethod
            def get_adapter_level(cls): return AdapterLevel.LOCAL

            @classmethod
            def is_available(cls): return True

            def __init__(self, config=None):
                self._config = config or AdapterConfig()

            def start(self): pass
            def stop(self): pass
            def get_name(self): return "dummy"
            def get_status(self): return AdapterStatus(
                running=False, name="dummy", level=AdapterLevel.LOCAL
            )

        mgr = AdapterManager()
        mgr.register_adapter("dummy", DummyAdapter)
        adapter = mgr.get_adapter("dummy")
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.get_name(), "dummy")

    def test_get_unknown_adapter_returns_none(self):
        from bt_adapters.adapter_manager import AdapterManager
        mgr = AdapterManager()
        self.assertIsNone(mgr.get_adapter("unknown"))


if __name__ == '__main__':
    unittest.main()

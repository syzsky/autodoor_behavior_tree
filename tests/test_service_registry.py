# tests/test_service_registry.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestServiceRegistry(unittest.TestCase):
    def test_register_and_get(self):
        from bt_services.registry import ServiceRegistry
        from bt_services.base import BaseService

        class DummyService(BaseService):
            def get_name(self): return "dummy"
            def start(self): pass
            def stop(self): pass

        reg = ServiceRegistry()
        svc = DummyService()
        reg.register("dummy", svc)
        self.assertIs(reg.get("dummy"), svc)

    def test_get_unknown_returns_none(self):
        from bt_services.registry import ServiceRegistry
        reg = ServiceRegistry()
        self.assertIsNone(reg.get("unknown"))

    def test_list_services(self):
        from bt_services.registry import ServiceRegistry
        from bt_services.base import BaseService

        class S1(BaseService):
            def get_name(self): return "s1"
            def start(self): pass
            def stop(self): pass

        class S2(BaseService):
            def get_name(self): return "s2"
            def start(self): pass
            def stop(self): pass

        reg = ServiceRegistry()
        reg.register("s1", S1())
        reg.register("s2", S2())
        names = reg.list_services()
        self.assertIn("s1", names)
        self.assertIn("s2", names)

    def test_unregister(self):
        from bt_services.registry import ServiceRegistry
        from bt_services.base import BaseService

        class S(BaseService):
            def get_name(self): return "s"
            def start(self): pass
            def stop(self): pass

        reg = ServiceRegistry()
        svc = S()
        reg.register("s", svc)
        reg.unregister("s")
        self.assertIsNone(reg.get("s"))


if __name__ == '__main__':
    unittest.main()

# tests/test_base_server.py
"""验证 BaseServer 的 attach_bus() 和 get_status() 默认实现"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestBaseServerDefaults(unittest.TestCase):
    """验证 BaseServer 提供的 attach_bus / get_status 默认实现"""

    def _make_server(self):
        from bt_servers.base import BaseServer

        class _ConcreteServer(BaseServer):
            def start(self):
                pass

            def stop(self):
                pass

        return _ConcreteServer()

    def test_attach_bus_sets_bus_attribute(self):
        """attach_bus 默认实现应将 bus 绑定到 self._bus"""
        server = self._make_server()
        sentinel = object()
        server.attach_bus(sentinel)
        self.assertIs(server._bus, sentinel)

    def test_get_status_default_returns_not_running(self):
        """get_status 默认实现应返回 {'running': False}"""
        server = self._make_server()
        status = server.get_status()
        self.assertEqual(status, {"running": False})

    def test_rest_server_inherits_attach_bus(self):
        """RESTServer 应继承 BaseServer 的 attach_bus 默认实现"""
        from bt_servers.rest_server import RESTServer
        server = RESTServer()
        sentinel = object()
        server.attach_bus(sentinel)
        self.assertIs(server._bus, sentinel)

    def test_rest_server_inherits_get_status(self):
        """RESTServer 应继承 BaseServer 的 get_status 默认实现"""
        from bt_servers.rest_server import RESTServer
        server = RESTServer()
        status = server.get_status()
        self.assertEqual(status, {"running": False})


if __name__ == "__main__":
    unittest.main()

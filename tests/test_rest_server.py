import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestRESTServer(unittest.TestCase):
    def test_can_import(self):
        from bt_servers.rest_server import RESTServer
        self.assertTrue(hasattr(RESTServer, '__init__'))

    def test_health_endpoint(self):
        """测试 /api/v1/health 端点"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        server = RESTServer(message_bus=MagicMock(), auth_service=None)
        client = TestClient(server.app)
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_list_trees_endpoint(self):
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_tree_svc = MagicMock()
        mock_tree_svc.list_trees.return_value = [{"tree_id": "1", "name": "Tree1"}]
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tree_svc

        server = RESTServer(message_bus=MagicMock(), auth_service=None,
                            service_registry=mock_registry)
        client = TestClient(server.app)
        response = client.get("/api/v1/trees")
        self.assertEqual(response.status_code, 200)
        self.assertIn("trees", response.json())

    def test_start_tree_endpoint(self):
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_tree_svc = MagicMock()
        mock_tree_svc.start.return_value = {"status": "started", "tree_id": "1"}
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tree_svc

        server = RESTServer(message_bus=MagicMock(), auth_service=None,
                            service_registry=mock_registry)
        client = TestClient(server.app)
        response = client.post("/api/v1/trees/1/start")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "started")

    def test_noop_auth_no_token_passes(self):
        """测试 NoopAuthService 下无 Token 请求正常放行（非公开端点）"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_registry = MagicMock()
        mock_tree_svc = MagicMock()
        mock_tree_svc.list_trees.return_value = []
        mock_registry.get.return_value = mock_tree_svc

        server = RESTServer(message_bus=MagicMock(), auth_service=None,
                            service_registry=mock_registry)
        client = TestClient(server.app)
        # 访问非公开端点 /api/v1/trees（需要 auth 但 NoopAuth 放行）
        response = client.get("/api/v1/trees")
        self.assertEqual(response.status_code, 200)

    def test_endpoints_return_404_when_no_registry(self):
        """无 service_registry 时端点返回 404"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        server = RESTServer(message_bus=MagicMock(), auth_service=None)
        client = TestClient(server.app)
        # health 是公开端点，仍然 200
        self.assertEqual(client.get("/api/v1/health").status_code, 200)
        # trees 端点无 registry 时 404
        self.assertEqual(client.get("/api/v1/trees").status_code, 404)
        self.assertEqual(client.get("/api/v1/trees/1/status").status_code, 404)
        self.assertEqual(client.post("/api/v1/trees/1/start").status_code, 404)

    def test_endpoints_return_404_when_service_not_registered(self):
        """registry 中无对应服务时返回 404"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_registry = MagicMock()
        mock_registry.get.return_value = None  # 没有注册 tree service

        server = RESTServer(message_bus=MagicMock(), auth_service=None,
                            service_registry=mock_registry)
        client = TestClient(server.app)
        self.assertEqual(client.get("/api/v1/trees").status_code, 404)

    def test_auth_returns_401_when_verify_token_returns_none(self):
        """非公开端点 + verify_token 返回 None 时返回 401"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_auth = MagicMock()
        mock_auth.verify_token.return_value = None  # 认证失败

        server = RESTServer(message_bus=MagicMock(), auth_service=mock_auth)
        client = TestClient(server.app)
        # 访问非公开端点（无 registry 也会先走 auth）
        response = client.get("/api/v1/trees")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "AUTH_REQUIRED")

    def test_options_preflight_passes_auth(self):
        """CORS preflight OPTIONS 请求不被 auth 拦截"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_auth = MagicMock()
        mock_auth.verify_token.return_value = None  # 严格 auth

        server = RESTServer(message_bus=MagicMock(), auth_service=mock_auth)
        client = TestClient(server.app)
        # OPTIONS preflight 应该通过
        response = client.options("/api/v1/trees")
        # 不应该是 401
        self.assertNotEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()

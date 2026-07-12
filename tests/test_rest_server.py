import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock

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
        """测试 NoopAuthService 下无 Token 请求正常放行"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        server = RESTServer(message_bus=MagicMock(), auth_service=None)
        client = TestClient(server.app)
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()

# tests/test_http_adapter.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestHTTPAdapter(unittest.TestCase):
    def test_is_available(self):
        from bt_adapters.http_adapter import HTTPAdapter
        # requests 已安装时返回 True
        self.assertTrue(HTTPAdapter.is_available())

    def test_adapter_level_remote(self):
        from bt_adapters.http_adapter import HTTPAdapter
        from bt_adapters.base import AdapterLevel
        self.assertEqual(HTTPAdapter.get_adapter_level(), AdapterLevel.REMOTE)

    def test_call_get_returns_response(self):
        """测试 GET 请求返回 HTTPResponse

        使用 httpbin.org 或本地 mock，此处使用 mock 验证接口契约。
        """
        from bt_adapters.http_adapter import HTTPAdapter, HTTPResponse
        from unittest.mock import patch, MagicMock

        adapter = HTTPAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"hello": "world"}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"hello": "world"}
        mock_response.elapsed.total_seconds.return_value = 0.123

        with patch.object(adapter, '_session') as mock_session:
            mock_session.request.return_value = mock_response
            response = adapter.call(
                method="GET",
                url="https://httpbin.org/get",
                timeout_ms=5000
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {"hello": "world"})

    def test_call_post_with_body(self):
        from bt_adapters.http_adapter import HTTPAdapter
        from unittest.mock import patch, MagicMock

        adapter = HTTPAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = '{"id": 1}'
        mock_response.headers = {}
        mock_response.json.return_value = {"id": 1}
        mock_response.elapsed.total_seconds.return_value = 0.05

        with patch.object(adapter, '_session') as mock_session:
            mock_session.request.return_value = mock_response
            response = adapter.call(
                method="POST",
                url="https://httpbin.org/post",
                body={"key": "value"},
                headers={"Content-Type": "application/json"}
            )
            self.assertEqual(response.status_code, 201)


if __name__ == '__main__':
    unittest.main()

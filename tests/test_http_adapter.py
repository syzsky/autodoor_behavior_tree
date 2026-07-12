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

        with patch.object(adapter, '_session') as mock_session:
            mock_session.request.return_value = mock_response
            response = adapter.call(
                method="POST",
                url="https://httpbin.org/post",
                body={"key": "value"},
                headers={"Content-Type": "application/json"}
            )
            self.assertEqual(response.status_code, 201)

    def test_retry_success_after_failure(self):
        """验证重试机制：前几次失败，最后一次成功"""
        from bt_adapters.http_adapter import HTTPAdapter
        from unittest.mock import patch, MagicMock
        import requests as req

        adapter = HTTPAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{}'
        mock_response.headers = {}

        mock_session = MagicMock()
        mock_session.request.side_effect = [
            req.RequestException("fail1"),
            req.RequestException("fail2"),
            mock_response,
        ]

        with patch.object(adapter, '_session', mock_session):
            response = adapter.call(
                method="GET",
                url="https://example.com",
                retry_count=2,
                retry_interval_ms=10,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_session.request.call_count, 3)

    def test_retry_exhausted_raises_exception(self):
        """验证重试机制：所有重试均失败时抛出异常"""
        from bt_adapters.http_adapter import HTTPAdapter
        from unittest.mock import patch, MagicMock
        import requests as req

        adapter = HTTPAdapter()

        mock_session = MagicMock()
        mock_session.request.side_effect = req.RequestException("always fail")

        with patch.object(adapter, '_session', mock_session):
            with self.assertRaises(req.RequestException):
                adapter.call(
                    method="GET",
                    url="https://example.com",
                    retry_count=2,
                    retry_interval_ms=10,
                )

        # 1 + retry_count = 3 次
        self.assertEqual(mock_session.request.call_count, 3)

    def test_stop_then_call_restarts_session(self):
        """验证 C1 修复：stop() 后 _session 被置 None，再次 call() 能重建 session"""
        from bt_adapters.http_adapter import HTTPAdapter
        from unittest.mock import patch, MagicMock
        import requests as req

        adapter = HTTPAdapter()
        adapter.start()
        original_session = adapter._session
        self.assertIsNotNone(original_session)

        adapter.stop()
        # C1 修复：stop() 应将 _session 置 None
        self.assertIsNone(adapter._session)
        self.assertFalse(adapter._running)

        # 再次 call() 应能重建 session 并完成请求
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{}'
        mock_response.headers = {}

        # patch Session.request 避免真实网络请求
        with patch.object(req.Session, 'request') as mock_request:
            mock_request.return_value = mock_response
            response = adapter.call(method="GET", url="https://example.com")

        self.assertEqual(response.status_code, 200)
        # 验证创建了新的 session（与原 session 不同）
        self.assertIsNotNone(adapter._session)
        self.assertIsNot(adapter._session, original_session)

    def test_json_parse_null_response(self):
        """验证 C2 修复：合法 JSON null 返回 None 且正确缓存"""
        from bt_adapters.http_adapter import HTTPResponse, _JSON_UNSET

        response = HTTPResponse(
            status_code=200, text='null', headers={}, elapsed_ms=0
        )
        # 初始状态：_json_cache 是 sentinel
        self.assertIs(response._json_cache, _JSON_UNSET)
        # 第一次访问：解析 'null' 得到 None
        result1 = response.json
        self.assertIsNone(result1)
        # 缓存应不再是 sentinel（已被覆盖为 None）
        self.assertIsNot(response._json_cache, _JSON_UNSET)
        # 第二次访问：直接返回缓存的 None，不重新解析
        result2 = response.json
        self.assertIsNone(result2)

    def test_json_parse_invalid_returns_none(self):
        """验证 C2/I2 修复：非法 JSON 返回 None"""
        from bt_adapters.http_adapter import HTTPResponse, _JSON_UNSET

        response = HTTPResponse(
            status_code=200, text='not-json', headers={}, elapsed_ms=0
        )
        self.assertIs(response._json_cache, _JSON_UNSET)
        result = response.json
        self.assertIsNone(result)
        # 缓存应不再是 sentinel
        self.assertIsNot(response._json_cache, _JSON_UNSET)

    def test_call_uses_config_defaults_when_args_none(self):
        """验证 I1 修复：call 默认参数为 None 时回退到 config"""
        from bt_adapters.http_adapter import HTTPAdapter
        from bt_adapters.config import AdapterConfig
        from unittest.mock import patch, MagicMock
        import requests as req

        config = AdapterConfig(
            read_timeout=20, max_retries=2, retry_backoff_ms=50
        )
        adapter = HTTPAdapter(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{}'
        mock_response.headers = {}

        # 前两次失败，第三次成功 -> 验证 max_retries=2 生效
        mock_session = MagicMock()
        mock_session.request.side_effect = [
            req.RequestException("fail1"),
            req.RequestException("fail2"),
            mock_response,
        ]

        with patch.object(adapter, '_session', mock_session):
            # 不传 timeout_ms/retry_count/retry_interval_ms，使用 config 默认
            response = adapter.call(method="GET", url="https://example.com")

        self.assertEqual(response.status_code, 200)
        # 1 + max_retries = 3 次
        self.assertEqual(mock_session.request.call_count, 3)
        # 验证 timeout 使用 config.read_timeout * 1000 / 1000 = read_timeout 秒
        for call in mock_session.request.call_args_list:
            _, kwargs = call
            self.assertEqual(kwargs['timeout'], 20.0)


if __name__ == '__main__':
    unittest.main()

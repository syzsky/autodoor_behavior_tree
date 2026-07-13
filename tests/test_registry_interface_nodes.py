# tests/test_registry_interface_nodes.py
"""验证 5 个接口节点可被 NodeRegistry 反序列化创建"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestRegistryInterfaceNodes(unittest.TestCase):
    """验证接口节点注册到 NodeRegistry 后可被 create_node 反序列化"""

    @classmethod
    def setUpClass(cls):
        from bt_core.registry import register_all_nodes
        register_all_nodes()

    def _create_and_assert(self, node_type: str, expected_cls, config: dict):
        from bt_core.registry import NodeRegistry
        node = NodeRegistry.create_node({
            "type": node_type,
            "id": f"{node_type}-1",
            "config": config,
        })
        self.assertIsNotNone(node, f"{node_type} 未注册到 NodeRegistry")
        self.assertIsInstance(node, expected_cls)

    def test_http_request_node_registered(self):
        from bt_nodes.network.http_request_node import HTTPRequestNode
        self._create_and_assert("HTTPRequestNode", HTTPRequestNode, {
            "name": "http", "url": "http://example.com", "method": "GET",
        })

    def test_api_condition_node_registered(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        self._create_and_assert("APIConditionNode", APIConditionNode, {
            "name": "api", "url": "http://example.com", "method": "GET",
        })

    def test_websocket_node_registered(self):
        from bt_nodes.network.websocket_node import WebSocketNode
        self._create_and_assert("WebSocketNode", WebSocketNode, {
            "name": "ws", "url": "ws://example.com", "action": "send",
        })

    def test_message_publish_node_registered(self):
        from bt_nodes.message.publish_node import MessagePublishNode
        self._create_and_assert("MessagePublishNode", MessagePublishNode, {
            "name": "pub", "topic": "bt.test.event", "payload": {},
        })

    def test_message_subscribe_node_registered(self):
        from bt_nodes.message.subscribe_node import MessageSubscribeNode
        self._create_and_assert("MessageSubscribeNode", MessageSubscribeNode, {
            "name": "sub", "topic": "bt.test.**", "wait_mode": "nonblocking",
        })


if __name__ == "__main__":
    unittest.main()

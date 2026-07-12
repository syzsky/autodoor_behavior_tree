import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestNodeService(unittest.TestCase):
    def setUp(self):
        from bt_services.node_service import NodeService
        self.engine = MagicMock()
        self.context = MagicMock()
        self.service = NodeService(self.engine, self.context)

    def test_get_name(self):
        self.assertEqual(self.service.get_name(), "node")

    def test_list_nodes_empty(self):
        self.engine.root_node = None
        nodes = self.service.list_nodes()
        self.assertEqual(nodes, [])

    def test_list_nodes_with_root(self):
        from bt_core.nodes import SequenceNode
        from bt_core.config import NodeConfig
        root = SequenceNode(node_id="root", config=NodeConfig())
        self.engine.root_node = root
        nodes = self.service.list_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["node_id"], "root")

    def _build_tree_with_children(self):
        """构建 root + 2 children 的测试树"""
        from bt_core.nodes import SequenceNode
        from bt_core.config import NodeConfig
        root = SequenceNode(node_id="root", config=NodeConfig())
        child1 = SequenceNode(node_id="child1", config=NodeConfig())
        child2 = SequenceNode(node_id="child2", config=NodeConfig())
        root.add_child(child1)
        root.add_child(child2)
        return root

    def test_list_nodes_with_children(self):
        self.engine.root_node = self._build_tree_with_children()
        nodes = self.service.list_nodes()
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes[0]["node_id"], "root")
        self.assertEqual(nodes[1]["node_id"], "child1")
        self.assertEqual(nodes[2]["node_id"], "child2")

    def test_get_node_status_found(self):
        self.engine.root_node = self._build_tree_with_children()
        # 查询根节点
        result = self.service.get_node_status("root")
        self.assertEqual(result["node_id"], "root")
        self.assertIn("status", result)
        # 查询子节点（验证递归 _search 逻辑）
        result = self.service.get_node_status("child1")
        self.assertEqual(result["node_id"], "child1")
        self.assertIn("status", result)
        # 验证第二个子节点
        result = self.service.get_node_status("child2")
        self.assertEqual(result["node_id"], "child2")
        self.assertIn("status", result)

    def test_get_node_status_not_found(self):
        self.engine.root_node = self._build_tree_with_children()
        result = self.service.get_node_status("nonexistent")
        self.assertEqual(result, {"error": "Node not found", "node_id": "nonexistent"})

    def test_get_node_config_found(self):
        self.engine.root_node = self._build_tree_with_children()
        # 查询根节点
        result = self.service.get_node_config("root")
        self.assertEqual(result["node_id"], "root")
        self.assertEqual(result["node_type"], "SequenceNode")
        self.assertIn("config", result)
        # 查询子节点
        result = self.service.get_node_config("child1")
        self.assertEqual(result["node_id"], "child1")
        self.assertEqual(result["node_type"], "SequenceNode")
        self.assertIn("config", result)

    def test_get_node_config_not_found(self):
        self.engine.root_node = self._build_tree_with_children()
        result = self.service.get_node_config("nonexistent")
        self.assertEqual(result, {"error": "Node not found", "node_id": "nonexistent"})


if __name__ == '__main__':
    unittest.main()

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


if __name__ == '__main__':
    unittest.main()

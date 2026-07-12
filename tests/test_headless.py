import os
import sys
import json
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestHeadlessRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        )
        # 注意：序列化器期望扁平格式（nodes 字典 + connections 列表 + root_node ID），
        # 而非嵌套的 root.children 结构。
        tree_data = {
            "version": "2.1",
            "format_type": "behavior_tree",
            "root_node": "root",
            "nodes": {
                "root": {
                    "id": "root",
                    "type": "SequenceNode",
                    "name": "Root",
                    "config": {}
                },
                "delay1": {
                    "id": "delay1",
                    "type": "DelayNode",
                    "name": "Delay100ms",
                    "config": {"duration_ms": 100}
                }
            },
            "connections": [
                {"parent_id": "root", "child_id": "delay1"}
            ]
        }
        json.dump(tree_data, self.tmp)
        self.tmp.close()

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_headless_runner_can_be_imported(self):
        from bt_core.headless import HeadlessRunner
        self.assertTrue(hasattr(HeadlessRunner, 'run'))
        self.assertTrue(hasattr(HeadlessRunner, 'stop'))

    def test_headless_run_simple_tree(self):
        from bt_core.headless import HeadlessRunner
        runner = HeadlessRunner()
        result = runner.run(self.tmp.name)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()

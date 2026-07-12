import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTopicRouter(unittest.TestCase):
    def test_exact_match(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        sub_id = router.subscribe("bt.1.event.tree.started", lambda m: m)
        matches = router.match("bt.1.event.tree.started")
        self.assertEqual(len(matches), 1)

    def test_single_wildcard(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        router.subscribe("bt.1.event.*", lambda m: m)
        # * 匹配单层
        matches = router.match("bt.1.event.started")
        self.assertEqual(len(matches), 1)
        # 不匹配多层
        matches = router.match("bt.1.event.node.changed")
        self.assertEqual(len(matches), 0)

    def test_double_wildcard(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        router.subscribe("bt.1.event.**", lambda m: m)
        # ** 匹配多层
        matches = router.match("bt.1.event.node.changed")
        self.assertEqual(len(matches), 1)
        matches = router.match("bt.1.event.tree.started")
        self.assertEqual(len(matches), 1)

    def test_no_match(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        router.subscribe("bt.1.event.*", lambda m: m)
        matches = router.match("bt.2.event.started")
        self.assertEqual(len(matches), 0)

    def test_unsubscribe_by_id(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        sub_id = router.subscribe("bt.1.event.*", lambda m: m)
        ok = router.unsubscribe(sub_id)
        self.assertTrue(ok)
        matches = router.match("bt.1.event.started")
        self.assertEqual(len(matches), 0)

    def test_multiple_subscribers(self):
        from bt_bus.topic import TopicRouter
        router = TopicRouter()
        router.subscribe("bt.1.event.*", lambda m: m)
        router.subscribe("bt.1.event.**", lambda m: m)
        matches = router.match("bt.1.event.started")
        self.assertEqual(len(matches), 2)


if __name__ == '__main__':
    unittest.main()

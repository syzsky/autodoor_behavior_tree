import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestDeadLetterQueue(unittest.TestCase):
    def test_no_subscriber_dead_letter(self):
        from bt_bus.dead_letter import DeadLetterQueue
        from bt_bus.message import Message
        q = DeadLetterQueue(max_size=100)
        msg = Message.create("test", "data")
        q.add(msg, reason="NO_SUBSCRIBER")
        self.assertEqual(q.size(), 1)

    def test_dead_letter_max_size(self):
        from bt_bus.dead_letter import DeadLetterQueue
        from bt_bus.message import Message
        q = DeadLetterQueue(max_size=3)
        for i in range(5):
            msg = Message.create(f"topic.{i}", i)
            q.add(msg, reason="NO_SUBSCRIBER")
        self.assertEqual(q.size(), 3)

    def test_dead_letter_reason(self):
        from bt_bus.dead_letter import DeadLetterQueue
        from bt_bus.message import Message
        q = DeadLetterQueue(max_size=100)
        msg = Message.create("test", "data")
        q.add(msg, reason="EXCEPTION")
        entries = q.get_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["reason"], "EXCEPTION")


if __name__ == '__main__':
    unittest.main()

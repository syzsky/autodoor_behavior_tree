# tests/test_sse_queue_bounds.py
"""SSE 队列上限测试"""


def test_subscribe_async_with_maxsize(message_bus):
    """测试 subscribe_async 支持 maxsize 参数"""
    queue, sub_id = message_bus.subscribe_async("test.topic", maxsize=5)
    assert queue.maxsize == 5
    message_bus.unsubscribe_async(sub_id)


def test_queue_drops_old_when_full(message_bus):
    """测试队列满时丢弃旧消息"""
    queue, sub_id = message_bus.subscribe_async("test.topic", maxsize=3)

    # 不运行 event loop，消息走 put_nowait 路径
    for i in range(5):
        message_bus.publish("test.topic", {"index": i})

    # 队列应仅保留最后 3 条
    assert queue.qsize() <= 3
    message_bus.unsubscribe_async(sub_id)

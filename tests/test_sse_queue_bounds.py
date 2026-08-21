# tests/test_sse_queue_bounds.py
"""SSE 队列上限测试"""
import asyncio
import time


def test_subscribe_async_with_maxsize(message_bus):
    """测试 subscribe_async 支持 maxsize 参数"""
    queue, sub_id = message_bus.subscribe_async("test.topic", maxsize=5)
    assert queue.maxsize == 5
    message_bus.unsubscribe_async(sub_id)


def test_queue_drops_old_when_full(message_bus):
    """测试队列满时丢弃旧消息，保留最新消息"""
    queue, sub_id = message_bus.subscribe_async("test.topic", maxsize=3)

    # 不运行 event loop，消息走 put_nowait 路径
    # 每条 publish 后短暂等待 _deliver 完成，确保投递顺序与发布顺序一致
    for i in range(5):
        message_bus.publish("test.topic", {"index": i})
        time.sleep(0.02)

    # 等待所有投递完成
    time.sleep(0.1)

    # 队列应仅保留最后 3 条（index 2, 3, 4）
    assert queue.qsize() == 3

    # 验证保留的是最新的消息
    kept_indices = []
    while not queue.empty():
        try:
            msg = queue.get_nowait()
            kept_indices.append(msg.data["index"])
        except asyncio.QueueEmpty:
            break

    assert kept_indices == [2, 3, 4], f"Expected [2, 3, 4], got {kept_indices}"

    message_bus.unsubscribe_async(sub_id)

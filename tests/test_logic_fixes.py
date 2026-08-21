# tests/test_logic_fixes.py
"""逻辑修复测试 (B3, B4, B6)"""
import time
from unittest.mock import MagicMock


def test_deliver_depth_limit(message_bus):
    """测试 _deliver 递归深度限制（通过公共 publish API 触发）(B3)"""
    from bt_bus.message import Message

    call_count = [0]

    def recursive_callback(msg):
        call_count[0] += 1
        # 回复会触发递归发布
        return Message.create(
            msg.headers.get("reply_to", "test.deep"),
            "reply",
            headers={"reply_to": msg.headers.get("reply_to", "test.deep")}
        )

    message_bus.subscribe("test.deep", recursive_callback)

    # 设置 reply_to 触发递归
    message_bus.publish("test.deep", "start", headers={"reply_to": "test.deep"})

    # 等待异步投递完成（递归在线程池中执行）
    time.sleep(0.5)

    # 递归应被限制（MAX_DELIVER_DEPTH=5），不应无限循环
    # depth 0~4 触发回调（5 次），depth 5 被拦截
    assert call_count[0] <= 10, f"递归深度过大: {call_count[0]}"
    assert call_count[0] >= 1, "回调未被调用"


def test_deliver_depth_dead_letter(message_bus):
    """测试超深递归消息进入死信队列 (B3)"""
    from bt_bus.message import Message

    def recursive_callback(msg):
        return Message.create(
            msg.headers.get("reply_to", "test.deep2"),
            "reply",
            headers={"reply_to": msg.headers.get("reply_to", "test.deep2")}
        )

    message_bus.subscribe("test.deep2", recursive_callback)
    message_bus.publish("test.deep2", "start", headers={"reply_to": "test.deep2"})

    time.sleep(0.5)

    dlq = message_bus.get_dead_letter_queue()
    entries = dlq.get_all()
    depth_exceeded = [e for e in entries if e["reason"] == "MAX_DEPTH_EXCEEDED"]
    assert len(depth_exceeded) >= 1, "超深递归消息未进入死信队列"


def test_validation_middleware_records_dead_letter():
    """测试 ValidationMiddleware 验证失败时记录死信 (B4)"""
    from bt_bus.middleware import ValidationMiddleware
    from bt_bus.message import Message
    from bt_bus.dead_letter import DeadLetterQueue

    # 使用真实 DeadLetterQueue 而非 mock，验证集成
    dlq = DeadLetterQueue()
    middleware = ValidationMiddleware(dead_letter_queue=dlq)

    # 空 topic 消息
    msg = Message.create("", {"data": "test"})
    result = middleware.process(msg, lambda m: m)

    # 验证：返回 None（消息被拦截）
    assert result is None
    # 验证：死信队列记录了该消息
    entries = dlq.get_all()
    assert len(entries) == 1
    assert entries[0]["reason"] == "VALIDATION_FAILED_EMPTY_TOPIC"


def test_validation_middleware_null_data_records_dead_letter():
    """测试 ValidationMiddleware 对 None data 记录死信 (B4)"""
    from bt_bus.middleware import ValidationMiddleware
    from bt_bus.message import Message
    from bt_bus.dead_letter import DeadLetterQueue

    dlq = DeadLetterQueue()
    middleware = ValidationMiddleware(dead_letter_queue=dlq)

    msg = Message.create("valid.topic", None)
    result = middleware.process(msg, lambda m: m)

    assert result is None
    entries = dlq.get_all()
    assert len(entries) == 1
    assert entries[0]["reason"] == "VALIDATION_FAILED_NULL_DATA"


def test_validation_middleware_passes_valid_message():
    """测试 ValidationMiddleware 放行有效消息 (B4)"""
    from bt_bus.middleware import ValidationMiddleware
    from bt_bus.message import Message

    middleware = ValidationMiddleware(dead_letter_queue=None)
    msg = Message.create("valid.topic", {"data": "test"})

    called = [False]
    def next_handler(m):
        called[0] = True
        return m

    result = middleware.process(msg, next_handler)

    assert result is msg
    assert called[0] is True


def test_validation_middleware_in_default_chain(message_bus):
    """测试 MessageBus 默认中间件链包含 ValidationMiddleware (B4)"""
    # 默认链应包含 ValidationMiddleware
    from bt_bus.middleware import ValidationMiddleware
    has_validation = any(
        isinstance(mw, ValidationMiddleware) for mw in message_bus._middleware_chain
    )
    assert has_validation, "ValidationMiddleware 未在默认中间件链中"


def test_adapter_manager_unregister():
    """测试 AdapterManager unregister_adapter 方法 (B6)"""
    from bt_adapters.adapter_manager import AdapterManager
    from bt_adapters.base import BaseAdapter, AdapterLevel, AdapterStatus

    AdapterManager.reset_instance()
    manager = AdapterManager()

    class TestAdapter(BaseAdapter):
        @classmethod
        def get_adapter_level(cls): return AdapterLevel.LOCAL
        @classmethod
        def is_available(cls): return True
        def start(self): pass
        def stop(self): pass
        def get_name(self): return "test"
        def get_status(self): return AdapterStatus(running=False, name="test", level=AdapterLevel.LOCAL)

    manager.register_adapter("test", TestAdapter)
    adapter = manager.get_adapter("test")
    assert adapter is not None

    # 注销
    manager.unregister_adapter("test")
    adapter = manager.get_adapter("test")
    assert adapter is None

    AdapterManager.reset_instance()

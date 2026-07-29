# tests/conftest.py
"""pytest 共享 fixtures"""
import asyncio
import os
import sys
import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def message_bus():
    """提供隔离的 MessageBus 实例，自动清理单例和 event loop"""
    from bt_bus.message_bus import MessageBus

    MessageBus.reset_instance()
    bus = MessageBus()
    bus.start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bus.set_event_loop(loop)

    yield bus

    # 清理
    try:
        bus.stop()
    except Exception:
        pass
    try:
        loop.close()
    except Exception:
        pass
    asyncio.set_event_loop(None)
    MessageBus.reset_instance()

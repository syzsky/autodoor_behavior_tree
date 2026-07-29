# tests/test_thread_safety_fixes.py
"""线程安全修复测试 (A3, A4, P1)"""
import threading
from unittest.mock import MagicMock


def test_message_bus_init_thread_safe():
    """测试 MessageBus 并发初始化不产生半初始化实例 (A3)"""
    from bt_bus.message_bus import MessageBus
    MessageBus.reset_instance()

    instances = []
    errors = []
    barrier = threading.Barrier(20)

    def create_instance():
        try:
            barrier.wait(timeout=5)
            bus = MessageBus()
            # 立即访问多个属性，检测半初始化
            _ = bus._router
            _ = bus._async_queues
            _ = bus._dead_letter_queue
            _ = bus._bus_lock
            _ = bus._stats
            _ = bus._middleware_chain
            _ = bus._shared_pool
            instances.append(bus)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=create_instance) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 无并发错误
    assert not errors, f"并发初始化错误: {errors}"
    # 所有实例应为同一对象
    assert len(instances) == 20
    assert all(inst is instances[0] for inst in instances)
    # 实例应已完全初始化
    assert instances[0]._initialized is True

    MessageBus.reset_instance()


def test_message_bus_init_no_double_initialization():
    """测试 MessageBus 不会重复初始化（__init__ 为 no-op）(A3)"""
    from bt_bus.message_bus import MessageBus
    MessageBus.reset_instance()

    bus = MessageBus()
    router_id = id(bus._router)
    dlq_id = id(bus._dead_letter_queue)
    stats_id = id(bus._stats)

    # 再次调用构造函数不应重新初始化
    bus2 = MessageBus()
    assert bus2 is bus
    assert id(bus2._router) == router_id, "router 被重新初始化"
    assert id(bus2._dead_letter_queue) == dlq_id, "dead_letter_queue 被重新初始化"
    assert id(bus2._stats) == stats_id, "stats 被重新初始化"

    MessageBus.reset_instance()


def test_service_registry_no_lock_during_start_stop():
    """测试 ServiceRegistry start_all/stop_all 不持锁调用服务方法 (P1)"""
    from bt_services.registry import ServiceRegistry

    registry = ServiceRegistry()
    mock_svc = MagicMock()
    mock_svc.get_name.return_value = "test"
    registry.register("test", mock_svc)

    # 记录 start 调用时的锁状态
    lock_held_during_start = []
    lock_held_during_stop = []

    def check_lock_start():
        lock_held_during_start.append(registry._lock._is_owned())

    def check_lock_stop():
        lock_held_during_stop.append(registry._lock._is_owned())

    mock_svc.start.side_effect = check_lock_start
    mock_svc.stop.side_effect = check_lock_stop

    registry.start_all()
    registry.stop_all()

    # start/stop 不应在持锁状态下调用
    assert mock_svc.start.called, "service.start 未被调用"
    assert mock_svc.stop.called, "service.stop 未被调用"
    assert not any(lock_held_during_start), "Service start called while holding registry lock"
    assert not any(lock_held_during_stop), "Service stop called while holding registry lock"


def test_http_adapter_call_thread_safe():
    """测试 HTTPAdapter 并发 call 不产生竞态 (A4)"""
    from bt_adapters.http_adapter import HTTPAdapter
    from bt_adapters.config import AdapterConfig

    adapter = HTTPAdapter(AdapterConfig())
    adapter.start()

    errors = []
    barrier = threading.Barrier(5)

    def make_call():
        try:
            barrier.wait(timeout=5)
            # mock session.request 避免真实网络请求
            adapter._session.request = MagicMock(return_value=MagicMock(
                status_code=200, text="{}", headers={}
            ))
            adapter.call("GET", "http://example.com/test")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=make_call) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"HTTPAdapter 并发错误: {errors}"
    adapter.stop()

"""适配器管理器（单例）— 参考 InputControllerManager 设计

参考开发方案 §3.2 和开发计划 §2.1.1。
"""
import threading
from typing import Dict, Optional, Type

from .base import BaseAdapter


class AdapterManager:
    """适配器管理器（单例）

    核心职责:
    1. 管理所有适配器实例（单例池）
    2. 按配置启停适配器
    3. 适配器可用性检测
    """

    _instance: Optional["AdapterManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._adapters: Dict[str, BaseAdapter] = {}
        self._adapter_classes: Dict[str, Type[BaseAdapter]] = {}
        self._message_bus = None
        # 注意：实例级锁命名为 _adapters_lock，避免与类级 _lock（单例双重检查锁定）同名遮蔽
        # 与 MessageBus 命名规范一致（_lock 类级 + _bus_lock 实例级）
        self._adapters_lock = threading.RLock()
        # 注意：_initialized 必须放在所有属性初始化之后，避免半初始化问题
        # （参考 Tasks 11+12 的代码质量教训）
        self._initialized = True

    def register_adapter(self, name: str,
                         adapter_class: Type[BaseAdapter]) -> None:
        """注册适配器类型"""
        with self._adapters_lock:
            self._adapter_classes[name] = adapter_class

    def get_adapter(self, name: str) -> Optional[BaseAdapter]:
        """获取适配器实例"""
        with self._adapters_lock:
            if name in self._adapters:
                return self._adapters[name]
            cls = self._adapter_classes.get(name)
            if cls is None:
                return None
            if not cls.is_available():
                return None
            adapter = cls()
            self._adapters[name] = adapter
            return adapter

    def start_all(self, message_bus) -> None:
        """启动所有已启用的适配器"""
        with self._adapters_lock:
            self._message_bus = message_bus
            for name, adapter in self._adapters.items():
                try:
                    adapter.start()
                except Exception as e:
                    # 容错：单个适配器启动失败不应中断后续启动（与 stop_all 风格一致）
                    print(f"[AdapterManager] start failed for {name}: {e}")

    def stop_all(self) -> None:
        """停止所有适配器"""
        with self._adapters_lock:
            for adapter in self._adapters.values():
                try:
                    adapter.stop()
                except Exception:
                    pass

    def list_adapters(self) -> Dict[str, dict]:
        """列出所有适配器状态"""
        with self._adapters_lock:
            return {
                name: {"status": adapter.get_status()}
                for name, adapter in self._adapters.items()
            }

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例 — 仅供测试使用

        调用 stop_all() 停止所有适配器后清空单例状态，
        与 InputControllerManager.reset_instance 设计一致。
        """
        if cls._instance is not None:
            cls._instance.stop_all()
        cls._instance = None
        cls._initialized = False

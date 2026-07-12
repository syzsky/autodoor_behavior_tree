"""服务注册中心"""
import threading
from typing import Dict, List, Optional

from .base import BaseService


class ServiceRegistry:
    """服务注册中心

    管理所有业务服务的注册、查询、生命周期。
    """

    def __init__(self):
        self._services: Dict[str, BaseService] = {}
        self._lock = threading.RLock()

    def register(self, name: str, service: BaseService) -> None:
        """注册服务"""
        with self._lock:
            self._services[name] = service

    def unregister(self, name: str) -> None:
        """注销服务"""
        with self._lock:
            self._services.pop(name, None)

    def get(self, name: str) -> Optional[BaseService]:
        """获取服务"""
        with self._lock:
            return self._services.get(name)

    def list_services(self) -> List[str]:
        """列出所有已注册服务名"""
        with self._lock:
            return list(self._services.keys())

    def start_all(self) -> None:
        """启动所有服务"""
        with self._lock:
            for name, svc in self._services.items():
                try:
                    svc.start()
                except Exception as e:
                    print(f"[ServiceRegistry] start failed for {name}: {e}")

    def stop_all(self) -> None:
        """停止所有服务"""
        with self._lock:
            for name, svc in self._services.items():
                try:
                    svc.stop()
                except Exception as e:
                    print(f"[ServiceRegistry] stop failed for {name}: {e}")

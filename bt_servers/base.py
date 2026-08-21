"""服务端基类"""
from abc import ABC, abstractmethod


class BaseServer(ABC):
    """服务端抽象基类"""

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    def attach_bus(self, bus) -> None:
        """绑定消息总线（默认实现，子类可覆盖）"""
        self._bus = bus

    def get_status(self) -> dict:
        """获取服务端状态（默认实现，子类可覆盖）"""
        return {"running": False}

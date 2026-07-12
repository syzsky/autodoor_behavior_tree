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

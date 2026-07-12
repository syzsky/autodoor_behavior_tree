"""服务基类"""
from abc import ABC, abstractmethod


class BaseService(ABC):
    """服务抽象基类

    所有业务服务（TreeService、DataService 等）继承此类。
    """

    @abstractmethod
    def get_name(self) -> str:
        """返回服务名称"""
        ...

    @abstractmethod
    def start(self) -> None:
        """启动服务"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止服务"""
        ...

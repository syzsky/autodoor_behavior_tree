"""适配器基类 — 参考 BaseKeyboardController 设计

参考开发方案 §3.2。
"""
import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


class AdapterLevel(enum.Enum):
    """适配器级别 — 参考 InputLevel"""
    LOCAL = "local"
    REMOTE = "remote"
    HYBRID = "hybrid"


@dataclass
class AdapterStatus:
    """适配器状态"""
    running: bool = False
    name: str = ""
    level: AdapterLevel = AdapterLevel.LOCAL
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """适配器基类 — 参考 BaseKeyboardController

    子类必须实现:
    - get_adapter_level(): 返回适配器级别
    - is_available(): 检测依赖是否可用
    - start() / stop(): 生命周期管理
    - get_name(): 适配器名称
    - get_status(): 状态查询
    """

    @classmethod
    @abstractmethod
    def get_adapter_level(cls) -> AdapterLevel:
        """返回适配器级别"""
        ...

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """检测依赖是否可用 — 参考 is_driver_available()"""
        ...

    @abstractmethod
    def start(self) -> None:
        """启动适配器"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止适配器"""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """返回适配器名称"""
        ...

    @abstractmethod
    def get_status(self) -> AdapterStatus:
        """返回适配器状态"""
        ...

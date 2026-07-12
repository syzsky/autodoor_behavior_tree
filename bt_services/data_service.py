"""数据服务 — 封装 Blackboard

参考开发方案 §3.3 和开发计划 §3.1.3。
"""
from typing import Any, List

from .base import BaseService


class DataService(BaseService):
    """数据服务

    封装 Blackboard 的读写操作，通过消息总线暴露。
    """

    def __init__(self, context):
        self._context = context
        self._blackboard = context.blackboard

    def get_name(self) -> str:
        return "data"

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get(self, key: str, default=None) -> Any:
        """读取黑板变量"""
        return self._blackboard.get(key, default)

    def set(self, key: str, value: Any) -> dict:
        """写入黑板变量"""
        self._blackboard.set(key, value)
        return {"key": key, "value": value}

    def delete(self, key: str) -> dict:
        """删除黑板变量"""
        self._blackboard.delete(key)
        return {"key": key, "deleted": True}

    def list_keys(self) -> List[str]:
        """列出所有黑板变量名"""
        return self._blackboard.get_all_keys()

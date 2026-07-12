"""节点服务 — 节点状态/配置查询

参考开发计划 §3.1.5。

注意：返回字典使用服务层契约键名（node_id/node_type/name/status），
与 bt_core.nodes.Node.to_dict() 的序列化键名（id/type/name/config/children）不同。
"""
from typing import List

from .base import BaseService


class NodeService(BaseService):
    """节点服务"""

    def __init__(self, engine, context):
        self._engine = engine
        self._context = context

    def get_name(self) -> str:
        return "node"

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def list_nodes(self) -> List[dict]:
        """列出行为树所有节点"""
        if not self._engine.root_node:
            return []
        result = []
        self._collect_nodes(self._engine.root_node, result)
        return result

    def _collect_nodes(self, node, result: list) -> None:
        result.append({
            "node_id": node.node_id,
            "node_type": node.NODE_TYPE,
            "name": node.name,
            "status": node.status.name,
        })
        for child in node.children:
            self._collect_nodes(child, result)

    def get_node_status(self, node_id: str) -> dict:
        """查询节点状态"""
        node = self._find_node(node_id)
        if not node:
            return {"error": "Node not found", "node_id": node_id}
        return {
            "node_id": node.node_id,
            "status": node.status.name,
        }

    def get_node_config(self, node_id: str) -> dict:
        """查询节点配置"""
        node = self._find_node(node_id)
        if not node:
            return {"error": "Node not found", "node_id": node_id}
        return {
            "node_id": node.node_id,
            "node_type": node.NODE_TYPE,
            "config": node.config.to_dict(),
        }

    def _find_node(self, node_id: str):
        """递归查找节点"""
        if not self._engine.root_node:
            return None
        return self._search(self._engine.root_node, node_id)

    def _search(self, node, node_id: str):
        if node.node_id == node_id:
            return node
        for child in node.children:
            found = self._search(child, node_id)
            if found:
                return found
        return None

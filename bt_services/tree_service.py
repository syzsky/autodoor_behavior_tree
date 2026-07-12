"""行为树服务 — 封装 engine + tab_manager

复用现有 StartTreeNode/StopTreeNode 的 tab_manager 跨树控制能力。
参考开发方案 §3.3 和开发计划 §3.1.2。
"""
from .base import BaseService


class TreeService(BaseService):
    """行为树服务

    封装 BehaviorTreeEngine 和 GuiTabManager，
    通过消息总线暴露行为树控制能力。
    """

    def __init__(self, engine, context):
        self._engine = engine
        self._context = context

    def get_name(self) -> str:
        return "tree"

    def start(self, tree_id: str = None) -> dict:
        """启动行为树

        Args:
            tree_id: 指定 Tab 的 tree_id，None 表示当前树

        Returns:
            {"status": "started", "tree_id": ...}
        """
        tab_manager = self._context.get_tab_manager()
        if tree_id and tab_manager:
            tab_manager.start_tab(tree_id)
        else:
            self._engine.start(self._context)
        return {"status": "started", "tree_id": tree_id}

    def stop(self, tree_id: str = None) -> dict:
        """停止行为树"""
        tab_manager = self._context.get_tab_manager()
        if tree_id and tab_manager:
            tab_manager.stop_tab(tree_id)
        else:
            self._engine.stop()
        return {"status": "stopped", "tree_id": tree_id}

    def pause(self, tree_id: str = None) -> dict:
        """暂停行为树"""
        self._engine.pause()
        return {"status": "paused", "tree_id": tree_id}

    def resume(self, tree_id: str = None) -> dict:
        """恢复行为树"""
        self._engine.resume()
        return {"status": "resumed", "tree_id": tree_id}

    def get_status(self) -> dict:
        """获取行为树状态"""
        status = self._engine.get_status()
        return {
            "running": status.get("running", False),
            "paused": status.get("paused", False),
        }

    def list_trees(self) -> list:
        """列出所有行为树 Tab"""
        tab_manager = self._context.get_tab_manager()
        if not tab_manager:
            return []
        if hasattr(tab_manager, 'get_all_status'):
            return tab_manager.get_all_status()
        return []

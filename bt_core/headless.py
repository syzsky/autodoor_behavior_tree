"""Headless 运行模式 — 无 GUI 运行行为树

为服务端模式奠定基础，支持命令行运行行为树文件。
"""
import os
import time
import threading
from typing import Optional


class HeadlessRunner:
    """无 GUI 模式运行行为树

    完整启动流程（阶段 4 实现后启用）:
        1. 加载行为树 → 创建 Context
        2. 启动消息总线 MessageBus（阶段 1）
        3. 启动适配器层 AdapterManager（阶段 2）
        4. 启动服务层 ServiceRegistry（阶段 3）
        5. 启动 REST API 服务端（阶段 4）
        6. 启动引擎
    """

    def __init__(self):
        self._engine = None
        self._context = None
        self._tree_file: Optional[str] = None
        self._stop_requested = threading.Event()

    def run(self, tree_file: str, project_root: str = None) -> bool:
        """加载并运行行为树

        Args:
            tree_file: 行为树 JSON 文件路径
            project_root: 项目根目录，默认为行为树所在目录

        Returns:
            True=正常完成, False=出错
        """
        import json
        from bt_core.serializer import Serializer
        from bt_core.context import ExecutionContext
        from bt_core.engine import BehaviorTreeEngine
        from bt_core.registry import register_all_nodes

        # 注册全部节点类型（core nodes 仅注册 Sequence/Selector 等，
        # DelayNode 等动作/条件节点需要 register_all_nodes 注册）
        register_all_nodes()

        self._tree_file = tree_file
        self._stop_requested.clear()

        with open(tree_file, 'r', encoding='utf-8') as f:
            tree_data = json.load(f)

        # Serializer.deserialize 返回 (root_node, canvas_state, editor_state) 元组
        result = Serializer.deserialize(tree_data)
        if isinstance(result, tuple):
            root = result[0]
        else:
            root = result

        self._context = ExecutionContext(
            project_root=project_root or os.path.dirname(os.path.abspath(tree_file))
        )
        if hasattr(self._context, 'set_headless'):
            self._context.set_headless(True)

        self._engine = BehaviorTreeEngine(root)
        self._engine.start(self._context)

        try:
            while self._engine._running:
                if self._stop_requested.is_set():
                    self._engine.stop()
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            self._engine.stop()

        return True

    def stop(self) -> None:
        """停止运行"""
        self._stop_requested.set()
        if self._engine:
            self._engine.stop()

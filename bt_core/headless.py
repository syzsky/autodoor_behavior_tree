"""Headless 运行模式 — 无 GUI 运行行为树

为服务端模式奠定基础，支持命令行运行行为树文件。
"""
import os
import time
import threading
import asyncio
from typing import Optional

from bt_adapters.adapter_manager import AdapterManager


class HeadlessRunner:
    """无 GUI 模式运行行为树

    完整启动流程:
        1. 加载行为树 → 创建 Context
        2. 启动消息总线 MessageBus
        3. 启动适配器层 AdapterManager
        4. 启动服务层 ServiceRegistry
        5. 启动 REST API 服务端
        6. 启动引擎
    """

    def __init__(self):
        self._engine = None
        self._context = None
        self._tree_file: Optional[str] = None
        self._stop_requested = threading.Event()
        self._bus = None
        self._adapter_manager = None
        self._service_registry = None
        self._rest_server = None
        self._websocket_server = None
        self._server_thread = None

    def run(self, tree_file: str, project_root: str = None) -> None:
        """加载并运行行为树

        Args:
            tree_file: 行为树 JSON 文件路径
            project_root: 项目根目录，默认为行为树所在目录

        Raises:
            Exception: 加载或运行失败时抛出异常（不返回 False）
        """
        import json
        from bt_core.serializer import Serializer
        from bt_core.context import ExecutionContext
        from bt_core.engine import BehaviorTreeEngine
        from bt_core.registry import register_all_nodes
        from config.settings_manager import get_settings_manager

        register_all_nodes()

        self._tree_file = tree_file
        self._stop_requested.clear()

        with open(tree_file, 'r', encoding='utf-8') as f:
            tree_data = json.load(f)

        result = Serializer.deserialize(tree_data)
        if isinstance(result, tuple):
            root = result[0]
        else:
            root = result

        settings = get_settings_manager()
        tree_id = os.path.splitext(os.path.basename(tree_file))[0]

        self._context = ExecutionContext(
            project_root=project_root or os.path.dirname(os.path.abspath(tree_file))
        )
        self._context.set_tab_manager(None, tree_id)
        if hasattr(self._context, 'set_headless'):
            self._context.set_headless(True)

        self._engine = BehaviorTreeEngine(root)

        self._start_service_layer(settings)

        self._engine.start(self._context)

        try:
            while self._engine.get_status()['running'] and self._engine._thread.is_alive():
                if self._stop_requested.is_set():
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            self._engine.stop()
        finally:
            self._stop_service_layer()

    def _start_service_layer(self, settings) -> None:
        """启动服务层（消息总线、适配器、服务注册、REST/WebSocket 服务器）"""
        if not settings.get("message_bus.enabled", False):
            return

        from bt_bus.message_bus import MessageBus
        from bt_adapters.adapter_manager import AdapterManager
        from bt_services.registry import ServiceRegistry
        from bt_services.auth_service import NoopAuthService

        self._bus = MessageBus()
        self._context.set_message_bus(self._bus)

        self._adapter_manager = AdapterManager()
        self._adapter_manager.start_all(self._bus)
        self._context.set_adapter_manager(self._adapter_manager)

        from bt_services.data_service import DataService
        from bt_services.tree_service import TreeService
        from bt_services.node_service import NodeService
        from bt_utils.async_executor import AsyncExecutor

        auth_service = NoopAuthService()

        self._service_registry = ServiceRegistry()
        self._service_registry.register("data", DataService(self._context))
        self._service_registry.register("tree", TreeService(self._context, self._engine))
        self._service_registry.register("node", NodeService(self._engine, self._context))
        self._service_registry.register("auth", auth_service)
        self._service_registry.register("async", AsyncExecutor())
        self._service_registry.start_all()

        if settings.get("rest_server.enabled", False):
            from bt_servers.rest_server import RESTServer
            rest_config = settings.get("rest_server", {})
            self._rest_server = RESTServer(
                message_bus=self._bus,
                auth_service=auth_service,
                service_registry=self._service_registry
            )
            self._server_thread = threading.Thread(
                target=self._start_rest_server,
                args=(rest_config.get("host", "127.0.0.1"), rest_config.get("port", 8080)),
                daemon=True
            )
            self._server_thread.start()

        if settings.get("websocket_server.enabled", False):
            from bt_servers.websocket_server import WebSocketServer
            ws_config = settings.get("websocket_server", {})
            self._websocket_server = WebSocketServer(
                host=ws_config.get("host", "127.0.0.1"),
                port=ws_config.get("port", 8765),
                auth_service=auth_service
            )
            self._websocket_server.attach_bus(self._bus)

    def _start_rest_server(self, host: str, port: int) -> None:
        """启动 REST 服务器（在独立线程中运行）"""
        import uvicorn
        uvicorn.run(
            self._rest_server.app,
            host=host,
            port=port,
            log_level="warning",
            loop="asyncio"
        )

    def _stop_service_layer(self) -> None:
        """停止服务层"""
        if self._server_thread and self._server_thread.is_alive():
            pass
        if self._websocket_server:
            try:
                asyncio.run(self._websocket_server.stop())
            except Exception:
                pass
        if self._adapter_manager:
            self._adapter_manager.stop_all()
            AdapterManager.reset_instance()
        if self._bus:
            self._bus.reset_instance()

    def stop(self) -> None:
        """停止运行"""
        self._stop_requested.set()
        if self._engine:
            self._engine.stop()
        self._stop_service_layer()

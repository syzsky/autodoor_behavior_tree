"""REST API 服务端 — 基于 FastAPI

参考开发方案 §3.6.6 和开发计划 §4.1.1。
使用 async/sync 桥接方案（asyncio.to_thread）。
"""
import asyncio
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .base import BaseServer
from .config import ServerConfig


class BlackboardValue(BaseModel):
    """set_blackboard_key 请求体模型"""
    value: object = None


class RESTServer(BaseServer):
    """REST API 服务端

    使用 FastAPI 提供 REST API。
    异步 handler 中通过 asyncio.to_thread() 桥接同步引擎调用。
    """

    def __init__(self, message_bus=None, auth_service=None,
                 service_registry=None, config: Optional[ServerConfig] = None):
        self._bus = message_bus
        self._config = config or ServerConfig()
        self._registry = service_registry

        # 默认使用 NoopAuthService
        if auth_service is None:
            from bt_services.auth_service import NoopAuthService
            auth_service = NoopAuthService()
        self._auth = auth_service

        self.app = FastAPI(title="AutoDoor BT API", version="1.0")
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        """配置中间件"""
        from bt_services.auth_service import PUBLIC_ENDPOINTS

        # CORS 中间件（外层）
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self._config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Auth 中间件（内层）
        @self.app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            # CORS preflight 直接放行
            if request.method == "OPTIONS":
                return await call_next(request)
            # 公开端点直接放行
            if request.url.path in PUBLIC_ENDPOINTS:
                return await call_next(request)
            # 解析 Bearer token
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            else:
                token = auth_header
            principal = self._auth.verify_token(token)
            if not principal:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized", "code": "AUTH_REQUIRED"}
                )
            request.state.principal = principal
            return await call_next(request)

    def _require_service(self, name: str):
        """获取指定服务，若不存在则抛 404"""
        if not self._registry:
            raise HTTPException(404, f"{name} service not available")
        svc = self._registry.get(name)
        if not svc:
            raise HTTPException(404, f"{name} service not available")
        return svc

    def _setup_routes(self) -> None:
        """配置路由"""
        @self.app.get("/api/v1/health")
        async def health():
            return {"status": "ok"}

        @self.app.get("/api/v1/trees")
        async def list_trees():
            tree_svc = self._require_service("tree")
            trees = await asyncio.to_thread(tree_svc.list_trees)
            return {"trees": trees}

        @self.app.get("/api/v1/trees/{tree_id}/status")
        async def get_tree_status(tree_id: str):
            # TODO: TreeService.get_status() currently returns global engine status.
            # Per-tree status requires TreeService extension (future task).
            tree_svc = self._require_service("tree")
            status = await asyncio.to_thread(tree_svc.get_status)
            return {"tree_id": tree_id, **status}

        @self.app.post("/api/v1/trees/{tree_id}/start")
        async def start_tree(tree_id: str):
            tree_svc = self._require_service("tree")
            result = await asyncio.to_thread(tree_svc.start, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/stop")
        async def stop_tree(tree_id: str):
            tree_svc = self._require_service("tree")
            result = await asyncio.to_thread(tree_svc.stop, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/pause")
        async def pause_tree(tree_id: str):
            tree_svc = self._require_service("tree")
            result = await asyncio.to_thread(tree_svc.pause, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/resume")
        async def resume_tree(tree_id: str):
            tree_svc = self._require_service("tree")
            result = await asyncio.to_thread(tree_svc.resume, tree_id)
            return result

        @self.app.get("/api/v1/trees/{tree_id}/blackboard")
        async def get_blackboard(tree_id: str):
            data_svc = self._require_service("data")
            keys = await asyncio.to_thread(data_svc.list_keys)
            if not keys:
                return {}
            values = await asyncio.gather(
                *[asyncio.to_thread(data_svc.get, k) for k in keys]
            )
            return dict(zip(keys, values))

        @self.app.get("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def get_blackboard_key(tree_id: str, key: str):
            data_svc = self._require_service("data")
            value = await asyncio.to_thread(data_svc.get, key)
            return {"key": key, "value": value}

        @self.app.put("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def set_blackboard_key(tree_id: str, key: str, body: BlackboardValue):
            data_svc = self._require_service("data")
            result = await asyncio.to_thread(data_svc.set, key, body.value)
            return result

        @self.app.delete("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def delete_blackboard_key(tree_id: str, key: str):
            data_svc = self._require_service("data")
            result = await asyncio.to_thread(data_svc.delete, key)
            return result

        @self.app.get("/api/v1/trees/{tree_id}/nodes")
        async def list_nodes(tree_id: str):
            node_svc = self._require_service("node")
            nodes = await asyncio.to_thread(node_svc.list_nodes)
            return {"nodes": nodes}

        @self.app.get("/api/v1/trees/{tree_id}/nodes/{node_id}/status")
        async def get_node_status(tree_id: str, node_id: str):
            node_svc = self._require_service("node")
            status = await asyncio.to_thread(node_svc.get_node_status, node_id)
            return status

    def start(self) -> None:
        """启动服务端（在 uvicorn 中调用）"""
        # 注入事件循环到 MessageBus（在 uvicorn 启动前由调用方调用）
        if self._bus:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            self._bus.set_event_loop(loop)

    def stop(self) -> None:
        """停止服务端"""
        pass

"""REST API 服务端 — 基于 FastAPI

参考开发方案 §3.6.6 和开发计划 §4.1.1。
使用 async/sync 桥接方案（asyncio.to_thread）。
"""
import asyncio
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .base import BaseServer
from .config import ServerConfig


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
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self._config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        """配置路由"""
        from bt_services.auth_service import PUBLIC_ENDPOINTS

        @self.app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            # 公开端点直接放行
            if request.url.path in PUBLIC_ENDPOINTS:
                return await call_next(request)

            # NoopAuthService 放行所有请求
            token = request.headers.get("Authorization", "")
            principal = self._auth.verify_token(token)
            if not principal:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized", "code": "AUTH_REQUIRED"}
                )
            request.state.principal = principal
            return await call_next(request)

        @self.app.get("/api/v1/health")
        async def health():
            return {"status": "ok"}

        @self.app.get("/api/v1/trees")
        async def list_trees():
            if not self._registry:
                return {"trees": []}
            tree_svc = self._registry.get("tree")
            if not tree_svc:
                return {"trees": []}
            trees = await asyncio.to_thread(tree_svc.list_trees)
            return {"trees": trees}

        @self.app.get("/api/v1/trees/{tree_id}/status")
        async def get_tree_status(tree_id: str):
            if not self._registry:
                raise HTTPException(404, "TreeService not available")
            tree_svc = self._registry.get("tree")
            if not tree_svc:
                raise HTTPException(404, "TreeService not available")
            status = await asyncio.to_thread(tree_svc.get_status)
            return {"tree_id": tree_id, **status}

        @self.app.post("/api/v1/trees/{tree_id}/start")
        async def start_tree(tree_id: str):
            if not self._registry:
                raise HTTPException(404, "TreeService not available")
            tree_svc = self._registry.get("tree")
            if not tree_svc:
                raise HTTPException(404, "TreeService not available")
            result = await asyncio.to_thread(tree_svc.start, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/stop")
        async def stop_tree(tree_id: str):
            if not self._registry:
                raise HTTPException(404, "TreeService not available")
            tree_svc = self._registry.get("tree")
            if not tree_svc:
                raise HTTPException(404, "TreeService not available")
            result = await asyncio.to_thread(tree_svc.stop, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/pause")
        async def pause_tree(tree_id: str):
            tree_svc = self._registry.get("tree") if self._registry else None
            if not tree_svc:
                raise HTTPException(404)
            result = await asyncio.to_thread(tree_svc.pause, tree_id)
            return result

        @self.app.post("/api/v1/trees/{tree_id}/resume")
        async def resume_tree(tree_id: str):
            tree_svc = self._registry.get("tree") if self._registry else None
            if not tree_svc:
                raise HTTPException(404)
            result = await asyncio.to_thread(tree_svc.resume, tree_id)
            return result

        @self.app.get("/api/v1/trees/{tree_id}/blackboard")
        async def get_blackboard(tree_id: str):
            data_svc = self._registry.get("data") if self._registry else None
            if not data_svc:
                raise HTTPException(404)
            keys = await asyncio.to_thread(data_svc.list_keys)
            result = {}
            for k in keys:
                result[k] = await asyncio.to_thread(data_svc.get, k)
            return result

        @self.app.get("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def get_blackboard_key(tree_id: str, key: str):
            data_svc = self._registry.get("data") if self._registry else None
            if not data_svc:
                raise HTTPException(404)
            value = await asyncio.to_thread(data_svc.get, key)
            return {"key": key, "value": value}

        @self.app.put("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def set_blackboard_key(tree_id: str, key: str, request: Request):
            data_svc = self._registry.get("data") if self._registry else None
            if not data_svc:
                raise HTTPException(404)
            body = await request.json()
            result = await asyncio.to_thread(data_svc.set, key, body.get("value"))
            return result

        @self.app.delete("/api/v1/trees/{tree_id}/blackboard/{key}")
        async def delete_blackboard_key(tree_id: str, key: str):
            data_svc = self._registry.get("data") if self._registry else None
            if not data_svc:
                raise HTTPException(404)
            result = await asyncio.to_thread(data_svc.delete, key)
            return result

        @self.app.get("/api/v1/trees/{tree_id}/nodes")
        async def list_nodes(tree_id: str):
            node_svc = self._registry.get("node") if self._registry else None
            if not node_svc:
                raise HTTPException(404)
            nodes = await asyncio.to_thread(node_svc.list_nodes)
            return {"nodes": nodes}

        @self.app.get("/api/v1/trees/{tree_id}/nodes/{node_id}/status")
        async def get_node_status(tree_id: str, node_id: str):
            node_svc = self._registry.get("node") if self._registry else None
            if not node_svc:
                raise HTTPException(404)
            status = await asyncio.to_thread(node_svc.get_node_status, node_id)
            return status

    def start(self) -> None:
        """启动服务端（在 uvicorn 中调用）"""
        # 注入事件循环到 MessageBus
        if self._bus:
            loop = asyncio.get_event_loop()
            self._bus.set_event_loop(loop)

    def stop(self) -> None:
        """停止服务端"""
        pass

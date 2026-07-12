"""认证服务接口 + NoopAuthService + 权限矩阵

参考开发方案 §3.6。
本阶段只定义接口和空实现，不实现具体认证逻辑。
后续接入认证模块时只需实现 BaseAuthService 子类，零返工。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AuthPrincipal:
    """认证主体信息

    认证通过后在整个系统中传递的用户身份。
    """
    user_id: str
    username: str = ""
    display_name: str = ""
    roles: List[str] = field(default_factory=list)
    token: str = ""
    scopes: List[str] = field(default_factory=list)
    is_offline: bool = False


class BaseAuthService(ABC):
    """认证服务抽象基类

    实现选项:
    1. PlatformAuthService  — 平台认证（参考 aut-import 分支 LoginManager）
    2. APIKeyAuthService    — API Key 静态校验
    3. OAuth2AuthService    — 对接外部 OAuth2 Provider
    4. 自定义实现            — 继承 BaseAuthService
    """

    @abstractmethod
    def verify_token(self, token: str) -> Optional[AuthPrincipal]:
        """校验 Token，返回认证主体或 None"""
        ...

    @abstractmethod
    def authenticate(self, credentials: dict) -> Optional[AuthPrincipal]:
        """认证（登录），返回认证主体或 None"""
        ...

    @abstractmethod
    def is_authenticated(self) -> bool:
        """当前是否已认证"""
        ...

    @abstractmethod
    def get_current_principal(self) -> Optional[AuthPrincipal]:
        """获取当前认证主体"""
        ...

    @abstractmethod
    def has_role(self, role: str) -> bool:
        """检查当前用户是否拥有指定角色"""
        ...

    @abstractmethod
    def has_permission(self, permission: str) -> bool:
        """检查当前用户是否拥有指定权限

        权限格式: "{资源}:{操作}"，如 "tree:start"
        支持通配符: "tree:*" 匹配所有 tree 操作
        """
        ...

    @abstractmethod
    def logout(self) -> None:
        """登出，清除认证状态"""
        ...


class NoopAuthService(BaseAuthService):
    """空实现 — 认证未启用时的默认行为

    所有验证都通过，所有权限都允许。
    消息总线和 REST Server 默认使用此实现。
    """

    _principal = AuthPrincipal(user_id="anonymous", roles=["anonymous"])

    def verify_token(self, token: str) -> Optional[AuthPrincipal]:
        return self._principal

    def authenticate(self, credentials: dict) -> Optional[AuthPrincipal]:
        return self._principal

    def is_authenticated(self) -> bool:
        return True

    def get_current_principal(self) -> Optional[AuthPrincipal]:
        return self._principal

    def has_role(self, role: str) -> bool:
        return True

    def has_permission(self, permission: str) -> bool:
        return True

    def logout(self) -> None:
        pass


# 权限矩阵定义
PERMISSIONS = {
    "tree:start":        "启动行为树",
    "tree:stop":         "停止行为树",
    "tree:pause":        "暂停行为树",
    "tree:resume":       "恢复行为树",
    "tree:status":       "查询行为树状态",
    "tree:load":         "加载行为树",
    "blackboard:read":   "读取黑板变量",
    "blackboard:write":  "写入黑板变量",
    "blackboard:delete": "删除黑板变量",
    "blackboard:list":   "列出黑板变量",
    "node:status":       "查询节点状态",
    "node:config":       "查询节点配置",
    "event:subscribe":   "订阅事件流",
    "adapter:http":      "HTTP 适配器调用",
    "adapter:websocket": "WebSocket 适配器调用",
}

ROLE_PERMISSIONS = {
    "admin": list(PERMISSIONS.keys()),
    "operator": [
        "tree:*", "blackboard:read", "blackboard:write", "blackboard:list",
        "node:status", "node:config", "event:subscribe",
        "adapter:http", "adapter:websocket",
    ],
    "viewer": [
        "tree:status", "blackboard:read", "blackboard:list",
        "node:status", "node:config", "event:subscribe",
    ],
    "anonymous": [],
}

PUBLIC_ENDPOINTS = [
    "/api/v1/auth/login",
    "/api/v1/health",
]

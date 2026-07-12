"""服务端配置"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class ServerConfig:
    """服务端配置"""
    host: str = "127.0.0.1"
    port: int = 8080
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    rate_limit_per_minute: int = 60
    api_key_enabled: bool = False

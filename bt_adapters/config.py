"""适配器配置"""
from dataclasses import dataclass, field


@dataclass
class AdapterConfig:
    """适配器配置"""
    name: str = ""
    enabled: bool = False
    connect_timeout: int = 10
    read_timeout: int = 30
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    extra: dict = field(default_factory=dict)

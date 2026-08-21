"""Message 数据类

参考开发方案 §3.1 消息格式。
"""
import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


class MessagePriority(enum.Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Message:
    """消息数据类

    Attributes:
        id: 消息唯一 ID（uuid4）
        topic: 点分层次主题（如 bt.1.event.tree.started）
        data: JSON 兼容数据
        headers: 元数据（含认证信息，见方案 §3.6）
        timestamp: 创建时间戳
        source: 来源标识
        priority: 消息优先级
        reply_to: 回复主题（请求-响应模式）
        correlation_id: 关联 ID
    """
    id: str
    topic: str
    data: Any
    headers: dict
    timestamp: float
    source: str
    priority: MessagePriority = MessagePriority.NORMAL
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None

    @classmethod
    def create(cls, topic: str, data: Any, source: str = "",
               headers: dict = None) -> "Message":
        """工厂方法：创建消息"""
        return cls(
            id=str(uuid.uuid4()),
            topic=topic,
            data=data,
            headers=headers or {},
            timestamp=time.time(),
            source=source,
            correlation_id=str(uuid.uuid4()),
        )

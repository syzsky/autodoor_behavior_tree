"""消息总线异常体系

参考开发方案 §1.1 和开发计划 §1.1.4。
"""


class BusError(Exception):
    """消息总线基础异常"""
    pass


class MessageValidationError(BusError):
    """消息格式校验失败"""
    pass


class NoSubscriberError(BusError):
    """无订阅者异常"""
    pass


class RequestTimeoutError(BusError):
    """请求-响应模式超时"""
    pass


class MiddlewareError(BusError):
    """中间件处理异常"""
    pass

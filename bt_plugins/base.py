"""插件接口规范 — BasePlugin / PluginInfo / PluginContext

定义插件系统的核心抽象：
- PluginInfo: 插件元信息数据类
- PluginContext: 插件运行上下文，隔离插件与主系统的直接依赖
- BasePlugin: 插件抽象基类，定义生命周期与扩展点
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass
class PluginInfo:
    """插件元信息

    所有字段在 plugin.json 中声明，由 PluginLoader 解析后构造。
    """
    name: str
    display_name: str
    version: str
    author: str
    description: str
    category: str = "general"
    min_app_version: str = ""
    dependencies: Optional[List[str]] = None


class PluginContext:
    """插件运行上下文 — 隔离插件与主系统的直接依赖

    插件通过此上下文访问配置、消息总线、适配器、服务与日志，
    避免直接导入主系统模块，保证插件的可移植性与隔离性。
    """

    def __init__(self, settings=None, message_bus=None,
                 adapter_manager=None, service_registry=None):
        self._settings = settings
        self._message_bus = message_bus
        self._adapter_manager = adapter_manager
        self._service_registry = service_registry
        self._plugin_name: str = ""

    def set_plugin_name(self, name: str) -> None:
        """设置当前插件名（由 PluginLoader 在加载时调用）"""
        self._plugin_name = name

    @property
    def plugin_name(self) -> str:
        return self._plugin_name

    def get_config(self, key: str, default: Any = None) -> Any:
        """从 settings 读取 plugins.{plugin_name}.{key}"""
        if self._settings:
            return self._settings.get(
                f"plugins.{self._plugin_name}.{key}", default
            )
        return default

    def publish(self, topic: str, data: Any) -> str:
        """通过消息总线发布消息"""
        if self._message_bus:
            return self._message_bus.publish(topic, data)
        return ""

    def subscribe(self, topic: str, callback: Callable) -> str:
        """订阅消息总线主题"""
        if self._message_bus:
            return self._message_bus.subscribe(topic, callback)
        return ""

    def get_adapter(self, name: str):
        """获取适配器实例"""
        if self._adapter_manager:
            return self._adapter_manager.get_adapter(name)
        return None

    def get_service(self, name: str):
        """获取服务实例"""
        if self._service_registry:
            return self._service_registry.get(name)
        return None

    def log(self, level: str, msg: str) -> None:
        """记录日志，前缀 [Plugin:{plugin_name}]

        通过 LogManager.debug_print 输出，保证开发环境终端可见。
        """
        from bt_utils.log_manager import LogManager
        prefix = f"[Plugin:{self._plugin_name}] "
        LogManager.debug_print(prefix + msg)


class BasePlugin:
    """插件抽象基类

    生命周期: on_load() → on_start() → [运行中] → on_stop() → on_unload()

    子类通过重写扩展点方法提供节点、适配器、服务、schema 等扩展能力。
    on_load / on_unload 提供默认实现（设置状态标志），子类可重写以执行
    自定义初始化/清理逻辑，但应调用 super().on_load() / super().on_unload()
    以保证状态标志正确。
    """

    def __init__(self, info: PluginInfo):
        self.info = info
        self._loaded: bool = False
        self._started: bool = False
        self._context: Optional[PluginContext] = None

    def set_context(self, context: PluginContext) -> None:
        """注入运行上下文（由 PluginLoader 调用）"""
        self._context = context

    @property
    def context(self) -> Optional[PluginContext]:
        return self._context

    def log(self, level: str, msg: str) -> None:
        """记录日志 — 优先通过 context，未注入时降级到 print"""
        if self._context:
            self._context.log(level, msg)
        else:
            print(f"[Plugin:{self.info.name}] {msg}")

    # ── 生命周期方法 ──

    def on_load(self) -> None:
        """加载 — 设置已加载标志"""
        self._loaded = True

    def on_unload(self) -> None:
        """卸载 — 清除已加载标志"""
        self._loaded = False

    def on_start(self) -> None:
        """启动 — 设置已启动标志"""
        self._started = True

    def on_stop(self) -> None:
        """停止 — 清除已启动标志"""
        self._started = False

    # ── 扩展点（子类按需重写） ──

    def get_nodes(self) -> Dict[str, Type]:
        """返回插件提供的节点类型 {node_type: NodeClass}"""
        return {}

    def get_adapters(self) -> Dict[str, Type]:
        """返回插件提供的适配器类型 {adapter_name: AdapterClass}"""
        return {}

    def get_services(self) -> Dict[str, Any]:
        """返回插件提供的服务实例 {service_name: service_instance}"""
        return {}

    def get_node_schemas(self) -> Dict[str, list]:
        """返回节点属性 schema {node_type: [field_schema, ...]}"""
        return {}

    def get_node_display_info(self) -> Dict[str, dict]:
        """返回节点展示信息 {node_type: {display_name, description, category}}"""
        return {}

    def get_config_schema(self) -> dict:
        """返回插件配置 schema"""
        return {}

"""示例插件 — 展示插件开发的基本模式"""

from bt_plugins.base import BasePlugin


class ExamplePlugin(BasePlugin):
    """示例插件"""

    def on_load(self):
        """加载时初始化"""
        self._loaded = True
        self.log("info", "示例插件已加载")

    def on_unload(self):
        """卸载时清理"""
        self._loaded = False
        self.log("info", "示例插件已卸载")

    def on_start(self):
        """启动时注册"""
        self._started = True
        self.log("info", "示例插件已启动")

    def on_stop(self):
        """停止时注销"""
        self._started = False
        self.log("info", "示例插件已停止")

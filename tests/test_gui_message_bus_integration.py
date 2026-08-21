# tests/test_gui_message_bus_integration.py
"""B-2: GUI 集成状态验证测试。

验证消息总线启动 → context 注入 → 节点访问的完整链路。
"""
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestGUIMessageBusIntegration(unittest.TestCase):
    """验证 GUI 消息总线集成链路"""

    def setUp(self):
        """重置单例，确保测试隔离"""
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()
        from bt_bus.message_bus import MessageBus
        MessageBus.reset_instance()
        from config.settings_manager import SettingsManager
        SettingsManager.reset_instance()

    def tearDown(self):
        """清理单例"""
        from bt_bus.thread_pool import SharedThreadPool
        SharedThreadPool.reset_instance()
        from bt_bus.message_bus import MessageBus
        MessageBus.reset_instance()
        from config.settings_manager import SettingsManager
        SettingsManager.reset_instance()

    def test_settings_enabled_app_has_message_bus(self):
        """settings.message_bus.enabled=True 时，_init_message_bus_and_servers 创建 message_bus"""
        from config.settings_manager import SettingsManager
        settings = SettingsManager.get_instance()
        settings.set("message_bus.enabled", True)

        from bt_gui.app import BehaviorTreeApp

        app = BehaviorTreeApp.__new__(BehaviorTreeApp)
        app._settings = settings
        app._message_bus = None

        app._init_message_bus_and_servers()

        self.assertIsNotNone(app._message_bus)
        from bt_bus.message_bus import MessageBus
        self.assertIsInstance(app._message_bus, MessageBus)

        app._message_bus.stop()

    def test_settings_disabled_app_has_no_message_bus(self):
        """settings.message_bus.enabled=False 时，_init_message_bus_and_servers 不创建 message_bus"""
        from config.settings_manager import SettingsManager
        settings = SettingsManager.get_instance()
        settings.set("message_bus.enabled", False)

        from bt_gui.app import BehaviorTreeApp

        app = BehaviorTreeApp.__new__(BehaviorTreeApp)
        app._settings = settings
        app._message_bus = None

        app._init_message_bus_and_servers()

        self.assertIsNone(app._message_bus)

    def test_context_get_message_bus_returns_bus_when_injected(self):
        """节点通过 context.get_message_bus() 能获取到总线引用"""
        from bt_core.context import ExecutionContext
        from bt_bus.message_bus import MessageBus

        bus = MessageBus()
        bus.start()

        ctx = ExecutionContext()
        ctx.set_message_bus(bus)

        self.assertIs(ctx.get_message_bus(), bus)

        bus.stop()

    def test_editor_run_passes_bus_to_context(self):
        """编辑器启动行为树时，应将 app 的 message_bus 传递给 context"""
        from bt_bus.message_bus import MessageBus
        from bt_core.context import ExecutionContext

        bus = MessageBus()
        bus.start()

        class MockApp:
            _message_bus = bus

        class MockTabManager:
            def get_tab(self, tab_id):
                return None

        editor_instance = type('TestEditor', (), {
            'app': MockApp(),
            'tab_manager': MockTabManager(),
        })

        ctx = ExecutionContext(project_root=None)
        ctx.set_message_bus(getattr(editor_instance.app, '_message_bus', None))

        self.assertIs(ctx.get_message_bus(), bus)

        bus.stop()

    def test_editor_source_code_has_bus_injection(self):
        """验证 editor.py 源码中包含将 app._message_bus 注入到 context 的逻辑"""
        editor_path = os.path.join(PROJECT_ROOT, "bt_gui", "bt_editor", "editor.py")
        with open(editor_path, "r", encoding="utf-8") as f:
            src = f.read()

        required_patterns = [
            "context.set_message_bus(getattr(self.app, '_message_bus'",
        ]

        missing = [p for p in required_patterns if p not in src]
        self.assertFalse(missing, f"editor.py 缺少 bus 注入逻辑: {missing}")


if __name__ == '__main__':
    unittest.main()

# tests/test_plugin_base.py
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
from bt_plugins.base import BasePlugin, PluginInfo, PluginContext


def test_plugin_info_creation():
    info = PluginInfo(name="test", display_name="测试", version="1.0.0",
                      author="tester", description="test plugin")
    assert info.name == "test"
    assert info.display_name == "测试"
    assert info.category == "general"
    assert info.dependencies is None


def test_plugin_lifecycle():
    info = PluginInfo(name="test", display_name="测试", version="1.0.0",
                      author="t", description="d")
    plugin = BasePlugin(info)
    assert not plugin._loaded
    plugin.on_load()
    assert plugin._loaded
    plugin.on_start()
    assert plugin._started
    plugin.on_stop()
    assert not plugin._started
    plugin.on_unload()


def test_plugin_default_extensions():
    info = PluginInfo(name="test", display_name="测试", version="1.0.0",
                      author="t", description="d")
    plugin = BasePlugin(info)
    assert plugin.get_nodes() == {}
    assert plugin.get_adapters() == {}
    assert plugin.get_services() == {}
    assert plugin.get_node_schemas() == {}
    assert plugin.get_node_display_info() == {}
    assert plugin.get_config_schema() == {}


def test_plugin_context_config():
    class MockSettings:
        def __init__(self):
            self.data = {"plugins.test.key": "value"}

        def get(self, key, default=None):
            return self.data.get(key, default)

    ctx = PluginContext(settings=MockSettings())
    ctx.set_plugin_name("test")
    assert ctx.get_config("key") == "value"
    assert ctx.get_config("missing", "default") == "default"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

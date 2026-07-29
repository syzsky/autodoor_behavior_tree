# tests/test_plugin_loader.py
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import pytest
from bt_plugins.base import PluginInfo, PluginContext
from bt_plugins.loader import PluginLoader


def _create_test_plugin(tmpdir, name="test_plugin"):
    """创建测试插件目录"""
    plugin_dir = os.path.join(tmpdir, name)
    os.makedirs(plugin_dir, exist_ok=True)
    manifest = {
        "name": name,
        "display_name": "测试插件",
        "version": "1.0.0",
        "author": "tester",
        "description": "test",
        "entry": "main.py",
        "class": "TestPlugin",
    }
    with open(os.path.join(plugin_dir, "plugin.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)
    main_py = '''
from bt_plugins.base import BasePlugin, PluginInfo

class TestPlugin(BasePlugin):
    def on_load(self):
        self._loaded = True
    def on_unload(self):
        self._loaded = False
'''
    with open(os.path.join(plugin_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(main_py)
    return plugin_dir


def test_scan_plugins(tmp_path):
    _create_test_plugin(str(tmp_path))
    loader = PluginLoader(PluginContext())
    infos = loader.scan(str(tmp_path))
    assert len(infos) == 1
    assert infos[0].name == "test_plugin"


def test_load_plugin(tmp_path):
    plugin_dir = _create_test_plugin(str(tmp_path))
    loader = PluginLoader(PluginContext())
    assert loader.load_plugin(plugin_dir)
    assert "test_plugin" in loader._plugins


def test_start_stop_plugin(tmp_path):
    plugin_dir = _create_test_plugin(str(tmp_path))
    loader = PluginLoader(PluginContext())
    loader.load_plugin(plugin_dir)
    assert loader.start_plugin("test_plugin")
    assert loader._plugins["test_plugin"]._started
    loader.stop_plugin("test_plugin")
    assert not loader._plugins["test_plugin"]._started


def test_unload_plugin(tmp_path):
    plugin_dir = _create_test_plugin(str(tmp_path))
    loader = PluginLoader(PluginContext())
    loader.load_plugin(plugin_dir)
    loader.start_plugin("test_plugin")
    loader.unload_plugin("test_plugin")
    assert "test_plugin" not in loader._plugins


def test_list_plugins(tmp_path):
    _create_test_plugin(str(tmp_path))
    loader = PluginLoader(PluginContext())
    loader.load_plugin(_create_test_plugin(str(tmp_path)))
    infos = loader.list_plugins()
    assert len(infos) == 1


def _create_plugin_with_nodes(tmpdir, name="node_plugin"):
    """创建带节点和显示信息的插件"""
    plugin_dir = os.path.join(tmpdir, name)
    os.makedirs(plugin_dir, exist_ok=True)
    manifest = {
        "name": name,
        "display_name": "节点插件",
        "version": "1.0.0",
        "author": "tester",
        "description": "带节点的插件",
        "entry": "main.py",
        "class": "NodePlugin",
    }
    with open(os.path.join(plugin_dir, "plugin.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)
    main_py = '''
from bt_plugins.base import BasePlugin


class NodePlugin(BasePlugin):
    def on_load(self):
        self._loaded = True
    def on_unload(self):
        self._loaded = False
    def get_nodes(self):
        from bt_core.nodes import ActionNode
        return {"GreetNode": ActionNode}
    def get_node_display_info(self):
        return {
            "GreetNode": {
                "display_name": "问候",
                "description": "打招呼节点",
                "category": "plugin",
                "icon": "★",
            }
        }
    def get_node_schemas(self):
        return {
            "GreetNode": [
                {"key": "message", "label": "消息", "type": "text", "default": "hello"}
            ]
        }
'''
    with open(os.path.join(plugin_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(main_py)
    return plugin_dir


def test_get_registered_display_info_empty(tmp_path):
    """未启动任何插件时，display_info 为空"""
    loader = PluginLoader(PluginContext())
    assert loader.get_registered_display_info() == {}


def test_get_registered_display_info_after_start(tmp_path):
    """启动插件后，display_info 含插件节点信息（key 为带前缀的 node_type）"""
    plugin_dir = _create_plugin_with_nodes(str(tmp_path))
    loader = PluginLoader(PluginContext())
    loader.load_plugin(plugin_dir)
    loader.start_plugin("node_plugin")
    info = loader.get_registered_display_info()
    assert "node_plugin.GreetNode" in info
    assert info["node_plugin.GreetNode"]["display_name"] == "问候"


def test_get_registered_schemas_after_start(tmp_path):
    """启动插件后，schemas 含插件节点 schema"""
    plugin_dir = _create_plugin_with_nodes(str(tmp_path))
    loader = PluginLoader(PluginContext())
    loader.load_plugin(plugin_dir)
    loader.start_plugin("node_plugin")
    schemas = loader.get_registered_schemas()
    assert "node_plugin.GreetNode" in schemas
    assert schemas["node_plugin.GreetNode"][0]["key"] == "message"


def test_registered_display_info_cleared_after_stop(tmp_path):
    """停止插件后，display_info 应清除该插件的节点"""
    plugin_dir = _create_plugin_with_nodes(str(tmp_path))
    loader = PluginLoader(PluginContext())
    loader.load_plugin(plugin_dir)
    loader.start_plugin("node_plugin")
    assert loader.get_registered_display_info()
    loader.stop_plugin("node_plugin")
    assert loader.get_registered_display_info() == {}
    assert loader.get_registered_schemas() == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

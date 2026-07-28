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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

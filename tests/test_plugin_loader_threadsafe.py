# tests/test_plugin_loader_threadsafe.py
"""PluginLoader 线程安全测试"""
import threading
import os
import sys
import tempfile
import json
from unittest.mock import MagicMock

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_concurrent_load_and_start():
    """测试并发 load_plugin + start_plugin 无竞态"""
    from bt_plugins.loader import PluginLoader
    from bt_plugins.base import PluginContext

    context = PluginContext()
    loader = PluginLoader(context)

    errors = []
    def load_and_start(plugin_name):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                plugin_dir = os.path.join(tmpdir, plugin_name)
                os.makedirs(plugin_dir)
                manifest = {
                    "name": plugin_name,
                    "display_name": plugin_name,
                    "version": "1.0.0",
                    "author": "test",
                    "description": "test plugin",
                    "entry": "main.py",
                    "class": "TestPlugin",
                }
                with open(os.path.join(plugin_dir, "plugin.json"), "w") as f:
                    json.dump(manifest, f)
                with open(os.path.join(plugin_dir, "main.py"), "w") as f:
                    f.write("""
from bt_plugins.base import BasePlugin
class TestPlugin(BasePlugin):
    pass
""")
                loader.load_plugin(plugin_dir)
                loader.start_plugin(plugin_name)
        except Exception as e:
            errors.append(str(e))

    threads = []
    for i in range(5):
        t = threading.Thread(target=load_and_start, args=(f"plugin_{i}",))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"并发错误: {errors}"
    assert len(loader.list_plugins()) == 5


def test_concurrent_list_during_modify():
    """测试在修改过程中并发查询"""
    from bt_plugins.loader import PluginLoader
    from bt_plugins.base import PluginContext

    context = PluginContext()
    loader = PluginLoader(context)

    errors = []
    def list_repeatedly():
        try:
            for _ in range(100):
                loader.list_plugins()
                loader.is_started("nonexistent")
        except Exception as e:
            errors.append(str(e))

    def modify_repeatedly():
        try:
            for _ in range(100):
                loader.unload_plugin("nonexistent")
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=list_repeatedly)
    t2 = threading.Thread(target=modify_repeatedly)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"并发查询错误: {errors}"

# tests/test_plugin_panel_ui.py
"""插件面板 UI 组件测试

测试 PluginStatusBarIndicator 和 PluginConfigEditor 的核心逻辑。
GUI 测试需要 display，无 display 时自动跳过。
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
from unittest.mock import MagicMock


def _try_create_root():
    """尝试创建 CTk 根窗口，失败则返回 None"""
    try:
        import customtkinter as ctk
        root = ctk.CTk()
        root.withdraw()
        return root
    except Exception:
        return None


def test_plugin_status_indicator_creation():
    """测试插件状态栏指示器创建"""
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter 不可用")

    root = _try_create_root()
    if root is None:
        pytest.skip("无法创建 GUI 窗口")

    try:
        from bt_gui.plugin_panel import PluginStatusBarIndicator
        loader = MagicMock()
        loader.list_plugins.return_value = []
        loader.is_started.return_value = False

        indicator = PluginStatusBarIndicator(root, loader)
        assert indicator is not None

        # 测试无插件时的状态
        assert indicator.get_status_text() == "插件: 0/0 已启动"
    finally:
        root.destroy()


def test_plugin_status_indicator_with_plugins():
    """测试有插件时的状态指示器"""
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter 不可用")

    root = _try_create_root()
    if root is None:
        pytest.skip("无法创建 GUI 窗口")

    try:
        from bt_gui.plugin_panel import PluginStatusBarIndicator
        from bt_plugins.base import PluginInfo

        loader = MagicMock()

        # 模拟 3 个插件，2 个已启动
        infos = [
            PluginInfo(name=f"plugin_{i}", display_name=f"插件{i}",
                       version="1.0.0", author="t", description="d")
            for i in range(3)
        ]
        loader.list_plugins.return_value = infos
        loader.is_started.side_effect = lambda name: name in ("plugin_0", "plugin_1")

        indicator = PluginStatusBarIndicator(root, loader)
        assert indicator.get_status_text() == "插件: 2/3 已启动"
    finally:
        root.destroy()


def test_plugin_status_indicator_refresh():
    """测试刷新状态指示器"""
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter 不可用")

    root = _try_create_root()
    if root is None:
        pytest.skip("无法创建 GUI 窗口")

    try:
        from bt_gui.plugin_panel import PluginStatusBarIndicator

        loader = MagicMock()
        loader.list_plugins.return_value = []
        loader.is_started.return_value = False

        indicator = PluginStatusBarIndicator(root, loader)
        assert indicator.get_status_text() == "插件: 0/0 已启动"

        # 模拟插件变化后刷新
        from bt_plugins.base import PluginInfo
        infos = [PluginInfo(name="p1", display_name="P1",
                            version="1.0", author="t", description="d")]
        loader.list_plugins.return_value = infos
        loader.is_started.return_value = True

        indicator.refresh()
        assert indicator.get_status_text() == "插件: 1/1 已启动"
    finally:
        root.destroy()


def test_plugin_config_editor_renders_schema():
    """测试配置编辑器根据 schema 渲染配置项"""
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter 不可用")

    root = _try_create_root()
    if root is None:
        pytest.skip("无法创建 GUI 窗口")

    try:
        from bt_gui.plugin_panel import PluginConfigEditor

        schema = {
            "heuristic": {
                "type": "select", "default": "manhattan",
                "label": "启发函数",
                "options": ["manhattan", "euclidean"]
            },
            "allow_diagonal": {
                "type": "bool", "default": True,
                "label": "允许对角线"
            },
            "max_iterations": {
                "type": "number", "default": 1000,
                "label": "最大迭代次数"
            }
        }

        editor = PluginConfigEditor(root, schema=schema, plugin_name="test")
        values = editor.get_values()

        assert values["heuristic"] == "manhattan"
        assert values["allow_diagonal"] is True
        assert values["max_iterations"] == 1000
    finally:
        root.destroy()


def test_plugin_config_editor_empty_schema():
    """测试空 schema 时配置编辑器显示提示"""
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter 不可用")

    root = _try_create_root()
    if root is None:
        pytest.skip("无法创建 GUI 窗口")

    try:
        from bt_gui.plugin_panel import PluginConfigEditor

        editor = PluginConfigEditor(root, schema={}, plugin_name="test")
        values = editor.get_values()
        assert values == {}
    finally:
        root.destroy()


def test_plugin_config_editor_set_values():
    """测试设置配置项的值"""
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter 不可用")

    root = _try_create_root()
    if root is None:
        pytest.skip("无法创建 GUI 窗口")

    try:
        from bt_gui.plugin_panel import PluginConfigEditor

        schema = {
            "threshold": {
                "type": "number", "default": 100,
                "label": "阈值"
            },
            "enabled": {
                "type": "bool", "default": False,
                "label": "启用"
            }
        }

        editor = PluginConfigEditor(root, schema=schema, plugin_name="test")
        editor.set_values({"threshold": 500, "enabled": True})

        values = editor.get_values()
        assert values["threshold"] == 500
        assert values["enabled"] is True
    finally:
        root.destroy()


def test_plugin_card_error_state():
    """测试 PluginCard 错误状态设置与清除"""
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter 不可用")

    root = _try_create_root()
    if root is None:
        pytest.skip("无法创建 GUI 窗口")

    try:
        from bt_gui.plugin_panel import PluginCard
        from bt_plugins.base import PluginInfo

        info = PluginInfo(
            name="test_plugin", display_name="测试插件",
            version="1.0.0", author="t", description="d"
        )
        card = PluginCard(root, info, is_started=False,
                          on_start=None, on_stop=None)

        # 设置错误状态
        card.set_error("启动失败：依赖缺失")
        assert card._error_message == "启动失败：依赖缺失"

        # 清除错误状态
        card.clear_error()
        assert card._error_message == ""
    finally:
        root.destroy()


def test_plugin_panel_find_card():
    """测试 PluginPanel._find_card 辅助方法"""
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter 不可用")

    root = _try_create_root()
    if root is None:
        pytest.skip("无法创建 GUI 窗口")

    try:
        from bt_gui.plugin_panel import PluginPanel
        from bt_plugins.base import PluginInfo
        from bt_plugins.loader import PluginLoader
        from bt_plugins.base import PluginContext

        loader = PluginLoader(PluginContext())
        panel = PluginPanel(root, loader, list_height=100)

        # 无插件时 _find_card 返回 None
        assert panel._find_card("nonexistent") is None
    finally:
        root.destroy()

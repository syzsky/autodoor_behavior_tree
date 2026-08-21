# tests/test_gui_integration.py
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bt_plugins.gui_integration import (
    merge_plugin_nodes, merge_plugin_schemas, merge_plugin_palette
)


def test_merge_plugin_nodes():
    category_map = {"ExistingNode": "action"}
    display_names = {"ExistingNode": "已有"}
    descriptions = {"ExistingNode": "desc"}
    plugin_info = {
        "CustomNode": {
            "display_name": "自定义",
            "description": "插件节点",
            "category": "plugin",
        }
    }
    merge_plugin_nodes(category_map, display_names, descriptions, plugin_info)
    assert "CustomNode" in category_map
    assert category_map["CustomNode"] == "plugin"
    assert display_names["CustomNode"] == "自定义"
    assert descriptions["CustomNode"] == "插件节点"


def test_merge_plugin_schemas():
    existing = {"ExistingNode": [{"key": "a", "label": "A"}]}
    plugin_schemas = {"CustomNode": [{"key": "b", "label": "B"}]}
    merge_plugin_schemas(existing, plugin_schemas)
    assert "CustomNode" in existing
    assert existing["CustomNode"][0]["key"] == "b"


def test_merge_plugin_palette():
    categories = {"组合节点": {"icon": "◇", "color": "#6366F1", "nodes": []}}
    plugin_nodes = [("CustomNode", "自定义", "插件节点")]
    merge_plugin_palette(categories, plugin_nodes)
    assert "插件节点" in categories
    assert len(categories["插件节点"]["nodes"]) == 1
    assert categories["插件节点"]["nodes"][0][0] == "CustomNode"


def test_merge_plugin_palette_existing():
    """已有插件节点分类时，追加到已有分类"""
    categories = {"插件节点": {"icon": "★", "color": "#6B7280", "nodes": [("NodeA", "A", "a")]}}
    plugin_nodes = [("NodeB", "B", "b")]
    merge_plugin_palette(categories, plugin_nodes)
    assert len(categories["插件节点"]["nodes"]) == 2


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

# tests/test_tree_modifier.py
"""TreeModifier 测试

环境说明:
    bt_utils/__init__.py 会 eager-import OCRManager / ScriptRecorder 等模块,
    它们依赖 rapidocr / pynput 等重型三方库。conftest.py 已为这些可选依赖
    注入 MagicMock,因此此处可直接导入 bt_cli.ai.tree_modifier。
"""
import json
from unittest.mock import MagicMock, patch

from bt_cli.ai.tree_modifier import TreeModifier, TreeModifyError


def _tree():
    """构造符合真实 tree.json 形态的已有树（nodes 为 dict）"""
    return {
        "version": "2.1", "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode",
                           "config": {}, "children": ["node_click"]},
            "node_click": {"id": "node_click", "type": "MouseClickNode",
                           "config": {"position": [100, 200]}, "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_click"}],
    }


def test_modify_returns_valid_tree_and_changes():
    """LLM 返回合法新树时,modify 校验通过并返回 tree/changes/summary"""
    new_tree = {
        "version": "2.1", "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode",
                           "config": {}, "children": ["node_delay"]},
            "node_delay": {"id": "node_delay", "type": "DelayNode",
                           "config": {"duration_ms": 1000}, "children": ["node_click"]},
            "node_click": {"id": "node_click", "type": "MouseClickNode",
                           "config": {"position": [100, 200]}, "children": []},
        },
        "connections": [
            {"parent_id": "node_start", "child_id": "node_delay"},
            {"parent_id": "node_delay", "child_id": "node_click"},
        ],
    }
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "tree": new_tree,
            "changes": [{"type": "add", "node_id": "node_delay",
                         "description": "点击前插入延时节点"}],
            "summary": "插入一个 1000ms 延时节点",
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        out = mod.modify(_tree(), "点击前加个延时")
        assert out["tree"]["nodes"]["node_delay"]["type"] == "DelayNode"
        assert len(out["changes"]) == 1
        assert out["changes"][0]["node_id"] == "node_delay"
        assert out["summary"] == "插入一个 1000ms 延时节点"


def test_modify_raises_on_invalid_tree():
    """LLM 返回结构非法(缺 root_node)时,modify 抛 TreeModifyError"""
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "tree": {"nodes": {}},  # 缺 root_node，校验失败
            "changes": [], "summary": ""
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError:
            pass


def test_summarize_tree_uses_dict_nodes():
    """_summarize_tree 按 dict 形态遍历 nodes,而非 list"""
    mod = TreeModifier()
    summary = mod._summarize_tree(_tree())
    assert len(summary) == 2
    by_id = {s["id"]: s for s in summary}
    assert by_id["node_start"]["type"] == "StartNode"
    assert by_id["node_start"]["children"] == ["node_click"]
    assert by_id["node_click"]["config"] == {"position": [100, 200]}


def test_modify_uses_summarized_tree_not_full_tree():
    """modify 应把精简树传给 LLM,而非完整 tree_data(剔除 name/enabled/position 展示字段)"""
    new_tree = {
        "version": "2.1", "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode",
                           "config": {}, "children": ["node_click"]},
            "node_click": {"id": "node_click", "type": "MouseClickNode",
                           "config": {"position": [100, 200]}, "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_click"}],
    }
    # 带展示性字段(name/enabled/position)的完整树,用于验证被精简剔除
    display_tree = {
        "version": "2.1", "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode",
                           "name": "UNIQUE_NAME_START", "enabled": True,
                           "position": {"x": 1, "y": 2},
                           "config": {}, "children": ["node_click"]},
            "node_click": {"id": "node_click", "type": "MouseClickNode",
                           "name": "UNIQUE_NAME_CLICK", "enabled": True,
                           "position": {"x": 3, "y": 4},
                           "config": {"position": [100, 200]}, "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_click"}],
    }
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "tree": new_tree, "changes": [], "summary": "",
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        mod.modify(display_tree, "改动")
        user_content = mock.chat.call_args[0][0][1]["content"]
        # 精简树结构:含 id/type,剔除展示性字段
        assert "精简结构" in user_content
        assert '"StartNode"' in user_content
        assert "UNIQUE_NAME_START" not in user_content
        assert "UNIQUE_NAME_CLICK" not in user_content
        assert '"enabled"' not in user_content
        assert '"position": {"x"' not in user_content


def test_modify_raises_on_llm_exception():
    """LLM chat 抛异常 → 抛 TreeModifyError"""
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.side_effect = RuntimeError("network down")
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError:
            pass


def test_modify_raises_on_invalid_json():
    """LLM 返回非法 JSON → 抛 TreeModifyError"""
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": "{ this is not json", "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError:
            pass


def test_modify_raises_on_missing_tree_field():
    """LLM 返回缺 tree 字段 → 抛 TreeModifyError"""
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "changes": [], "summary": "",
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError:
            pass


def test_modify_raises_on_non_dict_top_level():
    """LLM 返回顶层非 dict(数组) → 抛 TreeModifyError(而非 AttributeError)"""
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps([1, 2, 3]), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError:
            pass


def test_modify_raises_on_non_dict_tree():
    """LLM 返回的 tree 为列表(而非 dict) → 抛 TreeModifyError(而非 AttributeError)"""
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "tree": [{"id": "node_start", "type": "StartNode"}],  # 非 dict 形态
            "changes": [], "summary": "",
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError as e:
            assert "行为树格式错误" in str(e), "错误信息应说明行为树格式错误"


def test_modify_raises_on_non_dict_nodes():
    """LLM 返回的 tree.nodes 为列表(而非 dict) → 抛 TreeModifyError(而非原生 TypeError)"""
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "tree": {
                "root_node": "node_start",
                "nodes": [{"id": "node_start", "type": "StartNode"}],  # 非 dict 形态
            },
            "changes": [], "summary": "",
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError as e:
            assert "nodes 格式错误" in str(e), "错误信息应说明 nodes 格式错误"


def test_modify_raises_on_empty_nodes_list():
    """LLM 返回空 list 的 nodes(非 dict) → 抛 TreeModifyError"""
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "tree": {"root_node": "node_start", "nodes": []},
            "changes": [], "summary": "",
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError:
            pass
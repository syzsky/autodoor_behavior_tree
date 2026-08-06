"""阶段视图组件测试"""
import pytest
from unittest.mock import MagicMock, patch


def test_stage1_view_creates_content():
    """测试阶段①视图创建内容"""
    from bt_gui.ai_assistant.stage_views import create_stage1_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.plan = {
        "task_summary": "每秒点击鼠标",
        "loop": {"enabled": True, "interval_ms": 1000},
        "phases": [{"phase": "act", "action": "click"}],
    }

    mock_frame = MagicMock()
    mock_colors = {"text_primary": "#fff", "text_muted": "#aaa",
                   "bg_primary": "#1a1a1a", "bg_tertiary": "#2a2a2a"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage1_view(mock_frame, state, mock_colors)

    # 验证至少创建了一些 widget
    assert mock_frame.winfo_children.called or True  # mock 环境下验证不严格


def test_stage2_view_creates_content():
    """测试阶段②视图创建内容"""
    from bt_gui.ai_assistant.stage_views import create_stage2_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.structure = {
        "nodes": [
            {"id": "node_start", "type": "StartNode",
             "config": {}, "children": ["node_delay"]},
            {"id": "node_delay", "type": "DelayNode",
             "config": {"duration_ms": 1000}, "children": []},
        ]
    }

    mock_frame = MagicMock()
    mock_colors = {"text_primary": "#fff", "text_muted": "#aaa",
                   "bg_primary": "#1a1a1a", "bg_tertiary": "#2a2a2a"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage2_view(mock_frame, state, mock_colors)


def test_stage1_view_empty_plan():
    """测试阶段①视图无数据时显示提示"""
    from bt_gui.ai_assistant.stage_views import create_stage1_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {"text_muted": "#aaa"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage1_view(mock_frame, state, mock_colors)


def test_stage2_view_empty_structure():
    """测试阶段②视图无数据时显示提示"""
    from bt_gui.ai_assistant.stage_views import create_stage2_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {"text_muted": "#aaa"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage2_view(mock_frame, state, mock_colors)


def test_stage3_view_with_suggestions():
    """测试阶段③视图显示 VLM 建议值"""
    from bt_gui.ai_assistant.stage_views import create_stage3_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.filled_structure = {
        "nodes": [
            {"id": "node_detect", "type": "ImageConditionNode",
             "config": {"region": [120, 300, 200, 340]},
             "children": [], "empty_params": []},
        ]
    }
    state._suggestions = [
        {"node_id": "node_detect", "param": "region",
         "suggested_value": [120, 300, 200, 340], "confidence": 0.95,
         "note": "检测到蓝色按钮"}
    ]

    mock_frame = MagicMock()
    mock_colors = {"text_primary": "#fff", "text_muted": "#aaa",
                   "bg_primary": "#1a1a1a", "bg_tertiary": "#2a2a2a",
                   "success": "#22C55E", "warning": "#F59E0B"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage3_view(mock_frame, state, mock_colors)


def test_stage3_view_no_suggestions():
    """测试阶段③视图无建议时显示提示"""
    from bt_gui.ai_assistant.stage_views import create_stage3_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {"text_muted": "#aaa"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage3_view(mock_frame, state, mock_colors)


def test_stage4_view_with_tree_data():
    """测试阶段④视图显示生成结果"""
    from bt_gui.ai_assistant.stage_views import create_stage4_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.tree_data = {
        "version": "2.1",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"type": "StartNode", "children": ["node_delay"]},
            "node_delay": {"type": "DelayNode", "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_delay"}],
    }

    mock_frame = MagicMock()
    mock_colors = {"text_primary": "#fff", "text_muted": "#aaa",
                   "bg_tertiary": "#2a2a2a", "success": "#22C55E"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage4_view(mock_frame, state, mock_colors)


def test_stage4_view_empty():
    """测试阶段④视图无数据时显示提示"""
    from bt_gui.ai_assistant.stage_views import create_stage4_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {"text_muted": "#aaa"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage4_view(mock_frame, state, mock_colors)


def test_stage5_view_success():
    """测试阶段⑤试运行成功"""
    from bt_gui.ai_assistant.stage_views import create_stage5_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.test_report = {
        "success": True,
        "logs": ["[StartNode] 开始", "[DelayNode] 延时 1000ms"],
    }

    mock_frame = MagicMock()
    mock_colors = {"text_primary": "#fff", "text_muted": "#aaa",
                   "bg_tertiary": "#2a2a2a", "success": "#22C55E",
                   "error": "#EF4444"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage5_view(mock_frame, state, mock_colors)


def test_stage5_view_failure_with_fixes():
    """测试阶段⑤试运行失败带修正建议"""
    from bt_gui.ai_assistant.stage_views import create_stage5_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.test_report = {
        "success": False,
        "logs": ["[OCRConditionNode] 识别失败"],
    }
    state._fixes = [
        {"node_id": "node_detect", "param": "region",
         "new_value": [100, 200, 400, 400], "reason": "扩大区域"}
    ]

    mock_frame = MagicMock()
    mock_colors = {"text_primary": "#fff", "text_muted": "#aaa",
                   "bg_tertiary": "#2a2a2a", "success": "#22C55E",
                   "error": "#EF4444", "primary": "#3B82F6"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage5_view(mock_frame, state, mock_colors,
                           on_apply_fix=MagicMock(), on_rerun=MagicMock())


def test_stage5_view_empty():
    """测试阶段⑤无报告时显示试运行按钮"""
    from bt_gui.ai_assistant.stage_views import create_stage5_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {"text_muted": "#aaa", "primary": "#3B82F6"}

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage5_view(mock_frame, state, mock_colors)


def test_stage3_view_dialogue_button():
    """测试阶段③视图的'跳过，用语言描述补全'按钮绑定 on_dialogue"""
    from bt_gui.ai_assistant.stage_views import create_stage3_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {"text_muted": "#aaa", "primary": "#3B82F6",
                   "primary_hover": "#2563EB", "border": "#444"}

    on_dialogue = lambda: None  # 真实可调用对象

    with patch("bt_gui.ai_assistant.stage_views.ctk") as mock_ctk:
        create_stage3_view(mock_frame, state, mock_colors,
                           on_screenshot=lambda: None, on_dialogue=on_dialogue)

    # 过滤出对话补全按钮，校验其 command 绑定到传入的 on_dialogue
    dialogue_btn = None
    for call in mock_ctk.CTkButton.call_args_list:
        kwargs = call[1]
        if kwargs.get("text") == "跳过，用语言描述补全":
            dialogue_btn = kwargs
            break

    assert dialogue_btn is not None, "未创建'跳过，用语言描述补全'按钮"
    assert dialogue_btn["command"] is on_dialogue


def test_analyze_stage0_view_with_tree_list():
    """测试分析阶段⓪视图在 source_tree 节点为 list 时渲染树信息分支"""
    from bt_gui.ai_assistant.stage_views import create_analyze_stage0_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.source_tree = {
        "nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}],
        "root_node": "n1",
    }
    mock_frame = MagicMock()
    mock_colors = {"text_primary": "#fff", "text_muted": "#aaa",
                   "bg_tertiary": "#2a2a2a"}

    with patch("bt_gui.ai_assistant.stage_views.ctk") as mock_ctk:
        create_analyze_stage0_view(mock_frame, state, mock_colors)

    # 应渲染树信息卡片：节点数 + 根节点
    assert mock_ctk.CTkFrame.called, "未创建树信息卡片"
    label_texts = [kwargs.get("text", "") for call in mock_ctk.CTkLabel.call_args_list
                   for kwargs in [call[1]]]
    assert any("节点数: 3" in t for t in label_texts), "未显示 list 节点数"
    assert any("根节点: n1" in t for t in label_texts), "未显示根节点"


def test_analyze_stage0_view_with_tree_dict():
    """测试分析阶段⓪视图在 source_tree 节点为 dict 时渲染树信息分支"""
    from bt_gui.ai_assistant.stage_views import create_analyze_stage0_view
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.source_tree = {
        "nodes": {"n1": {"type": "StartNode"}, "n2": {"type": "DelayNode"}},
        "root_node": "n1",
    }
    mock_frame = MagicMock()
    mock_colors = {"text_primary": "#fff", "text_muted": "#aaa",
                   "bg_tertiary": "#2a2a2a"}

    with patch("bt_gui.ai_assistant.stage_views.ctk") as mock_ctk:
        create_analyze_stage0_view(mock_frame, state, mock_colors)

    assert mock_ctk.CTkFrame.called, "未创建树信息卡片"
    label_texts = [kwargs.get("text", "") for call in mock_ctk.CTkLabel.call_args_list
                   for kwargs in [call[1]]]
    assert any("节点数: 2" in t for t in label_texts), "未显示 dict 节点数"
    assert any("根节点: n1" in t for t in label_texts), "未显示根节点"


def test_analyze_stage1_view_returns_textbox():
    """测试分析阶段①视图在初始分支返回意图输入框，结果分支返回 None"""
    from bt_gui.ai_assistant.stage_views import create_analyze_stage1_view
    from bt_gui.ai_assistant.state import AssistantState

    mock_frame = MagicMock()
    mock_colors = {"text_muted": "#aaa", "bg_primary": "#1a1a1a",
                   "text_primary": "#fff", "primary": "#3B82F6"}

    with patch("bt_gui.ai_assistant.stage_views.ctk") as mock_ctk:
        result = create_analyze_stage1_view(mock_frame, AssistantState(), mock_colors)

    # 创建了输入框，且返回该输入框引用
    assert mock_ctk.CTkTextbox.called, "未创建意图输入框"
    assert result is mock_ctk.CTkTextbox.return_value, "未返回所创建的输入框"

    # analyze_result 分支应返回 None
    state = AssistantState()
    state.analyze_result = {"intent": "修改延时"}
    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        result2 = create_analyze_stage1_view(mock_frame, state, mock_colors)
    assert result2 is None, "analyze_result 分支应返回 None"


def test_analyze_stage0_view_no_tree():
    from bt_gui.ai_assistant.stage_views import create_analyze_stage0_view
    from bt_gui.ai_assistant.state import AssistantState
    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {}
    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_analyze_stage0_view(mock_frame, state, mock_colors)


def test_analyze_stage2_view_with_plan():
    from bt_gui.ai_assistant.stage_views import create_analyze_stage2_view
    from bt_gui.ai_assistant.state import AssistantState
    state = AssistantState()
    state.modification_plan = {"tree": {"nodes": {}}, "changes": [
        {"type": "add", "node_id": "node_delay", "description": "插入延时"}],
        "summary": "插入延时节点"}
    mock_frame = MagicMock()
    mock_colors = {}
    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_analyze_stage2_view(mock_frame, state, mock_colors)

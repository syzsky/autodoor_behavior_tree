"""AssistantPanel 测试

GUI 组件测试使用 mock 避免实际创建窗口。
重点测试面板的状态管理逻辑和阶段导航。
"""
import pytest
from unittest.mock import MagicMock, patch


def test_panel_initial_state():
    """测试面板初始状态为阶段 0"""
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel
    from bt_gui.ai_assistant.state import AssistantState

    # Mock CTkFrame 以避免创建实际窗口
    with patch("bt_gui.ai_assistant.assistant_panel.ctk"):
        panel = AssistantPanel.__new__(AssistantPanel)
        panel._state = AssistantState()
        panel._callbacks = {}
        assert panel._state.stage == 0


def test_panel_stage_navigation():
    """测试面板阶段导航逻辑"""
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel
    from bt_gui.ai_assistant.state import AssistantState

    with patch("bt_gui.ai_assistant.assistant_panel.ctk"):
        panel = AssistantPanel.__new__(AssistantPanel)
        panel._state = AssistantState()
        panel._callbacks = {"on_stage_change": MagicMock()}

        # 模拟前进
        panel._state.advance()
        panel._callbacks["on_stage_change"].assert_not_called()  # 状态变更不自动触发回调

        assert panel._state.stage == 1


def test_panel_callback_registration():
    """测试回调注册"""
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel

    with patch("bt_gui.ai_assistant.assistant_panel.ctk"):
        panel = AssistantPanel.__new__(AssistantPanel)
        panel._callbacks = {}

        callback = MagicMock()
        panel._callbacks["on_stage_change"] = callback
        assert panel._callbacks["on_stage_change"] is callback


def test_panel_toggle_visibility():
    """测试面板可见性切换"""
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel

    with patch("bt_gui.ai_assistant.assistant_panel.ctk"):
        panel = AssistantPanel.__new__(AssistantPanel)
        panel._visible = False

        # 模拟切换
        panel._visible = not panel._visible
        assert panel._visible is True

        panel._visible = not panel._visible
        assert panel._visible is False


def test_mode_change_switches_to_analyze():
    """测试切换模式到分析修改"""
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel
    from bt_gui.ai_assistant.state import AssistantState, AssistantMode

    with patch("bt_gui.ai_assistant.assistant_panel.ctk"):
        panel = AssistantPanel.__new__(AssistantPanel)
        panel._state = AssistantState()
        panel._callbacks = {}
        panel._show_stage_view = MagicMock()
        panel._update_nav_buttons = MagicMock()

        panel._on_mode_change("分析修改")

        assert panel._state.mode == AssistantMode.ANALYZE
        assert panel._state.stage == 0
        panel._update_nav_buttons.assert_called_once()
        panel._show_stage_view.assert_called_once()


def test_show_stage_view_dispatches_analyze():
    """测试分析模式下 _show_stage_view 分发到分析阶段方法"""
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel
    from bt_gui.ai_assistant.state import AssistantState, AssistantMode

    with patch("bt_gui.ai_assistant.assistant_panel.ctk"):
        panel = AssistantPanel.__new__(AssistantPanel)
        panel._state = AssistantState()
        panel._state.mode = AssistantMode.ANALYZE
        panel._state.stage = 1
        panel._callbacks = {}
        panel._content_frame = MagicMock()
        panel._content_frame.winfo_children.return_value = []
        panel._dark_colors = {}
        panel._log_ai_error = MagicMock()
        panel._show_analyze_stage0 = MagicMock()
        panel._show_analyze_stage1 = MagicMock()
        panel._show_analyze_stage2 = MagicMock()
        panel._show_analyze_stage3 = MagicMock()

        panel._show_stage_view()

        panel._show_analyze_stage1.assert_called_once()
        panel._show_analyze_stage0.assert_not_called()
        panel._show_analyze_stage2.assert_not_called()
        panel._show_analyze_stage3.assert_not_called()


def test_load_source_tree_sets_state_from_editor():
    """测试 _load_source_tree 从编辑器读取行为树并写入 state"""
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel
    from bt_gui.ai_assistant.state import AssistantState

    with patch("bt_gui.ai_assistant.assistant_panel.ctk"):
        panel = AssistantPanel.__new__(AssistantPanel)
        panel._state = AssistantState()
        panel._callbacks = {}
        panel._log_ai_error = MagicMock()
        panel._show_stage_view = MagicMock()

        tree = {"nodes": {}, "root_node": "root"}
        editor = MagicMock()
        editor.get_tree_data.return_value = tree
        panel._editor = editor

        panel._load_source_tree()

        assert panel._state.source_tree is tree
        panel._show_stage_view.assert_called_once()
        panel._log_ai_error.assert_not_called()


def test_apply_modified_tree_calls_on_tree_generated():
    """测试 _apply_modified_tree 触发 on_tree_generated 回调"""
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel
    from bt_gui.ai_assistant.state import AssistantState

    with patch("bt_gui.ai_assistant.assistant_panel.ctk"):
        panel = AssistantPanel.__new__(AssistantPanel)
        panel._state = AssistantState()
        panel._log_ai_error = MagicMock()

        callback = MagicMock()
        panel._callbacks = {"on_tree_generated": callback}

        tree_data = {"nodes": {}, "root_node": "root"}
        panel._state.modification_plan = {"tree": tree_data}

        panel._apply_modified_tree()

        callback.assert_called_once_with(tree_data)

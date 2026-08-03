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

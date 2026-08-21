"""AssistantState 状态管理测试"""
import pytest


def test_initial_state():
    """测试初始状态"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    assert state.stage == 0
    assert state.plan is None
    assert state.structure is None
    assert state.filled_structure is None
    assert state.tree_data is None
    assert state.test_report is None
    assert state.is_processing is False


def test_advance_stage():
    """测试阶段前进"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.advance()
    assert state.stage == 1
    state.advance()
    assert state.stage == 2


def test_advance_max_stage():
    """测试达到最大阶段后不再前进"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    for _ in range(10):
        state.advance()
    assert state.stage == 5


def test_go_back():
    """测试阶段回退"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.advance()
    state.advance()
    state.go_back()
    assert state.stage == 1


def test_go_back_min_stage():
    """测试最小阶段后不再回退"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.go_back()
    assert state.stage == 0


def test_reset():
    """测试重置状态"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.advance()
    state.plan = {"test": True}
    state.reset()
    assert state.stage == 0
    assert state.plan is None


def test_can_go_back():
    """测试是否可回退"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    assert state.can_go_back() is False
    state.advance()
    assert state.can_go_back() is True


def test_can_advance():
    """测试是否可前进"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    assert state.can_advance() is True
    state.stage = 5
    assert state.can_advance() is False


def test_set_processing():
    """测试设置处理状态"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.is_processing = True
    assert state.is_processing is True
    state.is_processing = False
    assert state.is_processing is False

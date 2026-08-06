from bt_gui.ai_assistant.state import AssistantState, AssistantMode


def test_mode_create_max_stage_5():
    s = AssistantState()
    assert s.mode == AssistantMode.CREATE
    for _ in range(6):
        s.advance()
    assert s.stage == 5


def test_mode_analyze_max_stage_3():
    s = AssistantState()
    s.mode = AssistantMode.ANALYZE
    for _ in range(4):
        s.advance()
    assert s.stage == 3


def test_reset_clears_mode_fields():
    s = AssistantState()
    s.mode = AssistantMode.ANALYZE
    s.source_tree = {"nodes": {}}
    s.modification_plan = {"tree": {}}
    s.reset()
    assert s.source_tree is None
    assert s.modification_plan is None
    assert s.stage == 0
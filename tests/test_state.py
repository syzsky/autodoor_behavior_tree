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


def test_clear_transient_clears_only_transient_attrs():
    """clear_transient 清空全部瞬时下划线属性，且不动永久字段（plan/structure/tree_data）"""
    s = AssistantState()
    # 瞬时属性预置为真值
    s._suggestions = [{"node_id": "n1"}]
    s._dialogue_questions = [{"node_id": "n1"}]
    s._fixes = [{"node_id": "n1"}]
    s._errors = ["err"]
    s._error = "boom"
    s._analysis = "分析文本"
    # 永久字段预置为真值
    s.plan = {"task_summary": "x"}
    s.structure = {"nodes": []}
    s.tree_data = {"nodes": {}}

    s.clear_transient()

    # 瞬时属性全部清空
    for attr in ('_suggestions', '_dialogue_questions', '_fixes', '_errors', '_error', '_analysis'):
        assert getattr(s, attr, None) is None, f"{attr} 未清空"
    # 永久字段不被清空
    assert s.plan == {"task_summary": "x"}
    assert s.structure == {"nodes": []}
    assert s.tree_data == {"nodes": {}}


def test_transient_attrs_init_to_none():
    """瞬时下划线属性在 __init__ 即声明为 None"""
    s = AssistantState()
    for attr in ('_suggestions', '_dialogue_questions', '_fixes', '_errors', '_error', '_analysis'):
        assert getattr(s, attr, None) is None, f"{attr} 初始值应为 None"
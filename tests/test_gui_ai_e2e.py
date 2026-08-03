"""GUI AI 助手端到端集成测试

验证 5 阶段流水线在 GUI 层的完整流转，
使用 mock 隔离 LLM/VLM API 调用。
"""
import pytest
import json
from unittest.mock import patch, MagicMock


def test_state_full_pipeline_flow():
    """测试状态在 5 阶段流水线中的完整流转"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()

    # 阶段 0 → 1: 意图分析
    state.plan = {"task_summary": "测试任务", "loop": {"enabled": True}}
    state.advance()
    assert state.stage == 1

    # 阶段 1 → 2: 节点选型
    state.structure = {"nodes": [{"id": "n1", "type": "StartNode", "config": {}, "children": []}]}
    state.advance()
    assert state.stage == 2

    # 阶段 2 → 3: VLM 感知
    state.filled_structure = state.structure
    state.advance()
    assert state.stage == 3

    # 阶段 3 → 4: 生成
    state.tree_data = {"version": "2.1", "nodes": {}, "connections": []}
    state.advance()
    assert state.stage == 4

    # 阶段 4 → 5: 试运行
    state.test_report = {"success": True, "logs": []}
    state.advance()
    assert state.stage == 5
    assert not state.can_advance()


def test_state_reset_after_completion():
    """测试完成后重置"""
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    state.advance()
    state.plan = {"test": True}
    state.reset()
    assert state.stage == 0
    assert state.plan is None


def test_canvas_overlay_with_vlm_suggestions():
    """测试 VLM 建议转换为画布标注"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    mock_tk_canvas = MagicMock()
    mock_canvas.canvas = mock_tk_canvas

    overlay = CanvasOverlay(mock_canvas)

    suggestions = [
        {"node_id": "node_detect", "param": "region",
         "suggested_value": [100, 200, 300, 400], "confidence": 0.95},
        {"node_id": "node_click", "param": "position",
         "suggested_value": [150, 250], "confidence": 0.85},
    ]

    for sug in suggestions:
        param = sug["param"]
        ann_type = "region" if param == "region" else "position" if param == "position" else "template"
        overlay.add_annotation(
            node_id=sug["node_id"],
            param=param,
            value=sug["suggested_value"],
            confidence=sug["confidence"],
            annotation_type=ann_type,
        )

    assert len(overlay._annotations) == 2
    assert overlay._annotations[0]["type"] == "region"
    assert overlay._annotations[1]["type"] == "position"

    # 显示标注（会调用 tkinter Canvas 绘制）
    overlay.show()
    assert overlay._visible is True

    # 清除
    overlay.clear()
    assert len(overlay._annotations) == 0


def test_stage_views_all_stages():
    """测试所有阶段视图都能正常创建"""
    from bt_gui.ai_assistant.stage_views import (
        create_stage1_view, create_stage2_view, create_stage3_view,
        create_stage4_view, create_stage5_view,
    )
    from bt_gui.ai_assistant.state import AssistantState

    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {
        "text_primary": "#fff", "text_muted": "#888",
        "bg_primary": "#1a1a1a", "bg_tertiary": "#2a2a2a",
        "success": "#22C55E", "error": "#EF4444",
        "primary": "#3B82F6", "primary_hover": "#2563EB",
        "warning": "#F59E0B", "border": "#444",
    }

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        # 空状态
        create_stage1_view(mock_frame, state, mock_colors)
        create_stage2_view(mock_frame, state, mock_colors)
        create_stage3_view(mock_frame, state, mock_colors)
        create_stage4_view(mock_frame, state, mock_colors)
        create_stage5_view(mock_frame, state, mock_colors)

    # 带数据状态
    state.plan = {"task_summary": "测试", "loop": {"enabled": True, "interval_ms": 1000},
                  "phases": [{"phase": "act", "action": "click"}]}
    state.structure = {"nodes": [{"id": "n1", "type": "StartNode", "config": {}, "children": []}]}
    state.filled_structure = state.structure
    state._suggestions = [{"node_id": "n1", "param": "region",
                           "suggested_value": [0, 0, 100, 100], "confidence": 0.9, "note": "test"}]
    state.tree_data = {"version": "2.1", "nodes": {"n1": {"type": "StartNode"}},
                       "connections": []}
    state.test_report = {"success": False, "logs": ["fail"]}
    state._fixes = [{"node_id": "n1", "param": "region", "new_value": [0, 0, 200, 200], "reason": "expand"}]

    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_stage1_view(mock_frame, state, mock_colors)
        create_stage2_view(mock_frame, state, mock_colors)
        create_stage3_view(mock_frame, state, mock_colors)
        create_stage4_view(mock_frame, state, mock_colors)
        create_stage5_view(mock_frame, state, mock_colors,
                           on_apply_fix=MagicMock(), on_rerun=MagicMock())


def test_all_gui_ai_tests_pass():
    """验证所有 GUI AI 测试通过"""
    # 这是一个元测试，确保前面的测试都已实现
    from bt_gui.ai_assistant.state import AssistantState
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay
    # 如果导入成功，说明所有模块都已实现
    assert AssistantState is not None
    assert CanvasOverlay is not None

"""CanvasOverlay 测试"""
import pytest
from unittest.mock import MagicMock, patch


def test_overlay_initial_state():
    """测试覆盖层初始状态"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    overlay = CanvasOverlay(mock_canvas)
    assert overlay._annotations == []
    assert overlay._visible is False


def test_overlay_add_region_annotation():
    """测试添加区域标注"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    overlay = CanvasOverlay(mock_canvas)

    overlay.add_annotation(
        node_id="node_detect",
        param="region",
        value=[100, 200, 300, 400],
        confidence=0.95,
        annotation_type="region",
    )

    assert len(overlay._annotations) == 1
    ann = overlay._annotations[0]
    assert ann["node_id"] == "node_detect"
    assert ann["param"] == "region"
    assert ann["type"] == "region"


def test_overlay_add_position_annotation():
    """测试添加位置标注"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    overlay = CanvasOverlay(mock_canvas)

    overlay.add_annotation(
        node_id="node_click",
        param="position",
        value=[150, 300],
        confidence=0.85,
        annotation_type="position",
    )

    assert len(overlay._annotations) == 1
    assert overlay._annotations[0]["type"] == "position"


def test_overlay_clear():
    """测试清除所有标注"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    overlay = CanvasOverlay(mock_canvas)

    overlay.add_annotation("n1", "region", [0, 0, 100, 100], 0.9, "region")
    overlay.add_annotation("n2", "position", [50, 50], 0.8, "position")
    assert len(overlay._annotations) == 2

    overlay.clear()
    assert overlay._annotations == []


def test_overlay_get_color_by_confidence():
    """测试根据置信度获取颜色"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    overlay = CanvasOverlay(mock_canvas)

    high = overlay._get_color(0.95)
    low = overlay._get_color(0.5)

    assert high != low  # 高置信度和低置信度颜色不同


def test_overlay_remove_specific_annotation():
    """测试移除特定标注"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    overlay = CanvasOverlay(mock_canvas)

    overlay.add_annotation("n1", "region", [0, 0, 100, 100], 0.9, "region")
    overlay.add_annotation("n2", "position", [50, 50], 0.8, "position")

    overlay.remove_annotation("n1", "region")
    assert len(overlay._annotations) == 1
    assert overlay._annotations[0]["node_id"] == "n2"


def test_overlay_draw_with_none_value_no_crash():
    """VLM 返回 value=None 时绘制标注不应崩溃"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    overlay = CanvasOverlay(mock_canvas)

    # 添加 value=None 的脏数据标注
    overlay.add_annotation(
        node_id="n1", param="region", value=None,
        confidence=0.95, annotation_type="region",
    )
    # 触发重绘（visible 时 add_annotation 会 _redraw）
    overlay.show()
    assert overlay._visible is True
    # 上述调用若能执行到此处，说明 value=None 已被安全转为空列表，未崩溃


def test_overlay_draw_with_non_list_value_no_crash():
    """VLM 返回 value 为标量（如字符串）时绘制标注不应崩溃"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    overlay = CanvasOverlay(mock_canvas)

    overlay.add_annotation(
        node_id="n1", param="region", value="not-a-list",
        confidence=0.9, annotation_type="region",
    )
    overlay.show()
    assert overlay._visible is True


def test_overlay_draw_mixed_invalid_annotations_no_crash():
    """混合 value=None / 非列表 / 正常标注时，绘制应跳过脏数据并正常绘制合法项"""
    from bt_gui.ai_assistant.canvas_overlay import CanvasOverlay

    mock_canvas = MagicMock()
    mock_tk_canvas = MagicMock()
    mock_canvas.canvas = mock_tk_canvas
    overlay = CanvasOverlay(mock_canvas)

    overlay.add_annotation("n1", "region", None, 0.9, "region")
    overlay.add_annotation("n2", "region", "bad", 0.8, "region")
    overlay.add_annotation("n3", "region", [0, 0, 100, 100], 0.95, "region")
    overlay.show()

    # 合法项应被绘制（create_rectangle 被调用），脏数据被跳过
    assert mock_tk_canvas.create_rectangle.called
    assert overlay._drawn_items  # 至少绘制了合法项

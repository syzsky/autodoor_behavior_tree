"""画布区域标注覆盖层

在 BehaviorTreeCanvas 上叠加半透明标注，
标识 VLM 识别到的 region/position 等参数。
"""
from typing import List, Dict, Any, Optional


class CanvasOverlay:
    """画布标注覆盖层

    标注层独立于节点图形，不参与节点选择/连线逻辑。
    """

    # 标注颜色
    COLOR_HIGH_CONFIDENCE = "#22C55E"  # 绿色（>=80%）
    COLOR_LOW_CONFIDENCE = "#F59E0B"   # 橙色（<80%）
    COLOR_POSITION = "#3B82F6"          # 蓝色
    COLOR_TEMPLATE = "#A855F7"          # 紫色

    def __init__(self, canvas):
        """
        Args:
            canvas: BehaviorTreeCanvas 实例（或其内部的 tkinter Canvas）
        """
        self._canvas = canvas
        self._annotations: List[Dict[str, Any]] = []
        self._visible = False
        self._drawn_items: List[int] = []  # tkinter Canvas item IDs

    def add_annotation(self, node_id: str, param: str, value: Any,
                       confidence: float = 1.0,
                       annotation_type: str = "region"):
        """添加一个标注

        Args:
            node_id: 节点 ID
            param: 参数名
            value: 参数值（region: [x1,y1,x2,y2], position: [x,y]）
            confidence: 置信度 0-1
            annotation_type: "region" | "position" | "template"
        """
        self._annotations.append({
            "node_id": node_id,
            "param": param,
            "value": value,
            "confidence": confidence,
            "type": annotation_type,
        })

        if self._visible:
            self._redraw()

    def remove_annotation(self, node_id: str, param: str):
        """移除特定标注"""
        self._annotations = [
            a for a in self._annotations
            if not (a["node_id"] == node_id and a["param"] == param)
        ]
        if self._visible:
            self._redraw()

    def clear(self):
        """清除所有标注"""
        self._annotations = []
        self._clear_drawn()

    def show(self):
        """显示标注"""
        self._visible = True
        self._redraw()

    def hide(self):
        """隐藏标注"""
        self._visible = False
        self._clear_drawn()

    def _redraw(self):
        """重绘所有标注"""
        self._clear_drawn()

        if not self._visible:
            return

        for ann in self._annotations:
            self._draw_annotation(ann)

    def _draw_annotation(self, ann: Dict[str, Any]):
        """绘制单个标注"""
        tk_canvas = self._get_tk_canvas()
        if tk_canvas is None:
            return

        ann_type = ann.get("type", "region")
        value = ann.get("value", [])
        confidence = ann.get("confidence", 1.0)

        if ann_type == "region" and len(value) >= 4:
            x1, y1, x2, y2 = value[:4]
            color = self._get_color(confidence)

            # 半透明矩形（用 stipple 模拟）
            rect_id = tk_canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=color,
                width=2,
                fill=color,
                stipple="gray25",
            )
            self._drawn_items.append(rect_id)

            # 置信度文本
            text_id = tk_canvas.create_text(
                x1, y1 - 8,
                text=f"{ann['node_id']}.{ann['param']} ({confidence:.0%})",
                fill=color,
                font=("Arial", 9),
                anchor="s",
            )
            self._drawn_items.append(text_id)

        elif ann_type == "position" and len(value) >= 2:
            x, y = value[:2]
            color = self.COLOR_POSITION
            r = 8

            # 圆形标记
            oval_id = tk_canvas.create_oval(
                x - r, y - r, x + r, y + r,
                outline=color,
                width=2,
                fill=color,
                stipple="gray25",
            )
            self._drawn_items.append(oval_id)

            # 十字线
            cross_h = tk_canvas.create_line(x - r - 4, y, x + r + 4, y, fill=color, width=1)
            cross_v = tk_canvas.create_line(x, y - r - 4, x, y + r + 4, fill=color, width=1)
            self._drawn_items.extend([cross_h, cross_v])

            text_id = tk_canvas.create_text(
                x + r + 4, y - r - 4,
                text=f"{ann['node_id']}.{ann['param']}",
                fill=color,
                font=("Arial", 9),
                anchor="sw",
            )
            self._drawn_items.append(text_id)

        elif ann_type == "template" and len(value) >= 4:
            x1, y1, x2, y2 = value[:4]
            color = self.COLOR_TEMPLATE

            rect_id = tk_canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=color,
                width=2,
            )
            self._drawn_items.append(rect_id)

    def _clear_drawn(self):
        """清除已绘制的项"""
        tk_canvas = self._get_tk_canvas()
        if tk_canvas is None:
            return

        for item_id in self._drawn_items:
            try:
                tk_canvas.delete(item_id)
            except Exception:
                pass
        self._drawn_items = []

    def _get_color(self, confidence: float) -> str:
        """根据置信度获取颜色"""
        if confidence >= 0.8:
            return self.COLOR_HIGH_CONFIDENCE
        return self.COLOR_LOW_CONFIDENCE

    def _get_tk_canvas(self):
        """获取 tkinter Canvas 对象"""
        # BehaviorTreeCanvas 内部的 tkinter Canvas
        if hasattr(self._canvas, 'canvas'):
            return self._canvas.canvas
        # 如果直接传入 tkinter Canvas
        if hasattr(self._canvas, 'create_rectangle'):
            return self._canvas
        return None

    def get_annotations(self) -> List[Dict[str, Any]]:
        """获取所有标注"""
        return list(self._annotations)

    def update_annotation_value(self, node_id: str, param: str, new_value: Any):
        """更新标注值（拖拽微调后调用）"""
        for ann in self._annotations:
            if ann["node_id"] == node_id and ann["param"] == param:
                ann["value"] = new_value
                if self._visible:
                    self._redraw()
                return

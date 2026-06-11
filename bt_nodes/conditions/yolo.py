"""
YOLO 目标检测条件节点

基于 YOLO 模型检测截图中是否出现指定类别的目标。
检测到目标 → SUCCESS，未检测到 → FAILURE。

依赖: ultralytics (pip install ultralytics)
"""
from bt_core.nodes import ConditionNode
from bt_core.config import NodeConfig
from typing import Dict, Any, Optional
import os


class YOLOConditionNode(ConditionNode):
    """YOLO 目标检测条件节点

    配置参数:
    - model_path: YOLO 模型文件路径 (.pt)
    - classes: 目标类别 ID 列表（逗号分隔），空=检测所有类别
    - class_names: 目标类别名称列表（逗号分隔），与 classes 二选一
    - confidence: 置信度阈值 (0-100)
    - match_mode: 匹配模式 (any=任一目标 / count=数量条件)
    - min_count: 最小目标数量 (match_mode=count 时生效)
    - position_key: 位置变量名（保存第一个检测到的坐标）
    - position_key_all: 全部位置变量名（保存所有检测到的坐标列表）
    """

    NODE_TYPE = "YOLOConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.model_path = self.config.get("model_path", "")
        self.confidence = self.config.get_int("confidence", 50) / 100.0
        self.classes_str = self.config.get("classes", "")
        self.class_names_str = self.config.get("class_names", "")
        self.match_mode = self.config.get("match_mode", "any")
        self.min_count = self.config.get_int("min_count", 1)
        self.position_key = self.config.get("position_key", "")

    def _check_condition(self, context) -> bool:
        from bt_utils.yolo_detector import YOLODetector

        detector = YOLODetector.get_instance()

        if not detector.is_available():
            self._log_condition_result(False, "YOLO 不可用，请安装 ultralytics: pip install ultralytics")
            return False

        model_path = self._resolve_model_path(context)
        if not model_path or not os.path.exists(model_path):
            self._log_condition_result(False, f"模型文件不存在: {self.model_path}")
            return False

        if not detector.load_model(model_path):
            self._log_condition_result(False, f"无法加载模型: {model_path}")
            return False

        screenshot = self._get_region_image(context)
        if screenshot is None:
            return False

        try:
            confidence = self.config.get_int("confidence", 50) / 100.0
            class_ids = self._parse_classes(detector)
            match_mode = self.config.get("match_mode", "any")
            min_count = self.config.get_int("min_count", 1)

            detections = detector.detect(screenshot, conf=confidence, classes=class_ids)

            found = len(detections) > 0
            count_ok = len(detections) >= min_count

            if found and (match_mode == "any" or (match_mode == "count" and count_ok)):
                self._save_detection_positions(detections, screenshot, context)
                detail = ", ".join(
                    f"{d['class_name']}({d['confidence']:.0%})"
                    for d in detections[:3]
                )
                suffix = f" [{detail}]" if detail else ""
                self._log_condition_result(True, f"检测到 {len(detections)} 个目标{suffix}")
                return True
            else:
                reason = (
                    f"检测到 {len(detections)} 个目标，不满足最小数量条件 {min_count}"
                    if found and match_mode == "count"
                    else "未检测到目标"
                )
                self._log_condition_result(False, reason)
                return False

        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"YOLOConditionNode '{self.name}'")
            self._log_condition_result(False, "检测异常，详情见终端日志")
            return False

    def _resolve_model_path(self, context) -> Optional[str]:
        """解析模型路径"""
        model_path = self.config.get("model_path", "")
        if not model_path:
            return None

        if model_path.startswith("./") and hasattr(context, 'resolve_path'):
            return context.resolve_path(model_path)

        if os.path.isabs(model_path):
            return model_path

        # 先搜索项目 models 目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(project_root, "models", model_path)
        if os.path.exists(candidate):
            return candidate

        return model_path

    def _parse_classes(self, detector) -> Optional[list]:
        """解析目标类别列表

        支持两种方式：
        1. classes: 数字 ID 列表（逗号分隔），如 "0,1,2"
        2. class_names: 名称列表（逗号分隔），如 "person,car"，自动映射 ID
        """
        classes_str = self.config.get("classes", "").strip()
        class_names_str = self.config.get("class_names", "").strip()

        if class_names_str:
            # 名称模式：通过 model.names 映射
            name_to_id = {}
            if detector._model and hasattr(detector._model, 'names'):
                name_to_id = {v.lower(): k for k, v in detector._model.names.items()}
            ids = []
            for name in [n.strip().lower() for n in class_names_str.split(",")]:
                if name and name in name_to_id:
                    ids.append(name_to_id[name])
            return ids if ids else None

        if classes_str:
            try:
                return [int(x.strip()) for x in classes_str.split(",") if x.strip()]
            except ValueError:
                return None

        return None

    def _save_detection_positions(self, detections: list, region_img, context) -> None:
        region = self._get_effective_region(context) if context else None
        offset_x = region[0] if region else 0
        offset_y = region[1] if region else 0

        # 保存第一个目标的位置
        if detections:
            cx = int(detections[0]["center"][0]) + offset_x
            cy = int(detections[0]["center"][1]) + offset_y
            self._save_position(context, (cx, cy))

            # 保存所有目标位置
            pos_key_all = self.config.get("position_key_all", "")
            if pos_key_all:
                all_positions = [
                    (int(d["center"][0]) + offset_x, int(d["center"][1]) + offset_y)
                    for d in detections
                ]
                if context and hasattr(context, 'blackboard'):
                    context.blackboard.set(pos_key_all, all_positions)

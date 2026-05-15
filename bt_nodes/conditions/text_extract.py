from bt_core.nodes import ConditionNode
from bt_core.config import NodeConfig
from typing import Dict, Any, Tuple, Optional
from bt_utils.log_manager import LogManager
from bt_utils.ocr_manager import OCRManager


LANGUAGE_MAP = {
    "English": "eng",
    "简体中文": "chi_sim",
    "繁体中文": "chi_tra",
    "eng": "eng",
    "chi_sim": "chi_sim",
    "chi_tra": "chi_tra",
}


class TextExtractNode(ConditionNode):
    NODE_TYPE = "TextExtractNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.extract_mode = self.config.get("extract_mode", "all")
        self.region: Optional[Tuple[int, int, int, int]] = self._parse_region(
            self.config.get("region", None)
        )
        self.keywords = self.config.get("keywords", "")
        language_display = self.config.get("language", "简体中文")
        self.language = LANGUAGE_MAP.get(language_display, "chi_sim")
        preprocess_display = self.config.get("preprocess_mode", "默认")
        self.preprocess_mode = "game" if preprocess_display == "复杂色彩" else "normal"
        self.output_key = self.config.get("output_key", "last_extracted_text")
        self.save_all_text = self.config.get_bool("save_all_text", False)
        self.all_text_key = self.config.get("all_text_key", "all_ocr_text")
        self.save_position = self.config.get_bool("save_position", True)
        self.position_key = self.config.get("position_key", "last_detection_position")

    def _check_condition(self, context) -> bool:
        try:
            screenshot = self._get_region_image(context)
            if screenshot is None:
                return False

            ocr_manager = OCRManager()
            all_text = ocr_manager.get_all_text(
                screenshot, self.language, self.preprocess_mode
            )

            if not all_text:
                self._log_condition_result(False, "未识别到文本")
                return False

            if self.extract_mode == "all":
                extracted_text = all_text
            else:
                extracted_text = self._extract_keywords_text(all_text, self.keywords)

            context.blackboard.set(self.output_key, extracted_text)

            if self.save_all_text:
                context.blackboard.set(self.all_text_key, all_text)

            if self.save_position and self.region:
                center_x = (self.region[0] + self.region[2]) // 2
                center_y = (self.region[1] + self.region[3]) // 2
                self._save_position(context, (center_x, center_y))

            if extracted_text:
                self._log_condition_result(True)
                LogManager.instance().log_info(
                    node_type="文本提取节点",
                    node_name=self.name,
                    message=f"提取文本: {extracted_text[:50]}..."
                )
                return True
            else:
                self._log_condition_result(False, "未提取到匹配的文本")
                return False

        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"TextExtractNode '{self.name}'")
            self._log_condition_result(False, "执行异常，详情见终端日志")
            return False

    def _extract_keywords_text(self, all_text: str, keywords: str) -> str:
        lines = all_text.split('\n')
        matched_lines = []

        for line in lines:
            line = line.strip()
            if line and keywords in line:
                matched_lines.append(line)

        return '\n'.join(matched_lines)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["config"]["extract_mode"] = self.extract_mode
        data["config"]["region"] = list(self.region) if self.region else None
        data["config"]["keywords"] = self.keywords
        reverse_language_map = {"eng": "English", "chi_sim": "简体中文", "chi_tra": "繁体中文"}
        data["config"]["language"] = reverse_language_map.get(self.language, self.language)
        data["config"]["preprocess_mode"] = "复杂色彩" if self.preprocess_mode == "game" else "默认"
        data["config"]["output_key"] = self.output_key
        data["config"]["save_all_text"] = self.save_all_text
        data["config"]["all_text_key"] = self.all_text_key
        data["config"]["save_position"] = self.save_position
        data["config"]["position_key"] = self.position_key
        data["config"]["offset"] = list(self.offset)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextExtractNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        return node

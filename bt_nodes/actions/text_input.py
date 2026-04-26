import time
import os
import random
import pyperclip
from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any, List
from bt_utils.log_manager import LogManager


INPUT_MODE_MAP = {
    "文本提取值": "extracted",
    "预设文本": "preset",
    "文件": "file",
    "extracted": "extracted",
    "preset": "preset",
    "file": "file",
}

EXECUTION_MODE_MAP = {
    "顺序": "sequential",
    "随机": "random",
    "sequential": "sequential",
    "random": "random",
}


class TextInputNode(ActionNode):
    NODE_TYPE = "TextInputNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        input_mode_display = self.config.get("input_mode", "文本提取值")
        self.input_mode = INPUT_MODE_MAP.get(input_mode_display, "extracted")
        self.preset_texts: List[str] = self.config.get("preset_texts", [])
        execution_mode_display = self.config.get("execution_mode", "顺序")
        self.execution_mode = EXECUTION_MODE_MAP.get(execution_mode_display, "sequential")
        self.blackboard_key = self.config.get("blackboard_key", "last_extracted_text")
        self.file_path = self.config.get("file_path", "")
        self.input_delay = self.config.get_int("input_delay", 50)
        self.clear_before_input = self.config.get_bool("clear_before_input", False)
        self.save_input_text = self.config.get_bool("save_input_text", False)
        self.output_key = self.config.get("output_key", "last_input_text")
        
        LogManager.debug_print(
            f"[TextInputNode] 初始化: node_id={self.node_id}, name={self.name}, "
            f"input_mode={self.input_mode}, execution_mode={self.execution_mode}, "
            f"blackboard_key={self.blackboard_key}, file_path={self.file_path}, "
            f"input_delay={self.input_delay}, clear_before_input={self.clear_before_input}, "
            f"preset_texts_count={len(self.preset_texts)}"
        )

    def _execute_action(self, context) -> NodeStatus:
        try:
            LogManager.debug_print(
                f"[TextInputNode] '{self.name}' 开始执行: input_mode={self.input_mode}"
            )
            
            text = self._get_text(context)
            if not text:
                LogManager.debug_print(f"[TextInputNode] '{self.name}' 未获取到文本内容")
                LogManager.instance().log_failure(
                    node_type="文本输入节点",
                    node_name=self.name,
                    reason="未获取到文本内容"
                )
                return NodeStatus.FAILURE

            LogManager.debug_print(
                f"[TextInputNode] '{self.name}' 获取文本成功, 长度={len(text)}, 内容预览: {text[:100]}..."
            )

            if self.clear_before_input:
                LogManager.debug_print(f"[TextInputNode] '{self.name}' 执行输入前清空 (Ctrl+A)")
                context.execute_key_press("ctrl", "down", 0)
                context.execute_key_press("a", "press", 0)
                context.execute_key_press("ctrl", "up", 0)
                time.sleep(0.1)

            LogManager.debug_print(
                f"[TextInputNode] '{self.name}' 开始输入文本, input_delay={self.input_delay}ms"
            )
            self._input_text(context, text)

            if self.save_input_text:
                context.blackboard.set(self.output_key, text)
                LogManager.debug_print(
                    f"[TextInputNode] '{self.name}' 保存输入文本到黑板: {self.output_key}"
                )

            LogManager.instance().log_success(
                node_type="文本输入节点",
                node_name=self.name
            )

            return NodeStatus.SUCCESS

        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"TextInputNode '{self.name}'")
            LogManager.instance().log_failure(
                node_type="文本输入节点",
                node_name=self.name,
                reason="执行异常，详情见终端日志"
            )
            return NodeStatus.FAILURE

    def _get_text(self, context) -> str:
        if self.input_mode == "preset":
            LogManager.debug_print(
                f"[TextInputNode] '{self.name}' 预设文本模式: preset_texts_count={len(self.preset_texts)}, execution_mode={self.execution_mode}"
            )
            if not self.preset_texts:
                LogManager.debug_print(f"[TextInputNode] '{self.name}' 预设文本列表为空")
                return ""
            if self.execution_mode == "sequential":
                text = self._get_next_preset_text(context)
                LogManager.debug_print(f"[TextInputNode] '{self.name}' 顺序获取预设文本: {text[:50] if text else '(空)'}...")
                return text
            else:
                text = self._get_random_preset_text()
                LogManager.debug_print(f"[TextInputNode] '{self.name}' 随机获取预设文本: {text[:50] if text else '(空)'}...")
                return text

        elif self.input_mode == "extracted":
            text = context.blackboard.get(self.blackboard_key, "")
            LogManager.debug_print(
                f"[TextInputNode] '{self.name}' 文本提取值模式: blackboard_key={self.blackboard_key}, 获取值长度={len(text)}"
            )
            return text

        elif self.input_mode == "file":
            LogManager.debug_print(
                f"[TextInputNode] '{self.name}' 文件模式: file_path={self.file_path}"
            )
            text = self._read_file(context)
            LogManager.debug_print(
                f"[TextInputNode] '{self.name}' 文件读取结果: 长度={len(text) if text else 0}"
            )
            return text

        LogManager.debug_print(f"[TextInputNode] '{self.name}' 未知输入模式: {self.input_mode}")
        return ""

    def _get_next_preset_text(self, context) -> str:
        index_key = f"{self.node_id}_text_index"
        current_index = context.blackboard.get(index_key, 0)
        
        LogManager.debug_print(
            f"[TextInputNode] '{self.name}' 顺序获取: index_key={index_key}, current_index={current_index}, total_texts={len(self.preset_texts)}"
        )
        
        text = self.preset_texts[current_index % len(self.preset_texts)]
        
        next_index = (current_index + 1) % len(self.preset_texts)
        context.blackboard.set(index_key, next_index)
        
        LogManager.debug_print(
            f"[TextInputNode] '{self.name}' 顺序获取结果: index={current_index}, next_index={next_index}, text={text[:30] if text else '(空)'}..."
        )
        
        return text

    def _get_random_preset_text(self) -> str:
        selected_index = random.randint(0, len(self.preset_texts) - 1)
        text = self.preset_texts[selected_index]
        
        LogManager.debug_print(
            f"[TextInputNode] '{self.name}' 随机获取: selected_index={selected_index}, total_texts={len(self.preset_texts)}, text={text[:30] if text else '(空)'}..."
        )
        
        return text

    def _read_file(self, context) -> str:
        if not self.file_path:
            LogManager.debug_print(f"[TextInputNode] '{self.name}' 文件路径为空")
            return ""
        
        file_path = self.file_path
        if not os.path.isabs(file_path):
            file_path = context.resolve_path(file_path)
            LogManager.debug_print(f"[TextInputNode] '{self.name}' 相对路径转绝对路径: {file_path}")
        
        LogManager.debug_print(f"[TextInputNode] '{self.name}' 尝试读取文件: {file_path}")
        
        if not os.path.exists(file_path):
            LogManager.debug_print(f"[TextInputNode] '{self.name}' 文件不存在: {file_path}")
            LogManager.instance().log_failure(
                node_type="文本输入节点",
                node_name=self.name,
                reason=f"文件不存在: {self.file_path}"
            )
            return ""
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            LogManager.debug_print(f"[TextInputNode] '{self.name}' 文件读取成功, 内容长度={len(content)}")
            return content
        except Exception as e:
            LogManager.debug_print(f"[TextInputNode] '{self.name}' 文件读取失败: {e}")
            return ""

    def _input_text(self, context, text: str) -> None:
        char_count = 0
        LogManager.debug_print(
            f"[TextInputNode] '{self.name}' 开始逐字符输入, 总字符数={len(text)}"
        )
        
        for char in text:
            if not context.check_running():
                LogManager.debug_print(
                    f"[TextInputNode] '{self.name}' 输入中断: 行为树已停止, 已输入字符数={char_count}"
                )
                break

            if char == "\n":
                context.execute_key_press("enter", "press", 0)
            elif char == "\t":
                context.execute_key_press("tab", "press", 0)
            else:
                pyperclip.copy(char)
                context.execute_key_press("ctrl", "down", 0)
                context.execute_key_press("v", "press", 0)
                context.execute_key_press("ctrl", "up", 0)

            char_count += 1
            if self.input_delay > 0:
                time.sleep(self.input_delay / 1000.0)
        
        LogManager.debug_print(
            f"[TextInputNode] '{self.name}' 输入完成, 实际输入字符数={char_count}"
        )

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        reverse_input_mode = {"extracted": "文本提取值", "preset": "预设文本", "file": "文件"}
        data["config"]["input_mode"] = reverse_input_mode.get(self.input_mode, self.input_mode)
        data["config"]["preset_texts"] = self.preset_texts
        reverse_execution_mode = {"sequential": "顺序", "random": "随机"}
        data["config"]["execution_mode"] = reverse_execution_mode.get(self.execution_mode, self.execution_mode)
        data["config"]["blackboard_key"] = self.blackboard_key
        data["config"]["file_path"] = self.file_path
        data["config"]["input_delay"] = self.input_delay
        data["config"]["clear_before_input"] = self.clear_before_input
        data["config"]["save_input_text"] = self.save_input_text
        data["config"]["output_key"] = self.output_key
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextInputNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        return node

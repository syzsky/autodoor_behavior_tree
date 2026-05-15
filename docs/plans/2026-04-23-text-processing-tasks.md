# 文本处理功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 AutoDoor 行为树系统新增文本输入和文本提取功能，实现动态文本交互。

**Architecture:** 采用新增独立节点的方式实现。新增 TextInputNode（文本输入节点）和 TextExtractNode（文本提取节点），通过黑板系统集成。

**Tech Stack:** Python 3.10+, RapidOCR, ONNX Runtime, pyperclip

---

## Task 1: 创建文本输入节点

**Files:**
- Create: `bt_nodes/actions/text_input.py`

**Step 1: 创建 TextInputNode 类**

```python
from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any, Tuple, Optional, List
from bt_utils.log_manager import LogManager
import os
import random
import time


class TextInputNode(ActionNode):
    """文本输入节点
    
    向目标位置输入文本，支持多种输入源和执行模式
    """
    NODE_TYPE = "TextInputNode"
    
    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.input_mode = self.config.get("input_mode", "preset")
        self.preset_texts: List[str] = self.config.get("preset_texts", [])
        self.execution_mode = self.config.get("execution_mode", "sequential")
        self.blackboard_key = self.config.get("blackboard_key", "extracted_text")
        self.file_path = self.config.get("file_path", "")
        self.position: Optional[Tuple[int, int]] = self.config.get("position", None)
        self.use_blackboard = self.config.get_bool("use_blackboard", False)
        self.position_key = self.config.get("position_key", "last_detection_position")
        self.input_delay = self.config.get_int("input_delay", 50)
        self.clear_before_input = self.config.get_bool("clear_before_input", False)
        self.save_input_text = self.config.get_bool("save_input_text", False)
        self.output_key = self.config.get("output_key", "last_input_text")
        self._current_text_index = 0
    
    def _execute_action(self, context) -> NodeStatus:
        try:
            text = self._get_text(context)
            if not text:
                LogManager.instance().log_failure(
                    node_type="文本输入节点",
                    node_name=self.name,
                    reason="未获取到文本内容"
                )
                return NodeStatus.FAILURE
            
            if self.use_blackboard:
                position = context.blackboard.get(self.position_key)
            else:
                position = self.position
            
            if position:
                context.execute_mouse_move(position)
                time.sleep(0.1)
            
            if self.clear_before_input:
                context.execute_key_press("ctrl", action="down")
                context.execute_key_press("a", action="press")
                context.execute_key_press("ctrl", action="up")
                time.sleep(0.1)
            
            self._input_text(context, text)
            
            if self.save_input_text:
                context.blackboard.set(self.output_key, text)
            
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
        """根据输入模式获取文本内容"""
        if self.input_mode == "preset":
            if not self.preset_texts:
                return ""
            
            if self.execution_mode == "sequential":
                return self._get_next_preset_text(context)
            else:
                return self._get_random_preset_text()
        
        elif self.input_mode == "blackboard":
            return context.blackboard.get(self.blackboard_key, "")
        
        elif self.input_mode == "file":
            return self._read_file(context)
        
        return ""
    
    def _get_next_preset_text(self, context) -> str:
        """获取下一个预设文本（顺序执行）"""
        index_key = f"{self.node_id}_text_index"
        current_index = context.blackboard.get(index_key, 0)
        
        text = self.preset_texts[current_index % len(self.preset_texts)]
        
        next_index = (current_index + 1) % len(self.preset_texts)
        context.blackboard.set(index_key, next_index)
        
        return text
    
    def _get_random_preset_text(self) -> str:
        """随机获取预设文本"""
        return random.choice(self.preset_texts)
    
    def _read_file(self, context) -> str:
        """读取文件内容"""
        try:
            if self.file_path.startswith("./"):
                file_path = context.resolve_path(self.file_path)
            else:
                file_path = self.file_path
            
            if not os.path.exists(file_path):
                LogManager.instance().log_failure(
                    node_type="文本输入节点",
                    node_name=self.name,
                    reason=f"文件不存在: {file_path}"
                )
                return ""
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        except Exception as e:
            LogManager.instance().log_failure(
                node_type="文本输入节点",
                node_name=self.name,
                reason=f"读取文件失败: {str(e)}"
            )
            return ""
    
    def _input_text(self, context, text: str) -> None:
        """逐字符输入文本"""
        for char in text:
            if not context.check_running():
                break
            
            if char == '\n':
                context.execute_key_press("enter", action="press")
            elif char == '\t':
                context.execute_key_press("tab", action="press")
            else:
                import pyperclip
                pyperclip.copy(char)
                context.execute_key_press("ctrl", action="down")
                context.execute_key_press("v", action="press")
                context.execute_key_press("ctrl", action="up")
            
            if self.input_delay > 0:
                time.sleep(self.input_delay / 1000.0)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["config"]["input_mode"] = self.input_mode
        data["config"]["preset_texts"] = self.preset_texts
        data["config"]["execution_mode"] = self.execution_mode
        data["config"]["blackboard_key"] = self.blackboard_key
        data["config"]["file_path"] = self.file_path
        data["config"]["position"] = self.position
        data["config"]["use_blackboard"] = self.use_blackboard
        data["config"]["position_key"] = self.position_key
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
```

**Step 2: 提交文本输入节点**

```bash
git add bt_nodes/actions/text_input.py
git commit -m "feat: add TextInputNode for text input with multiple input modes"
```

---

## Task 2: 创建文本提取节点

**Files:**
- Create: `bt_nodes/conditions/text_extract.py`

**Step 1: 创建 TextExtractNode 类**

```python
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
    """文本提取节点
    
    从指定区域提取文本并保存到黑板
    """
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
        self.output_key = self.config.get("output_key", "extracted_text")
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
                context.blackboard.set(self.position_key, (center_x, center_y))
            
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
        """提取包含关键词的文本行"""
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
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextExtractNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        return node
```

**Step 2: 提交文本提取节点**

```bash
git add bt_nodes/conditions/text_extract.py
git commit -m "feat: add TextExtractNode for text extraction with OCR"
```

---

## Task 3: 注册新节点到节点注册中心

**Files:**
- Modify: `bt_core/registry.py`

**Step 1: 在 registry.py 中导入并注册新节点**

```python
from bt_nodes.actions.text_input import TextInputNode
from bt_nodes.conditions.text_extract import TextExtractNode

NodeRegistry.register("TextInputNode", TextInputNode)
NodeRegistry.register("TextExtractNode", TextExtractNode)
```

**Step 2: 提交节点注册**

```bash
git add bt_core/registry.py
git commit -m "feat: register text processing nodes to NodeRegistry"
```

---

## Task 4: 更新节点面板配置

**Files:**
- Modify: `bt_gui/bt_editor/constants.py`

**Step 1: 在 constants.py 中添加新节点类型**

```python
NODE_TYPES = {
    # ... 现有节点 ...
    
    "TextInputNode": {
        "name": "文本输入",
        "category": "action",
        "color": "#FF5722",
        "description": "向目标位置输入文本"
    },
    "TextExtractNode": {
        "name": "文本提取",
        "category": "condition",
        "color": "#FF5722",
        "description": "从指定区域提取文本并保存到黑板"
    },
}
```

**Step 2: 提交节点面板配置**

```bash
git add bt_gui/bt_editor/constants.py
git commit -m "feat: add text processing node types to constants"
```

---

## Task 5: 更新属性面板支持文本列表字段

**Files:**
- Modify: `bt_gui/bt_editor/property.py`

**Step 1: 添加文本列表字段**

```python
class TextListField:
    """文本列表字段"""
    
    def __init__(self, master, label: str, key: str, value: list = None, on_change=None):
        self.master = master
        self.label = label
        self.key = key
        self.on_change = on_change
        self._texts = value or []
        
        self._create_widget()
    
    def _create_widget(self):
        self.frame = customtkinter.CTkFrame(self.master)
        self.frame.pack(fill="x", padx=5, pady=2)
        
        label = customtkinter.CTkLabel(self.frame, text=self.label, width=80, anchor="w")
        label.pack(side="top", padx=5, pady=2)
        
        self.textbox = customtkinter.CTkTextbox(self.frame, height=100)
        self.textbox.pack(fill="x", padx=5, pady=2)
        
        self.set_value(self._texts)
    
    def get_value(self) -> list:
        """获取文本列表"""
        text = self.textbox.get("1.0", tk.END).strip()
        if not text:
            return []
        return [line.strip() for line in text.split('\n') if line.strip()]
    
    def set_value(self, value: list):
        """设置文本列表"""
        self.textbox.delete("1.0", tk.END)
        if value:
            self.textbox.insert("1.0", '\n'.join(value))
```

**Step 2: 提交属性面板更新**

```bash
git add bt_gui/bt_editor/property.py
git commit -m "feat: add text list field to property panel"
```

---

## Task 6: 添加依赖项

**Files:**
- Modify: `requirements.txt`

**Step 1: 添加 pyperclip 依赖**

```
pyperclip>=1.8.2
```

**Step 2: 提交依赖更新**

```bash
git add requirements.txt
git commit -m "feat: add pyperclip dependency for text input"
```

---

## Task 7: 最终测试与提交

**Step 1: 运行测试**

```bash
python -m pytest tests/ -v
```

**Step 2: 检查代码风格**

```bash
python -m flake8 bt_nodes/actions/text_input.py bt_nodes/conditions/text_extract.py
```

**Step 3: 最终提交**

```bash
git add .
git commit -m "feat: complete text processing features"
```

---

## 执行选择

**计划已完成并保存到 `docs/plans/2026-04-23-text-processing-tasks.md`。两种执行方式：**

**1. Subagent-Driven（当前会话）** - 我在当前会话中逐个任务分派子代理执行，任务间进行代码审查，快速迭代

**2. Parallel Session（独立会话）** - 打开新会话使用 executing-plans 技能，批量执行并设置检查点

**您选择哪种方式？**

# AI 助手增强实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 AI 助手支持「屏幕感知可选化（缺失时语言对话补全）」和「分析修改已有行为树（结构级修改）」双模式。

**Architecture:** 在现有 `AssistantPanel` 内增加「创建 / 分析修改」双模式。新增两个 AI 模块 `DialogueFiller`（创建模式第 3 步的 VLM 语言回退）和 `TreeModifier`（分析模式核心，读已有树+用户意图→AI 返回整棵新树），复用 `LLMClient`/`NodeSpecExporter`/`TreeValidator`/`IterationEngine`。`AssistantState` 扩展 `mode` 字段区分两种阶段流。

**Tech Stack:** Python 3.10+，CustomTkinter，requests，pytest（mocked LLM/ctk，不发起真实网络请求）。

---

### Task 1: 新增 dialogue_filler.py 模块

**Files:**
- Create: `bt_cli/ai/dialogue_filler.py`
- Create: `bt_cli/ai/prompts/dialogue_fill.md`
- Test: `tests/test_dialogue_filler.py`

**Step 1: Write the failing test**

```python
# tests/test_dialogue_filler.py
import json
from unittest.mock import MagicMock, patch
from bt_cli.ai.dialogue_filler import DialogueFiller, DialogueFillError


def _structure():
    return {"nodes": [
        {"id": "node_detect", "type": "OCRConditionNode",
         "config": {}, "children": [], "empty_params": ["region", "keywords"]},
        {"id": "node_start", "type": "StartNode", "config": {}, "children": []},
    ]}


def test_propose_questions_returns_one_per_empty_param():
    with patch("bt_cli.ai.dialogue_filler.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "questions": [
                {"node_id": "node_detect", "param": "region", "question": "检测区域在哪里？"},
                {"node_id": "node_detect", "param": "keywords", "question": "要识别什么文字？"},
            ]
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        filler = DialogueFiller()
        out = filler.propose_questions(_structure(), "任务")
        assert len(out) == 2
        assert out[0]["param"] == "region"


def test_resolve_from_answers_fills_and_clears_empty():
    answers = [
        {"node_id": "node_detect", "param": "region",
         "suggested_value": [10, 20, 30, 40], "confidence": 0.8},
        {"node_id": "node_detect", "param": "keywords",
         "suggested_value": "签到", "confidence": 0.9},
    ]
    filler = DialogueFiller()
    filled = filler.resolve_from_answers(_structure(), answers)
    node = filled["nodes"][0]
    assert node["config"]["region"] == [10, 20, 30, 40]
    assert node["config"]["keywords"] == "签到"
    assert node["empty_params"] == []


def test_propose_questions_empty_params_returns_empty():
    filler = DialogueFiller()
    assert filler.propose_questions({"nodes": []}, "任务") == []
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dialogue_filler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bt_cli.ai.dialogue_filler'`

**Step 3: Write minimal implementation**

`bt_cli/ai/prompts/dialogue_fill.md` 开头（角色定义 + 输出格式，参考 node_selection.md 风格）：
```markdown
# AutoDoor 行为树自动化系统 — 参数补全引导专家

## 你的角色

你是行为树的参数补全引导专家。当系统无法通过屏幕截图感知参数时，你会列出所有空参数，并为每个参数生成一个引导用户用语言描述的问题，然后根据用户回答给出建议值。
```

`bt_cli/ai/dialogue_filler.py`：
```python
# bt_cli/ai/dialogue_filler.py
"""阶段③ 语言补全 — VLM 不可用时引导用户用语言描述补全空参数"""
import json
import os
import copy
from typing import Dict, Any, List

from bt_cli.ai.llm_client import LLMClient


class DialogueFillError(Exception):
    """语言补全错误"""
    pass


class DialogueFiller:
    """语言补全器：VLM 不可用/跳过的回退方案"""

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "dialogue_fill.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client

    def propose_questions(self, structure: Dict[str, Any],
                          task_context: str) -> List[Dict[str, Any]]:
        """列出所有空参数并生成引导问题"""
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")
        fill_requests = self._extract_empty_params(structure)
        if not fill_requests:
            return []
        system_prompt = self._load_prompt()
        user_content = (
            f"## 任务上下文\n{task_context}\n\n"
            f"## 需要补全的参数清单\n"
            + "\n".join(f"- 节点 {r['node_id']} ({r['node_type']}): 参数 '{r['param']}'"
                        for r in fill_requests)
            + "\n\n请为每个参数生成一个引导用户用语言描述的问题。"
        )
        try:
            result = self._llm.chat(
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": user_content}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise DialogueFillError(f"LLM 请求失败: {e}") from e
        try:
            data = json.loads(result["content"])
            return data.get("questions", [])
        except json.JSONDecodeError as e:
            raise DialogueFillError(f"LLM 返回的 JSON 无效: {e}") from e

    def resolve_from_answers(self, structure: Dict[str, Any],
                             answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """根据用户/LLM 的建议值填充结构（复用 fill_structure 同构逻辑）"""
        filled = copy.deepcopy(structure)
        nodes = filled.get("nodes", [])
        node_map = {n.get("id"): n for n in nodes if isinstance(n, dict)}
        for ans in answers:
            if not isinstance(ans, dict):
                continue
            node_id = ans.get("node_id")
            param = ans.get("param")
            value = ans.get("suggested_value")
            if node_id is None or param is None or value is None:
                continue
            if node_id in node_map:
                node = node_map[node_id]
                node.setdefault("config", {})[param] = value
                if "empty_params" in node:
                    node["empty_params"] = [
                        p for p in node["empty_params"] if p != param
                    ]
        return filled

    def _extract_empty_params(self, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        requests = []
        for node in structure.get("nodes", []):
            if not isinstance(node, dict):
                continue
            for param in node.get("empty_params", []):
                requests.append({
                    "node_id": node.get("id", ""),
                    "param": param,
                    "node_type": node.get("type", ""),
                })
        return requests

    def _load_prompt(self) -> str:
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dialogue_filler.py -v`
Expected: PASS (3 passed)

**Step 5: Commit**

```bash
git add bt_cli/ai/dialogue_filler.py bt_cli/ai/prompts/dialogue_fill.md tests/test_dialogue_filler.py
git commit -m "feat: add DialogueFiller for language-based param completion"
```

---

### Task 2: 新增 tree_modifier.py 模块

**Files:**
- Create: `bt_cli/ai/tree_modifier.py`
- Create: `bt_cli/ai/prompts/tree_modify.md`
- Test: `tests/test_tree_modifier.py`

**Step 1: Write the failing test**

```python
# tests/test_tree_modifier.py
import json
from unittest.mock import MagicMock, patch
from bt_cli.ai.tree_modifier import TreeModifier, TreeModifyError


def _tree():
    return {
        "version": "2.1", "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode",
                           "config": {}, "children": ["node_click"]},
            "node_click": {"id": "node_click", "type": "MouseClickNode",
                           "config": {"position": [100, 200]}, "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_click"}],
    }


def test_modify_returns_valid_tree_and_changes():
    new_tree = {
        "version": "2.1", "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode",
                           "config": {}, "children": ["node_delay"]},
            "node_delay": {"id": "node_delay", "type": "DelayNode",
                           "config": {"duration_ms": 1000}, "children": ["node_click"]},
            "node_click": {"id": "node_click", "type": "MouseClickNode",
                           "config": {"position": [100, 200]}, "children": []},
        },
        "connections": [
            {"parent_id": "node_start", "child_id": "node_delay"},
            {"parent_id": "node_delay", "child_id": "node_click"},
        ],
    }
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "tree": new_tree,
            "changes": [{"type": "add", "node_id": "node_delay",
                         "description": "点击前插入延时节点"}],
            "summary": "插入一个 1000ms 延时节点",
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        out = mod.modify(_tree(), "点击前加个延时")
        assert out["tree"]["nodes"]["node_delay"]["type"] == "DelayNode"
        assert len(out["changes"]) == 1
        assert out["summary"] == "插入一个 1000ms 延时节点"


def test_modify_raises_on_invalid_tree():
    with patch("bt_cli.ai.tree_modifier.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "tree": {"nodes": {}},  # 缺 root_node，校验失败
            "changes": [], "summary": ""
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        mod = TreeModifier()
        try:
            mod.modify(_tree(), "改动")
            assert False, "应抛出 TreeModifyError"
        except TreeModifyError:
            pass
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tree_modifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

`bt_cli/ai/prompts/tree_modify.md` 开头：
```markdown
# AutoDoor 行为树自动化系统 — 行为树修改专家

## 你的角色

你是行为树修改专家。用户会给出一个已有行为树（tree.json）和修改意图，你需要返回修改后的完整行为树（tree.json），以及人类可读的改动清单。你可以增删节点、修改连接关系、修改任意节点的配置参数。
```

`bt_cli/ai/tree_modifier.py`：
```python
# bt_cli/ai/tree_modifier.py
"""分析模式核心 — 根据用户意图结构级修改已有行为树"""
import json
import os
from typing import Dict, Any, List

from bt_cli.ai.llm_client import LLMClient
from bt_cli.ai.node_spec_exporter import NodeSpecExporter


class TreeModifyError(Exception):
    """行为树修改错误"""
    pass


class TreeModifier:
    """行为树修改器：读已有树+用户意图 → 返回整棵新树"""

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "tree_modify.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client
        self._spec_exporter = NodeSpecExporter()

    def modify(self, tree_data: Dict[str, Any], intent: str,
               task_context: str = "") -> Dict[str, Any]:
        """根据用户意图修改已有行为树"""
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")
        system_prompt = self._load_prompt()
        spec_text = self._spec_exporter.export_for_prompt()
        user_content = (
            f"## 现有行为树\n```json\n{json.dumps(tree_data, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## 用户修改意图\n{intent}\n\n"
            f"## 任务上下文\n{task_context}\n\n"
            f"## 可用节点规格\n{spec_text}\n\n"
            "请返回修改后的完整行为树 tree.json 和改动清单。"
        )
        try:
            result = self._llm.chat(
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": user_content}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise TreeModifyError(f"LLM 请求失败: {e}") from e
        try:
            data = json.loads(result["content"])
        except json.JSONDecodeError as e:
            raise TreeModifyError(f"LLM 返回的 JSON 无效: {e}") from e

        tree = data.get("tree")
        if not tree:
            raise TreeModifyError("LLM 未返回修改后的行为树")
        # 校验
        from bt_cli.ai.tree_validator import TreeValidator
        errors = TreeValidator().validate(tree)
        if errors:
            raise TreeModifyError("修改后的行为树校验失败: " + "; ".join(errors))

        return {
            "tree": tree,
            "changes": data.get("changes", []),
            "summary": data.get("summary", ""),
        }

    def _summarize_tree(self, tree_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """精简行为树用于 AI 分析（nodes 为 dict 形态）"""
        summary = []
        for node_id, node in tree_data.get("nodes", {}).items():
            summary.append({
                "id": node_id,
                "type": node.get("type"),
                "config": node.get("config", {}),
                "children": node.get("children", []),
            })
        return summary

    def _load_prompt(self) -> str:
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
```

**注意**：`TreeValidator().validate(tree)` 期望 tree 包含 `root_node` 且为 dict 形态 nodes。若测试中 `new_tree` 形态不符，需在 Task 中调整 fixtures 使其与真实 tree.json 一致（dict nodes + root_node）。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tree_modifier.py -v`
Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add bt_cli/ai/tree_modifier.py bt_cli/ai/prompts/tree_modify.md tests/test_tree_modifier.py
git commit -m "feat: add TreeModifier for structural tree modification"
```

---

### Task 3: 扩展 AssistantState 支持双模式

**Files:**
- Modify: `bt_gui/ai_assistant/state.py`
- Test: `tests/test_state.py`（若存在则扩展，否则新建）

**Step 1: Write the failing test**

```python
# tests/test_state.py
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL with `ImportError: cannot import name 'AssistantMode'`

**Step 3: Write minimal implementation**

```python
# bt_gui/ai_assistant/state.py
from enum import Enum
from typing import Dict, Any, Optional


class AssistantMode(Enum):
    CREATE = "create"
    ANALYZE = "analyze"


class AssistantState:
    MAX_STAGE = 5

    def __init__(self):
        self.mode: AssistantMode = AssistantMode.CREATE
        self.stage: int = 0
        self.plan: Optional[Dict[str, Any]] = None
        self.structure: Optional[Dict[str, Any]] = None
        self.filled_structure: Optional[Dict[str, Any]] = None
        self.tree_data: Optional[Dict[str, Any]] = None
        self.test_report: Optional[Dict[str, Any]] = None
        self.is_processing: bool = False
        # 分析模式
        self.source_tree: Optional[Dict[str, Any]] = None
        self.modification_plan: Optional[Dict[str, Any]] = None
        self.analyze_result: Optional[Dict[str, Any]] = None

    def _max_stage(self) -> int:
        return 3 if self.mode == AssistantMode.ANALYZE else self.MAX_STAGE

    def advance(self) -> int:
        if self.stage < self._max_stage():
            self.stage += 1
        return self.stage

    def go_back(self) -> int:
        if self.stage > 0:
            self.stage -= 1
        return self.stage

    def can_go_back(self) -> bool:
        return self.stage > 0

    def can_advance(self) -> bool:
        return self.stage < self._max_stage()

    def reset(self) -> None:
        self.stage = 0
        self.mode = AssistantMode.CREATE
        self.plan = None
        self.structure = None
        self.filled_structure = None
        self.tree_data = None
        self.test_report = None
        self.is_processing = False
        self.source_tree = None
        self.modification_plan = None
        self.analyze_result = None
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`
Expected: PASS (3 passed)

**Step 5: Commit**

```bash
git add bt_gui/ai_assistant/state.py tests/test_state.py
git commit -m "feat: support create/analyze dual-mode in AssistantState"
```

---

### Task 4: 扩展 stage_views.py 分析模式视图 + 创建第3步双入口

**Files:**
- Modify: `bt_gui/ai_assistant/stage_views.py`
- Test: `tests/test_stage_views.py`

**Step 1: Write the failing test**

在 `tests/test_stage_views.py` 追加：
```python
def test_analyze_stage0_view_no_tree():
    from bt_gui.ai_assistant.stage_views import create_analyze_stage0_view
    from bt_gui.ai_assistant.state import AssistantState
    state = AssistantState()
    mock_frame = MagicMock()
    mock_colors = {}
    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_analyze_stage0_view(mock_frame, state, mock_colors)


def test_analyze_stage2_view_with_plan():
    from bt_gui.ai_assistant.stage_views import create_analyze_stage2_view
    from bt_gui.ai_assistant.state import AssistantState
    state = AssistantState()
    state.modification_plan = {"tree": {"nodes": {}}, "changes": [
        {"type": "add", "node_id": "node_delay", "description": "插入延时"}],
        "summary": "插入延时节点"}
    mock_frame = MagicMock()
    mock_colors = {}
    with patch("bt_gui.ai_assistant.stage_views.ctk"):
        create_analyze_stage2_view(mock_frame, state, mock_colors)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stage_views.py -k analyze -v`
Expected: FAIL with `ImportError: cannot import name 'create_analyze_stage0_view'`

**Step 3: Write minimal implementation**

在 `stage_views.py` 新增 4 个分析模式视图函数（复用 `_create_section_label`、`get_ai_font`）：
- `create_analyze_stage0_view(parent, state, colors, on_load_tree=None)`：显示当前树信息或「请先打开一棵行为树」，提供「读取当前画布树」按钮。
- `create_analyze_stage1_view(parent, state, colors)`：意图输入文本框 + 开始按钮（由面板回调驱动）。
- `create_analyze_stage2_view(parent, state, colors)`：展示 `modification_plan["changes"]` 改动清单 + `summary`。
- `create_analyze_stage3_view(parent, state, colors, on_apply=None)`：展示「应用到画布」按钮。

同时修改创建模式 `create_stage3_view`：进入时若无 VLM 或不点截图，显示「跳过，用语言描述补全」按钮（通过 `on_dialogue` 回调）。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_stage_views.py -v`
Expected: PASS (全部通过)

**Step 5: Commit**

```bash
git add bt_gui/ai_assistant/stage_views.py tests/test_stage_views.py
git commit -m "feat: add analyze-mode stage views and dialogue fallback in stage3"
```

---

### Task 5: 扩展 assistant_panel.py 双模式分发 + 模式切换

**Files:**
- Modify: `bt_gui/ai_assistant/assistant_panel.py`
- Test: `tests/test_assistant_panel.py`

**Step 1: Write the failing test**

在 `tests/test_assistant_panel.py` 追加：
```python
def test_mode_switch_resets_stage():
    from bt_gui.ai_assistant.assistant_panel import AssistantPanel
    from bt_gui.ai_assistant.state import AssistantMode
    panel = AssistantPanel.__new__(AssistantPanel)
    panel._state = None
    # 通过真实构造 mock 上下文验证
    # 若无法构造，则验证 _show_stage_view 按 mode 分发
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_assistant_panel.py -v`
Expected: 需先确认现有测试如何构造 AssistantPanel（conftest mock 下应可构造）

**Step 3: Write minimal implementation**

在 `assistant_panel.py`：
1. 顶部标题栏下加 `CTkSegmentedButton(self, values=["创建", "分析修改"], command=self._on_mode_change)`。
2. `_on_mode_change(value)`：设置 `state.mode`、`state.stage=0`、`_show_stage_view()`。
3. `_show_stage_view()` 开头按 `state.mode` 分发：CREATE 走现有逻辑，ANALYZE 走 `_show_analyze_stage0/1/2/3`。
4. 新增 `_show_analyze_stage0/1/2/3` 方法 + 分析模式回调（`_run_tree_modify`、`_on_tree_modify_done`、`_on_tree_modify_error`、`_apply_modified_tree`）。
5. `_apply_modified_tree`：调用 `on_tree_generated` 回调把新树加载到画布（复用 `_on_ai_tree_generated` 的 `load_tree` 路径）。
6. 新增 `on_dialogue` 回调触发 `DialogueFiller` 流程（`_run_dialogue_fill`）。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_assistant_panel.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bt_gui/ai_assistant/assistant_panel.py tests/test_assistant_panel.py
git commit -m "feat: add dual-mode dispatch and mode switch in AssistantPanel"
```

---

### Task 6: 应用确认与画布加载

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: Verify current behavior**

检查 `editor.py` `_on_ai_tree_generated`（L634-640）已将 tree_data 落盘并 `load_tree`。确认已有回调 `on_tree_generated` 已注册到面板。

**Step 2: Add analyze 相关回调注册**

在 `editor.py` 中确认/补充：
```python
self.ai_assistant_panel.register_callback("on_tree_generated", self._on_ai_tree_generated)
```
（分析模式应用新树时复用该回调，无需新增。）

**Step 3: Verify manually**

手动验证：打开一棵已有树 → AI 助手切「分析修改」→ 读取画布树 → 输入意图 → 生成修改方案 → 应用到画布 → 画布刷新为新树。

**Step 4: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat: wire analyze-mode tree application to canvas"
```

---

### Task 7: 运行全量测试回归

**Files:**
- All modified files

**Step 1: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: 全部通过，无回归。

**Step 2: Fix any failures**

如有失败，按 systematic-debugging skill 排查修复。

**Step 3: Commit**

```bash
git add -A
git commit -m "test: full regression after AI assistant enhancement"
```

---

## 关键实现注意点

- **nodes 容器形态差异**：`DialogueFiller.resolve_from_answers` 基于 AI 中间格式（nodes=list）；`TreeModifier` 基于真实 tree.json（nodes=dict）。二者不要混用，`_summarize_tree` 明确按 dict 遍历。
- **LLM mock 约定**：`chat` 返回 `{"content": <json字符串>, "model", "usage"}`，测试内 `json.loads(result["content"])` 解析。参考 `tests/test_iteration_engine.py` 的 patch 模式。
- **TreeValidator 校验链**：`TreeModifier.modify` 输出必须通过 `TreeValidator().validate()`，否则抛 `TreeModifyError` 并展示错误。
- **错误处理**：新模块异常统一走 `_log_ai_error` 输出日志 + 面板显示可见错误，不中断流水线。
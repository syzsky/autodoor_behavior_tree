# AI 助手增强设计：屏幕感知可选化 + 已有行为树分析修改

- 日期：2026-08-06
- 状态：待评审
- 方案：方案 A（单面板双模式 + 复用现有 AI 模块）

## 1. 背景与目标

当前 AI 助手面板 `AssistantPanel` 是纯「从零创建」的 5 步流水线（意图分析 → 节点选型 → 屏幕感知 → 生成 JSON → 试运行）。本设计解决两个问题：

1. **屏幕感知（VLM）不可用/被跳过后，没有引导用户补全空缺参数**。当前 CLI 层在无 VLM 时静默跳过、参数留空，GUI 面板同样静默跳过，用户对空参数无从下手。
2. **AI 助手只能从零创建，不能分析/修改用户已有的行为树**。现有 `ai refine` 只改 config 参数值，且 GUI 面板完全没有「分析已有树」入口。

目标：让屏幕感知成为可选项，缺失时用语言对话引导补全；让 AI 助手能以「创建 / 分析修改」双模式作用于已有树（支持结构级修改）。

## 2. 总体架构

采用方案 A：**单面板双模式 + 复用现有 AI 模块**。

- 在现有 `AssistantPanel` 内增加「创建 / 分析修改」两种模式切换，两模式共享一套 AI 模块与 UI 骨架。
- 新增两个 AI 模块：
  - `DialogueFiller`（语言补全）：创建模式第 3 步的 VLM 回退。
  - `TreeModifier`（结构级修改）：分析模式核心。
- 复用现有：`LLMClient`、`NodeSpecExporter`、`TreeValidator`、`IterationEngine`、`NodeRegistry`。

## 3. 状态机设计（state.py）

```python
class AssistantMode(Enum):
    CREATE = "create"      # 从零创建（现有 5 步）
    ANALYZE = "analyze"    # 分析修改已有树

class AssistantState:
    mode: AssistantMode = AssistantMode.CREATE
    stage: int = 0
    # 创建模式阶段：0欢迎 1意图 2选型 3感知 4生成 5试运行
    # 分析模式阶段：0加载树 1意图理解 2修改方案 3应用确认
    # 创建模式字段（现有）
    plan: Optional[dict] = None
    structure: Optional[dict] = None
    filled_structure: Optional[dict] = None
    tree_data: Optional[dict] = None
    test_report: Optional[dict] = None
    # 分析模式新增
    source_tree: Optional[dict] = None        # 从画布读取的当前树
    modification_plan: Optional[dict] = None  # AI 产出的修改方案
    # 分析模式阶段1产物
    analyze_result: Optional[dict] = None      # AI 对树的解读 + 待确认意图
```

- `advance()/go_back()/can_go_back()/can_advance()` 需按 `mode` 区分最大阶段数（CREATE=5，ANALYZE=3）。
- `reset()` 需按 `mode` 重置对应字段。

## 4. 新增 AI 模块设计（bt_cli/ai/）

### 4.1 dialogue_filler.py — 语言补全（创建模式第 3 步回退）

职责：VLM 不可用/被跳过时，用语言提问引导用户补全空参数，AI 基于用户描述生成建议值。

```python
class DialogueFiller:
    def propose_questions(self, structure: dict, task_context: str) -> List[dict]:
        """AI 列出所有空参数，为每个生成一个问题。
        返回: [{"node_id","param","node_type","question","hint"}]"""

    def resolve_from_answers(self, structure: dict, answers: List[dict]) -> dict:
        """把用户逐项回答映射为建议值，写回 config、清空 empty_params。
        返回: 填充后的结构（深拷贝）"""
```

- **输入**：`structure`（含 `empty_params`）、`task_context`。
- **输出（propose_questions）**：每个空参数一个问题，含参数名、节点、期望用户描述什么。
- **输出（resolve_from_answers）**：复用 `fill_structure` 的同构逻辑（可提取公共私有方法），把 `answers` 中 AI 生成的 `suggested_value` 写入对应节点 `config[param]`，从 `empty_params` 移除。
- **Prompts**：`prompts/dialogue_fill.md`。
- 异常：`DialogueFillError`。

### 4.2 tree_modifier.py — 结构级修改（分析模式核心）

职责：读已有树 + 用户意图 → 产出结构级修改后的整棵新树。

```python
class TreeModifier:
    def modify(self, tree_data: dict, intent: str, task_context: str = "") -> dict:
        """根据用户意图修改已有树，返回完整新树 + 改动清单。
        返回: {"tree": dict, "changes": [{"type","node_id","description"}], "summary": str}"""

    def _summarize_tree(self, tree_data: dict) -> List[dict]:
        """精简树为 [{id,type,config,children}]（复用 iterator 逻辑）"""
```

- **输入**：`tree_data`（从画布读的完整树）、`intent`（用户自然语言修改意图）、`task_context`（可选，任务背景）。
- **输出**：`{"tree": 修改后的完整 tree.json, "changes": 人类可读改动清单, "summary": 修改摘要}`。`tree` 必须通过 `TreeValidator.validate()` 校验。
- **修改能力**：可增删节点、改连接关系、改任何节点 config 值。AI 以「整棵新树」形式返回，避免逐条 diff 的复杂协议。
- **构建**：user_content = 精简树 + 用户意图 + `NodeSpecExporter.export_for_prompt()` 节点规格；`llm.chat(temperature=0.2, json_object)`。
- **Prompts**：`prompts/tree_modify.md`。
- 异常：`TreeModifyError`。

## 5. UI 设计（assistant_panel.py + stage_views.py）

### 5.1 面板顶部模式切换

`assistant_panel.py` 顶部标题栏下加一个 `CTkSegmentedButton`（创建 / 分析修改）。切换时：
- 记录当前模式到 `state.mode`。
- 重置 `state.stage = 0` 并调用 `_show_stage_view()`。
- 若从「分析修改」切回「创建」，保留已生成的 `tree_data`（不销毁）。

### 5.2 创建模式阶段视图（改动）

- **阶段 3「屏幕感知」**：进入时检测 `ai.vlm.api_key`。有 key → 显示现有「截图并分析」按钮；无 key 或用户选择跳过 → 显示「跳过，用语言描述补全」按钮，进入 `DialogueFiller` 流程：
  - 子界面 A：AI 列出空参数问题清单（`propose_questions`）。
  - 子界面 B：针对关键参数，文本框逐项采集用户描述 → `resolve_from_answers` 生成建议值 → 展示确认列表 → 用户「确认并下一步」。

### 5.3 分析模式阶段视图（新增）

- **阶段 0「加载树」**：显示当前画布树的信息（名称、节点数、根节点），提供「读取当前画布树」按钮，或自动读取。
- **阶段 1「意图理解」**：文本框输入修改意图（如"点击后加个延时"、"把超时改成 5 秒"），AI 先解读当前树并确认理解。
- **阶段 2「修改方案」**：展示 `TreeModifier.modify` 产出的 `changes` 改动清单 + `summary`，用户可查看整棵新树的节点/连接概览。
- **阶段 3「应用确认」**：展示「应用到画布」按钮，确认后通过回调 `on_tree_modified` 把新树交给画布加载（复用 `_on_ai_tree_generated` 的 `load_tree` 路径）。

新增视图函数：`create_analyze_stage0_to_3_view`（4 个）。

## 6. 数据流

### 6.1 创建模式（含语言补全回退）

```
用户描述 → [IntentAnalyzer] → plan
        → [NodeSelector] → structure(含 empty_params)
        → ┌─ VLM 可用: [VLMAnalyzer] → filled_structure
        → └─ 无VLM/跳过: [DialogueFiller] 提问→用户回答→建议值 → filled_structure
        → [TreeGenerator.generate_and_validate] → tree_data
        → [IterationEngine] 试运行/修正 → 应用画布
```

### 6.2 分析修改模式

```
画布当前树 → tree_data
        + 用户意图 → [TreeModifier.modify] → 新tree + changes + summary
        → [TreeValidator.validate] 校验
        → 展示改动清单 → 用户确认 → 加载到画布
```

## 7. 错误处理

- **VLM 未配置/失败**：创建模式阶段 3 正常进入语言补全流程，不中断流水线。日志输出 `[AI助手][屏幕感知]` 提示。
- **DialogueFiller 失败**：显示错误并允许重试，不阻塞其他阶段。
- **TreeModifier 输出校验失败**：`TreeValidator.validate` 返回错误列表，展示给用户，提供「重试」或「查看原始输出」。
- **分析模式无画布树**：阶段 0 提示「请先打开或创建一棵行为树」，禁用下一步。
- **渲染异常**：沿用 `_show_stage_view` 的防御性 try/except（输出日志 + 显示可见错误）。

## 8. 测试

- **单元测试**：
  - `tests/test_dialogue_filler.py`：`propose_questions` 对空参数生成问题；`resolve_from_answers` 写入 config 并清空 empty_params；无空参数时返回空。
  - `tests/test_tree_modifier.py`：`modify` 返回结构通过 `TreeValidator`；`_summarize_tree` 精简正确；mocked LLM 返回合法新树。
  - `tests/test_stage_views.py`：新增分析模式 4 个阶段视图渲染测试 + 创建模式阶段 3 双入口渲染测试。
  - `tests/test_assistant_panel.py`：模式切换正确重置 stage；分析模式无树时禁用下一步。
- **验证方式**：mocked `LLMClient`/`ctk`，不发起真实网络请求。

## 9. 涉及文件清单

| 文件 | 改动 |
|---|---|
| `bt_cli/ai/dialogue_filler.py` | 新增 |
| `bt_cli/ai/tree_modifier.py` | 新增 |
| `bt_cli/ai/prompts/dialogue_fill.md` | 新增 |
| `bt_cli/ai/prompts/tree_modify.md` | 新增 |
| `bt_gui/ai_assistant/state.py` | 扩展双模式状态 |
| `bt_gui/ai_assistant/assistant_panel.py` | 加模式切换、分模式分发、新增分析模式回调 |
| `bt_gui/ai_assistant/stage_views.py` | 创建第3步双入口、新增分析模式4视图 |
| `tests/test_dialogue_filler.py` | 新增 |
| `tests/test_tree_modifier.py` | 新增 |
| `tests/test_stage_views.py` | 扩展 |
| `tests/test_assistant_panel.py` | 扩展 |

## 10. 关键决策记录

- 屏幕感知回退：AI 提问引导 + 建议值（用户确认）。
- 已有树修改粒度：结构级修改（增删节点、改连接、改配置）。
- 面板入口：AI 助手内双模式。
- 修改协议：AI 以「整棵新树」返回而非逐条 diff，简化协议与校验。
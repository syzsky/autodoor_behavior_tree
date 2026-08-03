# AI 编排自动化重新设计

> 日期：2026-08-03
> 状态：已确认，待实施
> 替代文档：`doc/AI_Tree_Generator_Prompt.md`（单次 prompt 生成方案，已废弃）

---

## 1 背景与问题

### 1.1 旧方案的问题

旧方案 `AI_Tree_Generator_Prompt.md` 采用"单次 prompt 生成完整 tree.json"模式，存在三个核心痛点：

| 痛点 | 根因 | 表现 |
|------|------|------|
| 参数全靠手填 | AI 无屏幕感知能力，无法获取坐标/区域 | 生成的 JSON 中 region/position/keywords 全为空，用户需手动在 GUI 逐个补充 |
| 节点选型不准 | 节点规格写死在 prompt 中，与真实 NodeRegistry 脱节 | AI 不了解节点真实参数和约束，选错节点类型或配置不符合实际 |
| 无法迭代修改 | 一次性生成，无试运行和反馈机制 | 生成后无法根据运行结果调整，AI 看不到屏幕也无法修正坐标 |

### 1.2 设计目标

- **参数自动填充**：通过 VLM（视觉大模型）分析截图，自动识别屏幕元素位置并填入 region/position/keywords
- **节点选型准确**：从 NodeRegistry 动态导出真实节点规格，AI 基于准确规格选择节点
- **支持迭代修正**：试运行后 AI 分析失败原因，自动建议并应用修正，多轮迭代直到成功
- **分阶段可确认**：每阶段独立可确认、可回退、可单独重做
- **通用 API 配置**：LLM/VLM 模型不固定，支持任意 OpenAI 兼容 API

---

## 2 整体架构

### 2.1 五阶段流水线

```
用户自然语言描述
      │
      ▼
┌──────────────────────────────────────────────────────┐
│  ① 意图分析                                            │
│  AI解析描述 → 输出结构化任务计划                         │
│  （检测目标/动作序列/循环策略/间隔时间）                   │
│  ← 用户确认任务计划                                     │
├──────────────────────────────────────────────────────┤
│  ② 节点选型                                            │
│  NodeSpecExporter 从 NodeRegistry 动态读取真实节点规格   │
│  AI 据任务计划选择节点 + 设计连接结构                      │
│  ← 用户确认节点结构                                     │
├──────────────────────────────────────────────────────┤
│  ③ 屏幕感知 (VLM)                                      │
│  截图 → VLM识别元素位置 → 自动填入region/position/keywords│
│  ← 用户确认或用放大镜微调                                │
├──────────────────────────────────────────────────────┤
│  ④ 生成JSON                                           │
│  带真实参数生成tree.json → TreeValidator结构校验         │
│  ← 输出JSON文件 + 参数清单                              │
├──────────────────────────────────────────────────────┤
│  ⑤ 试运行+迭代                                         │
│  run --headless试跑 → 收集日志/截图/黑板状态             │
│  AI分析失败节点 → 建议修正 → 用户确认 → 重新生成 → 重跑   │
│  ← 可多轮迭代直到成功                                   │
└──────────────────────────────────────────────────────┘
```

### 2.2 与旧方案对比

| 维度 | 旧方案 (AI_Tree_Generator_Prompt) | 新方案 |
|------|----------------------------------|--------|
| 节点规格来源 | 写死在 prompt 中，易过时 | 从 NodeRegistry 动态读取，始终准确 |
| 生成方式 | 一次性生成完整 JSON | 5 阶段分步生成，每步可确认 |
| 参数填充 | region/position 全留空 | VLM 分析截图自动填充 |
| 迭代能力 | 无 | 试运行 + AI 分析 + 迭代修正 |
| 用户介入 | 仅开头描述和结尾补充参数 | 每阶段可确认/回退/修改 |
| 模型支持 | 无模型接入 | 通用 OpenAI 兼容 API，自由配置 |

---

## 3 各阶段详细设计

### 3.1 阶段① 意图分析

**输入**：用户自然语言描述

**处理**：AI 解析描述，输出结构化任务计划（中间表示，非行为树 JSON）

**输出格式**（plan.json）：

```json
{
  "task_summary": "定时检测登录按钮并点击",
  "loop": {
    "enabled": true,
    "interval_ms": 60000,
    "max_iterations": -1
  },
  "phases": [
    {
      "phase": "detect",
      "method": "image_or_ocr",
      "target_description": "登录按钮",
      "on_success": "proceed_to_click"
    },
    {
      "phase": "act",
      "action": "click",
      "position_source": "from_detection",
      "on_complete": "loop_back"
    }
  ],
  "window": {
    "bind": false,
    "title": "",
    "pid": null
  }
}
```

**用户交互**：展示任务计划，用户确认后进入阶段②，或修改描述重新分析。

### 3.2 阶段② 节点选型

**输入**：确认后的任务计划（plan.json）

**核心组件**：`NodeSpecExporter` —— 从 `NodeRegistry` 动态导出真实节点规格

```python
class NodeSpecExporter:
    """从 NodeRegistry 动态导出节点完整规格，替代静态 prompt"""
    
    def export_all(self) -> dict:
        """遍历所有注册节点，导出真实参数规格"""
        specs = {}
        for node_type, node_class in NodeRegistry._registry.items():
            specs[node_type] = {
                "node_type": node_type,
                "category": self._get_category(node_class),
                "base_class": self._get_base_class(node_class),
                "parameters": self._extract_params(node_class),
                "constraints": self._extract_constraints(node_class),
                "is_async": getattr(node_class, '_is_async', False),
            }
        return specs
```

**关键设计**：节点规格从代码动态生成，新增节点或插件节点后 AI 自动获得新规格，无需手动更新 prompt。

**处理**：AI 接收任务计划 + 完整节点规格 → 选择节点 + 设计连接结构

**输出格式**（structure.json）：

```json
{
  "nodes": [
    {
      "id": "node_start",
      "type": "StartNode",
      "config": {"bind_window": false, "window_title": ""},
      "children": ["node_loop"]
    },
    {
      "id": "node_loop",
      "type": "SequenceNode",
      "config": {"repeat_count": -1, "repeat_interval_ms": 60000},
      "children": ["node_detect", "node_delay"]
    },
    {
      "id": "node_detect",
      "type": "ImageConditionNode",
      "config": {"region": [], "template_path": "", "threshold": 80},
      "children": ["node_click"],
      "empty_params": ["region", "template_path"]
    },
    {
      "id": "node_click",
      "type": "MouseClickNode",
      "config": {"use_blackboard": true, "button": "left"},
      "children": []
    },
    {
      "id": "node_delay",
      "type": "DelayNode",
      "config": {"duration_ms": 60000},
      "children": []
    }
  ]
}
```

`empty_params` 字段标记待阶段③填充的空参数。

**用户交互**：展示节点结构树形预览，用户确认后进入阶段③。

### 3.3 阶段③ 屏幕感知（VLM）

**输入**：节点结构（structure.json，含空参数）

**工作流程**：

1. **截图**：有窗口绑定 → `WindowCapture` 后台截图；无窗口绑定 → `ScreenshotManager` 全屏截图
2. **提取待填充参数**：遍历节点结构，收集所有 `empty_params`
3. **VLM 分析**：截图 + 待填充参数清单 + 任务上下文 → VLM API → 返回建议值
4. **填充 + 确认**：将建议值填入节点结构，展示给用户确认

**VLMAnalyzer 组件**：

```python
class VLMAnalyzer:
    """视觉大模型屏幕分析器"""
    
    def analyze(self, screenshot_path: str, 
                fill_requests: list,
                task_context: str) -> list:
        """
        分析截图，为空参数生成建议值
        
        Returns:
            [{"node_id": "node_detect", "param": "region", 
              "suggested_value": [120,300,200,340], 
              "confidence": 0.95,
              "note": "检测到蓝色登录按钮"}]
        """
```

**VLM 配置（通用化）**：

```json
{
  "ai": {
    "vlm": {
      "base_url": "https://api.openai.com/v1",
      "api_key": "",
      "model": "gpt-4o",
      "timeout_ms": 30000,
      "max_tokens": 4096,
      "image_detail": "high"
    }
  }
}
```

- 任何 OpenAI 兼容 API（OpenAI / Azure / 通义千问 / 本地 Ollama / 自部署模型）只需改 `base_url` + `model`
- LLM 和 VLM 可分别配置不同模型和端点
- API Key 复用现有 `CredentialStore` 安全存储
- 通过 `autodoor-bt config set ai.vlm.base_url "http://localhost:11434/v1"` 动态切换

**用户确认机制**：

VLM 填充后展示对比表，包含每个参数的建议值和置信度。置信度低于 80% 的参数标记提醒用户重点确认。用户可：直接确认 / 用放大镜微调 / 手动修改。

CLI 模式下通过交互式提示确认；GUI 模式下（后续阶段）可直接在画布上标注区域。

**输出**：structure_filled.json（所有参数已填充）

### 3.4 阶段④ 生成 JSON

**输入**：确认后的节点结构（structure_filled.json）

**处理**：

1. **结构转换**：节点结构 → tree.json v2.0 格式，自动计算布局坐标（层级 Y = 50 + N×100，同级 X 均匀分布间距 200）
2. **TreeValidator 校验**：

| 校验项 | 规则 |
|--------|------|
| 根节点 | 必须是 StartNode |
| 节点 ID | 全局唯一 |
| 条件节点 | 必须有至少一个子节点 |
| 必填参数 | 不为空 |
| 连接 | 无意外循环（SubtreeNode 的循环检测除外） |
| 序列化 | 通过 Serializer.deserialize 往返测试 |

3. **校验失败自动修正**：AI 根据校验错误自动修正结构，而非直接报错交给用户

**输出**：tree.json 文件 + 参数确认清单

### 3.5 阶段⑤ 试运行 + 迭代修正

**输入**：生成的 tree.json

**工作流程**：

1. **试运行**（限时）：`autodoor-bt run tree.json --headless --bus --rest --timeout 30000`
   - 限时 30 秒（可配置），避免无限循环行为树跑飞
2. **结果收集**：
   - 执行日志（debug_log_*.txt）
   - 节点状态（成功/失败/运行中）
   - 黑板变量快照
   - 失败节点截图（失败时自动截图）
3. **AI 分析**：将日志 + 状态 + 截图发给 AI，AI 输出失败原因和修正建议
4. **用户确认修正 → 重新生成 → 重跑**：可多轮迭代

**AI 常见修正策略**：

| 失败模式 | AI 建议策略 |
|---------|------------|
| OCR 识别失败 | 扩大 region / 切换 preprocess_mode / 调整 keywords |
| 图像匹配失败 | 降低 threshold / 重新截图更新模板 / 扩大 region |
| 点击位置偏差 | 切换 use_blackboard 使用检测位置而非固定坐标 |
| 循环过快/过慢 | 调整 repeat_interval_ms / duration_ms |
| 窗口未找到 | 检查 window_title / window_pid 配置 |

**迭代退出条件**：

- 全部节点执行成功 → 输出最终 tree.json
- 达到最大迭代次数（默认 3 次）→ 输出当前最佳版本 + 未解决问题清单
- 用户手动终止 → 输出当前版本

**输出**：test_report.json（试运行报告）+ tree.json（修正版）

---

## 4 CLI 命令设计

### 4.1 命令清单

```bash
# === 完整创建流程（交互式，按阶段推进）===
autodoor-bt ai create "每分钟检查登录按钮并点击"
#  → 依次执行 ①→②→③→④→⑤，每阶段暂停等待确认

# === 单独执行某阶段（可回退重做某一阶段）===
autodoor-bt ai plan "描述"                        # ① 仅意图分析，输出 plan.json
autodoor-bt ai select plan.json                  # ② 仅节点选型，输出 structure.json
autodoor-bt ai scan structure.json               # ③ VLM屏幕感知，输出 structure_filled.json
autodoor-bt ai generate structure_filled.json    # ④ 生成 tree.json + 校验
autodoor-bt ai test tree.json                    # ⑤ 试运行 + 分析
autodoor-bt ai refine tree.json                  # ⑤ 基于上次日志迭代修正

# === 辅助命令 ===
autodoor-bt ai validate tree.json                # 校验JSON结构
autodoor-bt ai nodes                             # 列出所有可用节点规格（从Registry动态导出）
autodoor-bt ai config set ai.llm.base_url "..."  # 配置AI参数
```

### 4.2 阶段间数据流

每阶段输出中间文件，支持单独重做某一阶段而不必从头开始：

```
用户描述 ──→ plan.json ──→ structure.json ──→ structure_filled.json ──→ tree.json
           (①意图)        (②节点选型)          (③VLM填充)              (④生成)
                                                                        │
                                                                        ▼
                                                                  test_report.json
                                                                  (⑤试运行结果)
                                                                        │
                                                                        ▼
                                                                  tree.json (修正版)
                                                                  (⑤迭代修正)
```

中间文件存放在项目目录的 `.ai/` 子目录下，不污染主项目结构。

---

## 5 模块文件结构

```
bt_cli/
├── commands/
│   └── ai.py                    # ai 命令组（CLI入口）
├── ai/                          # AI 编排核心模块
│   ├── __init__.py
│   ├── node_spec_exporter.py    # 从 NodeRegistry 动态导出节点规格
│   ├── intent_analyzer.py       # 阶段①：意图分析（调用LLM）
│   ├── node_selector.py         # 阶段②：节点选型（LLM + NodeSpec）
│   ├── vlm_analyzer.py          # 阶段③：VLM 屏幕感知
│   ├── tree_generator.py        # 阶段④：JSON 生成 + 布局
│   ├── tree_validator.py        # 结构校验器
│   ├── iteration_engine.py      # 阶段⑤：试运行 + 分析 + 修正
│   ├── llm_client.py            # 通用 LLM/VLM API 客户端（OpenAI兼容）
│   └── prompts/                 # 各阶段 Prompt 模板
│       ├── intent_analysis.md   # 阶段①系统提示词
│       ├── node_selection.md    # 阶段②系统提示词
│       ├── vlm_analysis.md      # 阶段③系统提示词
│       └── failure_analysis.md  # 阶段⑤失败分析提示词
```

---

## 6 与现有系统的集成点

| 新组件 | 复用的现有能力 | 集成方式 |
|--------|-------------|---------|
| `NodeSpecExporter` | `NodeRegistry` | 遍历注册表读取节点类，提取参数规格 |
| `VLMAnalyzer` | `ScreenshotManager` / `WindowCapture` | 调用截图能力获取屏幕画面 |
| `TreeGenerator` | `Serializer` | 复用序列化格式生成 tree.json |
| `TreeValidator` | 节点约束规则 | 校验后通过 `Serializer.deserialize` 往返测试 |
| `IterationEngine` | `HeadlessRunner` / `LogManager` | 通过 CLI `run --headless` 试运行，读取日志 |
| `LLMClient` | `CredentialStore` / `config` | API Key 安全存储，配置读取 |
| `ai` CLI 命令 | `bt_cli/commands/` 框架 | 新增命令组，遵循现有命令模式 |

---

## 7 配置项

```json
{
  "ai": {
    "enabled": false,
    "llm": {
      "base_url": "https://api.openai.com/v1",
      "api_key": "",
      "model": "gpt-4o",
      "timeout_ms": 30000,
      "max_tokens": 4096
    },
    "vlm": {
      "base_url": "https://api.openai.com/v1",
      "api_key": "",
      "model": "gpt-4o",
      "timeout_ms": 30000,
      "max_tokens": 4096,
      "image_detail": "high"
    },
    "iteration": {
      "max_rounds": 3,
      "test_timeout_ms": 30000
    }
  }
}
```

- LLM 和 VLM 分别配置，可使用不同模型和端点
- 任何 OpenAI 兼容 API 只需改 `base_url` + `model`
- API Key 通过 `CredentialStore` 安全存储，不明文出现在配置文件中
- 迭代次数和试运行超时时间可配置

---

## 8 实施路线

### 第一阶段（CLI 核心能力）

1. `LLMClient` —— 通用 OpenAI 兼容 API 客户端
2. `NodeSpecExporter` —— 从 NodeRegistry 动态导出节点规格
3. `IntentAnalyzer` —— 阶段①意图分析
4. `NodeSelector` —— 阶段②节点选型
5. `ai plan` / `ai select` / `ai nodes` 命令

### 第二阶段（VLM + 生成）

6. `VLMAnalyzer` —— 阶段③屏幕感知
7. `TreeGenerator` + `TreeValidator` —— 阶段④生成与校验
8. `ai scan` / `ai generate` / `ai validate` 命令
9. `ai create` —— 完整流程串联

### 第三阶段（迭代修正）

10. `IterationEngine` —— 阶段⑤试运行 + 分析 + 修正
11. `ai test` / `ai refine` 命令

### 第四阶段（GUI 内嵌助手，远期）

12. GUI 内嵌 AI 助手面板
13. 画布上直接标注 VLM 识别的区域
14. 可视化迭代修正流程

---

## 9 安全与成本控制

| 风险 | 缓解措施 |
|------|---------|
| LLM 幻觉导致错误结构 | 阶段②节点选型后用户确认；阶段④ TreeValidator 校验 |
| VLM 坐标偏差 | 置信度低于 80% 标记提醒；用户可用放大镜微调 |
| API 调用成本 | 阶段间中间文件缓存，重做某阶段不重复调用前序阶段 |
| API Key 泄露 | 复用 `CredentialStore` 存储；配置文件中不明文 |
| 试运行跑飞 | 限时 30 秒（可配置）；`--timeout` 参数控制 |
| 迭代死循环 | 最大迭代次数限制（默认 3 次）|

---

## 10 设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 交互模式 | CLI 优先，GUI 后续 | CLI 开发成本低，可快速验证核心流程 |
| 节点规格来源 | NodeRegistry 动态导出 | 避免静态 prompt 过时，插件节点自动纳入 |
| 屏幕感知方式 | VLM + 人工确认混合 | VLM 自动填充提效，人工确认保准确 |
| VLM 模型 | 通用 OpenAI 兼容 API | 不绑定具体模型，用户自由选择 |
| 生成方式 | 5 阶段分步生成 | 每阶段可确认可回退，比单次生成更可控 |
| 迭代机制 | 试运行 + AI 分析 + 修正 | 闭环反馈，逐步逼近正确结果 |
| 中间文件 | .ai/ 子目录存储 | 支持单独重做某阶段，不污染项目结构 |

# 插件系统与 CLI 工具完善设计文档

> **日期**: 2026-07-28
> **状态**: 已获用户认可
> **相关文档**: [08_插件系统与CLI工具开发方案.md](../../md/08_插件系统与CLI工具开发方案.md) | [2026-07-28-plugin-system-and-cli.md](./2026-07-28-plugin-system-and-cli.md)

---

## 1 背景与目标

### 1.1 项目现状

当前插件系统与 CLI 工具的 12 个核心 Task 已全部完成：

| 模块 | 完成情况 |
|------|---------|
| 插件系统后端（base.py, loader.py, gui_integration.py） | ✅ |
| 内置示例插件（bt_plugins/builtin/example） | ✅ |
| 插件管理面板（plugin_panel.py） | ✅ |
| GUI 动态合并（constants.py, palette.py, property.py） | ✅ |
| CLI 全部 8 个命令（run/schedule/status/stop/daemon/remote/plugin/config） | ✅ |
| 调度器（scheduler.py）+ run/enable/disable 子命令 | ✅ |
| main.py CLI 入口集成 | ✅ |
| HeadlessRunner 插件集成 | ✅ |
| 测试覆盖（plugin_base, plugin_loader, scheduler, cli_commands 等） | ✅ |
| 方案文档与实施计划文档 | ✅ |

### 1.2 本次目标

基于已完成的插件系统与 CLI 工具，通过并行子代理推进 4 个方向，最终交付：

1. 独立的、详细的 CLI 用户手册文档
2. 回归测试 + 代码质量审查报告 + 修复的代码
3. 完善的插件前端集成（状态栏指示、配置编辑器、错误提示）
4. 真实可用的示例插件（Excel 自动化、文件处理）

---

## 2 整体架构与阶段划分

### 2.1 架构图

```
阶段 1（3 个并行子代理）          阶段 2（1 个子代理，依赖阶段 1）
┌──────────────────────────┐    ┌──────────────────────────┐
│ A: 回归测试 + 代码审查    │    │                          │
│ - 运行全套测试            │    │ D: 添加示例插件          │
│ - code-review 审查       │───▶│ - Excel 自动化插件       │
│ - 修复发现的问题          │    │ - 文件处理插件           │
└──────────────────────────┘    │ - 验证插件系统完整能力    │
┌──────────────────────────┐    └──────────────────────────┘
│ B: 完善插件前端集成       │
│ - 状态栏指示              │
│ - 配置编辑器              │
│ - 错误提示                │
└──────────────────────────┘
┌──────────────────────────┐
│ C: 独立 CLI 用户手册      │
│ - docs/cli-manual.md     │
│ - 完整命令示例            │
│ - 退出码/环境变量/FAQ     │
└──────────────────────────┘
```

### 2.2 依赖关系

- **阶段 1** 三个子代理完全独立，可并行执行
- **阶段 2** 依赖阶段 1 完成（前端集成稳定后示例插件才能验证 GUI 显示）

### 2.3 交付物

1. `docs/cli-manual.md` — 独立 CLI 用户手册
2. `docs/reports/2026-07-28-plugin-system-test-report.md` — 测试报告
3. `docs/reports/2026-07-28-plugin-system-code-review.md` — 代码审查报告
4. 修复后的代码（直接编辑文件）
5. 完善的插件前端（状态栏、配置编辑器、错误提示）
6. `plugins/excel_automation/` — Excel 自动化示例插件
7. `plugins/file_processor/` — 文件处理示例插件
8. 更新后的本设计文档

---

## 3 阶段 1 子代理任务详情

### 3.1 子代理 A — 回归测试 + 代码审查

**目标**：验证现有代码质量，发现并修复潜在问题。

**任务清单**：

1. 运行全套测试套件 `pytest tests/ -v`，收集失败用例
2. 使用 `TRAE-code-review` skill 审查以下关键文件：
   - `bt_plugins/loader.py` — 插件加载器
   - `bt_cli/scheduler.py` — 调度器
   - `bt_cli/commands/plugin.py` — plugin 命令
   - `bt_gui/plugin_panel.py` — 插件管理面板
   - `bt_gui/bt_editor/palette.py` — 节点面板动态加载
3. 修复发现的问题：
   - 测试失败用例
   - 代码质量问题（命名、异常处理、资源泄漏）
   - 潜在的并发问题（调度器线程安全）
4. 输出测试报告 + 代码审查报告

**交付物**：
- 修复后的代码（直接编辑文件）
- `docs/reports/2026-07-28-plugin-system-test-report.md` — 测试报告
- `docs/reports/2026-07-28-plugin-system-code-review.md` — 代码审查报告

### 3.2 子代理 B — 完善插件前端集成

**目标**：完善 GUI 插件管理的细节功能，提升用户体验。

**任务清单**：

1. **状态栏插件指示器**：在 `bt_gui/app.py` 底部状态栏添加 `[● 插件: 2/3 已启动]` 指示器，点击打开插件管理面板
2. **配置编辑器**：在 `bt_gui/plugin_panel.py` 添加插件配置区域，根据 `get_config_schema()` 动态渲染配置项（text/number/select/bool）
3. **错误提示优化**：插件加载/启动失败时，在 PluginCard 上显示红色状态指示器，悬停查看错误详情
4. **刷新机制**：完善 `_on_plugins_changed` 回调，确保节点面板和属性面板同步刷新

**交付物**：
- 修改后的 `bt_gui/app.py`、`bt_gui/plugin_panel.py`
- 新增的 `tests/test_plugin_panel_ui.py`（UI 组件单元测试）

### 3.3 子代理 C — 独立 CLI 用户手册

**目标**：编写独立的、详细的 CLI 用户手册文档。

**任务清单**：

1. 创建 `docs/cli-manual.md`，包含：
   - 安装与快速开始
   - 8 个命令的完整语法、参数、选项、示例
   - `schedule` 的 cron 表达式详解 + 6 个子命令（add/list/remove/run/enable/disable）
   - 退出码参考表
   - 环境变量参考表
   - 配置文件完整说明
   - 日志文件路径
   - 常见问题排查（FAQ）
2. 从 `md/08_插件系统与CLI工具开发方案.md` 提取并扩展使用说明部分
3. 添加端到端使用场景示例（5 个典型场景）

**交付物**：
- `docs/cli-manual.md` — 独立 CLI 用户手册

---

## 4 阶段 2 子代理 D — 添加示例插件

**目标**：实现真实可用的示例插件，验证插件系统完整能力，为用户提供可参考的开发模板。

**任务清单**：

### 4.1 Excel 自动化插件

**目录**: `plugins/excel_automation/`

- 依赖：`openpyxl` 库
- 节点：
  - `ExcelReadNode` — 读取 Excel 文件指定 Sheet 和范围
  - `ExcelWriteNode` — 写入数据到 Excel 文件
  - `ExcelFormatNode` — 应用单元格格式（字体、颜色、边框）
- 适配器：`ExcelAdapter`（封装工作簿操作）
- Schema：完整的节点配置 schema
- 测试：`plugins/excel_automation/tests/test_*.py`

### 4.2 文件处理插件（轻量级，无外部依赖）

**目录**: `plugins/file_processor/`

- 节点：
  - `FileReadNode` — 读取文本文件内容到黑板
  - `FileWriteNode` — 将黑板数据写入文件
  - `FileMoveNode` — 移动/重命名文件
- Schema + 测试

### 4.3 集成验证

- 在 GUI 中加载并启动插件，验证节点出现在「插件节点」分类
- 验证属性面板正确渲染 schema
- 运行 Headless 模式验证 CLI 集成

**交付物**：
- `plugins/excel_automation/` 完整插件目录
- `plugins/file_processor/` 完整插件目录
- 集成验证截图/日志

---

## 5 错误处理与测试策略

### 5.1 错误处理

- 每个子代理独立运行，异常不影响其他子代理
- 子代理失败时，主代理接管并修复
- 插件加载/启动失败时，GUI 显示明确错误提示，不崩溃

### 5.2 测试策略

- 子代理 A 负责回归测试，发现现有问题
- 子代理 B 为新增 UI 功能编写单元测试
- 子代理 D 为示例插件编写完整测试
- 所有修改完成后，子代理 A 重新运行全套测试验证无回归

### 5.3 风险点与应对

| 风险 | 应对措施 |
|------|---------|
| `openpyxl` 依赖可能不可用 | 子代理 D 先检查依赖，缺失则跳过 Excel 插件 |
| GUI 测试需要 display | 使用 mock 或跳过 GUI 测试 |
| 并行修改可能冲突 | 阶段 1 子代理修改不同文件，阶段 2 在阶段 1 完成后执行 |

---

## 6 实施流程

### 6.1 流程图

```
开始
  │
  ├──▶ 阶段 1 并行执行
  │     ├── 子代理 A: 回归测试 + 代码审查
  │     ├── 子代理 B: 完善插件前端集成
  │     └── 子代理 C: 独立 CLI 用户手册
  │
  │   等待全部完成
  │
  └──▶ 阶段 2 执行
        └── 子代理 D: 添加示例插件
              │
              └── 阶段 1 子代理 A 重新运行测试验证无回归
                    │
                    └── 完成
```

### 6.2 使用 Skills

- **brainstorming** — 已完成（设计方案）
- **writing-plans** — 编写详细实施计划
- **dispatching-parallel-agents** — 阶段 1 并行调度子代理
- **subagent-driven-development** — 子代理执行 TDD 工作流
- **TRAE-code-review** — 子代理 A 代码审查
- **test-driven-development** — 子代理 B、D 编写测试
- **verification-before-completion** — 完成前验证

---

## 7 验收标准

1. ✅ `docs/cli-manual.md` 存在且内容完整（8 个命令 + cron + 退出码 + 环境变量 + FAQ）
2. ✅ 全套测试通过（`pytest tests/ -v` 无失败）
3. ✅ 代码审查报告已生成，发现的问题已修复
4. ✅ 插件管理面板具备：状态栏指示器、配置编辑器、错误提示
5. ✅ `plugins/excel_automation/` 可加载并运行（依赖可用时）
6. ✅ `plugins/file_processor/` 可加载并运行
7. ✅ 示例插件在 GUI 中正确显示节点和属性面板

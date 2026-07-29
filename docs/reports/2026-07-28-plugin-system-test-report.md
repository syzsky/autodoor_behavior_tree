# 插件系统与 CLI 工具测试报告

- 报告日期：2026-07-28
- 测试执行人：子代理 A
- 项目路径：`d:\workspace\autodoor_behavior_tree`
- 测试命令：`python -m pytest tests/ -v --tb=short`

## 1. 测试统计

| 指标 | 数值 |
|------|------|
| 测试总数 | 300 |
| 通过数 | 300 |
| 失败数 | 0 |
| 跳过数 | 0 |
| 警告数 | 17 |
| 执行耗时 | 约 7.6 秒 |

> 首次运行结果为 299 passed；修复 cron 周几 bug 后新增 1 个回归测试用例，最终 300 passed。

## 2. 失败用例清单

无失败用例。

## 3. 修复的测试清单

本次未修复失败测试（首次运行即全部通过），但新增了 1 个测试用例以覆盖此前未测试的严重 bug：

| 测试名 | 文件路径 | 说明 |
|--------|----------|------|
| `test_cron_match_weekday` | `tests/test_scheduler.py` | 新增。验证 cron 周几字段的标准约定（0=周日, 1=周一, ..., 6=周六），用于回归 `CronMatcher` 周几转换 bug 修复。 |

## 4. 最终测试结果

```
====================== 300 passed, 17 warnings in 7.61s =======================
```

所有测试通过，无失败、无跳过。17 个警告均为第三方库弃用提示（`ast.Num`/`ast.Str` 在 Python 3.14 将移除、`starlette` 的 `python_multipart` 导入提示、`httpx` 的 `app` 快捷方式弃用），不影响功能，且涉及的代码（如 `bt_nodes/actions/code.py`）不在本次插件系统/CLI 范围内。

## 5. 遗留问题

1. **测试覆盖缺口（建议）**：`bt_cli/commands/plugin.py` 的 `cmd_plugin` 命令分发逻辑、`bt_gui/plugin_panel.py` 的 GUI 交互逻辑目前缺少专门的单元测试覆盖。`test_cli_commands.py` 未覆盖 `plugin` 子命令。建议后续补充。
2. **警告（非阻塞）**：`bt_nodes/actions/code.py` 使用了 `ast.Num`/`ast.Str`/`ast.NameConstant` 等已弃用的 AST 节点，Python 3.14 将移除。该问题超出本次任务范围，未处理。

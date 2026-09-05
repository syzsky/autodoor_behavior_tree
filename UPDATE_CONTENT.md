**0.01**

**修复内容**

- 修复 Linux 兼容性：STARTUPINFO 注解求值崩溃问题（`bt_nodes/actions/code.py`）
- 同步调整 AI 命令行相关测试用例

**0.03**

**新增功能**

- 新增 `autodoor-bt ai run` 一键非交互命令：一条命令串联完成 意图分析 → 节点选型 → VLM屏幕感知 → 生成JSON →（可选）试运行，供 Hermes 等外部 Agent 调用
- 支持 `--json` 机器可读输出、`--workdir`/`--output` 自定义路径、`--no-screen` 跳过屏幕感知、默认不试运行（需 `--test` 显式开启）
- 新增 Hermes/OpenClaw 外部 Agent 对接 skill 草稿（`skills/autodoor-ai-run/`）


**V1.7.2**

**修复内容**

- 修复8月30号后1.7版本无法启动工具的问题
- 尝试修复VLM视觉模型API无法正确使用的问题（仍可能存在问题）


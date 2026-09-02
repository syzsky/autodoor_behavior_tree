---
name: autodoor-ai-run
description: 用自然语言为 AutoDoor 行为树系统生成行为树 JSON 文件，供 Hermes / OpenClaw 等外部 Agent 编排桌面自动化任务。
---

# autodoor-ai-run

当用户需要把一句自然语言指令（如"打开记事本并输入 hello"、"点击左上角红色按钮"）转成 AutoDoor 可执行的行为树时，使用本技能调用 `autodoor-bt ai run`。

## 用法

```
autodoor-bt ai run "<任务描述>" [选项]
```

常用选项：

| 选项 | 说明 |
|---|---|
| `--json` | stdout 输出机器可读 JSON 结果（推荐加） |
| `--no-screen` | 跳过 VLM 屏幕感知（无空间/坐标需求时省调用） |
| `--screenshot <path>` | 用指定截图做屏幕感知 |
| `--output <path>` | 指定最终 tree.json 输出路径 |
| `--workdir <dir>` | 指定中间产物目录（默认 ./.ai） |
| `--test` | 生成后试运行（会真实操作桌面，默认关闭） |
| `--canvas <name>` | 画布/树名 |

## 规则

- 默认**不试运行**、无截图时不自动截屏；涉及坐标/区域/点击位置的任务，先向用户索要截图或明确允许自动截屏后再调用。
- 解析 stdout 的 JSON：`success=true` 时取 `tree_file` 路径；失败时 `error` 含失败阶段与原因。
- 生成后如需直接执行：`autodoor-bt run <tree_file> --headless`（危险动作需用户确认）。
- 任务包含"定位元素/点击位置/OCR 区域"等空间需求时，不要盲生成坐标参数。

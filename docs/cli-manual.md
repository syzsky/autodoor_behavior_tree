# AutoDoor 行为树 CLI 用户手册

> 版本：1.0.0
> 适用对象：自动化测试工程师、运维人员、行为树开发者
> 最后更新：2026-07-28

AutoDoor 行为树 CLI 是一套命令行工具，用于在无 GUI 环境下运行行为树、管理定时调度、查看运行状态、控制守护进程、远程管理服务、加载插件以及读写配置。本手册基于 `cli.py` 路由实现及 `bt_cli/commands/` 下各命令模块编写，覆盖 8 个一级命令的完整用法。

---

## 目录

1. [简介与安装](#1-简介与安装)
2. [快速开始](#2-快速开始)
3. [命令参考](#3-命令参考)
4. [Cron 表达式](#4-cron-表达式)
5. [退出码参考表](#5-退出码参考表)
6. [环境变量参考表](#6-环境变量参考表)
7. [配置文件说明](#7-配置文件说明)
8. [日志](#8-日志)
9. [使用场景](#9-使用场景)
10. [常见问题 FAQ](#10-常见问题-faq)

---

## 1. 简介与安装

### 1.1 CLI 工具简介

`autodoor-bt` 是 AutoDoor 行为树项目的命令行入口，提供以下能力：

- **运行行为树**：支持 GUI 模式和无 GUI（Headless）模式运行
- **定时调度**：基于 cron 表达式、固定间隔或一次性时刻调度行为树执行
- **状态查询**：查看守护进程和运行中行为树的状态
- **停止行为树**：通过 REST API 停止单个或全部行为树
- **守护进程**：后台常驻运行调度器，自动执行定时任务
- **远程控制**：通过 HTTP REST API 远程查询和控制其他节点上的服务
- **插件管理**：扫描、加载、启动、停止、查看插件
- **配置管理**：读取、写入、列出、定位配置文件

CLI 与 GUI 共享同一套配置系统（`SettingsManager`）和消息总线/REST/WebSocket 服务，可平滑互通。

### 1.2 安装方式

CLI 随 AutoDoor 行为树主程序一起分发，无需单独安装。有两种使用方式：

**方式一：直接运行源码脚本**

在项目根目录下执行 `cli.py`：

```bash
# Windows PowerShell
python cli.py --help

# Linux / macOS
python3 cli.py --help
```

本手册后续示例统一以 `autodoor-bt` 作为命令名。若直接使用源码，请将 `autodoor-bt` 替换为 `python cli.py`。

**方式二：使用打包后的可执行文件**

项目通过 PyInstaller 打包（参见 `autodoor_bt.spec` 和 `build.bat`）。打包后 `autodoor-bt`（Windows 下为 `autodoor-bt.exe`）即为 CLI 入口：

```bash
autodoor-bt.exe --help
```

可选：将可执行文件所在目录加入 `PATH`，即可在任意位置调用 `autodoor-bt`。

### 1.3 环境要求

| 项 | 要求 |
|----|------|
| 操作系统 | Windows 10/11、Linux、macOS |
| Python | 3.8 及以上（源码运行方式） |
| 核心依赖 | 见 `requirements.txt` |
| 远程控制依赖 | `requests` 库（`pip install requests`） |
| 磁盘空间 | ≥ 100 MB（含日志与配置） |

> **说明**：`remote` 命令显式依赖 `requests`，缺失时退出码为 4（依赖缺失）。

### 1.4 顶层帮助

不带任何参数运行将打印帮助信息并退出（退出码 0）：

```bash
autodoor-bt
```

输出示例：

```
usage: autodoor-bt [-h] {run,status,stop,schedule,daemon,remote,plugin,config} ...

AutoDoor 行为树 CLI 工具

positional arguments:
  {run,status,stop,schedule,daemon,remote,plugin,config}
                        可用命令
```

---

## 2. 快速开始

以下 5 个示例覆盖最常见使用场景，可直接复制运行。

### 2.1 无 GUI 运行行为树

```bash
autodoor-bt run ./trees/daily_check.json --headless --bus --rest
```

### 2.2 添加每分钟执行的定时任务

```bash
autodoor-bt schedule add ./trees/heartbeat.json --cron "* * * * *" --name "心跳检测" --headless
```

### 2.3 启动守护进程

```bash
autodoor-bt daemon --start
autodoor-bt daemon --status
```

### 2.4 远程查询行为树列表

```bash
autodoor-bt remote 192.168.1.100:8080 trees
```

### 2.5 列出已安装插件并启动

```bash
autodoor-bt plugin list
autodoor-bt plugin start example
```

---

## 3. 命令参考

### 3.1 run — 运行行为树

加载并执行一个行为树 JSON 文件。默认以 GUI 模式启动主应用并打开该文件；加 `--headless` 则在无 GUI 的 Headless 模式下运行。

**语法**

```
autodoor-bt run <tree_file> [options]
```

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tree_file` | 位置参数（必填） | — | 行为树 JSON 文件路径 |
| `--headless` | 标志 | False | 无 GUI 模式运行 |
| `--project` | 字符串 | None | 项目根目录 |
| `--bus` | 标志 | False | 启用消息总线（等价于设置 `message_bus.enabled=true`） |
| `--rest` | 标志 | False | 启用 REST API 服务 |
| `--rest-host` | 字符串 | 127.0.0.1 | REST API 监听地址 |
| `--rest-port` | 整数 | 8080 | REST API 监听端口 |
| `--ws` | 标志 | False | 启用 WebSocket 服务 |
| `--ws-host` | 字符串 | 127.0.0.1 | WebSocket 监听地址 |
| `--ws-port` | 整数 | 8765 | WebSocket 监听端口 |
| `--plugins` | 标志 | False | 启用插件系统（仅打印提示，实际加载由 HeadlessRunner 完成） |

**行为说明**

- 若 `tree_file` 不存在，立即退出，退出码为 3。
- GUI 模式：将文件绝对路径写入环境变量 `AUTODOOR_BT_OPEN_FILE`，重置 `sys.argv` 后调用 `main.main()` 启动 GUI。
- Headless 模式：将 `--bus`/`--rest`/`--ws` 等参数同步写入 `SettingsManager`（仅当前进程生效），然后通过 `HeadlessRunner` 加载并运行行为树。
- 按 `Ctrl+C` 可优雅停止。

**示例**

```bash
# 1. 以 GUI 打开行为树
autodoor-bt run ./trees/login_flow.json

# 2. Headless 模式，开启消息总线 + REST API
autodoor-bt run ./trees/daily_check.json --headless --bus --rest --rest-port 9000

# 3. Headless 模式，开启 WebSocket
autodoor-bt run ./trees/monitor.json --headless --ws --ws-host 0.0.0.0 --ws-port 9001

# 4. 指定项目根目录
autodoor-bt run ./trees/auto_login.json --headless --project ./my_project

# 5. 全部服务开启
autodoor-bt run ./trees/full.json --headless --bus --rest --ws --plugins
```

**输出格式**

```
运行行为树: ./trees/daily_check.json
  模式: Headless
  消息总线: 已启用
  REST API: 127.0.0.1:8080
  WebSocket: 127.0.0.1:8765
  插件系统: 已启用
```

---

### 3.2 schedule — 定时调度

管理定时任务，支持 cron 表达式、固定间隔、一次性执行三种调度方式。任务持久化在 `~/.autodoor_bt/schedules.json`。

**语法**

```
autodoor-bt schedule <add|list|remove|run|enable|disable> [options]
```

不带子命令时打印用法并退出（退出码 1）。

#### 3.2.1 add — 添加定时任务

```
autodoor-bt schedule add <tree_file> (--cron|--interval|--once) [options]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tree_file` | 位置参数（必填） | — | 行为树 JSON 文件路径 |
| `--cron` | 字符串 | None | 5 字段 cron 表达式，如 `"*/5 * * * *"` |
| `--interval` | 字符串 | None | 间隔字符串，格式 `<数字><s\|m\|h>`，如 `30s`、`5m`、`1h` |
| `--once` | 字符串 | None | 一次性执行时刻，ISO 格式 `YYYY-MM-DD HH:MM:SS` |
| `--name` | 字符串 | "" | 任务名称，留空时使用 `tree_file` 作为名称 |
| `--headless` | 标志 | False | 是否以 Headless 模式运行该任务 |

> 必须指定 `--cron`、`--interval`、`--once` 中至少一个，否则退出码 1。

**示例**

```bash
# 每天凌晨 2 点执行
autodoor-bt schedule add ./trees/nightly.json --cron "0 2 * * *" --name "夜间巡检" --headless

# 每 10 分钟执行
autodoor-bt schedule add ./trees/heartbeat.json --interval 10m --name "心跳"

# 一次性：2026 年 12 月 25 日 9 点执行
autodoor-bt schedule add ./trees/xmas.json --once "2026-12-25 09:00:00" --name "圣诞活动"
```

**输出格式**

```
已添加定时任务:
  任务 ID: task_a1b2c3d4
  名称: 夜间巡检
  行为树: ./trees/nightly.json
  Cron: 0 2 * * *
  模式: Headless
```

#### 3.2.2 list — 列出定时任务

```
autodoor-bt schedule list
```

**输出格式**

```
定时任务列表 (2 个):
--------------------------------------------------------------------------------
  ID: task_a1b2c3d4
  名称: 夜间巡检
  行为树: ./trees/nightly.json
  调度: 0 2 * * *
  状态: 启用
  执行次数: 5
  上次执行: 2026-07-28T02:00:00.123456
--------------------------------------------------------------------------------
  ID: task_e5f6g7h8
  名称: 心跳
  行为树: ./trees/heartbeat.json
  调度: 10m
  状态: 启用
  执行次数: 0
--------------------------------------------------------------------------------
```

无任务时输出：`无定时任务`。

#### 3.2.3 remove — 删除定时任务

```
autodoor-bt schedule remove <task_id>
```

删除成功输出 `已删除任务: <task_id>`；任务不存在输出 `未找到任务: <task_id>` 并退出码 1。

#### 3.2.4 run — 立即执行一次

```
autodoor-bt schedule run <task_id>
```

立即触发任务执行（不影响其调度周期）。成功输出 `已触发执行: <task_id>`；未找到则退出码 1。

> **执行机制**：内部通过 `subprocess.Popen` 启动 `python cli.py run <tree_file> [--headless]` 子进程，不阻塞调度器主循环。

#### 3.2.5 enable / disable — 启用 / 禁用任务

```
autodoor-bt schedule enable <task_id>
autodoor-bt schedule disable <task_id>
```

仅切换 `enabled` 标志并持久化，不删除任务。禁用后调度器主循环会跳过该任务。成功输出 `已启用任务` / `已禁用任务`，未找到则退出码 1。

---

### 3.3 status — 查询运行状态

读取守护进程状态文件 `~/.autodoor_bt/daemon_status.json` 并展示当前守护进程与运行中行为树信息。

**语法**

```
autodoor-bt status
```

**参数**：无

**输出格式（守护进程运行时）**

```
守护进程状态:
  PID: 12345
  启动时间: 2026-07-28T10:00:00.000000
  运行中的行为树: 2
    - tree_abc123: running
    - tree_def456: running
```

**输出格式（守护进程未运行）**

```
未检测到运行中的守护进程
使用 'autodoor-bt run <tree_file> --headless' 运行行为树
```

> 说明：`status` 仅查询本地守护进程的状态文件，不直接通过 REST API 查询。要查询远程服务请使用 [remote](#36-remote--远程控制) 命令。

---

### 3.4 stop — 停止行为树

通过本地 REST API（默认 `http://127.0.0.1:8080`）发送停止命令。

**语法**

```
autodoor-bt stop [<tree_id>] [--all] [--force]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tree_id` | 位置参数（可选） | None | 要停止的行为树 ID |
| `--all` | 标志 | False | 停止所有行为树（先 GET `/api/v1/trees` 再逐个 stop） |
| `--force` | 标志 | False | 强制停止标志（当前实现未使用，预留给未来扩展） |

**行为说明**

- 既未提供 `tree_id` 也未指定 `--all`，输出提示并以退出码 1 退出。
- `--all` 时先 GET `/api/v1/trees`，再对每个 `tree_id` 调用 `POST /api/v1/trees/{tree_id}/stop`。
- 连接 REST API 失败时输出 `无法连接到 REST API 服务（服务未启动？）`。
- 成功时输出 `停止命令已发送`。

**示例**

```bash
# 停止单个
autodoor-bt stop tree_abc123

# 停止所有
autodoor-bt stop --all
```

> **注意**：`stop` 命令依赖 REST 服务已启动（即行为树是用 `--rest` 或 `--headless --rest` 启动的）。`--force` 标志当前未实现强制行为，仅做参数预留。

---

### 3.5 daemon — 守护进程模式

管理后台守护进程。守护进程内启动 `Scheduler` 调度器，自动按计划执行定时任务。

**语法**

```
autodoor-bt daemon --start|--stop|--restart|--status|--foreground
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--start` | 标志 | False | 启动守护进程（后台） |
| `--stop` | 标志 | False | 停止守护进程 |
| `--restart` | 标志 | False | 重启守护进程（先 stop 间隔 1 秒再 start） |
| `--status` | 标志 | False | 显示守护进程状态 |
| `--foreground` | 标志 | False | 前台运行守护进程（用于调试或被 `--start` 拉起） |

不带任何标志时打印用法并退出码 1。

**文件位置**

- PID 文件：`~/.autodoor_bt/daemon.pid`
- 状态文件：`~/.autodoor_bt/daemon_status.json`

**行为说明**

- `--start`：先检查 PID 文件，若对应进程仍存活则提示已运行；否则通过 `subprocess.Popen` 拉起 `python cli.py daemon --foreground` 子进程，使用 `CREATE_NO_WINDOW` 标志（Windows）避免弹出窗口。
- `--stop`：读取 PID，发送 `SIGTERM`，并清理 PID 与状态文件。
- `--status`：从状态文件读取 PID、启动时间、运行任务数。
- `--foreground`：写入 PID 与初始状态文件，启动 `Scheduler`，每 60 秒刷新一次状态文件中的 `task_count`，按 `Ctrl+C` 退出并清理文件。

**示例**

```bash
# 启动守护进程
autodoor-bt daemon --start

# 查看状态
autodoor-bt daemon --status

# 重启
autodoor-bt daemon --restart

# 前台运行（调试用）
autodoor-bt daemon --foreground

# 停止
autodoor-bt daemon --stop
```

**输出格式（`--status`）**

```
守护进程状态:
  PID: 12345
  启动时间: 2026-07-28T10:00:00.000000
  运行任务: 3
```

---

### 3.6 remote — 远程控制

通过 HTTP REST API 远程查询和控制目标主机上的 AutoDoor 服务。目标必须已开启 REST API（即用 `--rest` 启动）。

**语法**

```
autodoor-bt remote <target> <action> [--tree-id ID] [--token TOKEN] [--json]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | 位置参数（必填） | — | 目标地址，格式 `host:port` |
| `action` | 位置参数（必填） | — | 操作类型，枚举值：`status`/`trees`/`start`/`stop`/`blackboard`/`nodes` |
| `--tree-id` | 字符串 | None | 目标行为树 ID（`start`/`stop`/`blackboard`/`nodes` 必填） |
| `--token` | 字符串 | None | Bearer Token，附加到 `Authorization` 请求头 |
| `--json` | 标志 | False | 以 JSON 格式输出（保留字段原貌） |

**依赖**：`requests` 库。缺失时输出 `错误: 需要 requests 库` 并退出码 4。

**各 action 调用的接口**

| action | HTTP 方法 | 路径 | 需要 `--tree-id` |
|--------|-----------|------|------------------|
| `status` | GET | `/api/v1/health` | 否 |
| `trees` | GET | `/api/v1/trees` | 否 |
| `start` | POST | `/api/v1/trees/{tree_id}/start` | 是 |
| `stop` | POST | `/api/v1/trees/{tree_id}/stop` | 是 |
| `blackboard` | GET | `/api/v1/trees/{tree_id}/blackboard` | 是 |
| `nodes` | GET | `/api/v1/trees/{tree_id}/nodes` | 是 |

连接失败时输出 `无法连接到 <target>` 并退出码 1。

**示例**

```bash
# 1. 健康检查
autodoor-bt remote 192.168.1.100:8080 status

# 2. 列出所有行为树
autodoor-bt remote 192.168.1.100:8080 trees

# 3. 启动指定行为树
autodoor-bt remote 192.168.1.100:8080 start --tree-id tree_abc123

# 4. 查询黑板变量
autodoor-bt remote 192.168.1.100:8080 blackboard --tree-id tree_abc123

# 5. 查询节点状态
autodoor-bt remote 192.168.1.100:8080 nodes --tree-id tree_abc123

# 6. 带 Token 认证
autodoor-bt remote 192.168.1.100:8080 trees --token my_secret_token
```

**输出格式（`status`）**

```
服务状态: ok
版本: 1.0.0
```

**输出格式（`trees`）**

```
行为树列表 (2 个):
  - tree_abc123: running
  - tree_def456: stopped
```

**输出格式（`blackboard`）**

```
黑板变量 (3 个):
  last_position = (100, 200)
  last_value = 42
  last_ocr_text = hello
```

**输出格式（`nodes`）**

```
节点列表 (5 个):
  - [Sequence] 根节点 (node_001): success
  - [Action] 等待 (node_002): running
  ...
```

---

### 3.7 plugin — 插件管理

扫描、加载、启动、停止、查看插件。插件目录默认扫描两个位置：

1. 内置目录：`<项目根>/bt_plugins/builtin/`
2. 用户目录：`<当前工作目录>/plugins/`

**语法**

```
autodoor-bt plugin <list|load|start|stop|info> [args]
```

不带子命令时打印用法并退出码 1。

> **说明**：每次执行 `plugin` 命令时都会自动扫描上述两个目录并加载其中所有合法插件（带 `plugin.json`），然后才执行子命令。因此 `list`、`info` 等查询命令也能反映新放入目录的插件。

#### 3.7.1 list — 列出已安装插件

```
autodoor-bt plugin list
```

**输出格式**

```
插件列表 (2 个):
------------------------------------------------------------
  示例插件 (example) v1.0.0
    作者: AutoDoor Team
    描述: 插件开发示例
    分类: general
    状态: 已停止
------------------------------------------------------------
  Excel 自动化 (excel_automation) v1.2.0
    作者: AutoDoor Team
    描述: Excel 自动化操作插件
    分类: office
    状态: 已启动
------------------------------------------------------------
```

无插件时输出：`无已加载的插件`。

#### 3.7.2 load — 加载插件

```
autodoor-bt plugin load <path>
```

`path` 为插件目录路径（需包含 `plugin.json` 和入口文件）。

成功输出 `插件加载成功: <path>`；失败输出 `插件加载失败: <path>` 并退出码 1。

**加载流程**（由 `PluginLoader.load_plugin` 实现）：

1. 读取 `plugin.json`，校验必填字段 `name`/`display_name`/`version`/`author`/`description`
2. 检查 `dependencies` 列表是否已加载
3. 通过 `importlib.util.spec_from_file_location` 动态导入入口文件（默认 `main.py`）
4. 实例化 `plugin.json` 中 `class` 字段指定的类，校验为 `BasePlugin` 子类
5. 注入 `PluginContext` 并调用 `on_load()`
6. 失败时回滚 `sys.modules` 中的临时模块

#### 3.7.3 start — 启动插件

```
autodoor-bt plugin start <name>
```

`name` 为插件清单中的 `name` 字段。成功输出 `插件已启动: <name>`；失败退出码 1。

**启动时执行**：调用 `on_start()`，将 `get_nodes()` 返回的节点以 `{plugin_name}.{node_type}` 形式注册到 `NodeRegistry`，注册适配器、服务，并同步 GUI 属性面板 schema。

#### 3.7.4 stop — 停止插件

```
autodoor-bt plugin stop <name>
```

调用 `on_stop()` 并反向注销节点/适配器/服务。输出 `插件已停止: <name>`。

> 注意：`stop` 仅停止插件运行，不从加载器中卸载。如需彻底卸载请通过重启 CLI 进程或重新组织插件目录实现。

#### 3.7.5 info — 查看插件详情

```
autodoor-bt plugin info <name>
```

**输出格式**

```
插件详情:
  名称: example
  显示名: 示例插件
  版本: 1.0.0
  作者: AutoDoor Team
  描述: 插件开发示例
  分类: general
  最低版本: 无限制
  依赖: 无
```

未找到插件时输出 `未找到插件: <name>` 并退出码 1。

---

### 3.8 config — 配置管理

读写 `SettingsManager` 管理的配置文件。所有键支持点号分隔的嵌套路径，如 `rest_server.port`。

**语法**

```
autodoor-bt config <get|set|list|path> [args]
```

不带子命令时提示并退出码 1。

#### 3.8.1 get — 读取配置

```
autodoor-bt config get <key>
```

读取成功输出 `<key> = <value>`；键不存在输出 `配置项不存在: <key>` 并退出码 1。

```bash
autodoor-bt config get rest_server.port
# 输出: rest_server.port = 8080
```

#### 3.8.2 set — 设置配置

```
autodoor-bt config set <key> <value>
```

`value` 自动按以下顺序尝试类型解析：

- 布尔值：`true`/`yes`/`on` → True；`false`/`no`/`off` → False
- 整数：如 `8080`
- 浮点数：如 `3.14`
- 字符串：以上都不匹配时

设置后立即调用 `save_settings()` 持久化，输出 `已设置: <key> = <value>`。

```bash
autodoor-bt config set rest_server.enabled true
autodoor-bt config set rest_server.port 9000
autodoor-bt config set ui.theme dark
```

#### 3.8.3 list — 列出所有配置

```
autodoor-bt config list
```

按 key 字典序输出全部配置项，每行 `<key> = <value>`。

#### 3.8.4 path — 显示配置文件路径

```
autodoor-bt config path
```

输出当前实际使用的配置文件绝对路径。配置文件位置由操作系统决定：

- Windows：`%APPDATA%/autodoor_behavior_tree/config.json`
- Linux/macOS：`~/.config/autodoor_behavior_tree/config.json`

> 注意：项目仓库内 `config/settings.json` 仅作为开发期模板与默认值参考，运行时实际读取的是上述用户配置目录下的 `config.json`。

---

## 4. Cron 表达式

`schedule add --cron` 使用 5 字段标准 cron 表达式。表达式格式为：

```
分 时 日 月 周
```

### 4.1 字段定义

| 字段 | 名称 | 取值范围 | 说明 |
|------|------|----------|------|
| 1 | 分钟 | 0-59 | 每小时的第几分钟 |
| 2 | 小时 | 0-23 | 每天的第几小时（24 小时制） |
| 3 | 日期 | 1-31 | 每月的第几天 |
| 4 | 月份 | 1-12 | 第几月 |
| 5 | 星期 | 0-6 | 0=周日，1=周一，…，6=周六 |

### 4.2 特殊字符

| 字符 | 含义 | 示例 | 说明 |
|------|------|------|------|
| `*` | 任意值（通配） | `* * * * *` | 每分钟执行 |
| `,` | 列表分隔 | `0,15,30,45 * * * *` | 每小时的 0/15/30/45 分执行 |
| `-` | 范围 | `0 9-17 * * 1-5` | 工作日 9 点到 17 点每小时执行 |
| `*/N` | 步进 | `*/5 * * * *` | 每 5 分钟执行 |

> **匹配实现说明**：本项目使用简化版 `CronMatcher`（见 `bt_cli/scheduler.py`）：
> - 不支持 `L`（最后）、`W`（最近工作日）、`#`（第几周）等高级语法
> - 周日既可用 `0` 表示；`dt.weekday()==6`（Python 中周日）也会被归一为 `0`
> - 调度器主循环每 30 秒检查一次，同一分钟内不会重复执行（基于 `last_run` 时间戳防抖）

### 4.3 常见示例

| # | 表达式 | 说明 |
|---|--------|------|
| 1 | `* * * * *` | 每分钟执行 |
| 2 | `*/5 * * * *` | 每 5 分钟执行 |
| 3 | `0 * * * *` | 每小时整点执行 |
| 4 | `0 2 * * *` | 每天凌晨 2 点执行 |
| 5 | `0 9 * * 1-5` | 工作日（周一到周五）早上 9 点执行 |
| 6 | `0 0 * * 0` | 每周日 0 点执行 |
| 7 | `0 0 1 * *` | 每月 1 号 0 点执行 |
| 8 | `0 0 1 1 *` | 每年 1 月 1 号 0 点执行 |

### 4.4 间隔字符串（`--interval`）

`--interval` 不使用 cron，使用简洁格式：`<数字><单位>`，单位支持：

| 单位 | 含义 | 示例 |
|------|------|------|
| `s` | 秒 | `30s` |
| `m` | 分钟 | `5m` |
| `h` | 小时 | `1h` |

### 4.5 一次性执行（`--once`）

`--once` 使用 ISO 格式日期时间字符串：`YYYY-MM-DD HH:MM:SS`。

```bash
autodoor-bt schedule add ./trees/xmas.json --once "2026-12-25 09:00:00" --name "圣诞活动"
```

任务执行一次后，`last_run` 被设置，后续不再触发。

---

## 5. 退出码参考表

| 退出码 | 说明 | 触发场景 |
|--------|------|----------|
| 0 | 成功 | 命令正常执行完成 |
| 1 | 通用错误 | 业务逻辑失败（如任务未找到、参数缺失、API 调用失败） |
| 2 | 配置错误 | 配置项不存在或配置文件解析失败 |
| 3 | 文件未找到 | `run` 命令的 `tree_file` 不存在 |
| 4 | 依赖缺失 | `remote` 命令缺少 `requests` 库 |
| 5 | 认证失败 | 远程服务返回 401（保留，当前由 API 层处理） |
| 6 | 插件错误 | 插件加载/启动失败 |
| 130 | 用户中断（Ctrl+C） | 用户主动中断前台运行进程 |

> **说明**：当前 CLI 实现中显式使用的退出码为 0/1/3/4。2/5/6/130 为约定保留值，便于未来扩展和脚本统一处理。

---

## 6. 环境变量参考表

| 环境变量 | 用途 | 默认值 |
|----------|------|--------|
| `AUTODOOR_BT_CONFIG` | 配置文件路径 | `config/settings.json`（仓库内）→ 运行时迁移到用户配置目录 |
| `AUTODOOR_BT_PLUGINS_DIR` | 插件目录 | `plugins/`（用户插件）+ `bt_plugins/builtin/`（内置） |
| `AUTODOOR_BT_LOG_LEVEL` | 日志级别 | `INFO` |
| `AUTODOOR_BT_DATA_DIR` | 数据目录 | `~/.autodoor_bt/` |
| `AUTODOOR_BT_OPEN_FILE` | GUI 启动时自动打开的行为树文件路径（由 `run` 命令内部设置，一般不手动配置） | 无 |

### 6.1 数据目录说明

`~/.autodoor_bt/` 目录（即 `AUTODOOR_BT_DATA_DIR` 默认值）存放以下运行时文件：

| 文件 | 用途 |
|------|------|
| `daemon.pid` | 守护进程 PID |
| `daemon_status.json` | 守护进程状态（PID、启动时间、任务数、行为树清单） |
| `schedules.json` | 定时任务持久化文件 |

### 6.2 配置目录说明

配置文件存放于操作系统标准配置目录（由 `SettingsManager` 决定）：

- Windows：`%APPDATA%/autodoor_behavior_tree/config.json`
- Linux/macOS：`~/.config/autodoor_behavior_tree/config.json`

执行 `autodoor-bt config path` 可查看实际路径。

---

## 7. 配置文件说明

配置文件为 JSON 格式，由 `SettingsManager` 单例管理。配置文件结构（节选关键字段）：

```json
{
  "version": "1.0.0",
  "tesseract_path": "",
  "alarm_sound_path": "",
  "alarm_volume": 70,
  "default_project_path": "",
  "shortcuts": { "start": "F10", "stop": "F12", "record": "F11" },
  "behavior_tree": {
    "tick_interval": 50,
    "auto_save_interval": 30,
    "default_format": "json"
  },
  "ui": { "theme": "dark", "language": "zh_CN", "font_size": 10 },
  "session": { "last_file_path": "", "recent_files": [] },
  "blackboard": { "default_position_key": "last_detection_position" },
  "input": { "keyboard_method": "pyautogui", "mouse_method": "pyautogui" },
  "message_bus": {
    "enabled": false,
    "shared_thread_pool_size": 8,
    "dead_letter_queue_size": 1000
  },
  "rest_server": {
    "enabled": false,
    "host": "127.0.0.1",
    "port": 8080,
    "auth_enabled": false
  },
  "websocket_server": {
    "enabled": false,
    "host": "127.0.0.1",
    "port": 8765,
    "heartbeat_interval": 30
  },
  "sse_server": { "enabled": true, "max_clients": 10 },
  "adapters": {
    "http": { "enabled": false, "timeout_ms": 5000, "retry_count": 3 },
    "websocket": { "enabled": false, "reconnect_interval_ms": 5000 }
  },
  "auth": {
    "enabled": false,
    "method": "noop",
    "token_expiry_seconds": 3600
  },
  "plugins": {},
  "schedules": {}
}
```

### 7.1 各节说明

| 节 | 字段 | 说明 |
|----|------|------|
| `message_bus` | `enabled` | 是否启用消息总线 |
|  | `shared_thread_pool_size` | 共享线程池大小 |
|  | `dead_letter_queue_size` | 死信队列容量 |
| `rest_server` | `enabled` | 是否启用 REST API |
|  | `host` / `port` | 监听地址和端口 |
|  | `auth_enabled` | 是否启用 REST 鉴权 |
| `websocket_server` | `enabled` | 是否启用 WebSocket |
|  | `host` / `port` | 监听地址和端口 |
|  | `heartbeat_interval` | 心跳间隔（秒） |
| `sse_server` | `enabled` | 是否启用 SSE 推送 |
|  | `max_clients` | 最大客户端数 |
| `adapters` | `http` | HTTP 适配器配置（超时、重试） |
|  | `websocket` | WebSocket 适配器配置（重连间隔） |
| `auth` | `enabled` | 是否启用认证 |
|  | `method` | 认证方式（`noop`/`api_key`/...） |
|  | `token_expiry_seconds` | Token 过期时间 |
| `plugins` | （动态） | 各插件的配置以 `plugins.<plugin_name>.<key>` 形式存储 |
| `schedules` | （动态） | 定时任务运行时元数据（实际任务列表存于 `~/.autodoor_bt/schedules.json`） |
| `behavior_tree` | `tick_interval` | 行为树 tick 间隔（毫秒） |
|  | `auto_save_interval` | 自动保存间隔（秒） |
| `ui` | `theme` | 主题（`dark`/`light`） |
|  | `language` | 语言（`zh_CN`/`en_US`） |
| `input` | `keyboard_method` / `mouse_method` | 输入方式（`pyautogui`/`ib`/`dd`） |

### 7.2 配置访问规则

- 所有键支持点号分隔嵌套路径：`autodoor-bt config get rest_server.port`
- 未设置的键返回默认值（来自 `DEFAULT_SETTINGS`）
- 通过 `config set` 修改的值会立即持久化到用户配置目录下的 `config.json`
- 配置文件包含 `version` 字段，升级时 `SettingsManager._migrate_config` 会自动迁移旧字段

---

## 8. 日志

### 8.1 日志文件路径

| 类型 | 路径 | 说明 |
|------|------|------|
| 调试日志 | `<当前工作目录>/debug_log_<timestamp>.txt` | 由 `LogManager` 写入，文件名带启动时间戳 |
| 调度器日志 | 标准输出（守护进程后台模式下重定向到 `DEVNULL`） | `[Scheduler] ...` 前缀 |
| 插件日志 | 通过 `LogManager.debug_print` 输出 | 前缀 `[Plugin:<name>]` |
| 守护进程状态 | `~/.autodoor_bt/daemon_status.json` | 状态文件，非日志，但常用于排查 |

> **说明**：当前 `LogManager` 将日志写入当前工作目录下的 `debug_log_*.txt`。建议以守护进程方式运行时统一工作目录，便于日志收集。

### 8.2 日志级别

通过环境变量 `AUTODOOR_BT_LOG_LEVEL` 控制输出级别，默认 `INFO`。可选值：`DEBUG`/`INFO`/`WARNING`/`ERROR`。

### 8.3 查看守护进程运行情况

```bash
# 查看状态文件
autodoor-bt daemon --status

# 或直接读取状态文件（Linux/macOS 示例）
cat ~/.autodoor_bt/daemon_status.json
```

---

## 9. 使用场景

### 9.1 场景一：无 GUI 运行行为树（服务器/CI 环境）

在 Linux 服务器或 CI 流水线中，无图形界面运行行为树。

```bash
# 1. 进入项目目录
cd /opt/autodoor_behavior_tree

# 2. 以 headless 模式运行，同时开启消息总线和 REST API
python cli.py run ./trees/ci_check.json --headless --bus --rest --rest-host 0.0.0.0 --rest-port 8080
```

后台运行并记录日志：

```bash
nohup python cli.py run ./trees/ci_check.json --headless --rest > run.log 2>&1 &
```

随后通过 `autodoor-bt status` 或 `autodoor-bt remote 127.0.0.1:8080 status` 查看运行情况。停止时执行 `autodoor-bt stop --all`。

### 9.2 场景二：定时执行任务

每天凌晨 2 点自动执行巡检行为树，并以后台守护进程方式运行调度器。

```bash
# 1. 添加定时任务
autodoor-bt schedule add ./trees/nightly_check.json \
  --cron "0 2 * * *" \
  --name "夜间巡检" \
  --headless

# 2. 启动守护进程（自动加载 schedules.json 中的所有任务）
autodoor-bt daemon --start

# 3. 查看任务列表确认
autodoor-bt schedule list

# 4. 查看守护进程状态
autodoor-bt daemon --status
```

如需立即测试任务是否能正常运行：

```bash
autodoor-bt schedule run task_a1b2c3d4
```

### 9.3 场景三：守护进程模式

适合需要 7x24 小时运行多个定时任务的场景。

```bash
# 启动守护进程
autodoor-bt daemon --start

# 查看状态
autodoor-bt daemon --status

# 重启（修改 schedules.json 后建议重启）
autodoor-bt daemon --restart

# 调试模式：前台运行，直接观察 [Scheduler] 输出
autodoor-bt daemon --foreground

# 停止
autodoor-bt daemon --stop
```

守护进程会每 60 秒刷新 `daemon_status.json` 中的 `task_count`。

### 9.4 场景四：远程控制

在中心节点统一管理多台机器上的行为树执行。

```bash
# 1. 在被控端启动行为树并开启 REST API
# （在被控机器上）
autodoor-bt run ./trees/worker.json --headless --rest --rest-host 0.0.0.0 --rest-port 8080

# 2. 在控制端查询所有远程行为树
autodoor-bt remote 192.168.1.100:8080 trees
autodoor-bt remote 192.168.1.101:8080 trees

# 3. 查询某行为树的黑板变量和节点状态
autodoor-bt remote 192.168.1.100:8080 blackboard --tree-id tree_abc123
autodoor-bt remote 192.168.1.100:8080 nodes --tree-id tree_abc123

# 4. 远程停止
autodoor-bt remote 192.168.1.100:8080 stop --tree-id tree_abc123

# 5. 启用 Token 认证（被控端配置 auth.enabled=true）
autodoor-bt remote 192.168.1.100:8080 trees --token my_secret_token
```

### 9.5 场景五：使用插件

加载并启动插件以扩展行为树节点、适配器或服务。

```bash
# 1. 列出内置和用户插件
autodoor-bt plugin list

# 2. 加载自定义插件目录
autodoor-bt plugin load ./plugins/my_plugin

# 3. 查看插件详情
autodoor-bt plugin info my_plugin

# 4. 启动插件（注册节点到 NodeRegistry）
autodoor-bt plugin start my_plugin

# 5. 停止插件
autodoor-bt plugin stop my_plugin
```

插件节点在行为树 JSON 中以 `{plugin_name}.{node_type}` 形式引用，避免与其他插件或内置节点命名冲突。

---

## 10. 常见问题 FAQ

### Q1: 如何查看行为树运行状态？

**A**: 有两种方式：

1. 本地：`autodoor-bt status` — 读取本地守护进程状态文件。
2. 远程：`autodoor-bt remote <host:port> trees` — 通过 REST API 查询运行中的行为树列表，或 `remote <host:port> status` 查询服务健康度。

注意 `status` 命令只反映守护进程的状态文件，要查询具体行为树状态请使用 `remote` 命令或直接 GET `/api/v1/trees`。

### Q2: 定时任务不执行怎么办？

**A**: 按以下顺序排查：

1. 确认守护进程在运行：`autodoor-bt daemon --status`。
2. 确认任务处于启用状态：`autodoor-bt schedule list` 查看 `状态` 字段为 `启用`。
3. 检查 cron 表达式或 `--interval` 格式是否正确（cron 必须是 5 字段，间隔必须是 `<数字><s|m|h>`）。
4. 调度器主循环每 30 秒检查一次，cron 同一分钟内不会重复执行（防抖），请等待下一分钟。
5. 以前台模式运行守护进程观察日志：`autodoor-bt daemon --foreground`，查看 `[Scheduler] 执行任务: ...` 输出。
6. 手动触发一次任务验证：`autodoor-bt schedule run <task_id>`。

### Q3: 插件加载失败如何排查？

**A**: 常见原因：

1. **缺少 `plugin.json`**：插件目录必须含 `plugin.json`，且必填字段为 `name`/`display_name`/`version`/`author`/`description`。
2. **未指定 `class` 字段**：`plugin.json` 中 `class` 字段必须指向 `BasePlugin` 子类的类名。
3. **入口文件不存在**：`entry` 字段（默认 `main.py`）必须存在于插件目录。
4. **依赖未加载**：`dependencies` 列表中的插件必须先加载。
5. **类不是 BasePlugin 子类**：插件类必须继承 `bt_plugins.base.BasePlugin`。
6. **`on_load` 抛异常**：检查插件 `on_load()` 实现。

排查方法：以前台模式运行 `autodoor-bt daemon --foreground` 或直接执行 `autodoor-bt plugin load <path>`，观察 `[PluginLoader] ...` 输出的具体错误信息。

### Q4: REST API 端口被占用怎么办？

**A**: 通过 `--rest-port` 指定其他端口，或修改配置：

```bash
# 命令行临时指定
autodoor-bt run ./trees/x.json --headless --rest --rest-port 9000

# 持久化到配置
autodoor-bt config set rest_server.port 9000
```

Linux 下查找占用进程：`lsof -i :8080`；Windows 下：`netstat -ano | findstr :8080`。

### Q5: 如何在后台长期运行？

**A**: 推荐使用守护进程模式：

```bash
autodoor-bt daemon --start
```

守护进程会以后台子进程方式运行 `cli.py daemon --foreground`，并自动启动调度器执行所有定时任务。PID 写入 `~/.autodoor_bt/daemon.pid`，状态写入 `~/.autodoor_bt/daemon_status.json`。

如不使用守护进程，也可用 `nohup` 或系统服务管理器（systemd/Windows Service）直接拉起 `python cli.py run <tree> --headless`。

### Q6: 配置文件路径在哪？

**A**: 执行以下命令查看实际路径：

```bash
autodoor-bt config path
```

默认位置：

- Windows：`%APPDATA%/autodoor_behavior_tree/config.json`
- Linux/macOS：`~/.config/autodoor_behavior_tree/config.json`

仓库内 `config/settings.json` 仅为开发模板，运行时不直接读取。

### Q7: 如何查看日志？

**A**: 当前 `LogManager` 将调试日志写入当前工作目录下的 `debug_log_<timestamp>.txt`，文件名包含启动时间戳。建议：

1. 统一工作目录运行 CLI，便于日志收集。
2. 守护进程后台模式日志默认重定向到 `DEVNULL`，如需查看请使用 `--foreground` 前台模式。
3. 调度器日志以 `[Scheduler]` 前缀输出到 stdout。
4. 插件日志以 `[Plugin:<name>]` 前缀输出。
5. 可通过 `AUTODOOR_BT_LOG_LEVEL=DEBUG` 环境变量提高日志详细度。

### Q8: 守护进程异常退出怎么恢复？

**A**: 守护进程异常退出（如机器重启、进程被 kill）后，PID 文件可能残留但进程已不存在。恢复步骤：

1. 检查状态：`autodoor-bt daemon --status`。若提示状态文件不存在或读取失败，说明已退出。
2. 清理残留 PID 文件（如 `_start_daemon` 检测到进程不存在会自动跳过，但保险起见可手动删除）：`rm ~/.autodoor_bt/daemon.pid`。
3. 重新启动：`autodoor-bt daemon --start`。

定时任务持久化在 `~/.autodoor_bt/schedules.json`，重启守护进程后会自动加载恢复，无需重新添加。

### Q9: 远程控制需要认证吗？

**A**: 取决于被控端的 `auth.enabled` 配置：

- `auth.enabled=false`（默认）：无需认证，直接 `autodoor-bt remote <target> <action>` 即可。
- `auth.enabled=true`：需要通过 `--token` 提供 Bearer Token：`autodoor-bt remote <target> trees --token <your_token>`。Token 会被附加到 HTTP `Authorization: Bearer <token>` 请求头。

被控端认证方式由 `auth.method` 决定（如 `noop`、`api_key` 等）。

### Q10: 如何卸载插件？

**A**: CLI 当前未提供直接的 `plugin unload` 命令。卸载步骤：

1. 停止插件：`autodoor-bt plugin stop <name>`。
2. 从插件目录中移除插件文件夹（`bt_plugins/builtin/<name>` 或 `<cwd>/plugins/<name>`）。
3. 重启 CLI 进程（或守护进程），插件将不再被自动扫描加载。

`PluginLoader` 内部实现了 `unload_plugin` 方法（调用 `on_unload` 并清理 `sys.modules`），但 CLI 层暂未暴露为子命令。

### Q11: `run` 命令的 `--rest` 配置会被保存到配置文件吗？

**A**: 会临时写入 `SettingsManager` 的内存配置（影响当前进程的服务启动行为），但**不会**自动持久化到 `config.json`。下次启动如果不带 `--rest`，REST 服务不会自动启用。若需持久化，请使用 `autodoor-bt config set rest_server.enabled true`。

### Q12: 同一台机器能同时运行多个行为树吗？

**A**: 可以。每个 `autodoor-bt run ... --headless` 命令会启动一个独立进程。但注意：

- 多个进程若都启用 REST API，必须使用不同端口（`--rest-port`）。
- 调度器执行的多个任务默认各自启动子进程，互不干扰。
- 通过 `autodoor-bt remote 127.0.0.1:<port> trees` 可查询指定端口下的行为树列表。

---

## 附录：命令速查表

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `run` | 运行行为树 | `--headless`、`--bus`、`--rest`、`--ws`、`--plugins` |
| `schedule add` | 添加定时任务 | `--cron`、`--interval`、`--once`、`--name`、`--headless` |
| `schedule list` | 列出定时任务 | — |
| `schedule remove` | 删除定时任务 | `<task_id>` |
| `schedule run` | 立即执行一次 | `<task_id>` |
| `schedule enable` / `disable` | 启用/禁用任务 | `<task_id>` |
| `status` | 查询守护进程状态 | — |
| `stop` | 停止行为树 | `<tree_id>`、`--all`、`--force` |
| `daemon` | 守护进程管理 | `--start`、`--stop`、`--restart`、`--status`、`--foreground` |
| `remote` | 远程控制 | `<target>`、`<action>`、`--tree-id`、`--token`、`--json` |
| `plugin list` | 列出插件 | — |
| `plugin load` | 加载插件 | `<path>` |
| `plugin start` / `stop` | 启动/停止插件 | `<name>` |
| `plugin info` | 查看插件详情 | `<name>` |
| `config get` / `set` / `list` / `path` | 配置管理 | `<key>`、`<value>` |

---

*本手册基于 `cli.py` 与 `bt_cli/` 目录下的源码实现编写，如代码有更新请同步修订。*

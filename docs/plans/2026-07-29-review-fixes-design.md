# 审查问题修复设计文档

> 创建日期: 2026-07-29
> 基于: 消息总线与外部系统集成审查报告 + 插件系统与 CLI 工具审查报告
> 修复范围: 4 个高优先级 + 12 个中优先级 = 16 项
> 修复策略: 修复 + 局部重构
> 测试策略: TDD 流程（先写测试复现 → 修复 → 验证通过）

---

## 1. 问题清单

### Tier 1: 高优先级（4 项）

| ID | 问题 | 模块 | 影响 |
|----|------|------|------|
| B1/B2/R1 | remote.py trees/status/nodes 数据解析错误 | bt_cli/commands/remote.py | CLI 远程控制命令输出错误数据 |
| A1 | PluginLoader 缺乏线程安全保护 | bt_plugins/loader.py | 多线程并发访问导致数据竞争 |
| R2 | daemon stop 在 Windows 上不可用 | bt_cli/commands/daemon.py | Windows 平台守护进程无法停止 |
| A2 | SSE 无界队列 OOM 风险 | bt_bus/message_bus.py, bt_servers/rest_server.py | 长时间运行内存耗尽 |

### Tier 2: 中优先级（12 项）

| ID | 问题 | 模块 | 主题 |
|----|------|------|------|
| A3 | MessageBus 单例初始化竞态 | bt_bus/message_bus.py | 线程安全 |
| A4 | HTTPAdapter 线程安全不足 | bt_adapters/http_adapter.py | 线程安全 |
| P1 | ServiceRegistry 持锁执行 start/stop | bt_services/registry.py | 线程安全 |
| B3 | _deliver 递归发布无深度限制 | bt_bus/message_bus.py | 逻辑修复 |
| B4 | ValidationMiddleware 静默丢弃消息 | bt_bus/middleware.py | 逻辑修复 |
| B6 | AdapterManager 缺 unregister_adapter | bt_adapters/adapter_manager.py | 逻辑修复 |
| C1 | CLI plugin 命令缺少 unload | cli.py, bt_cli/commands/plugin.py | CLI 增强 |
| R3 | run --headless 配置不落盘 | bt_cli/commands/run.py | CLI 增强 |
| R5 | schedule add 未验证文件存在 | bt_cli/scheduler.py | CLI 增强 |
| E1 | CLI 错误处理不统一 | bt_cli/ 各命令模块 | CLI 增强 |
| E2 | schedule run 执行失败无反馈 | bt_cli/scheduler.py | CLI 增强 |
| D1 | plugin-guide.md 提到不存在的卸载按钮 | docs/plugin-guide.md | 文档同步 |
| D2 | cli-manual.md 退出码表与实现不符 | docs/cli-manual.md | 文档同步 |

---

## 2. 修复方案

### 2.1 Tier 1: 高优先级修复

#### 2.1.1 remote.py 数据解析修复（B1, B2, R1）

**根因**: REST API 返回 `{"trees": [...]}` / `{"nodes": [...]}` 包装结构，CLI 代码直接遍历 JSON 根而非提取内层字段。`/api/v1/health` 缺少 `version` 字段。

**修复**:
- `bt_servers/rest_server.py`: health 端点添加 `version` 字段
- `bt_cli/commands/remote.py`:
  - `_do_status`: 输出 version 字段
  - `_do_trees`: `data = resp.json(); trees = data.get("trees", [])`
  - `_do_nodes`: `data = resp.json(); nodes = data.get("nodes", [])`
  - `_do_blackboard`: 已正确（直接返回字典），无需修改

**测试**: 新建 `tests/test_remote_commands.py`，mock requests 响应验证解析。

#### 2.1.2 PluginLoader 线程安全（A1）

**根因**: `_plugins`、`_plugin_infos`、`_plugin_dirs`、`_registered_nodes` 等字典无锁保护。

**修复**:
- `PluginLoader.__init__` 添加 `self._lock = threading.RLock()`
- 所有公共方法（`load_plugin`、`unload_plugin`、`start_plugin`、`stop_plugin`、`start_all`、`stop_all`、`list_plugins`、`is_started`、`get_plugin_info`、`get_registered_display_info`、`get_registered_schemas`、`get_plugin_config_schema`）用 `with self._lock:` 包裹

**测试**: 多线程并发 `load_plugin` + `start_plugin` 测试，验证无竞态。

#### 2.1.3 Windows 守护进程兼容性（R2）

**根因**: `signal.SIGTERM` 在 Windows 上不存在。

**修复**:
- `bt_cli/commands/daemon.py` 的 `_stop_daemon()` 添加平台检测:
  - Windows: `subprocess.call(["taskkill", "/PID", str(pid), "/F"])`
  - Unix: `os.kill(pid, signal.SIGTERM)`

**测试**: mock `platform.system()` 验证不同平台调用路径。

#### 2.1.4 SSE 无界队列 OOM 修复（A2）

**根因**: `subscribe_async` 创建无界 `asyncio.Queue`，慢消费者堆积消息导致内存耗尽。

**修复**:
- `bt_bus/message_bus.py`:
  - `subscribe_async` 添加 `maxsize` 参数（默认 1000）
  - `_push_to_single_async_queue` 中队列满时丢弃最旧消息并记录警告
- `bt_servers/rest_server.py`: SSE 端点调用 `subscribe_async("bt.**.event.**", maxsize=500)`

**测试**: 填充超过 maxsize 消息，验证旧消息被丢弃、新消息保留。

---

### 2.2 Tier 2: 中优先级修复

#### 2.2.1 线程安全主题（A3, A4, P1）

**A3 — MessageBus 初始化竞态**:
- `__init__` 中 `_initialized` 检查移入 `_lock` 范围

**A4 — HTTPAdapter 竞态**:
- `call()` 方法中 `self._lock` 保护整个 session 初始化和首次请求

**P1 — ServiceRegistry 持锁执行**:
- `start_all`/`stop_all`: 锁内复制服务列表，锁外遍历调用

#### 2.2.2 逻辑修复主题（B3, B4, B6）

**B3 — _deliver 递归限制**:
- 添加 `MAX_DELIVER_DEPTH = 5` 常量
- `_deliver` 检查 `msg.headers.get("_deliver_depth", 0)`，超限记录死信

**B4 — ValidationMiddleware 死信记录**:
- 验证失败时调用 `MessageBus._dead_letter_queue.add(msg, "VALIDATION_FAILED")`
- 需在 MessageBus 中暴露死信队列访问方法或通过回调注入

**B6 — AdapterManager unregister_adapter**:
- 添加 `unregister_adapter(name)` 方法
- `bt_plugins/loader.py` 的 `stop_plugin` 中调用 `am.unregister_adapter()`

#### 2.2.3 CLI 增强主题（C1, R3, R5, E1, E2）

**C1 — plugin unload 命令**:
- `cli.py`: 添加 `plugin unload` subparser
- `bt_cli/commands/plugin.py`: 添加 `_unload_plugin` 函数

**R3 — run 配置落盘**:
- `bt_cli/commands/run.py`: CLI 参数设置后调用 `settings.save_settings()`

**R5 — schedule 文件验证**:
- `bt_cli/scheduler.py`: `add_task` 中检查 `os.path.isfile(tree_file)`

**E1 — 统一错误处理**:
- 新建 `bt_cli/errors.py`:
  ```python
  EXIT_SUCCESS = 0
  EXIT_GENERIC_ERROR = 1
  EXIT_CONFIG_ERROR = 2
  EXIT_FILE_NOT_FOUND = 3
  EXIT_DEPENDENCY_MISSING = 4
  EXIT_AUTH_FAILED = 5
  EXIT_PLUGIN_ERROR = 6
  EXIT_INTERRUPTED = 130

  def exit_with_code(code: int, message: str = ""):
      if message:
          print(message)
      sys.exit(code)
  ```
- 各命令模块替换 `sys.exit(N)` 为 `exit_with_code(EXIT_xxx, "msg")`

**E2 — schedule run 执行反馈**:
- `scheduler.py`: `_execute_task` 改用 `subprocess.run()` 捕获返回码
- 记录执行状态到任务的 `last_run_status` 字段

#### 2.2.4 文档同步主题（D1, D2）

**D1 — plugin-guide.md 卸载按钮**:
- 移除"卸载"按钮描述
- 说明通过 CLI `plugin unload` 命令卸载

**D2 — cli-manual.md 退出码表**:
- 更新退出码表，与 `bt_cli/errors.py` 中定义一致
- 标注哪些退出码已实现、哪些为预留

---

## 3. 执行顺序

```
Tier 1（高优先级，按模块分组）
  ├─ Step 1: remote.py + rest_server.py 数据解析修复
  ├─ Step 2: loader.py 线程安全
  ├─ Step 3: daemon.py Windows 兼容性
  └─ Step 4: message_bus.py + rest_server.py SSE 队列上限

Tier 2（中优先级，按主题分组）
  ├─ Step 5: 线程安全主题（message_bus.py, http_adapter.py, registry.py）
  ├─ Step 6: 逻辑修复主题（message_bus.py, middleware.py, adapter_manager.py, loader.py）
  ├─ Step 7: CLI 增强主题（cli.py, plugin.py, run.py, scheduler.py, errors.py）
  └─ Step 8: 文档同步主题（plugin-guide.md, cli-manual.md）
```

每个 Step 遵循 TDD: 写测试 → 验证失败 → 修复 → 验证通过 → 回归测试。

---

## 4. 涉及文件清单

| 文件 | 修改类型 | Step |
|------|----------|------|
| `bt_cli/commands/remote.py` | 修改 | 1 |
| `bt_servers/rest_server.py` | 修改 | 1, 4 |
| `bt_plugins/loader.py` | 修改 | 2, 6 |
| `bt_cli/commands/daemon.py` | 修改 | 3 |
| `bt_bus/message_bus.py` | 修改 | 4, 5, 6 |
| `bt_adapters/http_adapter.py` | 修改 | 5 |
| `bt_services/registry.py` | 修改 | 5 |
| `bt_bus/middleware.py` | 修改 | 6 |
| `bt_adapters/adapter_manager.py` | 修改 | 6 |
| `cli.py` | 修改 | 7 |
| `bt_cli/commands/plugin.py` | 修改 | 7 |
| `bt_cli/commands/run.py` | 修改 | 7 |
| `bt_cli/scheduler.py` | 修改 | 7 |
| `bt_cli/errors.py` | 新建 | 7 |
| `docs/plugin-guide.md` | 修改 | 8 |
| `docs/cli-manual.md` | 修改 | 8 |
| `tests/test_remote_commands.py` | 新建 | 1 |
| `tests/test_plugin_loader_threadsafe.py` | 新建 | 2 |
| `tests/test_daemon_platform.py` | 新建 | 3 |
| `tests/test_sse_queue_bounds.py` | 新建 | 4 |
| `tests/test_thread_safety_fixes.py` | 新建 | 5 |
| `tests/test_logic_fixes.py` | 新建 | 6 |
| `tests/test_cli_enhancements.py` | 新建 | 7 |

---

## 5. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 线程安全锁引入死锁 | 中 | 高 | 使用 RLock 而非 Lock；TDD 测试覆盖并发场景 |
| MessageBus 锁粒度过大影响性能 | 低 | 中 | 仅保护字典访问，不保护回调执行 |
| errors.py 退出码变更破坏现有脚本 | 低 | 低 | 保持退出码数值不变，仅统一调用方式 |
| 文档修改遗漏 | 低 | 低 | 对照代码逐项验证 |

# 插件系统与 CLI 工具完善实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在已完成的插件系统与 CLI 工具基础上，通过并行子代理推进 4 个方向：CLI 用户手册、回归测试与代码审查、前端集成完善、示例插件开发。

**Architecture:** 阶段 1 包含 3 个完全独立的并行子代理（A: 测试+审查、B: 前端集成、C: 用户手册），阶段 2 包含 1 个依赖阶段 1 的子代理（D: 示例插件）。每个子代理遵循 TDD 工作流，完成后由主代理验证。

**Tech Stack:** Python 3.10+, CustomTkinter (GUI), argparse (CLI), openpyxl (Excel 插件), pytest (测试)

**参考文档:**
- [设计文档](./2026-07-28-plugin-system-and-cli-design.md)
- [08_插件系统与CLI工具开发方案.md](../../md/08_插件系统与CLI工具开发方案.md)
- [2026-07-28-plugin-system-and-cli.md](./2026-07-28-plugin-system-and-cli.md)

---

## 执行说明

本计划包含 4 个子代理任务，建议使用 `dispatching-parallel-agents` skill 并行调度阶段 1 的子代理 A、B、C，阶段 1 完成后再调度子代理 D。

每个子代理任务内部按 TDD 步骤组织：写测试 → 验证失败 → 实现 → 验证通过 → 提交。

---

# 阶段 1：并行子代理任务

## 子代理 A: 回归测试 + 代码审查

### Task A1: 运行全套测试并收集结果

**Files:**
- Read: `tests/` 全部测试文件

**Step 1: 运行全套测试**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tee test_results.txt`

Expected: 输出测试结果到 `test_results.txt`，记录通过/失败数量

**Step 2: 分析失败用例**

读取 `test_results.txt`，对每个失败的测试用例：
- 记录测试名称和失败原因
- 查找对应的源代码文件
- 分析失败根本原因

**Step 3: 创建测试报告草稿**

创建 `docs/reports/2026-07-28-plugin-system-test-report.md`，包含：
- 测试总数 / 通过数 / 失败数 / 跳过数
- 失败用例清单（测试名 + 文件路径 + 失败原因）
- 修复建议

---

### Task A2: 代码审查 — bt_plugins/loader.py

**Files:**
- Read: `bt_plugins/loader.py`

**Step 1: 使用 TRAE-code-review skill 审查**

调用 `TRAE-code-review` skill，审查 `bt_plugins/loader.py`，关注：
- 异常处理是否完整（动态导入、on_load/on_start 异常）
- 资源泄漏（sys.modules 未清理、插件停止后资源未释放）
- 线程安全（_plugins 字典并发访问）
- 命名规范和代码风格

**Step 2: 记录审查发现**

在 `docs/reports/2026-07-28-plugin-system-code-review.md` 中记录：
- 严重问题（影响功能）
- 警告（潜在风险）
- 建议（代码质量改进）

---

### Task A3: 代码审查 — bt_cli/scheduler.py

**Files:**
- Read: `bt_cli/scheduler.py`

**Step 1: 审查调度器线程安全**

调用 `TRAE-code-review` skill，审查 `bt_cli/scheduler.py`，关注：
- `_tasks` 字典在多线程访问时的安全性
- `_stop_event` 的正确使用
- 任务持久化的原子性（_save 写入文件时崩溃）
- CronMatcher 的边界情况（无效表达式、越界值）

**Step 2: 记录并修复发现的问题**

对于严重问题，直接编辑 `bt_cli/scheduler.py` 修复。

---

### Task A4: 代码审查 — bt_gui/plugin_panel.py 和 palette.py

**Files:**
- Read: `bt_gui/plugin_panel.py`
- Read: `bt_gui/bt_editor/palette.py`

**Step 1: 审查 GUI 代码**

审查以下方面：
- `_notify_plugins_changed` 回调的异常处理
- `refresh_plugin_nodes` 中销毁旧 section 的安全性（winfo_exists 检查）
- PluginCard 状态切换的内存泄漏（事件绑定未解绑）

**Step 2: 记录发现**

将发现追加到代码审查报告。

---

### Task A5: 修复测试失败用例

**Files:**
- Modify: 视失败用例而定

**Step 1: 根据测试报告修复失败用例**

对 Task A1 中发现的每个失败测试：
- 分析根本原因
- 修复源代码或更新测试断言
- 重新运行单个测试验证修复

Run: `python -m pytest tests/<failing_test>.py -v`

**Step 2: 重新运行全套测试**

Run: `python -m pytest tests/ -v`

Expected: 全部测试通过（或剩余失败有合理解释）

**Step 3: 完成测试报告**

更新 `docs/reports/2026-07-28-plugin-system-test-report.md`，添加：
- 修复的测试清单
- 最终测试结果
- 遗留问题（如有）

**Step 4: Commit**

```bash
git add docs/reports/ <修复的源文件> <修复的测试文件>
git commit -m "fix: resolve test failures and code review issues in plugin system"
```

---

## 子代理 B: 完善插件前端集成

### Task B1: 编写状态栏插件指示器测试

**Files:**
- Test: `tests/test_plugin_panel_ui.py`

**Step 1: 编写失败测试**

```python
# tests/test_plugin_panel_ui.py
"""插件面板 UI 组件测试"""
import pytest
from unittest.mock import MagicMock, patch


def test_plugin_status_indicator_creation():
    """测试插件状态栏指示器创建"""
    # 由于 GUI 测试需要 display，使用 mock
    try:
        import customtkinter as ctk
        # 跳过如果无法创建窗口
        try:
            root = ctk.CTk()
            root.withdraw()
        except Exception:
            pytest.skip("无法创建 GUI 窗口")

        from bt_gui.plugin_panel import PluginStatusBarIndicator
        loader = MagicMock()
        loader.list_plugins.return_value = []
        loader.is_started.return_value = False

        indicator = PluginStatusBarIndicator(root, loader)
        assert indicator is not None

        # 测试无插件时的状态
        assert indicator.get_status_text() == "插件: 0/0 已启动"

        root.destroy()
    except ImportError:
        pytest.skip("customtkinter 不可用")


def test_plugin_status_indicator_with_plugins():
    """测试有插件时的状态指示器"""
    try:
        import customtkinter as ctk
        try:
            root = ctk.CTk()
            root.withdraw()
        except Exception:
            pytest.skip("无法创建 GUI 窗口")

        from bt_gui.plugin_panel import PluginStatusBarIndicator
        loader = MagicMock()

        # 模拟 3 个插件，2 个已启动
        from bt_plugins.base import PluginInfo
        infos = [
            PluginInfo(name=f"plugin_{i}", display_name=f"插件{i}",
                       version="1.0.0", author="t", description="d")
            for i in range(3)
        ]
        loader.list_plugins.return_value = infos
        loader.is_started.side_effect = lambda name: name in ("plugin_0", "plugin_1")

        indicator = PluginStatusBarIndicator(root, loader)
        assert indicator.get_status_text() == "插件: 2/3 已启动"

        root.destroy()
    except ImportError:
        pytest.skip("customtkinter 不可用")
```

**Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_plugin_panel_ui.py::test_plugin_status_indicator_creation -v`

Expected: FAIL with `ImportError: cannot import name 'PluginStatusBarIndicator'`

---

### Task B2: 实现状态栏插件指示器

**Files:**
- Modify: `bt_gui/plugin_panel.py`
- Modify: `bt_gui/app.py`

**Step 1: 在 plugin_panel.py 添加 PluginStatusBarIndicator 类**

在 `bt_gui/plugin_panel.py` 末尾添加：

```python
class PluginStatusBarIndicator(ctk.CTkFrame):
    """状态栏插件状态指示器 — 显示已启动插件数量，点击打开插件管理面板"""

    def __init__(self, master, plugin_loader, on_click=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._loader = plugin_loader
        self._on_click = on_click

        self._dark_colors = Theme.get_dark_colors()

        self._status_label = ctk.CTkLabel(
            self,
            text=self.get_status_text(),
            font=Theme.get_font('xs'),
            text_color=self._dark_colors['text_muted'],
            cursor="hand2" if on_click else "arrow"
        )
        self._status_label.pack(side="left", padx=4, pady=2)

        if on_click:
            self._status_label.bind("<Button-1>", lambda e: on_click())
            self.bind("<Button-1>", lambda e: on_click())

    def get_status_text(self) -> str:
        """获取状态文本"""
        try:
            infos = self._loader.list_plugins() if self._loader else []
            total = len(infos)
            if total == 0:
                return "插件: 0/0 已启动"
            started = sum(1 for info in infos if self._loader.is_started(info.name))
            return f"插件: {started}/{total} 已启动"
        except Exception:
            return "插件: -"

    def refresh(self):
        """刷新状态显示"""
        self._status_label.configure(text=self.get_status_text())
```

**Step 2: 在 app.py 底部状态栏添加指示器**

在 `bt_gui/app.py` 中找到状态栏创建位置（或创建底部状态栏），添加：

```python
# 在 _create_ui 或 _create_main_container 中
self._create_bottom_status_bar()

def _create_bottom_status_bar(self):
    """创建底部状态栏"""
    self.bottom_status = ctk.CTkFrame(
        self.main_container,
        height=24,
        fg_color=self._dark_colors['bg_secondary'],
        corner_radius=0
    )
    self.bottom_status.pack(side='bottom', fill='x')
    self.bottom_status.pack_propagate(False)

    # 插件状态指示器
    if hasattr(self, '_plugin_loader') and self._plugin_loader:
        self._plugin_indicator = PluginStatusBarIndicator(
            self.bottom_status,
            self._plugin_loader,
            on_click=self._show_plugin_panel
        )
        self._plugin_indicator.pack(side='left', padx=Theme.DIMENSIONS['spacing_md'])

def _show_plugin_panel(self):
    """切换到设置标签页的插件管理面板"""
    self._switch_tab('settings')
```

**Step 3: 在 _init_plugin_system 中刷新指示器**

在 `bt_gui/app.py` 的 `_init_plugin_system` 末尾添加：

```python
# 创建插件状态指示器
if hasattr(self, 'bottom_status'):
    self._plugin_indicator = PluginStatusBarIndicator(
        self.bottom_status,
        self._plugin_loader,
        on_click=self._show_plugin_panel
    )
    self._plugin_indicator.pack(side='left', padx=Theme.DIMENSIONS['spacing_md'])
```

**Step 4: 在 _on_plugins_changed 中刷新指示器**

修改 `bt_gui/app.py` 的 `_on_plugins_changed`:

```python
def _on_plugins_changed(self):
    """插件启停后刷新节点面板"""
    try:
        if hasattr(self.behavior_tree, 'palette'):
            self.behavior_tree.palette.refresh_plugin_nodes()
        # 刷新状态栏指示器
        if hasattr(self, '_plugin_indicator'):
            self._plugin_indicator.refresh()
    except Exception as e:
        LogManager.debug_print(f"[WARN] 刷新节点面板插件节点失败: {e}")
```

**Step 5: 运行测试验证通过**

Run: `python -m pytest tests/test_plugin_panel_ui.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add bt_gui/plugin_panel.py bt_gui/app.py tests/test_plugin_panel_ui.py
git commit -m "feat: add plugin status bar indicator with click-to-open panel"
```

---

### Task B3: 实现插件配置编辑器

**Files:**
- Modify: `bt_gui/plugin_panel.py`
- Test: `tests/test_plugin_panel_ui.py`

**Step 1: 编写配置编辑器测试**

在 `tests/test_plugin_panel_ui.py` 添加：

```python
def test_plugin_config_editor_renders_schema():
    """测试配置编辑器根据 schema 渲染配置项"""
    try:
        import customtkinter as ctk
        try:
            root = ctk.CTk()
            root.withdraw()
        except Exception:
            pytest.skip("无法创建 GUI 窗口")

        from bt_gui.plugin_panel import PluginConfigEditor

        schema = {
            "heuristic": {
                "type": "select", "default": "manhattan",
                "label": "启发函数",
                "options": ["manhattan", "euclidean"]
            },
            "allow_diagonal": {
                "type": "bool", "default": True,
                "label": "允许对角线"
            },
            "max_iterations": {
                "type": "number", "default": 1000,
                "label": "最大迭代次数"
            }
        }

        editor = PluginConfigEditor(root, schema=schema, plugin_name="test")
        values = editor.get_values()

        assert values["heuristic"] == "manhattan"
        assert values["allow_diagonal"] is True
        assert values["max_iterations"] == 1000

        root.destroy()
    except ImportError:
        pytest.skip("customtkinter 不可用")
```

**Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_plugin_panel_ui.py::test_plugin_config_editor_renders_schema -v`

Expected: FAIL with `ImportError: cannot import name 'PluginConfigEditor'`

**Step 3: 实现 PluginConfigEditor**

在 `bt_gui/plugin_panel.py` 添加：

```python
class PluginConfigEditor(ctk.CTkFrame):
    """插件配置编辑器 — 根据 get_config_schema() 动态渲染配置项"""

    def __init__(self, master, schema: dict, plugin_name: str,
                 on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._schema = schema or {}
        self._plugin_name = plugin_name
        self._on_change = on_change
        self._widgets = {}  # key → widget
        self._vars = {}     # key → variable

        self._dark_colors = Theme.get_dark_colors()
        self._create_ui()

    def _create_ui(self):
        """根据 schema 渲染配置项"""
        if not self._schema:
            ctk.CTkLabel(
                self,
                text="（此插件无配置项）",
                font=Theme.get_font('xs'),
                text_color=self._dark_colors['text_muted']
            ).pack(pady=8)
            return

        for key, spec in self._schema.items():
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row,
                text=spec.get("label", key),
                font=Theme.get_font('sm'),
                text_color=self._dark_colors['text_primary'],
                width=120,
                anchor="w"
            ).pack(side="left", padx=(0, 8))

            widget = self._create_widget_for_type(row, key, spec)
            if widget:
                widget.pack(side="left", fill="x", expand=True)

    def _create_widget_for_type(self, parent, key, spec):
        """根据 type 创建对应的 widget"""
        spec_type = spec.get("type", "text")
        default = spec.get("default")

        if spec_type == "bool":
            var = ctk.StringVar(value="1" if default else "0")
            self._vars[key] = var
            widget = ctk.CTkSwitch(
                parent,
                variable=var,
                onvalue="1", offvalue="0",
                command=lambda: self._on_value_changed(key)
            )
        elif spec_type == "select":
            options = spec.get("options", [])
            var = ctk.StringVar(value=default if default in options else (options[0] if options else ""))
            self._vars[key] = var
            widget = ctk.CTkOptionMenu(
                parent,
                variable=var,
                values=options,
                command=lambda v: self._on_value_changed(key, v)
            )
        elif spec_type == "number":
            var = ctk.StringVar(value=str(default if default is not None else 0))
            self._vars[key] = var
            widget = ctk.CTkEntry(
                parent,
                textvariable=var,
                width=80
            )
            widget.bind("<FocusOut>", lambda e: self._on_value_changed(key))
        else:  # text
            var = ctk.StringVar(value=str(default if default is not None else ""))
            self._vars[key] = var
            widget = ctk.CTkEntry(
                parent,
                textvariable=var
            )
            widget.bind("<FocusOut>", lambda e: self._on_value_changed(key))

        self._widgets[key] = widget
        return widget

    def _on_value_changed(self, key, value=None):
        """配置项变更回调"""
        if self._on_change:
            self._on_change(self._plugin_name, key, self.get_values())

    def get_values(self) -> dict:
        """获取所有配置项的当前值"""
        result = {}
        for key, var in self._vars.items():
            raw = var.get()
            spec = self._schema.get(key, {})
            spec_type = spec.get("type", "text")
            if spec_type == "bool":
                result[key] = raw == "1" or raw is True or raw == "True"
            elif spec_type == "number":
                try:
                    result[key] = int(raw)
                except (ValueError, TypeError):
                    result[key] = 0
            else:
                result[key] = raw
        return result

    def set_values(self, values: dict):
        """设置配置项的值"""
        for key, value in values.items():
            if key in self._vars:
                spec = self._schema.get(key, {})
                spec_type = spec.get("type", "text")
                if spec_type == "bool":
                    self._vars[key].set("1" if value else "0")
                else:
                    self._vars[key].set(str(value))
```

**Step 4: 在 PluginCard 中嵌入配置编辑器**

修改 `bt_gui/plugin_panel.py` 的 `PluginCard` 类，添加配置展开/收起按钮：

```python
# 在 PluginCard._create_ui 中添加
self._config_toggle = ctk.CTkButton(
    button_row,
    text="⚙",
    width=28,
    height=24,
    fg_color="transparent",
    hover_color=self._dark_colors['border'],
    command=self._toggle_config
)
self._config_toggle.pack(side="left", padx=2)

# 添加配置编辑器容器
self._config_frame = ctk.CTkFrame(self, fg_color="transparent")
# 默认隐藏
self._config_editor = None

def _toggle_config(self):
    """切换配置编辑器显示"""
    if self._config_editor is None:
        # 创建配置编辑器
        schema = self._get_plugin_schema()
        if not schema:
            return
        self._config_editor = PluginConfigEditor(
            self._config_frame,
            schema=schema,
            plugin_name=self._info.name,
            on_change=self._on_config_changed
        )
        self._config_editor.pack(fill="x", padx=12, pady=4)
        self._config_frame.pack(fill="x")
        self._config_toggle.configure(text="▲")
    else:
        # 收起配置
        self._config_frame.pack_forget()
        self._config_editor = None
        self._config_toggle.configure(text="⚙")

def _get_plugin_schema(self):
    """获取插件的配置 schema"""
    if hasattr(self._loader, 'get_plugin_config_schema'):
        return self._loader.get_plugin_config_schema(self._info.name) or {}
    return {}

def _on_config_changed(self, plugin_name, key, values):
    """配置变更回调"""
    # 保存到 settings
    from config.settings_manager import get_settings_manager
    settings = get_settings_manager()
    for k, v in values.items():
        settings.set(f"plugins.{plugin_name}.{k}", v)
```

**Step 5: 运行测试验证通过**

Run: `python -m pytest tests/test_plugin_panel_ui.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add bt_gui/plugin_panel.py tests/test_plugin_panel_ui.py
git commit -m "feat: add plugin config editor with dynamic schema rendering"
```

---

### Task B4: 优化插件错误提示

**Files:**
- Modify: `bt_gui/plugin_panel.py`

**Step 1: 在 PluginCard 添加错误状态支持**

修改 `PluginCard` 类：

```python
# 在 __init__ 中添加
self._error_message = ""
self._error_tooltip = None

# 修改状态指示器创建
self.status_indicator = ctk.CTkFrame(
    button_row,
    width=10,
    height=10,
    fg_color=self._dark_colors['text_muted'],  # 灰色（未启动）
    corner_radius=5
)
self.status_indicator.pack(side="left", padx=(0, 8))

# 绑定悬停事件
self.status_indicator.bind("<Enter>", self._show_error_tooltip)
self.status_indicator.bind("<Leave>", self._hide_error_tooltip)

def set_error(self, message: str):
    """设置错误状态"""
    self._error_message = message
    self.status_indicator.configure(fg_color=self._dark_colors['error'])
    # 添加红色边框
    self.configure(border_width=1, border_color=self._dark_colors['error'])

def clear_error(self):
    """清除错误状态"""
    self._error_message = ""
    self.configure(border_width=0)

def _show_error_tooltip(self, event):
    """显示错误提示"""
    if not self._error_message:
        return
    if self._error_tooltip is not None:
        return
    x = self.winfo_rootx() + event.x_root - self.winfo_rootx()
    y = self.winfo_rooty() + 20
    self._error_tooltip = ctk.CTkToplevel(self)
    self._error_tooltip.wm_overrideredirect(True)
    self._error_tooltip.wm_geometry(f"+{x}+{y}")
    ctk.CTkLabel(
        self._error_tooltip,
        text=self._error_message,
        fg_color=self._dark_colors['error'],
        text_color="white",
        corner_radius=4,
        padx=8,
        pady=4,
        wraplength=300
    ).pack()

def _hide_error_tooltip(self, event):
    """隐藏错误提示"""
    if self._error_tooltip is not None:
        self._error_tooltip.destroy()
        self._error_tooltip = None
```

**Step 2: 在 _start_plugin 失败时设置错误状态**

修改 `PluginPanel._start_plugin`:

```python
def _start_plugin(self, name: str):
    """启动插件"""
    try:
        success = self._loader.start_plugin(name)
        if success:
            self._update_plugin_card(name)
            self._notify_plugins_changed()
        else:
            # 显示错误状态
            card = self._find_card(name)
            if card:
                error_msg = "插件启动失败，请查看日志"
                card.set_error(error_msg)
    except Exception as e:
        card = self._find_card(name)
        if card:
            card.set_error(str(e))
```

**Step 3: 运行现有测试验证无回归**

Run: `python -m pytest tests/test_plugin_panel_ui.py -v`

Expected: PASS

**Step 4: Commit**

```bash
git add bt_gui/plugin_panel.py
git commit -m "feat: add error status indicator with hover tooltip on plugin cards"
```

---

## 子代理 C: 独立 CLI 用户手册

### Task C1: 创建 CLI 用户手册骨架

**Files:**
- Create: `docs/cli-manual.md`

**Step 1: 创建文档骨架**

创建 `docs/cli-manual.md`，包含完整目录结构：

```markdown
# AutoDoor 行为树 CLI 用户手册

> 版本: 1.0.0 | 更新日期: 2026-07-28

## 目录

1. [简介](#1-简介)
2. [安装](#2-安装)
3. [快速开始](#3-快速开始)
4. [命令参考](#4-命令参考)
   - 4.1 [run — 运行行为树](#41-run--运行行为树)
   - 4.2 [schedule — 定时调度](#42-schedule--定时调度)
   - 4.3 [status — 查询状态](#43-status--查询状态)
   - 4.4 [stop — 停止行为树](#44-stop--停止行为树)
   - 4.5 [daemon — 守护进程](#45-daemon--守护进程)
   - 4.6 [remote — 远程控制](#46-remote--远程控制)
   - 4.7 [plugin — 插件管理](#47-plugin--插件管理)
   - 4.8 [config — 配置管理](#48-config--配置管理)
5. [Cron 表达式](#5-cron-表达式)
6. [退出码](#6-退出码)
7. [环境变量](#7-环境变量)
8. [配置文件](#8-配置文件)
9. [日志](#9-日志)
10. [使用场景](#10-使用场景)
11. [常见问题](#11-常见问题)
```

---

### Task C2: 编写命令参考部分

**Files:**
- Modify: `docs/cli-manual.md`

**Step 1: 编写 run 命令章节**

参考 `bt_cli/commands/run.py` 实际实现和方案文档 08，编写完整的 run 命令文档：
- 命令语法
- 参数表（tree_file、--headless、--project、--bus、--rest、--rest-host、--rest-port、--ws、--ws-host、--ws-port、--plugins）
- 5 个使用示例
- 注意事项

**Step 2: 编写 schedule 命令章节**

参考 `bt_cli/commands/schedule.py`，编写：
- 6 个子命令（add/list/remove/run/enable/disable）的完整说明
- add 的参数表（tree_file、--cron、--interval、--once、--name、--headless）
- 6 个使用示例

**Step 3: 编写其他 6 个命令章节**

依次编写 status、stop、daemon、remote、plugin、config 命令的完整文档，每个命令包含：
- 命令语法
- 参数表
- 使用示例
- 输出格式说明

---

### Task C3: 编写参考章节

**Files:**
- Modify: `docs/cli-manual.md`

**Step 1: 编写 Cron 表达式章节**

包含：
- 5 字段说明（分钟/小时/日期/月份/星期）
- 特殊字符（* / - ,）
- 8 个常见示例

**Step 2: 编写退出码章节**

```markdown
| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 配置错误 |
| 3 | 文件未找到 |
| 4 | 依赖缺失 |
| 5 | 认证失败 |
| 6 | 插件错误 |
| 130 | 用户中断（Ctrl+C） |
```

**Step 3: 编写环境变量章节**

```markdown
| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AUTODOOR_BT_CONFIG` | 配置文件路径 | `config/settings.json` |
| `AUTODOOR_BT_PLUGINS_DIR` | 插件目录 | `plugins/` |
| `AUTODOOR_BT_LOG_LEVEL` | 日志级别 | `INFO` |
| `AUTODOOR_BT_DATA_DIR` | 数据目录 | `~/.autodoor_bt/` |
```

**Step 4: 编写配置文件章节**

包含完整的 settings.json 示例和各字段说明。

**Step 5: 编写日志章节**

```markdown
| 日志文件 | 路径 | 说明 |
|---------|------|------|
| 启动错误日志 | `~/.autodoor_bt/startup_error.log` | 应用启动异常 |
| 运行日志 | `~/.autodoor_bt/runtime.log` | 行为树运行日志 |
| 守护进程日志 | `~/.autodoor_bt/daemon.log` | 守护进程日志 |
| 插件日志 | `~/.autodoor_bt/plugins/{name}.log` | 各插件运行日志 |
```

---

### Task C4: 编写使用场景和 FAQ

**Files:**
- Modify: `docs/cli-manual.md`

**Step 1: 编写 5 个使用场景**

1. **无 GUI 运行行为树** — `run --headless`
2. **定时执行** — `schedule add --cron`
3. **守护进程模式** — `daemon --start`
4. **远程控制** — `remote status/start/stop`
5. **使用插件** — `plugin list/load/start` + `run --plugins`

**Step 2: 编写常见问题 FAQ**

至少包含 10 个常见问题：
- Q1: 如何查看行为树运行状态？
- Q2: 定时任务不执行怎么办？
- Q3: 插件加载失败如何排查？
- Q4: REST API 端口被占用怎么办？
- Q5: 如何在后台长期运行？
- Q6: 配置文件路径在哪？
- Q7: 如何查看日志？
- Q8: 守护进程异常退出怎么恢复？
- Q9: 远程控制需要认证吗？
- Q10: 如何卸载插件？

**Step 3: Commit**

```bash
git add docs/cli-manual.md
git commit -m "docs: add comprehensive CLI user manual with commands, FAQ, and scenarios"
```

---

# 阶段 2：示例插件开发

## 子代理 D: 添加示例插件

### Task D1: 文件处理插件 — 编写测试

**Files:**
- Create: `plugins/file_processor/plugin.json`
- Create: `plugins/file_processor/main.py`
- Create: `plugins/file_processor/nodes.py`
- Test: `plugins/file_processor/tests/test_nodes.py`

**Step 1: 创建插件目录结构**

```
plugins/file_processor/
├── plugin.json
├── main.py
├── nodes.py
└── tests/
    ├── __init__.py
    └── test_nodes.py
```

**Step 2: 编写测试**

```python
# plugins/file_processor/tests/test_nodes.py
"""文件处理插件节点测试"""
import os
import json
import tempfile
import pytest

from plugins.file_processor.nodes import FileReadNode, FileWriteNode, FileMoveNode


def _make_context(blackboard=None):
    """创建测试上下文"""
    from bt_core.context import ExecutionContext
    ctx = ExecutionContext()
    if blackboard:
        for k, v in blackboard.items():
            ctx.blackboard.set(k, v)
    return ctx


def test_file_read_node_reads_text_file(tmp_path):
    """测试文件读取节点"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world", encoding="utf-8")

    node = FileReadNode()
    node.config = {
        "file_path": str(test_file),
        "encoding": "utf-8",
        "target_key": "content"
    }

    ctx = _make_context()
    status = node._execute_action(ctx)

    from bt_core.status import NodeStatus
    assert status == NodeStatus.SUCCESS
    assert ctx.blackboard.get("content") == "hello world"


def test_file_read_node_failure_on_missing_file():
    """测试文件不存在时返回 FAILURE"""
    node = FileReadNode()
    node.config = {
        "file_path": "/nonexistent/file.txt",
        "encoding": "utf-8",
        "target_key": "content"
    }

    ctx = _make_context()
    status = node._execute_action(ctx)

    from bt_core.status import NodeStatus
    assert status == NodeStatus.FAILURE


def test_file_write_node_creates_file(tmp_path):
    """测试文件写入节点"""
    target_file = tmp_path / "output.txt"

    node = FileWriteNode()
    node.config = {
        "file_path": str(target_file),
        "source_key": "text_data",
        "encoding": "utf-8",
        "append": False
    }

    ctx = _make_context(blackboard={"text_data": "written content"})
    status = node._execute_action(ctx)

    from bt_core.status import NodeStatus
    assert status == NodeStatus.SUCCESS
    assert target_file.read_text(encoding="utf-8") == "written content"


def test_file_write_node_append_mode(tmp_path):
    """测试追加写入模式"""
    target_file = tmp_path / "output.txt"
    target_file.write_text("line1\n", encoding="utf-8")

    node = FileWriteNode()
    node.config = {
        "file_path": str(target_file),
        "source_key": "text_data",
        "encoding": "utf-8",
        "append": True
    }

    ctx = _make_context(blackboard={"text_data": "line2\n"})
    status = node._execute_action(ctx)

    from bt_core.status import NodeStatus
    assert status == NodeStatus.SUCCESS
    assert target_file.read_text(encoding="utf-8") == "line1\nline2\n"


def test_file_move_node_moves_file(tmp_path):
    """测试文件移动节点"""
    src = tmp_path / "source.txt"
    src.write_text("content", encoding="utf-8")
    dst = tmp_path / "destination.txt"

    node = FileMoveNode()
    node.config = {
        "source_path": str(src),
        "target_path": str(dst)
    }

    ctx = _make_context()
    status = node._execute_action(ctx)

    from bt_core.status import NodeStatus
    assert status == NodeStatus.SUCCESS
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "content"


def test_plugin_lifecycle():
    """测试插件完整生命周期"""
    from plugins.file_processor.main import FileProcessorPlugin
    from bt_plugins.base import PluginInfo, PluginContext

    info = PluginInfo(
        name="file_processor",
        display_name="文件处理",
        version="1.0.0",
        author="AutoDoor Team",
        description="文件读写和移动操作"
    )
    plugin = FileProcessorPlugin(info)
    plugin.on_load()
    assert plugin._loaded

    nodes = plugin.get_nodes()
    assert "FileReadNode" in nodes
    assert "FileWriteNode" in nodes
    assert "FileMoveNode" in nodes

    display_info = plugin.get_node_display_info()
    assert "FileReadNode" in display_info
    assert display_info["FileReadNode"]["display_name"] == "文件读取"

    plugin.on_unload()
```

**Step 3: 运行测试验证失败**

Run: `python -m pytest plugins/file_processor/tests/test_nodes.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'plugins.file_processor'`

---

### Task D2: 文件处理插件 — 实现

**Files:**
- Create: `plugins/file_processor/plugin.json`
- Create: `plugins/file_processor/main.py`
- Create: `plugins/file_processor/nodes.py`

**Step 1: 创建 plugin.json**

```json
{
    "name": "file_processor",
    "display_name": "文件处理",
    "version": "1.0.0",
    "author": "AutoDoor Team",
    "description": "文件读写和移动操作，提供 FileReadNode、FileWriteNode、FileMoveNode",
    "category": "office",
    "entry": "main.py",
    "class": "FileProcessorPlugin"
}
```

**Step 2: 创建 nodes.py**

```python
# plugins/file_processor/nodes.py
"""文件处理节点"""
import os
import shutil

from bt_core.nodes import ActionNode
from bt_core.status import NodeStatus


class FileReadNode(ActionNode):
    """文件读取节点 — 读取文件内容到黑板"""

    NODE_TYPE = "FileReadNode"

    def _execute_action(self, context):
        file_path = self.config.get("file_path", "")
        encoding = self.config.get("encoding", "utf-8")
        target_key = self.config.get("target_key", "file_content")

        if not file_path or not os.path.exists(file_path):
            return NodeStatus.FAILURE

        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            context.blackboard.set(target_key, content)
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE


class FileWriteNode(ActionNode):
    """文件写入节点 — 将黑板数据写入文件"""

    NODE_TYPE = "FileWriteNode"

    def _execute_action(self, context):
        file_path = self.config.get("file_path", "")
        source_key = self.config.get("source_key", "file_content")
        encoding = self.config.get("encoding", "utf-8")
        append = self.config.get("append", False)

        if not file_path:
            return NodeStatus.FAILURE

        content = context.blackboard.get(source_key)
        if content is None:
            return NodeStatus.FAILURE

        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            mode = "a" if append else "w"
            with open(file_path, mode, encoding=encoding) as f:
                f.write(str(content))
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE


class FileMoveNode(ActionNode):
    """文件移动节点 — 移动或重命名文件"""

    NODE_TYPE = "FileMoveNode"

    def _execute_action(self, context):
        source_path = self.config.get("source_path", "")
        target_path = self.config.get("target_path", "")

        if not source_path or not target_path:
            return NodeStatus.FAILURE
        if not os.path.exists(source_path):
            return NodeStatus.FAILURE

        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.move(source_path, target_path)
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE
```

**Step 3: 创建 main.py**

```python
# plugins/file_processor/main.py
"""文件处理插件入口"""
from bt_plugins.base import BasePlugin
from .nodes import FileReadNode, FileWriteNode, FileMoveNode


class FileProcessorPlugin(BasePlugin):
    """文件处理插件"""

    def on_load(self):
        self._loaded = True
        self.log("info", "文件处理插件已加载")

    def on_unload(self):
        self._loaded = False
        self.log("info", "文件处理插件已卸载")

    def on_start(self):
        self._started = True
        self.log("info", "文件处理插件已启动")

    def on_stop(self):
        self._started = False
        self.log("info", "文件处理插件已停止")

    def get_nodes(self):
        return {
            "FileReadNode": FileReadNode,
            "FileWriteNode": FileWriteNode,
            "FileMoveNode": FileMoveNode,
        }

    def get_node_schemas(self):
        return {
            "FileReadNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "encoding", "label": "编码", "type": "text", "default": "utf-8"},
                {"key": "target_key", "label": "目标键名", "type": "text", "default": "file_content"},
            ],
            "FileWriteNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "source_key", "label": "源键名", "type": "text", "default": "file_content"},
                {"key": "encoding", "label": "编码", "type": "text", "default": "utf-8"},
                {"key": "append", "label": "追加模式", "type": "bool", "default": False},
            ],
            "FileMoveNode": [
                {"key": "source_path", "label": "源路径", "type": "text", "default": ""},
                {"key": "target_path", "label": "目标路径", "type": "text", "default": ""},
            ],
        }

    def get_node_display_info(self):
        return {
            "FileReadNode": {
                "display_name": "文件读取",
                "description": "读取文件内容到黑板",
                "category": "plugin",
                "icon": "📄",
            },
            "FileWriteNode": {
                "display_name": "文件写入",
                "description": "将黑板数据写入文件",
                "category": "plugin",
                "icon": "📝",
            },
            "FileMoveNode": {
                "display_name": "文件移动",
                "description": "移动或重命名文件",
                "category": "plugin",
                "icon": "📁",
            },
        }
```

**Step 4: 创建 __init__.py 和 tests/__init__.py**

```python
# plugins/file_processor/__init__.py
"""文件处理插件"""
```

```python
# plugins/file_processor/tests/__init__.py
```

**Step 5: 运行测试验证通过**

Run: `python -m pytest plugins/file_processor/tests/test_nodes.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add plugins/file_processor/
git commit -m "feat: add file_processor plugin with FileRead/Write/Move nodes"
```

---

### Task D3: Excel 自动化插件 — 检查依赖并编写测试

**Files:**
- Create: `plugins/excel_automation/plugin.json`
- Create: `plugins/excel_automation/main.py`
- Create: `plugins/excel_automation/nodes.py`
- Create: `plugins/excel_automation/adapter.py`
- Test: `plugins/excel_automation/tests/test_nodes.py`

**Step 1: 检查 openpyxl 依赖**

Run: `python -c "import openpyxl; print(openpyxl.__version__)"`

如果失败，则：
- 在 `plugins/excel_automation/requirements.txt` 中添加 `openpyxl>=3.0.0`
- 跳过依赖 openpyxl 的测试（使用 `pytest.importorskip("openpyxl")`）

**Step 2: 编写测试**

```python
# plugins/excel_automation/tests/test_nodes.py
"""Excel 自动化插件测试"""
import os
import pytest

openpyxl = pytest.importorskip("openpyxl")


def _make_context(blackboard=None):
    from bt_core.context import ExecutionContext
    ctx = ExecutionContext()
    if blackboard:
        for k, v in blackboard.items():
            ctx.blackboard.set(k, v)
    return ctx


def test_excel_write_node_creates_file(tmp_path):
    """测试 Excel 写入节点"""
    from plugins.excel_automation.nodes import ExcelWriteNode
    from bt_core.status import NodeStatus

    target_file = tmp_path / "output.xlsx"
    node = ExcelWriteNode()
    node.config = {
        "file_path": str(target_file),
        "sheet_name": "Sheet1",
        "data_key": "table_data",
        "start_cell": "A1",
    }

    # 模拟表格数据 [[行1列1, 行1列2], [行2列1, 行2列2]]
    ctx = _make_context(blackboard={"table_data": [["Name", "Age"], ["Alice", 30], ["Bob", 25]]})
    status = node._execute_action(ctx)

    assert status == NodeStatus.SUCCESS
    assert target_file.exists()

    # 验证内容
    wb = openpyxl.load_workbook(str(target_file))
    ws = wb["Sheet1"]
    assert ws["A1"].value == "Name"
    assert ws["B1"].value == "Age"
    assert ws["A2"].value == "Alice"
    assert ws["B2"].value == 30


def test_excel_read_node_reads_file(tmp_path):
    """测试 Excel 读取节点"""
    from plugins.excel_automation.nodes import ExcelReadNode
    from bt_core.status import NodeStatus

    # 先创建测试文件
    test_file = tmp_path / "input.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "Name"
    ws["B1"] = "Age"
    ws["A2"] = "Alice"
    ws["B2"] = 30
    wb.save(str(test_file))

    node = ExcelReadNode()
    node.config = {
        "file_path": str(test_file),
        "sheet_name": "Sheet1",
        "cell_range": "A1:B2",
        "target_key": "read_data",
    }

    ctx = _make_context()
    status = node._execute_action(ctx)

    assert status == NodeStatus.SUCCESS
    data = ctx.blackboard.get("read_data")
    assert data[0] == ["Name", "Age"]
    assert data[1] == ["Alice", 30]


def test_excel_format_node_applies_style(tmp_path):
    """测试 Excel 格式化节点"""
    from plugins.excel_automation.nodes import ExcelFormatNode
    from bt_core.status import NodeStatus

    test_file = tmp_path / "format.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Test"
    wb.save(str(test_file))

    node = ExcelFormatNode()
    node.config = {
        "file_path": str(test_file),
        "sheet_name": "Sheet",
        "cell_range": "A1:A1",
        "bold": True,
        "bg_color": "FF0000",
    }

    ctx = _make_context()
    status = node._execute_action(ctx)

    assert status == NodeStatus.SUCCESS

    wb2 = openpyxl.load_workbook(str(test_file))
    ws2 = wb2.active
    cell = ws2["A1"]
    assert cell.font.bold is True


def test_plugin_lifecycle():
    """测试插件完整生命周期"""
    from plugins.excel_automation.main import ExcelAutomationPlugin
    from bt_plugins.base import PluginInfo

    info = PluginInfo(
        name="excel_automation",
        display_name="Excel自动化",
        version="1.0.0",
        author="AutoDoor Team",
        description="Excel 读写和格式化"
    )
    plugin = ExcelAutomationPlugin(info)
    plugin.on_load()
    assert plugin._loaded

    nodes = plugin.get_nodes()
    assert "ExcelReadNode" in nodes
    assert "ExcelWriteNode" in nodes
    assert "ExcelFormatNode" in nodes

    schemas = plugin.get_node_schemas()
    assert "ExcelReadNode" in schemas

    plugin.on_unload()
```

**Step 3: 运行测试验证失败**

Run: `python -m pytest plugins/excel_automation/tests/test_nodes.py -v`

Expected: FAIL with `ModuleNotFoundError`

---

### Task D4: Excel 自动化插件 — 实现

**Files:**
- Create: `plugins/excel_automation/plugin.json`
- Create: `plugins/excel_automation/main.py`
- Create: `plugins/excel_automation/nodes.py`
- Create: `plugins/excel_automation/adapter.py`

**Step 1: 创建 plugin.json**

```json
{
    "name": "excel_automation",
    "display_name": "Excel自动化",
    "version": "1.0.0",
    "author": "AutoDoor Team",
    "description": "Excel 读写和格式化操作，依赖 openpyxl",
    "category": "office",
    "entry": "main.py",
    "class": "ExcelAutomationPlugin"
}
```

**Step 2: 创建 nodes.py**

```python
# plugins/excel_automation/nodes.py
"""Excel 自动化节点"""
import os

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from bt_core.nodes import ActionNode
from bt_core.status import NodeStatus


class ExcelWriteNode(ActionNode):
    """Excel 写入节点 — 将黑板中的二维数据写入 Excel 文件"""

    NODE_TYPE = "ExcelWriteNode"

    def _execute_action(self, context):
        if not OPENPYXL_AVAILABLE:
            return NodeStatus.FAILURE

        file_path = self.config.get("file_path", "")
        sheet_name = self.config.get("sheet_name", "Sheet1")
        data_key = self.config.get("data_key", "table_data")
        start_cell = self.config.get("start_cell", "A1")

        if not file_path:
            return NodeStatus.FAILURE

        data = context.blackboard.get(data_key)
        if not data or not isinstance(data, (list, tuple)):
            return NodeStatus.FAILURE

        try:
            if os.path.exists(file_path):
                wb = openpyxl.load_workbook(file_path)
                if sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                else:
                    ws = wb.create_sheet(sheet_name)
            else:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = sheet_name

            # 解析起始单元格
            from openpyxl.utils import range_boundaries
            col, row, _, _ = range_boundaries(start_cell + ":" + start_cell)

            for r_idx, row_data in enumerate(data):
                for c_idx, value in enumerate(row_data):
                    ws.cell(row=row + r_idx, column=col + c_idx, value=value)

            wb.save(file_path)
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE


class ExcelReadNode(ActionNode):
    """Excel 读取节点 — 读取 Excel 范围到黑板"""

    NODE_TYPE = "ExcelReadNode"

    def _execute_action(self, context):
        if not OPENPYXL_AVAILABLE:
            return NodeStatus.FAILURE

        file_path = self.config.get("file_path", "")
        sheet_name = self.config.get("sheet_name", "")
        cell_range = self.config.get("cell_range", "A1:Z100")
        target_key = self.config.get("target_key", "excel_data")

        if not file_path or not os.path.exists(file_path):
            return NodeStatus.FAILURE

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            if sheet_name and sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
            else:
                ws = wb.active

            # 读取范围
            from openpyxl.utils import range_boundaries
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)

            data = []
            for r in range(min_row, max_row + 1):
                row = []
                for c in range(min_col, max_col + 1):
                    row.append(ws.cell(row=r, column=c).value)
                data.append(row)

            context.blackboard.set(target_key, data)
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE


class ExcelFormatNode(ActionNode):
    """Excel 格式化节点 — 应用单元格格式"""

    NODE_TYPE = "ExcelFormatNode"

    def _execute_action(self, context):
        if not OPENPYXL_AVAILABLE:
            return NodeStatus.FAILURE

        file_path = self.config.get("file_path", "")
        sheet_name = self.config.get("sheet_name", "")
        cell_range = self.config.get("cell_range", "A1:A1")
        bold = self.config.get("bold", False)
        bg_color = self.config.get("bg_color", "")

        if not file_path or not os.path.exists(file_path):
            return NodeStatus.FAILURE

        try:
            wb = openpyxl.load_workbook(file_path)
            if sheet_name and sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
            else:
                ws = wb.active

            font = Font(bold=bold)
            fill = PatternFill(start_color=bg_color, end_color=bg_color,
                               fill_type="solid") if bg_color else None

            for row in ws[cell_range]:
                for cell in row:
                    cell.font = font
                    if fill:
                        cell.fill = fill

            wb.save(file_path)
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE
```

**Step 3: 创建 adapter.py**

```python
# plugins/excel_automation/adapter.py
"""Excel 适配器 — 封装 openpyxl 工作簿操作"""
import os

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class ExcelAdapter:
    """Excel 适配器 — 简单的工作簿操作封装"""

    def __init__(self):
        self._workbooks = {}

    @classmethod
    def is_available(cls) -> bool:
        return OPENPYXL_AVAILABLE

    def open(self, file_path: str, read_only: bool = False):
        """打开工作簿"""
        if not OPENPYXL_AVAILABLE:
            return None
        try:
            wb = openpyxl.load_workbook(file_path, data_only=not read_only)
            self._workbooks[file_path] = wb
            return wb
        except Exception:
            return None

    def create(self, file_path: str):
        """创建新工作簿"""
        if not OPENPYXL_AVAILABLE:
            return None
        wb = openpyxl.Workbook()
        self._workbooks[file_path] = wb
        return wb

    def save(self, file_path: str) -> bool:
        """保存工作簿"""
        wb = self._workbooks.get(file_path)
        if not wb:
            return False
        try:
            wb.save(file_path)
            return True
        except Exception:
            return False

    def close(self, file_path: str) -> None:
        """关闭工作簿"""
        wb = self._workbooks.pop(file_path, None)
        if wb:
            wb.close()

    def close_all(self) -> None:
        """关闭所有工作簿"""
        for wb in list(self._workbooks.values()):
            wb.close()
        self._workbooks.clear()
```

**Step 4: 创建 main.py**

```python
# plugins/excel_automation/main.py
"""Excel 自动化插件入口"""
from bt_plugins.base import BasePlugin
from .nodes import ExcelWriteNode, ExcelReadNode, ExcelFormatNode
from .adapter import ExcelAdapter


class ExcelAutomationPlugin(BasePlugin):
    """Excel 自动化插件"""

    def on_load(self):
        self._loaded = True
        self.log("info", "Excel 自动化插件已加载")

    def on_unload(self):
        self._loaded = False
        self.log("info", "Excel 自动化插件已卸载")

    def on_start(self):
        self._started = True
        self.log("info", "Excel 自动化插件已启动")

    def on_stop(self):
        self._started = False
        self.log("info", "Excel 自动化插件已停止")

    def get_nodes(self):
        return {
            "ExcelReadNode": ExcelReadNode,
            "ExcelWriteNode": ExcelWriteNode,
            "ExcelFormatNode": ExcelFormatNode,
        }

    def get_adapters(self):
        return {
            "excel": ExcelAdapter,
        }

    def get_node_schemas(self):
        return {
            "ExcelReadNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "sheet_name", "label": "Sheet 名", "type": "text", "default": ""},
                {"key": "cell_range", "label": "单元格范围", "type": "text", "default": "A1:Z100"},
                {"key": "target_key", "label": "目标键名", "type": "text", "default": "excel_data"},
            ],
            "ExcelWriteNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "sheet_name", "label": "Sheet 名", "type": "text", "default": "Sheet1"},
                {"key": "data_key", "label": "数据键名", "type": "text", "default": "table_data"},
                {"key": "start_cell", "label": "起始单元格", "type": "text", "default": "A1"},
            ],
            "ExcelFormatNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "sheet_name", "label": "Sheet 名", "type": "text", "default": ""},
                {"key": "cell_range", "label": "单元格范围", "type": "text", "default": "A1:A1"},
                {"key": "bold", "label": "加粗", "type": "bool", "default": False},
                {"key": "bg_color", "label": "背景色（十六进制）", "type": "text", "default": ""},
            ],
        }

    def get_node_display_info(self):
        return {
            "ExcelReadNode": {
                "display_name": "Excel读取",
                "description": "读取 Excel 单元格范围到黑板",
                "category": "plugin",
                "icon": "📊",
            },
            "ExcelWriteNode": {
                "display_name": "Excel写入",
                "description": "将黑板数据写入 Excel 文件",
                "category": "plugin",
                "icon": "📈",
            },
            "ExcelFormatNode": {
                "display_name": "Excel格式化",
                "description": "应用单元格格式（字体、颜色）",
                "category": "plugin",
                "icon": "🎨",
            },
        }

    def get_config_schema(self):
        return {
            "default_sheet": {
                "type": "text",
                "default": "Sheet1",
                "label": "默认 Sheet 名"
            }
        }
```

**Step 5: 创建 __init__.py 和 tests/__init__.py**

```python
# plugins/excel_automation/__init__.py
"""Excel 自动化插件"""
```

```python
# plugins/excel_automation/tests/__init__.py
```

**Step 6: 运行测试验证通过**

Run: `python -m pytest plugins/excel_automation/tests/test_nodes.py -v`

Expected: PASS（如果 openpyxl 可用）

**Step 7: Commit**

```bash
git add plugins/excel_automation/
git commit -m "feat: add excel_automation plugin with Read/Write/Format nodes"
```

---

### Task D5: 集成验证

**Files:**
- Modify: `tests/test_plugin_integration.py`

**Step 1: 编写集成测试**

```python
# tests/test_plugin_integration.py
"""插件系统集成测试 — 验证示例插件可被加载并运行"""
import os
import pytest

from bt_plugins.base import PluginContext, PluginInfo
from bt_plugins.loader import PluginLoader


def test_file_processor_plugin_loads():
    """测试文件处理插件可加载"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugin_dir = os.path.join(project_root, "plugins", "file_processor")

    if not os.path.isdir(plugin_dir):
        pytest.skip("file_processor 插件目录不存在")

    loader = PluginLoader(PluginContext())
    assert loader.load_plugin(plugin_dir), "插件加载失败"

    info = loader.get_plugin_info("file_processor")
    assert info is not None
    assert info.display_name == "文件处理"


def test_file_processor_plugin_starts():
    """测试文件处理插件可启动"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugin_dir = os.path.join(project_root, "plugins", "file_processor")

    if not os.path.isdir(plugin_dir):
        pytest.skip("file_processor 插件目录不存在")

    loader = PluginLoader(PluginContext())
    loader.load_plugin(plugin_dir)
    assert loader.start_plugin("file_processor")

    # 验证节点显示信息
    display_info = loader.get_registered_display_info()
    assert "file_processor.FileReadNode" in display_info
    assert display_info["file_processor.FileReadNode"]["display_name"] == "文件读取"

    # 验证 schema
    schemas = loader.get_registered_schemas()
    assert "file_processor.FileReadNode" in schemas

    loader.stop_plugin("file_processor")


def test_excel_automation_plugin_loads():
    """测试 Excel 插件可加载（依赖 openpyxl）"""
    pytest.importorskip("openpyxl")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugin_dir = os.path.join(project_root, "plugins", "excel_automation")

    if not os.path.isdir(plugin_dir):
        pytest.skip("excel_automation 插件目录不存在")

    loader = PluginLoader(PluginContext())
    assert loader.load_plugin(plugin_dir), "插件加载失败"


def test_all_plugins_discovered_via_scan():
    """测试通过 scan 发现所有插件"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugins_dir = os.path.join(project_root, "plugins")

    if not os.path.isdir(plugins_dir):
        pytest.skip("plugins 目录不存在")

    loader = PluginLoader(PluginContext())
    infos = loader.scan(plugins_dir)

    names = [info.name for info in infos]
    assert "file_processor" in names

    if pytest.importorskip("openpyxl", reason="openpyxl 不可用"):
        assert "excel_automation" in names
```

**Step 2: 运行集成测试**

Run: `python -m pytest tests/test_plugin_integration.py -v`

Expected: PASS

**Step 3: 运行全套测试验证无回归**

Run: `python -m pytest tests/ plugins/ -v`

Expected: 所有测试通过

**Step 4: Commit**

```bash
git add tests/test_plugin_integration.py
git commit -m "test: add plugin integration tests for example plugins"
```

---

## 执行顺序总结

```
阶段 1（并行）:
  子代理 A: Task A1 → A2 → A3 → A4 → A5
  子代理 B: Task B1 → B2 → B3 → B4
  子代理 C: Task C1 → C2 → C3 → C4

阶段 2（依赖阶段 1）:
  子代理 D: Task D1 → D2 → D3 → D4 → D5

最终验证:
  重新运行全套测试 (子代理 A)
```

## 验收标准

1. ✅ `docs/cli-manual.md` 存在且内容完整
2. ✅ 全套测试通过（`pytest tests/ plugins/ -v` 无失败）
3. ✅ 代码审查报告已生成，发现的问题已修复
4. ✅ 插件管理面板具备：状态栏指示器、配置编辑器、错误提示
5. ✅ `plugins/file_processor/` 可加载并运行
6. ✅ `plugins/excel_automation/` 可加载并运行（依赖 openpyxl）
7. ✅ 示例插件在 GUI 中正确显示节点和属性面板

# AutoDoor 行为树插件接入与开发指南

> 版本: 1.0.0 | 更新日期: 2026-07-28
> 适用版本: AutoDoor Behavior Tree v2.0+

本指南面向两类读者：
- **使用者**：希望加载和使用现成插件的用户（第 1-2 章）
- **开发者**：希望开发自己插件的用户（第 3-8 章）

---

## 目录

1. [插件系统简介](#1-插件系统简介)
2. [使用现成插件](#2-使用现成插件)
3. [快速开始：开发你的第一个插件](#3-快速开始开发你的第一个插件)
4. [插件目录结构](#4-插件目录结构)
5. [插件清单 plugin.json](#5-插件清单-pluginjson)
6. [插件生命周期与入口类](#6-插件生命周期与入口类)
7. [节点开发](#7-节点开发)
8. [适配器开发](#8-适配器开发)
9. [服务开发](#9-服务开发)
10. [插件配置 Schema](#10-插件配置-schema)
11. [插件 API 参考](#11-插件-api-参考)
12. [测试与调试](#12-测试与调试)
13. [部署与发布](#13-部署与发布)
14. [常见问题](#14-常见问题)

---

## 1. 插件系统简介

### 1.1 什么是插件

插件是 AutoDoor 行为树的扩展模块，可以在不修改主程序代码的情况下：

- **新增节点类型**：如 Excel 读取、文件操作、数据库查询等
- **新增适配器**：如串口通信、数据库连接、邮件发送等
- **新增服务**：如通知服务、数据转换服务等
- **接入消息总线**：订阅行为树事件，发布自定义消息

### 1.2 插件系统能力

| 能力 | 说明 |
|------|------|
| 动态加载 | 运行时加载/卸载插件，无需重启应用 |
| 节点扩展 | 插件节点自动出现在 GUI 节点面板的「插件节点」分类 |
| 属性配置 | 通过 schema 动态渲染属性面板，支持 text/number/select/bool |
| 异常隔离 | 插件异常不影响主进程，自动记录日志 |
| 命名隔离 | 插件节点类型自动加前缀 `{plugin_name}.{node_type}` |
| 配置隔离 | 插件配置存储在 `plugins.{plugin_name}.` 命名空间 |
| 消息总线接入 | 插件可发布/订阅消息总线主题 |
| Headless 模式 | 无 GUI 环境下也可自动加载插件 |

### 1.3 内置插件与用户插件

| 类型 | 目录 | 说明 |
|------|------|------|
| 内置插件 | `bt_plugins/builtin/` | 随应用分发，不可卸载 |
| 用户插件 | `plugins/` | 用户自行开发或下载，可加载/卸载 |

---

## 2. 使用现成插件

### 2.1 通过 GUI 使用插件

#### 步骤 1：打开插件管理面板

启动应用 → 点击顶部「⚙ 设置」标签页 → 找到「插件管理」面板。

#### 步骤 2：加载插件

- **加载内置插件**：插件列表会自动显示内置插件，点击「启动」按钮
- **加载用户插件**：点击「+ 加载插件」按钮，选择 `plugins/` 下的插件目录（包含 `plugin.json` 的目录）

#### 步骤 3：启动插件

点击插件卡片右侧的「启动」按钮。启动后：

- 状态指示器变为绿色 ●
- 插件提供的节点自动出现在节点面板的「插件节点」分类
- 底部状态栏显示 `插件: X/Y 已启动`

#### 步骤 4：使用插件节点

在行为树编辑器中，从节点面板的「插件节点」分类拖拽节点到画布。选中节点后，属性面板会根据插件提供的 schema 自动渲染配置项。

#### 步骤 5：配置插件

点击插件卡片上的「⚙」按钮，展开插件配置区域。修改配置后会自动保存到 `settings.json`。

#### 步骤 6：停止/卸载插件

- 点击「停止」按钮停止插件（节点从面板移除）
- 如需完全卸载插件，使用 CLI 命令：`autodoor-bt plugin unload <plugin_name>`

### 2.2 通过 CLI 使用插件

#### 查看已安装的插件

```bash
python cli.py plugin list
```

输出示例：

```
插件列表 (2 个):
------------------------------------------------------------
  文件处理 (file_processor) v1.0.0
    作者: AutoDoor Team
    描述: 文件读写和移动操作
    分类: office
    状态: 已启动
------------------------------------------------------------
  Excel自动化 (excel_automation) v1.0.0
    作者: AutoDoor Team
    描述: Excel 读写和格式化操作
    分类: office
    状态: 已停止
------------------------------------------------------------
```

#### 加载插件

```bash
python cli.py plugin load plugins/file_processor/
```

#### 启动插件

```bash
python cli.py plugin start file_processor
```

#### 停止插件

```bash
python cli.py plugin stop file_processor
```

#### 查看插件详情

```bash
python cli.py plugin info file_processor
```

#### 在 Headless 模式启用插件

```bash
python cli.py run my_tree.json --headless --bus --plugins
```

### 2.3 状态指示说明

| 图标 | 颜色 | 状态 | 说明 |
|------|------|------|------|
| ● | 绿色 | 已启动 | 插件正在运行，节点已注册 |
| ○ | 灰色 | 已加载未启动 | 插件已加载但未启动 |
| ✕ | 红色 | 加载失败 | 悬停查看错误详情 |

---

## 3. 快速开始：开发你的第一个插件

以「文件处理」插件为例，10 分钟开发一个可用的插件。

### 步骤 1：创建插件目录

```
plugins/
└── my_first_plugin/
    ├── plugin.json
    ├── main.py
    └── nodes.py
```

### 步骤 2：编写 plugin.json

```json
{
    "name": "my_first_plugin",
    "display_name": "我的第一个插件",
    "version": "1.0.0",
    "author": "你的名字",
    "description": "一个示例插件，提供文件读取节点",
    "category": "office",
    "entry": "main.py",
    "class": "MyFirstPlugin"
}
```

### 步骤 3：编写节点实现 nodes.py

```python
import os
from bt_core.nodes import ActionNode
from bt_core.status import NodeStatus


class FileReadNode(ActionNode):
    """文件读取节点"""

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
```

### 步骤 4：编写插件入口 main.py

```python
from bt_plugins.base import BasePlugin
from plugins.my_first_plugin.nodes import FileReadNode


class MyFirstPlugin(BasePlugin):
    """我的第一个插件"""

    def on_load(self):
        self._loaded = True
        self.log("info", "插件已加载")

    def on_unload(self):
        self._loaded = False
        self.log("info", "插件已卸载")

    def on_start(self):
        self._started = True
        self.log("info", "插件已启动")

    def on_stop(self):
        self._started = False
        self.log("info", "插件已停止")

    def get_nodes(self):
        return {
            "FileReadNode": FileReadNode,
        }

    def get_node_schemas(self):
        return {
            "FileReadNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "encoding", "label": "编码", "type": "text", "default": "utf-8"},
                {"key": "target_key", "label": "目标键名", "type": "text", "default": "file_content"},
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
        }
```

### 步骤 5：加载并测试

```bash
# 通过 CLI 加载
python cli.py plugin load plugins/my_first_plugin/
python cli.py plugin start my_first_plugin

# 验证
python cli.py plugin list
python cli.py plugin info my_first_plugin
```

或通过 GUI 的「设置 → 插件管理 → 加载插件」加载。

### 步骤 6：在行为树中使用

启动应用，在节点面板的「插件节点」分类中找到「文件读取」节点，拖拽到画布即可使用。

---

## 4. 插件目录结构

### 4.1 标准目录结构

```
plugins/my_plugin/
├── plugin.json              # 插件清单（必需）
├── main.py                  # 插件入口（必需）
├── nodes.py                 # 节点实现（可选，可拆分多个文件）
├── adapters.py              # 适配器实现（可选）
├── services.py              # 服务实现（可选）
├── requirements.txt         # 第三方依赖（可选）
├── README.md               # 插件说明（可选）
├── __init__.py             # 包初始化（必需）
└── tests/
    ├── __init__.py
    └── test_nodes.py        # 节点单元测试
```

### 4.2 实际示例

以 `file_processor` 插件为例：

```
plugins/file_processor/
├── plugin.json
├── main.py                  # FileProcessorPlugin 入口类
├── nodes.py                 # FileReadNode, FileWriteNode, FileMoveNode
├── __init__.py
└── tests/
    ├── __init__.py
    └── test_nodes.py        # 6 个测试用例
```

以 `excel_automation` 插件为例（更完整）：

```
plugins/excel_automation/
├── plugin.json
├── main.py                  # ExcelAutomationPlugin 入口类
├── nodes.py                 # ExcelReadNode, ExcelWriteNode, ExcelFormatNode
├── adapter.py              # ExcelAdapter 适配器
├── requirements.txt        # openpyxl>=3.0.0
├── __init__.py
└── tests/
    ├── __init__.py
    └── test_nodes.py
```

### 4.3 重要说明

> **导入方式**：由于 PluginLoader 使用 `importlib.util.spec_from_file_location` 按文件路径加载模块，**必须使用绝对导入**，不能使用相对导入。

```python
# 正确 ✅
from plugins.my_plugin.nodes import MyNode
from bt_plugins.base import BasePlugin
from bt_core.nodes import ActionNode

# 错误 ❌ — 会报 attempted relative import with no known parent package
from .nodes import MyNode
from ..base import BasePlugin
```

---

## 5. 插件清单 plugin.json

### 5.1 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 插件唯一标识（英文，snake_case） |
| `display_name` | string | 是 | 显示名称（中文） |
| `version` | string | 是 | 语义化版本号（如 `1.0.0`） |
| `author` | string | 是 | 作者 |
| `description` | string | 是 | 功能描述 |
| `category` | string | 否 | 分类：`general`/`game`/`office`/`data`/`hardware` |
| `min_app_version` | string | 否 | 最低兼容的应用版本 |
| `dependencies` | string[] | 否 | 依赖的其他插件名 |
| `entry` | string | 是 | 入口 Python 文件名（如 `main.py`） |
| `class` | string | 是 | 插件类名（entry 文件中定义的类） |

### 5.2 完整示例

```json
{
    "name": "excel_automation",
    "display_name": "Excel自动化",
    "version": "1.0.0",
    "author": "AutoDoor Team",
    "description": "Excel 读写和格式化操作，依赖 openpyxl",
    "category": "office",
    "min_app_version": "2.0.0",
    "dependencies": ["file_processor"],
    "entry": "main.py",
    "class": "ExcelAutomationPlugin"
}
```

### 5.3 分类说明

| 分类 | 说明 | 典型场景 |
|------|------|---------|
| `general` | 通用 | 工具类、杂项 |
| `game` | 游戏自动化 | 寻路、图像识别、按键模拟 |
| `office` | 办公自动化 | Excel、Word、PDF 处理 |
| `data` | 数据处理 | 数据库、数据转换、ETL |
| `hardware` | 硬件交互 | 串口、GPIO、传感器 |

---

## 6. 插件生命周期与入口类

### 6.1 生命周期

```
on_load() → on_start() → [运行中] → on_stop() → on_unload()
```

| 方法 | 调用时机 | 用途 |
|------|---------|------|
| `on_load()` | 插件被加载时 | 初始化资源、读取配置 |
| `on_start()` | 插件被启动时 | 注册节点/适配器/服务 |
| `on_stop()` | 插件被停止时 | 注销已注册的内容、释放资源 |
| `on_unload()` | 插件被卸载时 | 清理所有资源 |

### 6.2 BasePlugin 扩展点

插件通过重写以下方法提供扩展能力：

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_nodes()` | `{node_type: NodeClass}` | 提供节点类型 |
| `get_adapters()` | `{adapter_name: AdapterClass}` | 提供适配器 |
| `get_services()` | `{service_name: instance}` | 提供服务实例 |
| `get_node_schemas()` | `{node_type: [field_schema]}` | 节点属性面板 schema |
| `get_node_display_info()` | `{node_type: {display_name, description, ...}}` | 节点显示信息 |
| `get_config_schema()` | `{key: {type, default, label}}` | 插件自身配置 schema |

### 6.3 完整入口类示例

```python
from bt_plugins.base import BasePlugin
from plugins.my_plugin.nodes import MyReadNode, MyWriteNode
from plugins.my_plugin.adapter import MyAdapter


class MyPlugin(BasePlugin):
    """我的插件"""

    def on_load(self):
        self._loaded = True
        self.log("info", "插件已加载")
        # 初始化资源

    def on_unload(self):
        self._loaded = False
        self.log("info", "插件已卸载")
        # 清理资源

    def on_start(self):
        self._started = True
        self.log("info", "插件已启动")

    def on_stop(self):
        self._started = False
        self.log("info", "插件已停止")

    def get_nodes(self):
        return {
            "MyReadNode": MyReadNode,
            "MyWriteNode": MyWriteNode,
        }

    def get_adapters(self):
        return {
            "my_adapter": MyAdapter,
        }

    def get_node_schemas(self):
        return {
            "MyReadNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "encoding", "label": "编码", "type": "text", "default": "utf-8"},
            ],
            "MyWriteNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "data_key", "label": "数据键名", "type": "text", "default": "data"},
            ],
        }

    def get_node_display_info(self):
        return {
            "MyReadNode": {
                "display_name": "读取数据",
                "description": "从文件读取数据到黑板",
                "category": "plugin",
                "icon": "📖",
            },
            "MyWriteNode": {
                "display_name": "写入数据",
                "description": "将黑板数据写入文件",
                "category": "plugin",
                "icon": "✏️",
            },
        }

    def get_config_schema(self):
        return {
            "default_encoding": {
                "type": "text",
                "default": "utf-8",
                "label": "默认编码"
            },
            "max_file_size": {
                "type": "number",
                "default": 10485760,
                "label": "最大文件大小（字节）"
            }
        }
```

---

## 7. 节点开发

### 7.1 ActionNode — 动作节点

动作节点执行某个操作，返回成功/失败/运行中。

```python
import os
from bt_core.nodes import ActionNode
from bt_core.status import NodeStatus


class FileReadNode(ActionNode):
    """文件读取节点"""

    NODE_TYPE = "FileReadNode"

    def _execute_action(self, context):
        # 1. 从 config 读取参数
        file_path = self.config.get("file_path", "")
        encoding = self.config.get("encoding", "utf-8")
        target_key = self.config.get("target_key", "file_content")

        # 2. 参数校验
        if not file_path or not os.path.exists(file_path):
            return NodeStatus.FAILURE

        # 3. 执行操作
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()

            # 4. 写入黑板
            context.blackboard.set(target_key, content)
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE
```

### 7.2 ConditionNode — 条件节点

条件节点返回 True/False，用于控制行为树流程。

```python
from bt_core.nodes import ConditionNode


class FileExistsNode(ConditionNode):
    """文件是否存在判断"""

    NODE_TYPE = "FileExistsNode"

    def _evaluate(self, context):
        file_path = self.config.get("file_path", "")
        target_key = self.config.get("target_key", "file_path")

        # 如果未指定 file_path，从黑板读取
        if not file_path:
            file_path = context.blackboard.get(target_key, "")

        return bool(file_path) and os.path.exists(file_path)
```

### 7.3 NodeStatus 返回值

| 状态 | 说明 | 使用场景 |
|------|------|---------|
| `NodeStatus.SUCCESS` | 执行成功 | 操作完成 |
| `NodeStatus.FAILURE` | 执行失败 | 文件不存在、参数错误、异常 |
| `NodeStatus.RUNNING` | 执行中 | 异步操作、等待资源 |

### 7.4 黑板操作

黑板是行为树中节点间共享数据的机制。

```python
def _execute_action(self, context):
    # 读取数据
    value = context.blackboard.get("key", default_value)

    # 写入数据
    context.blackboard.set("key", value)

    # 读取并删除（一次性消费）
    value = context.blackboard.get("key")
    if value is not None:
        context.blackboard.set("key", None)

    return NodeStatus.SUCCESS
```

### 7.5 异步节点

对于耗时操作（如网络请求、大文件处理），可设置为异步节点。

```python
class HttpRequestNode(ActionNode):
    """HTTP 请求节点（异步）"""

    NODE_TYPE = "HttpRequestNode"
    _is_async = True  # 标记为异步节点

    def _execute_action(self, context):
        import requests
        url = self.config.get("url", "")
        method = self.config.get("method", "GET")

        # 引擎会通过 AsyncExecutor 调度，不阻塞主循环
        response = requests.request(method, url, timeout=30)
        context.blackboard.set("response_status", response.status_code)
        context.blackboard.set("response_body", response.text)
        return NodeStatus.SUCCESS
```

---

## 8. 适配器开发

适配器用于封装外部系统连接（如数据库、串口、邮件服务器），供节点复用。

### 8.1 适配器基类

```python
from bt_adapters.base import BaseAdapter, AdapterLevel, AdapterStatus


class DatabaseAdapter(BaseAdapter):
    """数据库适配器示例"""

    @classmethod
    def get_adapter_level(cls) -> AdapterLevel:
        return AdapterLevel.REMOTE

    @classmethod
    def is_available(cls) -> bool:
        """检查依赖是否可用"""
        try:
            import sqlalchemy
            return True
        except ImportError:
            return False

    def start(self) -> None:
        """启动适配器 — 初始化连接池"""
        self._engine = sqlalchemy.create_engine(self._connection_string)

    def stop(self) -> None:
        """停止适配器 — 关闭连接"""
        if self._engine:
            self._engine.dispose()

    def get_name(self) -> str:
        return "database"

    def get_status(self) -> AdapterStatus:
        return AdapterStatus(
            running=self._engine is not None,
            name="database",
            level=AdapterLevel.REMOTE
        )
```

### 8.2 AdapterLevel 枚举

| 级别 | 说明 | 示例 |
|------|------|------|
| `LOCAL` | 本地资源 | 文件系统、剪贴板 |
| `REMOTE` | 远程资源 | 数据库、HTTP API |
| `HARDWARE` | 硬件设备 | 串口、GPIO |

### 8.3 在插件中注册适配器

```python
class MyPlugin(BasePlugin):
    def get_adapters(self):
        return {
            "database": DatabaseAdapter,
            "excel": ExcelAdapter,
        }
```

### 8.4 在节点中使用适配器

```python
def _execute_action(self, context):
    # 通过 PluginContext 获取适配器
    adapter = self.context.get_adapter("database")
    if not adapter:
        return NodeStatus.FAILURE

    result = adapter.query("SELECT * FROM users")
    context.blackboard.set("users", result)
    return NodeStatus.SUCCESS
```

---

## 9. 服务开发

服务是长期运行的功能模块，如通知服务、数据转换服务等。

### 9.1 服务基类

```python
from bt_services.base import BaseService


class EmailService(BaseService):
    """邮件通知服务"""

    def get_name(self) -> str:
        return "email"

    def start(self) -> None:
        """启动服务 — 初始化 SMTP 连接"""
        import smtplib
        self._smtp = smtplib.SMTP(self._host, self._port)
        self._smtp.login(self._username, self._password)

    def stop(self) -> None:
        """停止服务 — 关闭连接"""
        if self._smtp:
            self._smtp.quit()

    def send(self, to: str, subject: str, body: str) -> bool:
        """发送邮件"""
        try:
            self._smtp.sendmail(self._username, to, f"Subject: {subject}\n\n{body}")
            return True
        except Exception:
            return False
```

### 9.2 在插件中注册服务

```python
class MyPlugin(BasePlugin):
    def get_services(self):
        return {
            "email": EmailService(),  # 返回实例而非类
        }
```

### 9.3 在节点中使用服务

```python
def _execute_action(self, context):
    email_service = self.context.get_service("email")
    if not email_service:
        return NodeStatus.FAILURE

    to = self.config.get("to", "")
    subject = self.config.get("subject", "")
    body = context.blackboard.get("email_body", "")

    if email_service.send(to, subject, body):
        return NodeStatus.SUCCESS
    return NodeStatus.FAILURE
```

---

## 10. 插件配置 Schema

### 10.1 节点属性 Schema

定义节点在 GUI 属性面板中的配置项。

```python
def get_node_schemas(self):
    return {
        "FileReadNode": [
            {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
            {"key": "encoding", "label": "编码", "type": "text", "default": "utf-8"},
            {"key": "target_key", "label": "目标键名", "type": "text", "default": "file_content"},
        ],
    }
```

### 10.2 支持的字段类型

| type | GUI 控件 | 说明 |
|------|---------|------|
| `text` | 文本输入框 | 字符串 |
| `number` | 数字输入框 | 整数 |
| `select` | 下拉选择框 | 需提供 `options` |
| `bool` | 开关 | 布尔值 |
| `color` | 颜色选择器 | 十六进制颜色 |
| `region` | 区域选择器 | 屏幕区域 |
| `offset` | 偏移输入框 | 坐标偏移 |
| `screenshot` | 截图按钮 | 截图功能 |
| `region_offset` | 区域偏移组合 | 区域+偏移 |

### 10.3 select 类型示例

```python
{
    "key": "algorithm",
    "label": "算法",
    "type": "select",
    "options": ["astar", "dijkstra", "bfs"],
    "default": "astar"
}
```

### 10.4 插件配置 Schema

插件自身的配置（在插件管理面板中编辑）。

```python
def get_config_schema(self):
    return {
        "default_encoding": {
            "type": "text",
            "default": "utf-8",
            "label": "默认编码"
        },
        "max_file_size": {
            "type": "number",
            "default": 10485760,
            "label": "最大文件大小（字节）"
        },
        "allow_overwrite": {
            "type": "bool",
            "default": False,
            "label": "允许覆盖文件"
        },
        "default_algorithm": {
            "type": "select",
            "default": "astar",
            "label": "默认算法",
            "options": ["astar", "dijkstra", "bfs"]
        }
    }
```

配置项会自动保存到 `settings.json`：

```json
{
    "plugins": {
        "my_plugin": {
            "default_encoding": "utf-8",
            "max_file_size": 5242880,
            "allow_overwrite": true,
            "default_algorithm": "dijkstra"
        }
    }
}
```

在插件中读取配置：

```python
def on_start(self):
    # 通过 context 读取
    encoding = self.context.get_config("default_encoding", "utf-8")
    max_size = self.context.get_config("max_file_size", 10485760)
```

---

## 11. 插件 API 参考

### 11.1 BasePlugin API

| API | 说明 |
|-----|------|
| `self.info` | PluginInfo 对象，包含插件元信息 |
| `self.context` | PluginContext 对象 |
| `self.log(level, msg)` | 记录日志（level: info/warning/error/debug） |
| `self._loaded` | 是否已加载 |
| `self._started` | 是否已启动 |

### 11.2 PluginContext API

| API | 说明 | 示例 |
|-----|------|------|
| `self.context.get_config(key, default)` | 读取插件配置 | `self.context.get_config("encoding", "utf-8")` |
| `self.context.publish(topic, data)` | 发布消息 | `self.context.publish("my_plugin.event", {"key": "value"})` |
| `self.context.subscribe(topic, callback)` | 订阅消息 | `self.context.subscribe("bt.**.event.**", self._on_event)` |
| `self.context.get_adapter(name)` | 获取适配器 | `self.context.get_adapter("database")` |
| `self.context.get_service(name)` | 获取服务 | `self.context.get_service("email")` |
| `self.context.plugin_name` | 当前插件名 | `self.context.plugin_name` |

### 11.3 节点 API

| API | 说明 |
|-----|------|
| `self.config.get(key, default)` | 读取节点配置 |
| `self.NODE_TYPE` | 节点类型标识 |
| `self._is_async` | 是否为异步节点 |
| `context.blackboard.get(key, default)` | 读取黑板数据 |
| `context.blackboard.set(key, value)` | 写入黑板数据 |

### 11.4 消息总线主题

插件可订阅以下主题：

| 主题模式 | 说明 |
|---------|------|
| `bt.{tree_id}.tick` | 行为树每次 tick |
| `bt.{tree_id}.node.{node_id}.started` | 节点开始执行 |
| `bt.{tree_id}.node.{node_id}.finished` | 节点执行完成 |
| `bt.**.event.**` | 所有事件（通配符） |
| `bt.{tree_id}.blackboard.changed` | 黑板数据变更 |

发布自定义消息：

```python
def _execute_action(self, context):
    # ... 执行操作 ...
    self.context.publish("my_plugin.task_completed", {
        "task_id": "task_001",
        "result": "success",
        "timestamp": "2026-07-28T10:00:00"
    })
    return NodeStatus.SUCCESS
```

---

## 12. 测试与调试

### 12.1 测试目录结构

```
plugins/my_plugin/
└── tests/
    ├── __init__.py
    ├── test_nodes.py        # 节点单元测试
    └── test_plugin_lifecycle.py  # 插件生命周期测试
```

### 12.2 节点单元测试模板

```python
import os
import pytest
from bt_core.status import NodeStatus


def _make_context(blackboard=None):
    """创建测试上下文"""
    from bt_core.context import ExecutionContext
    ctx = ExecutionContext()
    if blackboard:
        for k, v in blackboard.items():
            ctx.blackboard.set(k, v)
    return ctx


def test_file_read_success(tmp_path):
    """测试文件读取成功"""
    from plugins.my_plugin.nodes import FileReadNode

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

    assert status == NodeStatus.SUCCESS
    assert ctx.blackboard.get("content") == "hello world"


def test_file_read_failure_missing_file():
    """测试文件不存在时返回 FAILURE"""
    from plugins.my_plugin.nodes import FileReadNode

    node = FileReadNode()
    node.config = {
        "file_path": "/nonexistent/file.txt",
        "encoding": "utf-8",
        "target_key": "content"
    }

    ctx = _make_context()
    status = node._execute_action(ctx)

    assert status == NodeStatus.FAILURE
```

### 12.3 插件生命周期测试模板

```python
def test_plugin_lifecycle():
    """测试插件完整生命周期"""
    from plugins.my_plugin.main import MyPlugin
    from bt_plugins.base import PluginInfo, PluginContext

    info = PluginInfo(
        name="my_plugin",
        display_name="我的插件",
        version="1.0.0",
        author="tester",
        description="test"
    )
    plugin = MyPlugin(info)
    plugin.on_load()
    assert plugin._loaded

    nodes = plugin.get_nodes()
    assert "FileReadNode" in nodes

    schemas = plugin.get_node_schemas()
    assert "FileReadNode" in schemas

    plugin.on_unload()
    assert not plugin._loaded
```

### 12.4 运行测试

```bash
# 运行单个插件的测试
python -m pytest plugins/my_plugin/tests/ -v

# 运行所有插件测试
python -m pytest plugins/ -v

# 运行集成测试
python -m pytest tests/test_plugin_integration.py -v

# 运行全套测试
python -m pytest tests/ plugins/ -v
```

### 12.5 调试技巧

#### 查看插件日志

插件日志通过 `LogManager.debug_print` 输出，前缀为 `[Plugin:{plugin_name}]`。

```bash
# 运行时查看日志
python cli.py run my_tree.json --headless --plugins 2>&1 | grep "\[Plugin:"
```

#### 使用 CLI 调试

```bash
# 查看插件信息
python cli.py plugin info my_plugin

# 加载并启动插件
python cli.py plugin load plugins/my_plugin/
python cli.py plugin start my_plugin
```

#### 常见调试问题

1. **节点未出现在面板**：检查 `get_node_display_info()` 是否返回正确
2. **属性面板空白**：检查 `get_node_schemas()` 的 `key` 与节点 `self.config.get(key)` 是否匹配
3. **插件加载失败**：检查 `plugin.json` 格式、`entry`/`class` 字段、导入语句
4. **节点执行失败**：在 `_execute_action` 中添加 `self.log("debug", ...)` 打印调试信息

---

## 13. 部署与发布

### 13.1 依赖管理

在插件目录下创建 `requirements.txt`：

```
openpyxl>=3.0.0
requests>=2.28.0
```

用户安装插件时需要手动安装依赖：

```bash
pip install -r plugins/my_plugin/requirements.txt
```

### 13.2 依赖检测

在节点中使用 try/except 检测依赖：

```python
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class ExcelReadNode(ActionNode):
    def _execute_action(self, context):
        if not OPENPYXL_AVAILABLE:
            self.log("error", "openpyxl 未安装，请运行 pip install openpyxl")
            return NodeStatus.FAILURE
        # ... 正常逻辑 ...
```

### 13.3 版本兼容性

在 `plugin.json` 中声明最低应用版本：

```json
{
    "min_app_version": "2.0.0"
}
```

在插件代码中可检查版本：

```python
def on_load(self):
    from main import VERSION
    if VERSION < "2.0.0":
        raise RuntimeError("需要应用版本 2.0.0 或更高")
```

### 13.4 插件打包

插件以目录形式分发，包含所有必要文件：

```
my_plugin_v1.0.0.zip
└── my_plugin/
    ├── plugin.json
    ├── main.py
    ├── nodes.py
    ├── __init__.py
    ├── requirements.txt
    └── README.md
```

用户解压到 `plugins/` 目录即可使用。

---

## 14. 常见问题

### Q1: 插件加载失败怎么办？

**排查步骤**：

1. 检查 `plugin.json` 格式是否正确（使用 JSON 验证器）
2. 检查 `entry` 字段指向的文件是否存在
3. 检查 `class` 字段指向的类名是否正确
4. 检查 `main.py` 中是否使用了相对导入（`from .xxx`）— 必须使用绝对导入
5. 运行 `python cli.py plugin load plugins/my_plugin/` 查看错误信息

### Q2: 插件节点未出现在节点面板？

**排查步骤**：

1. 确认插件已启动（状态指示器为绿色 ●）
2. 检查 `get_node_display_info()` 是否返回了节点信息
3. 检查 `get_nodes()` 返回的字典 key 是否与 `get_node_display_info()` 的 key 一致
4. 点击节点面板的「插件节点」分类展开

### Q3: 属性面板配置项为空？

**排查步骤**：

1. 检查 `get_node_schemas()` 是否返回了 schema
2. 检查 schema 中的 `key` 是否与节点 `self.config.get(key)` 使用的 key 一致
3. 检查 schema 中的 `type` 是否为支持的类型（text/number/select/bool）

### Q4: 节点执行总是返回 FAILURE？

**排查步骤**：

1. 在 `_execute_action` 开头添加 `self.log("debug", ...)` 打印参数
2. 检查 `self.config.get(key, default)` 的 key 是否与 schema 中的 key 匹配
3. 检查文件路径、URL 等是否正确
4. 检查 try/except 是否吞掉了异常（建议记录异常信息）

```python
import traceback

def _execute_action(self, context):
    try:
        # ... 你的逻辑 ...
        return NodeStatus.SUCCESS
    except Exception as e:
        self.log("error", f"执行失败: {e}\n{traceback.format_exc()}")
        return NodeStatus.FAILURE
```

### Q5: 第三方依赖未安装怎么办？

**方案 1**：在节点中检测并提示

```python
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

class ExcelReadNode(ActionNode):
    def _execute_action(self, context):
        if not OPENPYXL_AVAILABLE:
            self.log("error", "请安装 openpyxl: pip install openpyxl")
            return NodeStatus.FAILURE
```

**方案 2**：在 `on_load` 中检测

```python
def on_load(self):
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("此插件需要 openpyxl，请运行: pip install openpyxl")
```

### Q6: 如何在 Headless 模式使用插件？

```bash
# 启用插件系统
python cli.py run my_tree.json --headless --plugins

# 或在配置文件中启用
python cli.py config set plugins.enabled true
```

Headless 模式会自动扫描 `bt_plugins/builtin/` 和 `plugins/` 目录下的插件。

### Q7: 如何发布我的插件？

1. 整理插件目录，确保包含 `plugin.json`、`main.py`、`__init__.py`
2. 编写 `README.md` 说明插件功能和使用方法
3. 创建 `requirements.txt` 列出第三方依赖
4. 打包为 zip 文件
5. 用户解压到 `plugins/` 目录即可

### Q8: 插件之间如何通信？

**方案 1**：通过消息总线

```python
# 插件 A 发布消息
self.context.publish("plugin_a.event", {"data": "value"})

# 插件 B 订阅消息
def on_load(self):
    self.context.subscribe("plugin_a.event", self._on_event)

def _on_event(self, topic, data):
    print(f"收到消息: {data}")
```

**方案 2**：通过黑板

```python
# 插件 A 写入黑板
context.blackboard.set("shared_data", value)

# 插件 B 读取黑板
value = context.blackboard.get("shared_data")
```

**方案 3**：通过服务

```python
# 插件 A 注册服务
def get_services(self):
    return {"my_service": MyService()}

# 插件 B 使用服务
service = self.context.get_service("my_service")
result = service.do_something()
```

### Q9: 如何处理插件的并发安全？

如果插件有共享状态，使用线程锁：

```python
import threading

class MyPlugin(BasePlugin):
    def on_load(self):
        self._lock = threading.Lock()
        self._cache = {}

    def _execute_action(self, context):
        with self._lock:
            # 线程安全的操作
            self._cache[key] = value
```

### Q10: 如何卸载插件？

```bash
# 停止插件
python cli.py plugin stop my_plugin

# 通过 CLI 卸载（用户插件）
python cli.py plugin unload my_plugin
```

内置插件（`bt_plugins/builtin/`）不可卸载，只能停止。

---

## 附录：插件示例清单

| 插件 | 目录 | 提供的节点 | 适配器 | 依赖 |
|------|------|-----------|--------|------|
| 示例插件 | `bt_plugins/builtin/example/` | — | — | 无 |
| 文件处理 | `plugins/file_processor/` | FileReadNode, FileWriteNode, FileMoveNode | — | 无 |
| Excel自动化 | `plugins/excel_automation/` | ExcelReadNode, ExcelWriteNode, ExcelFormatNode | ExcelAdapter | openpyxl |

---

## 附录：完整插件模板

最小可用插件模板（3 个文件）：

**plugin.json**:
```json
{
    "name": "my_plugin",
    "display_name": "我的插件",
    "version": "1.0.0",
    "author": "作者",
    "description": "插件描述",
    "category": "general",
    "entry": "main.py",
    "class": "MyPlugin"
}
```

**main.py**:
```python
from bt_plugins.base import BasePlugin
from bt_core.nodes import ActionNode
from bt_core.status import NodeStatus


class MyNode(ActionNode):
    NODE_TYPE = "MyNode"

    def _execute_action(self, context):
        self.log("info", "执行节点")
        return NodeStatus.SUCCESS


class MyPlugin(BasePlugin):
    def on_load(self):
        self._loaded = True
        self.log("info", "插件已加载")

    def on_unload(self):
        self._loaded = False

    def on_start(self):
        self._started = True

    def on_stop(self):
        self._started = False

    def get_nodes(self):
        return {"MyNode": MyNode}

    def get_node_schemas(self):
        return {
            "MyNode": [
                {"key": "param", "label": "参数", "type": "text", "default": ""}
            ]
        }

    def get_node_display_info(self):
        return {
            "MyNode": {
                "display_name": "我的节点",
                "description": "节点描述",
                "category": "plugin",
                "icon": "★"
            }
        }
```

**__init__.py**:
```python
"""我的插件"""
```

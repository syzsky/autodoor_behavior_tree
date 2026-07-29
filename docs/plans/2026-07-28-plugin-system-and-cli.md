# 插件系统与 CLI 工具实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在消息总线与外部系统集成基础上，实现插件系统（后端+前端）和 CLI 工具

**Architecture:** 插件系统通过 BasePlugin 抽象基类 + PluginLoader 加载器，复用现有 NodeRegistry/AdapterManager/ServiceRegistry 注册机制。CLI 工具基于 HeadlessRunner，通过 argparse 实现命令路由。

**Tech Stack:** Python 3.10+, CustomTkinter (GUI), argparse (CLI), importlib (插件加载)

**参考文档:** [08_插件系统与CLI工具开发方案.md](../../md/08_插件系统与CLI工具开发方案.md)

---

## Task 1: 插件框架基础 — bt_plugins/base.py

**Files:**
- Create: `bt_plugins/__init__.py`
- Create: `bt_plugins/base.py`
- Test: `tests/test_plugin_base.py`

**Step 1: Write the failing test**

```python
# tests/test_plugin_base.py
import pytest
from bt_plugins.base import BasePlugin, PluginInfo, PluginContext


def test_plugin_info_creation():
    info = PluginInfo(name="test", display_name="测试", version="1.0.0",
                      author="tester", description="test plugin")
    assert info.name == "test"
    assert info.display_name == "测试"
    assert info.category == "general"
    assert info.dependencies is None


def test_plugin_lifecycle():
    info = PluginInfo(name="test", display_name="测试", version="1.0.0",
                      author="t", description="d")
    plugin = BasePlugin(info)
    assert not plugin._loaded
    plugin.on_load()
    assert plugin._loaded
    plugin.on_start()
    assert plugin._started
    plugin.on_stop()
    assert not plugin._started
    plugin.on_unload()


def test_plugin_default_extensions():
    info = PluginInfo(name="test", display_name="测试", version="1.0.0",
                      author="t", description="d")
    plugin = BasePlugin(info)
    assert plugin.get_nodes() == {}
    assert plugin.get_adapters() == {}
    assert plugin.get_services() == {}
    assert plugin.get_node_schemas() == {}
    assert plugin.get_node_display_info() == {}
    assert plugin.get_config_schema() == {}
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plugin_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bt_plugins'`

**Step 3: Write minimal implementation**

```python
# bt_plugins/__init__.py
"""插件系统框架"""
from .base import BasePlugin, PluginInfo, PluginContext

__all__ = ["BasePlugin", "PluginInfo", "PluginContext"]
```

```python
# bt_plugins/base.py
"""插件接口规范 — BasePlugin / PluginInfo / PluginContext"""
from abc import ABC, abstractmethod
from typing import Dict, List, Type, Any, Optional
from dataclasses import dataclass, field


@dataclass
class PluginInfo:
    """插件元信息"""
    name: str
    display_name: str
    version: str
    author: str
    description: str
    category: str = "general"
    min_app_version: str = ""
    dependencies: List[str] = None


class PluginContext:
    """插件运行上下文 — 隔离插件与主系统的直接依赖"""

    def __init__(self, settings=None, message_bus=None,
                 adapter_manager=None, service_registry=None):
        self._settings = settings
        self._message_bus = message_bus
        self._adapter_manager = adapter_manager
        self._service_registry = service_registry
        self._plugin_name = ""

    def set_plugin_name(self, name: str):
        self._plugin_name = name

    @property
    def plugin_name(self) -> str:
        return self._plugin_name

    def get_config(self, key: str, default=None):
        if self._settings:
            return self._settings.get(f"plugins.{self._plugin_name}.{key}", default)
        return default

    def publish(self, topic: str, data: Any) -> str:
        if self._message_bus:
            return self._message_bus.publish(topic, data)
        return ""

    def subscribe(self, topic: str, callback) -> str:
        if self._message_bus:
            return self._message_bus.subscribe(topic, callback)
        return ""

    def get_adapter(self, name: str):
        if self._adapter_manager:
            return self._adapter_manager.get_adapter(name)
        return None

    def get_service(self, name: str):
        if self._service_registry:
            return self._service_registry.get(name)
        return None

    def log(self, level: str, msg: str):
        from bt_utils.log_manager import LogManager
        prefix = f"[Plugin:{self._plugin_name}] "
        getattr(LogManager, level.lower(), LogManager.info)(prefix + msg)


class BasePlugin(ABC):
    """插件抽象基类

    生命周期: on_load() → on_start() → [运行中] → on_stop() → on_unload()
    """

    def __init__(self, info: PluginInfo):
        self.info = info
        self._loaded = False
        self._started = False
        self._context: Optional[PluginContext] = None

    def set_context(self, context: PluginContext):
        self._context = context

    @property
    def context(self) -> PluginContext:
        return self._context

    def log(self, level: str, msg: str):
        if self._context:
            self._context.log(level, msg)
        else:
            print(f"[Plugin:{self.info.name}] {msg}")

    # ── 生命周期方法 ──

    @abstractmethod
    def on_load(self) -> None:
        self._loaded = True

    @abstractmethod
    def on_unload(self) -> None:
        self._loaded = False

    def on_start(self) -> None:
        self._started = True

    def on_stop(self) -> None:
        self._started = False

    # ── 扩展点 ──

    def get_nodes(self) -> Dict[str, Type]:
        return {}

    def get_adapters(self) -> Dict[str, Type]:
        return {}

    def get_services(self) -> Dict[str, Any]:
        return {}

    def get_node_schemas(self) -> Dict[str, list]:
        return {}

    def get_node_display_info(self) -> Dict[str, dict]:
        return {}

    def get_config_schema(self) -> dict:
        return {}
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_plugin_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bt_plugins/__init__.py bt_plugins/base.py tests/test_plugin_base.py
git commit -m "feat: add plugin framework base (BasePlugin, PluginInfo, PluginContext)"
```

---

## Task 2: 插件加载器 — bt_plugins/loader.py

**Files:**
- Create: `bt_plugins/loader.py`
- Test: `tests/test_plugin_loader.py`

**Step 1: Write the failing test**

```python
# tests/test_plugin_loader.py
import os
import json
import tempfile
import pytest
from bt_plugins.base import PluginInfo, PluginContext
from bt_plugins.loader import PluginLoader


def _create_test_plugin(tmpdir, name="test_plugin"):
    """创建测试插件目录"""
    plugin_dir = os.path.join(tmpdir, name)
    os.makedirs(plugin_dir, exist_ok=True)

    manifest = {
        "name": name,
        "display_name": "测试插件",
        "version": "1.0.0",
        "author": "tester",
        "description": "test",
        "entry": "main.py",
        "class": "TestPlugin",
    }
    with open(os.path.join(plugin_dir, "plugin.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)

    main_py = '''
from bt_plugins.base import BasePlugin, PluginInfo

class TestPlugin(BasePlugin):
    def on_load(self):
        self._loaded = True
    def on_unload(self):
        self._loaded = False
'''
    with open(os.path.join(plugin_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(main_py)

    return plugin_dir


def test_scan_plugins(tmp_path):
    _create_test_plugin(str(tmp_path))
    loader = PluginLoader(PluginContext())
    infos = loader.scan(str(tmp_path))
    assert len(infos) == 1
    assert infos[0].name == "test_plugin"


def test_load_plugin(tmp_path):
    plugin_dir = _create_test_plugin(str(tmp_path))
    loader = PluginLoader(PluginContext())
    assert loader.load_plugin(plugin_dir)
    assert "test_plugin" in loader._plugins


def test_start_stop_plugin(tmp_path):
    plugin_dir = _create_test_plugin(str(tmp_path))
    loader = PluginLoader(PluginContext())
    loader.load_plugin(plugin_dir)
    assert loader.start_plugin("test_plugin")
    assert loader._plugins["test_plugin"]._started
    loader.stop_plugin("test_plugin")
    assert not loader._plugins["test_plugin"]._started
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plugin_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bt_plugins.loader'`

**Step 3: Write implementation**

```python
# bt_plugins/loader.py
"""插件加载器 — 扫描、加载、管理插件生命周期"""
import os
import json
import importlib.util
import sys
import traceback
from typing import Dict, List, Optional, Type

from .base import BasePlugin, PluginInfo, PluginContext


class PluginLoader:
    """插件加载器"""

    def __init__(self, context: PluginContext):
        self._context = context
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_infos: Dict[str, PluginInfo] = {}
        self._plugin_dirs: Dict[str, str] = {}  # name → plugin directory
        self._registered_nodes: Dict[str, str] = {}  # node_type → plugin_name
        self._registered_adapters: Dict[str, str] = {}
        self._registered_services: Dict[str, str] = {}

    def scan(self, plugins_dir: str) -> List[PluginInfo]:
        """扫描插件目录，返回所有有效插件的 PluginInfo 列表"""
        results = []
        if not os.path.isdir(plugins_dir):
            return results

        for entry in os.listdir(plugins_dir):
            plugin_dir = os.path.join(plugins_dir, entry)
            manifest_path = os.path.join(plugin_dir, "plugin.json")
            if not os.path.isfile(manifest_path):
                continue
            try:
                info = self._read_manifest(manifest_path)
                if info:
                    results.append(info)
            except Exception as e:
                print(f"[PluginLoader] 跳过无效插件 {entry}: {e}")
        return results

    def _read_manifest(self, path: str) -> Optional[PluginInfo]:
        """读取 plugin.json"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PluginInfo(
            name=data["name"],
            display_name=data["display_name"],
            version=data["version"],
            author=data["author"],
            description=data["description"],
            category=data.get("category", "general"),
            min_app_version=data.get("min_app_version", ""),
            dependencies=data.get("dependencies"),
        )

    def load_plugin(self, plugin_dir: str) -> bool:
        """加载单个插件"""
        manifest_path = os.path.join(plugin_dir, "plugin.json")
        if not os.path.isfile(manifest_path):
            print(f"[PluginLoader] 未找到 plugin.json: {plugin_dir}")
            return False

        try:
            info = self._read_manifest(manifest_path)
            if not info:
                return False

            # 检查依赖
            if info.dependencies:
                for dep in info.dependencies:
                    if dep not in self._plugins:
                        print(f"[PluginLoader] 缺少依赖插件: {dep}")
                        return False

            # 读取入口文件配置
            manifest = json.load(open(manifest_path, "r", encoding="utf-8"))
            entry_file = manifest.get("entry", "main.py")
            class_name = manifest.get("class", "")

            # 动态导入
            entry_path = os.path.join(plugin_dir, entry_file)
            module_name = f"bt_plugin_{info.name}"

            spec = importlib.util.spec_from_file_location(module_name, entry_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 获取插件类
            plugin_class = getattr(module, class_name, None)
            if plugin_class is None or not issubclass(plugin_class, BasePlugin):
                print(f"[PluginLoader] 未找到有效的插件类: {class_name}")
                return False

            # 实例化
            plugin = plugin_class(info)
            context = PluginContext(
                settings=self._context._settings,
                message_bus=self._context._message_bus,
                adapter_manager=self._context._adapter_manager,
                service_registry=self._context._service_registry,
            )
            context.set_plugin_name(info.name)
            plugin.set_context(context)

            # 调用 on_load
            plugin.on_load()

            self._plugins[info.name] = plugin
            self._plugin_infos[info.name] = info
            self._plugin_dirs[info.name] = plugin_dir

            return True

        except Exception as e:
            print(f"[PluginLoader] 加载插件失败 {plugin_dir}: {e}")
            traceback.print_exc()
            return False

    def start_plugin(self, name: str) -> bool:
        """启动插件 — 注册节点/适配器/服务"""
        plugin = self._plugins.get(name)
        if not plugin:
            return False
        if plugin._started:
            return True

        try:
            plugin.on_start()

            # 注册节点
            nodes = plugin.get_nodes()
            for node_type, node_class in nodes.items():
                prefixed_type = f"{name}.{node_type}"
                from bt_core.registry import NodeRegistry
                NodeRegistry.register(prefixed_type, node_class)
                self._registered_nodes[prefixed_type] = name

            # 注册适配器
            adapters = plugin.get_adapters()
            for adapter_name, adapter_class in adapters.items():
                from bt_adapters.adapter_manager import AdapterManager
                AdapterManager.register_adapter(adapter_name, adapter_class)
                self._registered_adapters[adapter_name] = name

            # 注册服务
            services = plugin.get_services()
            for service_name, service_instance in services.items():
                from bt_services.registry import ServiceRegistry
                # ServiceRegistry 实例由外部注入，这里通过 context 获取
                if self._context._service_registry:
                    self._context._service_registry.register(service_name, service_instance)
                self._registered_services[service_name] = name

            return True
        except Exception as e:
            print(f"[PluginLoader] 启动插件失败 {name}: {e}")
            traceback.print_exc()
            return False

    def stop_plugin(self, name: str) -> None:
        """停止插件 — 注销已注册的内容"""
        plugin = self._plugins.get(name)
        if not plugin or not plugin._started:
            return

        try:
            plugin.on_stop()

            # 注销节点
            to_remove = [nt for nt, pn in self._registered_nodes.items() if pn == name]
            for node_type in to_remove:
                from bt_core.registry import NodeRegistry
                NodeRegistry.unregister(node_type)
                del self._registered_nodes[node_type]

            # 注销适配器
            to_remove = [an for an, pn in self._registered_adapters.items() if pn == name]
            for adapter_name in to_remove:
                del self._registered_adapters[adapter_name]

            # 注销服务
            to_remove = [sn for sn, pn in self._registered_services.items() if pn == name]
            for service_name in to_remove:
                if self._context._service_registry:
                    self._context._service_registry.unregister(service_name)
                del self._registered_services[service_name]

        except Exception as e:
            print(f"[PluginLoader] 停止插件失败 {name}: {e}")

    def unload_plugin(self, name: str) -> None:
        """卸载插件"""
        self.stop_plugin(name)
        plugin = self._plugins.get(name)
        if plugin:
            try:
                plugin.on_unload()
            except Exception as e:
                print(f"[PluginLoader] 卸载插件失败 {name}: {e}")
            del self._plugins[name]
            self._plugin_infos.pop(name, None)
            self._plugin_dirs.pop(name, None)
            # 清理 sys.modules
            module_name = f"bt_plugin_{name}"
            sys.modules.pop(module_name, None)

    def start_all(self) -> None:
        """启动所有已加载的插件"""
        for name in list(self._plugins.keys()):
            self.start_plugin(name)

    def stop_all(self) -> None:
        """停止所有插件"""
        for name in list(self._plugins.keys()):
            self.stop_plugin(name)

    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        return self._plugin_infos.get(name)

    def list_plugins(self) -> List[PluginInfo]:
        return list(self._plugin_infos.values())

    def is_started(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        return plugin._started if plugin else False
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_plugin_loader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bt_plugins/loader.py tests/test_plugin_loader.py
git commit -m "feat: add PluginLoader for plugin lifecycle management"
```

---

## Task 3: GUI 动态合并工具 — bt_plugins/gui_integration.py

**Files:**
- Create: `bt_plugins/gui_integration.py`
- Test: `tests/test_gui_integration.py`

**Step 1: Write the failing test**

```python
# tests/test_gui_integration.py
from bt_plugins.gui_integration import (
    merge_plugin_nodes, merge_plugin_schemas, merge_plugin_palette
)


def test_merge_plugin_nodes():
    category_map = {"ExistingNode": "action"}
    display_names = {"ExistingNode": "已有"}
    descriptions = {"ExistingNode": "desc"}

    plugin_info = {
        "CustomNode": {
            "display_name": "自定义",
            "description": "插件节点",
            "category": "plugin",
        }
    }

    merge_plugin_nodes(category_map, display_names, descriptions, plugin_info)

    assert "CustomNode" in category_map
    assert category_map["CustomNode"] == "plugin"
    assert display_names["CustomNode"] == "自定义"
    assert descriptions["CustomNode"] == "插件节点"


def test_merge_plugin_schemas():
    existing = {"ExistingNode": [{"key": "a", "label": "A"}]}
    plugin_schemas = {"CustomNode": [{"key": "b", "label": "B"}]}

    merge_plugin_schemas(existing, plugin_schemas)

    assert "CustomNode" in existing
    assert existing["CustomNode"][0]["key"] == "b"


def test_merge_plugin_palette():
    categories = {
        "组合节点": {"icon": "◇", "color": "#6366F1", "nodes": []}
    }

    plugin_nodes = [
        ("CustomNode", "自定义", "插件节点"),
    ]

    merge_plugin_palette(categories, plugin_nodes, color="#6B7280")

    assert "插件节点" in categories
    assert len(categories["插件节点"]["nodes"]) == 1
    assert categories["插件节点"]["nodes"][0][0] == "CustomNode"
```

**Step 2-4: Write implementation and verify**

```python
# bt_plugins/gui_integration.py
"""GUI 常量动态合并工具"""


def merge_plugin_nodes(node_category_map, node_display_names,
                       node_descriptions, plugin_display_info):
    """将插件节点信息合并到 GUI 常量中"""
    for node_type, info in plugin_display_info.items():
        category = info.get("category", "plugin")
        node_category_map[node_type] = category
        node_display_names[node_type] = info.get("display_name", node_type)
        node_descriptions[node_type] = info.get("description", "")


def merge_plugin_schemas(existing_schemas, plugin_schemas):
    """将插件节点 schema 合并到属性面板配置中"""
    for node_type, schema in plugin_schemas.items():
        existing_schemas[node_type] = schema


def merge_plugin_palette(categories_dict, plugin_nodes, color="#6B7280", icon="★"):
    """将插件节点添加到节点面板的分类中"""
    if "插件节点" not in categories_dict:
        categories_dict["插件节点"] = {
            "icon": icon,
            "color": color,
            "nodes": []
        }
    categories_dict["插件节点"]["nodes"].extend(plugin_nodes)
```

**Step 5: Commit**

```bash
git add bt_plugins/gui_integration.py tests/test_gui_integration.py
git commit -m "feat: add GUI integration utilities for plugin node merging"
```

---

## Task 4: 配置支持 — settings_manager.py

**Files:**
- Modify: `config/settings_manager.py`

**Step 1: Read current settings_manager to find the default config dict**

Read `config/settings_manager.py` and locate the `_default_settings` or similar dict.

**Step 2: Add plugins/schedules config sections**

Add to default settings:
```python
"plugins": {},
"schedules": {},
```

**Step 3: Verify config loads**

Run: `python -c "from config.settings_manager import get_settings_manager; s = get_settings_manager(); print(s.get('plugins', {}))"`

**Step 4: Commit**

```bash
git add config/settings_manager.py
git commit -m "feat: add plugins and schedules config sections"
```

---

## Task 5: 示例内置插件

**Files:**
- Create: `bt_plugins/builtin/__init__.py`
- Create: `bt_plugins/builtin/example/plugin.json`
- Create: `bt_plugins/builtin/example/main.py`

**Step 1: Create example plugin**

```python
# bt_plugins/builtin/__init__.py
"""内置插件包"""
```

```json
// bt_plugins/builtin/example/plugin.json
{
    "name": "example",
    "display_name": "示例插件",
    "version": "1.0.0",
    "author": "AutoDoor Team",
    "description": "插件开发示例",
    "category": "general",
    "entry": "main.py",
    "class": "ExamplePlugin"
}
```

```python
# bt_plugins/builtin/example/main.py
from bt_plugins.base import BasePlugin, PluginInfo


class ExamplePlugin(BasePlugin):
    """示例插件 — 展示插件开发的基本模式"""

    def on_load(self):
        self._loaded = True
        self.log("info", "示例插件已加载")

    def on_unload(self):
        self._loaded = False
        self.log("info", "示例插件已卸载")

    def on_start(self):
        self._started = True
        self.log("info", "示例插件已启动")

    def on_stop(self):
        self._started = False
        self.log("info", "示例插件已停止")
```

**Step 2: Commit**

```bash
git add bt_plugins/builtin/
git commit -m "feat: add example builtin plugin"
```

---

## Task 6: 插件管理面板 — bt_gui/plugin_panel.py

**Files:**
- Create: `bt_gui/plugin_panel.py`

**Step 1: Implement plugin management panel**

基于 CustomTkinter 的插件管理面板，包含：
- 插件列表（名称、版本、状态、启动/停止按钮）
- 加载插件按钮
- 插件配置区域

**Step 2: Commit**

---

## Task 7: GUI 集成

**Files:**
- Modify: `bt_gui/bt_editor/constants.py` — 添加插件节点合并支持
- Modify: `bt_gui/bt_editor/palette.py` — 支持动态分类
- Modify: `bt_gui/app.py` — 集成插件管理面板

**Step 1: Add dynamic merge support to constants.py**

在 `build_node_categories()` 末尾添加插件节点合并调用点。

**Step 2: Add dynamic palette support**

在 `NodePalette.__init__()` 中支持从 PluginLoader 获取插件节点。

**Step 3: Integrate plugin panel into app.py**

在设置标签页中嵌入插件管理面板。

**Step 4: Commit**

---

## Task 8: CLI 入口 — cli.py + bt_cli 包 + run 命令

**Files:**
- Create: `cli.py`
- Create: `bt_cli/__init__.py`
- Create: `bt_cli/commands/__init__.py`
- Create: `bt_cli/commands/run.py`

**Step 1: Create CLI entry and run command**

```python
# cli.py
"""AutoDoor Behavior Tree CLI"""
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(prog="autodoor-bt", description="AutoDoor 行为树 CLI 工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run 命令
    run_parser = subparsers.add_parser("run", help="运行行为树")
    run_parser.add_argument("tree_file", help="行为树 JSON 文件路径")
    run_parser.add_argument("--headless", action="store_true", help="无 GUI 模式")
    run_parser.add_argument("--project", default=None, help="项目根目录")
    run_parser.add_argument("--bus", action="store_true", help="启用消息总线")
    run_parser.add_argument("--rest", action="store_true", help="启用 REST API")
    run_parser.add_argument("--rest-host", default="127.0.0.1")
    run_parser.add_argument("--rest-port", type=int, default=8080)
    run_parser.add_argument("--ws", action="store_true", help="启用 WebSocket 服务")
    run_parser.add_argument("--ws-host", default="127.0.0.1")
    run_parser.add_argument("--ws-port", type=int, default=8765)
    run_parser.add_argument("--plugins", action="store_true", help="启用插件系统")

    # status 命令
    subparsers.add_parser("status", help="查询运行状态")

    # stop 命令
    stop_parser = subparsers.add_parser("stop", help="停止行为树")
    stop_parser.add_argument("tree_id", nargs="?", default=None)
    stop_parser.add_argument("--all", action="store_true")
    stop_parser.add_argument("--force", action="store_true")

    # schedule 命令
    sched_parser = subparsers.add_parser("schedule", help="定时调度管理")
    sched_sub = sched_parser.add_subparsers(dest="schedule_action")
    sched_add = sched_sub.add_parser("add")
    sched_add.add_argument("tree_file")
    sched_add.add_argument("--cron", default=None)
    sched_add.add_argument("--interval", default=None)
    sched_add.add_argument("--once", default=None)
    sched_add.add_argument("--name", default="")
    sched_add.add_argument("--headless", action="store_true")
    sched_sub.add_parser("list")
    sched_rm = sched_sub.add_parser("remove")
    sched_rm.add_argument("task_id")

    # daemon 命令
    daemon_parser = subparsers.add_parser("daemon", help="守护进程模式")
    daemon_parser.add_argument("--start", action="store_true")
    daemon_parser.add_argument("--stop", action="store_true")
    daemon_parser.add_argument("--restart", action="store_true")
    daemon_parser.add_argument("--status", action="store_true")
    daemon_parser.add_argument("--foreground", action="store_true")

    # remote 命令
    remote_parser = subparsers.add_parser("remote", help="远程控制")
    remote_parser.add_argument("target", help="host:port")
    remote_parser.add_argument("action", choices=["status", "trees", "start", "stop", "blackboard", "nodes"])
    remote_parser.add_argument("--tree-id", default=None)
    remote_parser.add_argument("--token", default=None)
    remote_parser.add_argument("--json", action="store_true")

    # plugin 命令
    plugin_parser = subparsers.add_parser("plugin", help="插件管理")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_action")
    plugin_sub.add_parser("list")
    plugin_load = plugin_sub.add_parser("load")
    plugin_load.add_argument("path")
    plugin_start = plugin_sub.add_parser("start")
    plugin_start.add_argument("name")
    plugin_stop = plugin_sub.add_parser("stop")
    plugin_stop.add_argument("name")
    plugin_info = plugin_sub.add_parser("info")
    plugin_info.add_argument("name")

    # config 命令
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_get = config_sub.add_parser("get")
    config_get.add_argument("key")
    config_set = config_sub.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_sub.add_parser("list")
    config_sub.add_parser("path")

    args = parser.parse_args()

    if args.command == "run":
        from bt_cli.commands.run import cmd_run
        cmd_run(args)
    elif args.command == "status":
        from bt_cli.commands.status import cmd_status
        cmd_status(args)
    elif args.command == "stop":
        from bt_cli.commands.stop import cmd_stop
        cmd_stop(args)
    elif args.command == "schedule":
        from bt_cli.commands.schedule import cmd_schedule
        cmd_schedule(args)
    elif args.command == "daemon":
        from bt_cli.commands.daemon import cmd_daemon
        cmd_daemon(args)
    elif args.command == "remote":
        from bt_cli.commands.remote import cmd_remote
        cmd_remote(args)
    elif args.command == "plugin":
        from bt_cli.commands.plugin import cmd_plugin
        cmd_plugin(args)
    elif args.command == "config":
        from bt_cli.commands.config import cmd_config
        cmd_config(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Step 2: Create bt_cli package and run command**

```python
# bt_cli/__init__.py
"""CLI 工具包"""
```

```python
# bt_cli/commands/__init__.py
"""CLI 命令包"""
```

```python
# bt_cli/commands/run.py
"""run 命令 — 运行行为树"""
import os
import sys


def cmd_run(args):
    """运行行为树"""
    if not os.path.isfile(args.tree_file):
        print(f"错误: 文件不存在: {args.tree_file}")
        sys.exit(3)

    if args.headless:
        from bt_core.headless import HeadlessRunner
        from config.settings_manager import get_settings_manager

        settings = get_settings_manager()

        # 应用 CLI 参数到配置
        if args.bus:
            settings.set("message_bus.enabled", True)
        if args.rest:
            settings.set("rest_server.enabled", True)
            settings.set("rest_server.host", args.rest_host)
            settings.set("rest_server.port", args.rest_port)
        if args.ws:
            settings.set("websocket_server.enabled", True)
            settings.set("websocket_server.host", args.ws_host)
            settings.set("websocket_server.port", args.ws_port)

        runner = HeadlessRunner()
        print(f"运行行为树: {args.tree_file} (Headless 模式)")
        if args.bus:
            print(f"  消息总线: 已启用")
        if args.rest:
            print(f"  REST API: {args.rest_host}:{args.rest_port}")
        if args.ws:
            print(f"  WebSocket: {args.ws_host}:{args.ws_port}")

        try:
            runner.run(args.tree_file, args.project)
        except KeyboardInterrupt:
            print("\n停止运行...")
            runner.stop()
    else:
        # GUI 模式 — 启动主应用
        from main import main as gui_main
        # 将 tree_file 传递给 GUI
        os.environ["AUTODOOR_BT_OPEN_FILE"] = os.path.abspath(args.tree_file)
        gui_main()
```

**Step 3: Commit**

```bash
git add cli.py bt_cli/
git commit -m "feat: add CLI entry point and run command"
```

---

## Task 9: status / stop / config 命令

**Files:**
- Create: `bt_cli/commands/status.py`
- Create: `bt_cli/commands/stop.py`
- Create: `bt_cli/commands/config.py`

**Step 1: Implement status command**

查询本地运行状态（通过读取 PID 文件和状态文件）或远程状态。

**Step 2: Implement stop command**

停止运行中的行为树（通过信号或 REST API）。

**Step 3: Implement config command**

读写 settings.json 配置项。

**Step 4: Commit**

---

## Task 10: schedule 命令 + 调度器

**Files:**
- Create: `bt_cli/scheduler.py`
- Create: `bt_cli/commands/schedule.py`

**Step 1: Implement scheduler**

基于 APScheduler 或自实现的轻量调度器，支持 cron 表达式和间隔执行。

**Step 2: Implement schedule command**

add/list/remove/enable/disable/run 子命令。

**Step 3: Commit**

---

## Task 11: daemon / remote / plugin 命令

**Files:**
- Create: `bt_cli/commands/daemon.py`
- Create: `bt_cli/commands/remote.py`
- Create: `bt_cli/commands/plugin.py`

**Step 1: Implement daemon command** — 启动/停止/重启/状态守护进程

**Step 2: Implement remote command** — 通过 requests 调用 REST API

**Step 3: Implement plugin command** — list/load/start/stop/info

**Step 4: Commit**

---

## Task 12: main.py CLI 入口 + HeadlessRunner 插件集成

**Files:**
- Modify: `main.py`
- Modify: `bt_core/headless.py`

**Step 1: Add CLI entry detection to main.py**

在 `main()` 函数开头添加 CLI 参数检测：
```python
if len(sys.argv) > 1 and sys.argv[1] in ("run", "schedule", "status", "stop", "daemon", "remote", "plugin", "config"):
    from cli import main as cli_main
    cli_main()
    return
```

**Step 2: Add PluginLoader support to HeadlessRunner**

在 `_start_service_layer()` 中添加插件加载：
```python
if settings.get("plugins.enabled", False):
    from bt_plugins.loader import PluginLoader
    plugin_loader = PluginLoader(context)
    # 扫描内置插件和用户插件
    plugin_loader.scan("bt_plugins/builtin")
    plugin_loader.scan("plugins")
    plugin_loader.load_all()
    plugin_loader.start_all()
```

**Step 3: Test end-to-end**

```bash
python cli.py run test_tree.json --headless --bus
```

**Step 4: Commit**

---

## 执行顺序

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5    (插件后端)
                                              ↓
Task 6 → Task 7                               (插件前端)
                                              ↓
Task 8 → Task 9 → Task 10 → Task 11 → Task 12 (CLI 工具)
```

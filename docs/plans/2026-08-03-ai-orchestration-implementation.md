# AI 编排自动化实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现基于 5 阶段流水线的 AI 行为树编排系统，替代旧的单次 prompt 生成方案。

**Architecture:** 分阶段流水线（意图分析→节点选型→VLM屏幕感知→JSON生成→试运行迭代），每阶段独立可测试、可回退。核心模块位于 `bt_cli/ai/`，CLI 命令位于 `bt_cli/commands/ai.py`，通过 `cli.py` 集中路由。LLM/VLM 使用通用 OpenAI 兼容 API 客户端，模型可自由配置。

**Tech Stack:** Python 3, requests（HTTP客户端）, PIL（截图处理）, pytest（测试）, argparse（CLI）

**设计文档:** `docs/plans/2026-08-03-ai-orchestration-redesign-design.md`

---

## 现有代码模式摘要

实现前必须了解的现有模式：

| 模式 | 关键文件 | 要点 |
|------|---------|------|
| CLI 命令 | `cli.py` + `bt_cli/commands/*.py` | argparse 集中定义，`_dispatch()` 延迟导入，每个命令导出 `cmd_xxx(args)` |
| 节点注册 | `bt_core/registry.py` | `NodeRegistry._node_types` 类级字典，`register()` / `list_types()` / `create_node()` |
| 节点基类 | `bt_core/nodes.py` | `Node.NODE_TYPE` 类属性，`to_dict()` / `from_dict()`，`config: NodeConfig` |
| 节点配置 | `bt_core/config.py` | `NodeConfig` dataclass，已知字段 + `extra` 字典，`get()` / `set()` / `get_int()` 等 |
| 序列化 | `bt_core/serializer.py` | `Serializer.serialize()` → 扁平 nodes 字典 + connections 列表，version "2.1" |
| 配置管理 | `config/settings_manager.py` | `SettingsManager` 单例，`DEFAULT_SETTINGS` 字典，`get("a.b.c")` 点号分隔 |
| 截图 | `bt_utils/screenshot.py` | `ScreenshotManager` 单例，`get_full_screenshot()` → PIL Image |
| 窗口截图 | `bt_utils/window_capture.py` | `WindowCapture.capture_by_title(title)` → PIL Image |
| 日志 | `bt_utils/log_manager.py` | `LogManager` 单例，`debug_print()` / `log_failure()` / `log_success()` |
| 退出码 | `bt_cli/errors.py` | `EXIT_SUCCESS` / `EXIT_GENERIC_ERROR` 等，`exit_with_code(code, msg)` |
| 测试 | `tests/conftest.py` | pytest，`sys.path.insert` 确保项目根在路径中 |

---

## Task 1: 添加 AI 配置项到 SettingsManager

**Files:**
- Modify: `config/settings_manager.py` (在 `DEFAULT_SETTINGS` 字典末尾添加 `"ai"` 配置段)
- Test: `tests/test_ai_config.py`

**Step 1: Write the failing test**

```python
# tests/test_ai_config.py
"""AI 配置项测试"""
import pytest


def test_ai_config_defaults():
    """验证 AI 配置默认值存在且结构正确"""
    from config.settings_manager import SettingsManager
    SettingsManager._instance = None  # 重置单例

    sm = SettingsManager(config_dir="/tmp/test_ai_config")
    
    assert sm.get("ai.enabled") == False
    assert sm.get("ai.llm.base_url") == "https://api.openai.com/v1"
    assert sm.get("ai.llm.model") == "gpt-4o"
    assert sm.get("ai.llm.timeout_ms") == 30000
    assert sm.get("ai.llm.max_tokens") == 4096
    assert sm.get("ai.vlm.base_url") == "https://api.openai.com/v1"
    assert sm.get("ai.vlm.model") == "gpt-4o"
    assert sm.get("ai.vlm.image_detail") == "high"
    assert sm.get("ai.iteration.max_rounds") == 3
    assert sm.get("ai.iteration.test_timeout_ms") == 30000


def test_ai_config_set_and_get():
    """验证 AI 配置可读写"""
    from config.settings_manager import SettingsManager
    SettingsManager._instance = None

    sm = SettingsManager(config_dir="/tmp/test_ai_config")
    sm.set("ai.llm.base_url", "http://localhost:11434/v1")
    sm.set("ai.llm.model", "qwen2.5")
    
    assert sm.get("ai.llm.base_url") == "http://localhost:11434/v1"
    assert sm.get("ai.llm.model") == "qwen2.5"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ai_config.py -v`
Expected: FAIL with `KeyError` or `None != expected`（`ai` 配置段不存在）

**Step 3: Add AI config to DEFAULT_SETTINGS**

在 `config/settings_manager.py` 的 `DEFAULT_SETTINGS` 字典中，`"schedules": {},` 之后添加：

```python
        # 定时调度配置
        "schedules": {},
        # AI 编排配置
        "ai": {
            "enabled": False,
            "llm": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o",
                "timeout_ms": 30000,
                "max_tokens": 4096,
            },
            "vlm": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o",
                "timeout_ms": 30000,
                "max_tokens": 4096,
                "image_detail": "high",
            },
            "iteration": {
                "max_rounds": 3,
                "test_timeout_ms": 30000,
            },
        },
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ai_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add config/settings_manager.py tests/test_ai_config.py
git commit -m "feat(ai): add AI orchestration config to DEFAULT_SETTINGS"
```

---

## Task 2: LLMClient — 通用 OpenAI 兼容 API 客户端

**Files:**
- Create: `bt_cli/ai/__init__.py`
- Create: `bt_cli/ai/llm_client.py`
- Test: `tests/test_llm_client.py`

**Step 1: Write the failing test**

```python
# tests/test_llm_client.py
"""LLMClient 测试"""
import pytest
import json
from unittest.mock import patch, MagicMock


def test_llm_client_chat_text():
    """测试文本对话请求"""
    from bt_cli.ai.llm_client import LLMClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {"message": {"role": "assistant", "content": "你好，我是AI助手"}}
        ],
        "usage": {"total_tokens": 50}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("bt_cli.ai.llm_client.requests.post", return_value=mock_response):
        client = LLMClient(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
        )
        result = client.chat(
            messages=[{"role": "user", "content": "你好"}],
        )

    assert result["content"] == "你好，我是AI助手"
    assert result["usage"]["total_tokens"] == 50
    assert result["model"] == "gpt-4o"


def test_llm_client_chat_with_image():
    """测试带图片的对话请求（VLM）"""
    from bt_cli.ai.llm_client import LLMClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {"message": {"role": "assistant", "content": '{"region": [100, 200, 300, 400]}'}}
        ],
        "usage": {"total_tokens": 100}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("bt_cli.ai.llm_client.requests.post", return_value=mock_response):
        client = LLMClient(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
        )
        result = client.chat_with_image(
            text_prompt="分析截图中的按钮位置",
            image_base64="iVBORw0KGgoAAAANSUhEUg==",
            image_detail="high",
        )

    assert "region" in result["content"]


def test_llm_client_api_error():
    """测试 API 错误处理"""
    from bt_cli.ai.llm_client import LLMClient, LLMClientError

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")

    with patch("bt_cli.ai.llm_client.requests.post", return_value=mock_response):
        client = LLMClient(
            base_url="https://api.openai.com/v1",
            api_key="bad-key",
            model="gpt-4o",
        )
        with pytest.raises(LLMClientError):
            client.chat(messages=[{"role": "user", "content": "test"}])


def test_llm_client_from_config():
    """测试从 SettingsManager 配置创建客户端"""
    from bt_cli.ai.llm_client import LLMClient
    from config.settings_manager import SettingsManager
    SettingsManager._instance = None

    SettingsManager(config_dir="/tmp/test_llm_config")
    SettingsManager._instance.set("ai.llm.base_url", "http://localhost:11434/v1")
    SettingsManager._instance.set("ai.llm.api_key", "test-key")
    SettingsManager._instance.set("ai.llm.model", "qwen2.5")

    client = LLMClient.from_config("llm")
    assert client.base_url == "http://localhost:11434/v1"
    assert client.api_key == "test-key"
    assert client.model == "qwen2.5"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# bt_cli/ai/__init__.py
"""AI 编排模块"""
```

```python
# bt_cli/ai/llm_client.py
"""通用 OpenAI 兼容 API 客户端

支持任意 OpenAI 兼容 API（OpenAI / Azure / 通义千问 / 本地 Ollama 等）。
只需配置 base_url + api_key + model 即可切换模型。
"""
import base64
import json
import requests
from typing import Any, Dict, List, Optional


class LLMClientError(Exception):
    """LLM 客户端错误"""
    pass


class LLMClient:
    """通用 LLM/VLM API 客户端（OpenAI 兼容协议）"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout_ms: int = 30000, max_tokens: int = 4096):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_ms = timeout_ms
        self.max_tokens = max_tokens

    @classmethod
    def from_config(cls, config_key: str = "llm") -> "LLMClient":
        """从 SettingsManager 配置创建客户端

        Args:
            config_key: "llm" 或 "vlm"，对应 ai.llm / ai.vlm 配置段
        """
        from config.settings_manager import get_settings_manager
        sm = get_settings_manager()

        return cls(
            base_url=sm.get(f"ai.{config_key}.base_url", "https://api.openai.com/v1"),
            api_key=sm.get(f"ai.{config_key}.api_key", ""),
            model=sm.get(f"ai.{config_key}.model", "gpt-4o"),
            timeout_ms=sm.get(f"ai.{config_key}.timeout_ms", 30000),
            max_tokens=sm.get(f"ai.{config_key}.max_tokens", 4096),
        )

    def chat(self, messages: List[Dict[str, Any]],
             temperature: float = 0.7,
             response_format: Optional[Dict] = None) -> Dict[str, Any]:
        """发送文本对话请求

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 温度参数
            response_format: 响应格式（如 {"type": "json_object"}）

        Returns:
            {"content": str, "model": str, "usage": dict, "raw": dict}
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = self._post("/chat/completions", payload)
        choice = resp["choices"][0]
        return {
            "content": choice["message"]["content"],
            "model": resp.get("model", self.model),
            "usage": resp.get("usage", {}),
            "raw": resp,
        }

    def chat_with_image(self, text_prompt: str, image_base64: str,
                        image_detail: str = "high",
                        system_prompt: str = "",
                        temperature: float = 0.3) -> Dict[str, Any]:
        """发送带图片的对话请求（VLM）

        Args:
            text_prompt: 文本提示
            image_base64: base64 编码的图片数据（不含 data:image/... 前缀）
            image_detail: 图片精度 "low" / "high" / "auto"
            system_prompt: 系统提示词
            temperature: 温度参数

        Returns:
            {"content": str, "model": str, "usage": dict, "raw": dict}
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": text_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": image_detail,
                    },
                },
            ],
        })

        return self.chat(messages, temperature=temperature)

    def _post(self, path: str, payload: dict) -> dict:
        """发送 POST 请求"""
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            resp = requests.post(
                url, json=payload, headers=headers,
                timeout=self.timeout_ms / 1000,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            raise LLMClientError(f"API 返回错误: {resp.status_code} {resp.text[:500]}") from e
        except requests.exceptions.ConnectionError as e:
            raise LLMClientError(f"无法连接到 API: {url}") from e
        except requests.exceptions.Timeout as e:
            raise LLMClientError(f"API 请求超时 ({self.timeout_ms}ms)") from e
        except Exception as e:
            raise LLMClientError(f"API 请求失败: {e}") from e
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add bt_cli/ai/__init__.py bt_cli/ai/llm_client.py tests/test_llm_client.py
git commit -m "feat(ai): add universal OpenAI-compatible LLM/VLM client"
```

---

## Task 3: NodeSpecExporter — 从 NodeRegistry 动态导出节点规格

**Files:**
- Create: `bt_cli/ai/node_spec_exporter.py`
- Test: `tests/test_node_spec_exporter.py`

**Step 1: Write the failing test**

```python
# tests/test_node_spec_exporter.py
"""NodeSpecExporter 测试"""
import pytest


def test_export_all_returns_registered_nodes():
    """验证导出所有已注册节点"""
    from bt_core.registry import register_all_nodes, NodeRegistry
    from bt_cli.ai.node_spec_exporter import NodeSpecExporter

    register_all_nodes()
    exporter = NodeSpecExporter()
    specs = exporter.export_all()

    # 核心节点必须存在
    assert "StartNode" in specs
    assert "SequenceNode" in specs
    assert "SelectorNode" in specs
    assert "MouseClickNode" in specs
    assert "DelayNode" in specs
    assert "OCRConditionNode" in specs
    assert "ImageConditionNode" in specs


def test_export_node_has_required_fields():
    """验证导出的节点规格包含必需字段"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_spec_exporter import NodeSpecExporter

    register_all_nodes()
    exporter = NodeSpecExporter()
    specs = exporter.export_all()

    start_spec = specs["StartNode"]
    assert "node_type" in start_spec
    assert "category" in start_spec
    assert "base_class" in start_spec
    assert "parameters" in start_spec
    assert start_spec["node_type"] == "StartNode"


def test_export_categorizes_nodes():
    """验证节点分类正确"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_spec_exporter import NodeSpecExporter

    register_all_nodes()
    exporter = NodeSpecExporter()
    specs = exporter.export_all()

    assert specs["SequenceNode"]["category"] == "composite"
    assert specs["MouseClickNode"]["category"] == "action"
    assert specs["OCRConditionNode"]["category"] == "condition"


def test_export_extract_parameters():
    """验证参数提取包含已知参数"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_spec_exporter import NodeSpecExporter

    register_all_nodes()
    exporter = NodeSpecExporter()
    specs = exporter.export_all()

    delay_spec = specs["DelayNode"]
    params = delay_spec["parameters"]
    # DelayNode 应包含 duration_ms 参数
    param_names = [p["name"] for p in params]
    assert "duration_ms" in param_names


def test_export_node_descriptions():
    """验证节点描述提取"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_spec_exporter import NodeSpecExporter

    register_all_nodes()
    exporter = NodeSpecExporter()
    specs = exporter.export_all()

    # 每个节点应有描述
    for node_type, spec in specs.items():
        assert "description" in spec
        assert isinstance(spec["description"], str)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_node_spec_exporter.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# bt_cli/ai/node_spec_exporter.py
"""从 NodeRegistry 动态导出节点完整规格

替代旧方案中写死在 prompt 中的节点清单。
新增节点或插件节点注册后，AI 自动获得新规格，无需手动更新。
"""
import inspect
from typing import Any, Dict, List, Type

from bt_core.registry import NodeRegistry
from bt_core.nodes import Node, CompositeNode, ConditionNode, ActionNode
from bt_core.config import NodeConfig


# 节点参数文档 — 每种节点类型的关键参数说明
# 从 AI_Tree_Generator_Prompt.md 迁移，但以代码形式维护
_NODE_PARAM_DOCS = {
    "StartNode": {
        "params": [
            {"name": "bind_window", "type": "bool", "default": False, "desc": "是否绑定窗口"},
            {"name": "window_title", "type": "string", "default": "", "desc": "窗口标题"},
            {"name": "window_pid", "type": "int", "default": 0, "desc": "窗口进程ID"},
        ],
        "desc": "行为树根节点，入口节点",
    },
    "SequenceNode": {
        "params": [
            {"name": "repeat_count", "type": "int", "default": 0, "desc": "重复次数（-1无限）"},
            {"name": "repeat_interval_ms", "type": "int", "default": 100, "desc": "重复间隔毫秒"},
            {"name": "childinterval", "type": "int", "default": 0, "desc": "子节点间隔毫秒"},
            {"name": "childinterval_random", "type": "int", "default": 0, "desc": "子节点间隔随机范围"},
            {"name": "continue_on_failure", "type": "bool", "default": False, "desc": "失败是否继续"},
        ],
        "desc": "顺序执行：全部成功才成功，任一失败则失败",
    },
    "SelectorNode": {
        "params": [
            {"name": "repeat_count", "type": "int", "default": 0, "desc": "重复次数（-1无限）"},
            {"name": "repeat_interval_ms", "type": "int", "default": 100, "desc": "重复间隔毫秒"},
            {"name": "childinterval", "type": "int", "default": 0, "desc": "子节点间隔毫秒"},
            {"name": "childinterval_random", "type": "int", "default": 0, "desc": "子节点间隔随机范围"},
        ],
        "desc": "选择执行：任一成功即成功，全部失败才失败",
    },
    "ParallelNode": {
        "params": [
            {"name": "success_policy", "type": "string", "default": "require_all",
             "desc": "成功策略：require_all/require_one"},
        ],
        "desc": "并行执行：同时执行所有子节点",
    },
    "RandomNode": {
        "params": [
            {"name": "success_policy", "type": "string", "default": "require_all", "desc": "成功策略"},
            {"name": "fully_random", "type": "bool", "default": False, "desc": "每次完全随机"},
        ],
        "desc": "随机执行：随机选择子节点",
    },
    "SubtreeNode": {
        "params": [
            {"name": "subtree_path", "type": "string", "default": "", "desc": "子树文件路径"},
            {"name": "blackboard_mode", "type": "string", "default": "shared", "desc": "黑板模式"},
            {"name": "namespace", "type": "string", "default": "", "desc": "命名空间"},
            {"name": "auto_reload", "type": "bool", "default": False, "desc": "自动重载"},
        ],
        "desc": "子树引用：加载外部行为树",
    },
    "KeyPressNode": {
        "params": [
            {"name": "key", "type": "string", "default": "", "desc": "按键名称"},
            {"name": "action", "type": "string", "default": "press_release",
             "desc": "动作：press/release/press_release"},
            {"name": "duration", "type": "int", "default": 50, "desc": "按下持续时间毫秒"},
            {"name": "duration_random", "type": "int", "default": 0, "desc": "持续时间随机范围"},
        ],
        "desc": "键盘按键",
    },
    "MouseClickNode": {
        "params": [
            {"name": "button", "type": "string", "default": "left",
             "desc": "按钮：left/right/middle"},
            {"name": "position", "type": "list", "default": [], "desc": "点击位置 [x,y]"},
            {"name": "use_blackboard", "type": "bool", "default": False,
             "desc": "使用黑板中最近检测到的位置"},
            {"name": "click_count", "type": "int", "default": 1, "desc": "点击次数"},
            {"name": "click_interval", "type": "int", "default": 50, "desc": "点击间隔毫秒"},
        ],
        "desc": "鼠标点击",
    },
    "MouseMoveNode": {
        "params": [
            {"name": "position", "type": "list", "default": [], "desc": "目标位置 [x,y]"},
            {"name": "use_blackboard", "type": "bool", "default": False, "desc": "使用黑板位置"},
            {"name": "relative", "type": "bool", "default": False, "desc": "相对移动"},
            {"name": "offset", "type": "list", "default": [0, 0], "desc": "偏移量"},
            {"name": "move_type", "type": "string", "default": "instant",
             "desc": "移动类型：instant/linear/smooth"},
            {"name": "move_duration", "type": "int", "default": 300, "desc": "移动持续时间毫秒"},
        ],
        "desc": "鼠标移动",
    },
    "MouseScrollNode": {
        "params": [
            {"name": "distance", "type": "int", "default": 100, "desc": "滚动距离"},
            {"name": "clicks", "type": "int", "default": 1, "desc": "滚动次数"},
            {"name": "direction", "type": "string", "default": "up", "desc": "方向：up/down"},
        ],
        "desc": "鼠标滚轮",
    },
    "DelayNode": {
        "params": [
            {"name": "duration_ms", "type": "int", "default": 1000, "desc": "延时毫秒"},
            {"name": "duration_random", "type": "int", "default": 0, "desc": "随机范围毫秒"},
        ],
        "desc": "延时等待",
    },
    "SetVariableNode": {
        "params": [
            {"name": "variable_name", "type": "string", "default": "", "desc": "变量名"},
            {"name": "variable_value", "type": "any", "default": "", "desc": "变量值"},
        ],
        "desc": "设置黑板变量",
    },
    "AlarmNode": {
        "params": [
            {"name": "sound_file", "type": "string", "default": "", "desc": "声音文件路径"},
            {"name": "loop", "type": "bool", "default": False, "desc": "循环播放"},
            {"name": "duration", "type": "int", "default": 3000, "desc": "播放时长毫秒"},
        ],
        "desc": "播放报警声音",
    },
    "ScriptNode": {
        "params": [
            {"name": "script_path", "type": "string", "default": "", "desc": "脚本文件路径"},
        ],
        "desc": "执行外部脚本",
    },
    "CodeNode": {
        "params": [
            {"name": "code_file", "type": "string", "default": "", "desc": "代码文件路径"},
        ],
        "desc": "执行代码文件",
    },
    "TextInputNode": {
        "params": [
            {"name": "input_mode", "type": "string", "default": "preset",
             "desc": "输入模式：preset/file/extract"},
            {"name": "text_content", "type": "string", "default": "", "desc": "输入内容"},
            {"name": "file_path", "type": "string", "default": "", "desc": "文件路径"},
            {"name": "position", "type": "list", "default": [], "desc": "输入位置 [x,y]"},
        ],
        "desc": "文本输入",
    },
    "OCRConditionNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "检测区域 [x1,y1,x2,y2]"},
            {"name": "keywords", "type": "string", "default": "", "desc": "检测关键词"},
            {"name": "language", "type": "string", "default": "ch", "desc": "识别语言"},
            {"name": "preprocess_mode", "type": "string", "default": "default",
             "desc": "预处理模式：default/complex_color/adaptive/auto_tune"},
        ],
        "desc": "OCR识别文字条件节点",
    },
    "ImageConditionNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "检测区域 [x1,y1,x2,y2]"},
            {"name": "template_path", "type": "string", "default": "", "desc": "模板图片路径"},
            {"name": "threshold", "type": "int", "default": 80, "desc": "匹配阈值%（0-100）"},
        ],
        "desc": "图像匹配条件节点",
    },
    "ColorConditionNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "检测区域 [x1,y1,x2,y2]"},
            {"name": "target_color", "type": "string", "default": "", "desc": "目标颜色 #RRGGBB"},
            {"name": "tolerance", "type": "int", "default": 30, "desc": "颜色容差"},
            {"name": "min_pixels", "type": "int", "default": 10, "desc": "最小像素数"},
        ],
        "desc": "颜色检测条件节点",
    },
    "NumberConditionNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "检测区域"},
            {"name": "extract_mode", "type": "string", "default": "ocr", "desc": "提取模式"},
            {"name": "compare_mode", "type": "string", "default": ">",
             "desc": "比较模式：>/<&gt;/<=/==/!="},
            {"name": "threshold", "type": "int", "default": 0, "desc": "阈值"},
            {"name": "value_key", "type": "string", "default": "", "desc": "黑板变量键名"},
        ],
        "desc": "数字比较条件节点",
    },
    "VariableConditionNode": {
        "params": [
            {"name": "variable_name", "type": "string", "default": "", "desc": "变量名"},
            {"name": "operator", "type": "string", "default": "==",
             "desc": "操作符：>/<&gt;/==/!=/contains等"},
            {"name": "target_value", "type": "any", "default": "", "desc": "目标值"},
        ],
        "desc": "变量判断条件节点",
    },
    "TextExtractNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "提取区域"},
            {"name": "extract_mode", "type": "string", "default": "ocr", "desc": "提取模式"},
            {"name": "keywords", "type": "string", "default": "", "desc": "关键词"},
            {"name": "output_key", "type": "string", "default": "", "desc": "输出黑板键名"},
            {"name": "save_all_text", "type": "bool", "default": False, "desc": "保存全部文本"},
        ],
        "desc": "文本提取节点",
    },
    "HTTPRequestNode": {
        "params": [
            {"name": "url", "type": "string", "default": "", "desc": "请求URL"},
            {"name": "method", "type": "string", "default": "GET", "desc": "HTTP方法"},
            {"name": "headers", "type": "dict", "default": {}, "desc": "请求头"},
            {"name": "body", "type": "string", "default": "", "desc": "请求体"},
        ],
        "desc": "HTTP请求节点",
    },
    "MessagePublishNode": {
        "params": [
            {"name": "topic", "type": "string", "default": "", "desc": "消息主题"},
            {"name": "data", "type": "any", "default": "", "desc": "消息数据"},
        ],
        "desc": "消息发布节点",
    },
    "MessageSubscribeNode": {
        "params": [
            {"name": "topic", "type": "string", "default": "", "desc": "订阅主题"},
        ],
        "desc": "消息订阅节点",
    },
}

# 装饰参数（条件节点通用）
_CONDITION_DECORATOR_PARAMS = [
    {"name": "invert", "type": "bool", "default": False, "desc": "结果取反"},
    {"name": "retry_count", "type": "int", "default": 3, "desc": "失败重试次数（-1无限）"},
    {"name": "timeout_ms", "type": "int", "default": 10000, "desc": "超时毫秒（0不限）"},
    {"name": "check_interval_ms", "type": "int", "default": 500, "desc": "检测间隔毫秒"},
]

# 动作节点通用装饰参数
_ACTION_DECORATOR_PARAMS = [
    {"name": "repeat_count", "type": "int", "default": 0, "desc": "重复次数（-1无限）"},
    {"name": "repeat_interval_ms", "type": "int", "default": 100, "desc": "重复间隔毫秒"},
    {"name": "repeat_interval_ms_random", "type": "int", "default": 0, "desc": "间隔随机范围"},
    {"name": "timeout_ms", "type": "int", "default": 0, "desc": "超时毫秒（0不限）"},
]


class NodeSpecExporter:
    """从 NodeRegistry 动态导出节点完整规格"""

    def export_all(self) -> Dict[str, dict]:
        """遍历所有注册节点，导出真实参数规格

        Returns:
            {node_type: {node_type, category, base_class, parameters, description, is_async}}
        """
        specs = {}
        for node_type, node_class in NodeRegistry.list_types().items():
            specs[node_type] = self.export_one(node_type, node_class)
        return specs

    def export_one(self, node_type: str, node_class: Type[Node]) -> dict:
        """导出单个节点规格"""
        category = self._get_category(node_class)
        base_class = self._get_base_class(node_class)

        # 从文档表获取参数
        param_docs = _NODE_PARAM_DOCS.get(node_type, {})
        parameters = list(param_docs.get("params", []))

        # 条件节点追加装饰参数
        if category == "condition":
            parameters = parameters + _CONDITION_DECORATOR_PARAMS

        # 动作节点追加装饰参数
        if category == "action":
            parameters = parameters + _ACTION_DECORATOR_PARAMS

        return {
            "node_type": node_type,
            "category": category,
            "base_class": base_class,
            "parameters": parameters,
            "description": param_docs.get("desc", node_class.__doc__ or ""),
            "is_async": getattr(node_class, "_is_async", False),
        }

    def _get_category(self, node_class: Type[Node]) -> str:
        """获取节点分类"""
        if issubclass(node_class, CompositeNode):
            return "composite"
        if issubclass(node_class, ConditionNode):
            return "condition"
        if issubclass(node_class, ActionNode):
            return "action"
        return "other"

    def _get_base_class(self, node_class: Type[Node]) -> str:
        """获取基类名"""
        for base in (CompositeNode, ConditionNode, ActionNode):
            if issubclass(node_class, base):
                return base.__name__
        return "Node"

    def export_for_prompt(self) -> str:
        """导出为 LLM 可读的文本格式"""
        specs = self.export_all()
        lines = []
        for category in ("composite", "condition", "action", "other"):
            cat_nodes = {k: v for k, v in specs.items() if v["category"] == category}
            if not cat_nodes:
                continue
            lines.append(f"\n### {category.upper()} 节点\n")
            for node_type, spec in cat_nodes.items():
                lines.append(f"**{node_type}**: {spec['description']}")
                if spec["parameters"]:
                    param_strs = []
                    for p in spec["parameters"]:
                        default = f'="{p["default"]}"' if isinstance(p["default"], str) else f"={p['default']}"
                        param_strs.append(f'{p["name"]}{default}({p["desc"]})')
                    lines.append(f"  参数: {', '.join(param_strs)}")
                lines.append("")
        return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_node_spec_exporter.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add bt_cli/ai/node_spec_exporter.py tests/test_node_spec_exporter.py
git commit -m "feat(ai): add NodeSpecExporter for dynamic node spec export"
```

---

## Task 4: IntentAnalyzer — 阶段①意图分析

**Files:**
- Create: `bt_cli/ai/prompts/__init__.py`
- Create: `bt_cli/ai/prompts/intent_analysis.md`
- Create: `bt_cli/ai/intent_analyzer.py`
- Test: `tests/test_intent_analyzer.py`

**Step 1: Write the failing test**

```python
# tests/test_intent_analyzer.py
"""IntentAnalyzer 测试"""
import pytest
import json
from unittest.mock import patch, MagicMock


def test_analyze_returns_valid_plan():
    """测试意图分析返回有效的任务计划"""
    from bt_cli.ai.intent_analyzer import IntentAnalyzer

    mock_llm_response = {
        "content": json.dumps({
            "task_summary": "定时检测登录按钮并点击",
            "loop": {"enabled": True, "interval_ms": 60000, "max_iterations": -1},
            "phases": [
                {"phase": "detect", "method": "image_or_ocr", "target_description": "登录按钮",
                 "on_success": "proceed_to_click"},
                {"phase": "act", "action": "click", "position_source": "from_detection",
                 "on_complete": "loop_back"}
            ],
            "window": {"bind": False, "title": "", "pid": None}
        }, ensure_ascii=False),
        "model": "gpt-4o",
        "usage": {"total_tokens": 100},
    }

    with patch("bt_cli.ai.intent_analyzer.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = mock_llm_response
        mock_client_cls.from_config.return_value = mock_client

        analyzer = IntentAnalyzer()
        result = analyzer.analyze("每分钟检查登录按钮并点击")

    assert result["task_summary"] == "定时检测登录按钮并点击"
    assert result["loop"]["enabled"] == True
    assert result["loop"]["interval_ms"] == 60000
    assert len(result["phases"]) == 2
    assert result["phases"][0]["phase"] == "detect"
    assert result["phases"][1]["phase"] == "act"


def test_analyze_handles_llm_error():
    """测试 LLM 错误处理"""
    from bt_cli.ai.intent_analyzer import IntentAnalyzer, IntentAnalysisError

    with patch("bt_cli.ai.intent_analyzer.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("API error")
        mock_client_cls.from_config.return_value = mock_client

        analyzer = IntentAnalyzer()
        with pytest.raises(IntentAnalysisError):
            analyzer.analyze("测试描述")


def test_analyze_handles_invalid_json():
    """测试无效 JSON 响应处理"""
    from bt_cli.ai.intent_analyzer import IntentAnalyzer, IntentAnalysisError

    mock_llm_response = {
        "content": "这不是JSON格式的回复",
        "model": "gpt-4o",
        "usage": {},
    }

    with patch("bt_cli.ai.intent_analyzer.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = mock_llm_response
        mock_client_cls.from_config.return_value = mock_client

        analyzer = IntentAnalyzer()
        with pytest.raises(IntentAnalysisError):
            analyzer.analyze("测试描述")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_intent_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write the prompt template**

```python
# bt_cli/ai/prompts/__init__.py
"""AI Prompt 模板"""
```

```markdown
<!-- bt_cli/ai/prompts/intent_analysis.md -->
你是行为树自动化任务分析专家。用户会用自然语言描述一个自动化需求，你需要将其解析为结构化的任务计划。

## 输出格式

你必须输出严格的 JSON，包含以下字段：

```json
{
  "task_summary": "一句话概述任务目标",
  "loop": {
    "enabled": true,
    "interval_ms": 60000,
    "max_iterations": -1
  },
  "phases": [
    {
      "phase": "detect",
      "method": "image_or_ocr|color|number|variable",
      "target_description": "检测目标的自然语言描述",
      "on_success": "proceed_to_next"
    },
    {
      "phase": "act",
      "action": "click|keypress|scroll|delay|input_text|set_variable|alarm|script",
      "position_source": "from_detection|fixed|blackboard",
      "on_complete": "loop_back|finish"
    }
  ],
  "window": {
    "bind": false,
    "title": "",
    "pid": null
  }
}
```

## 字段说明

- **task_summary**: 简洁概述任务目标
- **loop**: 循环配置
  - enabled: 是否循环
  - interval_ms: 循环间隔（毫秒）
  - max_iterations: 最大迭代次数（-1无限）
- **phases**: 任务阶段列表，按执行顺序排列
  - phase: "detect"（检测）或 "act"（动作）
  - method（detect阶段）: 检测方法
  - action（act阶段）: 动作类型
  - position_source: 位置来源
  - on_success/on_complete: 成功/完成后的行为
- **window**: 窗口绑定配置

## 分析规则

1. 根据用户描述识别检测目标和动作
2. 如果用户提到"每隔"、"定时"、"循环"等词，设置 loop.enabled = true
3. 检测方法优先级：image_or_ocr > color > number
4. 如果用户提到特定窗口，设置 window.bind = true 并填写 title
5. 不要在计划中包含具体坐标、颜色值等需要屏幕采集的参数

## 重要

- 只输出 JSON，不要输出其他内容
- JSON 必须可被 json.loads 解析
- 不要使用 markdown 代码块包裹
```

**Step 4: Write minimal implementation**

```python
# bt_cli/ai/intent_analyzer.py
"""阶段① 意图分析 — 将自然语言描述解析为结构化任务计划"""
import json
import os
from typing import Dict, Any

from bt_cli.ai.llm_client import LLMClient


class IntentAnalysisError(Exception):
    """意图分析错误"""
    pass


class IntentAnalyzer:
    """意图分析器

    将用户自然语言描述解析为结构化任务计划（plan.json）。
    """

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "intent_analysis.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client

    def analyze(self, description: str) -> Dict[str, Any]:
        """分析用户描述，输出任务计划

        Args:
            description: 用户的自然语言任务描述

        Returns:
            结构化任务计划字典（plan.json 格式）

        Raises:
            IntentAnalysisError: 分析失败
        """
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")

        system_prompt = self._load_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": description},
        ]

        try:
            result = self._llm.chat(
                messages,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise IntentAnalysisError(f"LLM 请求失败: {e}") from e

        try:
            plan = json.loads(result["content"])
        except json.JSONDecodeError as e:
            raise IntentAnalysisError(f"LLM 返回的 JSON 无效: {e}\n原始内容: {result['content'][:500]}") from e

        if not self._validate_plan(plan):
            raise IntentAnalysisError(f"任务计划结构不完整: {plan}")

        return plan

    def _load_prompt(self) -> str:
        """加载系统提示词"""
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def _validate_plan(self, plan: dict) -> bool:
        """验证任务计划结构"""
        required_keys = {"task_summary", "loop", "phases", "window"}
        if not required_keys.issubset(plan.keys()):
            return False
        if not isinstance(plan["phases"], list) or len(plan["phases"]) == 0:
            return False
        return True
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_intent_analyzer.py -v`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add bt_cli/ai/prompts/__init__.py bt_cli/ai/prompts/intent_analysis.md \
        bt_cli/ai/intent_analyzer.py tests/test_intent_analyzer.py
git commit -m "feat(ai): add IntentAnalyzer for phase 1 intent analysis"
```

---

## Task 5: NodeSelector — 阶段②节点选型

**Files:**
- Create: `bt_cli/ai/prompts/node_selection.md`
- Create: `bt_cli/ai/node_selector.py`
- Test: `tests/test_node_selector.py`

**Step 1: Write the failing test**

```python
# tests/test_node_selector.py
"""NodeSelector 测试"""
import pytest
import json
from unittest.mock import patch, MagicMock


def test_select_returns_valid_structure():
    """测试节点选型返回有效的节点结构"""
    from bt_cli.ai.node_selector import NodeSelector

    mock_llm_response = {
        "content": json.dumps({
            "nodes": [
                {"id": "node_start", "type": "StartNode",
                 "config": {"bind_window": False, "window_title": ""},
                 "children": ["node_loop"]},
                {"id": "node_loop", "type": "SequenceNode",
                 "config": {"repeat_count": -1, "repeat_interval_ms": 60000},
                 "children": ["node_detect", "node_delay"]},
                {"id": "node_detect", "type": "ImageConditionNode",
                 "config": {"region": [], "template_path": "", "threshold": 80},
                 "children": ["node_click"],
                 "empty_params": ["region", "template_path"]},
                {"id": "node_click", "type": "MouseClickNode",
                 "config": {"use_blackboard": True, "button": "left"},
                 "children": []},
                {"id": "node_delay", "type": "DelayNode",
                 "config": {"duration_ms": 60000},
                 "children": []}
            ]
        }, ensure_ascii=False),
        "model": "gpt-4o",
        "usage": {},
    }

    plan = {
        "task_summary": "定时检测登录按钮并点击",
        "loop": {"enabled": True, "interval_ms": 60000, "max_iterations": -1},
        "phases": [
            {"phase": "detect", "method": "image_or_ocr", "target_description": "登录按钮"},
            {"phase": "act", "action": "click", "position_source": "from_detection"}
        ],
        "window": {"bind": False, "title": "", "pid": None}
    }

    with patch("bt_cli.ai.node_selector.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = mock_llm_response
        mock_client_cls.from_config.return_value = mock_client

        selector = NodeSelector()
        result = selector.select(plan)

    assert "nodes" in result
    assert len(result["nodes"]) == 5
    assert result["nodes"][0]["type"] == "StartNode"
    assert result["nodes"][2]["empty_params"] == ["region", "template_path"]


def test_select_validates_node_types():
    """测试选型结果中的节点类型都存在于 Registry"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_selector import NodeSelector, NodeSelectionError

    register_all_nodes()

    mock_llm_response = {
        "content": json.dumps({
            "nodes": [
                {"id": "node_start", "type": "NonExistentNode",
                 "config": {}, "children": []}
            ]
        }),
        "model": "gpt-4o",
        "usage": {},
    }

    plan = {"task_summary": "test", "loop": {"enabled": False}, "phases": [], "window": {}}

    with patch("bt_cli.ai.node_selector.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = mock_llm_response
        mock_client_cls.from_config.return_value = mock_client

        selector = NodeSelector()
        with pytest.raises(NodeSelectionError):
            selector.select(plan)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_node_selector.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write the prompt template**

```markdown
<!-- bt_cli/ai/prompts/node_selection.md -->
你是行为树节点选型专家。根据任务计划和可用节点规格，选择合适的节点并设计连接结构。

## 输入

你会收到：
1. 任务计划（JSON）：包含任务摘要、循环配置、阶段列表、窗口配置
2. 可用节点规格：所有可用节点类型及其参数

## 输出格式

输出严格的 JSON：

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
    }
  ]
}
```

## 选型规则

1. **根节点**：必须是 StartNode
2. **循环结构**：如果 loop.enabled=true，使用 SequenceNode 包裹，设置 repeat_count=-1
3. **检测阶段**：
   - image_or_ocr → ImageConditionNode 或 OCRConditionNode
   - color → ColorConditionNode
   - number → NumberConditionNode
   - variable → VariableConditionNode
4. **动作阶段**：
   - click → MouseClickNode（如 position_source=from_detection 则 use_blackboard=true）
   - keypress → KeyPressNode
   - scroll → MouseScrollNode
   - delay → DelayNode
   - input_text → TextInputNode
   - set_variable → SetVariableNode
   - alarm → AlarmNode
5. **条件节点必须有子节点**：检测成功后执行的动作作为子节点
6. **空参数标记**：需要屏幕采集的参数（region, position, template_path, keywords, target_color 等）在 config 中留空（[]或""），并在 empty_params 中列出

## 重要

- 只输出 JSON
- 节点 id 必须唯一
- children 中的 id 必须在 nodes 中存在
- 不要输出 markdown 代码块
```

**Step 4: Write minimal implementation**

```python
# bt_cli/ai/node_selector.py
"""阶段② 节点选型 — 根据任务计划和节点规格选择节点并设计结构"""
import json
import os
from typing import Dict, Any, List

from bt_cli.ai.llm_client import LLMClient
from bt_cli.ai.node_spec_exporter import NodeSpecExporter
from bt_core.registry import NodeRegistry


class NodeSelectionError(Exception):
    """节点选型错误"""
    pass


class NodeSelector:
    """节点选型器

    根据任务计划 + 动态导出的节点规格，选择节点并设计连接结构。
    """

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "node_selection.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client
        self._spec_exporter = NodeSpecExporter()

    def select(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """根据任务计划选择节点

        Args:
            plan: 任务计划（plan.json 格式）

        Returns:
            节点结构（structure.json 格式）

        Raises:
            NodeSelectionError: 选型失败
        """
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")

        system_prompt = self._load_prompt()
        node_specs = self._spec_exporter.export_all()
        spec_text = self._spec_exporter.export_for_prompt()

        user_content = (
            f"## 任务计划\n```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## 可用节点规格\n{spec_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            result = self._llm.chat(
                messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise NodeSelectionError(f"LLM 请求失败: {e}") from e

        try:
            structure = json.loads(result["content"])
        except json.JSONDecodeError as e:
            raise NodeSelectionError(f"LLM 返回的 JSON 无效: {e}") from e

        if not self._validate_structure(structure):
            raise NodeSelectionError(f"节点结构无效: {structure}")

        return structure

    def _load_prompt(self) -> str:
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def _validate_structure(self, structure: dict) -> bool:
        """验证节点结构基本完整性"""
        if "nodes" not in structure or not isinstance(structure["nodes"], list):
            return False
        if len(structure["nodes"]) == 0:
            return False

        # 检查根节点是 StartNode
        root = structure["nodes"][0]
        if root.get("type") != "StartNode":
            return False

        # 检查节点类型存在
        registered = NodeRegistry.list_types()
        all_ids = {n["id"] for n in structure["nodes"]}
        for node in structure["nodes"]:
            if node["type"] not in registered:
                return False
            # 检查 children 引用有效
            for child_id in node.get("children", []):
                if child_id not in all_ids:
                    return False

        return True
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_node_selector.py -v`
Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add bt_cli/ai/prompts/node_selection.md bt_cli/ai/node_selector.py \
        tests/test_node_selector.py
git commit -m "feat(ai): add NodeSelector for phase 2 node selection"
```

---

## Task 6: AI CLI 命令基础结构 + `ai nodes` 命令

**Files:**
- Create: `bt_cli/commands/ai.py`
- Modify: `cli.py`（添加 ai 命令组）
- Test: `tests/test_ai_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_ai_cli.py
"""AI CLI 命令测试"""
import pytest
import subprocess
import sys
import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_ai_nodes_command():
    """测试 ai nodes 命令输出节点规格"""
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "cli.py"), "ai", "nodes"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
        timeout=30,
    )
    assert result.returncode == 0
    assert "StartNode" in result.stdout
    assert "SequenceNode" in result.stdout
    assert "MouseClickNode" in result.stdout
    assert "OCRConditionNode" in result.stdout


def test_ai_command_help():
    """测试 ai 命令帮助"""
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "cli.py"), "ai", "--help"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
        timeout=10,
    )
    assert result.returncode == 0
    assert "plan" in result.stdout
    assert "select" in result.stdout
    assert "nodes" in result.stdout


def test_ai_plan_command_no_api_key():
    """测试 ai plan 命令在未配置 API Key 时的错误提示"""
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "cli.py"),
         "ai", "plan", "测试描述"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
        timeout=30,
    )
    # 未配置 API Key 应返回错误码
    assert result.returncode != 0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ai_cli.py -v`
Expected: FAIL（ai 命令不存在）

**Step 3: Write the AI command module**

```python
# bt_cli/commands/ai.py
"""ai 命令组 — AI 编排自动化"""
import sys
import os
import json

from bt_cli.errors import exit_with_code, EXIT_SUCCESS, EXIT_CONFIG_ERROR, EXIT_GENERIC_ERROR


def cmd_ai(args):
    """AI 编排命令入口"""
    action = args.ai_action

    if action is None:
        print("请指定操作: plan/select/nodes/scan/generate/validate/test/refine/create")
        sys.exit(1)

    if action == "nodes":
        _cmd_nodes(args)
    elif action == "plan":
        _cmd_plan(args)
    elif action == "select":
        _cmd_select(args)
    elif action == "scan":
        _cmd_scan(args)
    elif action == "generate":
        _cmd_generate(args)
    elif action == "validate":
        _cmd_validate(args)
    elif action == "test":
        _cmd_test(args)
    elif action == "refine":
        _cmd_refine(args)
    elif action == "create":
        _cmd_create(args)
    else:
        print(f"未知操作: {action}")
        sys.exit(1)


def _cmd_nodes(args):
    """列出所有可用节点规格"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_spec_exporter import NodeSpecExporter

    register_all_nodes()
    exporter = NodeSpecExporter()
    specs = exporter.export_all()

    # 按分类输出
    categories = {"composite": "复合节点", "condition": "条件节点",
                  "action": "动作节点", "other": "其他节点"}

    for cat, cat_name in categories.items():
        cat_nodes = {k: v for k, v in specs.items() if v["category"] == cat}
        if not cat_nodes:
            continue
        print(f"\n{'='*60}")
        print(f"  {cat_name}（{len(cat_nodes)} 个）")
        print(f"{'='*60}")
        for node_type, spec in cat_nodes.items():
            print(f"\n  [{node_type}]")
            print(f"    描述: {spec['description']}")
            print(f"    基类: {spec['base_class']}")
            if spec["parameters"]:
                print(f"    参数:")
                for p in spec["parameters"]:
                    default = p["default"]
                    if isinstance(default, str):
                        default_str = f'"{default}"' if default else '""'
                    else:
                        default_str = str(default)
                    print(f"      {p['name']} ({p['type']}) = {default_str}  — {p['desc']}")

    print(f"\n共 {len(specs)} 个节点")


def _cmd_plan(args):
    """阶段① 意图分析"""
    from config.settings_manager import get_settings_manager
    from bt_cli.ai.intent_analyzer import IntentAnalyzer, IntentAnalysisError

    sm = get_settings_manager()
    api_key = sm.get("ai.llm.api_key", "")
    if not api_key:
        exit_with_code(
            EXIT_CONFIG_ERROR,
            "错误: 未配置 AI API Key\n"
            "请运行: autodoor-bt config set ai.llm.api_key \"your-key\""
        )

    description = args.description
    print(f"正在分析任务描述: {description}")

    try:
        analyzer = IntentAnalyzer()
        plan = analyzer.analyze(description)
    except IntentAnalysisError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"意图分析失败: {e}")

    # 保存到 .ai/ 目录
    ai_dir = _ensure_ai_dir()
    output_path = os.path.join(ai_dir, "plan.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    print(f"\n任务计划已生成: {output_path}")
    print(f"  任务概述: {plan['task_summary']}")
    print(f"  循环: {'是' if plan['loop']['enabled'] else '否'}"
          + (f" (间隔 {plan['loop']['interval_ms']}ms)" if plan['loop']['enabled'] else ""))
    print(f"  阶段数: {len(plan['phases'])}")
    print(f"\n确认后运行: autodoor-bt ai select plan.json")


def _cmd_select(args):
    """阶段② 节点选型"""
    from config.settings_manager import get_settings_manager
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_selector import NodeSelector, NodeSelectionError

    sm = get_settings_manager()
    api_key = sm.get("ai.llm.api_key", "")
    if not api_key:
        exit_with_code(
            EXIT_CONFIG_ERROR,
            "错误: 未配置 AI API Key\n"
            "请运行: autodoor-bt config set ai.llm.api_key \"your-key\""
        )

    plan_path = args.plan_file
    if not os.path.exists(plan_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {plan_path}")

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    register_all_nodes()
    print("正在进行节点选型...")

    try:
        selector = NodeSelector()
        structure = selector.select(plan)
    except NodeSelectionError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"节点选型失败: {e}")

    # 保存
    ai_dir = _ensure_ai_dir()
    output_path = os.path.join(ai_dir, "structure.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    print(f"\n节点结构已生成: {output_path}")
    print(f"  节点数: {len(structure['nodes'])}")
    for node in structure["nodes"]:
        empty = node.get("empty_params", [])
        empty_str = f" [待填充: {', '.join(empty)}]" if empty else ""
        print(f"    {node['id']} ({node['type']}){empty_str}")
    print(f"\n确认后运行: autodoor-bt ai scan structure.json")


def _cmd_scan(args):
    """阶段③ VLM 屏幕感知"""
    exit_with_code(EXIT_GENERIC_ERROR, "VLM 屏幕感知功能将在第二阶段实现")


def _cmd_generate(args):
    """阶段④ 生成 JSON"""
    exit_with_code(EXIT_GENERIC_ERROR, "JSON 生成功能将在第二阶段实现")


def _cmd_validate(args):
    """校验 JSON 结构"""
    exit_with_code(EXIT_GENERIC_ERROR, "校验功能将在第二阶段实现")


def _cmd_test(args):
    """阶段⑤ 试运行"""
    exit_with_code(EXIT_GENERIC_ERROR, "试运行功能将在第三阶段实现")


def _cmd_refine(args):
    """阶段⑤ 迭代修正"""
    exit_with_code(EXIT_GENERIC_ERROR, "迭代修正功能将在第三阶段实现")


def _cmd_create(args):
    """完整创建流程"""
    exit_with_code(EXIT_GENERIC_ERROR, "完整流程将在所有阶段实现后集成")


def _ensure_ai_dir() -> str:
    """确保 .ai/ 目录存在"""
    ai_dir = os.path.join(os.getcwd(), ".ai")
    os.makedirs(ai_dir, exist_ok=True)
    return ai_dir
```

**Step 4: Add ai command to cli.py**

在 `cli.py` 的 `config` 命令定义之后、`args = parser.parse_args()` 之前添加：

```python
    # ai 命令
    ai_parser = subparsers.add_parser("ai", help="AI 编排自动化")
    ai_sub = ai_parser.add_subparsers(dest="ai_action")

    ai_plan = ai_sub.add_parser("plan", help="阶段①: 意图分析")
    ai_plan.add_argument("description", help="任务描述")

    ai_select = ai_sub.add_parser("select", help="阶段②: 节点选型")
    ai_select.add_argument("plan_file", help="plan.json 文件路径")

    ai_scan = ai_sub.add_parser("scan", help="阶段③: VLM屏幕感知")
    ai_scan.add_argument("structure_file", help="structure.json 文件路径")

    ai_generate = ai_sub.add_parser("generate", help="阶段④: 生成JSON")
    ai_generate.add_argument("structure_file", help="structure_filled.json 文件路径")

    ai_validate = ai_sub.add_parser("validate", help="校验JSON结构")
    ai_validate.add_argument("tree_file", help="tree.json 文件路径")

    ai_test = ai_sub.add_parser("test", help="阶段⑤: 试运行")
    ai_test.add_argument("tree_file", help="tree.json 文件路径")

    ai_refine = ai_sub.add_parser("refine", help="阶段⑤: 迭代修正")
    ai_refine.add_argument("tree_file", help="tree.json 文件路径")

    ai_nodes = ai_sub.add_parser("nodes", help="列出可用节点规格")

    ai_create = ai_sub.add_parser("create", help="完整创建流程")
    ai_create.add_argument("description", help="任务描述")
```

在 `_dispatch()` 函数的 `elif cmd == "config":` 之后添加：

```python
    elif cmd == "ai":
        from bt_cli.commands.ai import cmd_ai
        cmd_ai(args)
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_ai_cli.py -v`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add bt_cli/commands/ai.py cli.py tests/test_ai_cli.py
git commit -m "feat(ai): add AI CLI command group with plan/select/nodes commands"
```

---

## Task 7: VLMAnalyzer — 阶段③屏幕感知

**Files:**
- Create: `bt_cli/ai/prompts/vlm_analysis.md`
- Create: `bt_cli/ai/vlm_analyzer.py`
- Test: `tests/test_vlm_analyzer.py`

**Step 1: Write the failing test**

```python
# tests/test_vlm_analyzer.py
"""VLMAnalyzer 测试"""
import pytest
import json
import base64
from unittest.mock import patch, MagicMock


def test_analyze_returns_fill_suggestions():
    """测试 VLM 分析返回参数填充建议"""
    from bt_cli.ai.vlm_analyzer import VLMAnalyzer

    mock_vlm_response = {
        "content": json.dumps({
            "suggestions": [
                {
                    "node_id": "node_detect",
                    "param": "region",
                    "suggested_value": [120, 300, 200, 340],
                    "confidence": 0.95,
                    "note": "检测到蓝色登录按钮"
                },
                {
                    "node_id": "node_click",
                    "param": "position",
                    "suggested_value": [160, 320],
                    "confidence": 0.90,
                    "note": "按钮中心位置"
                }
            ]
        }, ensure_ascii=False),
        "model": "gpt-4o",
        "usage": {},
    }

    structure = {
        "nodes": [
            {"id": "node_detect", "type": "ImageConditionNode",
             "config": {"region": [], "template_path": ""},
             "children": ["node_click"],
             "empty_params": ["region", "template_path"]},
            {"id": "node_click", "type": "MouseClickNode",
             "config": {"position": [], "use_blackboard": True},
             "children": [],
             "empty_params": ["position"]},
        ]
    }

    with patch("bt_cli.ai.vlm_analyzer.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat_with_image.return_value = mock_vlm_response
        mock_client_cls.from_config.return_value = mock_client

        analyzer = VLMAnalyzer()
        result = analyzer.analyze(
            screenshot_path="/tmp/test_screenshot.png",
            structure=structure,
            task_context="定时检测登录按钮并点击",
        )

    assert len(result) == 2
    assert result[0]["node_id"] == "node_detect"
    assert result[0]["param"] == "region"
    assert result[0]["suggested_value"] == [120, 300, 200, 340]
    assert result[0]["confidence"] == 0.95


def test_fill_structure_applies_suggestions():
    """测试将建议值填入节点结构"""
    from bt_cli.ai.vlm_analyzer import VLMAnalyzer

    analyzer = VLMAnalyzer()

    structure = {
        "nodes": [
            {"id": "node_detect", "type": "ImageConditionNode",
             "config": {"region": [], "template_path": ""},
             "children": ["node_click"],
             "empty_params": ["region"]},
        ]
    }

    suggestions = [
        {"node_id": "node_detect", "param": "region",
         "suggested_value": [120, 300, 200, 340], "confidence": 0.95,
         "note": "检测到按钮"}
    ]

    filled = analyzer.fill_structure(structure, suggestions)
    assert filled["nodes"][0]["config"]["region"] == [120, 300, 200, 340]
    assert "region" not in filled["nodes"][0].get("empty_params", [])
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write the prompt template**

```markdown
<!-- bt_cli/ai/prompts/vlm_analysis.md -->
你是屏幕分析专家。分析截图，为行为树节点的空参数提供建议值。

## 输入

你会收到：
1. 一张屏幕截图
2. 需要填充的参数清单（节点ID、参数名、参数类型）
3. 任务上下文描述

## 输出格式

输出严格的 JSON：

```json
{
  "suggestions": [
    {
      "node_id": "node_detect",
      "param": "region",
      "suggested_value": [120, 300, 200, 340],
      "confidence": 0.95,
      "note": "检测到蓝色登录按钮在左上区域"
    }
  ]
}
```

## 参数类型规则

- **region**: [x1, y1, x2, y2] 矩形区域坐标
- **position**: [x, y] 点击位置坐标
- **keywords**: "识别关键词" 字符串
- **target_color**: "#RRGGBB" 颜色值
- **template_path**: 模板图片保存路径（保持为空，由系统自动截图保存）

## 分析规则

1. 仔细查看截图中与任务上下文相关的元素
2. 对于 region 参数，标注包含目标元素的矩形区域
3. 对于 position 参数，给出目标元素的中心坐标
4. 对于 keywords 参数，识别截图中可用的文字
5. 置信度 0-1：0.9+ 非常确定，0.7-0.9 较确定，<0.7 不确定
6. 如果无法确定某个参数，置信度设为 0 并在 note 中说明

## 重要

- 只输出 JSON
- 坐标基于截图的实际像素尺寸
- 不要输出 markdown 代码块
```

**Step 4: Write minimal implementation**

```python
# bt_cli/ai/vlm_analyzer.py
"""阶段③ VLM 屏幕感知 — 分析截图为空参数生成建议值"""
import json
import os
import base64
from typing import Dict, Any, List

from bt_cli.ai.llm_client import LLMClient


class VLMAnalysisError(Exception):
    """VLM 分析错误"""
    pass


class VLMAnalyzer:
    """视觉大模型屏幕分析器

    分析截图，为行为树节点中的空参数（region/position/keywords 等）
    生成建议值。
    """

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "vlm_analysis.md")

    def __init__(self, vlm_client: LLMClient = None):
        self._vlm = vlm_client

    def analyze(self, screenshot_path: str, structure: Dict[str, Any],
                task_context: str) -> List[Dict[str, Any]]:
        """分析截图，为空参数生成建议值

        Args:
            screenshot_path: 截图文件路径
            structure: 节点结构（含 empty_params）
            task_context: 任务上下文描述

        Returns:
            建议值列表 [{"node_id", "param", "suggested_value", "confidence", "note"}]

        Raises:
            VLMAnalysisError: 分析失败
        """
        if self._vlm is None:
            self._vlm = LLMClient.from_config("vlm")

        # 提取待填充参数
        fill_requests = self._extract_empty_params(structure)
        if not fill_requests:
            return []

        # 编码截图
        image_base64 = self._encode_image(screenshot_path)

        # 构建 prompt
        system_prompt = self._load_prompt()
        user_prompt = self._build_user_prompt(fill_requests, task_context)

        try:
            result = self._vlm.chat_with_image(
                text_prompt=user_prompt,
                image_base64=image_base64,
                image_detail="high",
                system_prompt=system_prompt,
            )
        except Exception as e:
            raise VLMAnalysisError(f"VLM 请求失败: {e}") from e

        try:
            data = json.loads(result["content"])
            suggestions = data.get("suggestions", [])
        except json.JSONDecodeError as e:
            raise VLMAnalysisError(f"VLM 返回的 JSON 无效: {e}") from e

        return suggestions

    def fill_structure(self, structure: Dict[str, Any],
                       suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将建议值填入节点结构

        Args:
            structure: 节点结构
            suggestions: 建议值列表

        Returns:
            填充后的节点结构（深拷贝）
        """
        import copy
        filled = copy.deepcopy(structure)

        # 创建查找索引
        node_map = {n["id"]: n for n in filled["nodes"]}

        for sug in suggestions:
            node_id = sug["node_id"]
            param = sug["param"]
            value = sug["suggested_value"]

            if node_id in node_map:
                node = node_map[node_id]
                node["config"][param] = value
                # 从 empty_params 中移除已填充的
                if "empty_params" in node:
                    node["empty_params"] = [
                        p for p in node["empty_params"] if p != param
                    ]

        return filled

    def _extract_empty_params(self, structure: Dict) -> List[Dict]:
        """从节点结构中提取所有空参数"""
        requests = []
        for node in structure.get("nodes", []):
            for param in node.get("empty_params", []):
                requests.append({
                    "node_id": node["id"],
                    "param": param,
                    "node_type": node["type"],
                })
        return requests

    def _encode_image(self, image_path: str) -> str:
        """将图片编码为 base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _build_user_prompt(self, fill_requests: List[Dict], task_context: str) -> str:
        """构建用户提示词"""
        lines = [f"## 任务上下文\n{task_context}\n"]
        lines.append("## 需要填充的参数清单\n")
        for req in fill_requests:
            lines.append(f"- 节点 {req['node_id']} ({req['node_type']}): 参数 '{req['param']}'")
        lines.append("\n请分析截图，为以上参数提供建议值。")
        return "\n".join(lines)

    def _load_prompt(self) -> str:
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_analyzer.py -v`
Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add bt_cli/ai/prompts/vlm_analysis.md bt_cli/ai/vlm_analyzer.py \
        tests/test_vlm_analyzer.py
git commit -m "feat(ai): add VLMAnalyzer for phase 3 screen perception"
```

---

## Task 8: TreeGenerator + TreeValidator — 阶段④生成与校验

**Files:**
- Create: `bt_cli/ai/tree_generator.py`
- Create: `bt_cli/ai/tree_validator.py`
- Test: `tests/test_tree_generator.py`

**Step 1: Write the failing test**

```python
# tests/test_tree_generator.py
"""TreeGenerator + TreeValidator 测试"""
import pytest
import json


def test_generate_valid_tree():
    """测试从节点结构生成 tree.json"""
    from bt_cli.ai.tree_generator import TreeGenerator

    structure = {
        "nodes": [
            {"id": "node_start", "type": "StartNode",
             "config": {"bind_window": False}, "children": ["node_seq"]},
            {"id": "node_seq", "type": "SequenceNode",
             "config": {"repeat_count": -1, "repeat_interval_ms": 1000},
             "children": ["node_delay"]},
            {"id": "node_delay", "type": "DelayNode",
             "config": {"duration_ms": 1000}, "children": []},
        ]
    }

    gen = TreeGenerator()
    tree_data = gen.generate(structure, canvas_name="测试流程")

    assert tree_data["version"] == "2.1"
    assert tree_data["format_type"] == "behavior_tree"
    assert tree_data["root_node"] == "node_start"
    assert "node_start" in tree_data["nodes"]
    assert "node_seq" in tree_data["nodes"]
    assert "node_delay" in tree_data["nodes"]
    assert len(tree_data["connections"]) == 2


def test_generate_layout_positions():
    """测试生成的节点有布局坐标"""
    from bt_cli.ai.tree_generator import TreeGenerator

    structure = {
        "nodes": [
            {"id": "node_start", "type": "StartNode",
             "config": {}, "children": ["node_seq"]},
            {"id": "node_seq", "type": "SequenceNode",
             "config": {}, "children": ["node_delay"]},
            {"id": "node_delay", "type": "DelayNode",
             "config": {}, "children": []},
        ]
    }

    gen = TreeGenerator()
    tree_data = gen.generate(structure)

    # 根节点 Y=50
    assert tree_data["nodes"]["node_start"]["position"]["y"] == 50
    # 第二层 Y=150
    assert tree_data["nodes"]["node_seq"]["position"]["y"] == 150
    # 第三层 Y=250
    assert tree_data["nodes"]["node_delay"]["position"]["y"] == 250


def test_validate_valid_tree():
    """测试校验通过的有效行为树"""
    from bt_cli.ai.tree_validator import TreeValidator

    tree_data = {
        "version": "2.1",
        "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode",
                           "name": "开始", "enabled": True, "config": {},
                           "position": {"x": 400, "y": 50}, "children": ["node_delay"]},
            "node_delay": {"id": "node_delay", "type": "DelayNode",
                           "name": "延时", "enabled": True, "config": {"duration_ms": 1000},
                           "position": {"x": 400, "y": 150}, "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_delay"}],
    }

    validator = TreeValidator()
    errors = validator.validate(tree_data)
    assert errors == []


def test_validate_missing_root():
    """测试缺少根节点"""
    from bt_cli.ai.tree_validator import TreeValidator

    tree_data = {
        "version": "2.1",
        "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_delay": {"id": "node_delay", "type": "DelayNode",
                           "name": "延时", "enabled": True, "config": {},
                           "position": {"x": 400, "y": 50}, "children": []},
        },
        "connections": [],
    }

    validator = TreeValidator()
    errors = validator.validate(tree_data)
    assert any("root_node" in e.lower() or "根节点" in e for e in errors)


def test_validate_duplicate_ids():
    """测试重复节点 ID"""
    from bt_cli.ai.tree_validator import TreeValidator

    tree_data = {
        "version": "2.1",
        "root_node": "node_1",
        "nodes": {
            "node_1": {"id": "node_1", "type": "StartNode", "name": "", "enabled": True,
                       "config": {}, "position": {"x": 0, "y": 0}, "children": ["node_1"]},
        },
        "connections": [{"parent_id": "node_1", "child_id": "node_1"}],
    }

    validator = TreeValidator()
    errors = validator.validate(tree_data)
    # 自引用应被检测到
    assert len(errors) > 0


def test_validate_condition_without_children():
    """测试条件节点没有子节点"""
    from bt_cli.ai.tree_validator import TreeValidator

    tree_data = {
        "version": "2.1",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode", "name": "",
                           "enabled": True, "config": {}, "position": {"x": 0, "y": 0},
                           "children": ["node_cond"]},
            "node_cond": {"id": "node_cond", "type": "OCRConditionNode", "name": "",
                          "enabled": True, "config": {"region": [0,0,100,100], "keywords": "test"},
                          "position": {"x": 0, "y": 100}, "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_cond"}],
    }

    validator = TreeValidator()
    errors = validator.validate(tree_data)
    assert any("子节点" in e for e in errors)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tree_generator.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write TreeValidator**

```python
# bt_cli/ai/tree_validator.py
"""行为树结构校验器

在 AI 生成 tree.json 后进行结构校验，确保可被 Serializer 正确加载。
"""
from typing import List, Dict, Any


class TreeValidator:
    """行为树 JSON 结构校验器"""

    # 条件节点类型（必须有子节点）
    CONDITION_TYPES = {
        "OCRConditionNode", "ImageConditionNode", "ColorConditionNode",
        "NumberConditionNode", "VariableConditionNode", "TextExtractNode",
    }

    def validate(self, tree_data: Dict[str, Any]) -> List[str]:
        """校验行为树结构

        Args:
            tree_data: tree.json 字典

        Returns:
            错误列表（空列表表示通过）
        """
        errors = []

        # 1. 基本结构检查
        if not isinstance(tree_data, dict):
            return ["tree_data 不是字典"]

        if "nodes" not in tree_data:
            errors.append("缺少 nodes 字段")
            return errors

        nodes = tree_data.get("nodes", {})
        root_id = tree_data.get("root_node")

        # 2. 根节点检查
        if not root_id:
            errors.append("缺少 root_node 字段")
        elif root_id not in nodes:
            errors.append(f"root_node '{root_id}' 在 nodes 中不存在")
        else:
            root_node = nodes[root_id]
            if root_node.get("type") != "StartNode":
                errors.append(f"根节点必须是 StartNode，当前为 {root_node.get('type')}")

        # 3. 节点 ID 唯一性（nodes 字典的 key 就是 ID，天然唯一）
        # 但检查 children 中的自引用
        for node_id, node in nodes.items():
            children = node.get("children", [])
            if node_id in children:
                errors.append(f"节点 {node_id} 自引用为子节点")

        # 4. 条件节点必须有子节点
        for node_id, node in nodes.items():
            node_type = node.get("type", "")
            if node_type in self.CONDITION_TYPES:
                children = node.get("children", [])
                if len(children) == 0:
                    errors.append(f"条件节点 {node_id} ({node_type}) 必须有至少一个子节点")

        # 5. connections 完整性
        connections = tree_data.get("connections", [])
        for conn in connections:
            parent_id = conn.get("parent_id")
            child_id = conn.get("child_id")
            if parent_id not in nodes:
                errors.append(f"connection 的 parent_id '{parent_id}' 不存在")
            if child_id not in nodes:
                errors.append(f"connection 的 child_id '{child_id}' 不存在")

        # 6. children 引用一致性
        for node_id, node in nodes.items():
            children = node.get("children", [])
            for child_id in children:
                if child_id not in nodes:
                    errors.append(f"节点 {node_id} 的子节点 '{child_id}' 不存在")

        return errors

    def validate_with_serializer(self, tree_data: Dict[str, Any]) -> List[str]:
        """使用 Serializer 进行往返校验

        Args:
            tree_data: tree.json 字典

        Returns:
            错误列表
        """
        errors = self.validate(tree_data)
        if errors:
            return errors

        try:
            from bt_core.serializer import Serializer
            from bt_core.registry import register_all_nodes
            register_all_nodes()
            result = Serializer.deserialize(tree_data)
            if result is None or (isinstance(result, tuple) and result[0] is None):
                errors.append("Serializer.deserialize 返回 None，反序列化失败")
        except Exception as e:
            errors.append(f"Serializer 反序列化失败: {e}")

        return errors
```

**Step 4: Write TreeGenerator**

```python
# bt_cli/ai/tree_generator.py
"""阶段④ JSON 生成 — 将节点结构转换为 tree.json 格式"""
import json
from typing import Dict, Any, List
from datetime import datetime


class TreeGenerator:
    """行为树 JSON 生成器

    将节点结构（structure.json）转换为 tree.json v2.1 格式，
    自动计算布局坐标。
    """

    def generate(self, structure: Dict[str, Any],
                 canvas_name: str = "AI生成流程",
                 description: str = "") -> Dict[str, Any]:
        """生成 tree.json

        Args:
            structure: 节点结构（structure_filled.json 格式）
            canvas_name: 画布名称
            description: 描述

        Returns:
            tree.json 格式字典
        """
        nodes_list = structure.get("nodes", [])
        if not nodes_list:
            raise ValueError("节点结构为空")

        # 构建节点查找表
        node_map = {n["id"]: n for n in nodes_list}

        # 计算布局
        layout = self._compute_layout(nodes_list)

        # 转换为 tree.json 节点格式
        nodes_dict = {}
        connections = []

        for node in nodes_list:
            node_id = node["id"]
            pos = layout[node_id]

            nodes_dict[node_id] = {
                "id": node_id,
                "type": node["type"],
                "name": self._generate_name(node),
                "enabled": True,
                "config": node.get("config", {}),
                "position": {"x": pos[0], "y": pos[1]},
                "children": node.get("children", []),
            }

            # 添加 connections
            for child_id in node.get("children", []):
                connections.append({
                    "parent_id": node_id,
                    "child_id": child_id,
                })

        tree_data = {
            "version": "2.1",
            "format_type": "behavior_tree",
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "modified_at": datetime.now().isoformat(),
                "app_version": "ai-generated",
            },
            "canvas": {
                "name": canvas_name,
                "description": description,
                "viewport": {"zoom": 1.0, "offset_x": 0, "offset_y": 0},
            },
            "root_node": nodes_list[0]["id"],
            "nodes": nodes_dict,
            "connections": connections,
        }

        return tree_data

    def generate_and_validate(self, structure: Dict[str, Any],
                              **kwargs) -> tuple:
        """生成并校验

        Returns:
            (tree_data, errors) 元组
        """
        from bt_cli.ai.tree_validator import TreeValidator

        tree_data = self.generate(structure, **kwargs)
        validator = TreeValidator()
        errors = validator.validate(tree_data)
        return tree_data, errors

    def _compute_layout(self, nodes_list: List[Dict]) -> Dict[str, tuple]:
        """计算节点布局坐标

        规则：同级节点横向排列，父子节点纵向排列。
        根节点 Y=50，每层 Y+=100，同级 X 间距 200。
        """
        layout = {}
        node_map = {n["id"]: n for n in nodes_list}
        root_id = nodes_list[0]["id"]

        # BFS 遍历计算层级
        levels = {}  # node_id → level
        queue = [(root_id, 0)]
        while queue:
            node_id, level = queue.pop(0)
            if node_id in levels:
                continue
            levels[node_id] = level
            for child_id in node_map.get(node_id, {}).get("children", []):
                if child_id not in levels:
                    queue.append((child_id, level + 1))

        # 按层级分组
        level_nodes = {}
        for node_id, level in levels.items():
            if level not in level_nodes:
                level_nodes[level] = []
            level_nodes[level].append(node_id)

        # 计算坐标
        for level, node_ids in level_nodes.items():
            y = 50 + level * 100
            count = len(node_ids)
            for i, node_id in enumerate(node_ids):
                x = 400 + (i - (count - 1) / 2) * 200
                layout[node_id] = (int(x), y)

        # 未遍历到的节点（孤立节点）
        for node in nodes_list:
            if node["id"] not in layout:
                layout[node["id"]] = (400, 50)

        return layout

    def _generate_name(self, node: Dict) -> str:
        """生成节点显示名称"""
        type_names = {
            "StartNode": "开始",
            "SequenceNode": "顺序执行",
            "SelectorNode": "选择执行",
            "ParallelNode": "并行执行",
            "RandomNode": "随机执行",
            "SubtreeNode": "子树",
            "DelayNode": "延时",
            "MouseClickNode": "鼠标点击",
            "MouseMoveNode": "鼠标移动",
            "MouseScrollNode": "鼠标滚轮",
            "KeyPressNode": "键盘按键",
            "TextInputNode": "文本输入",
            "SetVariableNode": "设置变量",
            "AlarmNode": "报警",
            "ScriptNode": "执行脚本",
            "CodeNode": "执行代码",
            "OCRConditionNode": "OCR识别",
            "ImageConditionNode": "图像匹配",
            "ColorConditionNode": "颜色检测",
            "NumberConditionNode": "数字比较",
            "VariableConditionNode": "变量判断",
            "TextExtractNode": "文本提取",
        }
        return type_names.get(node["type"], node["type"])
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_tree_generator.py -v`
Expected: PASS (6 tests)

**Step 6: Commit**

```bash
git add bt_cli/ai/tree_generator.py bt_cli/ai/tree_validator.py \
        tests/test_tree_generator.py
git commit -m "feat(ai): add TreeGenerator and TreeValidator for phase 4"
```

---

## Task 9: 更新 AI CLI — 实现 scan/generate/validate 命令

**Files:**
- Modify: `bt_cli/commands/ai.py`
- Test: `tests/test_ai_cli_phase2.py`

**Step 1: Write the failing test**

```python
# tests/test_ai_cli_phase2.py
"""AI CLI 第二阶段命令测试"""
import pytest
import subprocess
import sys
import os
import json
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_ai_validate_valid_tree():
    """测试 validate 命令校验有效行为树"""
    tree_data = {
        "version": "2.1",
        "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode", "name": "开始",
                           "enabled": True, "config": {}, "position": {"x": 400, "y": 50},
                           "children": ["node_delay"]},
            "node_delay": {"id": "node_delay", "type": "DelayNode", "name": "延时",
                           "enabled": True, "config": {"duration_ms": 1000},
                           "position": {"x": 400, "y": 150}, "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_delay"}],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(tree_data, f)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "cli.py"),
             "ai", "validate", tmp_path],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            timeout=30,
        )
        assert result.returncode == 0
        assert "校验通过" in result.stdout
    finally:
        os.unlink(tmp_path)


def test_ai_validate_invalid_tree():
    """测试 validate 命令检测无效行为树"""
    tree_data = {
        "version": "2.1",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "DelayNode", "name": "",
                           "enabled": True, "config": {}, "position": {"x": 0, "y": 0},
                           "children": []},
        },
        "connections": [],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(tree_data, f)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "cli.py"),
             "ai", "validate", tmp_path],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            timeout=30,
        )
        assert result.returncode != 0
        assert "StartNode" in result.stdout or "StartNode" in result.stderr
    finally:
        os.unlink(tmp_path)


def test_ai_generate_from_structure():
    """测试 generate 命令从结构生成 tree.json"""
    structure = {
        "nodes": [
            {"id": "node_start", "type": "StartNode",
             "config": {"bind_window": False}, "children": ["node_delay"]},
            {"id": "node_delay", "type": "DelayNode",
             "config": {"duration_ms": 1000}, "children": []},
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(structure, f)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "cli.py"),
             "ai", "generate", tmp_path],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            timeout=30,
        )
        assert result.returncode == 0
        assert "tree.json" in result.stdout
        assert "校验通过" in result.stdout
    finally:
        os.unlink(tmp_path)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ai_cli_phase2.py -v`
Expected: FAIL（scan/generate/validate 返回错误消息）

**Step 3: Update AI CLI commands**

替换 `bt_cli/commands/ai.py` 中的 `_cmd_scan`、`_cmd_generate`、`_cmd_validate` 函数：

```python
def _cmd_scan(args):
    """阶段③ VLM 屏幕感知"""
    from config.settings_manager import get_settings_manager

    sm = get_settings_manager()
    api_key = sm.get("ai.vlm.api_key", "")
    if not api_key:
        exit_with_code(
            EXIT_CONFIG_ERROR,
            "错误: 未配置 VLM API Key\n"
            "请运行: autodoor-bt config set ai.vlm.api_key \"your-key\""
        )

    structure_path = args.structure_file
    if not os.path.exists(structure_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {structure_path}")

    with open(structure_path, "r", encoding="utf-8") as f:
        structure = json.load(f)

    # 截图
    screenshot_path = os.path.join(_ensure_ai_dir(), "screenshot.png")
    print("正在截取屏幕...")
    _take_screenshot(screenshot_path)

    # 获取任务上下文
    plan_path = os.path.join(os.path.dirname(structure_path), "plan.json")
    task_context = ""
    if os.path.exists(plan_path):
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
            task_context = plan.get("task_summary", "")

    print("VLM 正在分析截图...")

    from bt_cli.ai.vlm_analyzer import VLMAnalyzer, VLMAnalysisError
    try:
        analyzer = VLMAnalyzer()
        suggestions = analyzer.analyze(screenshot_path, structure, task_context)
        filled = analyzer.fill_structure(structure, suggestions)
    except VLMAnalysisError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"VLM 分析失败: {e}")

    # 保存
    ai_dir = _ensure_ai_dir()
    output_path = os.path.join(ai_dir, "structure_filled.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filled, f, ensure_ascii=False, indent=2)

    print(f"\n参数填充完成: {output_path}")
    print(f"  填充建议数: {len(suggestions)}")
    for sug in suggestions:
        conf_mark = "✓" if sug["confidence"] >= 0.8 else "⚠"
        print(f"    {conf_mark} {sug['node_id']}.{sug['param']} = {sug['suggested_value']}"
              f" (置信度: {sug['confidence']:.0%}) — {sug.get('note', '')}")
    print(f"\n确认后运行: autodoor-bt ai generate structure_filled.json")


def _cmd_generate(args):
    """阶段④ 生成 JSON"""
    structure_path = args.structure_file
    if not os.path.exists(structure_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {structure_path}")

    with open(structure_path, "r", encoding="utf-8") as f:
        structure = json.load(f)

    print("正在生成行为树 JSON...")

    from bt_cli.ai.tree_generator import TreeGenerator
    from bt_cli.ai.tree_validator import TreeValidator

    gen = TreeGenerator()
    tree_data, errors = gen.generate_and_validate(structure, canvas_name="AI生成流程")

    if errors:
        print(f"\n校验发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"  - {e}")
        exit_with_code(EXIT_GENERIC_ERROR, "生成失败，请检查节点结构")
    else:
        print("校验通过 ✓")

    # 保存
    ai_dir = _ensure_ai_dir()
    output_path = os.path.join(ai_dir, "tree.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)

    print(f"\n行为树已生成: {output_path}")
    print(f"  节点数: {len(tree_data['nodes'])}")
    print(f"  连接数: {len(tree_data['connections'])}")
    print(f"\n可运行: autodoor-bt run {output_path} --headless")
    print(f"或试运行: autodoor-bt ai test {output_path}")


def _cmd_validate(args):
    """校验 JSON 结构"""
    tree_path = args.tree_file
    if not os.path.exists(tree_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {tree_path}")

    with open(tree_path, "r", encoding="utf-8") as f:
        tree_data = json.load(f)

    from bt_cli.ai.tree_validator import TreeValidator

    validator = TreeValidator()
    errors = validator.validate_with_serializer(tree_data)

    if errors:
        print(f"校验失败，发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"  ✗ {e}")
        exit_with_code(EXIT_GENERIC_ERROR)
    else:
        print("校验通过 ✓")
        print(f"  节点数: {len(tree_data.get('nodes', {}))}")
        print(f"  连接数: {len(tree_data.get('connections', []))}")


def _take_screenshot(output_path: str):
    """截取屏幕并保存"""
    from bt_utils.screenshot import ScreenshotManager
    sm = ScreenshotManager()
    img = sm.get_full_screenshot()
    img.save(output_path)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ai_cli_phase2.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add bt_cli/commands/ai.py tests/test_ai_cli_phase2.py
git commit -m "feat(ai): implement scan/generate/validate CLI commands"
```

---

## Task 10: IterationEngine — 阶段⑤试运行+迭代修正

**Files:**
- Create: `bt_cli/ai/prompts/failure_analysis.md`
- Create: `bt_cli/ai/iteration_engine.py`
- Test: `tests/test_iteration_engine.py`

**Step 1: Write the failing test**

```python
# tests/test_iteration_engine.py
"""IterationEngine 测试"""
import pytest
import json
from unittest.mock import patch, MagicMock


def test_analyze_failure_returns_suggestions():
    """测试失败分析返回修正建议"""
    from bt_cli.ai.iteration_engine import IterationEngine

    mock_llm_response = {
        "content": json.dumps({
            "analysis": "OCR识别失败，可能区域过小",
            "fixes": [
                {
                    "node_id": "node_detect",
                    "param": "region",
                    "new_value": [100, 200, 400, 400],
                    "reason": "扩大检测区域以提高识别率"
                }
            ],
            "confidence": 0.85
        }, ensure_ascii=False),
        "model": "gpt-4o",
        "usage": {},
    }

    test_report = {
        "success": False,
        "node_statuses": {
            "node_start": "success",
            "node_detect": "failure",
            "node_click": "skipped",
        },
        "logs": ["[FAILURE] node_detect: OCR识别失败"],
        "blackboard": {},
    }

    tree_data = {
        "nodes": {
            "node_detect": {"type": "OCRConditionNode", "config": {"region": [100, 200, 200, 250]}},
        }
    }

    with patch("bt_cli.ai.iteration_engine.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.return_value = mock_llm_response
        mock_client_cls.from_config.return_value = mock_client

        engine = IterationEngine()
        result = engine.analyze_failure(test_report, tree_data, "测试任务")

    assert "analysis" in result
    assert len(result["fixes"]) == 1
    assert result["fixes"][0]["node_id"] == "node_detect"


def test_apply_fixes_modifies_tree():
    """测试应用修正建议到行为树"""
    from bt_cli.ai.iteration_engine import IterationEngine

    engine = IterationEngine()

    tree_data = {
        "nodes": {
            "node_detect": {"id": "node_detect", "type": "OCRConditionNode",
                           "config": {"region": [100, 200, 200, 250], "keywords": "test"},
                           "children": []},
        }
    }

    fixes = [
        {"node_id": "node_detect", "param": "region",
         "new_value": [100, 200, 400, 400], "reason": "扩大区域"}
    ]

    fixed_tree = engine.apply_fixes(tree_data, fixes)
    assert fixed_tree["nodes"]["node_detect"]["config"]["region"] == [100, 200, 400, 400]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_iteration_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write the prompt template**

```markdown
<!-- bt_cli/ai/prompts/failure_analysis.md -->
你是行为树调试专家。分析试运行失败日志，找出失败原因并提供修正建议。

## 输入

你会收到：
1. 试运行报告（JSON）：包含节点状态、执行日志、黑板变量
2. 当前行为树结构（JSON）
3. 任务上下文描述

## 输出格式

输出严格的 JSON：

```json
{
  "analysis": "失败原因分析",
  "fixes": [
    {
      "node_id": "node_detect",
      "param": "region",
      "new_value": [100, 200, 400, 400],
      "reason": "扩大检测区域以提高识别率"
    }
  ],
  "confidence": 0.85
}
```

## 常见失败模式与修正策略

| 失败模式 | 修正策略 |
|---------|---------|
| OCR 识别失败 | 扩大 region / 切换 preprocess_mode / 调整 keywords |
| 图像匹配失败 | 降低 threshold / 重新截图更新模板 / 扩大 region |
| 点击位置偏差 | 切换 use_blackboard 使用检测位置而非固定坐标 |
| 循环过快/过慢 | 调整 repeat_interval_ms / duration_ms |
| 窗口未找到 | 检查 window_title / window_pid 配置 |

## 重要

- 只输出 JSON
- fixes 中的 node_id 必须存在于行为树中
- new_value 的类型必须与参数类型匹配
```

**Step 4: Write minimal implementation**

```python
# bt_cli/ai/iteration_engine.py
"""阶段⑤ 试运行 + 迭代修正

通过 HeadlessRunner 试运行行为树，收集日志，
AI 分析失败原因，提供修正建议，应用修正后重新试运行。
"""
import json
import os
import copy
import subprocess
import sys
from typing import Dict, Any, List, Optional

from bt_cli.ai.llm_client import LLMClient


class IterationError(Exception):
    """迭代修正错误"""
    pass


class IterationEngine:
    """试运行 + 迭代修正引擎

    工作流程：
    1. 试运行行为树（限时）
    2. 收集执行日志、节点状态、黑板变量
    3. AI 分析失败原因
    4. 应用修正建议
    5. 重新试运行（可多轮）
    """

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "failure_analysis.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client

    def run_test(self, tree_path: str, timeout_ms: int = 30000) -> Dict[str, Any]:
        """试运行行为树

        Args:
            tree_path: tree.json 文件路径
            timeout_ms: 超时毫秒

        Returns:
            试运行报告 {"success", "node_statuses", "logs", "blackboard"}
        """
        # 通过 subprocess 调用 CLI run --headless
        cmd = [
            sys.executable, os.path.join(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))), "cli.py"),
            "run", tree_path, "--headless",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout_ms / 1000,
            )
            success = result.returncode == 0
            logs = result.stdout.split("\n") if result.stdout else []
            if result.stderr:
                logs.extend(result.stderr.split("\n"))
        except subprocess.TimeoutExpired:
            success = False
            logs = [f"试运行超时 ({timeout_ms}ms)"]
        except Exception as e:
            success = False
            logs = [f"试运行异常: {e}"]

        return {
            "success": success,
            "node_statuses": {},  # 后续可通过日志解析
            "logs": logs,
            "blackboard": {},
        }

    def analyze_failure(self, test_report: Dict[str, Any],
                        tree_data: Dict[str, Any],
                        task_context: str) -> Dict[str, Any]:
        """AI 分析失败原因

        Args:
            test_report: 试运行报告
            tree_data: 当前行为树结构
            task_context: 任务上下文

        Returns:
            {"analysis", "fixes", "confidence"}

        Raises:
            IterationError: 分析失败
        """
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")

        system_prompt = self._load_prompt()

        # 精简行为树结构（只保留关键信息）
        tree_summary = self._summarize_tree(tree_data)

        user_content = (
            f"## 任务上下文\n{task_context}\n\n"
            f"## 试运行报告\n```json\n{json.dumps(test_report, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## 行为树结构\n```json\n{json.dumps(tree_summary, ensure_ascii=False, indent=2)}\n```\n\n"
            f"请分析失败原因并提供修正建议。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            result = self._llm.chat(
                messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise IterationError(f"LLM 请求失败: {e}") from e

        try:
            analysis = json.loads(result["content"])
        except json.JSONDecodeError as e:
            raise IterationError(f"LLM 返回的 JSON 无效: {e}") from e

        return analysis

    def apply_fixes(self, tree_data: Dict[str, Any],
                    fixes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """应用修正建议到行为树

        Args:
            tree_data: 行为树数据
            fixes: 修正建议列表

        Returns:
            修正后的行为树（深拷贝）
        """
        fixed = copy.deepcopy(tree_data)
        nodes = fixed.get("nodes", {})

        for fix in fixes:
            node_id = fix["node_id"]
            param = fix["param"]
            new_value = fix["new_value"]

            if node_id in nodes:
                if "config" not in nodes[node_id]:
                    nodes[node_id]["config"] = {}
                nodes[node_id]["config"][param] = new_value

        return fixed

    def iterate(self, tree_path: str, max_rounds: int = 3,
                task_context: str = "") -> Dict[str, Any]:
        """完整迭代流程

        Args:
            tree_path: tree.json 文件路径
            max_rounds: 最大迭代次数
            task_context: 任务上下文

        Returns:
            {"success", "rounds", "final_tree", "reports"}
        """
        with open(tree_path, "r", encoding="utf-8") as f:
            tree_data = json.load(f)

        reports = []

        for round_num in range(1, max_rounds + 1):
            print(f"\n--- 第 {round_num} 轮试运行 ---")

            # 试运行
            report = self.run_test(tree_path)
            reports.append(report)

            if report["success"]:
                print("试运行成功！")
                return {
                    "success": True,
                    "rounds": round_num,
                    "final_tree": tree_data,
                    "reports": reports,
                }

            # AI 分析
            print("AI 正在分析失败原因...")
            try:
                analysis = self.analyze_failure(report, tree_data, task_context)
            except IterationError as e:
                print(f"分析失败: {e}")
                break

            print(f"分析: {analysis.get('analysis', '')}")
            fixes = analysis.get("fixes", [])

            if not fixes:
                print("无修正建议，停止迭代")
                break

            # 应用修正
            tree_data = self.apply_fixes(tree_data, fixes)
            print(f"应用了 {len(fixes)} 个修正")

            # 保存修正后的树
            with open(tree_path, "w", encoding="utf-8") as f:
                json.dump(tree_data, f, ensure_ascii=False, indent=2)

        return {
            "success": False,
            "rounds": len(reports),
            "final_tree": tree_data,
            "reports": reports,
        }

    def _summarize_tree(self, tree_data: Dict) -> List[Dict]:
        """精简行为树结构用于 AI 分析"""
        summary = []
        for node_id, node in tree_data.get("nodes", {}).items():
            summary.append({
                "id": node_id,
                "type": node.get("type"),
                "config": node.get("config", {}),
                "children": node.get("children", []),
            })
        return summary

    def _load_prompt(self) -> str:
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_iteration_engine.py -v`
Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add bt_cli/ai/prompts/failure_analysis.md bt_cli/ai/iteration_engine.py \
        tests/test_iteration_engine.py
git commit -m "feat(ai): add IterationEngine for phase 5 trial run and iteration"
```

---

## Task 11: 更新 AI CLI — 实现 test/refine/create 命令

**Files:**
- Modify: `bt_cli/commands/ai.py`
- Test: `tests/test_ai_cli_phase3.py`

**Step 1: Write the failing test**

```python
# tests/test_ai_cli_phase3.py
"""AI CLI 第三阶段命令测试"""
import pytest
import subprocess
import sys
import os
import json
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_ai_test_command():
    """测试 ai test 命令执行试运行"""
    # 创建一个简单的有效行为树
    tree_data = {
        "version": "2.1",
        "format_type": "behavior_tree",
        "root_node": "node_start",
        "nodes": {
            "node_start": {"id": "node_start", "type": "StartNode", "name": "开始",
                           "enabled": True, "config": {},
                           "position": {"x": 400, "y": 50}, "children": ["node_delay"]},
            "node_delay": {"id": "node_delay", "type": "DelayNode", "name": "延时",
                           "enabled": True, "config": {"duration_ms": 100},
                           "position": {"x": 400, "y": 150}, "children": []},
        },
        "connections": [{"parent_id": "node_start", "child_id": "node_delay"}],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(tree_data, f)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "cli.py"),
             "ai", "test", tmp_path, "--timeout", "5000"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            timeout=60,
        )
        # 应该返回 0（试运行执行完毕，无论成功失败）
        # 或者非 0（如果未配置 API Key 且试运行失败）
        assert "试运行" in result.stdout or "试运行" in result.stderr
    finally:
        os.unlink(tmp_path)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ai_cli_phase3.py -v`
Expected: FAIL（test 命令返回"功能将在第三阶段实现"）

**Step 3: Update AI CLI commands**

替换 `bt_cli/commands/ai.py` 中的 `_cmd_test`、`_cmd_refine`、`_cmd_create` 函数：

```python
def _cmd_test(args):
    """阶段⑤ 试运行"""
    tree_path = args.tree_file
    if not os.path.exists(tree_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {tree_path}")

    from config.settings_manager import get_settings_manager
    sm = get_settings_manager()
    timeout_ms = getattr(args, "timeout", None) or sm.get("ai.iteration.test_timeout_ms", 30000)

    from bt_cli.ai.iteration_engine import IterationEngine

    engine = IterationEngine()
    print(f"正在试运行（超时 {timeout_ms}ms）...")

    report = engine.run_test(tree_path, timeout_ms=timeout_ms)

    # 保存报告
    ai_dir = _ensure_ai_dir()
    report_path = os.path.join(ai_dir, "test_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if report["success"]:
        print(f"\n试运行成功 ✓")
        print(f"报告已保存: {report_path}")
    else:
        print(f"\n试运行失败 ✗")
        print(f"报告已保存: {report_path}")
        print(f"\n执行日志（最后 10 行）:")
        for line in report["logs"][-10:]:
            print(f"  {line}")
        print(f"\n可运行迭代修正: autodoor-bt ai refine {tree_path}")


def _cmd_refine(args):
    """阶段⑤ 迭代修正"""
    tree_path = args.tree_file
    if not os.path.exists(tree_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {tree_path}")

    from config.settings_manager import get_settings_manager
    sm = get_settings_manager()
    api_key = sm.get("ai.llm.api_key", "")
    if not api_key:
        exit_with_code(
            EXIT_CONFIG_ERROR,
            "错误: 未配置 AI API Key\n"
            "请运行: autodoor-bt config set ai.llm.api_key \"your-key\""
        )

    max_rounds = getattr(args, "max_rounds", None) or sm.get("ai.iteration.max_rounds", 3)
    timeout_ms = sm.get("ai.iteration.test_timeout_ms", 30000)

    # 获取任务上下文
    task_context = ""
    plan_path = os.path.join(os.path.dirname(tree_path), "plan.json")
    if os.path.exists(plan_path):
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
            task_context = plan.get("task_summary", "")

    from bt_cli.ai.iteration_engine import IterationEngine

    engine = IterationEngine()
    result = engine.iterate(tree_path, max_rounds=max_rounds, task_context=task_context)

    if result["success"]:
        print(f"\n迭代成功！共 {result['rounds']} 轮")
    else:
        print(f"\n迭代未完全成功，共试运行 {result['rounds']} 轮")
        print(f"最终版本已保存: {tree_path}")
        print(f"建议手动检查或调整参数后重试")


def _cmd_create(args):
    """完整创建流程"""
    from config.settings_manager import get_settings_manager
    sm = get_settings_manager()
    api_key = sm.get("ai.llm.api_key", "")
    if not api_key:
        exit_with_code(
            EXIT_CONFIG_ERROR,
            "错误: 未配置 AI API Key\n"
            "请运行: autodoor-bt config set ai.llm.api_key \"your-key\""
        )

    description = args.description
    print(f"=== AI 行为树创建流程 ===")
    print(f"任务描述: {description}\n")

    # 阶段① 意图分析
    print("--- 阶段 1/5: 意图分析 ---")
    from bt_cli.ai.intent_analyzer import IntentAnalyzer, IntentAnalysisError
    try:
        analyzer = IntentAnalyzer()
        plan = analyzer.analyze(description)
    except IntentAnalysisError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"意图分析失败: {e}")

    ai_dir = _ensure_ai_dir()
    plan_path = os.path.join(ai_dir, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"  任务概述: {plan['task_summary']}")
    print(f"  阶段数: {len(plan['phases'])}")

    if not _confirm("是否继续节点选型？"):
        print(f"任务计划已保存: {plan_path}")
        print(f"后续可运行: autodoor-bt ai select {plan_path}")
        return

    # 阶段② 节点选型
    print("\n--- 阶段 2/5: 节点选型 ---")
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_selector import NodeSelector, NodeSelectionError
    register_all_nodes()
    try:
        selector = NodeSelector()
        structure = selector.select(plan)
    except NodeSelectionError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"节点选型失败: {e}")

    structure_path = os.path.join(ai_dir, "structure.json")
    with open(structure_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)
    print(f"  节点数: {len(structure['nodes'])}")

    if not _confirm("是否继续屏幕感知？"):
        print(f"节点结构已保存: {structure_path}")
        print(f"后续可运行: autodoor-bt ai scan {structure_path}")
        return

    # 阶段③ 屏幕感知
    print("\n--- 阶段 3/5: VLM 屏幕感知 ---")
    vlm_key = sm.get("ai.vlm.api_key", "")
    if not vlm_key:
        print("  跳过：未配置 VLM API Key")
        print("  节点结构保持原样（参数需手动补充）")
        filled = structure
    else:
        screenshot_path = os.path.join(ai_dir, "screenshot.png")
        print("  正在截取屏幕...")
        _take_screenshot(screenshot_path)

        from bt_cli.ai.vlm_analyzer import VLMAnalyzer, VLMAnalysisError
        try:
            vlm = VLMAnalyzer()
            suggestions = vlm.analyze(screenshot_path, structure, plan["task_summary"])
            filled = vlm.fill_structure(structure, suggestions)
            print(f"  填充建议数: {len(suggestions)}")
        except VLMAnalysisError as e:
            print(f"  VLM 分析失败: {e}")
            print("  节点结构保持原样")
            filled = structure

    filled_path = os.path.join(ai_dir, "structure_filled.json")
    with open(filled_path, "w", encoding="utf-8") as f:
        json.dump(filled, f, ensure_ascii=False, indent=2)

    # 阶段④ 生成
    print("\n--- 阶段 4/5: 生成 JSON ---")
    from bt_cli.ai.tree_generator import TreeGenerator
    gen = TreeGenerator()
    tree_data, errors = gen.generate_and_validate(filled, canvas_name=plan["task_summary"])
    if errors:
        print(f"  校验发现问题:")
        for e in errors:
            print(f"    - {e}")
        exit_with_code(EXIT_GENERIC_ERROR, "生成失败")
    print("  校验通过 ✓")

    tree_path = os.path.join(ai_dir, "tree.json")
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)
    print(f"  行为树已生成: {tree_path}")

    if not _confirm("是否继续试运行？"):
        print(f"\n可运行: autodoor-bt run {tree_path} --headless")
        return

    # 阶段⑤ 试运行
    print("\n--- 阶段 5/5: 试运行 ---")
    from bt_cli.ai.iteration_engine import IterationEngine
    engine = IterationEngine()
    timeout_ms = sm.get("ai.iteration.test_timeout_ms", 30000)
    report = engine.run_test(tree_path, timeout_ms=timeout_ms)

    if report["success"]:
        print("\n试运行成功 ✓")
        print(f"最终行为树: {tree_path}")
    else:
        print("\n试运行失败 ✗")
        print(f"报告: {os.path.join(ai_dir, 'test_report.json')}")
        if _confirm("是否进行 AI 迭代修正？"):
            max_rounds = sm.get("ai.iteration.max_rounds", 3)
            result = engine.iterate(tree_path, max_rounds=max_rounds,
                                    task_context=plan["task_summary"])
            if result["success"]:
                print(f"\n迭代成功！最终行为树: {tree_path}")
            else:
                print(f"\n迭代未完全成功，最终版本: {tree_path}")

    print(f"\n=== 完成 ===")
    print(f"行为树文件: {tree_path}")
    print(f"中间文件目录: {ai_dir}")


def _confirm(message: str) -> bool:
    """交互式确认"""
    try:
        answer = input(f"{message} (y/n): ")
        return answer.lower() in ("y", "yes", "")
    except EOFError:
        return False
```

同时需要更新 `cli.py` 中的 `ai test` 和 `ai refine` 参数定义，添加可选参数：

```python
    ai_test = ai_sub.add_parser("test", help="阶段⑤: 试运行")
    ai_test.add_argument("tree_file", help="tree.json 文件路径")
    ai_test.add_argument("--timeout", type=int, default=None, help="超时毫秒")

    ai_refine = ai_sub.add_parser("refine", help="阶段⑤: 迭代修正")
    ai_refine.add_argument("tree_file", help="tree.json 文件路径")
    ai_refine.add_argument("--max-rounds", type=int, default=None, help="最大迭代次数")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ai_cli_phase3.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bt_cli/commands/ai.py cli.py tests/test_ai_cli_phase3.py
git commit -m "feat(ai): implement test/refine/create CLI commands"
```

---

## Task 12: 端到端集成测试

**Files:**
- Test: `tests/test_ai_e2e.py`

**Step 1: Write the integration test**

```python
# tests/test_ai_e2e.py
"""AI 编排端到端集成测试"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock


def test_full_pipeline_plan_to_generate():
    """测试从意图分析到生成的完整流程（mock LLM）"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.intent_analyzer import IntentAnalyzer
    from bt_cli.ai.node_selector import NodeSelector
    from bt_cli.ai.tree_generator import TreeGenerator
    from bt_cli.ai.tree_validator import TreeValidator

    register_all_nodes()

    # Mock LLM 响应
    plan_response = {
        "content": json.dumps({
            "task_summary": "每秒点击一次鼠标",
            "loop": {"enabled": True, "interval_ms": 1000, "max_iterations": -1},
            "phases": [
                {"phase": "act", "action": "click", "position_source": "fixed",
                 "on_complete": "loop_back"}
            ],
            "window": {"bind": False, "title": "", "pid": None}
        }, ensure_ascii=False),
        "model": "gpt-4o", "usage": {},
    }

    structure_response = {
        "content": json.dumps({
            "nodes": [
                {"id": "node_start", "type": "StartNode",
                 "config": {"bind_window": False}, "children": ["node_loop"]},
                {"id": "node_loop", "type": "SequenceNode",
                 "config": {"repeat_count": -1, "repeat_interval_ms": 1000},
                 "children": ["node_click", "node_delay"]},
                {"id": "node_click", "type": "MouseClickNode",
                 "config": {"button": "left", "position": [500, 500],
                            "use_blackboard": False},
                 "children": []},
                {"id": "node_delay", "type": "DelayNode",
                 "config": {"duration_ms": 1000}, "children": []},
            ]
        }, ensure_ascii=False),
        "model": "gpt-4o", "usage": {},
    }

    with patch("bt_cli.ai.intent_analyzer.LLMClient") as mock1, \
         patch("bt_cli.ai.node_selector.LLMClient") as mock2:

        client1 = MagicMock()
        client1.chat.return_value = plan_response
        mock1.from_config.return_value = client1

        client2 = MagicMock()
        client2.chat.return_value = structure_response
        mock2.from_config.return_value = client2

        # 阶段①
        analyzer = IntentAnalyzer()
        plan = analyzer.analyze("每秒点击一次鼠标")
        assert plan["loop"]["enabled"] == True

        # 阶段②
        selector = NodeSelector()
        structure = selector.select(plan)
        assert len(structure["nodes"]) == 4

    # 阶段④（跳过③，使用已填充参数）
    gen = TreeGenerator()
    tree_data, errors = gen.generate_and_validate(structure)
    assert errors == []
    assert tree_data["root_node"] == "node_start"
    assert len(tree_data["nodes"]) == 4

    # Serializer 往返测试
    validator = TreeValidator()
    serializer_errors = validator.validate_with_serializer(tree_data)
    assert serializer_errors == []


def test_node_spec_exporter_covers_all_registered():
    """验证 NodeSpecExporter 覆盖所有已注册节点"""
    from bt_core.registry import register_all_nodes, NodeRegistry
    from bt_cli.ai.node_spec_exporter import NodeSpecExporter

    register_all_nodes()
    exporter = NodeSpecExporter()
    specs = exporter.export_all()

    registered = NodeRegistry.list_types()
    for node_type in registered:
        assert node_type in specs, f"NodeSpecExporter 缺少节点: {node_type}"


def test_iteration_engine_apply_and_validate():
    """测试迭代修正后行为树仍通过校验"""
    from bt_cli.ai.tree_generator import TreeGenerator
    from bt_cli.ai.tree_validator import TreeValidator
    from bt_cli.ai.iteration_engine import IterationEngine

    structure = {
        "nodes": [
            {"id": "node_start", "type": "StartNode",
             "config": {"bind_window": False}, "children": ["node_loop"]},
            {"id": "node_loop", "type": "SequenceNode",
             "config": {"repeat_count": 1}, "children": ["node_detect"]},
            {"id": "node_detect", "type": "OCRConditionNode",
             "config": {"region": [100, 200, 200, 250], "keywords": "test"},
             "children": ["node_click"]},
            {"id": "node_click", "type": "MouseClickNode",
             "config": {"button": "left", "position": [150, 225]},
             "children": []},
        ]
    }

    gen = TreeGenerator()
    tree_data = gen.generate(structure)

    # 应用修正
    engine = IterationEngine()
    fixes = [
        {"node_id": "node_detect", "param": "region",
         "new_value": [100, 200, 400, 400], "reason": "扩大区域"}
    ]
    fixed_tree = engine.apply_fixes(tree_data, fixes)

    # 验证修正后的树仍有效
    validator = TreeValidator()
    errors = validator.validate(fixed_tree)
    assert errors == []

    # 验证修正已应用
    assert fixed_tree["nodes"]["node_detect"]["config"]["region"] == [100, 200, 400, 400]
```

**Step 2: Run the integration test**

Run: `python -m pytest tests/test_ai_e2e.py -v`
Expected: PASS (3 tests)

**Step 3: Run all AI tests together**

Run: `python -m pytest tests/test_ai_config.py tests/test_llm_client.py tests/test_node_spec_exporter.py tests/test_intent_analyzer.py tests/test_node_selector.py tests/test_ai_cli.py tests/test_vlm_analyzer.py tests/test_tree_generator.py tests/test_ai_cli_phase2.py tests/test_iteration_engine.py tests/test_ai_cli_phase3.py tests/test_ai_e2e.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/test_ai_e2e.py
git commit -m "test(ai): add end-to-end integration tests for AI orchestration pipeline"
```

---

## 实施路线总结

| 阶段 | Task | 模块 | 交付物 |
|------|------|------|--------|
| 基础 | 1 | 配置 | AI 配置项（DEFAULT_SETTINGS） |
| 基础 | 2 | LLMClient | 通用 OpenAI 兼容 API 客户端 |
| 基础 | 3 | NodeSpecExporter | 节点规格动态导出 |
| 阶段① | 4 | IntentAnalyzer | 意图分析（plan.json） |
| 阶段② | 5 | NodeSelector | 节点选型（structure.json） |
| CLI | 6 | ai 命令组 | `ai plan` / `ai select` / `ai nodes` |
| 阶段③ | 7 | VLMAnalyzer | VLM 屏幕感知 |
| 阶段④ | 8 | TreeGenerator + TreeValidator | JSON 生成 + 校验 |
| CLI | 9 | ai 命令扩展 | `ai scan` / `ai generate` / `ai validate` |
| 阶段⑤ | 10 | IterationEngine | 试运行 + 迭代修正 |
| CLI | 11 | ai 命令完成 | `ai test` / `ai refine` / `ai create` |
| 集成 | 12 | E2E 测试 | 端到端集成测试 |

## 验证命令

```bash
# 运行所有 AI 相关测试
python -m pytest tests/test_ai_*.py -v

# 验证 CLI 可用
python cli.py ai --help
python cli.py ai nodes

# 验证配置
python cli.py config get ai.enabled
python cli.py config set ai.llm.api_key "your-key"
python cli.py config set ai.llm.base_url "https://api.openai.com/v1"
python cli.py config set ai.llm.model "gpt-4o"
```

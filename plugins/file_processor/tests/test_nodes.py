# plugins/file_processor/tests/test_nodes.py
"""文件处理插件节点测试"""
import os
import sys
import json
import tempfile
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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

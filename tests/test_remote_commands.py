# tests/test_remote_commands.py
"""remote 命令数据解析测试"""
import os
import sys
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_do_status_parses_version(capsys):
    """测试 status 命令正确解析 version 字段"""
    from bt_cli.commands.remote import _do_status
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "version": "1.0.0"}
    with patch("requests.get", return_value=mock_resp):
        _do_status("http://localhost:8080", {}, MagicMock())
    captured = capsys.readouterr().out
    assert "1.0.0" in captured
    assert "ok" in captured


def test_do_trees_parses_wrapped_list(capsys):
    """测试 trees 命令正确解析 {"trees": [...]} 包装结构"""
    from bt_cli.commands.remote import _do_trees
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "trees": [
            {"tree_id": "tree1", "status": "running"},
            {"tree_id": "tree2", "status": "stopped"},
        ]
    }
    with patch("requests.get", return_value=mock_resp):
        _do_trees("http://localhost:8080", {}, MagicMock())
    captured = capsys.readouterr().out
    assert "tree1" in captured
    assert "tree2" in captured
    assert "running" in captured
    assert "stopped" in captured
    assert "行为树列表 (2 个)" in captured


def test_do_nodes_parses_wrapped_list(capsys):
    """测试 nodes 命令正确解析 {"nodes": [...]} 包装结构"""
    from bt_cli.commands.remote import _do_nodes
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "nodes": [
            {"node_id": "n1", "node_type": "SequenceNode", "name": "root", "status": "idle"}
        ]
    }
    args = MagicMock()
    args.tree_id = "tree1"
    with patch("requests.get", return_value=mock_resp):
        _do_nodes("http://localhost:8080", {}, args)
    captured = capsys.readouterr().out
    assert "n1" in captured
    assert "SequenceNode" in captured
    assert "root" in captured
    assert "节点列表 (1 个)" in captured


def test_do_trees_empty_list(capsys):
    """测试 trees 命令空列表处理"""
    from bt_cli.commands.remote import _do_trees
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"trees": []}
    with patch("requests.get", return_value=mock_resp):
        _do_trees("http://localhost:8080", {}, MagicMock())
    captured = capsys.readouterr().out
    assert "无行为树" in captured

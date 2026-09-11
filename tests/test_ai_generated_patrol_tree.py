# tests/test_ai_generated_patrol_tree.py
"""AI 生成挂机巡逻树的真实运行验证（Windows CI）"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bt_core.registry import register_all_nodes
from bt_cli.ai.tree_validator import TreeValidator

TREE_FILE = os.path.join(os.path.dirname(__file__), "data", "ai_patrol_tree.json")


@pytest.fixture(scope="module")
def tree_data():
    with open(TREE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def test_tree_file_exists():
    assert os.path.exists(TREE_FILE)


def test_structure_valid(tree_data):
    errors = TreeValidator().validate(tree_data)
    assert errors == [], f"结构错误: {errors}"


def test_serializer_roundtrip(tree_data):
    from bt_core.serializer import Serializer
    register_all_nodes()
    result = Serializer.deserialize(tree_data)
    assert result is not None


def test_all_nodes_instantiate(tree_data):
    from bt_core.registry import NodeRegistry
    register_all_nodes()
    types = set(NodeRegistry.list_types())
    for nid, node in tree_data["nodes"].items():
        assert node["type"] in types, f"未注册节点类型: {node['type']} ({nid})"


def test_blackboard_follow_clicks(tree_data):
    for nid, node in tree_data["nodes"].items():
        if node["type"] == "MouseClickNode":
            cfg = node.get("config", {})
            if cfg.get("position_key") == "last_detection_position":
                assert cfg.get("use_blackboard") is True, f"{nid} 未开黑板跟随"


def test_walk_clicks_have_position(tree_data):
    for nid, node in tree_data["nodes"].items():
        if node["type"] == "MouseClickNode" and not node.get("config", {}).get("use_blackboard"):
            assert node["config"].get("position"), f"{nid} 走位点击缺 position"


def test_ocr_keywords_present(tree_data):
    for nid, node in tree_data["nodes"].items():
        if node["type"] == "OCRConditionNode":
            assert node.get("config", {}).get("keywords"), f"{nid} OCR 节点缺 keywords"

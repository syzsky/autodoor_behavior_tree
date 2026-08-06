import json
import pytest
from unittest.mock import MagicMock, patch
from bt_cli.ai.dialogue_filler import DialogueFiller, DialogueFillError


def _structure():
    return {"nodes": [
        {"id": "node_detect", "type": "OCRConditionNode",
         "config": {}, "children": [], "empty_params": ["region", "keywords"]},
        {"id": "node_start", "type": "StartNode", "config": {}, "children": []},
    ]}


def test_propose_questions_returns_one_per_empty_param():
    with patch("bt_cli.ai.dialogue_filler.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "questions": [
                {"node_id": "node_detect", "param": "region", "question": "检测区域在哪里？"},
                {"node_id": "node_detect", "param": "keywords", "question": "要识别什么文字？"},
            ]
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        filler = DialogueFiller()
        out = filler.propose_questions(_structure(), "任务")
        assert len(out) == 2
        assert out[0]["param"] == "region"
        assert "node_type" in out[0]
        assert "hint" in out[0]
        assert out[0]["node_type"] == "OCRConditionNode"
        assert out[1]["node_type"] == "OCRConditionNode"


def test_resolve_from_answers_fills_and_clears_empty():
    answers = [
        {"node_id": "node_detect", "param": "region",
         "suggested_value": [10, 20, 30, 40], "confidence": 0.8},
        {"node_id": "node_detect", "param": "keywords",
         "suggested_value": "签到", "confidence": 0.9},
    ]
    filler = DialogueFiller()
    filled = filler.resolve_from_answers(_structure(), answers)
    node = filled["nodes"][0]
    assert node["config"]["region"] == [10, 20, 30, 40]
    assert node["config"]["keywords"] == "签到"
    assert node["empty_params"] == []


def test_propose_questions_empty_params_returns_empty():
    filler = DialogueFiller()
    assert filler.propose_questions({"nodes": []}, "任务") == []


def test_propose_questions_backfills_missing_param():
    """LLM 漏掉一个参数时，仍应返回覆盖所有空参数的问题"""
    with patch("bt_cli.ai.dialogue_filler.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "questions": [
                {"node_id": "node_detect", "param": "region",
                 "question": "检测区域在哪里？"},
            ]
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        filler = DialogueFiller()
        out = filler.propose_questions(_structure(), "任务")
        params = {q["param"] for q in out}
        assert params == {"region", "keywords"}
        # 补齐的 keywords 问题带默认 question 与 hint
        kw = next(q for q in out if q["param"] == "keywords")
        assert kw["question"] == "请描述该参数的目标位置或特征"
        assert kw["hint"]
        assert kw["node_type"] == "OCRConditionNode"


def test_propose_questions_dedupes_duplicates():
    """LLM 对同一 (node_id, param) 返回多个问题时只保留一个"""
    with patch("bt_cli.ai.dialogue_filler.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps({
            "questions": [
                {"node_id": "node_detect", "param": "region", "question": "A"},
                {"node_id": "node_detect", "param": "region", "question": "B"},
            ]
        }), "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        filler = DialogueFiller()
        out = filler.propose_questions(_structure(), "任务")
        regions = [q for q in out if q["param"] == "region"]
        assert len(regions) == 1
        # 同时保证 keywords 仍被补齐
        assert {"region", "keywords"} <= {q["param"] for q in out}


def test_propose_questions_invalid_json_raises():
    """无效 JSON 时抛 DialogueFillError"""
    with patch("bt_cli.ai.dialogue_filler.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": "这不是JSON格式的回复",
                                  "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        filler = DialogueFiller()
        with pytest.raises(DialogueFillError, match="JSON 无效"):
            filler.propose_questions(_structure(), "任务")


def test_propose_questions_json_array_raises():
    """content 为 JSON 数组（非 dict）时抛 DialogueFillError"""
    with patch("bt_cli.ai.dialogue_filler.LLMClient") as cls:
        mock = MagicMock()
        mock.chat.return_value = {"content": json.dumps([1, 2, 3]),
                                  "model": "m", "usage": {}}
        cls.from_config.return_value = mock
        filler = DialogueFiller()
        with pytest.raises(DialogueFillError, match="应为对象"):
            filler.propose_questions(_structure(), "任务")
import json
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
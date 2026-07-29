# tests/test_scheduler.py
"""定时调度器单元测试"""
import os
import sys
import json
import tempfile
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
from bt_cli.scheduler import (
    ScheduleTask, CronMatcher, Scheduler, parse_interval,
)


# ── parse_interval ──

def test_parse_interval_seconds():
    assert parse_interval("30s") == 30.0


def test_parse_interval_minutes():
    assert parse_interval("5m") == 300.0


def test_parse_interval_hours():
    assert parse_interval("2h") == 7200.0


def test_parse_interval_invalid():
    assert parse_interval("invalid") is None
    assert parse_interval("") is None
    assert parse_interval(None) is None


def test_parse_interval_uppercase():
    assert parse_interval("30S") == 30.0
    assert parse_interval("5M") == 300.0


# ── CronMatcher ──

def test_cron_match_every_minute():
    """* * * * * 每分钟都匹配"""
    dt = datetime(2026, 7, 28, 10, 30, 0)
    assert CronMatcher.match("* * * * *", dt)


def test_cron_match_specific_minute():
    """30 * * * * 第30分钟匹配"""
    assert CronMatcher.match("30 * * * *", datetime(2026, 7, 28, 10, 30, 0))
    assert not CronMatcher.match("30 * * * *", datetime(2026, 7, 28, 10, 31, 0))


def test_cron_match_specific_hour():
    """0 10 * * * 每天10:00匹配"""
    assert CronMatcher.match("0 10 * * *", datetime(2026, 7, 28, 10, 0, 0))
    assert not CronMatcher.match("0 10 * * *", datetime(2026, 7, 28, 11, 0, 0))


def test_cron_match_range():
    """0 9-17 * * 1-5 工作日工作时间"""
    dt = datetime(2026, 7, 28, 14, 0, 0)  # 周二 14:00
    assert CronMatcher.match("0 9-17 * * 1-5", dt)


def test_cron_match_step():
    """*/15 * * * * 每15分钟"""
    assert CronMatcher.match("*/15 * * * *", datetime(2026, 7, 28, 10, 0, 0))
    assert CronMatcher.match("*/15 * * * *", datetime(2026, 7, 28, 10, 15, 0))
    assert CronMatcher.match("*/15 * * * *", datetime(2026, 7, 28, 10, 30, 0))
    assert not CronMatcher.match("*/15 * * * *", datetime(2026, 7, 28, 10, 7, 0))


def test_cron_match_comma():
    """0,30 * * * * 第0和30分钟"""
    assert CronMatcher.match("0,30 * * * *", datetime(2026, 7, 28, 10, 0, 0))
    assert CronMatcher.match("0,30 * * * *", datetime(2026, 7, 28, 10, 30, 0))
    assert not CronMatcher.match("0,30 * * * *", datetime(2026, 7, 28, 10, 15, 0))


def test_cron_match_invalid():
    """无效表达式不匹配"""
    assert not CronMatcher.match("invalid", datetime.now())
    assert not CronMatcher.match("* * *", datetime.now())  # 字段数不足


def test_cron_match_weekday():
    """cron 周几字段使用标准约定：0=周日, 1=周一, ..., 6=周六

    Python datetime.weekday(): 周一=0..周日=6，需转换为 cron 约定。
    验证关键边界：cron 0 只匹配周日，cron 1 只匹配周一。
    """
    # 2026-07-26 是周日（weekday()==6），cron 0 应匹配
    sunday = datetime(2026, 7, 26, 10, 0, 0)
    assert CronMatcher.match("0 10 * * 0", sunday)
    # 2026-07-27 是周一（weekday()==0），cron 0 不应匹配
    monday = datetime(2026, 7, 27, 10, 0, 0)
    assert not CronMatcher.match("0 10 * * 0", monday)
    # cron 1 应匹配周一，不匹配周二
    assert CronMatcher.match("0 10 * * 1", monday)
    tuesday = datetime(2026, 7, 28, 10, 0, 0)
    assert not CronMatcher.match("0 10 * * 1", tuesday)
    # cron 6 应匹配周六
    saturday = datetime(2026, 8, 1, 10, 0, 0)
    assert CronMatcher.match("0 10 * * 6", saturday)


# ── ScheduleTask ──

def test_schedule_task_to_dict():
    task = ScheduleTask(
        task_id="t1", name="测试", tree_file="tree.json",
        cron="0 * * * *", headless=True
    )
    d = task.to_dict()
    assert d["task_id"] == "t1"
    assert d["name"] == "测试"
    assert d["tree_file"] == "tree.json"
    assert d["cron"] == "0 * * * *"
    assert d["headless"] is True
    assert d["enabled"] is True
    assert d["run_count"] == 0


def test_schedule_task_from_dict():
    data = {
        "task_id": "t1", "name": "测试", "tree_file": "tree.json",
        "cron": "0 * * * *", "interval": None, "once": None,
        "headless": False, "enabled": False,
        "last_run": "2026-07-28T10:00:00", "next_run": None,
        "run_count": 3,
    }
    task = ScheduleTask.from_dict(data)
    assert task.task_id == "t1"
    assert task.enabled is False
    assert task.run_count == 3
    assert task.last_run == "2026-07-28T10:00:00"


def test_schedule_task_roundtrip():
    """to_dict → from_dict 应保留所有字段"""
    task = ScheduleTask(
        task_id="t1", name="测试", tree_file="tree.json",
        interval="30s", headless=False, enabled=False
    )
    task.run_count = 5
    task.last_run = "2026-07-28T10:00:00"
    data = task.to_dict()
    restored = ScheduleTask.from_dict(data)
    assert restored.task_id == task.task_id
    assert restored.interval == task.interval
    assert restored.run_count == task.run_count
    assert restored.last_run == task.last_run


# ── Scheduler ──

@pytest.fixture
def temp_scheduler(tmp_path, monkeypatch):
    """使用临时目录的 Scheduler，避免污染用户配置"""
    schedules_file = tmp_path / "schedules.json"
    monkeypatch.setattr(Scheduler, "SCHEDULES_FILE", str(schedules_file))
    monkeypatch.setattr(Scheduler, "DATA_DIR", str(tmp_path))
    # 创建临时行为树文件供测试使用（add_task 现在会验证文件存在）
    tree_file = tmp_path / "tree.json"
    tree_file.write_text("{}")
    scheduler = Scheduler()
    scheduler._test_tree_file = str(tree_file)
    return scheduler


def test_scheduler_add_task(temp_scheduler):
    task_id = temp_scheduler.add_task(
        name="测试任务", tree_file=temp_scheduler._test_tree_file,
        cron="0 * * * *", headless=True
    )
    assert task_id.startswith("task_")
    tasks = temp_scheduler.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].name == "测试任务"


def test_scheduler_remove_task(temp_scheduler):
    task_id = temp_scheduler.add_task(name="t1", tree_file=temp_scheduler._test_tree_file, cron="0 * * * *")
    assert temp_scheduler.remove_task(task_id) is True
    assert len(temp_scheduler.list_tasks()) == 0
    # 删除不存在的任务返回 False
    assert temp_scheduler.remove_task("nonexistent") is False


def test_scheduler_enable_disable_task(temp_scheduler):
    task_id = temp_scheduler.add_task(name="t1", tree_file=temp_scheduler._test_tree_file, cron="0 * * * *")
    assert temp_scheduler.disable_task(task_id) is True
    task = temp_scheduler.list_tasks()[0]
    assert task.enabled is False
    assert temp_scheduler.enable_task(task_id) is True
    task = temp_scheduler.list_tasks()[0]
    assert task.enabled is True


def test_scheduler_persistence(tmp_path, monkeypatch):
    """任务应持久化到文件，重新加载后仍存在"""
    schedules_file = tmp_path / "schedules.json"
    monkeypatch.setattr(Scheduler, "SCHEDULES_FILE", str(schedules_file))
    monkeypatch.setattr(Scheduler, "DATA_DIR", str(tmp_path))
    # 创建临时行为树文件（add_task 现在会验证文件存在）
    tree_file = tmp_path / "tree.json"
    tree_file.write_text("{}")

    s1 = Scheduler()
    task_id = s1.add_task(name="持久任务", tree_file=str(tree_file), cron="0 * * * *")

    # 重新加载
    s2 = Scheduler()
    tasks = s2.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].task_id == task_id
    assert tasks[0].name == "持久任务"


def test_scheduler_should_run_cron(temp_scheduler):
    """cron 模式下，匹配时间应执行"""
    task = ScheduleTask(
        task_id="t1", name="test", tree_file="tree.json",
        cron="30 10 * * *", headless=True
    )
    # 10:30 匹配
    assert temp_scheduler._should_run(task, datetime(2026, 7, 28, 10, 30, 0))
    # 10:31 不匹配（分钟不对）
    assert not temp_scheduler._should_run(task, datetime(2026, 7, 28, 10, 31, 0))


def test_scheduler_should_run_interval(temp_scheduler):
    """interval 模式下，间隔到达应执行"""
    task = ScheduleTask(
        task_id="t1", name="test", tree_file="tree.json",
        interval="60s", headless=True
    )
    # 首次执行
    assert temp_scheduler._should_run(task, datetime(2026, 7, 28, 10, 0, 0))
    # 设置上次执行时间，60 秒后应再次执行
    task.last_run = datetime(2026, 7, 28, 10, 0, 0).isoformat()
    assert temp_scheduler._should_run(task, datetime(2026, 7, 28, 10, 1, 0))
    # 30 秒后不应执行
    assert not temp_scheduler._should_run(task, datetime(2026, 7, 28, 10, 0, 30, 0))


def test_scheduler_should_run_once(temp_scheduler):
    """once 模式下，到达指定时间且未执行过应执行"""
    task = ScheduleTask(
        task_id="t1", name="test", tree_file="tree.json",
        once="2026-07-28T10:00:00", headless=True
    )
    # 时间已到
    assert temp_scheduler._should_run(task, datetime(2026, 7, 28, 10, 0, 1))
    # 时间未到
    assert not temp_scheduler._should_run(task, datetime(2026, 7, 28, 9, 59, 59))
    # 已执行过则不再执行
    task.last_run = datetime(2026, 7, 28, 10, 0, 0).isoformat()
    assert not temp_scheduler._should_run(task, datetime(2026, 7, 28, 11, 0, 0))


def test_scheduler_should_run_disabled(temp_scheduler):
    """禁用的任务在 _should_run 中仍按时间匹配（enabled 检查在 _run_loop 中）"""
    task = ScheduleTask(
        task_id="t1", name="test", tree_file="tree.json",
        cron="* * * * *", headless=True, enabled=False
    )
    # _should_run 只检查时间条件，enabled 检查由 _run_loop 负责
    # 这里验证时间匹配正常
    assert temp_scheduler._should_run(task, datetime(2026, 7, 28, 10, 0, 0))
    # enabled=False 应在外层循环中被跳过，不影响 _should_run 本身
    assert task.enabled is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

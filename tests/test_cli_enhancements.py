# tests/test_cli_enhancements.py
"""CLI 增强功能测试 (C1, R3, R5, E1, E2)"""
import inspect
from unittest.mock import patch, MagicMock


def _make_scheduler():
    """创建 Scheduler 实例，patch _save 避免写入真实文件"""
    from bt_cli.scheduler import Scheduler
    scheduler = Scheduler.__new__(Scheduler)
    scheduler._tasks = {}
    scheduler._thread = None
    scheduler._stop_event = __import__('threading').Event()
    return scheduler


def test_plugin_unload_command_exists():
    """测试 plugin unload 子命令存在 (C1)"""
    import cli
    source = inspect.getsource(cli)
    assert "unload" in source, "cli.py 中未找到 unload 子命令"


def test_plugin_unload_handler_exists():
    """测试 plugin.py 中有 _unload_plugin 处理函数 (C1)"""
    from bt_cli.commands import plugin
    source = inspect.getsource(plugin)
    assert "_unload_plugin" in source, "plugin.py 中未找到 _unload_plugin 函数"
    assert "unload" in source, "plugin.py 中未找到 unload action 分支"


def test_errors_module_exists():
    """测试 bt_cli/errors.py 模块存在且退出码正确 (E1)"""
    from bt_cli.errors import (
        exit_with_code, EXIT_SUCCESS, EXIT_GENERIC_ERROR,
        EXIT_FILE_NOT_FOUND, EXIT_PLUGIN_ERROR, EXIT_INTERRUPTED,
    )
    assert EXIT_SUCCESS == 0
    assert EXIT_GENERIC_ERROR == 1
    assert EXIT_FILE_NOT_FOUND == 3
    assert EXIT_PLUGIN_ERROR == 6
    assert EXIT_INTERRUPTED == 130


def test_schedule_add_validates_file():
    """测试 schedule add 验证文件存在 (R5)"""
    scheduler = _make_scheduler()
    scheduler._save = MagicMock()  # 避免写入文件
    # 不存在的文件应返回空字符串表示失败
    result = scheduler.add_task("test", "/nonexistent/file.json", interval="30s")
    assert result == "" or result is None, f"期望空字符串或 None, 得到 {result}"


def test_scheduler_execute_returns_status():
    """测试调度器执行任务记录状态 (E2)"""
    from bt_cli.scheduler import ScheduleTask
    scheduler = _make_scheduler()
    scheduler._save = MagicMock()  # 避免写入文件
    task = ScheduleTask("test_id", "test", "/nonexistent/file.json", interval="30s")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        scheduler._execute_task(task)
        assert hasattr(task, 'last_run_status'), "task 缺少 last_run_status 属性"
        assert task.last_run_status == "success", f"期望 success, 得到 {task.last_run_status}"


def test_scheduler_execute_failed_status():
    """测试调度器执行失败记录状态 (E2)"""
    from bt_cli.scheduler import ScheduleTask
    scheduler = _make_scheduler()
    scheduler._save = MagicMock()  # 避免写入文件
    task = ScheduleTask("test_id2", "test", "/nonexistent/file.json", interval="30s")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        scheduler._execute_task(task)
        assert task.last_run_status is not None
        assert "failed" in task.last_run_status, f"期望包含 failed, 得到 {task.last_run_status}"

# tests/test_daemon_platform.py
"""daemon 命令平台兼容性测试"""
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_stop_daemon_on_windows():
    """测试 Windows 上停止守护进程使用 taskkill"""
    from bt_cli.commands import daemon

    with tempfile.TemporaryDirectory() as tmpdir:
        pid_file = os.path.join(tmpdir, "daemon.pid")
        with open(pid_file, "w") as f:
            f.write("12345")

        with patch.object(daemon, "DAEMON_PID_FILE", pid_file), \
             patch("platform.system", return_value="Windows"), \
             patch("subprocess.call", return_value=0) as mock_call:
            daemon._stop_daemon()
            mock_call.assert_called_once_with(["taskkill", "/PID", "12345", "/F"])


def test_stop_daemon_on_linux():
    """测试 Linux 上停止守护进程使用 SIGTERM"""
    from bt_cli.commands import daemon

    with tempfile.TemporaryDirectory() as tmpdir:
        pid_file = os.path.join(tmpdir, "daemon.pid")
        with open(pid_file, "w") as f:
            f.write("12345")

        with patch.object(daemon, "DAEMON_PID_FILE", pid_file), \
             patch("platform.system", return_value="Linux"), \
             patch("os.kill") as mock_kill:
            daemon._stop_daemon()
            mock_kill.assert_called_once()

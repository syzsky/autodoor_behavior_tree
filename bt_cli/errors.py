"""CLI 标准退出码和错误处理"""
import sys

EXIT_SUCCESS = 0
EXIT_GENERIC_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_FILE_NOT_FOUND = 3
EXIT_DEPENDENCY_MISSING = 4
EXIT_AUTH_FAILED = 5
EXIT_PLUGIN_ERROR = 6
EXIT_INTERRUPTED = 130


def exit_with_code(code: int, message: str = ""):
    """以指定退出码退出，可选打印消息"""
    if message:
        print(message)
    sys.exit(code)

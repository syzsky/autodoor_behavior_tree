"""资源路径工具 — 兼容 PyInstaller 打包环境

PyInstaller 打包后：
- 源码中的 __file__ 可能指向 _internal 目录内的 .py / .pyc 文件
- 数据文件（如 .md prompt）需通过 datas 项打包到对应相对路径
- sys._MEIPASS 指向 _internal 目录（PyInstaller 运行时根）

本模块提供统一的 get_resource_path() 函数，
在开发环境和 PyInstaller 环境下均能正确解析资源文件路径。

用法：
    from bt_cli.ai.resource_path import get_resource_path
    prompt_path = get_resource_path(__file__, "prompts", "intent_analysis.md")
"""
import os
import sys


def _is_pyinstaller() -> bool:
    """判断是否运行在 PyInstaller 打包环境中"""
    return hasattr(sys, "_MEIPASS")


def get_resource_path(ref_file: str, *path_parts: str) -> str:
    """获取资源文件的绝对路径

    优先按 __file__ 相对路径解析（开发环境），
    若文件不存在且运行在 PyInstaller 中，则按 sys._MEIPASS 相对路径兜底。

    Args:
        ref_file: 参照文件的 __file__（调用方传自身 __file__ 即可）
        *path_parts: 相对于 ref_file 所在目录的路径片段

    Returns:
        资源文件的绝对路径
    """
    # 方式 1：按 __file__ 相对路径解析（开发环境 & PyInstaller 数据文件模式）
    base_dir = os.path.dirname(os.path.abspath(ref_file))
    candidate = os.path.join(base_dir, *path_parts)
    if os.path.exists(candidate):
        return candidate

    # 方式 2：PyInstaller 环境下按 _MEIPASS 兜底
    if _is_pyinstaller():
        # 计算相对于项目根的路径：从 ref_file 中提取包路径部分
        # ref_file 形如 .../bt_cli/ai/xxx.py，需得到 bt_cli/ai/ 相对路径
        rel_dir = _extract_package_relpath(ref_file)
        if rel_dir:
            candidate = os.path.join(sys._MEIPASS, rel_dir, *path_parts)
            if os.path.exists(candidate):
                return candidate

        # 再兜底：直接在 _MEIPASS 下按 path_parts 查找
        candidate = os.path.join(sys._MEIPASS, *path_parts)
        if os.path.exists(candidate):
            return candidate

    # 最终仍返回候选路径（让调用方 open 时抛标准 FileNotFoundError）
    return os.path.join(base_dir, *path_parts)


def _extract_package_relpath(file_path: str) -> str:
    """从 __file__ 中提取包相对路径（如 bt_cli/ai/）

    通过向上查找包含 __init__.py 的目录来识别包根。
    在 PyInstaller 环境中，文件可能在 _internal 目录下，
    我们提取 bt_cli/bt_gui/bt_nodes/bt_utils/config 等已知包名之后的相对路径。
    """
    abs_path = os.path.abspath(file_path)
    dir_path = os.path.dirname(abs_path)

    # 已知包名列表（项目内的顶级包）
    known_packages = ["bt_cli", "bt_gui", "bt_nodes", "bt_core", "bt_utils", "config", "plugins"]

    # 从路径中查找第一个已知包名的位置
    parts = dir_path.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part in known_packages:
            # 返回从该包名开始的相对路径
            return "/".join(parts[i:])

    return ""


def get_cli_path() -> str:
    """获取 cli.py 的路径（试运行用）

    开发环境：项目根目录下的 cli.py
    PyInstaller 环境：_internal 目录下的 cli.py（需在 spec 的 datas 中包含）
    """
    if _is_pyinstaller():
        candidate = os.path.join(sys._MEIPASS, "cli.py")
        if os.path.exists(candidate):
            return candidate

    # 开发环境：从 bt_cli/ai/ 向上两级到项目根
    current_dir = os.path.dirname(os.path.abspath(__file__))  # bt_cli/ai/
    project_root = os.path.dirname(os.path.dirname(current_dir))  # 项目根
    candidate = os.path.join(project_root, "cli.py")
    if os.path.exists(candidate):
        return candidate

    return candidate  # 不存在也返回，让调用方自行处理

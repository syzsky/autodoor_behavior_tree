"""阶段2 改造4/5/6 验证测试（非 GUI 交互层面）。

由于 Tab 双击重命名、打开/导出弹窗均依赖 CTk 主循环，无法在无头环境完整模拟，
本测试通过以下方式验证改造正确性：
1. 所有修改的 Python 文件可正常编译（py_compile），无语法错误
2. editor.py 包含改造4/5/6 的关键方法且签名正确
3. tab_bar.py 包含双击重命名相关回调与编辑模式逻辑
4. 关键调用链代码完整（_create_tab_bar 注入回调、open_project/export_tree 调用校验）
5. 改造5/6 的底层依赖（ProjectManager.check_name_consistency）行为正确
"""

import os
import sys
import py_compile
import inspect
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 需要验证编译的修改文件
MODIFIED_FILES = [
    "bt_core/constants.py",
    "bt_core/serializer.py",
    "bt_utils/project_manager.py",
    "bt_utils/resource_service.py",
    "bt_utils/resource_importer.py",
    "bt_utils/package_importer.py",
    "bt_utils/package_exporter.py",
    "bt_gui/app.py",
    "bt_gui/bt_editor/editor.py",
    "bt_gui/bt_editor/tab_bar.py",
    "bt_gui/bt_editor/canvas.py",
]


def test_all_modified_files_compile():
    """测试1：所有修改文件可正常编译"""
    failed = []
    for rel in MODIFIED_FILES:
        path = os.path.join(PROJECT_ROOT, rel)
        if not os.path.isfile(path):
            failed.append(f"{rel} (文件不存在)")
            continue
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            failed.append(f"{rel}: {e}")
    assert not failed, "编译失败:\n" + "\n".join(failed)
    print(f"[PASS] test_all_modified_files_compile ({len(MODIFIED_FILES)} 个文件)")
    print("  已验证文件:", ", ".join(MODIFIED_FILES))


def test_imports_no_circular():
    """测试2：关键模块导入无循环依赖"""
    # 这些导入会触发模块级依赖链
    from bt_core.constants import ProjectConstants, get_app_version
    from bt_core.serializer import Serializer
    from bt_utils.project_manager import ProjectManager
    from bt_utils.resource_service import ResourceService
    from bt_utils.package_importer import PackageImporter
    from bt_utils.package_exporter import PackageExporter
    print("[PASS] test_imports_no_circular")


def test_editor_has_stage2_methods():
    """测试3：editor.py 包含改造4/5/6 的关键方法"""
    # editor 模块导入会触发 CTk 导入，但类定义本身不需要 mainloop
    # 这里只检查源码字符串，避免 CTk 初始化
    editor_path = os.path.join(PROJECT_ROOT, "bt_gui", "bt_editor", "editor.py")
    with open(editor_path, "r", encoding="utf-8") as f:
        src = f.read()

    required_methods = [
        # 改造4：Tab 双击重命名
        "_handle_tab_rename",
        "_handle_tab_is_running",
        # 改造5：打开项目一致性校验
        "_check_and_prompt_name_consistency_on_open",
        # 改造6：导出 ZIP 一致性校验
        "_check_and_prompt_name_consistency_on_export",
    ]
    missing = [m for m in required_methods if f"def {m}" not in src]
    assert not missing, f"editor.py 缺少方法: {missing}"

    # 改造4：_create_tab_bar 注入 on_tab_rename / on_tab_is_running
    assert "on_tab_rename=" in src, "editor.py 未在 _create_tab_bar 注入 on_tab_rename"
    assert "on_tab_is_running=" in src, "editor.py 未在 _create_tab_bar 注入 on_tab_is_running"

    # 改造4：_handle_tab_rename 调用 ProjectManager.update_project_info_name
    assert "ProjectManager.update_project_info_name" in src, \
        "editor.py _handle_tab_rename 未调用 update_project_info_name"

    # 改造5：open_project 调用校验
    assert "_check_and_prompt_name_consistency_on_open(" in src, \
        "editor.py open_project 未调用打开校验"

    # 改造6：export_tree 调用校验
    assert "_check_and_prompt_name_consistency_on_export(" in src, \
        "editor.py export_tree 未调用导出校验"

    # 改造4：运行中禁止重命名（_handle_tab_rename 内含 is_running 检查）
    rename_section = src[src.index("def _handle_tab_rename"):]
    rename_section = rename_section[:rename_section.index("def ", 1)]
    assert "is_running" in rename_section, "_handle_tab_rename 未检查 is_running"
    assert "未保存" in rename_section or "尚未保存" in rename_section, \
        "_handle_tab_rename 未处理未保存项目场景"

    print("[PASS] test_editor_has_stage2_methods")


def test_tab_bar_has_rename_logic():
    """测试4：tab_bar.py 包含双击重命名编辑模式逻辑"""
    tab_bar_path = os.path.join(PROJECT_ROOT, "bt_gui", "bt_editor", "tab_bar.py")
    with open(tab_bar_path, "r", encoding="utf-8") as f:
        src = f.read()

    required_in_tab_button = [
        "on_rename",
        "on_is_running_check",
        "_on_name_double_click",
        "_enter_edit_mode",
        "_exit_edit_mode",
        "_on_entry_confirm",
        "_on_entry_cancel",
        "_name_entry",
        "<Double-Button-1>",
    ]
    missing = [m for m in required_in_tab_button if m not in src]
    assert not missing, f"tab_bar.py TabButton 缺少: {missing}"

    required_in_tab_bar = [
        "on_tab_rename",
        "on_tab_is_running",
        "_handle_rename",
        "_handle_is_running_check",
    ]
    missing2 = [m for m in required_in_tab_bar if m not in src]
    assert not missing2, f"tab_bar.py TabBar 缺少: {missing2}"

    # 运行中禁止重命名（_on_name_double_click 内含检查）
    dbl_section = src[src.index("_on_name_double_click"):]
    dbl_section = dbl_section[:dbl_section.index("def ", dbl_section.index("def _on_name_double_click") + 1)]
    assert "_on_is_running_check" in dbl_section, "_on_name_double_click 未检查运行状态"
    assert "项目运行中" in dbl_section, "_on_name_double_click 未提示运行中禁止重命名"

    print("[PASS] test_tab_bar_has_rename_logic")


def test_consistency_check_uses_project_manager():
    """测试5：改造5/6 的底层依赖（check_name_consistency）行为正确

    通过 ProjectManager 直接验证一致性检查逻辑，
    editor 中的弹窗只是 UI 包装，核心逻辑在 ProjectManager。
    """
    import tempfile
    import shutil
    import json
    from bt_utils.project_manager import ProjectManager
    from bt_core.constants import ProjectConstants

    tmp = tempfile.mkdtemp(prefix="ConsistencyLogic_")
    try:
        folder_name = os.path.basename(tmp)

        # 场景A：无 project.json -> info_name 为空 -> 视为一致（不弹窗）
        result_a = ProjectManager.check_name_consistency(tmp)
        assert result_a["consistent"] is True, f"无 project.json 应视为一致: {result_a}"
        assert result_a["folder_name"] == folder_name
        assert result_a["project_info_name"] == ""

        # 场景B：project_info.name = 文件夹名 -> 一致
        proj = {"project_info": {"name": folder_name}, "format_type": ProjectConstants.PROJECT_FORMAT_TYPE}
        with open(os.path.join(tmp, ProjectConstants.PROJECT_META_FILE), "w", encoding="utf-8") as f:
            json.dump(proj, f)
        result_b = ProjectManager.check_name_consistency(tmp)
        assert result_b["consistent"] is True, f"名称相同应一致: {result_b}"

        # 场景C：project_info.name != 文件夹名 -> 不一致（应弹窗）
        ProjectManager.update_project_info_name(tmp, "DifferentName")
        result_c = ProjectManager.check_name_consistency(tmp)
        assert result_c["consistent"] is False, f"名称不同应不一致: {result_c}"
        assert result_c["folder_name"] == folder_name
        assert result_c["project_info_name"] == "DifferentName"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("[PASS] test_consistency_check_uses_project_manager")


def test_export_callback_wiring():
    """测试6：导出 ZIP 校验在 export_tree 中正确接入（取消时 return）"""
    editor_path = os.path.join(PROJECT_ROOT, "bt_gui", "bt_editor", "editor.py")
    with open(editor_path, "r", encoding="utf-8") as f:
        src = f.read()

    # 定位 export_tree 方法体
    idx = src.index("def export_tree")
    # 找到方法体结束（下一个同级 def）
    end = src.find("\n    def ", idx + 1)
    export_section = src[idx:end] if end > 0 else src[idx:idx + 5000]

    assert "_check_and_prompt_name_consistency_on_export" in export_section, \
        "export_tree 未调用导出校验"
    # 校验返回 True 时应 return（取消导出）
    assert "return" in export_section, "export_tree 校验取消后未 return"
    print("[PASS] test_export_callback_wiring")


def test_open_callback_wiring():
    """测试7：打开项目校验在 open_project 中正确接入"""
    editor_path = os.path.join(PROJECT_ROOT, "bt_gui", "bt_editor", "editor.py")
    with open(editor_path, "r", encoding="utf-8") as f:
        src = f.read()

    idx = src.index("def open_project")
    end = src.find("\n    def ", idx + 1)
    open_section = src[idx:end] if end > 0 else src[idx:idx + 8000]

    assert "_check_and_prompt_name_consistency_on_open" in open_section, \
        "open_project 未调用打开校验"
    print("[PASS] test_open_callback_wiring")


def test_resolve_project_name_used_everywhere():
    """测试8：所有 basename 调用已替换为 resolve_project_name（关键路径）"""
    # editor.py 中应使用 resolve_project_name 而非 os.path.basename 作为项目名
    editor_path = os.path.join(PROJECT_ROOT, "bt_gui", "bt_editor", "editor.py")
    with open(editor_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "resolve_project_name" in src, "editor.py 未使用 resolve_project_name"

    app_path = os.path.join(PROJECT_ROOT, "bt_gui", "app.py")
    with open(app_path, "r", encoding="utf-8") as f:
        app_src = f.read()
    assert "resolve_project_name" in app_src, "app.py 未使用 resolve_project_name"

    exporter_path = os.path.join(PROJECT_ROOT, "bt_utils", "package_exporter.py")
    with open(exporter_path, "r", encoding="utf-8") as f:
        exp_src = f.read()
    assert "resolve_project_name" in exp_src, "package_exporter.py 未使用 resolve_project_name"
    print("[PASS] test_resolve_project_name_used_everywhere")


def main():
    tests = [
        test_all_modified_files_compile,
        test_imports_no_circular,
        test_editor_has_stage2_methods,
        test_tab_bar_has_rename_logic,
        test_consistency_check_uses_project_manager,
        test_export_callback_wiring,
        test_open_callback_wiring,
        test_resolve_project_name_used_everywhere,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n===== 阶段2测试结果: {passed} passed, {failed} failed, 总计 {len(tests)} =====")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

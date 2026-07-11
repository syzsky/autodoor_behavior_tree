"""全面集成测试：模拟项目完整生命周期，验证阶段1+2所有改造点的协同工作。

工作流：
1. 创建项目 -> 验证常量/目录/无死代码
2. 修改 project_info.name 与文件夹名不一致 -> 验证 check_name_consistency 识别
3. 构造带反斜杠路径的 tree.json -> 验证保存时路径规范化
4. 导出 ZIP -> 验证 ZIP 名使用文件夹名
5. 导入 ZIP 到新位置 -> 验证 project_info.name 强制同步
6. 反序列化 tree.json -> 验证 format_type 兼容旧值
7. 序列化子树引用 -> 验证 ref.path 规范化
8. resolve_project_name 在所有边界场景正确
"""

import os
import sys
import json
import shutil
import tempfile
import zipfile
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_full_project_lifecycle():
    """全面测试：项目完整生命周期"""
    from bt_utils.project_manager import ProjectManager
    from bt_utils.package_importer import PackageImporter
    from bt_utils.package_exporter import PackageExporter
    from bt_core.constants import ProjectConstants
    from bt_core.serializer import Serializer
    from bt_core.nodes import StartNode, SequenceNode, SubtreeNode
    from bt_core.config import NodeConfig

    parent = tempfile.mkdtemp(prefix="FullLifecycle_")
    try:
        # ===== 步骤1：创建项目 =====
        proj_name = "MyBehaviorTree"
        proj_root = os.path.join(parent, proj_name)
        pm = ProjectManager(proj_root)
        pm.create_project(proj_name)

        assert os.path.isdir(proj_root)
        with open(os.path.join(proj_root, ProjectConstants.PROJECT_META_FILE), "r", encoding="utf-8") as f:
            proj = json.load(f)
        assert proj["format_type"] == ProjectConstants.PROJECT_FORMAT_TYPE
        assert proj["project_info"]["name"] == proj_name
        assert "resources" not in proj  # 死代码已清除
        print("  [1/8] 创建项目 OK")

        # ===== 步骤2：制造不一致并校验 =====
        ProjectManager.update_project_info_name(proj_root, "MismatchedName")
        result = ProjectManager.check_name_consistency(proj_root)
        assert not result["consistent"]
        assert result["folder_name"] == proj_name
        assert result["project_info_name"] == "MismatchedName"
        # 模拟用户选择"同步"：把 project_info.name 改回文件夹名
        ProjectManager.update_project_info_name(proj_root, proj_name)
        result2 = ProjectManager.check_name_consistency(proj_root)
        assert result2["consistent"]
        print("  [2/8] 一致性校验 OK")

        # ===== 步骤3：构造带反斜杠路径的 tree.json 并保存 =====
        root = StartNode(config=NodeConfig(name="root"))
        seq = SequenceNode(config=NodeConfig(name="seq"))
        # 模拟 Windows 路径（反斜杠）
        subtree = SubtreeNode(config=NodeConfig(
            name="sub",
            extra={"subtree_path": ".\\subtrees\\child_tree"},
        ))
        root.add_child(seq)
        seq.add_child(subtree)

        tree_data = Serializer.serialize(root)
        # 保存到项目
        pm.save_project(tree_data)

        # 读取 tree.json 验证路径已规范化
        with open(os.path.join(proj_root, ProjectConstants.MAIN_TREE_FILE), "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["version"] == ProjectConstants.TREE_FORMAT_VERSION
        assert saved["format_type"] == ProjectConstants.TREE_FORMAT_TYPE
        for nid, nd in saved["nodes"].items():
            cfg = nd.get("config", {})
            if "subtree_path" in cfg:
                assert "\\" not in cfg["subtree_path"], \
                    f"tree.json 中 subtree_path 未规范化: {cfg['subtree_path']}"
                assert cfg["subtree_path"] == "./subtrees/child_tree"
        print("  [3/8] 路径规范化保存 OK")

        # ===== 步骤4：导出 ZIP =====
        zip_path = os.path.join(parent, "export.zip")
        exporter = PackageExporter(proj_root)
        result_path = exporter.export_to_zip(zip_path)
        assert result_path and os.path.isfile(result_path)
        # ZIP 默认名应使用 resolve_project_name（文件夹名）
        # 这里显式指定了路径，验证 ZIP 内容即可
        with zipfile.ZipFile(result_path, "r") as zf:
            names = zf.namelist()
            assert any("project.json" in n for n in names), "ZIP 缺少 project.json"
            assert any("tree.json" in n for n in names), "ZIP 缺少 tree.json"
        print("  [4/8] 导出 ZIP OK")

        # ===== 步骤5：导入 ZIP 到新位置，验证强制同步 =====
        import_dir = os.path.join(parent, "imports")
        os.makedirs(import_dir, exist_ok=True)
        importer = PackageImporter()
        ok, msg, imported_root = importer.import_from_zip(result_path, import_dir)
        assert ok, f"导入失败: {msg}"

        # 导入后 project_info.name 必须与文件夹名一致
        result3 = ProjectManager.check_name_consistency(imported_root)
        assert result3["consistent"], f"导入后不一致: {result3}"
        assert result3["folder_name"] == result3["project_info_name"]
        print("  [5/8] ZIP 导入强制同步 OK")

        # ===== 步骤6：反序列化 tree.json，验证 format_type 兼容 =====
        loaded_root, canvas_state, editor_state = Serializer.load_from_file(
            os.path.join(proj_root, ProjectConstants.MAIN_TREE_FILE)
        )
        assert loaded_root is not None, "反序列化根节点为空"
        assert loaded_root.name == "root"
        # 子树节点应保留规范化后的路径
        found_subtree = False
        for child in loaded_root.children:
            for grandchild in child.children:
                if isinstance(grandchild, SubtreeNode):
                    assert "\\" not in grandchild.subtree_path, \
                        f"反序列化后路径含反斜杠: {grandchild.subtree_path}"
                    found_subtree = True
        assert found_subtree, "未找到 SubtreeNode"
        print("  [6/8] 反序列化兼容 OK")

        # ===== 步骤7：serialize_with_subtrees 验证 ref.path 规范化 =====
        refs_data = Serializer.serialize_with_subtrees(root, project_root=proj_root)
        refs = refs_data.get("subtree_references", {})
        assert len(refs) >= 1
        for nid, ref in refs.items():
            assert "\\" not in ref["path"], f"ref.path 未规范化: {ref['path']}"
        print("  [7/8] 子树引用路径规范化 OK")

        # ===== 步骤8：resolve_project_name 边界场景 =====
        assert ProjectManager.resolve_project_name(proj_root) == proj_name
        assert ProjectManager.resolve_project_name("") == "未命名"
        assert ProjectManager.resolve_project_name(proj_root + os.sep) == proj_name
        assert ProjectManager.resolve_project_name(os.path.join(proj_root, "subtrees")) == "subtrees"
        print("  [8/8] resolve_project_name 边界 OK")

    finally:
        shutil.rmtree(parent, ignore_errors=True)

    print("[PASS] test_full_project_lifecycle")


def test_old_format_type_backward_compat():
    """全面测试：旧 format_type 向后兼容加载"""
    from bt_core.serializer import Serializer
    from bt_core.constants import ProjectConstants
    import warnings

    tmp = tempfile.mkdtemp(prefix="OldFormat_")
    try:
        tree_file = os.path.join(tmp, "old_tree.json")
        # 模拟旧格式文件（format_type = behavior_tree_editor, version = 2.0）
        old_data = {
            "version": "2.0",
            "format_type": "behavior_tree_editor",
            "root_node": None,
            "nodes": {},
            "connections": [],
        }
        with open(tree_file, "w", encoding="utf-8") as f:
            json.dump(old_data, f)

        # 应能加载（向后兼容，仅警告不报错）
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            root, _, _ = Serializer.load_from_file(tree_file)
        # 空树返回 None 根节点是正常的
        assert root is None
        print("[PASS] test_old_format_type_backward_compat")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_zip_default_name_uses_folder_name():
    """全面测试：ZIP 默认名使用文件夹名（resolve_project_name）"""
    from bt_utils.project_manager import ProjectManager
    from bt_utils.package_exporter import PackageExporter

    parent = tempfile.mkdtemp(prefix="ZipDefaultName_")
    try:
        proj_name = "UniqueProjectName"
        proj_root = os.path.join(parent, proj_name)
        pm = ProjectManager(proj_root)
        pm.create_project(proj_name)

        # 不指定 output_path，应使用 resolve_project_name 生成默认名
        exporter = PackageExporter(proj_root)
        # 在 parent 目录下生成
        cwd = os.getcwd()
        os.chdir(parent)
        try:
            default_zip = exporter.export_to_zip(None)
        finally:
            os.chdir(cwd)

        assert default_zip, "默认 ZIP 路径为空"
        # 默认名应为 "{文件夹名}.zip"
        expected = os.path.join(parent, f"{proj_name}.zip")
        assert os.path.isfile(expected), f"默认 ZIP 名未使用文件夹名, 期望 {expected}, 实际 {default_zip}"
        print("[PASS] test_zip_default_name_uses_folder_name")
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def main():
    tests = [
        test_full_project_lifecycle,
        test_old_format_type_backward_compat,
        test_zip_default_name_uses_folder_name,
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
    print(f"\n===== 全面测试结果: {passed} passed, {failed} failed, 总计 {len(tests)} =====")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

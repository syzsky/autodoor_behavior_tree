"""阶段2-改造8 路径规范化 + 阶段1回归 端到端测试。

验证点：
1. Serializer._normalize_node_paths 将反斜杠转为正斜杠
2. canvas.get_tree_data() 输出统一 version/format_type 和正斜杠路径
3. 非字符串/空值字段不被破坏
4. ProjectConstants.RESOURCE_PATH_KEYS 与 ResourceService.RESOURCE_KEYS 一致
5. format_type/version 在所有序列化路径上一致
6. 阶段1回归：resolve_project_name / check_name_consistency / update_project_info_name
"""

import os
import sys
import json
import shutil
import tempfile
import traceback

# 确保项目根目录在 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_normalize_node_paths_basic():
    """测试1：基础反斜杠 -> 正斜杠"""
    from bt_core.serializer import Serializer
    from bt_core.constants import ProjectConstants

    node_dict = {
        "id": "n1",
        "type": "ActionNode",
        "config": {
            "template_path": ".\\images\\templates\\foo.png",
            "script_path": ".\\scripts\\script\\bar.py",
            "code_path": "scripts\\code\\baz.py",
            "sound_path": ".\\audio\\alarms\\beep.wav",
            "file_path": "data\\config\\cfg.json",
            "subtree_path": ".\\subtrees\\child",
        },
    }
    Serializer._normalize_node_paths(node_dict)
    cfg = node_dict["config"]
    assert cfg["template_path"] == "./images/templates/foo.png", cfg["template_path"]
    assert cfg["script_path"] == "./scripts/script/bar.py", cfg["script_path"]
    assert cfg["code_path"] == "scripts/code/baz.py", cfg["code_path"]
    assert cfg["sound_path"] == "./audio/alarms/beep.wav", cfg["sound_path"]
    assert cfg["file_path"] == "data/config/cfg.json", cfg["file_path"]
    assert cfg["subtree_path"] == "./subtrees/child", cfg["subtree_path"]
    print("[PASS] test_normalize_node_paths_basic")


def test_normalize_node_paths_idempotent():
    """测试2：已是正斜杠的路径保持不变（幂等）"""
    from bt_core.serializer import Serializer

    node_dict = {
        "id": "n2",
        "config": {
            "template_path": "./images/templates/already.png",
            "script_path": "scripts/script/ok.py",
        },
    }
    Serializer._normalize_node_paths(node_dict)
    assert node_dict["config"]["template_path"] == "./images/templates/already.png"
    assert node_dict["config"]["script_path"] == "scripts/script/ok.py"
    print("[PASS] test_normalize_node_paths_idempotent")


def test_normalize_node_paths_non_string_preserved():
    """测试3：非字符串/空值字段不被破坏"""
    from bt_core.serializer import Serializer

    node_dict = {
        "id": "n3",
        "config": {
            "template_path": "",            # 空字符串跳过
            "script_path": None,            # None 跳过
            "code_path": 123,               # 非字符串跳过
            "region": [0, 0, 100, 100],     # 非路径字段不处理
            "timeout_ms": 5000,
            "name": "TestNode",
        },
    }
    Serializer._normalize_node_paths(node_dict)
    cfg = node_dict["config"]
    assert cfg["template_path"] == ""
    assert cfg["script_path"] is None
    assert cfg["code_path"] == 123
    assert cfg["region"] == [0, 0, 100, 100]
    assert cfg["timeout_ms"] == 5000
    assert cfg["name"] == "TestNode"
    print("[PASS] test_normalize_node_paths_non_string_preserved")


def test_normalize_node_paths_no_config():
    """测试4：缺 config 或 config 非 dict 时不报错"""
    from bt_core.serializer import Serializer

    Serializer._normalize_node_paths({"id": "n4"})  # 无 config
    Serializer._normalize_node_paths({"id": "n4", "config": "not_a_dict"})
    print("[PASS] test_normalize_node_paths_no_config")


def test_constants_ssot_consistency():
    """测试5：ProjectConstants.RESOURCE_PATH_KEYS 与 ResourceService.RESOURCE_KEYS 一致"""
    from bt_core.constants import ProjectConstants
    from bt_utils.resource_service import ResourceService

    keys_const = set(ProjectConstants.RESOURCE_PATH_KEYS)
    keys_svc = set(ResourceService.RESOURCE_KEYS)
    assert keys_const == keys_svc, f"SSOT 不一致: {keys_const} vs {keys_svc}"
    print("[PASS] test_constants_ssot_consistency")


def test_canvas_get_tree_data_uses_constants():
    """测试6：canvas.get_tree_data() 输出统一 version/format_type（不依赖 GUI 实例化）

    通过直接构造一个伪 canvas 对象调用 get_tree_data 验证常量引用，
    避免 CTk 初始化。这里改为验证 canvas.py 源码不再包含旧硬编码。
    """
    canvas_path = os.path.join(PROJECT_ROOT, "bt_gui", "bt_editor", "canvas.py")
    with open(canvas_path, "r", encoding="utf-8") as f:
        src = f.read()

    assert '"version": "2.0"' not in src, "canvas.py 仍硬编码 version=2.0"
    assert '"format_type": "behavior_tree_editor"' not in src, "canvas.py 仍硬编码 format_type=behavior_tree_editor"
    assert "ProjectConstants.TREE_FORMAT_VERSION" in src, "canvas.py 未引用统一常量"
    assert "ProjectConstants.TREE_FORMAT_TYPE" in src, "canvas.py 未引用统一常量"
    assert "_normalize_node_paths" in src, "canvas.py 未调用路径规范化"
    print("[PASS] test_canvas_get_tree_data_uses_constants")


def test_serializer_serialize_applies_normalization():
    """测试7：Serializer.serialize() 对节点路径做规范化（端到端）"""
    from bt_core.serializer import Serializer
    from bt_core.nodes import StartNode, SequenceNode, SubtreeNode
    from bt_core.config import NodeConfig

    # 构造一棵带反斜杠路径的小树
    root = StartNode(config=NodeConfig(name="root"))
    seq = SequenceNode(config=NodeConfig(name="seq"))
    subtree = SubtreeNode(config=NodeConfig(
        name="sub",
        extra={"subtree_path": ".\\subtrees\\child_tree"},
    ))
    root.add_child(seq)
    seq.add_child(subtree)

    data = Serializer.serialize(root)
    # 检查 version/format_type 统一
    from bt_core.constants import ProjectConstants
    assert data["version"] == ProjectConstants.TREE_FORMAT_VERSION
    assert data["format_type"] == ProjectConstants.TREE_FORMAT_TYPE

    # 检查 subtree_path 已规范化
    found = False
    for node_id, node_dict in data["nodes"].items():
        cfg = node_dict.get("config", {})
        if "subtree_path" in cfg:
            assert "\\" not in cfg["subtree_path"], f"路径未规范化: {cfg['subtree_path']}"
            assert cfg["subtree_path"] == "./subtrees/child_tree", cfg["subtree_path"]
            found = True
    assert found, "未找到 subtree_path 字段"
    print("[PASS] test_serializer_serialize_applies_normalization")


def test_serialize_with_subtrees_normalizes_ref_path():
    """测试8：serialize_with_subtrees 的 subtree_references.path 也规范化"""
    from bt_core.serializer import Serializer
    from bt_core.nodes import StartNode, SubtreeNode
    from bt_core.config import NodeConfig

    root = StartNode(config=NodeConfig(name="root"))
    subtree = SubtreeNode(config=NodeConfig(
        name="sub",
        extra={"subtree_path": ".\\subtrees\\missing_tree"},
    ))
    root.add_child(subtree)

    data = Serializer.serialize_with_subtrees(root, project_root=tempfile.gettempdir())
    refs = data.get("subtree_references", {})
    assert len(refs) == 1, f"期望 1 个引用, 实际 {len(refs)}"
    for nid, ref in refs.items():
        assert "\\" not in ref["path"], f"ref.path 未规范化: {ref['path']}"
        assert ref["path"] == "./subtrees/missing_tree", ref["path"]
    print("[PASS] test_serialize_with_subtrees_normalizes_ref_path")


# ===== 阶段1回归测试 =====

def test_stage1_resolve_project_name():
    """阶段1回归：resolve_project_name 以文件夹名为权威源"""
    from bt_utils.project_manager import ProjectManager

    tmp = tempfile.mkdtemp(prefix="MyProject_")
    try:
        name = ProjectManager.resolve_project_name(tmp)
        assert name == os.path.basename(tmp), f"期望 {os.path.basename(tmp)}, 实际 {name}"
        # 空路径
        assert ProjectManager.resolve_project_name("") == "未命名"
        # 带尾部分隔符
        assert ProjectManager.resolve_project_name(tmp + os.sep) == os.path.basename(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("[PASS] test_stage1_resolve_project_name")


def test_stage1_check_and_update_name_consistency():
    """阶段1回归：check_name_consistency + update_project_info_name"""
    from bt_utils.project_manager import ProjectManager
    from bt_core.constants import ProjectConstants

    tmp = tempfile.mkdtemp(prefix="ConsistencyTest_")
    try:
        folder_name = os.path.basename(tmp)
        # 创建 project.json，project_info.name 故意写一个不同的值
        proj = {
            "project_info": {"name": "DifferentName", "version": "1.0"},
            "format_type": ProjectConstants.PROJECT_FORMAT_TYPE,
        }
        with open(os.path.join(tmp, ProjectConstants.PROJECT_META_FILE), "w", encoding="utf-8") as f:
            json.dump(proj, f, ensure_ascii=False)

        # 校验：应识别为不一致
        result = ProjectManager.check_name_consistency(tmp)
        assert result["consistent"] is False, f"期望不一致, 实际 {result}"
        assert result["folder_name"] == folder_name
        assert result["project_info_name"] == "DifferentName"

        # 更新 project_info.name = 文件夹名
        ok = ProjectManager.update_project_info_name(tmp, folder_name)
        assert ok, "update_project_info_name 返回 False"

        # 再次校验：应一致
        result2 = ProjectManager.check_name_consistency(tmp)
        assert result2["consistent"] is True, f"期望一致, 实际 {result2}"
        assert result2["project_info_name"] == folder_name
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("[PASS] test_stage1_check_and_update_name_consistency")


def test_stage1_create_project_uses_constants():
    """阶段1回归：create_project 使用统一常量，且不含 resources 死代码字段"""
    from bt_utils.project_manager import ProjectManager
    from bt_core.constants import ProjectConstants

    tmp_parent = tempfile.mkdtemp(prefix="CreateParent_")
    try:
        proj_name = "CreatedProject"
        proj_root = os.path.join(tmp_parent, proj_name)
        pm = ProjectManager(proj_root)
        pm.create_project(proj_name)
        assert os.path.isdir(proj_root), "项目目录未创建"

        # 检查 project.json 存在且使用统一 format_type
        with open(os.path.join(proj_root, ProjectConstants.PROJECT_META_FILE), "r", encoding="utf-8") as f:
            proj = json.load(f)
        assert proj.get("format_type") == ProjectConstants.PROJECT_FORMAT_TYPE, proj.get("format_type")
        assert "resources" not in proj, "project.json 仍含 resources 死代码字段"

        # 检查初始目录结构
        for d in ProjectConstants.PROJECT_INIT_DIRS:
            assert os.path.isdir(os.path.join(proj_root, d)), f"初始目录缺失: {d}"

        # 检查 tree.json 存在
        assert os.path.isfile(os.path.join(proj_root, ProjectConstants.MAIN_TREE_FILE))
    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)
    print("[PASS] test_stage1_create_project_uses_constants")


def test_stage1_zip_import_forces_sync():
    """阶段1回归：ZIP 导入后 project_info.name 与文件夹名强制一致"""
    from bt_utils.project_manager import ProjectManager
    from bt_utils.package_importer import PackageImporter
    from bt_utils.package_exporter import PackageExporter
    from bt_core.constants import ProjectConstants

    parent = tempfile.mkdtemp(prefix="ZipSync_")
    try:
        # 1. 创建源项目
        src_name = "ZipSource"
        src_root = os.path.join(parent, src_name)
        pm = ProjectManager(src_root)
        pm.create_project(src_name)

        # 2. 故意把 project_info.name 改成与文件夹名不同
        ProjectManager.update_project_info_name(src_root, "MismatchName")

        # 3. 导出 ZIP
        zip_path = os.path.join(parent, "export.zip")
        exporter = PackageExporter(src_root)
        zip_path = exporter.export_to_zip(zip_path)
        assert zip_path and os.path.isfile(zip_path), f"导出失败: {zip_path}"

        # 4. 导入到新位置
        import_dir = os.path.join(parent, "imports")
        os.makedirs(import_dir, exist_ok=True)
        importer = PackageImporter()
        ok, msg, imported_root = importer.import_from_zip(zip_path, import_dir)
        assert ok, f"导入失败: {msg}"

        # 5. 校验：导入后 project_info.name 应 = 实际文件夹名
        result = ProjectManager.check_name_consistency(imported_root)
        assert result["consistent"], f"导入后不一致: {result}"
        assert result["folder_name"] == result["project_info_name"]
    finally:
        shutil.rmtree(parent, ignore_errors=True)
    print("[PASS] test_stage1_zip_import_forces_sync")


def main():
    tests = [
        test_normalize_node_paths_basic,
        test_normalize_node_paths_idempotent,
        test_normalize_node_paths_non_string_preserved,
        test_normalize_node_paths_no_config,
        test_constants_ssot_consistency,
        test_canvas_get_tree_data_uses_constants,
        test_serializer_serialize_applies_normalization,
        test_serialize_with_subtrees_normalizes_ref_path,
        test_stage1_resolve_project_name,
        test_stage1_check_and_update_name_consistency,
        test_stage1_create_project_uses_constants,
        test_stage1_zip_import_forces_sync,
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
    print(f"\n===== 测试结果: {passed} passed, {failed} failed, 总计 {len(tests)} =====")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

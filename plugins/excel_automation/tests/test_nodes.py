# plugins/excel_automation/tests/test_nodes.py
"""Excel 自动化插件测试"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# openpyxl 不可用时跳过整个模块的测试
openpyxl = pytest.importorskip("openpyxl")


def _make_context(blackboard=None):
    from bt_core.context import ExecutionContext
    ctx = ExecutionContext()
    if blackboard:
        for k, v in blackboard.items():
            ctx.blackboard.set(k, v)
    return ctx


def test_excel_write_node_creates_file(tmp_path):
    """测试 Excel 写入节点"""
    from plugins.excel_automation.nodes import ExcelWriteNode
    from bt_core.status import NodeStatus

    target_file = tmp_path / "output.xlsx"
    node = ExcelWriteNode()
    node.config = {
        "file_path": str(target_file),
        "sheet_name": "Sheet1",
        "data_key": "table_data",
        "start_cell": "A1",
    }

    # 模拟表格数据 [[行1列1, 行1列2], [行2列1, 行2列2]]
    ctx = _make_context(blackboard={"table_data": [["Name", "Age"], ["Alice", 30], ["Bob", 25]]})
    status = node._execute_action(ctx)

    assert status == NodeStatus.SUCCESS
    assert target_file.exists()

    # 验证内容
    wb = openpyxl.load_workbook(str(target_file))
    ws = wb["Sheet1"]
    assert ws["A1"].value == "Name"
    assert ws["B1"].value == "Age"
    assert ws["A2"].value == "Alice"
    assert ws["B2"].value == 30


def test_excel_read_node_reads_file(tmp_path):
    """测试 Excel 读取节点"""
    from plugins.excel_automation.nodes import ExcelReadNode
    from bt_core.status import NodeStatus

    # 先创建测试文件
    test_file = tmp_path / "input.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "Name"
    ws["B1"] = "Age"
    ws["A2"] = "Alice"
    ws["B2"] = 30
    wb.save(str(test_file))

    node = ExcelReadNode()
    node.config = {
        "file_path": str(test_file),
        "sheet_name": "Sheet1",
        "cell_range": "A1:B2",
        "target_key": "read_data",
    }

    ctx = _make_context()
    status = node._execute_action(ctx)

    assert status == NodeStatus.SUCCESS
    data = ctx.blackboard.get("read_data")
    assert data[0] == ["Name", "Age"]
    assert data[1] == ["Alice", 30]


def test_excel_format_node_applies_style(tmp_path):
    """测试 Excel 格式化节点"""
    from plugins.excel_automation.nodes import ExcelFormatNode
    from bt_core.status import NodeStatus

    test_file = tmp_path / "format.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Test"
    wb.save(str(test_file))

    node = ExcelFormatNode()
    node.config = {
        "file_path": str(test_file),
        "sheet_name": "Sheet",
        "cell_range": "A1:A1",
        "bold": True,
        "bg_color": "FF0000",
    }

    ctx = _make_context()
    status = node._execute_action(ctx)

    assert status == NodeStatus.SUCCESS

    wb2 = openpyxl.load_workbook(str(test_file))
    ws2 = wb2.active
    cell = ws2["A1"]
    assert cell.font.bold is True


def test_plugin_lifecycle():
    """测试插件完整生命周期"""
    from plugins.excel_automation.main import ExcelAutomationPlugin
    from bt_plugins.base import PluginInfo

    info = PluginInfo(
        name="excel_automation",
        display_name="Excel自动化",
        version="1.0.0",
        author="AutoDoor Team",
        description="Excel 读写和格式化"
    )
    plugin = ExcelAutomationPlugin(info)
    plugin.on_load()
    assert plugin._loaded

    nodes = plugin.get_nodes()
    assert "ExcelReadNode" in nodes
    assert "ExcelWriteNode" in nodes
    assert "ExcelFormatNode" in nodes

    schemas = plugin.get_node_schemas()
    assert "ExcelReadNode" in schemas

    plugin.on_unload()

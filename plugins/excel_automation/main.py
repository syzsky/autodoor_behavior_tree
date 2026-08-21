# plugins/excel_automation/main.py
"""Excel 自动化插件入口"""
from bt_plugins.base import BasePlugin
from plugins.excel_automation.nodes import ExcelWriteNode, ExcelReadNode, ExcelFormatNode
from plugins.excel_automation.adapter import ExcelAdapter


class ExcelAutomationPlugin(BasePlugin):
    """Excel 自动化插件"""

    def on_load(self):
        self._loaded = True
        self.log("info", "Excel 自动化插件已加载")

    def on_unload(self):
        self._loaded = False
        self.log("info", "Excel 自动化插件已卸载")

    def on_start(self):
        self._started = True
        self.log("info", "Excel 自动化插件已启动")

    def on_stop(self):
        self._started = False
        self.log("info", "Excel 自动化插件已停止")

    def get_nodes(self):
        return {
            "ExcelReadNode": ExcelReadNode,
            "ExcelWriteNode": ExcelWriteNode,
            "ExcelFormatNode": ExcelFormatNode,
        }

    def get_adapters(self):
        return {
            "excel": ExcelAdapter,
        }

    def get_node_schemas(self):
        return {
            "ExcelReadNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "sheet_name", "label": "Sheet 名", "type": "text", "default": ""},
                {"key": "cell_range", "label": "单元格范围", "type": "text", "default": "A1:Z100"},
                {"key": "target_key", "label": "目标键名", "type": "text", "default": "excel_data"},
            ],
            "ExcelWriteNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "sheet_name", "label": "Sheet 名", "type": "text", "default": "Sheet1"},
                {"key": "data_key", "label": "数据键名", "type": "text", "default": "table_data"},
                {"key": "start_cell", "label": "起始单元格", "type": "text", "default": "A1"},
            ],
            "ExcelFormatNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "sheet_name", "label": "Sheet 名", "type": "text", "default": ""},
                {"key": "cell_range", "label": "单元格范围", "type": "text", "default": "A1:A1"},
                {"key": "bold", "label": "加粗", "type": "bool", "default": False},
                {"key": "bg_color", "label": "背景色（十六进制）", "type": "text", "default": ""},
            ],
        }

    def get_node_display_info(self):
        return {
            "ExcelReadNode": {
                "display_name": "Excel读取",
                "description": "读取 Excel 单元格范围到黑板",
                "category": "plugin",
                "icon": "📊",
            },
            "ExcelWriteNode": {
                "display_name": "Excel写入",
                "description": "将黑板数据写入 Excel 文件",
                "category": "plugin",
                "icon": "📈",
            },
            "ExcelFormatNode": {
                "display_name": "Excel格式化",
                "description": "应用单元格格式（字体、颜色）",
                "category": "plugin",
                "icon": "🎨",
            },
        }

    def get_config_schema(self):
        return {
            "default_sheet": {
                "type": "text",
                "default": "Sheet1",
                "label": "默认 Sheet 名"
            }
        }

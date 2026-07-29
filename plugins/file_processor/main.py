# plugins/file_processor/main.py
"""文件处理插件入口"""
from bt_plugins.base import BasePlugin
from plugins.file_processor.nodes import FileReadNode, FileWriteNode, FileMoveNode


class FileProcessorPlugin(BasePlugin):
    """文件处理插件"""

    def on_load(self):
        self._loaded = True
        self.log("info", "文件处理插件已加载")

    def on_unload(self):
        self._loaded = False
        self.log("info", "文件处理插件已卸载")

    def on_start(self):
        self._started = True
        self.log("info", "文件处理插件已启动")

    def on_stop(self):
        self._started = False
        self.log("info", "文件处理插件已停止")

    def get_nodes(self):
        return {
            "FileReadNode": FileReadNode,
            "FileWriteNode": FileWriteNode,
            "FileMoveNode": FileMoveNode,
        }

    def get_node_schemas(self):
        return {
            "FileReadNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "encoding", "label": "编码", "type": "text", "default": "utf-8"},
                {"key": "target_key", "label": "目标键名", "type": "text", "default": "file_content"},
            ],
            "FileWriteNode": [
                {"key": "file_path", "label": "文件路径", "type": "text", "default": ""},
                {"key": "source_key", "label": "源键名", "type": "text", "default": "file_content"},
                {"key": "encoding", "label": "编码", "type": "text", "default": "utf-8"},
                {"key": "append", "label": "追加模式", "type": "bool", "default": False},
            ],
            "FileMoveNode": [
                {"key": "source_path", "label": "源路径", "type": "text", "default": ""},
                {"key": "target_path", "label": "目标路径", "type": "text", "default": ""},
            ],
        }

    def get_node_display_info(self):
        return {
            "FileReadNode": {
                "display_name": "文件读取",
                "description": "读取文件内容到黑板",
                "category": "plugin",
                "icon": "📄",
            },
            "FileWriteNode": {
                "display_name": "文件写入",
                "description": "将黑板数据写入文件",
                "category": "plugin",
                "icon": "📝",
            },
            "FileMoveNode": {
                "display_name": "文件移动",
                "description": "移动或重命名文件",
                "category": "plugin",
                "icon": "📁",
            },
        }

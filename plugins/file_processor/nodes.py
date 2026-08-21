# plugins/file_processor/nodes.py
"""文件处理节点"""
import os
import shutil

from bt_core.nodes import ActionNode
from bt_core.status import NodeStatus


class FileReadNode(ActionNode):
    """文件读取节点 — 读取文件内容到黑板"""

    NODE_TYPE = "FileReadNode"

    def _execute_action(self, context):
        file_path = self.config.get("file_path", "")
        encoding = self.config.get("encoding", "utf-8")
        target_key = self.config.get("target_key", "file_content")

        if not file_path or not os.path.exists(file_path):
            return NodeStatus.FAILURE

        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            context.blackboard.set(target_key, content)
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE


class FileWriteNode(ActionNode):
    """文件写入节点 — 将黑板数据写入文件"""

    NODE_TYPE = "FileWriteNode"

    def _execute_action(self, context):
        file_path = self.config.get("file_path", "")
        source_key = self.config.get("source_key", "file_content")
        encoding = self.config.get("encoding", "utf-8")
        append = self.config.get("append", False)

        if not file_path:
            return NodeStatus.FAILURE

        content = context.blackboard.get(source_key)
        if content is None:
            return NodeStatus.FAILURE

        try:
            parent = os.path.dirname(file_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            mode = "a" if append else "w"
            with open(file_path, mode, encoding=encoding) as f:
                f.write(str(content))
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE


class FileMoveNode(ActionNode):
    """文件移动节点 — 移动或重命名文件"""

    NODE_TYPE = "FileMoveNode"

    def _execute_action(self, context):
        source_path = self.config.get("source_path", "")
        target_path = self.config.get("target_path", "")

        if not source_path or not target_path:
            return NodeStatus.FAILURE
        if not os.path.exists(source_path):
            return NodeStatus.FAILURE

        try:
            parent = os.path.dirname(target_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.move(source_path, target_path)
            return NodeStatus.SUCCESS
        except Exception:
            return NodeStatus.FAILURE

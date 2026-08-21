# plugins/excel_automation/adapter.py
"""Excel 适配器 — 封装 openpyxl 工作簿操作"""
import os

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class ExcelAdapter:
    """Excel 适配器 — 简单的工作簿操作封装"""

    def __init__(self):
        self._workbooks = {}

    @classmethod
    def is_available(cls) -> bool:
        return OPENPYXL_AVAILABLE

    def open(self, file_path: str, read_only: bool = False):
        """打开工作簿"""
        if not OPENPYXL_AVAILABLE:
            return None
        try:
            wb = openpyxl.load_workbook(file_path, data_only=not read_only)
            self._workbooks[file_path] = wb
            return wb
        except Exception:
            return None

    def create(self, file_path: str):
        """创建新工作簿"""
        if not OPENPYXL_AVAILABLE:
            return None
        wb = openpyxl.Workbook()
        self._workbooks[file_path] = wb
        return wb

    def save(self, file_path: str) -> bool:
        """保存工作簿"""
        wb = self._workbooks.get(file_path)
        if not wb:
            return False
        try:
            wb.save(file_path)
            return True
        except Exception:
            return False

    def close(self, file_path: str) -> None:
        """关闭工作簿"""
        wb = self._workbooks.pop(file_path, None)
        if wb:
            wb.close()

    def close_all(self) -> None:
        """关闭所有工作簿"""
        for wb in list(self._workbooks.values()):
            wb.close()
        self._workbooks.clear()

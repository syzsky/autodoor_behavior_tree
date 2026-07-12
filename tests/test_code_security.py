import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestCodeSecurity(unittest.TestCase):
    def _write_script(self, code: str) -> str:
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, encoding='utf-8'
        )
        tmp.write(code)
        tmp.close()
        return tmp.name

    def tearDown(self):
        # 清理由 setUp 创建的临时文件在子类中处理
        pass

    def test_allowed_import_math(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("import math\nprint(math.pi)")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertTrue(ok, f"应允许导入 math: {msg}")
        finally:
            os.unlink(path)

    def test_forbidden_import_os(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("import os\nos.system('whoami')")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok, "应禁止导入 os")
            self.assertIn("os", msg)
        finally:
            os.unlink(path)

    def test_forbidden_import_subprocess(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("import subprocess\nsubprocess.run(['calc'])")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)

    def test_forbidden_import_socket(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("import socket\ns = socket.socket()")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)

    def test_allowed_math_operations(self):
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script(
            "import math\nresult = math.sqrt(16)\nprint(result)"
        )
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertTrue(ok, msg)
        finally:
            os.unlink(path)

    def test_dynamic_import_bypass_blocked(self):
        """测试 __import__('os') 动态绕过被拦截"""
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script(
            "os_module = __import__('os')\nos_module.system('whoami')"
        )
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok, "应拦截 __import__ 动态调用")
        finally:
            os.unlink(path)

    def test_eval_exec_blocked(self):
        """测试 eval/exec 被拦截"""
        from bt_nodes.actions.code import CodeSecurityChecker
        path = self._write_script("result = eval('1+1')")
        try:
            ok, msg = CodeSecurityChecker.check_python_script(path)
            self.assertFalse(ok)
        finally:
            os.unlink(path)

    def test_sandbox_builtins_filter(self):
        """测试沙箱 __builtins__ 过滤函数存在"""
        from bt_nodes.actions.code import CodeSecurityChecker
        self.assertTrue(hasattr(CodeSecurityChecker, 'get_safe_builtins'))
        safe = CodeSecurityChecker.get_safe_builtins()
        self.assertIn('print', safe)
        self.assertIn('len', safe)
        self.assertNotIn('__import__', safe)
        self.assertNotIn('eval', safe)
        self.assertNotIn('exec', safe)
        self.assertNotIn('open', safe)


if __name__ == '__main__':
    unittest.main()


import subprocess, sys

# Linux 兼容补丁：模拟 Windows subprocess 属性
class _CompatSTARTUPINFO:
    def __init__(self):
        self.dwFlags = 0
        self.wShowWindow = 0
        self.hStdInput = None
        self.hStdOutput = None
        self.hStdError = None
    def __repr__(self):
        return "<CompatSTARTUPINFO>"

if not hasattr(subprocess, "STARTUPINFO"):
    subprocess.STARTUPINFO = _CompatSTARTUPINFO
if not hasattr(subprocess, "STARTF_USESHOWWINDOW"):
    subprocess.STARTF_USESHOWWINDOW = 0x00000001
if not hasattr(subprocess, "SW_HIDE"):
    subprocess.SW_HIDE = 0
if not hasattr(subprocess, "CREATE_NEW_CONSOLE"):
    subprocess.CREATE_NEW_CONSOLE = 0x00000010

# 其余 Windows 可能用到的常量兜底
for _n in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "STARTF_USESTDHANDLES"):
    if not hasattr(subprocess, _n):
        setattr(subprocess, _n, 0)

sys.argv = ["autodoor-bt"] + sys.argv[1:]
sys.path.insert(0, "/tmp/autodoor_behavior_tree")
from cli import main
main()

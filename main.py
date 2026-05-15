import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    """获取资源文件的绝对路径，支持PyInstaller打包后的路径"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

def load_version():
    """从build_info.json加载版本信息"""
    build_info_file = get_resource_path('bt_utils/build_info.json')
    
    if os.path.exists(build_info_file):
        try:
            with open(build_info_file, 'r', encoding='utf-8') as f:
                build_info = json.load(f)
                return build_info.get('version', '1.0.0')
        except Exception:
            pass
    
    return "1.2.2a"

def load_github_info():
    """从build_info.json加载GitHub仓库信息"""
    build_info_file = get_resource_path('bt_utils/build_info.json')
    
    if os.path.exists(build_info_file):
        try:
            with open(build_info_file, 'r', encoding='utf-8') as f:
                build_info = json.load(f)
                github = build_info.get('github', {})
                return github.get('owner', 'wdhq4261761'), github.get('repo', 'autodoor_behavior_tree')
        except Exception:
            pass
    
    return 'wdhq4261761', 'autodoor_behavior_tree'

VERSION = load_version()

from bt_utils.version_checker import BetaExpirationChecker

beta_checker = BetaExpirationChecker()
if beta_checker.check_expiration():
    beta_checker.show_expiration_dialog()
    sys.exit(0)

import customtkinter as ctk
from bt_gui.app import BehaviorTreeApp
from bt_core.registry import register_all_nodes


def ensure_workspace_exists():
    """确保workspace文件夹存在"""
    from config.settings_manager import SettingsManager
    
    settings_manager = SettingsManager()
    saved_path = settings_manager.get("default_project_path", "")
    
    if saved_path and os.path.exists(saved_path):
        return
    
    workspace_dir = SettingsManager.get_default_workspace_path()
    
    try:
        os.makedirs(workspace_dir, exist_ok=True)
    except Exception:
        pass


def check_vcredist():
    """检查 Visual C++ Redistributable 运行时库"""
    try:
        import onnxruntime
        return True
    except ImportError as e:
        if "DLL load failed" in str(e) or "onnxruntime_pybind11_state" in str(e):
            return False
        raise
    except Exception:
        return False


def initialize_ocr():
    """初始化OCR引擎"""
    try:
        if not check_vcredist():
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            
            messagebox.showwarning(
                "缺少运行时库",
                "程序检测到缺少 Visual C++ Redistributable 运行时库。\n\n"
                "OCR 相关功能将无法使用。\n\n"
                "请下载并安装：\n"
                "https://aka.ms/vs/17/release/vc_redist.x64.exe\n\n"
                "安装后重启程序即可使用 OCR 功能。\n\n"
                "其他功能不受影响，可正常使用。"
            )
            
            root.destroy()
            
            from bt_utils.ocr_manager import OCRManager
            OCRManager.set_unavailable("缺少 Visual C++ Redistributable 运行时库")
            
            return False
        
        from bt_utils.ocr_manager import OCRManager
        OCRManager.initialize()
        return True
        
    except Exception as e:
        from bt_utils.ocr_manager import OCRManager
        OCRManager.set_unavailable(str(e))
        
        return False


def initialize_input():
    """初始化输入控制器（预加载DD虚拟键盘）"""
    try:
        from bt_utils.input_controller_factory import InputController
        # 预加载输入控制器，会自动加载DD虚拟键盘（如果启用）
        InputController()
        return True
    except Exception:
        return False


def main():
    ensure_workspace_exists()
    
    initialize_ocr()
    initialize_input()
    
    register_all_nodes()
    
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = BehaviorTreeApp()
    
    from bt_utils.version_checker import VersionChecker
    github_owner, github_repo = load_github_info()
    version_checker = VersionChecker(
        app=app,
        owner=github_owner,
        repo=github_repo,
        current_version=VERSION
    )
    
    app._version_checker = version_checker
    
    version_checker.check_force_update()
    
    version_checker.start_auto_check(app)
    
    app.mainloop()


if __name__ == "__main__":
    main()

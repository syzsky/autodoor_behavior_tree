"""
运行时依赖自动检查与下载模块
=============================
在 exe 启动时自动检测环境、下载缺失的依赖和模型。

使用方式:
    from modules.yolo_trainer.runtime_setup import RuntimeSetup
    
    # 在程序入口处调用
    setup = RuntimeSetup()
    if not setup.check_and_install():
        print("环境初始化失败")
        sys.exit(1)
"""

import subprocess
import sys
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Callable


# ─── 配置 ───────────────────────────────────────────

# pip 镜像源（国内加速）
PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"

# 模型下载源（GitHub 镜像）
MODEL_MIRRORS = [
    "https://ghfast.top/https://github.com/ultralytics/assets/releases/download/v8.2.0/{name}.pt",
    "https://github.com/ultralytics/assets/releases/download/v8.2.0/{name}.pt",
]

# 依赖检查列表: (import名, pip包名, 最小版本)
REQUIRED_PACKAGES = [
    ("cv2",        "opencv-python",  "4.8"),
    ("PIL",        "Pillow",         "10.0"),
    ("yaml",       "PyYAML",         "6.0"),
    ("numpy",      "numpy",          "1.24"),
]

# 重量级依赖：首次运行时自动 pip install（不打包进 exe 以减小体积）
HEAVY_PACKAGES = [
    ("torch",       "torch>=2.0",     None),   # CPU 版 ~200MB，CUDA 版 ~2GB
    ("torchvision", "torchvision>=0.15", None),
    ("ultralytics", "ultralytics>=8.2", None),  # 含 scipy 等依赖
]

OPTIONAL_PACKAGES = [
    ("matplotlib", "matplotlib",     "3.7"),
    ("tqdm",       "tqdm",           "4.65"),
]

# 预训练模型
PRETRAINED_MODELS = {
    "yolov8n.pt": {
        "size_mb": 6.3,
        "desc": "YOLOv8 Nano",
    },
    "yolov8s.pt": {
        "size_mb": 21.5,
        "desc": "YOLOv8 Small",
    },
}


# ─── 版本解析工具 ────────────────────────────────────

def _parse_version(v: str) -> tuple:
    """解析版本号为可比较的元组"""
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)


def _version_gte(current: str, required: str) -> bool:
    """检查 current >= required"""
    try:
        return _parse_version(current) >= _parse_version(required)
    except Exception:
        return True  # 无法比较时默认通过


# ─── 下载工具 ───────────────────────────────────────

def _download_file(url: str, dest: str, progress_cb: Optional[Callable] = None) -> bool:
    """
    下载文件，支持进度回调
    
    Args:
        url: 下载 URL
        dest: 目标路径
        progress_cb: 进度回调函数(percent: int, downloaded_mb: float, total_mb: float)
    
    Returns:
        是否下载成功
    """
    dest_path = Path(dest)

    # 已存在则跳过
    if dest_path.exists() and dest_path.stat().st_size > 1024:
        size_mb = dest_path.stat().st_size / (1024 * 1024)
        if progress_cb:
            progress_cb(100, size_mb, size_mb)
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 添加随机延迟避免被封
    time.sleep(0.5)

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    })

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = resp.headers.get("Content-Length")
            total_mb = int(total) / (1024 * 1024) if total else 0

            downloaded = 0
            chunk_size = 65536  # 64KB chunks

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total and progress_cb:
                        pct = min(int(downloaded / int(total) * 100), 100)
                        dl_mb = downloaded / (1024 * 1024)
                        progress_cb(pct, dl_mb, total_mb)

        return dest_path.exists() and dest_path.stat().st_size > 1024

    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        raise


# ─── 核心类 ─────────────────────────────────────────

class RuntimeSetup:
    """
    运行时环境自动设置
    
    在 exe 启动时自动:
    1. 检查并安装缺失的 Python 包
    2. 下载预训练模型
    3. 验证 CUDA 可用性
    
    使用方式:
        setup = RuntimeSetup(progress_callback=my_gui_update_fn)
        ok = setup.check_and_install()
        
        # 或仅检查不安装
        missing = setup.check_packages()
        
        # 或仅下载模型
        setup.download_models(["yolov8n.pt"])
    """
    
    def __init__(self, 
                 progress_cb: Optional[Callable] = None,
                 model_dir: Optional[str] = None,
                 pip_index: str = PIP_INDEX):
        """
        Args:
            progress_cb: 进度回调 (stage: str, percent: int, message: str)
            model_dir: 模型保存目录，默认 exe 同目录下的 models/
            pip_index: pip 镜像源
        """
        self._progress_cb = progress_cb or self._default_progress
        self._pip_index = pip_index
        
        # 模型目录: exe 同目录/models/
        if model_dir:
            self._model_dir = Path(model_dir)
        else:
            exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
            self._model_dir = exe_dir / "models"
        
        self._model_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录检查结果
        self._missing_packages = []
        self._installed_packages = []
        self._downloaded_models = []

    @staticmethod
    def _default_progress(stage: str, percent: int, message: str):
        """默认进度输出到控制台"""
        bar_len = 30
        filled = int(bar_len * percent / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r[{stage}] [{bar}] {percent:3d}% {message}", end="", flush=True)
        if percent >= 100:
            print()

    def _report(self, stage: str, percent: int, message: str):
        """报告进度"""
        try:
            self._progress_cb(stage, percent, message)
        except Exception:
            pass

    # ─── 包检查 ─────────────────────────────────────
    
    def check_packages(self) -> list:
        """
        检查缺失的包
        
        Returns:
            缺失包列表 [(import_name, pip_name, required_version), ...]
        """
        missing = []
        
        for import_name, pip_name, min_ver in REQUIRED_PACKAGES:
            try:
                mod = __import__(import_name)
                ver = getattr(mod, "__version__", "0.0.0")
                if not _version_gte(ver, min_ver):
                    missing.append((import_name, pip_name, min_ver))
            except ImportError:
                missing.append((import_name, pip_name, min_ver))
        
        self._missing_packages = missing
        return missing

    def check_torch(self) -> dict:
        """
        检查 PyTorch 状态
        
        Returns:
            {"installed": bool, "version": str, "cuda": bool, "device": str}
        """
        result = {"installed": False, "version": "", "cuda": False, "device": "cpu"}
        
        try:
            import torch
            result["installed"] = True
            result["version"] = torch.__version__
            result["cuda"] = torch.cuda.is_available()
            if result["cuda"]:
                result["device"] = torch.cuda.get_device_name(0)
        except ImportError:
            pass
        
        return result

    # ─── 包安装 ─────────────────────────────────────
    
    def install_package(self, pip_name: str, timeout: int = 120) -> bool:
        """
        安装单个包
        
        Args:
            pip_name: pip 包名
            timeout: 超时秒数
        
        Returns:
            是否安装成功
        """
        cmd = [
            sys.executable, "-m", "pip", "install",
            "-i", self._pip_index,
            "--no-warn-script-location",
            "--disable-pip-version-check",
            pip_name,
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return result.returncode == 0
        except Exception:
            return False

    def install_missing_packages(self) -> bool:
        """
        安装所有缺失的包
        
        Returns:
            是否全部安装成功
        """
        if not self._missing_packages:
            self.check_packages()
        
        if not self._missing_packages:
            return True

        total = len(self._missing_packages)
        all_ok = True

        for i, (import_name, pip_name, min_ver) in enumerate(self._missing_packages):
            idx = i + 1
            self._report("依赖", int(idx / total * 50), f"安装 {pip_name} ({idx}/{total})")

            # 重试 2 次
            ok = False
            for attempt in range(2):
                if attempt > 0:
                    time.sleep(3)
                ok = self.install_package(pip_name, timeout=120)
                if ok:
                    break

            if ok:
                self._installed_packages.append(pip_name)
            else:
                all_ok = False
                print(f"\n⚠️  {pip_name} 安装失败")

        return all_ok

    # ─── 模型下载 ────────────────────────────────────
    
    def check_models(self, model_names: Optional[list] = None) -> dict:
        """
        检查模型文件是否存在
        
        Args:
            model_names: 要检查的模型列表，默认检查所有
        
        Returns:
            {"yolov8n.pt": {"exists": bool, "path": str, "size_mb": float}, ...}
        """
        names = model_names or list(PRETRAINED_MODELS.keys())
        result = {}
        
        for name in names:
            path = self._model_dir / name
            if path.exists():
                size_mb = path.stat().st_size / (1024 * 1024)
                result[name] = {"exists": True, "path": str(path), "size_mb": size_mb}
            else:
                result[name] = {"exists": False, "path": str(path), "size_mb": 0}
        
        return result

    def download_model(self, name: str, use_ultralytics: bool = True) -> bool:
        """
        下载单个预训练模型
        
        Args:
            name: 模型文件名 (如 yolov8n.pt)
            use_ultralytics: 优先使用 ultralytics 自动下载
        
        Returns:
            是否下载成功
        """
        dest = str(self._model_dir / name)
        dest_path = Path(dest)
        
        # 已存在
        if dest_path.exists() and dest_path.stat().st_size > 1024:
            return True

        # 方法1: 通过 ultralytics 下载
        if use_ultralytics:
            try:
                from ultralytics import YOLO
                model = YOLO(name)  # ultralytics 会自动下载到当前目录
                # 移动到目标目录
                src = Path(name)
                if src.exists():
                    src.rename(dest)
                return True
            except Exception:
                pass

        # 方法2: 从 GitHub 镜像手动下载
        for mirror_url in MODEL_MIRRORS:
            url = mirror_url.format(name=name)
            try:
                def progress(pct, dl_mb, total_mb):
                    msg = f"{name}: {dl_mb:.1f}/{total_mb:.1f}MB" if total_mb > 0 else f"{name}: {dl_mb:.1f}MB"
                    self._report("模型", 50 + int(pct / 2), msg)
                
                if _download_file(url, dest, progress):
                    return True
            except Exception:
                continue

        return False

    def download_models(self, model_names: Optional[list] = None) -> dict:
        """
        下载多个预训练模型
        
        Args:
            model_names: 模型列表，默认下载 yolov8n.pt
        
        Returns:
            {"yolov8n.pt": True/False, ...}
        """
        names = model_names or ["yolov8n.pt"]
        results = {}
        
        for i, name in enumerate(names):
            base_pct = int(i / len(names) * 50)
            self._report("模型", base_pct, f"下载 {name} ({i+1}/{len(names)})")
            results[name] = self.download_model(name)
        
        return results

    # ─── 完整流程 ───────────────────────────────────
    
    def check_and_install(self, auto_download_models: bool = True) -> bool:
        """
        完整的环境检查和安装流程
        
        Args:
            auto_download_models: 是否自动下载模型
        
        Returns:
            是否环境就绪
        """
        self._report("检查", 0, "开始环境检查...")
        
        # Step 1: 检查包
        self._report("检查", 5, "检查依赖包...")
        missing = self.check_packages()
        
        if missing:
            pkg_names = [p[1] for p in missing]
            print(f"\n📦 缺失依赖: {', '.join(pkg_names)}")
            
            # Step 2: 安装缺失包
            if not self.install_missing_packages():
                self._report("错误", 0, "部分依赖安装失败")
                return False
        else:
            self._report("检查", 50, "所有依赖已安装")
        
        # Step 3: 检查并安装重量级依赖 (torch/torchvision/ultralytics)
        self._report("检查", 55, "检查 PyTorch 环境...")
        
        # 3a: torch
        try:
            import torch
            print(f"  ✅ torch {torch.__version__}")
        except ImportError:
            print("\n📦 安装 PyTorch CPU 版 (~200MB)...")
            self.install_package("torch", timeout=600)
        
        # 3b: torchvision
        try:
            import torchvision
            print(f"  ✅ torchvision {torchvision.__version__}")
        except ImportError:
            print("\n📦 安装 torchvision...")
            self.install_package("torchvision", timeout=300)
        
        # 3c: ultralytics
        try:
            import ultralytics
            print(f"  ✅ ultralytics {ultralytics.__version__}")
        except ImportError:
            print("\n📦 安装 ultralytics...")
            self.install_package("ultralytics", timeout=300)
        
        # Step 4: 下载模型
        if auto_download_models:
            self._report("模型", 50, "检查预训练模型...")
            model_status = self.check_models(["yolov8n.pt"])
            
            if not model_status.get("yolov8n.pt", {}).get("exists", False):
                print("\n📥 下载 yolov8n.pt...")
                self.download_model("yolov8n.pt")
        
        # Step 5: 最终验证
        self._report("检查", 95, "最终验证...")
        final_missing = self.check_packages()
        
        if final_missing:
            pkg_names = [p[1] for p in final_missing]
            self._report("错误", 0, f"以下包仍缺失: {', '.join(pkg_names)}")
            return False
        
        self._report("完成", 100, "环境就绪！")
        return True

    def get_status(self) -> dict:
        """获取当前环境状态摘要"""
        torch_info = self.check_torch()
        model_status = self.check_models(["yolov8n.pt", "yolov8s.pt"])
        
        return {
            "python": sys.version,
            "platform": sys.platform,
            "torch": torch_info,
            "models": model_model_status,
            "model_dir": str(self._model_dir),
            "exe_dir": str(Path(sys.executable).parent) if getattr(sys, 'frozen', False) else str(Path(__file__).parent),
        }


# ─── 便捷函数 ───────────────────────────────────────

def quick_setup(progress_cb: Optional[Callable] = None) -> bool:
    """
    一键环境设置（便捷函数）
    
    用法:
        from modules.yolo_trainer.runtime_setup import quick_setup
        if not quick_setup():
            print("环境初始化失败")
            sys.exit(1)
    """
    setup = RuntimeSetup(progress_cb=progress_cb)
    return setup.check_and_install()


def ensure_model(model_name: str = "yolov8n.pt", 
                 progress_cb: Optional[Callable] = None) -> Optional[str]:
    """
    确保模型存在，不存在则下载
    
    Returns:
        模型文件路径，失败返回 None
    """
    setup = RuntimeSetup(progress_cb=progress_cb)
    status = setup.check_models([model_name])
    
    if status.get(model_name, {}).get("exists", False):
        return status[model_name]["path"]
    
    if setup.download_model(model_name):
        path = str(setup._model_dir / model_name)
        if Path(path).exists():
            return path
    
    return None


# ─── 自测 ───────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("YOLO 训练器 - 运行时环境自检")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"平台: {sys.platform}")
    print(f"exe 模式: {getattr(sys, 'frozen', False)}")
    print()
    
    ok = quick_setup()
    
    if ok:
        print("\n✅ 环境就绪！")
    else:
        print("\n❌ 环境问题，请检查网络后重试")
        sys.exit(1)

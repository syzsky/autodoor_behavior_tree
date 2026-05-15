#!/usr/bin/env python3
"""
YOLO 训练器 - 智能依赖安装脚本
==============================
支持断点续传、超时重试、进度显示
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path

# ─── 配置 ───────────────────────────────────────────

PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
HF_MIRROR = "https://hf-mirror.com"

# 依赖分组（按安装顺序，小的先装）
INSTALL_STEPS = [
    {
        "name": "核心依赖 (numpy, opencv, Pillow, PyYAML)",
        "packages": ["numpy>=1.24", "opencv-python>=4.8", "Pillow>=10.0", "PyYAML>=6.0"],
        "timeout": 300,
    },
    {
        "name": "PyTorch CPU 版",
        "packages": ["torch>=2.0", "torchvision>=0.15"],
        "extra_index": "https://download.pytorch.org/whl/cpu",
        "timeout": 600,
    },
    {
        "name": "Ultralytics (YOLOv8)",
        "packages": ["ultralytics>=8.2"],
        "timeout": 300,
    },
    {
        "name": "GUI 依赖 (customtkinter)",
        "packages": ["customtkinter>=5.2"],
        "timeout": 120,
    },
    {
        "name": "可选依赖 (matplotlib, tqdm, tensorboard)",
        "packages": ["matplotlib>=3.7", "tqdm>=4.65", "tensorboard>=2.13"],
        "timeout": 300,
    },
]

# 预训练模型
MODELS = {
    "yolov8n": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt",
        "size_mb": 6.3,
    },
    "yolov8s": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt",
        "size_mb": 21.5,
    },
}


def pip_install_step(step: dict) -> bool:
    """执行一个安装步骤"""
    name = step["name"]
    pkgs = step["packages"]
    timeout = step.get("timeout", 600)
    extra_index = step.get("extra_index")

    print(f"\n{'='*60}")
    print(f"📦 {name}")
    print(f"   包: {', '.join(pkgs)}")
    print(f"   超时: {timeout}s")
    print(f"{'='*60}")

    cmd = [
        sys.executable, "-m", "pip", "install",
        "-i", PIP_INDEX,
        "--no-warn-script-location",
    ]
    if extra_index:
        cmd += ["--extra-index-url", extra_index]
    cmd += pkgs

    # 重试机制
    for attempt in range(3):
        if attempt > 0:
            wait = 10 * attempt
            print(f"🔄 第 {attempt+1} 次重试 (等待 {wait}s)...")
            time.sleep(wait)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # 实时输出 + 超时控制
            start = time.time()
            output_lines = []

            while proc.poll() is None:
                # 检查超时
                if time.time() - start > timeout:
                    proc.kill()
                    print(f"⏰ 安装超时 ({timeout}s)")
                    break

                # 读取输出
                line = proc.stdout.readline()
                if line:
                    line = line.rstrip()
                    output_lines.append(line)
                    # 只显示关键行
                    if any(kw in line.lower() for kw in [
                        "collecting", "downloading", "installing",
                        "successfully", "error", "already", "requirement",
                    ]):
                        print(f"   {line}")

            # 等待进程结束
            proc.wait(timeout=30)

            if proc.returncode == 0:
                print(f"✅ {name} 安装成功")
                return True
            else:
                print(f"❌ {name} 安装失败 (exit: {proc.returncode})")

        except subprocess.TimeoutExpired:
            print(f"⏰ 安装超时")
        except Exception as e:
            print(f"❌ 安装出错: {e}")

    return False


def download_model(name: str, url: str, dest_dir: Path) -> bool:
    """下载预训练模型"""
    dest = dest_dir / f"{name}.pt"

    if dest.exists():
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"⏭️  {name} 已存在 ({size_mb:.1f}MB)")
        return True

    print(f"\n⬇️  下载 {name}...")
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 使用 wget（支持断点续传）
    cmd = [
        "wget", "-c",  # 断点续传
        "--timeout=60",
        "--tries=3",
        "-O", str(dest),
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and dest.exists():
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"✅ {name} 下载完成 ({size_mb:.1f}MB)")
            return True
        else:
            print(f"❌ {name} 下载失败")
            if dest.exists():
                dest.unlink()
            return False
    except Exception as e:
        print(f"❌ {name} 下载出错: {e}")
        return False


def verify_environment():
    """验证环境"""
    print(f"\n{'='*60}")
    print("🔍 环境验证")
    print(f"{'='*60}")

    results = []

    # 检查 Python 包
    packages = [
        ("numpy", "numpy"),
        ("cv2", "opencv-python"),
        ("PIL", "Pillow"),
        ("yaml", "PyYAML"),
        ("torch", "torch"),
        ("torchvision", "torchvision"),
        ("ultralytics", "ultralytics"),
        ("customtkinter", "customtkinter"),
        ("matplotlib", "matplotlib"),
        ("tqdm", "tqdm"),
    ]

    for module, pkg in packages:
        try:
            mod = __import__(module)
            ver = getattr(mod, "__version__", "?")
            print(f"  ✅ {pkg}: {ver}")
            results.append((pkg, True))
        except ImportError:
            print(f"  ❌ {pkg}: 未安装")
            results.append((pkg, False))

    # 检查 CUDA
    try:
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            name = torch.cuda.get_device_name(0)
            mem = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            print(f"  🎮 CUDA: {name} ({mem:.1f}GB)")
        else:
            print(f"  💻 CPU 模式 (CUDA 不可用)")
    except ImportError:
        pass

    # 检查模型
    model_dir = Path("./models")
    for name in MODELS:
        path = model_dir / f"{name}.pt"
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  📦 {name}: {size_mb:.1f}MB")
        else:
            print(f"  ⬜ {name}: 未下载")

    return results


def main():
    print("=" * 60)
    print("🚀 YOLO 训练器 - 智能依赖安装")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"平台: {sys.platform}")
    print(f"pip 源: {PIP_INDEX}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 解析参数
    skip_torch = "--skip-torch" in sys.argv
    skip_models = "--skip-models" in sys.argv
    only_verify = "--verify" in sys.argv
    model_names = None

    for i, arg in enumerate(sys.argv):
        if arg == "--models" and i + 1 < len(sys.argv):
            model_names = sys.argv[i + 1].split(",")

    if only_verify:
        verify_environment()
        return

    # 安装依赖
    results = {}
    for step in INSTALL_STEPS:
        # 跳过 torch
        if skip_torch and "torch" in step["name"].lower():
            print(f"\n⏭️  跳过: {step['name']}")
            continue

        ok = pip_install_step(step)
        results[step["name"]] = ok

        if not ok:
            print(f"\n⚠️  {step['name']} 安装失败，是否继续?")
            if "--force" not in sys.argv:
                break

    # 下载模型
    if not skip_models:
        print(f"\n{'='*60}")
        print("📥 下载预训练模型")
        print(f"{'='*60}")

        model_dir = Path("./models")
        models_to_download = model_names or list(MODELS.keys())

        for name in models_to_download:
            if name in MODELS:
                info = MODELS[name]
                download_model(name, info["url"], model_dir)
            else:
                print(f"⚠️  未知模型: {name}")

    # 验证
    verify_environment()

    # 总结
    print(f"\n{'='*60}")
    print("📋 安装总结")
    print(f"{'='*60}")
    for name, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")

    all_ok = all(results.values())
    if all_ok:
        print(f"\n🎉 全部安装成功！")
    else:
        print(f"\n⚠️  部分安装失败")

    print(f"\n💡 使用方式:")
    print(f"  python3 -m modules.yolo_trainer.gui_tab")


if __name__ == "__main__":
    main()

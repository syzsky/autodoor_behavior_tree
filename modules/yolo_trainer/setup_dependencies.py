#!/usr/bin/env python3
"""
YOLO 训练器 - 依赖与模型自动下载脚本
=====================================
用法: python3 setup_dependencies.py [--with-torch] [--with-ultralytics] [--with-gui] [--all]
"""

import subprocess
import sys
import os
import argparse
import urllib.request
import json
from pathlib import Path

# ─── 配置 ───────────────────────────────────────────

# pip 镜像源
PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
# 或使用官方源: "https://pypi.org/simple"

# HuggingFace 模型下载镜像
HF_MIRROR = "https://hf-mirror.com"

# 依赖组
DEPENDENCIES = {
    "core": [
        "numpy>=1.24",
        "opencv-python>=4.8",
        "Pillow>=10.0",
        "PyYAML>=6.0",
    ],
    "torch": [
        "torch>=2.0",
        "torchvision>=0.15",
    ],
    "ultralytics": [
        "ultralytics>=8.2",
    ],
    "gui": [
        "customtkinter>=5.2",
    ],
    "optional": [
        "matplotlib>=3.7",
        "seaborn>=0.12",
        "pandas>=2.0",
        "scikit-learn>=1.3",
        "tqdm>=4.65",
        "tensorboard>=2.13",
    ],
}

# 预训练模型列表
PRETRAINED_MODELS = {
    "yolov8n": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt",
        "size_mb": 6.3,
        "desc": "YOLOv8 Nano - 最快，适合实时检测",
    },
    "yolov8s": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt",
        "size_mb": 21.5,
        "desc": "YOLOv8 Small - 速度与精度平衡",
    },
    "yolov8m": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt",
        "size_mb": 49.7,
        "desc": "YOLOv8 Medium - 较高精度",
    },
    "yolov8l": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8l.pt",
        "size_mb": 83.7,
        "desc": "YOLOv8 Large - 高精度",
    },
    "yolov8x": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8x.pt",
        "size_mb": 131.0,
        "desc": "YOLOv8 XLarge - 最高精度",
    },
}

# ─── 工具函数 ───────────────────────────────────────

def run_pip_install(packages: list, label: str = ""):
    """通过 pip 安装包"""
    if not packages:
        return True

    print(f"\n{'='*60}")
    if label:
        print(f"📦 安装: {label}")
    print(f"   包: {', '.join(packages)}")
    print(f"{'='*60}")

    cmd = [
        sys.executable, "-m", "pip", "install",
        "-i", PIP_INDEX,
        "--no-warn-script-location",
    ] + packages

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            print(f"✅ {label} 安装成功")
            return True
        else:
            print(f"❌ {label} 安装失败 (exit code: {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ {label} 安装超时")
        return False
    except Exception as e:
        print(f"❌ {label} 安装出错: {e}")
        return False


def download_file(url: str, dest: str, desc: str = "") -> bool:
    """带进度条的下载"""
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists():
        size_mb = dest_path.stat().st_size / (1024 * 1024)
        print(f"⏭️  已存在: {dest_path.name} ({size_mb:.1f}MB)，跳过")
        return True

    print(f"\n⬇️  下载: {desc or dest_path.name}")
    print(f"   URL: {url}")
    print(f"   目标: {dest_path}")

    try:
        # 创建请求（带 User-Agent 避免 403）
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        with urllib.request.urlopen(req, timeout=120) as resp:
            total = resp.headers.get("Content-Length")
            total_mb = int(total) / (1024 * 1024) if total else 0

            downloaded = 0
            chunk_size = 8192
            last_pct = -1

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total:
                        pct = int(downloaded / int(total) * 100)
                        if pct != last_pct and pct % 5 == 0:
                            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                            print(f"   [{bar}] {pct}% ({downloaded/(1024*1024):.1f}/{total_mb:.1f}MB)")
                            last_pct = pct

        final_mb = dest_path.stat().st_size / (1024 * 1024)
        print(f"✅ 下载完成: {dest_path.name} ({final_mb:.1f}MB)")
        return True

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP 错误 {e.code}: {e.reason}")
        if dest_path.exists():
            dest_path.unlink()
        return False
    except urllib.error.URLError as e:
        print(f"❌ 网络错误: {e.reason}")
        if dest_path.exists():
            dest_path.unlink()
        return False
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def check_cuda():
    """检查 CUDA 可用性"""
    try:
        import torch
        cuda = torch.cuda.is_available()
        count = torch.cuda.device_count()
        if cuda:
            name = torch.cuda.get_device_name(0)
            mem = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            return True, f"✅ CUDA 可用: {name} ({mem:.1f}GB) x{count}"
        else:
            return False, "⚠️  CUDA 不可用，将使用 CPU 模式"
    except ImportError:
        return False, "⚠️  torch 未安装"


def verify_imports():
    """验证所有关键导入"""
    print(f"\n{'='*60}")
    print("🔍 验证导入")
    print(f"{'='*60}")

    checks = [
        ("numpy", "numpy"),
        ("cv2", "opencv-python"),
        ("PIL", "Pillow"),
        ("yaml", "PyYAML"),
        ("torch", "torch"),
        ("torchvision", "torchvision"),
        ("ultralytics", "ultralytics"),
        ("customtkinter", "customtkinter"),
        ("matplotlib", "matplotlib"),
        ("seaborn", "seaborn"),
        ("pandas", "pandas"),
        ("sklearn", "scikit-learn"),
        ("tqdm", "tqdm"),
        ("tensorboard", "tensorboard"),
    ]

    ok, fail = 0, 0
    for module, pkg in checks:
        try:
            __import__(module)
            print(f"  ✅ {pkg}")
            ok += 1
        except ImportError:
            print(f"  ❌ {pkg} (未安装)")
            fail += 1

    print(f"\n结果: {ok} 成功 / {fail} 失败")
    return fail == 0


def verify_models(model_dir: Path):
    """验证预训练模型"""
    print(f"\n{'='*60}")
    print("🔍 验证预训练模型")
    print(f"{'='*60}")

    found = 0
    for name, info in PRETRAINED_MODELS.items():
        path = model_dir / f"{name}.pt"
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  ✅ {name}: {size_mb:.1f}MB - {info['desc']}")
            found += 1
        else:
            print(f"  ⬜ {name}: 未下载 - {info['desc']}")

    print(f"\n结果: {found}/{len(PRETRAINED_MODELS)} 模型已下载")
    return found


# ─── 主流程 ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YOLO 训练器依赖与模型自动下载",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 setup_dependencies.py --all          # 安装所有依赖和模型
  python3 setup_dependencies.py --minimal      # 仅安装核心依赖
  python3 setup_dependencies.py --with-torch   # 安装核心 + PyTorch
  python3 setup_dependencies.py --models-only  # 仅下载模型
  python3 setup_dependencies.py --verify       # 仅验证当前环境
        """,
    )
    parser.add_argument("--all", action="store_true", help="安装所有依赖和模型")
    parser.add_argument("--minimal", action="store_true", help="仅安装核心依赖")
    parser.add_argument("--with-torch", action="store_true", help="包含 PyTorch")
    parser.add_argument("--with-ultralytics", action="store_true", help="包含 Ultralytics")
    parser.add_argument("--with-gui", action="store_true", help="包含 GUI 依赖")
    parser.add_argument("--with-optional", action="store_true", help="包含可选依赖")
    parser.add_argument("--models-only", action="store_true", help="仅下载预训练模型")
    parser.add_argument("--models", nargs="+", choices=list(PRETRAINED_MODELS.keys()),
                        help="指定下载的模型，如 --models yolov8n yolov8s")
    parser.add_argument("--model-dir", default="./models", help="模型保存目录 (默认: ./models)")
    parser.add_argument("--verify", action="store_true", help="仅验证环境")
    parser.add_argument("--index-url", default=PIP_INDEX, help="pip 镜像源 URL")

    args = parser.parse_args()

    print("=" * 60)
    print("🚀 YOLO 训练器 - 依赖与模型自动下载")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"平台: {sys.platform}")
    print(f"pip 源: {args.index_url}")

    # 仅验证模式
    if args.verify:
        verify_imports()
        verify_models(Path(args.model_dir))
        cuda_ok, cuda_msg = check_cuda()
        print(f"\n{cuda_msg}")
        return

    # 仅下载模型
    if args.models_only:
        model_dir = Path(args.model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)

        if args.models:
            to_download = {k: PRETRAINED_MODELS[k] for k in args.models}
        else:
            to_download = PRETRAINED_MODELS

        for name, info in to_download.items():
            dest = str(model_dir / f"{name}.pt")
            # 先尝试从 ultralytics 自动下载
            print(f"\n📥 {name}: {info['desc']} (~{info['size_mb']}MB)")
            print(f"   将尝试通过 ultralytics 自动下载...")

        print(f"\n💡 提示: 安装 ultralytics 后，首次使用时会自动下载模型")
        print(f"   也可手动运行: python3 -c \"from ultralytics import YOLO; YOLO('yolov8n.pt')\"")
        return

    # 确定要安装的依赖组
    groups_to_install = ["core"]

    if args.all:
        groups_to_install = ["core", "torch", "ultralytics", "gui", "optional"]
        download_models = True
        model_names = list(PRETRAINED_MODELS.keys())
    elif args.minimal:
        groups_to_install = ["core"]
        download_models = False
        model_names = []
    else:
        if args.with_torch:
            groups_to_install.append("torch")
        if args.with_ultralytics:
            groups_to_install.append("ultralytics")
        if args.with_gui:
            groups_to_install.append("gui")
        if args.with_optional:
            groups_to_install.append("optional")
        download_models = args.with_ultralytics
        model_names = ["yolov8n"] if args.with_ultralytics else []

    # ─── Step 1: 升级 pip ───
    print(f"\n{'='*60}")
    print("📦 Step 1: 升级 pip")
    print(f"{'='*60}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip",
         "-i", args.index_url, "--quiet"],
        timeout=120,
    )

    # ─── Step 2: 安装依赖 ───
    print(f"\n{'='*60}")
    print("📦 Step 2: 安装依赖")
    print(f"{'='*60}")

    results = {}
    for group in groups_to_install:
        pkgs = DEPENDENCIES.get(group, [])
        label = {
            "core": "核心依赖",
            "torch": "PyTorch",
            "ultralytics": "Ultralytics",
            "gui": "GUI 依赖",
            "optional": "可选依赖",
        }.get(group, group)

        results[group] = run_pip_install(pkgs, label)

    # ─── Step 3: 验证安装 ───
    print(f"\n{'='*60}")
    print("🔍 Step 3: 验证安装")
    print(f"{'='*60}")
    all_ok = verify_imports()

    # ─── Step 4: CUDA 检查 ───
    print(f"\n{'='*60}")
    print("🔍 Step 4: CUDA 检查")
    print(f"{'='*60}")
    cuda_ok, cuda_msg = check_cuda()
    print(cuda_msg)

    # ─── Step 5: 下载预训练模型 ───
    if download_models and model_names:
        print(f"\n{'='*60}")
        print("📥 Step 5: 下载预训练模型")
        print(f"{'='*60}")

        model_dir = Path(args.model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)

        # 方法1: 通过 ultralytics 自动下载（推荐）
        try:
            from ultralytics import YOLO
            for name in model_names:
                print(f"\n📥 通过 Ultralytics 下载 {name}...")
                try:
                    model = YOLO(f"{name}.pt")
                    print(f"   ✅ {name} 下载/加载成功")
                except Exception as e:
                    print(f"   ❌ {name} 下载失败: {e}")
        except ImportError:
            print("⚠️  ultralytics 未安装，跳过自动下载")

            # 方法2: 手动下载
            for name in model_names:
                info = PRETRAINED_MODELS[name]
                dest = str(model_dir / f"{name}.pt")
                download_file(info["url"], dest, f"{name} ({info['size_mb']}MB)")

        # 验证模型
        verify_models(model_dir)

    # ─── 总结 ───
    print(f"\n{'='*60}")
    print("📋 安装总结")
    print(f"{'='*60}")
    for group, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {group}")

    if all_ok:
        print(f"\n🎉 所有依赖安装成功！")
    else:
        print(f"\n⚠️  部分依赖安装失败，请检查错误信息")

    print(f"\n💡 下一步:")
    print(f"   1. 运行验证: python3 setup_dependencies.py --verify")
    print(f"   2. 启动 GUI: python3 -m modules.yolo_trainer.gui_tab")
    print(f"   3. 命令行训练: python3 -c \"from modules.yolo_trainer.training.smart_train import SmartTrainer; ...\"")


if __name__ == "__main__":
    main()

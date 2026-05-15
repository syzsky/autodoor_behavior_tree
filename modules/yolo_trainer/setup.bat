@echo off
chcp 65001 >nul 2>&1
title YOLO 训练器 - 环境安装
echo ============================================
echo   YOLO 训练器 - 依赖与模型自动安装
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 升级 python...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo [2/4] 安装核心依赖...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ^
    numpy>=1.24 ^
    opencv-python>=4.8 ^
    Pillow>=10.0 ^
    PyYAML>=6.0

echo.
echo [3/4] 安装 PyTorch (CUDA 12.1)...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ^
    torch>=2.0 ^
    torchvision>=0.15 ^
    --extra-index-url https://download.pytorch.org/whl/cu121

echo.
echo [4/4] 安装 Ultralytics + GUI...
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ^
    ultralytics>=8.2 ^
    customtkinter>=5.2 ^
    matplotlib>=3.7 ^
    tqdm>=4.65

echo.
echo ============================================
echo   验证安装
echo ============================================
python -c "import numpy; print('  numpy:', numpy.__version__)"
python -c "import cv2; print('  opencv:', cv2.__version__)"
python -c "import PIL; print('  Pillow:', PIL.__version__)"
python -c "import torch; print('  torch:', torch.__version__); print('  CUDA:', torch.cuda.is_available())"
python -c "import ultralytics; print('  ultralytics:', ultralytics.__version__)"
python -c "import customtkinter; print('  customtkinter:', customtkinter.__version__)"

echo.
echo ============================================
echo   下载预训练模型 (YOLOv8n)
echo ============================================
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); print('  yolov8n.pt: OK')"

echo.
echo ============================================
echo   安装完成！
echo ============================================
echo.
echo 使用方法:
echo   1. 启动 GUI 训练器:
echo      python -m modules.yolo_trainer.gui_tab
echo.
echo   2. 命令行训练:
echo      python -c "from modules.yolo_trainer.training.smart_train import SmartTrainer; ..."
echo.
pause

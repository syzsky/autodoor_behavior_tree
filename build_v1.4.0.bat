@echo off
chcp 65001 >nul
echo ============================================
echo  AutoDoor Behavior Tree v1.4.0 — 打包脚本
echo ============================================
echo.

echo [1/4] 安装依赖...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo 依赖安装失败！
    pause
    exit /b 1
)

echo.
echo [2/4] 生成构建信息...
python generate_build_info.py
if %ERRORLEVEL% neq 0 (
    echo 构建信息生成失败！
    pause
    exit /b 1
)

echo.
echo [3/4] PyInstaller 打包...
pyinstaller autodoor_bt.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo 打包失败！
    pause
    exit /b 1
)

echo.
echo [4/4] 创建便携版压缩包...
cd dist
powershell -Command "Compress-Archive -Path 'autodoor-behavior-tree-1.4.0-normal\*' -DestinationPath '..\autodoor-behavior-tree-v1.4.0-portable.zip' -Force"
cd ..

echo.
echo ============================================
echo  打包完成！
echo  文件夹: dist\autodoor-behavior-tree-1.4.0-normal\
echo  便携版: autodoor-behavior-tree-v1.4.0-portable.zip
echo ============================================
pause

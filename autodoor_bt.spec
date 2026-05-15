# -*- mode: python ; coding: utf-8 -*-
"""
AutoDoor BehaviorTree - PyInstaller 打包配置（优化版 v2）

体积优化策略:
  1. torch/torchvision: 排除 CUDA/cuDNN/MKL 等不需要的二进制文件
  2. ultralytics: 排除测试文件、示例图片
  3. rapidocr: 排除多余的模型文件（仅保留中英文）
  4. onnxruntime: 排除 CUDA/TensorRT provider
  5. numpy: 排除测试和文档
  6. 全局排除: unittest, test, tests, testing, examples, docs, doc, tutorials
"""

block_cipher = None

import os
import sys
import fnmatch
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

project_root = os.path.abspath('.')


def get_version():
    config_file = os.path.join(project_root, 'build_config.json')
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('version', '0.0.0')
    except Exception:
        return "0.0.0"


def is_debug_build():
    config_file = os.path.join(project_root, 'build_config.json')
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('build_type', 'release') == 'debug'
    except Exception:
        return False


import json

VERSION = get_version()
DEBUG_BUILD = is_debug_build()


# ─── 排除规则 ───────────────────────────────────────

# 排除的模块（不打包）
EXCLUDED_MODULES = [
    # ML 框架（不需要的）
    'tensorflow', 'keras', 'scipy', 'pandas', 'matplotlib',
    'sklearn', 'xgboost', 'lightgbm', 'catboost', 'seaborn',
    'statsmodels', 'plotly', 'bokeh', 'networkx', 'nltk',
    'spacy', 'transformers', 'onnx',
    'jax', 'jaxlib', 'timm', 'diffusers', 'peft',
    'gradio', 'streamlit', 'dash',
    # Web 框架
    'flask', 'django', 'fastapi', 'uvicorn', 'gunicorn',
    'beautifulsoup4', 'selenium', 'webdriver_manager',
    # GUI 框架（不需要的）
    'pyqt5', 'pyside6', 'wxpython', 'tkinterdnd2',
    'pillow_heif', 'PIL._tkinter_finder', 'PIL.ImageQt',
    # 开发工具
    'pkg_resources', 'pycparser', 'cffi',
    'platformdirs', 'pyparsing', 'colorama', 'chardet',
    'IPython', 'jupyter', 'notebook', 'pytest', 'tox',
    'mypy', 'pylint', 'flake8', 'black', 'isort',
    # 其他
    'setuptools', 'pip', 'wheel', 'pkg_resources',
]

# 排除的文件模式（glob）
EXCLUDED_FILE_PATTERNS = [
    # 测试文件
    '*/test/*', '*/tests/*', '*/testing/*',
    '*/test_*.py', '*/_test.py', '*/*_test.py',
    '*/conftest.py', '*/pytest.py',
    # 示例和文档
    '*/example/*', '*/examples/*',
    '*/doc/*', '*/docs/*', '*/tutorial/*', '*/tutorials/*',
    # CUDA / cuDNN（体积巨大，用户运行时自动下载 torch 即可）
    'cudnn*.dll', 'cublas*.dll', 'cusparse*.dll',
    'curand*.dll', 'cusolver*.dll', 'nvrtc*.dll',
    'nvToolsExt*.dll', 'nvblas*.dll',
    # MKL（Intel 数学库，体积大，非必需）
    'mkl*.dll', 'libiomp5md.dll', 'libiomp5md.pdb',
    # ONNX Runtime 多余 provider
    'onnxruntime_providers_cuda.dll',
    'onnxruntime_providers_tensorrt.dll',
    'onnxruntime_providers_openvino.dll',
    'onnxruntime_providers_vitisai.dll',
    'onnxruntime_providers_qnn.dll',
    # torch 多余二进制
    'torch/lib/*.dll',   # torch DLL 通过 hiddenimports 加载
    # Python 开发文件
    '*.pdb', '*.lib', '*.exp', '*.a',
    # 其他大文件
    '*/.git/*', '*/.github/*', '*/LICENSE*', '*/README*', '*/CHANGELOG*',
    '*/.md', '*/.rst', '*/.txt',
]


def _should_exclude(name: str) -> bool:
    """判断文件是否应该被排除"""
    for pattern in EXCLUDED_FILE_PATTERNS:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name.lower(), pattern.lower()):
            return True
    return False


# ─── 数据文件 ───────────────────────────────────────

# 手动指定需要的数据文件（不用 collect_data_files 避免引入过多）
data_files = [
    (os.path.join(project_root, 'assets/sounds/alarm.mp3'), 'assets/sounds'),
    (os.path.join(project_root, 'assets/sounds/temp_reversed.mp3'), 'assets/sounds'),
    (os.path.join(project_root, 'assets/icons/autodoor.ico'), 'assets/icons'),
    (os.path.join(project_root, 'assets/icons/autodoor.png'), 'assets/icons'),
    (os.path.join(project_root, 'config/settings.json'), 'config'),
    (os.path.join(project_root, 'bt_utils/build_info.json'), 'bt_utils'),
]

# ─── 分析 ───────────────────────────────────────────

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=data_files,
    hiddenimports=[
        # bt 核心
        'bt_core', 'bt_core.blackboard', 'bt_core.config', 'bt_core.context',
        'bt_core.engine', 'bt_core.nodes', 'bt_core.registry',
        'bt_core.serializer', 'bt_core.status',
        # bt GUI
        'bt_gui', 'bt_gui.app', 'bt_gui.script_tab', 'bt_gui.settings_tab',
        'bt_gui.theme', 'bt_gui.widgets',
        'bt_gui.bt_editor', 'bt_gui.bt_editor.canvas',
        'bt_gui.bt_editor.constants', 'bt_gui.bt_editor.editor',
        'bt_gui.bt_editor.node_item', 'bt_gui.bt_editor.palette',
        'bt_gui.bt_editor.property', 'bt_gui.bt_editor.toolbar',
        'bt_gui.bt_editor.undo_redo', 'bt_gui.bt_editor.dialogs',
        'bt_gui.editor',
        # bt 节点
        'bt_nodes', 'bt_nodes.actions', 'bt_nodes.actions.alarm',
        'bt_nodes.actions.code', 'bt_nodes.actions.delay',
        'bt_nodes.actions.keyboard', 'bt_nodes.actions.mouse',
        'bt_nodes.actions.script', 'bt_nodes.actions.variable',
        'bt_nodes.conditions', 'bt_nodes.conditions.color',
        'bt_nodes.conditions.image', 'bt_nodes.conditions.number',
        'bt_nodes.conditions.ocr', 'bt_nodes.conditions.variable',
        # bt 工具
        'bt_utils', 'bt_utils.alarm', 'bt_utils.base_input',
        'bt_utils.dd_input', 'bt_utils.image_processor',
        'bt_utils.input_controller', 'bt_utils.input_controller_factory',
        'bt_utils.ocr_manager', 'bt_utils.recorder',
        'bt_utils.screenshot', 'bt_utils.script_executor',
        # 配置
        'config', 'config.settings_manager',
        # 第三方库
        'pygame', 'pygame.mixer',
        'tkinter', 'tkinter.ttk',
        'customtkinter',
        'PIL', 'PIL.Image', 'PIL.ImageGrab',
        'rapidocr', 'onnxruntime',
        'screeninfo', 'screeninfo.common',
        'pynput', 'pynput.keyboard', 'pynput.mouse',
        'pydub', 'requests',
        'numpy', 'numpy.core', 'numpy.core.multiarray',
        'six', 'imagehash', 'cv2',
        # === YOLO 训练器模块 ===
        'modules.yolo_trainer',
        'modules.yolo_trainer.capture',
        'modules.yolo_trainer.capture.window_capture',
        'modules.yolo_trainer.capture.screen_stream',
        'modules.yolo_trainer.capture.live_view',
        'modules.yolo_trainer.training',
        'modules.yolo_trainer.training.trainer',
        'modules.yolo_trainer.training.smart_train',
        'modules.yolo_trainer.annotation',
        'modules.yolo_trainer.annotation.smart_labeler',
        'modules.yolo_trainer.bt_nodes',
        'modules.yolo_trainer.gui_tab',
        'modules.yolo_trainer.utils',
        'modules.yolo_trainer.utils.config',
        'modules.yolo_trainer.utils.visualizer',
        'modules.yolo_trainer.utils.dataset_utils',
        'modules.yolo_trainer.runtime_setup',
        'ultralytics', 'ultralytics.models', 'ultralytics.models.yolo',
        'torch', 'torchvision',
        # Windows API
        'win32gui', 'win32ui', 'win32con', 'win32api',
        'win32process', 'pywintypes', 'pythoncom',
    ] + collect_submodules('bt_core') + collect_submodules('bt_gui') + collect_submodules('bt_nodes') + collect_submodules('bt_utils'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ─── 过滤二进制文件 ─────────────────────────────────

# 排除 CUDA/cuDNN/MKL 等大块头 DLL
exclude_binaries = [
    'cudnn', 'cublas', 'cusparse', 'curand', 'cusolver',
    'nvrtc', 'nvToolsExt', 'nvblas',
    'mkl', 'libiomp',
    'onnxruntime_providers_cuda',
    'onnxruntime_providers_tensorrt',
    'onnxruntime_providers_openvino',
    'onnxruntime_providers_vitisai',
    'onnxruntime_providers_qnn',
]

a.binaries = [
    x for x in a.binaries
    if not any(ex.lower() in x[0].lower() for ex in exclude_binaries)
    and not _should_exclude(x[0])
]

# 过滤数据文件
a.datas = [
    x for x in a.datas
    if not _should_exclude(x[0])
]

print(f"📊 打包统计:")
print(f"   二进制文件: {len(a.binaries)} 个")
print(f"   数据文件: {len(a.datas)} 个")
print(f"   脚本: {len(a.scripts)} 个")

# ─── 打包 ───────────────────────────────────────────

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=f'autodoor-behaviortree-{VERSION}-normal',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=DEBUG_BUILD,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'assets', 'icons', 'autodoor.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=f'autodoor-behaviortree-{VERSION}-normal',
)

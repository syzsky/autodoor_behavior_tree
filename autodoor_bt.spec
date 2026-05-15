# -*- mode: python ; coding: utf-8 -*-
"""
AutoDoor BehaviorTree - PyInstaller 打包配置（优化版 v2）

体积优化策略:
  1. 排除 CUDA/cuDNN DLL（~150MB+）
  2. 排除 MKL 库（~80MB+）
  3. 排除测试/示例/文档文件
  4. 排除不需要的 ONNX Runtime provider
  5. torch/torchvision 数据文件选择性排除
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
            import json
            config = json.load(f)
            return config.get('version', '0.0.0')
    except Exception:
        return "0.0.0"


def is_debug_build():
    config_file = os.path.join(project_root, 'build_config.json')
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            import json
            config = json.load(f)
            return config.get('build_type', 'release') == 'debug'
    except Exception:
        return False


VERSION = get_version()
DEBUG_BUILD = is_debug_build()


# ─── 数据文件 ───────────────────────────────────────

data_files = [
    (os.path.join(project_root, 'assets/sounds/alarm.mp3'), 'assets/sounds'),
    (os.path.join(project_root, 'assets/sounds/temp_reversed.mp3'), 'assets/sounds'),
    (os.path.join(project_root, 'assets/icons/autodoor.ico'), 'assets/icons'),
    (os.path.join(project_root, 'assets/icons/autodoor.png'), 'assets/icons'),
    (os.path.join(project_root, 'config/settings.json'), 'config'),
    (os.path.join(project_root, 'bt_utils/build_info.json'), 'bt_utils'),
    # rapidocr 和 ultralytics 数据文件必须保留
    *collect_data_files('rapidocr'),
    *collect_data_files('ultralytics'),
    # torch 数据文件通过过滤添加（排除 CUDA）
]

# 过滤 torch 数据文件：排除 CUDA/cuDNN 相关
torch_datas = collect_data_files('torch')
for src, dst in torch_datas:
    # 跳过 CUDA/cuDNN/MKL 二进制
    basename = os.path.basename(src).lower()
    if any(kw in basename for kw in ['cudnn', 'cublas', 'cusparse', 'curand', 'cusolver',
                                       'nvrtc', 'nvtoolsext', 'nvblas', 'mkl', 'libiomp']):
        continue
    # 跳过测试和示例
    if any(kw in src.lower() for kw in ['/test/', '/tests/', '/testing/', '/example/', '/examples/',
                                         '/doc/', '/docs/', '/tutorial/', '/tutorials/']):
        continue
    data_files.append((src, dst))


# ─── 排除模块 ───────────────────────────────────────

EXCLUDED_MODULES = [
    'tensorflow', 'keras', 'scipy', 'pandas', 'matplotlib',
    'sklearn', 'xgboost', 'lightgbm', 'catboost', 'seaborn',
    'statsmodels', 'plotly', 'bokeh', 'networkx', 'nltk',
    'spacy', 'transformers', 'onnx',
    'jax', 'jaxlib', 'timm', 'diffusers', 'peft',
    'gradio', 'streamlit', 'dash',
    'flask', 'django', 'fastapi', 'uvicorn', 'gunicorn',
    'beautifulsoup4', 'selenium', 'webdriver_manager',
    'pyqt5', 'pyside6', 'wxpython', 'tkinterdnd2',
    'pillow_heif', 'PIL._tkinter_finder', 'PIL.ImageQt',
    'numpy.testing', 'numpy.f2py', 'numpy.distutils',
    'pkg_resources',
    'pycparser', 'cffi',
    'platformdirs', 'pyparsing', 'colorama', 'chardet',
    'IPython', 'jupyter', 'notebook',
    'pytest', 'tox', 'mypy', 'pylint', 'flake8',
    'setuptools', 'pip', 'wheel',
]


# ─── 分析 ───────────────────────────────────────────

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=data_files,
    hiddenimports=[
        'bt_core', 'bt_core.blackboard', 'bt_core.config', 'bt_core.context',
        'bt_core.engine', 'bt_core.nodes', 'bt_core.registry',
        'bt_core.serializer', 'bt_core.status',
        'bt_gui', 'bt_gui.app', 'bt_gui.script_tab', 'bt_gui.settings_tab',
        'bt_gui.theme', 'bt_gui.widgets',
        'bt_gui.bt_editor', 'bt_gui.bt_editor.canvas',
        'bt_gui.bt_editor.constants', 'bt_gui.bt_editor.editor',
        'bt_gui.bt_editor.node_item', 'bt_gui.bt_editor.palette',
        'bt_gui.bt_editor.property', 'bt_gui.bt_editor.toolbar',
        'bt_gui.bt_editor.undo_redo', 'bt_gui.dialogs',
        'bt_gui.editor',
        'bt_nodes', 'bt_nodes.actions', 'bt_nodes.actions.alarm',
        'bt_nodes.actions.code', 'bt_nodes.actions.delay',
        'bt_nodes.actions.keyboard', 'bt_nodes.actions.mouse',
        'bt_nodes.actions.script', 'bt_nodes.actions.variable',
        'bt_nodes.conditions', 'bt_nodes.conditions.color',
        'bt_nodes.conditions.image', 'bt_nodes.conditions.number',
        'bt_nodes.conditions.ocr', 'bt_nodes.conditions.variable',
        'bt_utils', 'bt_utils.alarm', 'bt_utils.base_input',
        'bt_utils.dd_input', 'bt_utils.image_processor',
        'bt_utils.input_controller', 'bt_utils.input_controller_factory',
        'bt_utils.ocr_manager', 'bt_utils.recorder',
        'bt_utils.screenshot', 'bt_utils.script_executor',
        'config', 'config.settings_manager',
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

exclude_binaries = [
    'cudnn', 'cublas', 'cusparse', 'curand', 'cusolver',
    'nvrtc', 'nvToolsExt', 'nvblas',
    'mkl', 'libiomp',
    'onnxruntime_providers_cuda',
    'onnxruntime_providers_tensorrt',
    'onnxruntime_providers_openvino',
]

a.binaries = [
    x for x in a.binaries
    if not any(ex.lower() in x[0].lower() for ex in exclude_binaries)
]

print(f"📊 打包统计: binaries={len(a.binaries)}, datas={len(a.datas)}")

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

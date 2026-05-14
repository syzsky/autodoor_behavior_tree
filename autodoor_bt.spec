# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
import sys
import json
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
project_root = os.path.abspath('.')

def get_version():
    """从 build_config.json 读取版本号"""
    config_file = os.path.join(project_root, 'build_config.json')
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            version = config.get('version', '0.0.0')
            return version
    except Exception:
        return "0.0.0"

def is_debug_build():
    """检查是否为 debug 构建"""
    config_file = os.path.join(project_root, 'build_config.json')
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('build_type', 'release') == 'debug'
    except Exception:
        return False

VERSION = get_version()
DEBUG_BUILD = is_debug_build()

data_files = [
    (os.path.join(project_root, 'assets/sounds/alarm.mp3'), 'assets/sounds'),
    (os.path.join(project_root, 'assets/sounds/temp_reversed.mp3'), 'assets/sounds'),
    (os.path.join(project_root, 'assets/icons/autodoor.ico'), 'assets/icons'),
    (os.path.join(project_root, 'assets/icons/autodoor.png'), 'assets/icons'),
    (os.path.join(project_root, 'config/settings.json'), 'config'),
    (os.path.join(project_root, 'bt_utils/build_info.json'), 'bt_utils'),
] + collect_data_files('rapidocr') + collect_data_files('ultralytics') + collect_data_files('torch')

binaries = []

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=binaries,
    datas=data_files,
    hiddenimports=[
        'bt_core',
        'bt_core.blackboard',
        'bt_core.config',
        'bt_core.context',
        'bt_core.engine',
        'bt_core.nodes',
        'bt_core.registry',
        'bt_core.serializer',
        'bt_core.status',
        
        'bt_gui',
        'bt_gui.app',
        'bt_gui.script_tab',
        'bt_gui.settings_tab',
        'bt_gui.theme',
        'bt_gui.widgets',
        'bt_gui.bt_editor',
        'bt_gui.bt_editor.canvas',
        'bt_gui.bt_editor.constants',
        'bt_gui.bt_editor.editor',
        'bt_gui.bt_editor.node_item',
        'bt_gui.bt_editor.palette',
        'bt_gui.bt_editor.property',
        'bt_gui.bt_editor.toolbar',
        'bt_gui.bt_editor.undo_redo',
        'bt_gui.dialogs',
        'bt_gui.editor',
        
        'bt_nodes',
        'bt_nodes.actions',
        'bt_nodes.actions.alarm',
        'bt_nodes.actions.code',
        'bt_nodes.actions.delay',
        'bt_nodes.actions.keyboard',
        'bt_nodes.actions.mouse',
        'bt_nodes.actions.script',
        'bt_nodes.actions.variable',
        'bt_nodes.conditions',
        'bt_nodes.conditions.color',
        'bt_nodes.conditions.image',
        'bt_nodes.conditions.number',
        'bt_nodes.conditions.ocr',
        'bt_nodes.conditions.variable',
        
        'bt_utils',
        'bt_utils.alarm',
        'bt_utils.base_input',
        'bt_utils.dd_input',
        'bt_utils.image_processor',
        'bt_utils.input_controller',
        'bt_utils.input_controller_factory',
        'bt_utils.ocr_manager',
        'bt_utils.recorder',
        'bt_utils.screenshot',
        'bt_utils.script_executor',
        
        'config',
        'config.settings_manager',
        
        'pygame',
        'pygame.mixer',
        'tkinter',
        'tkinter.ttk',
        'customtkinter',
        'PIL',
        'PIL.Image',
        'PIL.ImageGrab',
        'rapidocr',
        'onnxruntime',
        'screeninfo',
        'screeninfo.common',
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        'pydub',
        'requests',
        'numpy',
        'numpy.core',
        'numpy.core.multiarray',
        'six',
        'imagehash',
        'cv2',
        
        # === YOLO 训练器模块 ===
        'modules.yolo_trainer',
        'modules.yolo_trainer.capture',
        'modules.yolo_trainer.capture.window_capture',
        'modules.yolo_trainer.capture.screen_stream',
        'modules.yolo_trainer.training',
        'modules.yolo_trainer.training.trainer',
        'modules.yolo_trainer.annotation',
        'modules.yolo_trainer.annotation.smart_labeler',
        'modules.yolo_trainer.bt_nodes',
        'modules.yolo_trainer.gui_tab',
        'modules.yolo_trainer.utils',
        'modules.yolo_trainer.utils.config',
        'modules.yolo_trainer.utils.visualizer',
        'modules.yolo_trainer.utils.dataset_utils',
        'ultralytics',
        'ultralytics.models',
        'ultralytics.models.yolo',
        'torch',
        'torchvision',
        
        'win32gui',
        'win32ui',
        'win32con',
        'win32api',
        'win32process',
        'pywintypes',
        'pythoncom',
    ] + collect_submodules('bt_core') + collect_submodules('bt_gui') + collect_submodules('bt_nodes') + collect_submodules('bt_utils'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
        'platformdirs', 'pyparsing', 'colorama', 'chardet'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exclude_binaries = [
    'onnxruntime_providers_cuda.dll',
    'onnxruntime_providers_tensorrt.dll',
]
a.binaries = [x for x in a.binaries if not any(ex in x[0] for ex in exclude_binaries)]

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

"""bt_utils 包

所有子模块均通过 __getattr__ 延迟导入，避免因可选依赖缺失导致整个包不可用。
"""

# 名称 → 子模块路径的映射（相对导入）
_LAZY_MODULES = {
    # screenshot
    "ScreenshotManager": ".screenshot",
    # input controller
    "InputController": ".input_controller_factory",
    "BaseInputController": ".base_input",
    # ocr
    "OCRManager": ".ocr_manager",
    # image
    "ImageProcessor": ".image_processor",
    # recorder / executor
    "ScriptRecorder": ".recorder",
    "ScriptExecutor": ".script_executor",
    # alarm
    "AlarmPlayer": ".alarm",
    # consistency checker
    "ConsistencyChecker": ".consistency_checker",
    "ConsistencyReport": ".consistency_checker",
    "ConsistencyIssue": ".consistency_checker",
    "run_consistency_check": ".consistency_checker",
    "print_consistency_report": ".consistency_checker",
    # proxies
    "InputProxy": ".proxies",
    "ScreenshotProxy": ".proxies",
    "AlarmProxy": ".proxies",
    # coordinate
    "CoordinateConverter": ".coordinate",
    # window capture
    "WindowCapture": ".window_capture",
    # resource manager
    "ResourceManager": ".resource_manager",
    "get_resource_manager": ".resource_manager",
    "get_app_root": ".resource_manager",
    "get_resource_path": ".resource_manager",
}

# config 相关：名称 → (模块路径, 属性名)
_LAZY_CONFIG = {
    "ConfigManager": ("config.settings_manager", "SettingsManager"),
    "SettingsManager": ("config.settings_manager", "SettingsManager"),
    "BlackboardConfig": ("config.settings_manager", "BlackboardConfig"),
    "SessionConfig": ("config.settings_manager", "SessionConfig"),
    "BehaviorTreeConfig": ("config.settings_manager", "SessionConfig"),
    "get_default_position_key": ("config.settings_manager", "get_default_position_key"),
    "get_default_value_key": ("config.settings_manager", "get_default_value_key"),
    "get_blackboard_config": ("config.settings_manager", "get_blackboard_config"),
    "get_behavior_tree_config": ("config.settings_manager", "get_session_config"),
    "get_session_config": ("config.settings_manager", "get_session_config"),
    "get_settings_manager": ("config.settings_manager", "get_settings_manager"),
}


def __getattr__(name):
    """延迟导入所有子模块，避免可选依赖缺失时阻断整个包"""
    import importlib

    if name in _LAZY_MODULES:
        mod = importlib.import_module(_LAZY_MODULES[name], __name__)
        return getattr(mod, name)

    if name in _LAZY_CONFIG:
        mod_path, attr = _LAZY_CONFIG[name]
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ScreenshotManager",
    "InputController",
    "OCRManager",
    "ImageProcessor",
    "ScriptRecorder",
    "ScriptExecutor",
    "AlarmPlayer",
    "ConfigManager",
    "BehaviorTreeConfig",
    "BlackboardConfig",
    "SessionConfig",
    "get_default_position_key",
    "get_default_value_key",
    "get_blackboard_config",
    "get_behavior_tree_config",
    "get_session_config",
    "get_settings_manager",
    "ConsistencyChecker",
    "ConsistencyReport",
    "ConsistencyIssue",
    "run_consistency_check",
    "print_consistency_report",
    "InputProxy",
    "ScreenshotProxy",
    "AlarmProxy",
    "CoordinateConverter",
    "WindowCapture",
    "BaseInputController",
    "ResourceManager",
    "get_resource_manager",
    "get_app_root",
    "get_resource_path",
]

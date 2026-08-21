"""config 命令 — 配置管理"""
import sys


def cmd_config(args):
    """配置管理"""
    action = args.config_action

    if action is None:
        print("请指定操作: get/set/list/path")
        sys.exit(1)

    from config.settings_manager import get_settings_manager
    settings = get_settings_manager()

    if action == "get":
        value = settings.get(args.key)
        if value is not None:
            print(f"{args.key} = {value}")
        else:
            print(f"配置项不存在: {args.key}")
            sys.exit(1)

    elif action == "set":
        # 尝试解析值类型
        value = _parse_value(args.value)
        settings.set(args.key, value)
        settings.save_settings()
        print(f"已设置: {args.key} = {value}")

    elif action == "list":
        data = settings.get_all_settings()
        for key in sorted(data.keys()):
            print(f"{key} = {data[key]}")

    elif action == "path":
        # 显示实际配置文件路径（位于用户配置目录）
        print(settings.config_file)


def _parse_value(value):
    """尝试解析值类型"""
    # 布尔值
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False
    # 数字
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    # 字符串
    return value

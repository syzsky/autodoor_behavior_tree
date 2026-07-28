"""plugin 命令 — 插件管理"""
import sys
import os


def cmd_plugin(args):
    """插件管理"""
    action = getattr(args, "plugin_action", None)

    if action is None:
        print("用法: autodoor-bt plugin <list|load|start|stop|info>")
        sys.exit(1)

    from bt_plugins.base import PluginContext
    from bt_plugins.loader import PluginLoader
    from config.settings_manager import get_settings_manager

    settings = get_settings_manager()
    context = PluginContext(settings=settings)
    loader = PluginLoader(context)

    # 先扫描和加载已知的插件
    builtin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bt_plugins", "builtin")
    if os.path.isdir(builtin_dir):
        infos = loader.scan(builtin_dir)
        for info in infos:
            plugin_dir = os.path.join(builtin_dir, info.name)
            loader.load_plugin(plugin_dir)

    # 也扫描用户插件目录
    user_dir = os.path.join(os.getcwd(), "plugins")
    if os.path.isdir(user_dir):
        infos = loader.scan(user_dir)
        for info in infos:
            plugin_dir = os.path.join(user_dir, info.name)
            loader.load_plugin(plugin_dir)

    if action == "list":
        _list_plugins(loader)
    elif action == "load":
        _load_plugin(loader, args)
    elif action == "start":
        _start_plugin(loader, args)
    elif action == "stop":
        _stop_plugin(loader, args)
    elif action == "info":
        _show_info(loader, args)


def _list_plugins(loader):
    """列出插件"""
    infos = loader.list_plugins()
    if not infos:
        print("无已加载的插件")
        return

    print(f"插件列表 ({len(infos)} 个):")
    print("-" * 60)
    for info in infos:
        status = "已启动" if loader.is_started(info.name) else "已停止"
        print(f"  {info.display_name} ({info.name}) v{info.version}")
        print(f"    作者: {info.author}")
        print(f"    描述: {info.description}")
        print(f"    分类: {info.category}")
        print(f"    状态: {status}")
        print("-" * 60)


def _load_plugin(loader, args):
    """加载插件"""
    if loader.load_plugin(args.path):
        print(f"插件加载成功: {args.path}")
    else:
        print(f"插件加载失败: {args.path}")
        sys.exit(1)


def _start_plugin(loader, args):
    """启动插件"""
    if loader.start_plugin(args.name):
        print(f"插件已启动: {args.name}")
    else:
        print(f"插件启动失败: {args.name}")
        sys.exit(1)


def _stop_plugin(loader, args):
    """停止插件"""
    loader.stop_plugin(args.name)
    print(f"插件已停止: {args.name}")


def _show_info(loader, args):
    """显示插件详情"""
    info = loader.get_plugin_info(args.name)
    if not info:
        print(f"未找到插件: {args.name}")
        sys.exit(1)

    print(f"插件详情:")
    print(f"  名称: {info.name}")
    print(f"  显示名: {info.display_name}")
    print(f"  版本: {info.version}")
    print(f"  作者: {info.author}")
    print(f"  描述: {info.description}")
    print(f"  分类: {info.category}")
    print(f"  最低版本: {info.min_app_version or '无限制'}")
    print(f"  依赖: {', '.join(info.dependencies) if info.dependencies else '无'}")

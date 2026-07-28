"""plugin 命令 — 插件管理"""
def cmd_plugin(args):
    action = getattr(args, 'plugin_action', None)
    if action is None:
        print("请指定操作: list/load/start/stop/info")
        return
    print(f"插件{action}功能开发中...")

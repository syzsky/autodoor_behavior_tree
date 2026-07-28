"""AutoDoor Behavior Tree CLI"""
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="autodoor-bt",
        description="AutoDoor 行为树 CLI 工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run 命令
    run_parser = subparsers.add_parser("run", help="运行行为树")
    run_parser.add_argument("tree_file", help="行为树 JSON 文件路径")
    run_parser.add_argument("--headless", action="store_true", help="无 GUI 模式")
    run_parser.add_argument("--project", default=None, help="项目根目录")
    run_parser.add_argument("--bus", action="store_true", help="启用消息总线")
    run_parser.add_argument("--rest", action="store_true", help="启用 REST API")
    run_parser.add_argument("--rest-host", default="127.0.0.1")
    run_parser.add_argument("--rest-port", type=int, default=8080)
    run_parser.add_argument("--ws", action="store_true", help="启用 WebSocket 服务")
    run_parser.add_argument("--ws-host", default="127.0.0.1")
    run_parser.add_argument("--ws-port", type=int, default=8765)
    run_parser.add_argument("--plugins", action="store_true", help="启用插件系统")

    # status 命令
    subparsers.add_parser("status", help="查询运行状态")

    # stop 命令
    stop_parser = subparsers.add_parser("stop", help="停止行为树")
    stop_parser.add_argument("tree_id", nargs="?", default=None)
    stop_parser.add_argument("--all", action="store_true")
    stop_parser.add_argument("--force", action="store_true")

    # schedule 命令
    sched_parser = subparsers.add_parser("schedule", help="定时调度管理")
    sched_sub = sched_parser.add_subparsers(dest="schedule_action")
    sched_add = sched_sub.add_parser("add", help="添加定时任务")
    sched_add.add_argument("tree_file")
    sched_add.add_argument("--cron", default=None)
    sched_add.add_argument("--interval", default=None)
    sched_add.add_argument("--once", default=None)
    sched_add.add_argument("--name", default="")
    sched_add.add_argument("--headless", action="store_true")
    sched_sub.add_parser("list", help="列出定时任务")
    sched_rm = sched_sub.add_parser("remove", help="删除定时任务")
    sched_rm.add_argument("task_id")

    # daemon 命令
    daemon_parser = subparsers.add_parser("daemon", help="守护进程模式")
    daemon_parser.add_argument("--start", action="store_true")
    daemon_parser.add_argument("--stop", action="store_true")
    daemon_parser.add_argument("--restart", action="store_true")
    daemon_parser.add_argument("--status", action="store_true")
    daemon_parser.add_argument("--foreground", action="store_true")

    # remote 命令
    remote_parser = subparsers.add_parser("remote", help="远程控制")
    remote_parser.add_argument("target", help="host:port")
    remote_parser.add_argument("action", choices=["status", "trees", "start", "stop", "blackboard", "nodes"])
    remote_parser.add_argument("--tree-id", default=None)
    remote_parser.add_argument("--token", default=None)
    remote_parser.add_argument("--json", action="store_true")

    # plugin 命令
    plugin_parser = subparsers.add_parser("plugin", help="插件管理")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_action")
    plugin_sub.add_parser("list", help="列出已安装插件")
    plugin_load = plugin_sub.add_parser("load", help="加载插件")
    plugin_load.add_argument("path", help="插件目录路径")
    plugin_start = plugin_sub.add_parser("start", help="启动插件")
    plugin_start.add_argument("name")
    plugin_stop = plugin_sub.add_parser("stop", help="停止插件")
    plugin_stop.add_argument("name")
    plugin_info = plugin_sub.add_parser("info", help="查看插件详情")
    plugin_info.add_argument("name")

    # config 命令
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_get = config_sub.add_parser("get", help="读取配置")
    config_get.add_argument("key")
    config_set = config_sub.add_parser("set", help="设置配置")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_sub.add_parser("list", help="列出所有配置")
    config_sub.add_parser("path", help="显示配置文件路径")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # 路由到对应命令处理函数
    _dispatch(args)


def _dispatch(args):
    """路由到对应命令"""
    cmd = args.command
    if cmd == "run":
        from bt_cli.commands.run import cmd_run
        cmd_run(args)
    elif cmd == "status":
        from bt_cli.commands.status import cmd_status
        cmd_status(args)
    elif cmd == "stop":
        from bt_cli.commands.stop import cmd_stop
        cmd_stop(args)
    elif cmd == "schedule":
        from bt_cli.commands.schedule import cmd_schedule
        cmd_schedule(args)
    elif cmd == "daemon":
        from bt_cli.commands.daemon import cmd_daemon
        cmd_daemon(args)
    elif cmd == "remote":
        from bt_cli.commands.remote import cmd_remote
        cmd_remote(args)
    elif cmd == "plugin":
        from bt_cli.commands.plugin import cmd_plugin
        cmd_plugin(args)
    elif cmd == "config":
        from bt_cli.commands.config import cmd_config
        cmd_config(args)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""schedule 命令 — 定时调度管理"""
import sys
from bt_cli.scheduler import Scheduler


def cmd_schedule(args):
    """定时调度管理"""
    action = args.schedule_action

    if action is None:
        print("用法: autodoor-bt schedule <add|list|remove|run|enable|disable>")
        sys.exit(1)

    scheduler = Scheduler()

    if action == "add":
        _add_task(scheduler, args)
    elif action == "list":
        _list_tasks(scheduler)
    elif action == "remove":
        if scheduler.remove_task(args.task_id):
            print(f"已删除任务: {args.task_id}")
        else:
            print(f"未找到任务: {args.task_id}")
            sys.exit(1)
    elif action == "run":
        if scheduler.run_task_now(args.task_id):
            print(f"已触发执行: {args.task_id}")
        else:
            print(f"未找到任务: {args.task_id}")
            sys.exit(1)
    elif action == "enable":
        if scheduler.enable_task(args.task_id):
            print(f"已启用任务: {args.task_id}")
        else:
            print(f"未找到任务: {args.task_id}")
            sys.exit(1)
    elif action == "disable":
        if scheduler.disable_task(args.task_id):
            print(f"已禁用任务: {args.task_id}")
        else:
            print(f"未找到任务: {args.task_id}")
            sys.exit(1)


def _add_task(scheduler, args):
    """添加定时任务"""
    if not args.cron and not args.interval and not args.once:
        print("错误: 必须指定 --cron、--interval 或 --once")
        sys.exit(1)

    task_id = scheduler.add_task(
        name=args.name,
        tree_file=args.tree_file,
        cron=args.cron,
        interval=args.interval,
        once=args.once,
        headless=args.headless,
    )
    print(f"已添加定时任务:")
    print(f"  任务 ID: {task_id}")
    print(f"  名称: {args.name or args.tree_file}")
    print(f"  行为树: {args.tree_file}")
    if args.cron:
        print(f"  Cron: {args.cron}")
    if args.interval:
        print(f"  间隔: {args.interval}")
    if args.once:
        print(f"  定时: {args.once}")
    print(f"  模式: {'Headless' if args.headless else 'GUI'}")


def _list_tasks(scheduler):
    """列出所有定时任务"""
    tasks = scheduler.list_tasks()
    if not tasks:
        print("无定时任务")
        return

    print(f"定时任务列表 ({len(tasks)} 个):")
    print("-" * 80)
    for task in tasks:
        status = "启用" if task.enabled else "禁用"
        schedule = task.cron or task.interval or task.once or "未设置"
        print(f"  ID: {task.task_id}")
        print(f"  名称: {task.name}")
        print(f"  行为树: {task.tree_file}")
        print(f"  调度: {schedule}")
        print(f"  状态: {status}")
        print(f"  执行次数: {task.run_count}")
        if task.last_run:
            print(f"  上次执行: {task.last_run}")
        print("-" * 80)

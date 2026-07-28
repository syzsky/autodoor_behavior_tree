"""remote 命令 — 远程控制"""
import sys


def cmd_remote(args):
    """远程控制"""
    base_url = f"http://{args.target}"
    headers = {}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    try:
        import requests
    except ImportError:
        print("错误: 需要 requests 库，请安装: pip install requests")
        sys.exit(4)

    try:
        if args.action == "status":
            _do_status(base_url, headers, args)
        elif args.action == "trees":
            _do_trees(base_url, headers, args)
        elif args.action == "start":
            _do_start(base_url, headers, args)
        elif args.action == "stop":
            _do_stop(base_url, headers, args)
        elif args.action == "blackboard":
            _do_blackboard(base_url, headers, args)
        elif args.action == "nodes":
            _do_nodes(base_url, headers, args)
    except requests.ConnectionError:
        print(f"无法连接到 {args.target}")
        sys.exit(1)


def _do_status(base_url, headers, args):
    """查询远程状态"""
    import requests
    resp = requests.get(f"{base_url}/api/v1/health", headers=headers, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"服务状态: {data.get('status', 'unknown')}")
        print(f"版本: {data.get('version', 'N/A')}")
    else:
        print(f"查询失败: {resp.status_code}")


def _do_trees(base_url, headers, args):
    """列出远程行为树"""
    import requests
    resp = requests.get(f"{base_url}/api/v1/trees", headers=headers, timeout=10)
    if resp.status_code == 200:
        trees = resp.json()
        if not trees:
            print("无行为树")
            return
        print(f"行为树列表 ({len(trees)} 个):")
        for tree in trees:
            tree_id = tree.get("tree_id", "N/A")
            status = tree.get("status", "unknown")
            print(f"  - {tree_id}: {status}")
    else:
        print(f"查询失败: {resp.status_code}")


def _do_start(base_url, headers, args):
    """远程启动行为树"""
    import requests
    if not args.tree_id:
        print("错误: 需要 --tree-id")
        sys.exit(1)
    resp = requests.post(f"{base_url}/api/v1/trees/{args.tree_id}/start", headers=headers, timeout=10)
    if resp.status_code == 200:
        print(f"已发送启动命令: {args.tree_id}")
    else:
        print(f"启动失败: {resp.status_code} - {resp.text}")


def _do_stop(base_url, headers, args):
    """远程停止行为树"""
    import requests
    if not args.tree_id:
        print("错误: 需要 --tree-id")
        sys.exit(1)
    resp = requests.post(f"{base_url}/api/v1/trees/{args.tree_id}/stop", headers=headers, timeout=10)
    if resp.status_code == 200:
        print(f"已发送停止命令: {args.tree_id}")
    else:
        print(f"停止失败: {resp.status_code} - {resp.text}")


def _do_blackboard(base_url, headers, args):
    """查询远程黑板"""
    import requests
    if not args.tree_id:
        print("错误: 需要 --tree-id")
        sys.exit(1)
    resp = requests.get(f"{base_url}/api/v1/trees/{args.tree_id}/blackboard", headers=headers, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"黑板变量 ({len(data)} 个):")
        for key, value in data.items():
            print(f"  {key} = {value}")
    else:
        print(f"查询失败: {resp.status_code}")


def _do_nodes(base_url, headers, args):
    """查询远程节点"""
    import requests
    if not args.tree_id:
        print("错误: 需要 --tree-id")
        sys.exit(1)
    resp = requests.get(f"{base_url}/api/v1/trees/{args.tree_id}/nodes", headers=headers, timeout=10)
    if resp.status_code == 200:
        nodes = resp.json()
        print(f"节点列表 ({len(nodes)} 个):")
        for node in nodes:
            node_id = node.get("node_id", "N/A")
            node_type = node.get("node_type", "N/A")
            name = node.get("name", "")
            status = node.get("status", "unknown")
            print(f"  - [{node_type}] {name} ({node_id}): {status}")
    else:
        print(f"查询失败: {resp.status_code}")

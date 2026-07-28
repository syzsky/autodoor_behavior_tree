"""stop 命令 — 停止行为树"""
import sys


def cmd_stop(args):
    """停止行为树"""
    if args.all:
        print("停止所有行为树...")
        # 通过 REST API 或信号停止
        _stop_via_api(None)
    elif args.tree_id:
        print(f"停止行为树: {args.tree_id}")
        _stop_via_api(args.tree_id)
    else:
        print("请指定要停止的行为树 ID，或使用 --all 停止所有")
        sys.exit(1)


def _stop_via_api(tree_id):
    """通过 REST API 停止行为树"""
    try:
        import requests
        base_url = "http://127.0.0.1:8080"
        if tree_id:
            resp = requests.post(f"{base_url}/api/v1/trees/{tree_id}/stop", timeout=5)
        else:
            resp = requests.get(f"{base_url}/api/v1/trees", timeout=5)
            trees = resp.json()
            for tree in trees:
                tid = tree.get("tree_id")
                if tid:
                    requests.post(f"{base_url}/api/v1/trees/{tid}/stop", timeout=5)
        print("停止命令已发送")
    except requests.ConnectionError:
        print("无法连接到 REST API 服务（服务未启动？）")
    except Exception as e:
        print(f"停止失败: {e}")

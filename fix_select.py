
import sys, json, ast, subprocess
sys.path.insert(0, "/tmp/autodoor_behavior_tree")

if not hasattr(subprocess, "STARTUPINFO"):
    class _C:
        def __init__(self): self.dwFlags=0; self.wShowWindow=0
    subprocess.STARTUPINFO = _C

from bt_core.registry import register_all_nodes
from bt_cli.ai.node_selector import NodeSelector, NodeSelectionError
register_all_nodes()

plan = json.load(open("/tmp/autodoor_behavior_tree/.ai/plan.json", encoding="utf-8"))
selector = NodeSelector()
structure = None
try:
    structure = selector.select(plan)
except NodeSelectionError as e:
    msg = str(e)
    if "节点结构无效" in msg:
        raw = msg.split("节点结构无效: ", 1)[1]
        structure = ast.literal_eval(raw)
        print("已从异常消息恢复 structure")

if structure is None:
    raise SystemExit("无法获取 structure")

# 修复无效 children 引用
all_ids = {n["id"] for n in structure["nodes"]}
fixed = 0
for node in structure["nodes"]:
    old = list(node.get("children", []))
    new = [c for c in old if c in all_ids]
    if len(new) != len(old):
        node["children"] = new
        fixed += 1
        print(f"修复 {node['id']}: children {old} -> {new}")

json.dump(structure, open("/tmp/autodoor_behavior_tree/.ai/structure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"已保存 structure.json, {len(structure['nodes'])} 个节点, 修复 {fixed} 处")

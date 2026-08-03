# bt_cli/ai/node_spec_exporter.py
"""从 NodeRegistry 动态导出节点完整规格

替代旧方案中写死在 prompt 中的节点清单。
新增节点或插件节点注册后，AI 自动获得新规格，无需手动更新。
"""
from typing import Dict, Type

from bt_core.registry import NodeRegistry
from bt_core.nodes import Node, CompositeNode, ConditionNode, ActionNode


# 节点参数文档 — 每种节点类型的关键参数说明
_NODE_PARAM_DOCS = {
    "StartNode": {
        "params": [
            {"name": "bind_window", "type": "bool", "default": False, "desc": "是否绑定窗口"},
            {"name": "window_title", "type": "string", "default": "", "desc": "窗口标题"},
            {"name": "window_pid", "type": "int", "default": 0, "desc": "窗口进程ID"},
        ],
        "desc": "行为树根节点，入口节点",
    },
    "SequenceNode": {
        "params": [
            {"name": "repeat_count", "type": "int", "default": 0, "desc": "重复次数（-1无限）"},
            {"name": "repeat_interval_ms", "type": "int", "default": 100, "desc": "重复间隔毫秒"},
            {"name": "childinterval", "type": "int", "default": 0, "desc": "子节点间隔毫秒"},
            {"name": "childinterval_random", "type": "int", "default": 0, "desc": "子节点间隔随机范围"},
            {"name": "continue_on_failure", "type": "bool", "default": False, "desc": "失败是否继续"},
        ],
        "desc": "顺序执行：全部成功才成功，任一失败则失败",
    },
    "SelectorNode": {
        "params": [
            {"name": "repeat_count", "type": "int", "default": 0, "desc": "重复次数（-1无限）"},
            {"name": "repeat_interval_ms", "type": "int", "default": 100, "desc": "重复间隔毫秒"},
            {"name": "childinterval", "type": "int", "default": 0, "desc": "子节点间隔毫秒"},
            {"name": "childinterval_random", "type": "int", "default": 0, "desc": "子节点间隔随机范围"},
        ],
        "desc": "选择执行：任一成功即成功，全部失败才失败",
    },
    "ParallelNode": {
        "params": [
            {"name": "success_policy", "type": "string", "default": "require_all",
             "desc": "成功策略：require_all/require_one"},
        ],
        "desc": "并行执行：同时执行所有子节点",
    },
    "RandomNode": {
        "params": [
            {"name": "success_policy", "type": "string", "default": "require_all", "desc": "成功策略"},
            {"name": "fully_random", "type": "bool", "default": False, "desc": "每次完全随机"},
        ],
        "desc": "随机执行：随机选择子节点",
    },
    "SubtreeNode": {
        "params": [
            {"name": "subtree_path", "type": "string", "default": "", "desc": "子树文件路径"},
            {"name": "blackboard_mode", "type": "string", "default": "shared", "desc": "黑板模式"},
            {"name": "namespace", "type": "string", "default": "", "desc": "命名空间"},
            {"name": "auto_reload", "type": "bool", "default": False, "desc": "自动重载"},
        ],
        "desc": "子树引用：加载外部行为树",
    },
    "KeyPressNode": {
        "params": [
            {"name": "key", "type": "string", "default": "", "desc": "按键名称"},
            {"name": "action", "type": "string", "default": "press_release",
             "desc": "动作：press/release/press_release"},
            {"name": "duration", "type": "int", "default": 50, "desc": "按下持续时间毫秒"},
            {"name": "duration_random", "type": "int", "default": 0, "desc": "持续时间随机范围"},
        ],
        "desc": "键盘按键",
    },
    "MouseClickNode": {
        "params": [
            {"name": "button", "type": "string", "default": "left",
             "desc": "按钮：left/right/middle"},
            {"name": "position", "type": "list", "default": [], "desc": "点击位置 [x,y]"},
            {"name": "use_blackboard", "type": "bool", "default": False,
             "desc": "使用黑板中最近检测到的位置"},
            {"name": "click_count", "type": "int", "default": 1, "desc": "点击次数"},
            {"name": "click_interval", "type": "int", "default": 50, "desc": "点击间隔毫秒"},
        ],
        "desc": "鼠标点击",
    },
    "MouseMoveNode": {
        "params": [
            {"name": "position", "type": "list", "default": [], "desc": "目标位置 [x,y]"},
            {"name": "use_blackboard", "type": "bool", "default": False, "desc": "使用黑板位置"},
            {"name": "relative", "type": "bool", "default": False, "desc": "相对移动"},
            {"name": "offset", "type": "list", "default": [0, 0], "desc": "偏移量"},
            {"name": "move_type", "type": "string", "default": "instant",
             "desc": "移动类型：instant/linear/smooth"},
            {"name": "move_duration", "type": "int", "default": 300, "desc": "移动持续时间毫秒"},
        ],
        "desc": "鼠标移动",
    },
    "MouseScrollNode": {
        "params": [
            {"name": "distance", "type": "int", "default": 100, "desc": "滚动距离"},
            {"name": "clicks", "type": "int", "default": 1, "desc": "滚动次数"},
            {"name": "direction", "type": "string", "default": "up", "desc": "方向：up/down"},
        ],
        "desc": "鼠标滚轮",
    },
    "DelayNode": {
        "params": [
            {"name": "duration_ms", "type": "int", "default": 1000, "desc": "延时毫秒"},
            {"name": "duration_random", "type": "int", "default": 0, "desc": "随机范围毫秒"},
        ],
        "desc": "延时等待",
    },
    "SetVariableNode": {
        "params": [
            {"name": "variable_name", "type": "string", "default": "", "desc": "变量名"},
            {"name": "variable_value", "type": "any", "default": "", "desc": "变量值"},
        ],
        "desc": "设置黑板变量",
    },
    "AlarmNode": {
        "params": [
            {"name": "sound_file", "type": "string", "default": "", "desc": "声音文件路径"},
            {"name": "loop", "type": "bool", "default": False, "desc": "循环播放"},
            {"name": "duration", "type": "int", "default": 3000, "desc": "播放时长毫秒"},
        ],
        "desc": "播放报警声音",
    },
    "ScriptNode": {
        "params": [
            {"name": "script_path", "type": "string", "default": "", "desc": "脚本文件路径"},
        ],
        "desc": "执行外部脚本",
    },
    "CodeNode": {
        "params": [
            {"name": "code_file", "type": "string", "default": "", "desc": "代码文件路径"},
        ],
        "desc": "执行代码文件",
    },
    "StartTreeNode": {
        "params": [
            {"name": "target_tree", "type": "string", "default": "", "desc": "目标行为树名称"},
            {"name": "sound_path", "type": "string", "default": "", "desc": "启动音效文件路径"},
            {"name": "volume", "type": "int", "default": 70, "desc": "音量（0-100）"},
        ],
        "desc": "启动其他已加载的行为树",
    },
    "StopTreeNode": {
        "params": [
            {"name": "target_tree", "type": "string", "default": "", "desc": "目标行为树名称（空则停止当前树）"},
            {"name": "sound_path", "type": "string", "default": "", "desc": "停止音效文件路径"},
            {"name": "volume", "type": "int", "default": 70, "desc": "音量（0-100）"},
        ],
        "desc": "停止当前或其他已加载的行为树",
    },
    "TextInputNode": {
        "params": [
            {"name": "input_mode", "type": "string", "default": "preset",
             "desc": "输入模式：preset/file/extract"},
            {"name": "text_content", "type": "string", "default": "", "desc": "输入内容"},
            {"name": "file_path", "type": "string", "default": "", "desc": "文件路径"},
            {"name": "position", "type": "list", "default": [], "desc": "输入位置 [x,y]"},
        ],
        "desc": "文本输入",
    },
    "OCRConditionNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "检测区域 [x1,y1,x2,y2]"},
            {"name": "keywords", "type": "string", "default": "", "desc": "检测关键词"},
            {"name": "language", "type": "string", "default": "ch", "desc": "识别语言"},
            {"name": "preprocess_mode", "type": "string", "default": "default",
             "desc": "预处理模式：default/complex_color/adaptive/auto_tune"},
        ],
        "desc": "OCR识别文字条件节点",
    },
    "ImageConditionNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "检测区域 [x1,y1,x2,y2]"},
            {"name": "template_path", "type": "string", "default": "", "desc": "模板图片路径"},
            {"name": "threshold", "type": "int", "default": 80, "desc": "匹配阈值%（0-100）"},
        ],
        "desc": "图像匹配条件节点",
    },
    "ColorConditionNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "检测区域 [x1,y1,x2,y2]"},
            {"name": "target_color", "type": "string", "default": "", "desc": "目标颜色 #RRGGBB"},
            {"name": "tolerance", "type": "int", "default": 30, "desc": "颜色容差"},
            {"name": "min_pixels", "type": "int", "default": 10, "desc": "最小像素数"},
        ],
        "desc": "颜色检测条件节点",
    },
    "NumberConditionNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "检测区域"},
            {"name": "extract_mode", "type": "string", "default": "ocr", "desc": "提取模式"},
            {"name": "compare_mode", "type": "string", "default": ">",
             "desc": "比较模式：>/</<=/==/!="},
            {"name": "threshold", "type": "int", "default": 0, "desc": "阈值"},
            {"name": "value_key", "type": "string", "default": "", "desc": "黑板变量键名"},
        ],
        "desc": "数字比较条件节点",
    },
    "VariableConditionNode": {
        "params": [
            {"name": "variable_name", "type": "string", "default": "", "desc": "变量名"},
            {"name": "operator", "type": "string", "default": "==",
             "desc": "操作符：>/</==/!=/contains等"},
            {"name": "target_value", "type": "any", "default": "", "desc": "目标值"},
        ],
        "desc": "变量判断条件节点",
    },
    "TextExtractNode": {
        "params": [
            {"name": "region", "type": "list", "default": [], "desc": "提取区域"},
            {"name": "extract_mode", "type": "string", "default": "ocr", "desc": "提取模式"},
            {"name": "keywords", "type": "string", "default": "", "desc": "关键词"},
            {"name": "output_key", "type": "string", "default": "", "desc": "输出黑板键名"},
            {"name": "save_all_text", "type": "bool", "default": False, "desc": "保存全部文本"},
        ],
        "desc": "文本提取节点",
    },
    "HTTPRequestNode": {
        "params": [
            {"name": "url", "type": "string", "default": "", "desc": "请求URL"},
            {"name": "method", "type": "string", "default": "GET", "desc": "HTTP方法"},
            {"name": "headers", "type": "dict", "default": {}, "desc": "请求头"},
            {"name": "body", "type": "string", "default": "", "desc": "请求体"},
        ],
        "desc": "HTTP请求节点",
    },
    "APIConditionNode": {
        "params": [
            {"name": "url", "type": "string", "default": "", "desc": "请求URL"},
            {"name": "method", "type": "string", "default": "GET", "desc": "HTTP方法"},
            {"name": "body", "type": "string", "default": "", "desc": "请求体"},
            {"name": "expected_status", "type": "int", "default": 0, "desc": "期望HTTP状态码（0不检查）"},
            {"name": "json_path", "type": "string", "default": "", "desc": "响应JSON字段路径（点分，如data.code）"},
            {"name": "expected_value", "type": "any", "default": None, "desc": "期望字段值"},
            {"name": "timeout_ms", "type": "int", "default": 5000, "desc": "超时毫秒"},
            {"name": "headers", "type": "dict", "default": {}, "desc": "请求头"},
        ],
        "desc": "根据HTTP响应内容判断条件是否成立",
    },
    "WebSocketNode": {
        "params": [
            {"name": "url", "type": "string", "default": "", "desc": "WebSocket地址（ws://或wss://）"},
            {"name": "action", "type": "string", "default": "send", "desc": "操作类型：send/recv"},
            {"name": "message", "type": "string", "default": "", "desc": "send模式下发送的消息内容"},
            {"name": "payload_key", "type": "string", "default": "ws_message", "desc": "recv模式下接收数据写入黑板的键名"},
            {"name": "timeout_ms", "type": "int", "default": 1000, "desc": "recv模式下接收超时毫秒"},
        ],
        "desc": "WebSocket客户端节点：发送或接收消息",
    },
    "MessagePublishNode": {
        "params": [
            {"name": "topic", "type": "string", "default": "", "desc": "消息主题"},
            {"name": "data", "type": "any", "default": "", "desc": "消息数据"},
        ],
        "desc": "消息发布节点",
    },
    "MessageSubscribeNode": {
        "params": [
            {"name": "topic", "type": "string", "default": "", "desc": "订阅主题"},
        ],
        "desc": "消息订阅节点",
    },
}

# 装饰参数（条件节点通用）
_CONDITION_DECORATOR_PARAMS = [
    {"name": "invert", "type": "bool", "default": False, "desc": "结果取反"},
    {"name": "retry_count", "type": "int", "default": 3, "desc": "失败重试次数（-1无限）"},
    {"name": "timeout_ms", "type": "int", "default": 10000, "desc": "超时毫秒（0不限）"},
    {"name": "check_interval_ms", "type": "int", "default": 500, "desc": "检测间隔毫秒"},
]

# 动作节点通用装饰参数
_ACTION_DECORATOR_PARAMS = [
    {"name": "repeat_count", "type": "int", "default": 0, "desc": "重复次数（-1无限）"},
    {"name": "repeat_interval_ms", "type": "int", "default": 100, "desc": "重复间隔毫秒"},
    {"name": "repeat_interval_ms_random", "type": "int", "default": 0, "desc": "间隔随机范围"},
    {"name": "timeout_ms", "type": "int", "default": 0, "desc": "超时毫秒（0不限）"},
]

# 已知异步节点集合
# _is_async 是在 __init__ 中设置的实例属性，无法通过类属性探测，
# 因此维护此显式集合来标识异步节点；新增异步节点时只需追加到此集合。
_KNOWN_ASYNC_NODES = {"HTTPRequestNode"}


class NodeSpecExporter:
    """从 NodeRegistry 动态导出节点完整规格"""

    def export_all(self) -> Dict[str, dict]:
        """遍历所有注册节点，导出真实参数规格

        Returns:
            {node_type: {node_type, category, base_class, parameters, description, is_async}}
        """
        specs = {}
        for node_type, node_class in NodeRegistry.list_types().items():
            specs[node_type] = self.export_one(node_type, node_class)
        return specs

    def export_one(self, node_type: str, node_class: Type[Node]) -> dict:
        """导出单个节点规格"""
        category = self._get_category(node_class)
        base_class = self._get_base_class(node_class)

        # 从文档表获取参数
        param_docs = _NODE_PARAM_DOCS.get(node_type, {})
        parameters = list(param_docs.get("params", []))

        # 条件节点追加装饰参数
        if category == "condition":
            parameters = parameters + _CONDITION_DECORATOR_PARAMS

        # 动作节点追加装饰参数
        if category == "action":
            parameters = parameters + _ACTION_DECORATOR_PARAMS

        return {
            "node_type": node_type,
            "category": category,
            "base_class": base_class,
            "parameters": parameters,
            "description": param_docs.get("desc", node_class.__doc__ or ""),
            "is_async": node_type in _KNOWN_ASYNC_NODES,
        }

    def _get_category(self, node_class: Type[Node]) -> str:
        """获取节点分类"""
        if issubclass(node_class, CompositeNode):
            return "composite"
        if issubclass(node_class, ConditionNode):
            return "condition"
        if issubclass(node_class, ActionNode):
            return "action"
        return "other"

    def _get_base_class(self, node_class: Type[Node]) -> str:
        """获取基类名"""
        for base in (CompositeNode, ConditionNode, ActionNode):
            if issubclass(node_class, base):
                return base.__name__
        return "Node"

    def export_for_prompt(self) -> str:
        """导出为 LLM 可读的文本格式"""
        specs = self.export_all()
        lines = []
        for category in ("composite", "condition", "action", "other"):
            cat_nodes = {k: v for k, v in specs.items() if v["category"] == category}
            if not cat_nodes:
                continue
            lines.append(f"\n### {category.upper()} 节点\n")
            for node_type, spec in cat_nodes.items():
                lines.append(f"**{node_type}**: {spec['description']}")
                if spec["parameters"]:
                    param_strs = []
                    for p in spec["parameters"]:
                        default = f'="{p["default"]}"' if isinstance(p["default"], str) else f"={p['default']}"
                        param_strs.append(f'{p["name"]}{default}({p["desc"]})')
                    lines.append(f"  参数: {', '.join(param_strs)}")
                lines.append("")
        return "\n".join(lines)

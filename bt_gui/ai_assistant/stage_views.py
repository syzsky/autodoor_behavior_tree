"""5 阶段视图组件"""
import customtkinter as ctk
from typing import Dict, Any, Optional, Callable

from ..theme import Theme


# AI 助手面板专属字体（比全局主题大一号，提升可读性）
AI_FONTS = {
    'xs': 12,
    'sm': 13,
    'md': 14,
    'lg': 16,
    'xl': 18,
}


def get_ai_font(size_key: str = 'sm'):
    """AI 助手面板字体（仅影响本面板，不改变全局主题）"""
    return (Theme.FONTS['family'], AI_FONTS.get(size_key, 13))


def _create_section_label(parent, text, colors):
    """创建分区标题"""
    return ctk.CTkLabel(
        parent,
        text=text,
        font=get_ai_font('md'),
        text_color=colors.get('text_primary', '#FFFFFF'),
    )


def create_stage1_view(parent, state, colors, **kwargs):
    """阶段①视图：意图分析结果"""
    plan = state.plan

    if not plan:
        ctk.CTkLabel(
            parent,
            text="暂无分析结果",
            font=get_ai_font('sm'),
            text_color=colors.get('text_muted', '#888'),
        ).pack(pady=20)
        return

    # 任务概述
    _create_section_label(parent, "任务概述", colors).pack(anchor="w", pady=(0, 5))
    ctk.CTkLabel(
        parent,
        text=plan.get("task_summary", "N/A"),
        font=get_ai_font('sm'),
        text_color=colors.get('text_muted', '#888'),
        wraplength=320,
        justify="left",
    ).pack(anchor="w", pady=(0, 15))

    # 循环配置
    loop = plan.get("loop", {})
    if isinstance(loop, dict) and loop.get("enabled"):
        _create_section_label(parent, "循环配置", colors).pack(anchor="w", pady=(0, 5))
        interval = loop.get("interval_ms", "N/A")
        max_iter = loop.get("max_iterations", -1)
        iter_str = "无限" if max_iter == -1 else str(max_iter)
        ctk.CTkLabel(
            parent,
            text=f"间隔: {interval}ms | 次数: {iter_str}",
            font=get_ai_font('sm'),
            text_color=colors.get('text_muted', '#888'),
        ).pack(anchor="w", pady=(0, 15))

    # 阶段列表
    phases = plan.get("phases", [])
    if phases:
        _create_section_label(parent, f"执行阶段（{len(phases)} 个）", colors).pack(anchor="w", pady=(0, 5))
        for i, phase in enumerate(phases):
            phase_text = f"{i+1}. {phase.get('phase', '?')} → {phase.get('action', phase.get('method', '?'))}"
            ctk.CTkLabel(
                parent,
                text=phase_text,
                font=get_ai_font('sm'),
                text_color=colors.get('text_muted', '#888'),
                anchor="w",
            ).pack(anchor="w", padx=10)


def create_stage2_view(parent, state, colors, **kwargs):
    """阶段②视图：节点选型结果"""
    structure = state.structure

    if not structure:
        ctk.CTkLabel(
            parent,
            text="暂无节点结构",
            font=get_ai_font('sm'),
            text_color=colors.get('text_muted', '#888'),
        ).pack(pady=20)
        return

    nodes = structure.get("nodes", [])
    _create_section_label(parent, f"节点结构（{len(nodes)} 个节点）", colors).pack(anchor="w", pady=(0, 10))

    # 节点类型中文名
    type_names = {
        "StartNode": "开始", "SequenceNode": "顺序执行", "SelectorNode": "选择执行",
        "ParallelNode": "并行执行", "DelayNode": "延时", "MouseClickNode": "鼠标点击",
        "MouseMoveNode": "鼠标移动", "KeyPressNode": "键盘按键", "TextInputNode": "文本输入",
        "OCRConditionNode": "OCR识别", "ImageConditionNode": "图像匹配",
        "ColorConditionNode": "颜色检测", "NumberConditionNode": "数字比较",
        "VariableConditionNode": "变量判断", "HTTPRequestNode": "HTTP请求",
        "APIConditionNode": "API条件", "WebSocketNode": "WebSocket连接",
        "SetVariableNode": "设置变量", "AlarmNode": "报警", "ScriptNode": "执行脚本",
        "MessagePublishNode": "消息发布", "MessageSubscribeNode": "消息订阅",
        "StartTreeNode": "启动树", "StopTreeNode": "停止树",
    }

    for node in nodes:
        node_type = node.get("type", "?")
        node_name = type_names.get(node_type, node_type)
        node_id = node.get("id", "?")
        empty = node.get("empty_params", [])
        children = node.get("children", [])

        # 节点卡片
        card = ctk.CTkFrame(parent, fg_color=colors.get('bg_tertiary', '#2A2A2A'),
                            corner_radius=8)
        card.pack(fill="x", pady=3)

        header_text = f"{node_name} ({node_id})"
        ctk.CTkLabel(
            card,
            text=header_text,
            font=get_ai_font('sm'),
            text_color=colors.get('text_primary', '#FFF'),
            anchor="w",
        ).pack(anchor="w", padx=10, pady=(5, 2))

        info_parts = []
        if children:
            info_parts.append(f"子节点: {', '.join(children)}")
        if empty:
            info_parts.append(f"待填充: {', '.join(empty)}")
        if info_parts:
            ctk.CTkLabel(
                card,
                text=" | ".join(info_parts),
                font=get_ai_font('xs'),
                text_color=colors.get('text_muted', '#888'),
                anchor="w",
            ).pack(anchor="w", padx=10, pady=(0, 5))


def create_stage3_view(parent, state, colors, on_screenshot=None, **kwargs):
    """阶段③视图：VLM 屏幕感知"""
    suggestions = getattr(state, '_suggestions', None)
    filled = state.filled_structure

    if not suggestions and not filled:
        # 初始状态：显示截图按钮
        ctk.CTkLabel(
            parent,
            text="点击下方按钮截取屏幕\nVLM 将分析截图并自动填充参数",
            font=get_ai_font('sm'),
            text_color=colors.get('text_muted', '#888'),
        ).pack(pady=(30, 10))

        if on_screenshot:
            ctk.CTkButton(
                parent,
                text="截图并分析",
                height=32,
                font=get_ai_font('sm'),
                fg_color=colors.get('primary', '#3B82F6'),
                hover_color=colors.get('primary_hover', '#2563EB'),
                command=on_screenshot,
            ).pack(pady=10)
        return

    if not suggestions:
        ctk.CTkLabel(
            parent,
            text="无需填充的参数",
            font=get_ai_font('sm'),
            text_color=colors.get('text_muted', '#888'),
        ).pack(pady=20)
        return

    # 显示建议值列表
    _create_section_label(parent, f"参数填充建议（{len(suggestions)} 个）", colors).pack(anchor="w", pady=(0, 10))

    for sug in suggestions:
        card = ctk.CTkFrame(parent, fg_color=colors.get('bg_tertiary', '#2A2A2A'),
                            corner_radius=8)
        card.pack(fill="x", pady=3)

        confidence = sug.get("confidence", 0)
        # 健壮性：VLM 返回的 confidence 可能是字符串（如 "0.95"），
        # 直接与数值比较会抛 TypeError，导致整个阶段视图渲染中断、面板空白。
        try:
            confidence = float(confidence)
        except (ValueError, TypeError):
            confidence = 0.0
        conf_color = colors.get('success', '#22C55E') if confidence >= 0.8 else colors.get('warning', '#F59E0B')
        conf_mark = "✓" if confidence >= 0.8 else "⚠"

        header = f"{conf_mark} {sug.get('node_id', '?')}.{sug.get('param', '?')}"
        ctk.CTkLabel(
            card,
            text=header,
            font=get_ai_font('sm'),
            text_color=colors.get('text_primary', '#FFF'),
            anchor="w",
        ).pack(anchor="w", padx=10, pady=(5, 2))

        value = sug.get("suggested_value", "")
        ctk.CTkLabel(
            card,
            text=f"值: {value}",
            font=get_ai_font('xs'),
            text_color=colors.get('text_muted', '#888'),
            anchor="w",
        ).pack(anchor="w", padx=10)

        note = sug.get("note", "")
        if note:
            ctk.CTkLabel(
                card,
                text=f"说明: {note}",
                font=get_ai_font('xs'),
                text_color=colors.get('text_muted', '#888'),
                anchor="w",
            ).pack(anchor="w", padx=10)

        ctk.CTkLabel(
            card,
            text=f"置信度: {confidence:.0%}",
            font=get_ai_font('xs'),
            text_color=conf_color,
            anchor="w",
        ).pack(anchor="w", padx=10, pady=(0, 5))


def create_stage4_view(parent, state, colors, **kwargs):
    """阶段④视图：生成结果"""
    tree_data = state.tree_data

    if not tree_data:
        ctk.CTkLabel(
            parent,
            text="点击下方按钮生成行为树 JSON",
            font=get_ai_font('sm'),
            text_color=colors.get('text_muted', '#888'),
        ).pack(pady=20)
        ctk.CTkButton(
            parent,
            text="生成 JSON",
            height=32,
            font=get_ai_font('sm'),
            fg_color=colors.get('primary', '#3B82F6'),
            hover_color=colors.get('primary_hover', '#2563EB'),
            command=kwargs.get('on_generate', lambda: None),
        ).pack(pady=10)
        return

    # 生成结果摘要
    _create_section_label(parent, "生成结果", colors).pack(anchor="w", pady=(0, 10))

    nodes = tree_data.get("nodes", {})
    connections = tree_data.get("connections", [])

    summary_card = ctk.CTkFrame(parent, fg_color=colors.get('bg_tertiary', '#2A2A2A'),
                                corner_radius=8)
    summary_card.pack(fill="x", pady=5)

    ctk.CTkLabel(
        summary_card,
        text="✓ 校验通过",
        font=get_ai_font('sm'),
        text_color=colors.get('success', '#22C55E'),
        anchor="w",
    ).pack(anchor="w", padx=10, pady=(8, 4))

    ctk.CTkLabel(
        summary_card,
        text=f"节点数: {len(nodes)}",
        font=get_ai_font('sm'),
        text_color=colors.get('text_muted', '#888'),
        anchor="w",
    ).pack(anchor="w", padx=10)

    ctk.CTkLabel(
        summary_card,
        text=f"连接数: {len(connections)}",
        font=get_ai_font('sm'),
        text_color=colors.get('text_muted', '#888'),
        anchor="w",
    ).pack(anchor="w", padx=10)

    ctk.CTkLabel(
        summary_card,
        text=f"版本: {tree_data.get('version', '?')}",
        font=get_ai_font('xs'),
        text_color=colors.get('text_muted', '#888'),
        anchor="w",
    ).pack(anchor="w", padx=10, pady=(0, 8))

    ctk.CTkLabel(
        parent,
        text="行为树已加载到画布",
        font=get_ai_font('xs'),
        text_color=colors.get('text_muted', '#888'),
    ).pack(pady=10)


def create_stage5_view(parent, state, colors, on_apply_fix=None, on_rerun=None, **kwargs):
    """阶段⑤视图：试运行报告 + 修正建议"""
    report = state.test_report

    if not report:
        # 初始状态
        ctk.CTkLabel(
            parent,
            text="点击下方按钮开始试运行",
            font=get_ai_font('sm'),
            text_color=colors.get('text_muted', '#888'),
        ).pack(pady=20)

        if on_rerun:
            ctk.CTkButton(
                parent,
                text="开始试运行",
                height=32,
                font=get_ai_font('sm'),
                fg_color=colors.get('primary', '#3B82F6'),
                hover_color=colors.get('primary_hover', '#2563EB'),
                command=on_rerun,
            ).pack(pady=10)
        return

    success = report.get("success", False)
    status_text = "✓ 试运行成功" if success else "✗ 试运行失败"
    status_color = colors.get('success', '#22C55E') if success else colors.get('error', '#EF4444')

    ctk.CTkLabel(
        parent,
        text=status_text,
        font=get_ai_font('lg'),
        text_color=status_color,
    ).pack(anchor="w", pady=(0, 10))

    # 执行日志
    logs = report.get("logs", [])
    if logs:
        _create_section_label(parent, "执行日志", colors).pack(anchor="w", pady=(0, 5))

        log_text = "\n".join(logs[-10:])  # 最后 10 行
        log_box = ctk.CTkTextbox(
            parent,
            height=120,
            font=get_ai_font('xs'),
            fg_color=colors.get('bg_primary', '#1A1A1A'),
            text_color=colors.get('text_muted', '#888'),
        )
        log_box.pack(fill="x", pady=(0, 10))
        log_box.insert("1.0", log_text)
        log_box.configure(state="disabled")

    # 修正建议
    fixes = getattr(state, '_fixes', [])
    if fixes and not success:
        _create_section_label(parent, f"AI 修正建议（{len(fixes)} 个）", colors).pack(anchor="w", pady=(10, 5))

        for i, fix in enumerate(fixes):
            card = ctk.CTkFrame(parent, fg_color=colors.get('bg_tertiary', '#2A2A2A'),
                                corner_radius=8)
            card.pack(fill="x", pady=3)

            ctk.CTkLabel(
                card,
                text=f"节点: {fix.get('node_id', '?')}",
                font=get_ai_font('sm'),
                text_color=colors.get('text_primary', '#FFF'),
                anchor="w",
            ).pack(anchor="w", padx=10, pady=(5, 2))

            ctk.CTkLabel(
                card,
                text=f"参数: {fix.get('param', '?')}",
                font=get_ai_font('xs'),
                text_color=colors.get('text_muted', '#888'),
                anchor="w",
            ).pack(anchor="w", padx=10)

            ctk.CTkLabel(
                card,
                text=f"建议值: {fix.get('new_value', '?')}",
                font=get_ai_font('xs'),
                text_color=colors.get('text_muted', '#888'),
                anchor="w",
            ).pack(anchor="w", padx=10)

            reason = fix.get("reason", "")
            if reason:
                ctk.CTkLabel(
                    card,
                    text=f"原因: {reason}",
                    font=get_ai_font('xs'),
                    text_color=colors.get('text_muted', '#888'),
                    anchor="w",
                ).pack(anchor="w", padx=10)

            # 应用/跳过按钮
            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.pack(fill="x", padx=10, pady=(5, 8))

            if on_apply_fix:
                ctk.CTkButton(
                    btn_frame,
                    text="应用",
                    width=60,
                    height=26,
                    font=get_ai_font('xs'),
                    fg_color=colors.get('primary', '#3B82F6'),
                    command=lambda f=fix: on_apply_fix(f),
                ).pack(side="left", padx=2)

            ctk.CTkButton(
                btn_frame,
                text="跳过",
                width=60,
                height=26,
                font=get_ai_font('xs'),
                fg_color="transparent",
                hover_color=colors.get('border', '#444'),
            ).pack(side="left", padx=2)

    # 重新试运行按钮
    if not success and on_rerun:
        ctk.CTkButton(
            parent,
            text="重新试运行",
            height=32,
            font=get_ai_font('sm'),
            fg_color=colors.get('primary', '#3B82F6'),
            hover_color=colors.get('primary_hover', '#2563EB'),
            command=on_rerun,
        ).pack(pady=10)

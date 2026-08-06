"""AI 助手主面板容器"""
import customtkinter as ctk
from typing import Optional, Callable, Dict, Any

from ..theme import Theme
from .state import AssistantState, AssistantMode
from .stage_views import get_ai_font


# 阶段步骤元数据：序号 + 标题 + 简短说明
STEPS_INFO = [
    (1, "意图分析：", "理解任务，拆解执行步骤"),
    (2, "节点选型：", "匹配行为树的节点组合"),
    (3, "屏幕感知：", "截图并识别界面元素"),
    (4, "生成脚本：", "输出完整自动化脚本"),
    (5, "试运行：", "实际执行并自动修正"),
]

# 模式标签常量（用于分段按钮取值、初始设置及模式切换比较）
MODE_LABEL_CREATE = "创建"
MODE_LABEL_ANALYZE = "分析修改"


class AssistantPanel(ctk.CTkFrame):
    """AI 助手主面板

    固定右侧侧栏，包含：
    - 阶段进度指示器
    - 当前阶段内容区
    - 导航按钮（上一步/下一步）
    """

    PANEL_WIDTH = 400

    def __init__(self, master, editor, **kwargs):
        super().__init__(master, **kwargs)
        self._editor = editor
        self._state = AssistantState()
        self._callbacks: Dict[str, Optional[Callable]] = {}
        self._visible = False
        self._stage_views = {}
        # 流程令牌：切换模式时自增，用于忽略过期后台线程的回调
        self._flow_token = 0

        self._dark_colors = Theme.get_dark_colors()
        self.configure(
            fg_color=self._dark_colors['bg_secondary'],
            corner_radius=0,
            width=self.PANEL_WIDTH,
        )
        # 固定面板宽度：关闭 pack 尺寸传播，使 configure(width=...) 真正生效，
        # 否则面板实际宽度会塌缩为内容自然宽度（约 258px），导致 VLM 等阶段布局错乱。
        self.pack_propagate(False)

        self._create_ui()

    def _create_ui(self):
        """创建面板 UI"""
        # 标题栏
        self._header = ctk.CTkFrame(self, fg_color="transparent")
        self._header.pack(fill="x", padx=Theme.DIMENSIONS['spacing_sm'],
                          pady=Theme.DIMENSIONS['spacing_sm'])

        self._title_label = ctk.CTkLabel(
            self._header,
            text="AI 助手",
            font=get_ai_font('lg'),
            text_color=self._dark_colors['text_primary'],
        )
        self._title_label.pack(side="left")

        self._close_btn = ctk.CTkButton(
            self._header,
            text="×",
            width=30,
            height=30,
            font=get_ai_font('xl'),
            fg_color="transparent",
            hover_color=self._dark_colors['border'],
            command=self.hide
        )
        self._close_btn.pack(side="right")

        # 模式切换（创建 / 分析修改）
        self._mode_btn = ctk.CTkSegmentedButton(
            self,
            values=[MODE_LABEL_CREATE, MODE_LABEL_ANALYZE],
            command=self._on_mode_change,
            font=get_ai_font('sm'),
        )
        self._mode_btn.set(MODE_LABEL_CREATE if self._state.mode == AssistantMode.CREATE else MODE_LABEL_ANALYZE)
        self._mode_btn.pack(fill="x", padx=Theme.DIMENSIONS['spacing_sm'],
                            pady=(0, Theme.DIMENSIONS['spacing_sm']))

        # 阶段进度指示器
        self._progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._progress_frame.pack(fill="x", padx=Theme.DIMENSIONS['spacing_sm'],
                                   pady=(0, Theme.DIMENSIONS['spacing_sm']))
        self._create_progress_indicator()

        # 内容区（可滚动）
        self._content_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self._content_frame.pack(fill="both", expand=True,
                                  padx=Theme.DIMENSIONS['spacing_sm'],
                                  pady=Theme.DIMENSIONS['spacing_sm'])

        # 底部导航
        self._nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._nav_frame.pack(fill="x", padx=Theme.DIMENSIONS['spacing_sm'],
                              pady=Theme.DIMENSIONS['spacing_sm'])

        self._back_btn = ctk.CTkButton(
            self._nav_frame,
            text="上一步",
            width=80,
            height=32,
            font=get_ai_font('sm'),
            fg_color=self._dark_colors['bg_tertiary'],
            hover_color=self._dark_colors['border'],
            command=self._go_back
        )
        self._back_btn.pack(side="left")

        self._next_btn = ctk.CTkButton(
            self._nav_frame,
            text="确认并下一步",
            width=120,
            height=32,
            font=get_ai_font('sm'),
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            command=self._go_next
        )
        self._next_btn.pack(side="right")

        self._update_nav_buttons()

    def _on_mode_change(self, value):
        """切换工作模式（创建 / 分析修改）"""
        if value == MODE_LABEL_ANALYZE:
            new_mode = AssistantMode.ANALYZE
        else:
            new_mode = AssistantMode.CREATE
        # 递增流程令牌，使在途后台线程的回调（_on_*_done/_on_*_error）被忽略，
        # 避免旧模式的回调污染新模式的阶段/导航状态或泄漏 is_processing。
        self._flow_token += 1
        self._state.is_processing = False
        self._state.mode = new_mode
        self._state.stage = 0
        # 清空模式专属字段
        self._state.source_tree = None
        self._state.modification_plan = None
        self._state.analyze_result = None
        # 同时清空创建模式专属字段，避免跨模式残留（如 create 阶段写入的 plan/structure 等）
        self._state.plan = None
        self._state.structure = None
        self._state.filled_structure = None
        self._state.tree_data = None
        self._state.test_report = None
        # 移除瞬时下划线属性（后台线程写入的临时态）
        for attr in ('_suggestions', '_dialogue_questions', '_fixes', '_errors', '_error'):
            self._state.__dict__.pop(attr, None)
        self._update_nav_buttons()
        self._show_stage_view()

    def _create_progress_indicator(self):
        """创建竖直步骤条：序号圆点 + 标题 + 简短说明

        每步单行（标题与说明同行），圆点列用连接线串联，
        整体紧凑，突出显示当前/已完成步骤。
        """
        self._progress_frame.grid_columnconfigure(0, minsize=26)
        self._progress_frame.grid_columnconfigure(1, weight=1)

        self._step_widgets = []
        for i, (num, title, desc) in enumerate(STEPS_INFO):
            r = i * 2

            # 圆形序号圆点
            circle = ctk.CTkLabel(
                self._progress_frame,
                text=str(num),
                width=22,
                height=22,
                corner_radius=11,
                font=get_ai_font('xs'),
                text_color='#FFFFFF',
                fg_color=self._dark_colors['bg_tertiary'],
            )
            circle.grid(row=r, column=0, sticky="n", pady=(3, 0))

            # 标题 + 简短说明（同行）
            text_col = ctk.CTkFrame(self._progress_frame, fg_color="transparent")
            text_col.grid(row=r, column=1, sticky="nw", padx=(8, 0), pady=(2, 0))

            title_label = ctk.CTkLabel(
                text_col,
                text=title,
                font=get_ai_font('sm'),
                text_color=self._dark_colors['text_primary'],
                anchor="w",
            )
            title_label.pack(side="left")

            desc_label = ctk.CTkLabel(
                text_col,
                text=desc,
                font=get_ai_font('xs'),
                text_color=self._dark_colors['text_muted'],
                anchor="w",
            )
            desc_label.pack(side="left", padx=(8, 0))

            self._step_widgets.append({
                'circle': circle,
                'title': title_label,
                'desc': desc_label,
            })

            # 步骤间连接线（除最后一行）
            if i < len(STEPS_INFO) - 1:
                line = ctk.CTkFrame(
                    self._progress_frame,
                    fg_color=self._dark_colors['border'],
                )
                line.configure(width=2, height=10)
                line.grid(row=r + 1, column=0, sticky="n")

    def _update_progress(self):
        """更新步骤条（已完成=绿色，当前=蓝色高亮，待完成=灰色）"""
        for i, w in enumerate(self._step_widgets):
            stage_num = i + 1
            circle = w['circle']
            title = w['title']
            if stage_num < self._state.stage:
                # 已完成
                circle.configure(
                    fg_color=self._dark_colors.get('success', '#22C55E'))
                title.configure(text_color=self._dark_colors['text_primary'])
                w['desc'].configure(text_color=self._dark_colors['text_muted'])
            elif stage_num == self._state.stage:
                # 当前
                circle.configure(
                    fg_color=self._dark_colors['primary'])
                title.configure(text_color='#FFFFFF')
                w['desc'].configure(
                    text_color=self._dark_colors['text_secondary'])
            else:
                # 未开始
                circle.configure(fg_color=self._dark_colors['bg_tertiary'])
                title.configure(text_color=self._dark_colors['text_muted'])
                w['desc'].configure(text_color=self._dark_colors['text_muted'])

    def _update_nav_buttons(self):
        """更新导航按钮状态"""
        self._back_btn.configure(
            state="normal" if self._state.can_go_back() else "disabled"
        )
        self._next_btn.configure(
            state="normal" if self._state.can_advance() else "disabled"
        )
        self._update_progress()

    def _go_back(self):
        """回退到上一阶段"""
        self._state.go_back()
        self._update_nav_buttons()
        self._show_stage_view()
        if self._callbacks.get("on_stage_change"):
            self._callbacks["on_stage_change"](self._state.stage)

    def _go_next(self):
        """前进到下一阶段"""
        self._state.advance()
        self._update_nav_buttons()
        self._show_stage_view()
        if self._callbacks.get("on_stage_change"):
            self._callbacks["on_stage_change"](self._state.stage)

    def _show_stage_view(self):
        """显示当前阶段视图"""
        # 清除当前内容
        for widget in self._content_frame.winfo_children():
            widget.destroy()

        stage = self._state.stage
        try:
            if self._state.mode == AssistantMode.ANALYZE:
                # 分析修改模式：0=读取树, 1=意图, 2=方案, 3=应用
                if stage == 0:
                    self._show_analyze_stage0()
                elif stage == 1:
                    self._show_analyze_stage1()
                elif stage == 2:
                    self._show_analyze_stage2()
                elif stage == 3:
                    self._show_analyze_stage3()
                else:
                    self._show_welcome()
            else:
                # 创建模式
                if stage == 0:
                    self._show_welcome()
                elif stage == 1:
                    self._show_stage1()
                elif stage == 2:
                    self._show_stage2()
                elif stage == 3:
                    self._show_stage3()
                elif stage == 4:
                    self._show_stage4()
                elif stage == 5:
                    self._show_stage5()
        except Exception as e:
            # 视图渲染异常：绝不能静默导致面板空白，输出日志并显示可见错误
            self._log_ai_error("视图渲染", repr(e))
            try:
                ctk.CTkLabel(
                    self._content_frame,
                    text=f"视图渲染失败: {e}",
                    text_color=self._dark_colors.get('error', '#EF4444'),
                    wraplength=320,
                    justify="left",
                ).pack(pady=20, fill="x")
            except Exception:
                pass

    def _show_welcome(self):
        """显示欢迎页（先清空内容区，避免叠加残留报错）"""
        for widget in self._content_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self._content_frame,
            text="输入任务描述开始创建行为树",
            font=get_ai_font('md'),
            text_color=self._dark_colors['text_primary'],
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            self._content_frame,
            text="例：打开网站，登录后点击签到按钮\n并循环检测签到是否成功",
            font=get_ai_font('xs'),
            text_color=self._dark_colors['text_muted'],
            justify="center",
        ).pack(pady=(0, 15))

        self._desc_entry = ctk.CTkTextbox(
            self._content_frame,
            height=150,
            font=get_ai_font('sm'),
            fg_color=self._dark_colors['bg_primary'],
            border_width=1,
            border_color=self._dark_colors.get('border', '#333'),
            text_color=self._dark_colors['text_primary'],
        )
        self._desc_entry.pack(fill="x", pady=10)

        # 恢复上次输入的任务描述（重试时保留内容）
        if getattr(self, '_last_desc', None):
            self._desc_entry.insert("1.0", self._last_desc)

        self._start_btn = ctk.CTkButton(
            self._content_frame,
            text="开始分析",
            height=32,
            font=get_ai_font('sm'),
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            command=self._start_analysis
        )
        self._start_btn.pack(pady=10)

    def _show_stage1(self):
        """阶段①视图：意图分析结果"""
        from .stage_views import create_stage1_view
        create_stage1_view(self._content_frame, self._state, self._dark_colors)

    def _show_stage2(self):
        """阶段②视图：节点选型结果"""
        from .stage_views import create_stage2_view
        create_stage2_view(self._content_frame, self._state, self._dark_colors)

    def _show_stage3(self):
        """阶段③视图：VLM 屏幕感知"""
        from .stage_views import create_stage3_view
        create_stage3_view(
            self._content_frame, self._state, self._dark_colors,
            on_screenshot=self._run_vlm_analysis,
            on_dialogue=self._run_dialogue_fill,
        )

    def _show_stage4(self):
        """阶段④视图：生成 JSON"""
        from .stage_views import create_stage4_view
        create_stage4_view(
            self._content_frame, self._state, self._dark_colors,
            on_generate=self._run_generate
        )
        # 如果已有 tree_data，说明已生成
        if self._state.tree_data:
            return
        # 否则自动生成
        self._run_generate()

    def _show_stage5(self):
        """阶段⑤视图：试运行"""
        from .stage_views import create_stage5_view
        create_stage5_view(
            self._content_frame, self._state, self._dark_colors,
            on_apply_fix=self._apply_fix,
            on_rerun=self._run_test,
        )
        # 如果已有报告，不自动运行
        if self._state.test_report:
            return
        # 否则自动开始试运行
        self._run_test()

    # ============ 分析修改模式 ============

    def _show_analyze_stage0(self):
        """分析阶段⓪：读取行为树"""
        from .stage_views import create_analyze_stage0_view
        create_analyze_stage0_view(
            self._content_frame, self._state, self._dark_colors,
            on_load_tree=self._load_source_tree,
        )

    def _load_source_tree(self):
        """从画布读取当前行为树作为分析源"""
        tree = None
        if self._editor and hasattr(self._editor, 'get_tree_data'):
            try:
                tree = self._editor.get_tree_data()
            except Exception as e:
                # 异常已有专属日志，不再走下方"画布为空"的通用提示
                self._log_ai_error("读取行为树", repr(e))
                return
        if not tree or not tree.get("nodes"):
            self._log_ai_error("读取行为树", "当前画布为空，无法读取行为树")
            return
        self._state.source_tree = tree
        self._show_stage_view()

    def _show_analyze_stage1(self):
        """分析阶段①：意图描述输入"""
        from .stage_views import create_analyze_stage1_view
        self._analyze_desc_entry = create_analyze_stage1_view(
            self._content_frame, self._state, self._dark_colors,
            on_start=self._start_tree_modify,
        )
        # 重试时恢复上次输入的意图文本（与 _show_welcome 恢复 _last_desc 保持一致）
        if getattr(self, '_last_analyze_desc', None) and self._analyze_desc_entry is not None:
            self._analyze_desc_entry.insert("1.0", self._last_analyze_desc)

    def _start_tree_modify(self):
        """执行行为树修改"""
        intent = self._analyze_desc_entry.get("1.0", "end").strip()
        if not intent:
            return
        # 缓存本次意图，重试时保留内容
        self._last_analyze_desc = intent
        self._state.is_processing = True
        self._next_btn.configure(state="disabled", text="分析中...")
        source_tree = self._state.source_tree
        token = self._flow_token

        import threading
        def _run():
            try:
                from bt_cli.ai.tree_modifier import TreeModifier
                plan = TreeModifier().modify(source_tree, intent)
                self._state.modification_plan = plan
                self.after(0, self._on_tree_modify_done, token)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_tree_modify_error, token)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_tree_modify_done(self, token=None):
        """行为树修改完成"""
        if token is not None and token != self._flow_token:
            return
        self._next_btn.configure(state="normal", text="确认并下一步")
        self._state.is_processing = False
        self._state.advance()  # 前进到阶段 2（方案）
        self._update_nav_buttons()
        self._show_stage_view()
        summary = self._state.modification_plan.get("summary", "") if self._state.modification_plan else ""
        self._log_ai_info(MODE_LABEL_ANALYZE, f"修改完成: {summary}")

    def _on_tree_modify_error(self, token=None):
        """行为树修改失败"""
        if token is not None and token != self._flow_token:
            return
        self._next_btn.configure(state="normal", text="确认并下一步")
        self._state.is_processing = False
        error = getattr(self._state, '_error', '未知错误')
        self._log_ai_error(MODE_LABEL_ANALYZE, error)
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"修改失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
            wraplength=320,
            justify="left",
        ).pack(pady=20, fill="x")
        ctk.CTkButton(
            self._content_frame,
            text="重试",
            command=self._show_analyze_stage1,
        ).pack(pady=10)

    def _show_analyze_stage2(self):
        """分析阶段②：修改方案"""
        from .stage_views import create_analyze_stage2_view
        create_analyze_stage2_view(self._content_frame, self._state, self._dark_colors)

    def _show_analyze_stage3(self):
        """分析阶段③：应用到画布"""
        from .stage_views import create_analyze_stage3_view
        create_analyze_stage3_view(
            self._content_frame, self._state, self._dark_colors,
            on_apply=self._apply_modified_tree,
        )

    def _apply_modified_tree(self):
        """将修改后的行为树加载到画布"""
        plan = self._state.modification_plan
        if plan and plan.get("tree"):
            tree = plan["tree"]
            # 与 _on_generate_done 保持一致，先写入 tree_data 再触发回调
            self._state.tree_data = tree
            if self._callbacks.get("on_tree_generated"):
                self._callbacks["on_tree_generated"](tree)
            self._log_ai_info(MODE_LABEL_ANALYZE, "已应用修改后的行为树到画布")
        else:
            self._log_ai_error(MODE_LABEL_ANALYZE, "没有可应用的修改方案")

    # ============ 创建模式：语言补全回退 ============

    def _run_dialogue_fill(self):
        """用语言描述补全空参数（VLM 不可用时回退）"""
        structure = self._state.structure
        if not structure:
            return
        self._state.is_processing = True
        self._next_btn.configure(state="disabled", text="生成问题中...")
        task_context = self._state.plan.get("task_summary", "") if self._state.plan else ""
        token = self._flow_token

        import threading
        def _run():
            try:
                from bt_cli.ai.dialogue_filler import DialogueFiller
                questions = DialogueFiller().propose_questions(structure, task_context)
                self._state._dialogue_questions = questions
                self.after(0, self._show_dialogue_form, token)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_dialogue_error, token)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _show_dialogue_form(self, token=None):
        """渲染语言补全表单"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        questions = getattr(self._state, '_dialogue_questions', [])
        for widget in self._content_frame.winfo_children():
            widget.destroy()

        if not questions:
            # 没有空参数，直接前进到阶段④
            self._state.filled_structure = self._state.structure
            self._state.advance()
            self._update_nav_buttons()
            self._show_stage_view()
            return

        ctk.CTkLabel(
            self._content_frame,
            text="请用语言描述以下参数，AI 将据此补全",
            font=get_ai_font('md'),
            text_color=self._dark_colors['text_primary'],
        ).pack(pady=(10, 10))

        self._dialogue_entries = []
        for q in questions:
            card = ctk.CTkFrame(
                self._content_frame,
                fg_color=self._dark_colors['bg_tertiary'],
                corner_radius=8,
            )
            card.pack(fill="x", pady=3)

            header = f"{q.get('node_id', '?')}.{q.get('param', '?')}"
            ctk.CTkLabel(
                card,
                text=header,
                font=get_ai_font('sm'),
                text_color=self._dark_colors['text_primary'],
                anchor="w",
            ).pack(anchor="w", padx=10, pady=(6, 2))

            question = q.get("question", "")
            if question:
                ctk.CTkLabel(
                    card,
                    text=question,
                    font=get_ai_font('xs'),
                    text_color=self._dark_colors['text_muted'],
                    anchor="w",
                    wraplength=300,
                ).pack(anchor="w", padx=10)

            entry = ctk.CTkTextbox(
                card,
                height=60,
                font=get_ai_font('sm'),
                fg_color=self._dark_colors['bg_primary'],
                border_width=1,
                border_color=self._dark_colors.get('border', '#333'),
                text_color=self._dark_colors['text_primary'],
            )
            entry.pack(fill="x", padx=10, pady=(4, 8))
            hint = q.get("hint", "")
            if hint:
                entry.insert("1.0", hint)
            self._dialogue_entries.append(entry)

        ctk.CTkButton(
            self._content_frame,
            text="确认补全",
            height=32,
            font=get_ai_font('sm'),
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            command=self._confirm_dialogue,
        ).pack(pady=10)

    def _confirm_dialogue(self):
        """收集答案并补全结构"""
        questions = getattr(self._state, '_dialogue_questions', [])
        answers = []
        for i, q in enumerate(questions):
            raw = ""
            if i < len(self._dialogue_entries):
                raw = self._dialogue_entries[i].get("1.0", "end").strip()
            if not raw:
                continue
            answers.append({
                "node_id": q.get("node_id"),
                "param": q.get("param"),
                "suggested_value": self._parse_answer(raw),
            })

        try:
            from bt_cli.ai.dialogue_filler import DialogueFiller
            filled = DialogueFiller().resolve_from_answers(self._state.structure, answers)
        except Exception as e:
            self._state._error = str(e)
            self._log_ai_error(MODE_LABEL_CREATE, str(e))
            self.after(0, self._on_dialogue_error, self._flow_token)
            return

        self._state.filled_structure = filled
        self._state.advance()  # 前进到阶段④
        self._update_nav_buttons()
        self._show_stage_view()

    def _on_dialogue_error(self, token=None):
        """语言补全失败"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        error = getattr(self._state, '_error', '未知错误')
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"语言补全失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
            wraplength=320,
            justify="left",
        ).pack(pady=20, fill="x")
        ctk.CTkButton(
            self._content_frame,
            text="重试",
            command=self._run_dialogue_fill,
        ).pack(pady=10)

    @staticmethod
    def _parse_answer(value):
        """尝试将答案解析为 int/float/list，否则保留为字符串"""
        s = str(value).strip()
        if not s:
            return s
        import json
        # 尝试 JSON（可覆盖 int/float/list/dict）
        try:
            return json.loads(s)
        except (ValueError, TypeError):
            pass
        # 尝试 int
        try:
            return int(s)
        except ValueError:
            pass
        # 尝试 float
        try:
            return float(s)
        except ValueError:
            pass
        return s

    def _log_ai_error(self, stage_name: str, error: str):
        """将 AI 助手面板错误输出到控制台

        Args:
            stage_name: 出错的阶段名称
            error: 错误信息
        """
        msg = f"[AI助手][{stage_name}] 错误: {error}"
        self._log_plain(stage_name, msg)

    def _log_ai_info(self, stage_name: str, message: str):
        """将 AI 助手面板的信息级日志输出到控制台（无"错误:"前缀）

        Args:
            stage_name: 阶段名称
            message: 信息内容
        """
        msg = f"[AI助手][{stage_name}] {message}"
        self._log_plain(stage_name, msg)

    def _log_plain(self, stage_name: str, msg: str):
        """统一输出日志：优先 LogManager.debug_print，失败回退到 print"""
        # 统一通过 LogManager.debug_print 输出（内部负责 print + 写文件），避免重复打印
        try:
            from bt_utils.log_manager import LogManager
            LogManager.debug_print(msg)
        except Exception:
            try:
                print(msg, flush=True)
            except Exception:
                pass

    def _start_analysis(self):
        """开始意图分析"""
        desc = self._desc_entry.get("1.0", "end").strip()
        if not desc:
            return
        # 缓存本次输入，重试时保留内容
        self._last_desc = desc

        # 检查 API Key
        from config.settings_manager import get_settings_manager
        sm = get_settings_manager()
        if not sm.get("ai.llm.api_key", ""):
            self._log_ai_error("意图分析", "未配置 LLM API Key")
            for widget in self._content_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(
                self._content_frame,
                text="未配置 LLM API Key",
                font=get_ai_font('md'),
                text_color=self._dark_colors.get('error', '#EF4444'),
            ).pack(pady=(30, 10))
            ctk.CTkLabel(
                self._content_frame,
                text="请前往「设置」→「AI 助手配置」\n填写 API 地址、API Key 和模型名称\n保存后重新打开 AI 助手",
                font=get_ai_font('sm'),
                text_color=self._dark_colors['text_muted'],
                justify="center",
            ).pack(pady=(0, 15))
            # 尝试切换到设置页
            if self._editor and hasattr(self._editor, 'app') and hasattr(self._editor.app, '_switch_tab'):
                ctk.CTkButton(
                    self._content_frame,
                    text="前往设置",
                    height=32,
                    font=get_ai_font('sm'),
                    fg_color=self._dark_colors['primary'],
                    hover_color=self._dark_colors['primary_hover'],
                    command=lambda: self._editor.app._switch_tab('settings'),
                ).pack(pady=5)
            return

        self._state.is_processing = True
        # 置灰"开始分析"按钮并显示"分析中..."（右下角导航按钮保持原样）
        self._start_btn.configure(state="disabled", text="分析中...")

        # 异步执行
        token = self._flow_token
        import threading
        def _run():
            try:
                from bt_cli.ai.intent_analyzer import IntentAnalyzer
                analyzer = IntentAnalyzer()
                plan = analyzer.analyze(desc)
                self._state.plan = plan

                # 节点选型
                from bt_cli.ai.node_selector import NodeSelector
                selector = NodeSelector()
                structure = selector.select(plan)
                self._state.structure = structure

                # 回到主线程更新 UI
                self.after(0, self._on_analysis_done, token)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_analysis_error, token)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_analysis_done(self, token=None):
        """意图分析完成"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._state.advance()  # 自动前进到阶段 0 → 1
        self._update_nav_buttons()
        self._show_stage_view()

    def _on_analysis_error(self, token=None):
        """意图分析失败"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        # 恢复"开始分析"按钮（此时内容区即将被错误视图替换，按钮随后被销毁，此处仅兜底）
        try:
            self._start_btn.configure(state="normal", text="开始分析")
        except Exception:
            pass
        error = getattr(self._state, '_error', '未知错误')
        self._log_ai_error("意图分析", error)
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"分析失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
            wraplength=320,
            justify="left",
        ).pack(pady=20, fill="x")
        ctk.CTkButton(
            self._content_frame,
            text="重试",
            command=self._show_welcome,
        ).pack(pady=10)

    def _run_vlm_analysis(self):
        """执行 VLM 分析"""
        from config.settings_manager import get_settings_manager
        sm = get_settings_manager()
        if not sm.get("ai.vlm.api_key", ""):
            # VLM 未配置，跳过
            self._state.filled_structure = self._state.structure
            self._state.advance()
            self._update_nav_buttons()
            self._show_stage_view()
            return

        self._state.is_processing = True
        self._next_btn.configure(state="disabled", text="分析中...")
        token = self._flow_token

        import threading
        def _run():
            try:
                # 截图
                from bt_utils.screenshot import ScreenshotManager
                sm_screenshot = ScreenshotManager()
                img = sm_screenshot.get_full_screenshot()

                import tempfile, os
                screenshot_path = os.path.join(tempfile.gettempdir(), "ai_screenshot.png")
                img.save(screenshot_path)

                # VLM 分析
                from bt_cli.ai.vlm_analyzer import VLMAnalyzer
                analyzer = VLMAnalyzer()
                task_context = self._state.plan.get("task_summary", "") if self._state.plan else ""
                suggestions = analyzer.analyze(screenshot_path, self._state.structure, task_context)
                self._state._suggestions = suggestions

                filled = analyzer.fill_structure(self._state.structure, suggestions)
                self._state.filled_structure = filled

                self.after(0, self._on_vlm_done, token)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_vlm_error, token)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_vlm_done(self, token=None):
        """VLM 分析完成"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        self._show_stage_view()

        # 通知画布绘制标注
        if self._callbacks.get("on_vlm_suggestions"):
            self._callbacks["on_vlm_suggestions"](getattr(self._state, '_suggestions', []))

    def _on_vlm_error(self, token=None):
        """VLM 分析失败"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        error = getattr(self._state, '_error', '未知错误')
        self._log_ai_error("屏幕感知", error)
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"VLM 分析失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
            wraplength=320,
            justify="left",
        ).pack(pady=20, fill="x")
        ctk.CTkButton(
            self._content_frame,
            text="重试",
            command=self._show_stage_view,
        ).pack(pady=10)

    def _run_generate(self):
        """执行生成"""
        structure = self._state.filled_structure or self._state.structure
        if not structure:
            return

        self._state.is_processing = True
        self._next_btn.configure(state="disabled", text="生成中...")
        token = self._flow_token

        import threading
        def _run():
            try:
                from bt_cli.ai.tree_generator import TreeGenerator
                gen = TreeGenerator()
                tree_data, errors = gen.generate_and_validate(structure)
                if errors:
                    self._state._errors = errors
                    self.after(0, self._on_generate_errors, token)
                else:
                    self._state.tree_data = tree_data
                    self.after(0, self._on_generate_done, token)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_generate_error, token)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_generate_done(self, token=None):
        """生成完成"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        self._show_stage_view()

        # 加载到画布
        if self._callbacks.get("on_tree_generated"):
            self._callbacks["on_tree_generated"](self._state.tree_data)

    def _on_generate_errors(self, token=None):
        """生成有校验错误"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        errors = getattr(self._state, '_errors', [])
        self._log_ai_error("JSON生成", "校验错误: " + "; ".join(errors))
        ctk.CTkLabel(
            self._content_frame,
            text=f"校验发现 {len(errors)} 个问题:",
            font=get_ai_font('sm'),
            text_color=self._dark_colors.get('error', '#EF4444'),
        ).pack(anchor="w", pady=10)
        for e in errors:
            ctk.CTkLabel(
                self._content_frame,
                text=f"  - {e}",
                font=get_ai_font('xs'),
                text_color=self._dark_colors.get('error', '#EF4444'),
            ).pack(anchor="w")

    def _on_generate_error(self, token=None):
        """生成异常"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        error = getattr(self._state, '_error', '未知错误')
        self._log_ai_error("JSON生成", error)
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"生成失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
            wraplength=320,
            justify="left",
        ).pack(pady=20, fill="x")

    def _run_test(self):
        """执行试运行"""
        if not self._state.tree_data:
            return

        self._state.is_processing = True
        self._next_btn.configure(state="disabled", text="试运行中...")
        token = self._flow_token

        import threading, tempfile, os, json
        def _run():
            try:
                from bt_cli.ai.iteration_engine import IterationEngine
                engine = IterationEngine()

                # 保存临时 tree.json
                tree_path = os.path.join(tempfile.gettempdir(), "ai_test_tree.json")
                with open(tree_path, "w", encoding="utf-8") as f:
                    json.dump(self._state.tree_data, f, ensure_ascii=False)

                # 试运行
                report = engine.run_test(tree_path)
                self._state.test_report = report

                # 如果失败，AI 分析
                if not report.get("success", False):
                    task_context = self._state.plan.get("task_summary", "") if self._state.plan else ""
                    analysis = engine.analyze_failure(report, self._state.tree_data, task_context)
                    self._state._fixes = analysis.get("fixes", [])
                    self._state._analysis = analysis.get("analysis", "")

                self.after(0, self._on_test_done, token)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_test_error, token)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_test_done(self, token=None):
        """试运行完成"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="完成")
        self._show_stage_view()

    def _on_test_error(self, token=None):
        """试运行失败"""
        if token is not None and token != self._flow_token:
            return
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="完成")
        error = getattr(self._state, '_error', '未知错误')
        self._log_ai_error("试运行", error)
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"试运行失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
            wraplength=320,
            justify="left",
        ).pack(pady=20, fill="x")
        ctk.CTkButton(
            self._content_frame,
            text="重试",
            command=self._show_stage_view,
        ).pack(pady=10)

    def _apply_fix(self, fix):
        """应用单条修正"""
        if not self._state.tree_data:
            return

        from bt_cli.ai.iteration_engine import IterationEngine
        engine = IterationEngine()
        self._state.tree_data = engine.apply_fixes(self._state.tree_data, [fix])

        # 通知画布更新
        if self._callbacks.get("on_tree_updated"):
            self._callbacks["on_tree_updated"](self._state.tree_data)

        # 刷新视图
        self._show_stage_view()

    def show(self):
        """显示面板"""
        self._visible = True
        self.pack(side="right", fill="y")
        # 渲染当前阶段视图（首次显示时为欢迎页）
        self._show_stage_view()

    def hide(self):
        """隐藏面板"""
        self._visible = False
        self.pack_forget()

    def toggle(self):
        """切换面板可见性"""
        if self._visible:
            self.hide()
        else:
            self.show()

    def register_callback(self, name: str, callback: Callable):
        """注册回调函数"""
        self._callbacks[name] = callback

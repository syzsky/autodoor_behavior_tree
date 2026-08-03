"""AI 助手主面板容器"""
import customtkinter as ctk
from typing import Optional, Callable, Dict, Any

from ..theme import Theme
from .state import AssistantState


class AssistantPanel(ctk.CTkFrame):
    """AI 助手主面板

    可折叠的右侧侧栏，包含：
    - 阶段进度指示器
    - 当前阶段内容区
    - 导航按钮（上一步/下一步）
    """

    PANEL_WIDTH = 380

    def __init__(self, master, editor, **kwargs):
        super().__init__(master, **kwargs)
        self._editor = editor
        self._state = AssistantState()
        self._callbacks: Dict[str, Optional[Callable]] = {}
        self._visible = False
        self._stage_views = {}

        self._dark_colors = Theme.get_dark_colors()
        self.configure(
            fg_color=self._dark_colors['bg_secondary'],
            corner_radius=0,
            width=self.PANEL_WIDTH,
        )

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
            font=Theme.get_font('lg'),
            text_color=self._dark_colors['text_primary']
        )
        self._title_label.pack(side="left")

        self._close_btn = ctk.CTkButton(
            self._header,
            text="×",
            width=30,
            height=30,
            font=Theme.get_font('xl'),
            fg_color="transparent",
            hover_color=self._dark_colors['border'],
            command=self.hide
        )
        self._close_btn.pack(side="right")

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
            font=Theme.get_font('sm'),
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
            font=Theme.get_font('sm'),
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            command=self._go_next
        )
        self._next_btn.pack(side="right")

        self._update_nav_buttons()

    def _create_progress_indicator(self):
        """创建阶段进度指示器"""
        self._progress_labels = []
        stages = ["①意图", "②选型", "③感知", "④生成", "⑤试运行"]

        for i, name in enumerate(stages):
            color = self._dark_colors['text_muted']  # 灰色（未开始）
            label = ctk.CTkLabel(
                self._progress_frame,
                text=name,
                font=Theme.get_font('xs'),
                text_color=color,
            )
            label.pack(side="left", padx=2)
            self._progress_labels.append(label)

            if i < len(stages) - 1:
                arrow = ctk.CTkLabel(
                    self._progress_frame,
                    text="→",
                    font=Theme.get_font('xs'),
                    text_color=self._dark_colors['text_muted'],
                )
                arrow.pack(side="left", padx=1)

    def _update_progress(self):
        """更新进度指示器"""
        for i, label in enumerate(self._progress_labels):
            stage_num = i + 1
            if stage_num < self._state.stage:
                # 已完成
                label.configure(text_color=self._dark_colors.get('success', '#22C55E'))
            elif stage_num == self._state.stage:
                # 当前
                label.configure(text_color=self._dark_colors['primary'])
            else:
                # 未开始
                label.configure(text_color=self._dark_colors['text_muted'])

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

    def _show_welcome(self):
        """显示欢迎页"""
        ctk.CTkLabel(
            self._content_frame,
            text="输入任务描述开始创建行为树",
            font=Theme.get_font('md'),
            text_color=self._dark_colors['text_muted'],
        ).pack(pady=40)

        self._desc_entry = ctk.CTkTextbox(
            self._content_frame,
            height=80,
            font=Theme.get_font('sm'),
            fg_color=self._dark_colors['bg_primary'],
        )
        self._desc_entry.pack(fill="x", pady=10)

        ctk.CTkButton(
            self._content_frame,
            text="开始分析",
            height=32,
            font=Theme.get_font('sm'),
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            command=self._start_analysis
        ).pack(pady=10)

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
            on_screenshot=self._run_vlm_analysis
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

    def _start_analysis(self):
        """开始意图分析"""
        desc = self._desc_entry.get("1.0", "end").strip()
        if not desc:
            return

        # 检查 API Key
        from config.settings_manager import get_settings_manager
        sm = get_settings_manager()
        if not sm.get("ai.llm.api_key", ""):
            ctk.CTkLabel(
                self._content_frame,
                text="未配置 AI API Key\n请在设置中配置",
                text_color=self._dark_colors.get('error', '#EF4444'),
            ).pack(pady=20)
            return

        self._state.is_processing = True
        self._next_btn.configure(state="disabled", text="分析中...")

        # 异步执行
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
                self.after(0, self._on_analysis_done)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_analysis_error)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_analysis_done(self):
        """意图分析完成"""
        self._state.is_processing = False
        self._state.advance()  # 自动前进到阶段 0 → 1
        self._update_nav_buttons()
        self._show_stage_view()

    def _on_analysis_error(self):
        """意图分析失败"""
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        error = getattr(self._state, '_error', '未知错误')
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"分析失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
        ).pack(pady=20)
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

                self.after(0, self._on_vlm_done)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_vlm_error)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_vlm_done(self):
        """VLM 分析完成"""
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        self._show_stage_view()

        # 通知画布绘制标注
        if self._callbacks.get("on_vlm_suggestions"):
            self._callbacks["on_vlm_suggestions"](getattr(self._state, '_suggestions', []))

    def _on_vlm_error(self):
        """VLM 分析失败"""
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        error = getattr(self._state, '_error', '未知错误')
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"VLM 分析失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
        ).pack(pady=20)
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

        import threading
        def _run():
            try:
                from bt_cli.ai.tree_generator import TreeGenerator
                gen = TreeGenerator()
                tree_data, errors = gen.generate_and_validate(structure)
                if errors:
                    self._state._errors = errors
                    self.after(0, self._on_generate_errors)
                else:
                    self._state.tree_data = tree_data
                    self.after(0, self._on_generate_done)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_generate_error)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_generate_done(self):
        """生成完成"""
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        self._show_stage_view()

        # 加载到画布
        if self._callbacks.get("on_tree_generated"):
            self._callbacks["on_tree_generated"](self._state.tree_data)

    def _on_generate_errors(self):
        """生成有校验错误"""
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        errors = getattr(self._state, '_errors', [])
        ctk.CTkLabel(
            self._content_frame,
            text=f"校验发现 {len(errors)} 个问题:",
            font=Theme.get_font('sm'),
            text_color=self._dark_colors.get('error', '#EF4444'),
        ).pack(anchor="w", pady=10)
        for e in errors:
            ctk.CTkLabel(
                self._content_frame,
                text=f"  - {e}",
                font=Theme.get_font('xs'),
                text_color=self._dark_colors.get('error', '#EF4444'),
            ).pack(anchor="w")

    def _on_generate_error(self):
        """生成异常"""
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="确认并下一步")
        error = getattr(self._state, '_error', '未知错误')
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"生成失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
        ).pack(pady=20)

    def _run_test(self):
        """执行试运行"""
        if not self._state.tree_data:
            return

        self._state.is_processing = True
        self._next_btn.configure(state="disabled", text="试运行中...")

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

                self.after(0, self._on_test_done)
            except Exception as e:
                self._state._error = str(e)
                self.after(0, self._on_test_error)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_test_done(self):
        """试运行完成"""
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="完成")
        self._show_stage_view()

    def _on_test_error(self):
        """试运行失败"""
        self._state.is_processing = False
        self._next_btn.configure(state="normal", text="完成")
        error = getattr(self._state, '_error', '未知错误')
        for widget in self._content_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._content_frame,
            text=f"试运行失败: {error}",
            text_color=self._dark_colors.get('error', '#EF4444'),
        ).pack(pady=20)
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

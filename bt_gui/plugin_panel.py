"""插件管理面板 — 提供 GUI 界面管理插件的加载、启动、停止

组件结构：
    PluginCard    — 单个插件的卡片组件（状态指示 + 信息 + 启停按钮）
    PluginPanel   — 插件管理面板（按钮栏 + 可滚动插件列表 + 状态栏）
"""
import customtkinter as ctk
from tkinter import filedialog

from .theme import Theme
from bt_plugins.loader import PluginLoader


class PluginCard(ctk.CTkFrame):
    """单个插件的卡片组件"""

    def __init__(self, master, plugin_info, is_started, on_start, on_stop, **kwargs):
        super().__init__(master, **kwargs)
        self.plugin_info = plugin_info
        self._on_start = on_start
        self._on_stop = on_stop
        self._dark_colors = Theme.get_dark_colors()

        self.configure(
            fg_color=self._dark_colors['bg_tertiary'],
            corner_radius=Theme.DIMENSIONS.get('button_corner_radius', 8)
        )

        # 状态指示器
        status_color = self._dark_colors.get('success', '#22C55E') if is_started else self._dark_colors.get('text_muted', '#9CA3AF')
        self.status_dot = ctk.CTkLabel(
            self, text="●", text_color=status_color,
            font=Theme.get_font('base')
        )
        self.status_dot.pack(side="left", padx=(8, 4), pady=8)

        # 信息区域
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=4)

        self.name_label = ctk.CTkLabel(
            info_frame,
            text=f"{plugin_info.display_name}  v{plugin_info.version}",
            font=Theme.get_font('sm'),
            text_color=self._dark_colors['text_primary'],
            anchor="w"
        )
        self.name_label.pack(fill="x")

        self.desc_label = ctk.CTkLabel(
            info_frame,
            text=f"{plugin_info.description}  作者: {plugin_info.author}",
            font=Theme.get_font('xs'),
            text_color=self._dark_colors['text_muted'],
            anchor="w"
        )
        self.desc_label.pack(fill="x")

        # 操作按钮
        self.start_btn = ctk.CTkButton(
            self, text="启动", width=60, height=28,
            font=Theme.get_font('xs'),
            command=self._handle_start
        )
        self.start_btn.pack(side="right", padx=(4, 8), pady=8)

        self.stop_btn = ctk.CTkButton(
            self, text="停止", width=60, height=28,
            font=Theme.get_font('xs'),
            fg_color=self._dark_colors.get('error', '#EF4444'),
            hover_color='#DC2626',
            command=self._handle_stop
        )
        self.stop_btn.pack(side="right", padx=(0, 4), pady=8)

        self._update_button_state(is_started)

    def _update_button_state(self, is_started):
        """根据启动状态更新按钮可用性"""
        if is_started:
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _handle_start(self):
        if self._on_start:
            self._on_start(self.plugin_info.name)

    def _handle_stop(self):
        if self._on_stop:
            self._on_stop(self.plugin_info.name)

    def update_status(self, is_started):
        """外部调用：更新状态显示"""
        status_color = self._dark_colors.get('success', '#22C55E') if is_started else self._dark_colors.get('text_muted', '#9CA3AF')
        self.status_dot.configure(text_color=status_color)
        self._update_button_state(is_started)


class PluginPanel(ctk.CTkFrame):
    """插件管理面板

    提供：
    - 顶部按钮栏：加载插件 / 刷新 / 全部启动 / 全部停止
    - 中间可滚动插件列表，每个插件一张 PluginCard
    - 底部状态标签（插件总数与已启动数）
    """

    def __init__(self, master, plugin_loader: PluginLoader, list_height: int = 240, **kwargs):
        super().__init__(master, **kwargs)
        self._loader = plugin_loader
        self._dark_colors = Theme.get_dark_colors()
        self._plugin_cards = {}  # name → PluginCard
        self._list_height = list_height

        self.configure(
            fg_color=self._dark_colors['bg_secondary'],
            corner_radius=8
        )

        self._create_ui()
        self._refresh_list()

    def _create_ui(self):
        """构建面板界面"""
        # 顶部标题栏
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=12, pady=(8, 4))

        title = ctk.CTkLabel(
            header_frame, text="插件管理",
            font=Theme.get_font('base'),
            text_color=self._dark_colors['text_primary']
        )
        title.pack(side="left")

        # 按钮栏
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=4)

        self.load_btn = ctk.CTkButton(
            btn_frame, text="加载插件", width=80, height=28,
            font=Theme.get_font('xs'),
            command=self._on_load
        )
        self.load_btn.pack(side="left", padx=(0, 4))

        self.refresh_btn = ctk.CTkButton(
            btn_frame, text="刷新", width=60, height=28,
            font=Theme.get_font('xs'),
            command=self._on_refresh
        )
        self.refresh_btn.pack(side="left", padx=4)

        self.start_all_btn = ctk.CTkButton(
            btn_frame, text="全部启动", width=80, height=28,
            font=Theme.get_font('xs'),
            command=self._on_start_all
        )
        self.start_all_btn.pack(side="right", padx=(4, 0))

        self.stop_all_btn = ctk.CTkButton(
            btn_frame, text="全部停止", width=80, height=28,
            font=Theme.get_font('xs'),
            fg_color=self._dark_colors.get('error', '#EF4444'),
            hover_color='#DC2626',
            command=self._on_stop_all
        )
        self.stop_all_btn.pack(side="right", padx=4)

        # 插件列表区域（可滚动，固定高度避免嵌套滚动失控）
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            label_text="",
            height=self._list_height
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        # 底部状态标签
        self.status_label = ctk.CTkLabel(
            self, text="",
            font=Theme.get_font('xs'),
            text_color=self._dark_colors['text_muted']
        )
        self.status_label.pack(fill="x", padx=12, pady=(0, 8))

    def _refresh_list(self):
        """刷新插件列表：销毁旧卡片并按当前 loader 状态重建"""
        # 清除现有卡片
        for card in self._plugin_cards.values():
            card.destroy()
        self._plugin_cards.clear()

        # 重新创建
        infos = self._loader.list_plugins()
        for info in infos:
            is_started = self._loader.is_started(info.name)
            card = PluginCard(
                self.scroll_frame,
                info,
                is_started,
                on_start=self._start_plugin,
                on_stop=self._stop_plugin
            )
            card.pack(fill="x", padx=4, pady=2)
            self._plugin_cards[info.name] = card

        self._update_status_label()

    def _on_load(self):
        """通过目录选择器加载单个插件"""
        dir_path = filedialog.askdirectory(title="选择插件目录")
        if dir_path:
            if self._loader.load_plugin(dir_path):
                self._refresh_list()
                self.status_label.configure(text="插件加载成功")
            else:
                self.status_label.configure(text="插件加载失败")

    def _on_refresh(self):
        """刷新列表"""
        self._refresh_list()

    def _on_start_all(self):
        """启动所有已加载插件"""
        self._loader.start_all()
        self._refresh_list()

    def _on_stop_all(self):
        """停止所有已启动插件"""
        self._loader.stop_all()
        self._refresh_list()

    def _start_plugin(self, name):
        """启动单个插件并更新对应卡片"""
        if self._loader.start_plugin(name):
            if name in self._plugin_cards:
                self._plugin_cards[name].update_status(True)
            self._update_status_label()

    def _stop_plugin(self, name):
        """ 停止单个插件并更新对应卡片"""
        self._loader.stop_plugin(name)
        if name in self._plugin_cards:
            self._plugin_cards[name].update_status(False)
        self._update_status_label()

    def _update_status_label(self):
        """根据当前 loader 状态更新底部状态文本"""
        infos = self._loader.list_plugins()
        started = sum(1 for info in infos if self._loader.is_started(info.name))
        self.status_label.configure(text=f"共 {len(infos)} 个插件，{started} 个已启动")

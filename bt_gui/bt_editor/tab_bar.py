import customtkinter as ctk
from typing import Callable, Optional, Dict


class TabButton(ctk.CTkFrame):
    """Tab 按钮组件

    包含运行/停止按钮、名称标签、状态指示器、关闭按钮
    支持双击名称标签进入编辑模式（仅修改 project_info.name）
    """
    ICON_RUN = "\u25b6"
    ICON_STOP = "\u25a0"
    ICON_CLOSE = "\u2715"

    def __init__(self, master, tab_id: str, name: str,
                 on_run_stop: Optional[Callable[[str, bool], None]] = None,
                 on_close: Optional[Callable[[str], None]] = None,
                 on_click: Optional[Callable[[str], None]] = None,
                 on_rename: Optional[Callable[[str, str], bool]] = None,
                 on_is_running_check: Optional[Callable[[str], bool]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)

        self.tab_id = tab_id
        self._name = name
        self._is_running = False
        self._is_active = False
        self._is_editing = False

        self._on_run_stop = on_run_stop
        self._on_close = on_close
        self._on_click = on_click
        self._on_rename = on_rename
        self._on_is_running_check = on_is_running_check

        self._create_widgets()

    def _create_widgets(self):
        self._run_stop_btn = ctk.CTkButton(
            self,
            text=self.ICON_RUN,
            width=24,
            height=24,
            font=("Arial", 10),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self._on_run_stop_click
        )
        self._run_stop_btn.pack(side="left", padx=2)

        self._name_label = ctk.CTkLabel(
            self,
            text=self._name,
            font=("Microsoft YaHei", 11),
            cursor="hand2"
        )
        self._name_label.pack(side="left", padx=4, fill="x", expand=True)
        # 单击切换 Tab
        self._name_label.bind("<Button-1>", self._on_name_click)
        # 双击进入重命名编辑模式
        self._name_label.bind("<Double-Button-1>", self._on_name_double_click)

        # 编辑模式的输入框（初始隐藏）
        self._name_entry = ctk.CTkEntry(
            self,
            font=("Microsoft YaHei", 11),
            height=20,
            width=120,
        )
        self._name_entry.bind("<Return>", self._on_entry_confirm)
        self._name_entry.bind("<Escape>", self._on_entry_cancel)
        self._name_entry.bind("<FocusOut>", self._on_entry_focus_out)

        self._status_indicator = ctk.CTkLabel(
            self,
            text="",
            font=("Arial", 8),
            text_color="#22c55e"
        )
        self._status_indicator.pack(side="left", padx=2)

        self._close_btn = ctk.CTkButton(
            self,
            text=self.ICON_CLOSE,
            width=20,
            height=20,
            font=("Arial", 8),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            text_color=("gray10", "gray90"),
            command=self._on_close_click
        )
        self._close_btn.pack(side="right", padx=2)

        self._update_style()

    def _update_style(self):
        if self._is_active:
            self.configure(fg_color=("gray75", "gray25"))
            self._name_label.configure(font=("Microsoft YaHei", 11, "bold"))
        else:
            self.configure(fg_color="transparent")
            self._name_label.configure(font=("Microsoft YaHei", 11))

        if self._is_running:
            self._run_stop_btn.configure(text=self.ICON_STOP, text_color="#22c55e")
            self._status_indicator.configure(text="\u2022")
        else:
            self._run_stop_btn.configure(text=self.ICON_RUN, text_color=("gray10", "gray90"))
            self._status_indicator.configure(text="")

    def _on_run_stop_click(self):
        if self._on_run_stop:
            self._on_run_stop(self.tab_id, not self._is_running)

    def _on_close_click(self):
        if self._on_close:
            self._on_close(self.tab_id)

    def _on_name_click(self, event):
        if self._is_editing:
            return
        if self._on_click:
            self._on_click(self.tab_id)

    def _on_name_double_click(self, event):
        """双击进入重命名编辑模式。

        项目运行中禁止重命名（避免状态错乱）。
        """
        if self._is_editing:
            return
        # 检查项目是否在运行
        if self._on_is_running_check and self._on_is_running_check(self.tab_id):
            # 项目运行中，禁止重命名
            try:
                from tkinter import messagebox
                messagebox.showinfo("提示", "项目运行中，无法重命名。请先停止运行。", parent=self)
            except Exception:
                pass
            return
        if not self._on_rename:
            return
        self._enter_edit_mode()

    def _enter_edit_mode(self):
        """进入编辑模式：隐藏 label，显示 entry"""
        self._is_editing = True
        self._name_label.pack_forget()
        # 将 entry 放在 label 原位置
        self._name_entry.pack(side="left", padx=4, fill="x", expand=True,
                              before=self._status_indicator)
        self._name_entry.delete(0, "end")
        self._name_entry.insert(0, self._name)
        self._name_entry.select_range(0, "end")
        self._name_entry.focus_set()

    def _exit_edit_mode(self, restore_label: bool = True):
        """退出编辑模式"""
        if not self._is_editing:
            return
        self._is_editing = False
        self._name_entry.pack_forget()
        if restore_label:
            self._name_label.pack(side="left", padx=4, fill="x", expand=True,
                                  before=self._status_indicator)

    def _on_entry_confirm(self, event=None):
        """Enter 确认重命名"""
        if not self._is_editing:
            return
        new_name = self._name_entry.get().strip()
        # 空值或未变更 → 取消
        if not new_name or new_name == self._name:
            self._exit_edit_mode()
            return
        # 校验：禁止控制字符
        if any(ord(c) < 32 for c in new_name):
            try:
                from tkinter import messagebox
                messagebox.showwarning("提示", "名称包含非法控制字符", parent=self)
            except Exception:
                pass
            return
        if len(new_name) > 100:
            try:
                from tkinter import messagebox
                messagebox.showwarning("提示", "名称过长（>100 字符）", parent=self)
            except Exception:
                pass
            return
        # 调用回调，由 editor 决定是否接受
        ok = False
        if self._on_rename:
            try:
                ok = bool(self._on_rename(self.tab_id, new_name))
            except Exception:
                ok = False
        if ok:
            # 接受：更新显示（editor 已通过 update_tab_name 更新，这里同步本地状态）
            self._name = new_name
            self._name_label.configure(text=new_name)
            self._exit_edit_mode()
        else:
            # 拒绝：保持编辑模式或退出？这里选择退出恢复原值
            self._exit_edit_mode()

    def _on_entry_cancel(self, event=None):
        """ESC 取消重命名"""
        self._exit_edit_mode()

    def _on_entry_focus_out(self, event=None):
        """失焦时确认（与多数 IDE 一致）"""
        if self._is_editing:
            self._on_entry_confirm()

    def set_running(self, running: bool):
        self._is_running = running
        self._update_style()

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()

    @property
    def name(self) -> str:
        return self._name

    def set_name(self, name: str):
        self._name = name
        if not self._is_editing:
            self._name_label.configure(text=name)


class TabBar(ctk.CTkFrame):
    """Tab 栏容器

    管理多个 TabButton，提供 Tab 切换、关闭、运行控制、双击重命名
    """

    def __init__(self, master,
                 on_tab_switch: Optional[Callable[[str], None]] = None,
                 on_tab_close: Optional[Callable[[str], None]] = None,
                 on_tab_run: Optional[Callable[[str], None]] = None,
                 on_tab_stop: Optional[Callable[[str], None]] = None,
                 on_import: Optional[Callable[[], None]] = None,
                 on_tab_rename: Optional[Callable[[str, str], bool]] = None,
                 on_tab_is_running: Optional[Callable[[str], bool]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)

        self._tab_buttons: Dict[str, TabButton] = {}
        self._active_tab_id: Optional[str] = None

        self._on_tab_switch = on_tab_switch
        self._on_tab_close = on_tab_close
        self._on_tab_run = on_tab_run
        self._on_tab_stop = on_tab_stop
        self._on_import = on_import
        self._on_tab_rename = on_tab_rename
        self._on_tab_is_running = on_tab_is_running

        self._create_widgets()

    def _create_widgets(self):
        self._tabs_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._tabs_frame.pack(side="left", fill="x", expand=True)

        self._add_btn = ctk.CTkButton(
            self._tabs_frame,
            text="+",
            width=28,
            height=28,
            font=("Arial", 14),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            text_color=("gray10", "gray90"),
            command=self._on_import_click
        )
        self._add_btn.pack(side="left", padx=2, pady=4)

    def _on_import_click(self):
        if self._on_import:
            self._on_import()

    def add_tab(self, tab_id: str, name: str) -> None:
        btn = TabButton(
            self._tabs_frame,
            tab_id=tab_id,
            name=name,
            on_run_stop=self._handle_run_stop,
            on_close=self._handle_close,
            on_click=self._handle_click,
            on_rename=self._handle_rename,
            on_is_running_check=self._handle_is_running_check,
        )
        btn.pack(side="left", padx=2, pady=4, before=self._add_btn)
        self._tab_buttons[tab_id] = btn

        if self._active_tab_id is None:
            self.set_active(tab_id)

    def remove_tab(self, tab_id: str) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].destroy()
            del self._tab_buttons[tab_id]

            if self._active_tab_id == tab_id:
                tab_ids = list(self._tab_buttons.keys())
                self._active_tab_id = tab_ids[0] if tab_ids else None
                if self._active_tab_id:
                    self.set_active(self._active_tab_id)

    def set_active(self, tab_id: str) -> None:
        for tid, btn in self._tab_buttons.items():
            btn.set_active(tid == tab_id)
        self._active_tab_id = tab_id

    def set_running(self, tab_id: str, running: bool) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].set_running(running)

    def _handle_run_stop(self, tab_id: str, should_run: bool):
        if should_run:
            if self._on_tab_run:
                self._on_tab_run(tab_id)
        else:
            if self._on_tab_stop:
                self._on_tab_stop(tab_id)

    def _handle_close(self, tab_id: str):
        if self._on_tab_close:
            self._on_tab_close(tab_id)

    def _handle_click(self, tab_id: str):
        if self._on_tab_switch:
            self._on_tab_switch(tab_id)

    def _handle_rename(self, tab_id: str, new_name: str) -> bool:
        """重命名回调，由 editor 处理实际逻辑"""
        if self._on_tab_rename:
            return bool(self._on_tab_rename(tab_id, new_name))
        return False

    def _handle_is_running_check(self, tab_id: str) -> bool:
        """检查 Tab 对应项目是否在运行"""
        if self._on_tab_is_running:
            return bool(self._on_tab_is_running(tab_id))
        return False

    def update_tab_name(self, tab_id: str, name: str) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].set_name(name)

    def get_tab_count(self) -> int:
        return len(self._tab_buttons)

    @property
    def active_tab_id(self) -> Optional[str]:
        return self._active_tab_id

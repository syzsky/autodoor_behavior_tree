import customtkinter as ctk
import tkinter as tk
import webbrowser
import os
from tkinter import messagebox

from bt_gui.theme import Theme


class LoginDialog(ctk.CTkToplevel):
    def __init__(self, parent, login_manager=None, on_success=None, on_failure=None):
        super().__init__(parent)
        self.title("平台登录")
        self.geometry("420x560")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._login_manager = login_manager
        self._on_success = on_success
        self._on_failure = on_failure
        self._dark_colors = Theme.get_dark_colors()
        self._build_ui()

    def _build_ui(self):
        self.configure(fg_color=self._dark_colors['bg_secondary'])

        main_frame = ctk.CTkFrame(self, fg_color=self._dark_colors['card_bg'], corner_radius=12)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Logo 区域
        logo_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        logo_frame.pack(pady=(20, 8))

        logo_label = self._create_logo_label(logo_frame)
        logo_label.pack(pady=(0, 6))

        title_label = ctk.CTkLabel(
            logo_frame,
            text="AutoDoor 平台登录",
            font=Theme.get_font('xl'),
            text_color=self._dark_colors['text_primary']
        )
        title_label.pack()

        subtitle_label = ctk.CTkLabel(
            logo_frame,
            text="登录以使用云端同步和高级功能",
            font=Theme.get_font('xs'),
            text_color=self._dark_colors['text_muted']
        )
        subtitle_label.pack(pady=(4, 0))

        # 表单区域
        form_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=25, pady=(4, 10))

        # 状态提示（放在登录按钮上方，确保可见）
        self.status_label = ctk.CTkLabel(
            form_frame,
            text="",
            font=Theme.get_font('sm'),
            text_color=self._dark_colors['error'],
            anchor="w",
            height=0
        )
        self.status_label.pack(fill="x", pady=(0, 4))

        # 用户名
        username_label = ctk.CTkLabel(
            form_frame,
            text="用户名",
            font=Theme.get_font('sm'),
            text_color=self._dark_colors['text_secondary'],
            anchor="w"
        )
        username_label.pack(fill="x", pady=(0, 6))
        self.username_entry = ctk.CTkEntry(
            form_frame,
            font=Theme.get_font('sm'),
            height=Theme.DIMENSIONS['input_height'],
            fg_color=self._dark_colors['bg_tertiary'],
            border_color=self._dark_colors['border'],
            text_color=self._dark_colors['text_primary'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            placeholder_text="请输入用户名"
        )
        self.username_entry.pack(fill="x", pady=(0, 12))
        self.username_entry.focus_set()

        # 密码
        password_label = ctk.CTkLabel(
            form_frame,
            text="密码",
            font=Theme.get_font('sm'),
            text_color=self._dark_colors['text_secondary'],
            anchor="w"
        )
        password_label.pack(fill="x", pady=(0, 6))
        self.password_entry = ctk.CTkEntry(
            form_frame,
            font=Theme.get_font('sm'),
            height=Theme.DIMENSIONS['input_height'],
            fg_color=self._dark_colors['bg_tertiary'],
            border_color=self._dark_colors['border'],
            text_color=self._dark_colors['text_primary'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            show="*",
            placeholder_text="请输入密码"
        )
        self.password_entry.pack(fill="x", pady=(0, 15))
        self.password_entry.bind("<Return>", lambda e: self._on_login())

        # 记住密码
        remember_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        remember_frame.pack(fill="x", pady=(0, 15))
        self.remember_var = tk.BooleanVar(value=False)
        remember_checkbox = ctk.CTkCheckBox(
            remember_frame,
            text="记住密码",
            font=Theme.get_font('sm'),
            text_color=self._dark_colors['text_secondary'],
            variable=self.remember_var,
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            checkmark_color="white"
        )
        remember_checkbox.pack(side="left")

        # 登录按钮
        self.login_btn = ctk.CTkButton(
            form_frame,
            text="登录",
            font=Theme.get_font('sm'),
            height=Theme.DIMENSIONS['button_height'],
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            command=self._on_login
        )
        self.login_btn.pack(fill="x", pady=(0, 8))

        # 注册按钮
        self.register_btn = ctk.CTkButton(
            form_frame,
            text="立即注册",
            font=Theme.get_font('sm'),
            height=32,
            fg_color="transparent",
            hover_color=self._dark_colors['border'],
            text_color=self._dark_colors['primary'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            command=self._on_register
        )
        self.register_btn.pack(fill="x")

        # 取消按钮
        cancel_btn = ctk.CTkButton(
            form_frame,
            text="取消",
            font=Theme.get_font('sm'),
            height=32,
            fg_color=self._dark_colors['bg_tertiary'],
            hover_color=self._dark_colors['border'],
            text_color=self._dark_colors['text_primary'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            command=self._on_cancel
        )
        cancel_btn.pack(fill="x", pady=(8, 0))

    def _create_logo_label(self, parent):
        try:
            from bt_utils.resource_manager import get_resource_manager
            from PIL import Image

            rm = get_resource_manager()
            icon_path = rm.get_icon_path()

            png_path = icon_path.replace('.ico', '.png')
            if os.path.exists(png_path):
                icon_path = png_path

            if os.path.exists(icon_path):
                image = Image.open(icon_path).resize((48, 48), Image.LANCZOS)
                tk_image = ctk.CTkImage(image, size=(48, 48))
                label = ctk.CTkLabel(parent, image=tk_image, text="")
                label.image = tk_image
                return label
        except Exception:
            pass

        return ctk.CTkLabel(
            parent,
            text="◉",
            font=('Microsoft YaHei', 32),
            text_color=self._dark_colors['primary']
        )

    def _on_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username:
            self._show_error("请输入用户名")
            return
        if not password:
            self._show_error("请输入密码")
            return

        self.login_btn.configure(state="disabled", text="登录中...")
        self.update()

        try:
            if self._login_manager:
                success = self._login_manager.login(username, password, self.remember_var.get())
                if success:
                    print(f"[Auth] 登录成功: {username}")
                    if self._on_success:
                        self._on_success(username)
                    self.destroy()
                else:
                    last_error = self._login_manager.get_last_error()
                    error_msg = last_error if last_error else "登录失败：用户名或密码错误"
                    print(f"[Auth] 登录失败: {error_msg}")
                    self._show_error(error_msg)
                    if self._on_failure:
                        self._on_failure()
            else:
                print("[Auth] 登录失败: 未配置登录管理器")
                self._show_error("未配置登录管理器")
                if self._on_failure:
                    self._on_failure()
        except Exception as e:
            print(f"[Auth] 登录异常: {e}")
            self._show_error(f"登录异常：{str(e)}")
            if self._on_failure:
                self._on_failure()
        finally:
            try:
                self.login_btn.configure(state="normal", text="登录")
            except Exception:
                pass

    def _show_error(self, text: str):
        """在状态标签中显示错误信息"""
        self.status_label.configure(text=text, height=20)

    def _on_register(self):
        base_url = self._get_base_url()
        if base_url:
            webbrowser.open(f"{base_url}/login/?tab=register")
        else:
            self._show_error("未配置服务器地址，无法打开注册页面")

    @staticmethod
    def _get_base_url() -> str:
        """从配置读取登录服务器地址（auth.platform.base_url）。

        开源仓库不包含真实服务器地址，用户需在配置中自行填写。
        """
        try:
            from config.settings_manager import SettingsManager
            return str(SettingsManager.get_instance().get(
                "auth.platform.base_url", "") or "").strip()
        except Exception:
            return ""

    def _on_cancel(self):
        self.destroy()

    def set_username(self, username: str):
        self.username_entry.delete(0, tk.END)
        self.username_entry.insert(0, username)

    def set_password(self, password: str):
        self.password_entry.delete(0, tk.END)
        self.password_entry.insert(0, password)

    def set_remember(self, remember: bool):
        self.remember_var.set(remember)

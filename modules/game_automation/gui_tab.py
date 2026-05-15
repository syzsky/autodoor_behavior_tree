"""
游戏自动化 GUI 标签页
====================
配置和管理自动化挂机任务
"""

import threading
import time
import cv2
from typing import Optional

try:
    import customtkinter as ctk
    from PIL import Image, ImageTk
    _GUI_AVAILABLE = True
except ImportError:
    _GUI_AVAILABLE = False

from .config import AutomationConfig, TaskConfig
from .engine import AutomationEngine, AutomationState


class GameAutomationTab:
    """
    游戏自动化标签页
    
    用法：
        app = ctk.CTk()
        tab_view = ctk.CTkTabview(app)
        tab_view.add("挂机自动化")
        tab = GameAutomationTab(tab_view.tab("挂机自动化"))
    """

    def __init__(self, parent, capture=None, input_ctrl=None):
        if not _GUI_AVAILABLE:
            raise ImportError("需要 customtkinter")

        self._parent = parent
        self._capture = capture
        self._input_ctrl = input_ctrl
        self._engine: Optional[AutomationEngine] = None

        # 配置
        self._config = AutomationConfig()

        # 构建UI
        self._build_ui()

    def _build_ui(self):
        """构建UI"""
        # 主布局：左配置 + 右状态
        self._left_frame = ctk.CTkFrame(self._parent, width=350)
        self._left_frame.pack(side="left", fill="y", padx=5, pady=5)
        self._left_frame.pack_propagate(False)

        self._right_frame = ctk.CTkFrame(self._parent)
        self._right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        self._build_config_panel()
        self._build_status_panel()

    def _build_config_panel(self):
        """构建配置面板"""
        scroll = ctk.CTkScrollableFrame(self._left_frame, width=330)
        scroll.pack(fill="both", expand=True)
        parent = scroll
        row = 0

        # ═══════════════════════════════════════
        # 🎯 窗口绑定
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="🎯 窗口绑定",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=10)
        row += 1

        ctk.CTkLabel(parent, text="窗口标题:").grid(row=row, column=0, sticky="w", padx=10)
        self._window_entry = ctk.CTkEntry(parent, width=200)
        self._window_entry.grid(row=row, column=1, padx=5, pady=2)
        self._window_entry.insert(0, self._config.window_title)
        row += 1

        # ═══════════════════════════════════════
        # 🏠 起点（盟重省）
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="🏠 起点设置",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        ctk.CTkLabel(parent, text="起点地图:").grid(row=row, column=0, sticky="w", padx=10)
        self._home_map_entry = ctk.CTkEntry(parent, width=200)
        self._home_map_entry.grid(row=row, column=1, padx=5, pady=2)
        self._home_map_entry.insert(0, self._config.home_map)
        row += 1

        ctk.CTkLabel(parent, text="地图模板:").grid(row=row, column=0, sticky="w", padx=10)
        self._home_template_entry = ctk.CTkEntry(parent, width=200,
                                                 placeholder_text="盟重省截图路径")
        self._home_template_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        # ═══════════════════════════════════════
        # 📋 任务配置
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="📋 任务配置",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        ctk.CTkLabel(parent, text="目标地图:").grid(row=row, column=0, sticky="w", padx=10)
        self._target_map_entry = ctk.CTkEntry(parent, width=200)
        self._target_map_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        ctk.CTkLabel(parent, text="传送NPC:").grid(row=row, column=0, sticky="w", padx=10)
        self._npc_name_entry = ctk.CTkEntry(parent, width=200)
        self._npc_name_entry.grid(row=row, column=1, padx=5, pady=2)
        self._npc_name_entry.insert(0, "传送员")
        row += 1

        ctk.CTkLabel(parent, text="NPC模板:").grid(row=row, column=0, sticky="w", padx=10)
        self._npc_template_entry = ctk.CTkEntry(parent, width=200,
                                                placeholder_text="NPC截图路径")
        self._npc_template_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        ctk.CTkLabel(parent, text="地图模板:").grid(row=row, column=0, sticky="w", padx=10)
        self._map_template_entry = ctk.CTkEntry(parent, width=200,
                                                placeholder_text="目标地图截图路径")
        self._map_template_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        # 参数
        param_frame = ctk.CTkFrame(parent)
        param_frame.grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        row += 1

        ctk.CTkLabel(param_frame, text="启动键:").grid(row=0, column=0, padx=2)
        self._hotkey_entry = ctk.CTkEntry(param_frame, width=50)
        self._hotkey_entry.insert(0, "F5")
        self._hotkey_entry.grid(row=0, column=1, padx=2)

        ctk.CTkLabel(param_frame, text="药阈值:").grid(row=0, column=2, padx=2)
        self._potion_entry = ctk.CTkEntry(param_frame, width=40)
        self._potion_entry.insert(0, "5")
        self._potion_entry.grid(row=0, column=3, padx=2)

        ctk.CTkLabel(param_frame, text="超时(s):").grid(row=0, column=4, padx=2)
        self._timeout_entry = ctk.CTkEntry(param_frame, width=50)
        self._timeout_entry.insert(0, "300")
        self._timeout_entry.grid(row=0, column=5, padx=2)

        # ═══════════════════════════════════════
        # ♻️ 回收配置
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="♻️ 自动回收",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        self._recycle_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(parent, text="启用自动回收", variable=self._recycle_var).grid(
            row=row, column=0, columnspan=2, padx=10, sticky="w")
        row += 1

        ctk.CTkLabel(parent, text="回收按钮模板:").grid(row=row, column=0, sticky="w", padx=10)
        self._recycle_template_entry = ctk.CTkEntry(parent, width=200,
                                                    placeholder_text="回收按钮截图")
        self._recycle_template_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        # ═══════════════════════════════════════
        # 💊 药品配置
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="💊 药品管理",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        ctk.CTkLabel(parent, text="药品图标模板:").grid(row=row, column=0, sticky="w", padx=10)
        self._potion_template_entry = ctk.CTkEntry(parent, width=200,
                                                   placeholder_text="药品截图")
        self._potion_template_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        ctk.CTkLabel(parent, text="商店NPC模板:").grid(row=row, column=0, sticky="w", padx=10)
        self._shop_npc_entry = ctk.CTkEntry(parent, width=200,
                                            placeholder_text="药店NPC截图")
        self._shop_npc_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        # ═══════════════════════════════════════
        # 🗺️ A* 寻路
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="🗺️ A* 寻路",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        self._astar_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(parent, text="启用A*寻路防卡怪", variable=self._astar_var).grid(
            row=row, column=0, columnspan=2, padx=10, sticky="w")
        row += 1

        # ═══════════════════════════════════════
        # 🚀 控制按钮
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="🚀 控制",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        ctrl_frame = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl_frame.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        self._start_btn = ctk.CTkButton(ctrl_frame, text="▶ 开始",
                                        command=self._start_auto, width=80)
        self._start_btn.pack(side="left", padx=3)

        self._stop_btn = ctk.CTkButton(ctrl_frame, text="⏹ 停止",
                                       command=self._stop_auto, width=80,
                                       state="disabled")
        self._stop_btn.pack(side="left", padx=3)

        self._pause_btn = ctk.CTkButton(ctrl_frame, text="⏸ 暂停",
                                        command=self._toggle_pause, width=80,
                                        state="disabled")
        self._pause_btn.pack(side="left", padx=3)

        # ═══════════════════════════════════════
        # 📸 截图模板按钮
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="📸 截图工具",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        capture_btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        capture_btn_frame.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        self._capture_map_btn = ctk.CTkButton(capture_btn_frame, text="📷 截地图模板",
                                              command=self._capture_map_template,
                                              width=100)
        self._capture_map_btn.pack(side="left", padx=3)

        self._capture_npc_btn = ctk.CTkButton(capture_btn_frame, text="📷 截NPC模板",
                                              command=self._capture_npc_template,
                                              width=100)
        self._capture_npc_btn.pack(side="left", padx=3)

    def _build_status_panel(self):
        """构建状态面板"""
        # 状态显示
        self._state_label = ctk.CTkLabel(self._right_frame, text="状态: 就绪",
                                          font=ctk.CTkFont(size=16, weight="bold"))
        self._state_label.pack(pady=10)

        # 进度条
        self._progress_bar = ctk.CTkProgressBar(self._right_frame, width=400)
        self._progress_bar.pack(pady=5)
        self._progress_bar.set(0)

        # 进度文本
        self._progress_label = ctk.CTkLabel(self._right_frame, text="等待开始...",
                                            font=ctk.CTkFont(size=12))
        self._progress_label.pack(pady=5)

        # 日志
        ctk.CTkLabel(self._right_frame, text="运行日志",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(15, 5))

        self._log_text = ctk.CTkTextbox(self._right_frame, height=250, width=450)
        self._log_text.pack(padx=10, pady=5, fill="both", expand=True)

        # 统计
        stats_frame = ctk.CTkFrame(self._right_frame)
        stats_frame.pack(pady=5, padx=10, fill="x")

        self._stats_labels = {}
        for i, (key, label) in enumerate([
            ("cycles", "执行轮次"), ("recycles", "回收次数"),
            ("potions_bought", "购药次数"), ("stuck_count", "卡怪次数"),
            ("errors", "错误次数"),
        ]):
            lbl = ctk.CTkLabel(stats_frame, text=f"{label}: 0")
            lbl.grid(row=i // 3, column=i % 3, padx=10, pady=2)
            self._stats_labels[key] = lbl

    # ── 回调 ─────────────────────────────────────

    def _on_state_change(self, state: AutomationState):
        """状态变化回调"""
        try:
            self._parent.after(0, lambda: self._state_label.configure(
                text=f"状态: {state.name}"))
        except Exception:
            pass

    def _on_status(self, msg: str):
        """状态消息回调"""
        try:
            self._parent.after(0, lambda: self._log(msg))
        except Exception:
            pass

    def _on_progress(self, pct: float, msg: str):
        """进度回调"""
        try:
            self._parent.after(0, lambda: (
                self._progress_bar.set(pct / 100),
                self._progress_label.configure(text=msg),
            ))
        except Exception:
            pass

    def _on_error(self, msg: str):
        """错误回调"""
        try:
            self._parent.after(0, lambda: self._log(f"❌ {msg}"))
        except Exception:
            pass

    def _log(self, msg: str):
        """添加日志"""
        import datetime
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self._log_text.insert("end", f"[{timestamp}] {msg}\n")
            self._log_text.see("end")
        except Exception:
            pass

    # ── 控制 ─────────────────────────────────────

    def _build_config_from_ui(self) -> AutomationConfig:
        """从UI读取配置"""
        config = AutomationConfig()
        config.window_title = self._window_entry.get().strip()
        config.home_map = self._home_map_entry.get().strip()
        config.home_map_image = self._home_template_entry.get().strip()

        # 任务配置
        if self._target_map_entry.get().strip():
            task = TaskConfig(
                name=f"挂机-{self._target_map_entry.get().strip()}",
                target_map=self._target_map_entry.get().strip(),
                target_map_image=self._map_template_entry.get().strip(),
                npc_name=self._npc_name_entry.get().strip() or "传送员",
                npc_image=self._npc_template_entry.get().strip(),
                start_hotkey=self._hotkey_entry.get().strip() or "F5",
                potion_threshold=int(self._potion_entry.get().strip() or "5"),
                auto_recycle=self._recycle_var.get(),
                timeout=int(self._timeout_entry.get().strip() or "300"),
            )
            config.tasks = [task]

        config.recycle_button_image = self._recycle_template_entry.get().strip()
        config.potion_image = self._potion_template_entry.get().strip()
        config.shop_npc_image = self._shop_npc_entry.get().strip()
        config.astar_enabled = self._astar_var.get()

        return config

    def _start_auto(self):
        """开始自动化"""
        if self._engine and self._engine.is_running:
            return

        # 构建配置
        self._config = self._build_config_from_ui()

        # 创建组件
        from .detector import GameDetector
        from .navigator import GameNavigator
        from .inventory import InventoryManager
        from .input_controller import InputController

        detector = GameDetector(self._capture)
        input_ctrl = self._input_ctrl or InputController()
        navigator = GameNavigator(detector, input_ctrl)
        inventory_mgr = InventoryManager(detector, input_ctrl)

        # 创建引擎
        self._engine = AutomationEngine(detector, navigator, inventory_mgr, self._config)
        self._engine.on_state_change = self._on_state_change
        self._engine.on_status = self._on_status
        self._engine.on_progress = self._on_progress
        self._engine.on_error = self._on_error

        # 启动
        self._engine.start()

        # 更新按钮状态
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._pause_btn.configure(state="normal")

        self._log("🚀 自动化已启动")

    def _stop_auto(self):
        """停止自动化"""
        if self._engine:
            self._engine.stop()

        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._pause_btn.configure(state="disabled")
        self._pause_btn.configure(text="⏸ 暂停")

        self._log("⏹ 自动化已停止")

    def _toggle_pause(self):
        """切换暂停"""
        if not self._engine:
            return

        if self._engine.is_running:
            if "暂停" in self._pause_btn.cget("text"):
                self._engine.pause()
                self._pause_btn.configure(text="▶ 继续")
                self._log("⏸ 已暂停")
            else:
                self._engine.resume()
                self._pause_btn.configure(text="⏸ 暂停")
                self._log("▶ 已继续")

    # ── 截图工具 ─────────────────────────────────

    def _capture_map_template(self):
        """截图当前画面作为地图模板"""
        if not self._capture:
            self._log("⚠️ 未绑定窗口")
            return

        frame = self._capture.capture()
        if frame is None:
            self._log("⚠️ 截图失败")
            return

        import os
        save_dir = "./data/game_automation/templates/maps"
        os.makedirs(save_dir, exist_ok=True)

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        map_name = self._target_map_entry.get().strip() or "unknown"
        path = f"{save_dir}/{map_name}_{timestamp}.jpg"
        cv2.imwrite(path, frame)

        self._log(f"✅ 地图模板已保存: {path}")
        self._map_template_entry.delete(0, "end")
        self._map_template_entry.insert(0, path)

    def _capture_npc_template(self):
        """截图当前画面作为NPC模板"""
        if not self._capture:
            self._log("⚠️ 未绑定窗口")
            return

        frame = self._capture.capture()
        if frame is None:
            self._log("⚠️ 截图失败")
            return

        import os
        save_dir = "./data/game_automation/templates/npcs"
        os.makedirs(save_dir, exist_ok=True)

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        npc_name = self._npc_name_entry.get().strip() or "npc"
        path = f"{save_dir}/{npc_name}_{timestamp}.jpg"
        cv2.imwrite(path, frame)

        self._log(f"✅ NPC模板已保存: {path}")
        self._npc_template_entry.delete(0, "end")
        self._npc_template_entry.insert(0, path)
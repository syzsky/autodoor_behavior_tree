"""
YOLO 训练器 GUI 标签页 v2.0
===========================
集成到 AutoDoor 行为树编辑器的标签页系统

功能：
  - 窗口绑定与实时预览（增强：缩放、平移、画中画、录制）
  - 自动截图采集控制
  - YOLO 智能训练（自动 HPO、迁移学习、模型对比）
  - 检测结果可视化
  - 训练监控仪表板
"""

import threading
import time
from typing import Optional, List, Dict

try:
    import customtkinter as ctk
    from PIL import Image, ImageTk
    import cv2
    import numpy as np
    _GUI_AVAILABLE = True
except ImportError:
    _GUI_AVAILABLE = False


class YOLOTrainerTab:
    """
    YOLO 训练器标签页 v2.0

    用法：
        app = ctk.CTk()
        tab_view = ctk.CTkTabview(app)
        tab_view.add("YOLO训练")

        yolo_tab = YOLOTrainerTab(tab_view.tab("YOLO训练"))
        yolo_tab.pack(fill="both", expand=True)
    """

    def __init__(self, parent, app=None):
        if not _GUI_AVAILABLE:
            raise ImportError("需要 customtkinter, PIL, cv2, numpy")

        self._parent = parent
        self._app = app

        # 核心组件
        self._capture = None
        self._stream = None
        self._live_view = None
        self._trainer = None
        self._smart_trainer = None
        self._visualizer = None
        self._collector = None

        # 状态
        self._is_streaming = False
        self._is_collecting = False
        self._is_training = False
        self._is_recording = False
        self._stream_thread = None

        # 配置
        self._config = {
            "window_title": "",
            "save_dir": "./data/yolo_raw",
            "dataset_name": "yolo_dataset",
            "model_size": "n",
            "epochs": 50,
            "batch_size": 16,
            "confidence": 0.5,
            "capture_interval": 0.5,
            "max_samples": 500,
            "classes": "",
            # 新增配置
            "enable_hpo": True,
            "hpo_trials": 10,
            "use_transfer_learning": True,
            "freeze_layers": 10,
            "enable_model_comparison": True,
            "show_fps": True,
            "show_crosshair": False,
            "pip_enabled": False,
            "record_fps": 15,
            "auto_export_on_complete": True,
        }

        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        # ── 左侧面板 ──
        self._left_frame = ctk.CTkFrame(self._parent, width=320)
        self._left_frame.pack(side="left", fill="y", padx=5, pady=5)
        self._left_frame.pack_propagate(False)

        # ── 右侧预览面板 ──
        self._right_frame = ctk.CTkFrame(self._parent)
        self._right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        """构建左侧面板（可滚动）"""
        # 使用滚动框架
        self._scroll_frame = ctk.CTkScrollableFrame(self._left_frame, width=300)
        self._scroll_frame.pack(fill="both", expand=True)

        parent = self._scroll_frame
        row = 0

        # ═══════════════════════════════════════
        # 🎯 窗口绑定
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="🎯 窗口绑定",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=10)
        row += 1

        # 窗口标题输入
        ctk.CTkLabel(parent, text="窗口标题:").grid(row=row, column=0, sticky="w", padx=10)
        self._window_title_entry = ctk.CTkEntry(parent, width=180)
        self._window_title_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        # 按钮行
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=5)

        self._refresh_btn = ctk.CTkButton(btn_frame, text="🔄 刷新",
                                          command=self._refresh_windows, width=90)
        self._refresh_btn.pack(side="left", padx=3)

        self._bind_btn = ctk.CTkButton(btn_frame, text="📌 绑定",
                                       command=self._bind_window, width=90)
        self._bind_btn.pack(side="left", padx=3)

        self._unbind_btn = ctk.CTkButton(btn_frame, text="❌ 解绑",
                                         command=self._unbind_window, width=90)
        self._unbind_btn.pack(side="left", padx=3)
        row += 1

        # 窗口列表
        self._window_listbox = ctk.CTkTextbox(parent, height=80)
        self._window_listbox.grid(row=row, column=0, columnspan=2, padx=10, pady=2, sticky="ew")
        row += 1

        self._window_status_label = ctk.CTkLabel(parent, text="未绑定窗口", text_color="gray")
        self._window_status_label.grid(row=row, column=0, columnspan=2, padx=10)
        row += 1

        # ═══════════════════════════════════════
        # 📺 实时预览（增强）
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="📺 实时预览",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        # 预览控制按钮
        preview_btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        preview_btn_frame.grid(row=row, column=0, columnspan=2, pady=3)

        self._stream_start_btn = ctk.CTkButton(
            preview_btn_frame, text="▶ 预览",
            command=self._start_stream, width=70)
        self._stream_start_btn.pack(side="left", padx=2)

        self._stream_stop_btn = ctk.CTkButton(
            preview_btn_frame, text="⏹ 停止",
            command=self._stop_stream, width=70, state="disabled")
        self._stream_stop_btn.pack(side="left", padx=2)

        self._record_btn = ctk.CTkButton(
            preview_btn_frame, text="⏺ 录制",
            command=self._toggle_recording, width=70)
        self._record_btn.pack(side="left", padx=2)

        self._screenshot_btn = ctk.CTkButton(
            preview_btn_frame, text="📷 截图",
            command=self._take_screenshot, width=70)
        self._screenshot_btn.pack(side="left", padx=2)
        row += 1

        # 缩放控制
        zoom_frame = ctk.CTkFrame(parent, fg_color="transparent")
        zoom_frame.grid(row=row, column=0, columnspan=2, pady=3)

        ctk.CTkButton(zoom_frame, text="🔍+", command=self._zoom_in, width=50).pack(side="left", padx=2)
        ctk.CTkButton(zoom_frame, text="🔍-", command=self._zoom_out, width=50).pack(side="left", padx=2)
        ctk.CTkButton(zoom_frame, text="↺", command=self._zoom_reset, width=40).pack(side="left", padx=2)

        # 画中画开关
        self._pip_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(zoom_frame, text="画中画", variable=self._pip_var,
                        command=self._toggle_pip).pack(side="left", padx=5)
        row += 1

        # 十字准星开关
        self._crosshair_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(parent, text="十字准星", variable=self._crosshair_var,
                        command=self._toggle_crosshair).grid(
            row=row, column=0, columnspan=2, padx=10, sticky="w")
        row += 1

        # FPS 和状态
        self._fps_label = ctk.CTkLabel(parent, text="FPS: 0.0 | Zoom: 1.0x")
        self._fps_label.grid(row=row, column=0, columnspan=2, padx=10)
        row += 1

        self._record_status_label = ctk.CTkLabel(parent, text="", text_color="gray")
        self._record_status_label.grid(row=row, column=0, columnspan=2, padx=10)
        row += 1

        # ═══════════════════════════════════════
        # 📷 截图采集
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="📷 截图采集",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        # 采集参数
        param_frame = ctk.CTkFrame(parent)
        param_frame.grid(row=row, column=0, columnspan=2, padx=10, pady=2, sticky="ew")

        ctk.CTkLabel(param_frame, text="间隔(s):").grid(row=0, column=0, padx=5)
        self._interval_entry = ctk.CTkEntry(param_frame, width=60)
        self._interval_entry.insert(0, "0.5")
        self._interval_entry.grid(row=0, column=1, padx=5)

        ctk.CTkLabel(param_frame, text="最大数量:").grid(row=0, column=2, padx=5)
        self._max_samples_entry = ctk.CTkEntry(param_frame, width=60)
        self._max_samples_entry.insert(0, "500")
        self._max_samples_entry.grid(row=0, column=3, padx=5)
        row += 1

        # 保存目录
        dir_frame = ctk.CTkFrame(parent, fg_color="transparent")
        dir_frame.grid(row=row, column=0, columnspan=2, padx=10, pady=2, sticky="ew")
        ctk.CTkLabel(dir_frame, text="保存目录:").pack(side="left")
        self._save_dir_entry = ctk.CTkEntry(dir_frame, width=150)
        self._save_dir_entry.insert(0, "./data/yolo_raw")
        self._save_dir_entry.pack(side="left", padx=5)
        row += 1

        # 采集按钮
        collect_btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        collect_btn_frame.grid(row=row, column=0, columnspan=2, pady=5)

        self._collect_start_btn = ctk.CTkButton(
            collect_btn_frame, text="▶ 开始采集",
            command=self._start_collection, width=100)
        self._collect_start_btn.pack(side="left", padx=3)

        self._collect_stop_btn = ctk.CTkButton(
            collect_btn_frame, text="⏹ 停止采集",
            command=self._stop_collection, width=100, state="disabled")
        self._collect_stop_btn.pack(side="left", padx=3)
        row += 1

        self._collect_progress = ctk.CTkProgressBar(parent, width=260)
        self._collect_progress.grid(row=row, column=0, columnspan=2, padx=10, pady=2)
        self._collect_progress.set(0)
        row += 1

        self._collect_status_label = ctk.CTkLabel(parent, text="未开始采集")
        self._collect_status_label.grid(row=row, column=0, columnspan=2, padx=10)
        row += 1

        # ═══════════════════════════════════════
        # 🧠 YOLO 智能训练
        # ═══════════════════════════════════════
        ctk.CTkLabel(parent, text="🧠 YOLO 智能训练",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1

        # 训练参数
        train_param = ctk.CTkFrame(parent)
        train_param.grid(row=row, column=0, columnspan=2, padx=10, pady=2, sticky="ew")

        ctk.CTkLabel(train_param, text="模型:").grid(row=0, column=0, padx=3)
        self._model_size_var = ctk.StringVar(value="n")
        self._model_size_menu = ctk.CTkOptionMenu(
            train_param, values=["n", "s", "m", "l", "x"],
            variable=self._model_size_var, width=50)
        self._model_size_menu.grid(row=0, column=1, padx=3)

        ctk.CTkLabel(train_param, text="轮数:").grid(row=0, column=2, padx=3)
        self._epochs_entry = ctk.CTkEntry(train_param, width=50)
        self._epochs_entry.insert(0, "50")
        self._epochs_entry.grid(row=0, column=3, padx=3)
        row += 1

        # 类别输入
        ctk.CTkLabel(parent, text="类别 (逗号分隔):").grid(
            row=row, column=0, sticky="w", padx=10)
        self._classes_entry = ctk.CTkEntry(parent, width=180)
        self._classes_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        # 智能训练选项
        smart_frame = ctk.CTkFrame(parent)
        smart_frame.grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        self._hpo_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(smart_frame, text="自动HPO", variable=self._hpo_var).grid(
            row=0, column=0, padx=5, pady=2, sticky="w")

        self._tl_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(smart_frame, text="迁移学习", variable=self._tl_var).grid(
            row=0, column=1, padx=5, pady=2, sticky="w")

        self._compare_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(smart_frame, text="模型对比", variable=self._compare_var).grid(
            row=1, column=0, padx=5, pady=2, sticky="w")

        self._auto_export_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(smart_frame, text="自动导出", variable=self._auto_export_var).grid(
            row=1, column=1, padx=5, pady=2, sticky="w")
        row += 1

        # 训练按钮
        train_btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        train_btn_frame.grid(row=row, column=0, columnspan=2, pady=5)

        self._auto_annotate_btn = ctk.CTkButton(
            train_btn_frame, text="🏷️ 标注",
            command=self._auto_annotate, width=75)
        self._auto_annotate_btn.pack(side="left", padx=2)

        self._quality_btn = ctk.CTkButton(
            train_btn_frame, text="📊 质检",
            command=self._check_quality, width=75)
        self._quality_btn.pack(side="left", padx=2)

        self._smart_train_btn = ctk.CTkButton(
            train_btn_frame, text="🚀 智能训练",
            command=self._start_smart_training, width=90)
        self._smart_train_btn.pack(side="left", padx=2)
        row += 1

        # 停止训练按钮
        self._stop_train_btn = ctk.CTkButton(
            parent, text="⏹ 停止训练",
            command=self._stop_training, width=200,
            fg_color="#cc3333", hover_color="#aa2222", state="disabled")
        self._stop_train_btn.grid(row=row, column=0, columnspan=2, pady=3)
        row += 1

        # 训练进度
        self._train_progress = ctk.CTkProgressBar(parent, width=260)
        self._train_progress.grid(row=row, column=0, columnspan=2, padx=10, pady=2)
        self._train_progress.set(0)
        row += 1

        self._train_status_label = ctk.CTkLabel(parent, text="未开始训练")
        self._train_status_label.grid(row=row, column=0, columnspan=2, padx=10)
        row += 1

        # 训练日志
        self._train_log = ctk.CTkTextbox(parent, height=100)
        self._train_log.grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        row += 1

    def _build_right_panel(self):
        """构建右侧预览面板"""
        # 预览画布
        self._preview_label = ctk.CTkLabel(
            self._right_frame, text="实时预览区域",
            font=ctk.CTkFont(size=16))
        self._preview_label.pack(pady=20)

        # 底部信息面板
        bottom_frame = ctk.CTkFrame(self._right_frame)
        bottom_frame.pack(fill="x", side="bottom", padx=10, pady=5)

        # 检测结果显示
        self._detection_frame = ctk.CTkFrame(bottom_frame)
        self._detection_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkLabel(self._detection_frame, text="📋 检测结果",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)

        self._detection_text = ctk.CTkTextbox(self._detection_frame, height=150)
        self._detection_text.pack(fill="both", expand=True, padx=10, pady=5)

    # ── 工具方法 ─────────────────────────────────

    def _log_train(self, msg: str):
        """写入训练日志"""
        self._train_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self._train_log.see("end")

    def _update_status(self, label, text, color="gray"):
        """更新状态标签"""
        label.configure(text=text, text_color=color)

    # ── 窗口操作 ─────────────────────────────────

    def _refresh_windows(self):
        """刷新窗口列表"""
        try:
            from ..capture.window_capture import WindowCapture
            windows = WindowCapture.enum_windows()
            self._window_listbox.delete("1.0", "end")
            for w in windows:
                self._window_listbox.insert("end", f"{w.title} [{w.class_name}]\n")
        except Exception as e:
            self._window_listbox.delete("1.0", "end")
            self._window_listbox.insert("end", f"获取窗口列表失败: {e}")

    def _bind_window(self):
        """绑定窗口"""
        title = self._window_title_entry.get().strip()
        if not title:
            self._update_status(self._window_status_label, "请输入窗口标题", "red")
            return

        try:
            from ..capture.window_capture import WindowCapture

            if self._capture is None:
                self._capture = WindowCapture()

            if self._capture.bind_window(title_contains=title):
                info = self._capture.window_info
                self._update_status(
                    self._window_status_label,
                    f"✅ 已绑定: {info.title} ({info.width}x{info.height})",
                    "green")
            else:
                self._update_status(
                    self._window_status_label,
                    f"❌ 未找到窗口: {title}", "red")
        except Exception as e:
            self._update_status(self._window_status_label, f"❌ 错误: {e}", "red")

    def _unbind_window(self):
        """解绑窗口"""
        if self._capture:
            self._capture.unbind()
            self._capture = None
        self._update_status(self._window_status_label, "未绑定窗口", "gray")

    # ── 实时预览（增强）───────────────────────────

    def _start_stream(self):
        """开始实时预览（使用 LiveView）"""
        if not self._capture or not self._capture.is_bound:
            self._update_status(self._window_status_label, "请先绑定窗口", "red")
            return

        try:
            from ..capture.live_view import LiveView, ViewConfig

            config = ViewConfig(
                max_width=960,
                max_height=540,
                show_fps=True,
                show_info=True,
                show_crosshair=self._crosshair_var.get(),
                pip_enabled=self._pip_var.get(),
            )

            self._live_view = LiveView(self._capture, config)
            self._live_view.on_frame = self._on_stream_frame
            self._live_view.on_fps_update = self._on_fps_update
            self._live_view.on_error = self._on_stream_error
            self._live_view.start(fps_limit=30)

            self._is_streaming = True
            self._stream_start_btn.configure(state="disabled")
            self._stream_stop_btn.configure(state="normal")

        except Exception as e:
            self._update_status(self._window_status_label, f"预览失败: {e}", "red")

    def _stop_stream(self):
        """停止实时预览"""
        if self._live_view:
            self._live_view.stop()
            self._live_view = None

        self._is_streaming = False
        self._stream_start_btn.configure(state="normal")
        self._stream_stop_btn.configure(state="disabled")
        self._fps_label.configure(text="FPS: 0.0 | Zoom: 1.0x")

    def _on_stream_frame(self, frame):
        """流帧回调"""
        try:
            self._parent.after(0, lambda f=frame: self._update_preview(f))
        except Exception:
            pass

    def _on_fps_update(self, fps):
        """FPS 更新回调"""
        try:
            zoom = self._live_view.zoom_level if self._live_view else 1.0
            self._parent.after(
                0, lambda: self._fps_label.configure(
                    text=f"FPS: {fps:.1f} | Zoom: {zoom:.1f}x"))
        except Exception:
            pass

    def _on_stream_error(self, error):
        """流错误回调"""
        pass

    def _update_preview(self, frame):
        """更新预览画面"""
        try:
            h, w = frame.shape[:2]
            max_size = 480
            scale = min(max_size / max(w, 1), max_size / max(h, 1))
            if scale < 1:
                new_w, new_h = int(w * scale), int(h * scale)
                preview = cv2.resize(frame, (new_w, new_h))
            else:
                preview = frame

            preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(preview_rgb)
            img_tk = ImageTk.PhotoImage(image=img)

            self._preview_label.configure(image=img_tk, text="")
            self._preview_label.image = img_tk
        except Exception:
            pass

    # ── 缩放控制 ─────────────────────────────────

    def _zoom_in(self):
        if self._live_view:
            self._live_view.zoom_in()

    def _zoom_out(self):
        if self._live_view:
            self._live_view.zoom_out()

    def _zoom_reset(self):
        if self._live_view:
            self._live_view.zoom_reset()

    def _toggle_pip(self):
        """切换画中画"""
        if self._live_view:
            self._live_view._config.pip_enabled = self._pip_var.get()

    def _toggle_crosshair(self):
        """切换十字准星"""
        if self._live_view:
            self._live_view._config.show_crosshair = self._crosshair_var.get()

    # ── 录制 ─────────────────────────────────────

    def _toggle_recording(self):
        """切换录制状态"""
        if not self._live_view:
            self._update_status(self._window_status_label, "请先开始预览", "red")
            return

        if self._is_recording:
            path = self._live_view.stop_recording()
            self._is_recording = False
            self._record_btn.configure(text="⏺ 录制")
            self._update_status(self._record_status_label,
                               f"已保存: {path}" if path else "录制已停止")
        else:
            path = self._live_view.start_recording()
            self._is_recording = True
            self._record_btn.configure(text="⏹ 停止")
            self._update_status(self._record_status_label,
                               f"录制中: {path}", "red")

    # ── 截图 ─────────────────────────────────────

    def _take_screenshot(self):
        """截取当前帧"""
        if not self._live_view:
            self._update_status(self._window_status_label, "请先开始预览", "red")
            return

        path = self._live_view.take_screenshot()
        if path:
            self._update_status(self._record_status_label, f"截图已保存: {path}", "green")
        else:
            self._update_status(self._record_status_label, "截图失败", "red")

    # ── 截图采集 ─────────────────────────────────

    def _start_collection(self):
        """开始截图采集"""
        if not self._capture or not self._capture.is_bound:
            self._update_status(self._collect_status_label, "请先绑定窗口", "red")
            return

        try:
            from ..training.trainer import AutoScreenshotCollector, TrainingConfig

            config = TrainingConfig()
            config.capture_interval = float(self._interval_entry.get() or "0.5")
            config.max_samples = int(self._max_samples_entry.get() or "500")

            save_dir = self._save_dir_entry.get().strip()

            self._collector = AutoScreenshotCollector(self._capture, config)
            self._collector.setup_directory()

            self._is_collecting = True
            self._collector.start()

            self._collect_start_btn.configure(state="disabled")
            self._collect_stop_btn.configure(state="normal")

            self._update_collection_progress()

        except Exception as e:
            self._update_status(self._collect_status_label, f"启动失败: {e}", "red")

    def _stop_collection(self):
        """停止截图采集"""
        if self._collector:
            self._collector.stop()

        self._is_collecting = False
        self._collect_start_btn.configure(state="normal")
        self._collect_stop_btn.configure(state="disabled")

        count = self._collector.count if self._collector else 0
        self._update_status(self._collect_status_label, f"采集完成: {count} 张")

    def _update_collection_progress(self):
        """更新采集进度"""
        if not self._is_collecting or not self._collector:
            return

        count = self._collector.count
        max_samples = int(self._max_samples_entry.get() or "500")
        progress = min(count / max(max_samples, 1), 1.0)

        self._collect_progress.set(progress)
        self._update_status(
            self._collect_status_label,
            f"采集中: {count}/{max_samples} ({progress*100:.0f}%)")

        if self._is_collecting and count < max_samples:
            if self._app:
                self._parent.after(200, self._update_collection_progress)

    # ── 自动标注 ─────────────────────────────────

    def _auto_annotate(self):
        """执行自动标注"""
        save_dir = self._save_dir_entry.get().strip()
        if not save_dir:
            self._update_status(self._train_status_label, "请先设置保存目录", "red")
            return

        classes_str = self._classes_entry.get().strip()
        classes = [c.strip() for c in classes_str.split(",") if c.strip()]

        def _do_annotate():
            try:
                from ..training.trainer import SmartAnnotator, TrainingConfig

                config = TrainingConfig()
                config.classes = classes
                config.confidence_threshold = float(
                    self._config.get("confidence", 0.5))

                annotator = SmartAnnotator(config)
                annotator.load_pretrained_model()

                stats = annotator.batch_annotate(save_dir, "", classes)

                total = sum(stats.values())
                msg = f"标注完成: {len(stats)} 张, {total} 个框"

                if self._app:
                    self._parent.after(0, lambda: self._update_status(
                        self._train_status_label, msg, "green"))

            except Exception as e:
                if self._app:
                    self._parent.after(0, lambda: self._update_status(
                        self._train_status_label, f"标注失败: {e}", "red"))

        self._update_status(self._train_status_label, "标注中...")
        threading.Thread(target=_do_annotate, daemon=True).start()

    # ── 数据质检 ─────────────────────────────────

    def _check_quality(self):
        """执行数据质量检查"""
        save_dir = self._save_dir_entry.get().strip()
        if not save_dir:
            self._update_status(self._train_status_label, "请先设置保存目录", "red")
            return

        def _do_check():
            try:
                from ..training.smart_train import TrainingQualityAnalyzer

                analyzer = TrainingQualityAnalyzer(save_dir)
                report = analyzer.analyze()

                score = report.get("score", 0)
                issues = report.get("issues", [])
                recommendations = report.get("recommendations", [])

                msg = f"质量评分: {score}/100"
                if issues:
                    msg += f" | 问题: {len(issues)}个"
                if recommendations:
                    msg += f" | 建议: {len(recommendations)}条"

                color = "green" if score >= 70 else ("orange" if score >= 40 else "red")

                if self._app:
                    self._parent.after(0, lambda: self._update_status(
                        self._train_status_label, msg, color))

                    # 详细报告写入日志
                    self._parent.after(0, lambda: self._log_train(
                        f"=== 数据质量报告 ===\n"
                        f"评分: {score}/100\n"
                        f"图片数: {report.get('total_images', 0)}\n"
                        f"标注数: {report.get('total_annotations', 0)}\n"
                        f"类别分布: {report.get('class_distribution', {})}\n"
                        + (f"问题:\n" + "\n".join(f"  - {i}" for i in issues) if issues else "")
                        + (f"\n建议:\n" + "\n".join(f"  - {r}" for r in recommendations) if recommendations else "")
                    ))

            except Exception as e:
                if self._app:
                    self._parent.after(0, lambda: self._update_status(
                        self._train_status_label, f"质检失败: {e}", "red"))

        self._update_status(self._train_status_label, "质检中...")
        threading.Thread(target=_do_check, daemon=True).start()

    # ── 智能训练 ─────────────────────────────────

    def _start_smart_training(self):
        """开始智能训练"""
        classes_str = self._classes_entry.get().strip()
        classes = [c.strip() for c in classes_str.split(",") if c.strip()]

        if not classes:
            self._update_status(self._train_status_label, "请输入类别", "red")
            return

        model_size = self._model_size_var.get()
        epochs = int(self._epochs_entry.get() or "50")
        save_dir = self._save_dir_entry.get().strip()

        self._smart_train_btn.configure(state="disabled")
        self._stop_train_btn.configure(state="normal")
        self._is_training = True
        self._train_progress.set(0)

        def _do_smart_train():
            try:
                from ..training.smart_train import SmartTrainer

                self._log_train(f"初始化智能训练器 (模型: yolov8{model_size}, 轮数: {epochs})")

                self._smart_trainer = SmartTrainer(
                    dataset_root=save_dir,
                    classes=classes,
                    model_size=model_size,
                    epochs=epochs,
                    batch_size=int(self._config.get("batch_size", 16)),
                )

                # 数据质检
                self._log_train("Step 1: 数据质量分析...")
                quality = self._smart_trainer.analyze_data_quality()
                self._log_train(f"  质量评分: {quality.get('score', 0)}/100")

                if quality.get("score", 0) < 30:
                    raise RuntimeError(f"数据质量过低 ({quality.get('score')}/100)")

                # 自动 HPO
                if self._hpo_var.get():
                    self._log_train("Step 2: 自动超参数优化...")
                    best_params = self._smart_trainer.auto_optimize(
                        epochs_per_trial=min(10, epochs // 5),
                        progress_callback=lambda t, total, p, r: self._log_train(
                            f"  HPO Trial {t}/{total}: {p}" +
                            (f" -> mAP50={r.get('mAP50', 0):.3f}" if r else "")
                        )
                    )
                    self._log_train(f"  最优参数: {best_params}")

                # 完整训练
                self._log_train("Step 3: 开始完整训练...")
                results = self._smart_trainer.train_smart(
                    use_hpo=False,  # HPO 已完成
                )

                # 模型对比
                if self._compare_var.get():
                    self._log_train("Step 4: 模型对比...")
                    compare_results = self._smart_trainer.compare_models(
                        model_sizes=["n", "s"],
                        epochs=min(30, epochs),
                    )
                    for r in compare_results:
                        if "error" not in r:
                            self._log_train(
                                f"  yolov8{r['model_size']}: "
                                f"mAP50={r.get('mAP50', 0):.3f}, "
                                f"mAP50-95={r.get('mAP50_95', 0):.3f}"
                            )

                # 获取结果
                best_path = self._smart_trainer.best_model_path
                msg = f"训练完成! 模型: {best_path}"
                self._log_train(msg)

                if self._app:
                    self._parent.after(0, lambda: self._update_status(
                        self._train_status_label, msg, "green"))
                    self._parent.after(0, lambda: self._train_progress.set(1.0))

            except Exception as e:
                self._log_train(f"训练失败: {e}")
                if self._app:
                    self._parent.after(0, lambda: self._update_status(
                        self._train_status_label, f"训练失败: {e}", "red"))

            finally:
                self._is_training = False
                if self._app:
                    self._parent.after(0, lambda: self._smart_train_btn.configure(state="normal"))
                    self._parent.after(0, lambda: self._stop_train_btn.configure(state="disabled"))

        self._update_status(self._train_status_label, "准备训练...")
        threading.Thread(target=_do_smart_train, daemon=True).start()

    def _stop_training(self):
        """停止训练"""
        if self._smart_trainer:
            self._smart_trainer.stop_training()
        self._is_training = False
        self._update_status(self._train_status_label, "训练已停止", "orange")
        self._smart_train_btn.configure(state="normal")
        self._stop_train_btn.configure(state="disabled")

    # ── 清理 ─────────────────────────────────────

    def destroy(self):
        """清理资源"""
        self._stop_stream()
        self._stop_collection()
        if self._live_view:
            self._live_view.destroy()

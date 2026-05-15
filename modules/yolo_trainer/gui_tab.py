"""
YOLO 训练器 GUI 标签页
=======================
集成到 AutoDoor 行为树编辑器的标签页系统中

功能：
  - 窗口绑定与实时预览
  - 自动截图采集控制
  - YOLO 训练控制面板
  - 检测结果可视化
"""

import threading
import time
from typing import Optional

try:
    import customtkinter as ctk
    from PIL import Image
    import cv2
    import numpy as np
    _GUI_AVAILABLE = True
except ImportError:
    _GUI_AVAILABLE = False


class YOLOTrainerTab:
    """
    YOLO 训练器标签页
    
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
        self._trainer = None
        self._visualizer = None
        self._collector = None
        
        # 状态
        self._is_streaming = False
        self._is_collecting = False
        self._is_training = False
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
        }
        
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        # ── 左侧面板 ──
        self._left_frame = ctk.CTkFrame(self._parent, width=300)
        self._left_frame.pack(side="left", fill="y", padx=5, pady=5)
        self._left_frame.pack_propagate(False)
        
        # ── 右侧预览面板 ──
        self._right_frame = ctk.CTkFrame(self._parent)
        self._right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        
        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        """构建左侧面板"""
        row = 0
        
        # === 窗口绑定 ===
        ctk.CTkLabel(self._left_frame, text="🎯 窗口绑定",
                    font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=10)
        row += 1
        
        # 窗口标题输入
        ctk.CTkLabel(self._left_frame, text="窗口标题:").grid(
            row=row, column=0, sticky="w", padx=10)
        self._window_title_entry = ctk.CTkEntry(self._left_frame, width=180)
        self._window_title_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        # 刷新窗口列表按钮
        btn_frame = ctk.CTkFrame(self._left_frame, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=5)
        
        self._refresh_btn = ctk.CTkButton(btn_frame, text="🔄 刷新窗口列表",
                                         command=self._refresh_windows, width=120)
        self._refresh_btn.pack(side="left", padx=3)
        
        self._bind_btn = ctk.CTkButton(btn_frame, text="📌 绑定窗口",
                                       command=self._bind_window, width=120)
        self._bind_btn.pack(side="left", padx=3)
        row += 1
        
        # 窗口列表
        self._window_listbox = ctk.CTkTextbox(self._left_frame, height=80)
        self._window_listbox.grid(row=row, column=0, columnspan=2, padx=10, pady=2, sticky="ew")
        row += 1
        
        self._window_status_label = ctk.CTkLabel(self._left_frame, text="未绑定窗口",
                                                 text_color="gray")
        self._window_status_label.grid(row=row, column=0, columnspan=2, padx=10)
        row += 1
        
        # === 实时预览控制 ===
        ctk.CTkLabel(self._left_frame, text="📺 实时预览",
                    font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1
        
        preview_btn_frame = ctk.CTkFrame(self._left_frame, fg_color="transparent")
        preview_btn_frame.grid(row=row, column=0, columnspan=2, pady=5)
        
        self._stream_start_btn = ctk.CTkButton(
            preview_btn_frame, text="▶ 开始预览",
            command=self._start_stream, width=100)
        self._stream_start_btn.pack(side="left", padx=3)
        
        self._stream_stop_btn = ctk.CTkButton(
            preview_btn_frame, text="⏹ 停止预览",
            command=self._stop_stream, width=100, state="disabled")
        self._stream_stop_btn.pack(side="left", padx=3)
        row += 1
        
        self._fps_label = ctk.CTkLabel(self._left_frame, text="FPS: 0.0")
        self._fps_label.grid(row=row, column=0, columnspan=2, padx=10)
        row += 1
        
        # === 截图采集 ===
        ctk.CTkLabel(self._left_frame, text="📷 截图采集",
                    font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1
        
        # 采集参数
        param_frame = ctk.CTkFrame(self._left_frame)
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
        dir_frame = ctk.CTkFrame(self._left_frame, fg_color="transparent")
        dir_frame.grid(row=row, column=0, columnspan=2, padx=10, pady=2, sticky="ew")
        
        ctk.CTkLabel(dir_frame, text="保存目录:").pack(side="left")
        self._save_dir_entry = ctk.CTkEntry(dir_frame, width=150)
        self._save_dir_entry.insert(0, "./data/yolo_raw")
        self._save_dir_entry.pack(side="left", padx=5)
        row += 1
        
        # 采集按钮
        collect_btn_frame = ctk.CTkFrame(self._left_frame, fg_color="transparent")
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
        
        self._collect_progress = ctk.CTkProgressBar(self._left_frame, width=260)
        self._collect_progress.grid(row=row, column=0, columnspan=2, padx=10, pady=2)
        self._collect_progress.set(0)
        row += 1
        
        self._collect_status_label = ctk.CTkLabel(self._left_frame, text="未开始采集")
        self._collect_status_label.grid(row=row, column=0, columnspan=2, padx=10)
        row += 1
        
        # === YOLO 训练 ===
        ctk.CTkLabel(self._left_frame, text="🧠 YOLO 训练",
                    font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 5), sticky="w", padx=10)
        row += 1
        
        # 训练参数
        train_param = ctk.CTkFrame(self._left_frame)
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
        ctk.CTkLabel(self._left_frame, text="类别 (逗号分隔):").grid(
            row=row, column=0, sticky="w", padx=10)
        self._classes_entry = ctk.CTkEntry(self._left_frame, width=180)
        self._classes_entry.grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        # 训练按钮
        train_btn_frame = ctk.CTkFrame(self._left_frame, fg_color="transparent")
        train_btn_frame.grid(row=row, column=0, columnspan=2, pady=5)
        
        self._auto_annotate_btn = ctk.CTkButton(
            train_btn_frame, text="🏷️ 自动标注",
            command=self._auto_annotate, width=100)
        self._auto_annotate_btn.pack(side="left", padx=3)
        
        self._train_btn = ctk.CTkButton(
            train_btn_frame, text="🚀 开始训练",
            command=self._start_training, width=100)
        self._train_btn.pack(side="left", padx=3)
        row += 1
        
        self._train_status_label = ctk.CTkLabel(self._left_frame, text="未开始训练")
        self._train_status_label.grid(row=row, column=0, columnspan=2, padx=10)

    def _build_right_panel(self):
        """构建右侧预览面板"""
        # 预览画布
        self._preview_label = ctk.CTkLabel(
            self._right_frame, text="实时预览区域",
            font=ctk.CTkFont(size=16))
        self._preview_label.pack(pady=20)
        
        # 检测结果显示
        self._detection_frame = ctk.CTkFrame(self._right_frame)
        self._detection_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(self._detection_frame, text="📋 检测结果",
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self._detection_text = ctk.CTkTextbox(self._detection_frame, height=200)
        self._detection_text.pack(fill="both", expand=True, padx=10, pady=5)

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
            self._window_status_label.configure(text="请输入窗口标题", text_color="red")
            return
        
        try:
            from ..capture.window_capture import WindowCapture
            
            if self._capture is None:
                self._capture = WindowCapture()
            
            if self._capture.bind_window(title_contains=title):
                info = self._capture.window_info
                self._window_status_label.configure(
                    text=f"✅ 已绑定: {info.title} ({info.width}x{info.height})",
                    text_color="green")
            else:
                self._window_status_label.configure(
                    text=f"❌ 未找到窗口: {title}", text_color="red")
        except Exception as e:
            self._window_status_label.configure(text=f"❌ 错误: {e}", text_color="red")

    # ── 实时预览 ─────────────────────────────────

    def _start_stream(self):
        """开始实时预览"""
        if not self._capture or not self._capture.is_bound:
            self._window_status_label.configure(text="请先绑定窗口", text_color="red")
            return
        
        try:
            from ..capture.screen_stream import ScreenStream
            
            self._stream = ScreenStream(self._capture, fps_limit=30)
            self._stream.on_frame = self._on_stream_frame
            self._stream.on_error = self._on_stream_error
            self._stream.start()
            
            self._is_streaming = True
            self._stream_start_btn.configure(state="disabled")
            self._stream_stop_btn.configure(state="normal")
            
        except Exception as e:
            self._window_status_label.configure(text=f"预览失败: {e}", text_color="red")

    def _stop_stream(self):
        """停止实时预览"""
        if self._stream:
            self._stream.stop()
            self._stream = None
        
        self._is_streaming = False
        self._stream_start_btn.configure(state="normal")
        self._stream_stop_btn.configure(state="disabled")
        self._fps_label.configure(text="FPS: 0.0")

    def _on_stream_frame(self, frame):
        """流帧回调（在捕获线程中执行）"""
        try:
            # 更新预览（需要线程安全）
            try:
                self._parent.after(0, lambda f=frame: self._update_preview(f))
            except Exception:
                pass
        except Exception:
            pass

    def _on_stream_error(self, error):
        """流错误回调"""
        pass

    def _update_preview(self, frame):
        """更新预览画面"""
        try:
            # 缩放预览
            h, w = frame.shape[:2]
            max_size = 480
            scale = min(max_size / w, max_size / h)
            if scale < 1:
                new_w, new_h = int(w * scale), int(h * scale)
                preview = cv2.resize(frame, (new_w, new_h))
            else:
                preview = frame
            
            # 转换为 PIL Image
            from PIL import Image, ImageTk
            preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(preview_rgb)
            img_tk = ImageTk.PhotoImage(image=img)
            
            self._preview_label.configure(image=img_tk, text="")
            self._preview_label.image = img_tk  # 防止 GC
            
            # 更新 FPS
            if self._stream:
                self._fps_label.configure(text=f"FPS: {self._stream.actual_fps:.1f}")
        except Exception:
            pass

    # ── 截图采集 ─────────────────────────────────

    def _start_collection(self):
        """开始截图采集"""
        if not self._capture or not self._capture.is_bound:
            self._collect_status_label.configure(text="请先绑定窗口", text_color="red")
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
            
            # 启动进度更新
            self._update_collection_progress()
            
        except Exception as e:
            self._collect_status_label.configure(text=f"启动失败: {e}", text_color="red")

    def _stop_collection(self):
        """停止截图采集"""
        if self._collector:
            self._collector.stop()
        
        self._is_collecting = False
        self._collect_start_btn.configure(state="normal")
        self._collect_stop_btn.configure(state="disabled")
        
        count = self._collector.count if self._collector else 0
        self._collect_status_label.configure(text=f"采集完成: {count} 张")

    def _update_collection_progress(self):
        """更新采集进度"""
        if not self._is_collecting or not self._collector:
            return
        
        count = self._collector.count
        max_samples = int(self._max_samples_entry.get() or "500")
        progress = min(count / max_samples, 1.0)
        
        self._collect_progress.set(progress)
        self._collect_status_label.configure(
            text=f"采集中: {count}/{max_samples} ({progress*100:.0f}%)")
        
        if self._is_collecting and count < max_samples:
            if self._app:
                self._parent.after(200, self._update_collection_progress)

    # ── 自动标注 ─────────────────────────────────

    def _auto_annotate(self):
        """执行自动标注"""
        save_dir = self._save_dir_entry.get().strip()
        if not save_dir:
            self._train_status_label.configure(text="请先设置保存目录", text_color="red")
            return
        
        classes_str = self._classes_entry.get().strip()
        classes = [c.strip() for c in classes_str.split(",") if c.strip()]
        
        def _do_annotate():
            try:
                from ..training.trainer import SmartAnnotator, TrainingConfig
                
                config = TrainingConfig()
                config.classes = classes
                config.confidence_threshold = float(self._confidence_entry.get() 
                                                     if hasattr(self, '_confidence_entry') 
                                                     else "0.5")
                
                annotator = SmartAnnotator(config)
                annotator.load_pretrained_model()
                
                stats = annotator.batch_annotate(save_dir, "", classes)
                
                total = sum(stats.values())
                msg = f"标注完成: {len(stats)} 张, {total} 个框"
                
                if self._app:
                    self._parent.after(0, lambda: self._train_status_label.configure(
                        text=msg, text_color="green"))
                    
            except Exception as e:
                if self._app:
                    self._parent.after(0, lambda: self._train_status_label.configure(
                        text=f"标注失败: {e}", text_color="red"))
        
        self._train_status_label.configure(text="标注中...")
        threading.Thread(target=_do_annotate, daemon=True).start()

    # ── 训练 ─────────────────────────────────────

    def _start_training(self):
        """开始 YOLO 训练"""
        classes_str = self._classes_entry.get().strip()
        classes = [c.strip() for c in classes_str.split(",") if c.strip()]
        
        if not classes:
            self._train_status_label.configure(text="请输入类别", text_color="red")
            return
        
        def _do_train():
            try:
                from ..training.trainer import YOLOTrainer, TrainingConfig
                
                config = TrainingConfig()
                config.classes = classes
                config.model_size = self._model_size_var.get()
                config.epochs = int(self._epochs_entry.get() or "50")
                config.batch_size = 16
                
                save_dir = self._save_dir_entry.get().strip()
                config.dataset_root = save_dir
                
                trainer = YOLOTrainer(config)
                trainer.prepare_dataset()
                
                if self._app:
                    self._parent.after(0, lambda: self._train_status_label.configure(
                        text="训练中..."))
                
                results = trainer.train()
                
                best_path = trainer.get_best_model_path()
                msg = f"训练完成! 模型: {best_path}"
                
                if self._app:
                    self._parent.after(0, lambda: self._train_status_label.configure(
                        text=msg, text_color="green"))
                    
            except Exception as e:
                if self._app:
                    self._parent.after(0, lambda: self._train_status_label.configure(
                        text=f"训练失败: {e}", text_color="red"))
        
        self._train_status_label.configure(text="准备训练...")
        threading.Thread(target=_do_train, daemon=True).start()

    # ── 清理 ─────────────────────────────────────

    def destroy(self):
        """清理资源"""
        self._stop_stream()
        self._stop_collection()

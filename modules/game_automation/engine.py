"""
自动化引擎
=========
核心状态机，编排完整的挂机流程：

状态流转：
  INIT → BIND_WINDOW → DETECT_START → FIND_NPC → TELEPORT
  → VERIFY_MAP → START_FARM → FARMING
  → (背包满 → RECYCLE → FARMING)
  → (药品不足 → GO_HOME → BUY_POTIONS → FARMING)
  → (卡怪 → A_STAR_MOVE → FARMING)
  → COMPLETED
"""

import time
import threading
from enum import Enum, auto
from typing import Optional, Callable
from pathlib import Path

import cv2
import numpy as np


class AutomationState(Enum):
    """自动化状态"""
    IDLE = auto()
    BIND_WINDOW = auto()        # 绑定窗口
    DETECT_START = auto()       # 检测起点（盟重省）
    FIND_NPC = auto()           # 找传送员NPC
    TELEPORT = auto()           # 点击传送
    VERIFY_MAP = auto()         # 地图一致性校验
    START_FARM = auto()         # 按F5启动挂机
    FARMING = auto()            # 挂机中
    RECYCLE = auto()            # 背包回收
    GO_HOME = auto()            # 回城
    BUY_POTIONS = auto()        # 购买药品
    A_STAR_MOVE = auto()        # A*寻路
    GO_TO_MAP = auto()          # 重新去地图
    COMPLETED = auto()          # 完成
    ERROR = auto()              # 错误


class AutomationEngine:
    """
    自动化引擎
    
    用法：
        engine = AutomationEngine(detector, navigator, inventory, config)
        engine.start()
        
        # 回调
        engine.on_state_change = lambda state: print(f"状态: {state}")
    """

    def __init__(self, detector, navigator, inventory_manager, config):
        self._detector = detector
        self._navigator = navigator
        self._inventory = inventory_manager
        self._config = config

        # 状态
        self._state = AutomationState.IDLE
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._pause_event.set()  # 默认不暂停

        # 计时
        self._state_start_time = 0
        self._stuck_start_time = 0
        self._last_stuck_frame = None
        self._last_farm_check_time = 0

        # 任务
        self._current_task_index = 0
        self._task_start_time = 0

        # 回调
        self.on_state_change: Optional[Callable[[AutomationState], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[float, str], None]] = None

        # 状态统计
        self._stats = {
            "cycles": 0,
            "recycles": 0,
            "potions_bought": 0,
            "stuck_count": 0,
            "errors": 0,
        }
        self._npc_retry_count = 0

    # ── 属性 ─────────────────────────────────────

    @property
    def state(self) -> AutomationState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    # ── 控制 ─────────────────────────────────────

    def start(self):
        """启动自动化"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._main_loop, daemon=True)
        self._thread.start()
        self._log_status("🚀 自动化启动")

    def stop(self):
        """停止自动化"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self._state = AutomationState.IDLE
        self._log_status("⏹ 自动化停止")

    def pause(self):
        """暂停"""
        self._pause_event.clear()
        self._log_status("⏸ 已暂停")

    def resume(self):
        """恢复"""
        self._pause_event.set()
        self._log_status("▶ 已恢复")

    # ── 主循环 ───────────────────────────────────

    def _main_loop(self):
        """主循环"""
        while self._running:
            self._pause_event.wait()  # 暂停检查

            try:
                self._run_state_machine()
            except Exception as e:
                self._on_error(f"主循环异常: {e}")
                time.sleep(2)

            time.sleep(0.5)

    def _run_state_machine(self):
        """运行状态机"""
        current_state = self._state

        if current_state == AutomationState.IDLE:
            self._change_state(AutomationState.BIND_WINDOW)

        elif current_state == AutomationState.BIND_WINDOW:
            self._do_bind_window()

        elif current_state == AutomationState.DETECT_START:
            self._do_detect_start()

        elif current_state == AutomationState.FIND_NPC:
            self._do_find_npc()

        elif current_state == AutomationState.TELEPORT:
            self._do_teleport()

        elif current_state == AutomationState.VERIFY_MAP:
            self._do_verify_map()

        elif current_state == AutomationState.START_FARM:
            self._do_start_farm()

        elif current_state == AutomationState.FARMING:
            self._do_farming()

        elif current_state == AutomationState.RECYCLE:
            self._do_recycle()

        elif current_state == AutomationState.GO_HOME:
            self._do_go_home()

        elif current_state == AutomationState.BUY_POTIONS:
            self._do_buy_potions()

        elif current_state == AutomationState.A_STAR_MOVE:
            self._do_astar_move()

        elif current_state == AutomationState.GO_TO_MAP:
            self._do_goto_map()

        elif current_state == AutomationState.COMPLETED:
            self._do_completed()

        elif current_state == AutomationState.ERROR:
            self._do_error()

    def _change_state(self, new_state: AutomationState):
        """切换状态"""
        old_state = self._state
        self._state = new_state
        self._state_start_time = time.time()

        if self.on_state_change:
            try:
                self.on_state_change(new_state)
            except Exception:
                pass

        self._log_status(f"状态: {old_state.name} → {new_state.name}")

    # ── 各状态实现 ───────────────────────────────

    def _do_bind_window(self):
        """1. 绑定窗口"""
        window_title = self._config.window_title
        if not window_title:
            self._change_state(AutomationState.ERROR)
            self._on_error("未设置窗口标题")
            return

        # 使用 window_capture 绑定
        if hasattr(self._detector, '_capture') and self._detector._capture:
            try:
                if hasattr(self._detector._capture, 'bind_window'):
                    self._detector._capture.bind_window(window_title)
                    self._on_progress(5, f"✅ 窗口绑定成功: {window_title}")
                    # 弹窗提示绑定成功
                    try:
                        import tkinter as tk
                        from tkinter import messagebox
                        _root = tk.Tk()
                        _root.withdraw()
                        _root.attributes('-topmost', True)
                        messagebox.showinfo("绑定成功", f"窗口绑定成功: {window_title}")
                        _root.destroy()
                    except Exception:
                        pass
                else:
                    self._on_progress(5, "窗口已绑定")
            except Exception as e:
                self._on_error(f"窗口绑定失败: {e}")
                return

        # 等待绑定稳定
        time.sleep(1)
        self._change_state(AutomationState.DETECT_START)

    def _do_detect_start(self):
        """2. 检测起点（盟重省）"""
        self._on_progress(10, "🔍 检测起点地图...")

        home_map_image = self._config.home_map_image
        if home_map_image:
            template = cv2.imread(home_map_image)
            frame = self._detector.capture_frame()
            if frame is not None and template is not None:
                result = self._detector.find_template(frame, template, threshold=0.6)
                if result.found:
                    self._on_progress(15, f"✅ 已确认起点: {self._config.home_map}")
                else:
                    self._on_error(f"起点地图不匹配，请确认在{self._config.home_map}")
                    return
            else:
                self._on_progress(15, "⚠️ 无起点模板，跳过检测")
        else:
            self._on_progress(15, "⚠️ 未设置起点模板，跳过")

        self._change_state(AutomationState.FIND_NPC)

    def _do_find_npc(self):
        """3. 找传送员NPC"""
        self._on_progress(20, "🔍 寻找传送员NPC...")
        config = self._config
        current_task = self._get_current_task()
        if not current_task:
            self._change_state(AutomationState.ERROR)
            self._on_error("没有可执行的任务")
            return
        npc_image = current_task.npc_image or config.tasks[0].npc_image if config.tasks else ""
        if not npc_image:
            self._on_error("未设置NPC模板图片")
            return
        npc_template = cv2.imread(npc_image)
        if npc_template is None:
            self._on_error(f"NPC模板图片不存在: {npc_image}")
            return
        found = self._navigator.find_and_click_npc(npc_template)
        if found:
            self._npc_retry_count = 0
            self._on_progress(25, f"✅ 找到{current_task.npc_name}并点击")
            self._change_state(AutomationState.TELEPORT)
        else:
            self._npc_retry_count += 1
            if self._npc_retry_count >= 5:
                self._on_error(f"连续{self._npc_retry_count}次未找到NPC，停止重试")
                self._npc_retry_count = 0
                return
            self._on_error(f"未找到{current_task.npc_name}(第{self._npc_retry_count}次)，尝试寻路")
            self._navigator.navigate_away_from_stuck(
                self._detector.capture_frame() or np.zeros((100, 100, 3), dtype=np.uint8))
            self._change_state(AutomationState.FIND_NPC)

    def _do_teleport(self):
        """4. 点击传送"""
        self._on_progress(30, "🚀 传送中...")
        current_task = self._get_current_task()
        if not current_task:
            self._change_state(AutomationState.ERROR)
            self._on_error("没有可执行的任务")
            return
        # 等待NPC对话框
        time.sleep(1.5)
        # 找"下图"或"传送"按钮
        if current_task.teleport_button_image:
            teleport_btn = cv2.imread(current_task.teleport_button_image)
            if teleport_btn is not None:
                frame = self._detector.capture_frame()
                if frame is not None:
                    result = self._detector.find_template(frame, teleport_btn, threshold=0.7)
                    if result.found:
                        self._navigator._input.click(result.center_x, result.center_y)
                        self._on_progress(32, "✅ 已点击传送按钮")
                        time.sleep(3)
                        self._change_state(AutomationState.VERIFY_MAP)
                        return
        # 尝试用goto_map
        if current_task.npc_image:
            npc_template = cv2.imread(current_task.npc_image)
            if npc_template is not None:
                success = self._navigator.goto_map(
                    current_task.target_map,
                    npc_template,
                    current_task.map_list_image,
                    current_task.teleport_button_image,
                )
                if success:
                    self._on_progress(32, "✅ 传送成功")
                    time.sleep(2)
                    self._change_state(AutomationState.VERIFY_MAP)
                    return
        self._on_error("传送失败")

    def _do_verify_map(self):
        """5. 地图一致性校验"""
        self._on_progress(35, "🔍 验证目标地图...")

        current_task = self._get_current_task()
        if not current_task:
            self._change_state(AutomationState.ERROR)
            return

        target_map = current_task.target_map
        target_image = current_task.target_map_image

        if target_image:
            template = cv2.imread(target_image)
            frame = self._detector.capture_frame()
            if frame is not None and template is not None:
                result = self._detector.find_template(frame, template, threshold=0.6)
                if result.found:
                    self._on_progress(40, f"✅ 已进入目标地图: {target_map}")
                else:
                    self._on_error(f"地图不匹配，当前不在{target_map}")
                    # 重试传送
                    self._change_state(AutomationState.FIND_NPC)
                    return
            else:
                self._on_progress(40, "⚠️ 无法验证地图，继续")
        else:
            self._on_progress(40, "⚠️ 未设置目标地图模板")

        self._change_state(AutomationState.START_FARM)

    def _do_start_farm(self):
        """6. 按F5启动挂机"""
        self._on_progress(45, "▶ 启动挂机...")

        current_task = self._get_current_task()
        hotkey = current_task.start_hotkey if current_task else "F5"

        # 模拟按键
        if hasattr(self._navigator, '_input'):
            self._navigator._input.press_key(hotkey.lower())

        self._on_progress(50, f"✅ 已按{hotkey}启动挂机")
        self._task_start_time = time.time()
        self._change_state(AutomationState.FARMING)

    def _do_farming(self):
        """7. 挂机中（循环检测）"""
        now = time.time()

        # 定期检测（每2秒）
        if now - self._last_farm_check_time < 2.0:
            return
        self._last_farm_check_time = now

        frame = self._detector.capture_frame()
        if frame is None:
            return

        # 7a. 检查背包是否满
        if self._config.inventory_full_indicator:
            full_indicator = cv2.imread(self._config.inventory_full_indicator)
            if full_indicator is not None:
                full_result = self._detector.find_template(frame, full_indicator, threshold=0.6)
                if full_result.found:
                    self._on_progress(55, "📦 背包满，准备回收")
                    self._change_state(AutomationState.RECYCLE)
                    return

        # 7b. 检查药品是否充足
        if self._config.potion_image:
            potion_template = cv2.imread(self._config.potion_image)
            if potion_template is not None:
                current_task = self._get_current_task()
                threshold = current_task.potion_threshold if current_task else 5
                count = self._detector.detect_potion_count(potion_template)
                if count < threshold:
                    self._on_progress(55, f"💊 药品不足({count}<{threshold})，回城购买")
                    self._change_state(AutomationState.GO_HOME)
                    return

        # 7c. 检测是否卡怪
        if self._last_stuck_frame is not None:
            is_stuck = self._detector.detect_stuck(self._last_stuck_frame, frame)
            if is_stuck:
                stuck_duration = now - self._stuck_start_time
                if stuck_duration > self._config.stuck_timeout:
                    self._stats["stuck_count"] += 1
                    self._on_progress(55, f"🚶 卡怪{stuck_duration:.0f}秒，执行A*寻路")
                    self._change_state(AutomationState.A_STAR_MOVE)
                    return
            else:
                self._stuck_start_time = now
        else:
            self._stuck_start_time = now

        self._last_stuck_frame = frame.copy()

        # 7e. 定期检测人物状态（每10秒）
        if hasattr(self._config, 'hp_roi') and self._config.hp_roi:
            hp = self._detector.detect_hp(frame, roi=self._config.hp_roi)
            if hp < 0.2:  # 血量低于20%
                self._on_progress(55, f"⚠️ 血量过低({hp:.0%})，注意安全")
        # 7f. 定期检测地图是否变化（每30秒）
        if hasattr(self._config, 'target_map_image') and self._config.target_map_image:
            if int(now) % 30 < 2:  # 每30秒检查一次
                current_task = self._get_current_task()
                if current_task and current_task.target_map_image:
                    map_template = cv2.imread(current_task.target_map_image)
                    if map_template is not None:
                        map_result = self._detector.find_template(frame, map_template, threshold=0.5)
                        if not map_result.found:
                            self._on_progress(55, "⚠️ 地图可能已变化，重新确认")
                            self._change_state(AutomationState.VERIFY_MAP)
                            return

        # 7d. 任务超时检查
        current_task = self._get_current_task()
        if current_task and current_task.timeout > 0:
            elapsed = now - self._task_start_time
            if elapsed > current_task.timeout:
                self._on_progress(55, f"⏰ 任务超时({elapsed:.0f}s)，下一个任务")
                self._next_task()
                return

        # 挂机中，更新进度
        elapsed = now - self._task_start_time
        self._on_progress(60 + min(elapsed / 60, 30),  # 60-90%
                         f"⏳ 挂机中... ({int(elapsed)}s)")

    def _do_recycle(self):
        """8. 自动回收"""
        self._stats["recycles"] += 1
        self._on_progress(55, "♻️ 执行回收...")

        recycle_template = cv2.imread(self._config.recycle_button_image)
        confirm_template = None
        if self._config.recycle_confirm_image:
            confirm_template = cv2.imread(self._config.recycle_confirm_image)

        if recycle_template is not None:
            success = self._inventory.auto_recycle(
                recycle_template, confirm_template)
            if success:
                self._on_progress(60, "✅ 回收完成")
            else:
                self._on_progress(60, "⚠️ 回收失败")

        self._change_state(AutomationState.FARMING)

    def _do_go_home(self):
        """9. 回城"""
        self._on_progress(60, "🏠 回城中...")

        home_map_template = None
        if self._config.home_map_image:
            home_map_template = cv2.imread(self._config.home_map_image)

        success = self._navigator.go_home(home_map_template)
        if success:
            self._on_progress(65, "✅ 已回城")
            self._change_state(AutomationState.BUY_POTIONS)
        else:
            self._on_progress(65, "⚠️ 回城可能失败，尝试继续")
            self._change_state(AutomationState.BUY_POTIONS)

    def _do_buy_potions(self):
        """10. 购买药品"""
        self._stats["potions_bought"] += 1
        self._on_progress(70, "💊 购买药品...")
        if (self._config.potion_image and self._config.shop_npc_image):
            potion_template = cv2.imread(self._config.potion_image)
            shop_npc = cv2.imread(self._config.shop_npc_image)
            buy_btn = cv2.imread(self._config.buy_button_image) if self._config.buy_button_image else None
            confirm_btn = cv2.imread(self._config.confirm_button_image) if self._config.confirm_button_image else None
            if potion_template is not None and shop_npc is not None:
                success = self._inventory.check_and_refill_potions(
                    potion_template,
                    potion_threshold=10,
                    shop_npc_template=shop_npc,
                    potion_shop_template=potion_template,
                    buy_button_template=buy_btn or potion_template,
                    confirm_template=confirm_btn,
                )
                if success:
                    self._on_progress(75, "✅ 药品购买完成")
                else:
                    self._on_progress(75, "⚠️ 购买药品失败")
        self._change_state(AutomationState.GO_TO_MAP)

    def _do_goto_map(self):
        """11. 重新去目标地图"""
        self._on_progress(80, "🚀 重新前往目标地图...")
        self._change_state(AutomationState.FIND_NPC)

    def _do_astar_move(self):
        """12. A* 寻路移动"""
        self._on_progress(80, "🗺️ A* 寻路中...")

        frame = self._detector.capture_frame()
        if frame is not None:
            self._navigator.navigate_away_from_stuck(frame)

        self._on_progress(85, "✅ 已移动位置")
        self._change_state(AutomationState.FARMING)

    def _do_completed(self):
        """完成"""
        self._on_progress(100, "✅ 所有任务完成")
        self._log_status("🎉 自动化完成")
        self.stop()

    def _do_error(self):
        """错误处理"""
        self._stats["errors"] += 1
        self._log_status("❌ 发生错误，等待5秒后重试...")
        time.sleep(5)

        # 尝试从错误恢复
        if self._state == AutomationState.ERROR:
            self._change_state(AutomationState.FARMING)

    # ── 工具方法 ─────────────────────────────────

    def _get_current_task(self):
        """获取当前任务"""
        if not self._config.tasks:
            return None
        if self._current_task_index < len(self._config.tasks):
            return self._config.tasks[self._current_task_index]
        return None

    def _next_task(self):
        """下一个任务"""
        self._current_task_index += 1
        if self._current_task_index >= len(self._config.tasks):
            self._change_state(AutomationState.COMPLETED)
        else:
            self._change_state(AutomationState.FIND_NPC)

    def _log_status(self, msg: str):
        """记录状态"""
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    def _on_error(self, msg: str):
        """错误回调"""
        self._change_state(AutomationState.ERROR)
        if self.on_error:
            try:
                self.on_error(msg)
            except Exception:
                pass

    def _on_progress(self, pct: float, msg: str):
        """进度回调"""
        if self.on_progress:
            try:
                self.on_progress(pct, msg)
            except Exception:
                pass

    # ── 清理 ─────────────────────────────────────

    def destroy(self):
        """清理资源"""
        self.stop()
        self._last_stuck_frame = None
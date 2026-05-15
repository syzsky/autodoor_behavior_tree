"""
背包管理模块
===========
功能：
  - 背包满自动回收
  - 药品数量检测
  - 药品不足回城购买
  - 商店购买药品
"""

import time
from typing import Optional, List


class InventoryManager:
    """
    背包管理器
    
    用法：
        inv = InventoryManager(detector, input_controller)
        if inv.is_inventory_full():
            inv.auto_recycle(recycle_button_template)
        if inv.get_potion_count(potion_template) < 5:
            inv.buy_potions(shop_npc_template)
    """

    def __init__(self, detector, input_controller):
        self._detector = detector
        self._input = input_controller
        self._last_recycle_time = 0
        self._recycle_cooldown = 5.0  # 回收冷却（秒）

    # ── 回收 ─────────────────────────────────────

    def auto_recycle(self, recycle_button_template,
                     confirm_template=None,
                     inventory_key: str = "B") -> bool:
        """
        自动回收背包
        
        Args:
            recycle_button_template: 回收按钮截图模板
            confirm_template: 确认按钮截图模板（可选）
            inventory_key: 打开背包快捷键
            
        Returns:
            是否成功回收
        """
        # 冷却检查
        now = time.time()
        if now - self._last_recycle_time < self._recycle_cooldown:
            return False

        # 打开背包
        self._input.press_key(inventory_key)
        time.sleep(0.5)

        # 找回收按钮
        frame = self._detector.capture_frame()
        if frame is None:
            self._input.press_key(inventory_key)  # 关闭背包
            return False

        result = self._detector.find_template(frame, recycle_button_template, threshold=0.7)
        if not result.found:
            self._input.press_key(inventory_key)  # 关闭背包
            return False

        # 点击回收
        self._input.click(result.center_x, result.center_y)
        time.sleep(0.5)

        # 确认
        if confirm_template is not None:
            confirm_frame = self._detector.capture_frame()
            if confirm_frame is not None:
                confirm_result = self._detector.find_template(
                    confirm_frame, confirm_template, threshold=0.7)
                if confirm_result.found:
                    self._input.click(confirm_result.center_x, confirm_result.center_y)
                    time.sleep(0.5)

        self._input.press_key(inventory_key)  # 关闭背包
        self._last_recycle_time = time.time()
        return True

    # ── 药品管理 ─────────────────────────────────

    def get_potion_count(self, potion_template,
                         inventory_roi: Optional[list] = None,
                         inventory_key: str = "B") -> int:
        """
        获取背包中药品数量
        
        Args:
            potion_template: 药品图标模板
            inventory_roi: 背包区域
            inventory_key: 打开背包快捷键
            
        Returns:
            药品数量
        """
        self._input.press_key(inventory_key)
        time.sleep(0.5)

        count = self._detector.detect_potion_count(
            potion_template, inventory_roi=inventory_roi)

        self._input.press_key(inventory_key)  # 关闭背包
        return count

    def buy_potions(self, shop_npc_template,
                    potion_shop_template,
                    buy_button_template,
                    confirm_template=None,
                    potion_count: int = 10) -> bool:
        """
        购买药品（回城后使用）
        
        流程：
            1. 找到商店NPC并点击
            2. 等待商店界面打开
            3. 点击药品购买
            4. 确认购买
            5. 关闭商店
            
        Args:
            shop_npc_template: 商店NPC模板
            potion_shop_template: 商店界面中药品图标
            buy_button_template: 购买按钮
            confirm_template: 确认按钮（可选）
            potion_count: 购买数量
            
        Returns:
            是否购买成功
        """
        # Step 1: 找商店NPC
        frame = self._detector.capture_frame()
        if frame is None:
            return False

        result = self._detector.find_template(frame, shop_npc_template, threshold=0.7)
        if result.found:
            self._input.click(result.center_x, result.center_y)
            time.sleep(1.5)  # 等待商店打开
        else:
            return False

        # Step 2: 找药品
        shop_frame = self._detector.capture_frame()
        if shop_frame is None:
            return False

        potion_result = self._detector.find_template(
            shop_frame, potion_shop_template, threshold=0.7)
        if potion_result.found:
            # 点击药品
            self._input.click(potion_result.center_x, potion_result.center_y)
            time.sleep(0.5)

            # 输入数量
            for _ in range(3):
                self._input.press_key("backspace")
            self._input.type_text(str(potion_count))
            time.sleep(0.3)

            # 点击购买
            buy_frame = self._detector.capture_frame()
            if buy_frame is not None:
                buy_result = self._detector.find_template(
                    buy_frame, buy_button_template, threshold=0.7)
                if buy_result.found:
                    self._input.click(buy_result.center_x, buy_result.center_y)
                    time.sleep(0.5)

            # 确认
            if confirm_template is not None:
                confirm_frame = self._detector.capture_frame()
                if confirm_frame is not None:
                    confirm_result = self._detector.find_template(
                        confirm_frame, confirm_template, threshold=0.7)
                    if confirm_result.found:
                        self._input.click(confirm_result.center_x, confirm_result.center_y)
                        time.sleep(0.5)

            return True

        # 关闭商店（按ESC）
        self._input.press_key("escape")
        return False

    def check_and_refill_potions(self, potion_template,
                                 potion_threshold: int,
                                 shop_npc_template,
                                 potion_shop_template,
                                 buy_button_template,
                                 inventory_roi: Optional[list] = None,
                                 confirm_template=None) -> bool:
        """
        检查药品数量并在不足时购买
        
        Args:
            potion_template: 药品图标模板
            potion_threshold: 低于此数量就购买
            shop_npc_template: 商店NPC模板
            potion_shop_template: 商店药品图标
            buy_button_template: 购买按钮
            inventory_roi: 背包区域
            confirm_template: 确认按钮
            
        Returns:
            是否需要购买（True=已购买）
        """
        count = self.get_potion_count(potion_template, inventory_roi)
        if count >= potion_threshold:
            return False  # 药品充足

        # 药品不足，购买
        return self.buy_potions(
            shop_npc_template,
            potion_shop_template,
            buy_button_template,
            confirm_template,
        )
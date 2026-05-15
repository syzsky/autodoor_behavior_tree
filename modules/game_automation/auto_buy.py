"""
自动买东西行为树脚本
==================
参考用法，可直接在 AutoDoor 行为树编辑器中导入使用

流程：
  1. 打开背包（按B）
  2. 检测药品数量
  3. 如果药品不足 → 关闭背包 → 找商店NPC → 购买 → 关闭商店
  4. 如果药品充足 → 关闭背包 → 继续挂机
"""

# ═══════════════════════════════════════════════
# 方式一：行为树 XML 格式（直接粘贴到编辑器）
# ═══════════════════════════════════════════════

BEHAVIOR_TREE_XML = '''<?xml version="1.0" encoding="utf-8"?>
<BehaviorTree ID="AutoBuyPotion">
    <Sequence name="自动买药流程">
        
        <!-- Step 1: 打开背包 -->
        <Action name="PressKey">
            <key>B</key>
            <delay>500</delay>
        </Action>
        
        <!-- Step 2: 检测药品数量（找图） -->
        <Condition name="ImageExists">
            <template>templates/potion_icon.jpg</template>
            <threshold>0.8</threshold>
            <count_min>5</count_min>  <!-- 少于5瓶则执行购买 -->
        </Condition>
        
        <!-- Step 3: 药品不足 → 购买 -->
        <Sequence name="购买流程">
            
            <!-- 关闭背包 -->
            <Action name="PressKey">
                <key>B</key>
                <delay>300</delay>
            </Action>
            
            <!-- 找商店NPC -->
            <Action name="FindAndClick">
                <template>templates/shop_npc.jpg</template>
                <threshold>0.75</threshold>
                <timeout>5000</timeout>
            </Action>
            
            <!-- 等待商店打开 -->
            <Action name="Wait">
                <ms>1500</ms>
            </Action>
            
            <!-- 找药品图标并点击 -->
            <Action name="FindAndClick">
                <template>templates/potion_shop.jpg</template>
                <threshold>0.75</threshold>
                <timeout>3000</timeout>
            </Action>
            
            <!-- 输入购买数量 -->
            <Action name="TypeText">
                <text>10</text>
                <delay>200</delay>
            </Action>
            
            <!-- 点击购买按钮 -->
            <Action name="FindAndClick">
                <template>templates/buy_button.jpg</template>
                <threshold>0.75</threshold>
                <timeout>3000</timeout>
            </Action>
            
            <!-- 确认购买 -->
            <Action name="FindAndClick">
                <template>templates/confirm_button.jpg</template>
                <threshold>0.75</threshold>
                <timeout>2000</timeout>
            </Action>
            
            <!-- 关闭商店（ESC） -->
            <Action name="PressKey">
                <key>ESC</key>
                <delay>500</delay>
            </Action>
            
            <Action name="Log">
                <message>✅ 药品购买完成</message>
            </Action>
            
        </Sequence>
        
    </Sequence>
</BehaviorTree>
'''

# ═══════════════════════════════════════════════
# 方式二：Python 脚本（直接运行）
# ═══════════════════════════════════════════════

AUTO_BUY_SCRIPT = '''"""
自动买东西脚本
============
用法：
  1. 先截好模板图放到 templates/ 目录
  2. 修改下面的模板路径
  3. 运行 python auto_buy.py
"""

import time
import cv2
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.game_automation.detector import GameDetector
from modules.game_automation.navigator import GameNavigator
from modules.game_automation.inventory import InventoryManager
from modules.game_automation.input_controller import InputController


# ═════ 配置区（修改这里的路径）═════

# 窗口标题
WINDOW_TITLE = "传奇"  # 改成你的游戏窗口标题

# 模板图片路径（先用截图工具截好）
SHOP_NPC_TEMPLATE = "./templates/shop_npc.jpg"       # 商店NPC截图
POTION_ICON = "./templates/potion_icon.jpg"           # 背包里药品图标
POTION_SHOP = "./templates/potion_shop.jpg"           # 商店界面药品图标
BUY_BUTTON = "./templates/buy_button.jpg"             # 购买按钮
CONFIRM_BUTTON = "./templates/confirm_button.jpg"     # 确认按钮

# 阈值
POTION_THRESHOLD = 5   # 少于这个数量就去买
BUY_COUNT = 10         # 一次买多少瓶

# ═════════════════════════════════════


def main():
    """主流程"""
    print("=" * 50)
    print("🛒 自动买东西脚本")
    print("=" * 50)

    # 1. 绑定窗口
    from modules.yolo_trainer.capture.window_capture import WindowCapture
    capture = WindowCapture()
    
    print(f"📌 绑定窗口: {WINDOW_TITLE}")
    try:
        capture.bind_window(WINDOW_TITLE)
        print("✅ 窗口绑定成功")
    except Exception as e:
        print(f"❌ 窗口绑定失败: {e}")
        return

    # 2. 创建组件
    detector = GameDetector(capture)
    input_ctrl = InputController()
    navigator = GameNavigator(detector, input_ctrl)
    inventory = InventoryManager(detector, input_ctrl)

    # 3. 加载模板
    potion_template = cv2.imread(POTION_ICON)
    shop_npc = cv2.imread(SHOP_NPC_TEMPLATE)
    potion_shop = cv2.imread(POTION_SHOP)
    buy_btn = cv2.imread(BUY_BUTTON)
    confirm_btn = cv2.imread(CONFIRM_BUTTON)

    if potion_template is None:
        print(f"❌ 药品模板不存在: {POTION_ICON}")
        return

    # 4. 检测药品数量
    print(f"🔍 检测药品数量...")
    count = inventory.get_potion_count(potion_template)
    print(f"📊 当前药品: {count}瓶")

    if count >= POTION_THRESHOLD:
        print(f"✅ 药品充足 ({count} >= {POTION_THRESHOLD})，无需购买")
        return

    # 5. 药品不足，开始购买
    print(f"💊 药品不足 ({count} < {POTION_THRESHOLD})，开始购买...")

    if shop_npc is None:
        print(f"❌ 商店NPC模板不存在: {SHOP_NPC_TEMPLATE}")
        return

    # 找商店NPC
    print("🔍 寻找商店NPC...")
    frame = detector.capture_frame()
    if frame is None:
        print("❌ 截图失败")
        return

    result = detector.find_template(frame, shop_npc, threshold=0.7)
    if not result.found:
        print("❌ 未找到商店NPC")
        return

    print(f"✅ 找到商店NPC，点击 ({result.center_x}, {result.center_y})")
    input_ctrl.click(result.center_x, result.center_y)
    time.sleep(1.5)

    # 在商店界面找药品
    if potion_shop is not None:
        print("🔍 寻找药品...")
        shop_frame = detector.capture_frame()
        if shop_frame is not None:
            potion_result = detector.find_template(shop_frame, potion_shop, threshold=0.7)
            if potion_result.found:
                print(f"✅ 找到药品，点击购买")
                input_ctrl.click(potion_result.center_x, potion_result.center_y)
                time.sleep(0.5)

                # 输入数量
                for _ in range(3):
                    input_ctrl.press_key("backspace")
                input_ctrl.type_text(str(BUY_COUNT))
                time.sleep(0.3)

                # 点击购买
                if buy_btn is not None:
                    buy_frame = detector.capture_frame()
                    if buy_frame is not None:
                        buy_result = detector.find_template(buy_frame, buy_btn, threshold=0.7)
                        if buy_result.found:
                            input_ctrl.click(buy_result.center_x, buy_result.center_y)
                            time.sleep(0.5)

                # 确认
                if confirm_btn is not None:
                    confirm_frame = detector.capture_frame()
                    if confirm_frame is not None:
                        confirm_result = detector.find_template(confirm_frame, confirm_btn, threshold=0.7)
                        if confirm_result.found:
                            input_ctrl.click(confirm_result.center_x, confirm_result.center_y)
                            time.sleep(0.5)

                print(f"✅ 购买完成！买了 {BUY_COUNT} 瓶")
            else:
                print("❌ 未找到药品")
        else:
            print("❌ 商店截图失败")
    else:
        print("⚠️ 无药品模板")

    # 关闭商店
    input_ctrl.press_key("escape")
    print("🏁 完成")


if __name__ == "__main__":
    main()
'''

# ═══════════════════════════════════════════════
# 方式三：使用 game_automation 模块（推荐）
# ═══════════════════════════════════════════════

MODULE_USAGE = '''
# 在 AutoDoor 的「挂机自动化」标签页中配置：
#
# 1. 药品图标模板 → 截一张背包里药品的图
# 2. 商店NPC模板  → 截一张药店NPC的图
# 3. 药品阈值     → 设置成 5（少于5瓶就去买）
#
# 然后点击「开始」，引擎会自动：
#   检测药品 → 不足 → 找商店NPC → 购买 → 继续挂机
'''

if __name__ == "__main__":
    print("=" * 60)
    print("🛒 自动买东西 - 使用说明")
    print("=" * 60)
    print()
    print("提供了三种方式：")
    print()
    print("1️⃣  行为树 XML")
    print("   直接复制 BEHAVIOR_TREE_XML 到编辑器")
    print()
    print("2️⃣  Python 脚本")
    print("   修改模板路径后运行: python auto_buy.py")
    print()
    print("3️⃣  挂机自动化模块（推荐）")
    print("   在 GUI 标签页配置即可")
    print()
    print("📸 需要先截的模板图：")
    print("   - shop_npc.jpg    商店NPC")
    print("   - potion_icon.jpg 背包药品图标")
    print("   - potion_shop.jpg 商店药品图标")
    print("   - buy_button.jpg  购买按钮")
    print("   - confirm_button.jpg 确认按钮")
"""
游戏自动化模块
=============
完整的游戏挂机自动化流程：
1. 窗口绑定 + 盟重省起点检测
2. 人物状态与地图位置检测（找图）
3. 找传送员NPC → 点击传送 → 地图一致性校验
4. F5 启动挂机
5. 背包满自动回收
6. 药品不足回城购买
7. A* 寻路防卡怪
"""

__version__ = "1.0.0"

from .config import AutomationConfig, TaskConfig
from .detector import GameDetector
from .navigator import GameNavigator
from .inventory import InventoryManager
from .engine import AutomationEngine

__all__ = [
    "AutomationConfig",
    "TaskConfig",
    "GameDetector",
    "GameNavigator",
    "InventoryManager",
    "AutomationEngine",
]
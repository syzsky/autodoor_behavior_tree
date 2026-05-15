"""
自动化配置
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class TaskConfig:
    """单个任务配置"""
    name: str = "挂机任务"
    target_map: str = ""           # 目标地图名称
    target_map_image: str = ""     # 目标地图的截图模板路径（用于地图一致性校验）
    npc_name: str = "传送员"       # 传送员NPC名称
    npc_image: str = ""            # NPC截图模板路径
    min_level: int = 0             # 最低等级要求
    potion_threshold: int = 5      # 药品数量低于此值回城
    auto_recycle: bool = True      # 背包满自动回收
    recycle_key: str = ""          # 回收快捷键
    start_hotkey: str = "F5"       # 启动挂机快捷键
    timeout: int = 300             # 任务超时秒数
    teleport_button_image: str = ""  # 传送按钮截图模板路径
    map_list_image: str = ""       # 地图列表截图模板路径


@dataclass
class AutomationConfig:
    """自动化引擎配置"""
    # 窗口
    window_title: str = ""         # 游戏窗口标题
    window_match_mode: str = "title"  # title / class / hwnd

    # 起点（盟重省）
    home_map: str = "盟重省"
    home_map_image: str = ""       # 盟重省地图截图模板

    # 检测
    detect_interval: float = 1.0   # 检测间隔（秒）
    screenshot_region: Optional[List[int]] = None  # 截图区域 [x,y,w,h]

    # 找图匹配
    match_threshold: float = 0.8   # 模板匹配阈值
    match_method: str = "cv2.TM_CCOEFF_NORMED"

    # A* 寻路
    astar_enabled: bool = True
    astar_grid_size: int = 32      # 网格像素大小
    astar_max_steps: int = 50      # 最大寻路步数
    stuck_timeout: float = 10.0    # 卡住检测超时（秒）

    # 背包
    recycle_button_image: str = ""  # 回收按钮截图模板
    recycle_confirm_image: str = "" # 回收确认按钮截图模板
    potion_image: str = ""         # 药品图标截图模板
    shop_npc_image: str = ""       # 商店NPC截图模板
    buy_button_image: str = ""     # 购买按钮截图模板
    confirm_button_image: str = "" # 确认按钮截图模板
    inventory_full_indicator: str = ""  # 背包满提示图标模板
    home_hotkey: str = "V"         # 回城快捷键
    hp_roi: list = None            # 血量检测区域 [x,y,w,h]
    mp_roi: list = None            # 蓝量检测区域 [x,y,w,h]

    # 任务列表
    tasks: List[TaskConfig] = field(default_factory=list)

    # 调试
    debug_mode: bool = False
    screenshot_dir: str = "./data/game_automation/screenshots"
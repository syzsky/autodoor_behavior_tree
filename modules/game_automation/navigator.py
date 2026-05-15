"""
导航模块
=======
功能：
  - 找传送员NPC → 点击传送
  - 地图一致性校验
  - A* 寻路防卡怪
  - 回城导航
"""

import time
import math
from typing import Optional, List, Tuple, Callable
from pathlib import Path

import cv2
import numpy as np


class AStarPathfinder:
    """
    A* 寻路算法
    
    用法：
        pf = AStarPathfinder(grid_size=32)
        path = pf.find_path(start=(100, 200), end=(500, 300), obstacles=[])
    """

    def __init__(self, grid_size: int = 32):
        self.grid_size = grid_size

    def _to_grid(self, x: int, y: int) -> Tuple[int, int]:
        """像素坐标转网格坐标"""
        return (x // self.grid_size, y // self.grid_size)

    def _to_pixel(self, gx: int, gy: int) -> Tuple[int, int]:
        """网格坐标转像素坐标"""
        return (gx * self.grid_size + self.grid_size // 2,
                gy * self.grid_size + self.grid_size // 2)

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """曼哈顿距离估算"""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _get_neighbors(self, pos: Tuple[int, int], grid_w: int, grid_h: int,
                       obstacles: set) -> List[Tuple[int, int]]:
        """获取相邻可达网格"""
        x, y = pos
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < grid_w and 0 <= ny < grid_h:
                if (nx, ny) not in obstacles:
                    neighbors.append((nx, ny))
        return neighbors

    def find_path(self, start: Tuple[int, int], end: Tuple[int, int],
                  obstacles: Optional[List[Tuple[int, int]]] = None,
                  map_size: Tuple[int, int] = (1920, 1080)) -> List[Tuple[int, int]]:
        """
        A* 寻路
        
        Args:
            start: 起点像素坐标 (x, y)
            end: 终点像素坐标 (x, y)
            obstacles: 障碍物网格坐标列表
            map_size: 地图像素大小 (w, h)
            
        Returns:
            像素坐标路径列表
        """
        grid_w = map_size[0] // self.grid_size
        grid_h = map_size[1] // self.grid_size
        obstacle_set = set(obstacles or [])

        start_g = self._to_grid(*start)
        end_g = self._to_grid(*end)

        # 边界检查
        if not (0 <= start_g[0] < grid_w and 0 <= start_g[1] < grid_h):
            return []
        if not (0 <= end_g[0] < grid_w and 0 <= end_g[1] < grid_h):
            return []

        # A* 算法
        open_set = {start_g}
        came_from = {}
        g_score = {start_g: 0}
        f_score = {start_g: self._heuristic(start_g, end_g)}

        while open_set:
            current = min(open_set, key=lambda p: f_score.get(p, float('inf')))

            if current == end_g:
                # 重建路径
                path = []
                while current in came_from:
                    path.append(self._to_pixel(*current))
                    current = came_from[current]
                path.append(self._to_pixel(*start_g))
                path.reverse()
                return path

            open_set.remove(current)

            for neighbor in self._get_neighbors(current, grid_w, grid_h, obstacle_set):
                tentative_g = g_score[current] + (
                    1 if neighbor[0] == current[0] or neighbor[1] == current[1]
                    else 1.414  # 对角线移动
                )

                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, end_g)
                    if neighbor not in open_set:
                        open_set.add(neighbor)

        return []  # 无路可达


class GameNavigator:
    """
    游戏导航器
    
    用法：
        nav = GameNavigator(detector, input_controller)
        nav.goto_map("猪洞七层")
        nav.find_and_click_npc("传送员")
        nav.navigate_to((500, 300))
    """

    def __init__(self, detector, input_controller):
        self._detector = detector
        self._input = input_controller
        self._astar = AStarPathfinder()
        self._last_npc_pos = None
        self._npc_click_count = 0

    # ── NPC 交互 ─────────────────────────────────

    def find_and_click_npc(self, npc_template, max_attempts: int = 5,
                           click_offset: Tuple[int, int] = (0, 0)) -> bool:
        """
        找到NPC并点击
        
        Args:
            npc_template: NPC截图模板
            max_attempts: 最大尝试次数
            click_offset: 点击偏移量
            
        Returns:
            是否成功点击
        """
        for attempt in range(max_attempts):
            frame = self._detector.capture_frame()
            if frame is None:
                time.sleep(1)
                continue

            result = self._detector.find_npc(npc_template, frame)
            if result.found:
                click_x = result.center_x + click_offset[0]
                click_y = result.center_y + click_offset[1]
                self._input.click(click_x, click_y)
                self._last_npc_pos = (click_x, click_y)
                self._npc_click_count += 1
                return True

            time.sleep(1)

        return False

    def click_dialog_option(self, option_image, max_attempts: int = 3) -> bool:
        """点击对话框选项"""
        for _ in range(max_attempts):
            frame = self._detector.capture_frame()
            if frame is None:
                time.sleep(1)
                continue

            result = self._detector.find_template(frame, option_image, threshold=0.7)
            if result.found:
                self._input.click(result.center_x, result.center_y)
                time.sleep(0.5)
                return True

            time.sleep(1)
        return False

    # ── 地图传送 ─────────────────────────────────

    def goto_map(self, target_map_name: str,
                 npc_template,
                 map_list_template,
                 map_dialog_template) -> bool:
        """
        通过NPC传送到目标地图
        
        流程：
            1. 找到传送员NPC并点击
            2. 等待对话框弹出
            3. 在地图列表中找目标地图并点击
            4. 点击确认传送
            5. 等待传送完成
            
        Args:
            target_map_name: 目标地图名称
            npc_template: 传送员NPC模板
            map_list_template: 地图列表模板（用于滚动找目标）
            map_dialog_template: 传送确认对话框模板
            
        Returns:
            是否传送成功
        """
        # Step 1: 找NPC
        if not self.find_and_click_npc(npc_template):
            return False

        time.sleep(1.5)  # 等待对话框

        # Step 2: 在地图列表中找目标
        for _ in range(5):  # 尝试滚动
            frame = self._detector.capture_frame()
            if frame is None:
                continue

            result = self._detector.find_template(frame, map_list_template, threshold=0.6)
            if result.found:
                self._input.click(result.center_x, result.center_y)
                time.sleep(0.5)
                break
            else:
                # 滚动列表
                self._input.scroll(-3)
                time.sleep(0.5)

        # Step 3: 确认传送
        if map_dialog_template is not None:
            if not self.click_dialog_option(map_dialog_template):
                # 尝试按 Enter
                self._input.press_key("enter")
                time.sleep(0.5)

        # Step 4: 等待传送完成
        time.sleep(3)
        return True

    def go_home(self, home_map_template, home_npc_template=None) -> bool:
        """
        回城（盟重省）
        
        Args:
            home_map_template: 盟重省地图模板（用于确认已回城）
            home_npc_template: 回城NPC模板（可选）
        """
        # 尝试使用回城卷/技能
        self._input.press_key("V")  # 假设V是回城快捷键
        time.sleep(3)

        # 检测是否回到盟重省
        frame = self._detector.capture_frame()
        if frame is None:
            return False

        result = self._detector.find_template(frame, home_map_template, threshold=0.6)
        return result.found

    # ── A* 寻路 ─────────────────────────────────

    def navigate_to(self, target_pos: Tuple[int, int],
                    get_obstacles: Optional[Callable] = None,
                    step_callback: Optional[Callable] = None,
                    map_size: Tuple[int, int] = (1920, 1080),
                    max_steps: int = 50) -> bool:
        """
        A* 寻路到目标位置
        
        Args:
            target_pos: 目标像素坐标
            get_obstacles: 获取障碍物的回调函数
            step_callback: 每步回调
            map_size: 地图大小
            max_steps: 最大步数
            
        Returns:
            是否到达目标
        """
        # 获取当前玩家位置（通过画面检测）
        current_pos = self._get_player_position()
        if current_pos is None:
            return False

        # 获取障碍物
        obstacles = get_obstacles() if get_obstacles else []

        # A* 寻路
        path = self._astar.find_path(
            start=current_pos,
            end=target_pos,
            obstacles=obstacles,
            map_size=map_size,
        )

        if not path:
            return False  # 无路可达

        # 沿路径移动
        steps = min(len(path), max_steps)
        for i in range(steps):
            px, py = path[i]

            # 点击移动
            self._input.click(px, py)
            time.sleep(0.5)

            if step_callback:
                step_callback(i, steps, px, py)

        return True

    def navigate_away_from_stuck(self, frame: np.ndarray) -> bool:
        """
        卡怪时随机走动
        
        Args:
            frame: 当前画面帧
            
        Returns:
            是否已移动
        """
        h, w = frame.shape[:2]
        import random
        # 随机方向点击
        target_x = random.randint(w // 4, 3 * w // 4)
        target_y = random.randint(h // 4, 3 * h // 4)
        self._input.click(target_x, target_y)
        time.sleep(1)
        return True

    def _get_player_position(self) -> Optional[Tuple[int, int]]:
        """
        获取玩家当前位置
        
        注：实际游戏中需要从小地图或角色位置识别，
        这里使用画面中心作为近似
        """
        frame = self._detector.capture_frame()
        if frame is None:
            return None

        h, w = frame.shape[:2]
        return (w // 2, h // 2)

    # ── 地图一致性校验 ──────────────────────────

    def verify_map(self, target_map_name: str,
                   templates_dir: str = "./templates/maps",
                   max_retries: int = 3) -> bool:
        """
        校验当前是否在目标地图
        
        Args:
            target_map_name: 目标地图名
            templates_dir: 地图模板目录
            max_retries: 最大重试次数
            
        Returns:
            是否在目标地图
        """
        for _ in range(max_retries):
            map_name, _ = self._detector.detect_map(templates_dir=templates_dir)
            if map_name == target_map_name:
                return True
            time.sleep(1)
        return False
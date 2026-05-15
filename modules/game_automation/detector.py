"""
画面检测模块
===========
功能：
  - 窗口截图与区域截图
  - 地图识别（模板匹配）
  - NPC 找图与点击
  - 人物状态检测（血量/蓝量/等级）
  - 背包状态检测
  - 卡怪检测
"""

import os
import time
import threading
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class DetectionResult:
    """检测结果"""
    found: bool = False
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    confidence: float = 0.0
    center_x: int = 0
    center_y: int = 0


class GameDetector:
    """
    游戏画面检测器
    
    用法：
        detector = GameDetector(capture)
        # 检测地图
        map_name = detector.detect_map(templates_dir="./templates/maps")
        # 找NPC
        npc_pos = detector.find_npc("传送员", npc_template)
        # 检测血量
        hp_pct = detector.detect_hp(roi=(10, 10, 200, 20))
    """

    def __init__(self, capture, config=None):
        self._capture = capture
        self._config = config or {}
        self._screenshot_dir = Path(self._config.get("screenshot_dir", "./data/game_automation/screenshots"))
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

        # 缓存
        self._last_frame = None
        self._last_frame_time = 0
        self._frame_lock = threading.Lock()

    # ── 截图 ─────────────────────────────────────

    def capture_frame(self, region: Optional[List[int]] = None) -> Optional[np.ndarray]:
        """捕获当前帧（可选区域）"""
        frame = self._capture.capture() if self._capture else None
        if frame is None:
            return None

        if region:
            x, y, w, h = region
            h_frame, w_frame = frame.shape[:2]
            x = max(0, min(x, w_frame - 1))
            y = max(0, min(y, h_frame - 1))
            w = min(w, w_frame - x)
            h = min(h, h_frame - y)
            frame = frame[y:y+h, x:x+w]

        with self._frame_lock:
            self._last_frame = frame
            self._last_frame_time = time.time()

        return frame

    def save_debug_screenshot(self, name: str, frame: Optional[np.ndarray] = None) -> str:
        """保存调试截图"""
        if frame is None:
            frame = self._last_frame
        if frame is None:
            return ""

        path = str(self._screenshot_dir / f"{name}_{int(time.time())}.jpg")
        cv2.imwrite(path, frame)
        return path

    # ── 模板匹配（找图） ─────────────────────────

    def find_template(self, frame: np.ndarray, template: np.ndarray,
                      threshold: float = 0.8) -> DetectionResult:
        """
        在画面中找模板图
        
        Args:
            frame: 待搜索的画面
            template: 模板图片
            threshold: 匹配阈值 0~1
            
        Returns:
            DetectionResult
        """
        if frame is None or template is None:
            return DetectionResult()

        # 灰度化
        if len(frame.shape) == 3:
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray_frame = frame
        if len(template.shape) == 3:
            gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            gray_template = template

        # 多尺度匹配（处理缩放）
        h, w = gray_template.shape
        best_match = DetectionResult()

        for scale in np.linspace(0.8, 1.2, 5):
            scaled = cv2.resize(gray_template, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_LINEAR)
            if scaled.shape[0] > gray_frame.shape[0] or scaled.shape[1] > gray_frame.shape[1]:
                continue

            result = cv2.matchTemplate(gray_frame, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_match.confidence and max_val >= threshold:
                sh, sw = scaled.shape
                best_match = DetectionResult(
                    found=True,
                    x=max_loc[0],
                    y=max_loc[1],
                    w=sw,
                    h=sh,
                    confidence=float(max_val),
                    center_x=max_loc[0] + sw // 2,
                    center_y=max_loc[1] + sh // 2,
                )

        return best_match

    def find_all_templates(self, frame: np.ndarray, template: np.ndarray,
                           threshold: float = 0.8) -> List[DetectionResult]:
        """找所有匹配的模板（多个NPC等）"""
        if frame is None or template is None:
            return []

        if len(frame.shape) == 3:
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray_frame = frame
        if len(template.shape) == 3:
            gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            gray_template = template

        result = cv2.matchTemplate(gray_frame, gray_template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        matches = []

        for pt in zip(*locations[::-1]):
            matches.append(DetectionResult(
                found=True,
                x=pt[0],
                y=pt[1],
                w=template.shape[1],
                h=template.shape[0],
                confidence=float(result[pt[1], pt[0]]),
                center_x=pt[0] + template.shape[1] // 2,
                center_y=pt[1] + template.shape[0] // 2,
            ))

        # 去重（NMS）
        return self._nms(matches, overlap_threshold=0.3)

    def _nms(self, boxes: List[DetectionResult],
             overlap_threshold: float = 0.3) -> List[DetectionResult]:
        """非极大值抑制去重"""
        if not boxes:
            return []

        boxes_sorted = sorted(boxes, key=lambda b: b.confidence, reverse=True)
        result = []

        for box in boxes_sorted:
            keep = True
            for kept in result:
                # 计算 IoU
                x1 = max(box.x, kept.x)
                y1 = max(box.y, kept.y)
                x2 = min(box.x + box.w, kept.x + kept.w)
                y2 = min(box.y + box.h, kept.y + kept.h)
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                area1 = box.w * box.h
                area2 = kept.w * kept.h
                iou = inter / min(area1, area2) if min(area1, area2) > 0 else 0
                if iou > overlap_threshold:
                    keep = False
                    break
            if keep:
                result.append(box)

        return result

    # ── 地图检测 ─────────────────────────────────

    def detect_map(self, frame: Optional[np.ndarray] = None,
                   templates_dir: str = "./templates/maps") -> Tuple[Optional[str], DetectionResult]:
        """
        检测当前地图
        
        Args:
            frame: 画面帧
            templates_dir: 地图模板目录（每个模板文件名=地图名.jpg）
            
        Returns:
            (地图名称, 检测结果)
        """
        frame = frame or self.capture_frame()
        if frame is None:
            return None, DetectionResult()

        templates_dir = Path(templates_dir)
        if not templates_dir.exists():
            return None, DetectionResult()

        best_match = DetectionResult()
        best_map = None

        for template_path in templates_dir.glob("*.jpg"):
            template = cv2.imread(str(template_path))
            if template is None:
                continue

            result = self.find_template(frame, template, threshold=0.6)
            if result.found and result.confidence > best_match.confidence:
                best_match = result
                best_map = template_path.stem  # 文件名 = 地图名

        return best_map, best_match

    def is_map_match(self, target_map_name: str, frame: Optional[np.ndarray] = None,
                     templates_dir: str = "./templates/maps") -> bool:
        """检测当前是否在目标地图"""
        map_name, _ = self.detect_map(frame, templates_dir)
        return map_name == target_map_name

    # ── NPC 检测 ─────────────────────────────────

    def find_npc(self, npc_template: np.ndarray,
                 frame: Optional[np.ndarray] = None,
                 threshold: float = 0.7) -> DetectionResult:
        """
        找NPC
        
        Args:
            npc_template: NPC截图模板
            frame: 画面帧
            threshold: 匹配阈值
            
        Returns:
            NPC位置
        """
        frame = frame or self.capture_frame()
        if frame is None or npc_template is None:
            return DetectionResult()
        return self.find_template(frame, npc_template, threshold)

    # ── 状态检测 ─────────────────────────────────

    def detect_hp(self, frame: Optional[np.ndarray] = None,
                  roi: Optional[List[int]] = None,
                  color_range: Tuple[int, int] = (0, 50)) -> float:
        """
        检测血量百分比（通过血条颜色区域）
        
        Args:
            frame: 画面帧
            roi: 血条区域 [x, y, w, h]
            color_range: 红色/绿色范围
            
        Returns:
            血量百分比 0~1
        """
        frame = frame or self.capture_frame()
        if frame is None:
            return 0.0

        if roi:
            x, y, w, h = roi
            roi_frame = frame[y:y+h, x:x+w]
        else:
            roi_frame = frame

        if roi_frame.size == 0:
            return 0.0

        # 假设血条是红色区域
        hsv = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2HSV)
        # 红色范围
        lower_red = np.array([0, 100, 100])
        upper_red = np.array([10, 255, 255])
        mask_red = cv2.inRange(hsv, lower_red, upper_red)

        # 绿色范围（也可能是血条颜色）
        lower_green = np.array([40, 100, 100])
        upper_green = np.array([80, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)

        mask = cv2.bitwise_or(mask_red, mask_green)
        total_pixels = roi_frame.shape[0] * roi_frame.shape[1]
        filled_pixels = cv2.countNonZero(mask)

        return filled_pixels / max(total_pixels, 1)

    def detect_mp(self, frame: Optional[np.ndarray] = None,
                  roi: Optional[List[int]] = None) -> float:
        """检测蓝量百分比"""
        frame = frame or self.capture_frame()
        if frame is None:
            return 0.0

        if roi:
            x, y, w, h = roi
            roi_frame = frame[y:y+h, x:x+w]
        else:
            roi_frame = frame

        if roi_frame.size == 0:
            return 0.0

        hsv = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2HSV)
        # 蓝色范围
        lower_blue = np.array([100, 100, 100])
        upper_blue = np.array([130, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)

        total_pixels = roi_frame.shape[0] * roi_frame.shape[1]
        filled_pixels = cv2.countNonZero(mask)
        return filled_pixels / max(total_pixels, 1)

    def detect_level(self, frame=None, roi=None):
        try:
            import pytesseract
            frame = frame or self.capture_frame()
            if frame is None:
                return None
            if roi:
                x, y, w, h = roi
                roi_frame = frame[y:y+h, x:x+w]
            else:
                roi_frame = frame
            gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            text = pytesseract.image_to_string(thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789')
            return int(text.strip()) if text.strip().isdigit() else None
        except ImportError:
            # 回退：尝试用模板匹配数字
            return self._detect_level_by_template(frame, roi)
        except Exception:
            return None

    def _detect_level_by_template(self, frame=None, roi=None):
        """用模板匹配方式检测等级（回退方案）"""
        return None  # 需要用户提供数字模板

    # ── 背包检测 ─────────────────────────────────

    def detect_inventory_full(self, frame: Optional[np.ndarray] = None,
                              full_indicator_template: Optional[np.ndarray] = None,
                              full_indicator_roi: Optional[List[int]] = None) -> bool:
        """
        检测背包是否满
        
        Args:
            frame: 画面帧
            full_indicator_template: 背包满提示图标模板（优先使用模板匹配）
            full_indicator_roi: 背包满的提示区域（回退方案）
        """
        frame = frame or self.capture_frame()
        if frame is None:
            return False

        # 优先使用模板匹配
        if full_indicator_template is not None:
            result = self.find_template(frame, full_indicator_template, threshold=0.6)
            return result.found

        # 回退：使用ROI亮度检测
        if full_indicator_roi:
            x, y, w, h = full_indicator_roi
            roi = frame[y:y+h, x:x+w]
            if roi.size == 0:
                return False
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            mean_brightness = np.mean(gray)
            return mean_brightness > 200  # 亮色提示

        return False

    def detect_potion_count(self, potion_template: np.ndarray,
                            frame: Optional[np.ndarray] = None,
                            inventory_roi: Optional[List[int]] = None) -> int:
        """
        检测背包中药品数量
        
        Args:
            potion_template: 药品图标模板
            frame: 画面帧
            inventory_roi: 背包区域
            
        Returns:
            药品数量
        """
        frame = frame or self.capture_frame()
        if frame is None or potion_template is None:
            return 0

        if inventory_roi:
            x, y, w, h = inventory_roi
            frame = frame[y:y+h, x:x+w]

        matches = self.find_all_templates(frame, potion_template, threshold=0.7)
        return len(matches)

    # ── 卡怪检测 ─────────────────────────────────

    def detect_stuck(self, reference_frame: np.ndarray,
                     current_frame: np.ndarray,
                     threshold: float = 0.95) -> bool:
        """
        检测是否卡怪（画面长时间几乎不变）
        
        Args:
            reference_frame: 参考帧（之前的画面）
            current_frame: 当前帧
            threshold: 相似度阈值
            
        Returns:
            是否卡住
        """
        if reference_frame is None or current_frame is None:
            return False

        # 计算结构相似度
        try:
            from skimage.metrics import structural_similarity as ssim
            gray_ref = cv2.cvtColor(reference_frame, cv2.COLOR_BGR2GRAY)
            gray_cur = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)

            h = min(gray_ref.shape[0], gray_cur.shape[0])
            w = min(gray_ref.shape[1], gray_cur.shape[1])
            gray_ref = gray_ref[:h, :w]
            gray_cur = gray_cur[:h, :w]

            score = ssim(gray_ref, gray_cur)
            return score > threshold
        except ImportError:
            # 使用均方误差
            h = min(reference_frame.shape[0], current_frame.shape[0])
            w = min(reference_frame.shape[1], current_frame.shape[1])
            diff = cv2.absdiff(reference_frame[:h, :w], current_frame[:h, :w])
            mse = np.mean(diff ** 2)
            return mse < 10.0  # 差异极小 = 卡住
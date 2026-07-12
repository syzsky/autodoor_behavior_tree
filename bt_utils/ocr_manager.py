from rapidocr import RapidOCR
from PIL import Image, ImageEnhance, ImageFilter
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from collections import OrderedDict
import numpy as np
import re
import time
import hashlib
import threading
import cv2
import logging
from bt_utils.singleton import singleton

_logger = logging.getLogger(__name__)


@dataclass
class ImageFeatures:
    """图像特征分析结果"""
    
    width: int
    height: int
    min_dimension: int
    mean_brightness: float
    brightness_std: float
    contrast: float
    is_low_contrast: bool
    noise_level: float
    has_noise: bool
    estimated_char_height: int
    is_small_font: bool
    is_dark_background: bool
    has_gradient: bool


class ImageFeatureAnalyzer:
    """图像特征分析器"""
    
    LOW_CONTRAST_THRESHOLD = 0.3
    NOISE_THRESHOLD = 0.5
    DARK_BACKGROUND_THRESHOLD = 128
    SMALL_FONT_HEIGHT_THRESHOLD = 15
    DEFAULT_CHAR_HEIGHT = 20
    MIN_CONTOUR_HEIGHT = 5
    GRADIENT_EDGE_DENSITY_THRESHOLD = 0.05
    GRADIENT_BRIGHTNESS_STD_THRESHOLD = 30
    CANNY_LOW_THRESHOLD = 50
    CANNY_HIGH_THRESHOLD = 150
    
    def analyze(self, image: Image.Image) -> ImageFeatures:
        """分析图像特征
        
        Args:
            image: 原始图像
            
        Returns:
            图像特征分析结果
        """
        img_array = np.array(image)
        
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array.copy()
        
        height, width = gray.shape
        min_dimension = min(width, height)
        
        mean_brightness = float(np.mean(gray))
        brightness_std = float(np.std(gray))
        
        min_val = float(np.min(gray))
        max_val = float(np.max(gray))
        contrast = (max_val - min_val) / (max_val + min_val + 1e-6)
        is_low_contrast = contrast < self.LOW_CONTRAST_THRESHOLD
        
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        noise_level = float(laplacian.var() / 10000)
        has_noise = noise_level > self.NOISE_THRESHOLD
        
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            heights = [cv2.boundingRect(c)[3] for c in contours if cv2.boundingRect(c)[3] > self.MIN_CONTOUR_HEIGHT]
            estimated_char_height = int(np.median(heights)) if heights else self.DEFAULT_CHAR_HEIGHT
        else:
            estimated_char_height = self.DEFAULT_CHAR_HEIGHT
        
        is_small_font = estimated_char_height < self.SMALL_FONT_HEIGHT_THRESHOLD
        
        is_dark_background = mean_brightness < self.DARK_BACKGROUND_THRESHOLD
        
        edges = cv2.Canny(gray, self.CANNY_LOW_THRESHOLD, self.CANNY_HIGH_THRESHOLD)
        edge_density = float(np.sum(edges > 0)) / (width * height)
        has_gradient = edge_density < self.GRADIENT_EDGE_DENSITY_THRESHOLD and brightness_std > self.GRADIENT_BRIGHTNESS_STD_THRESHOLD
        
        return ImageFeatures(
            width=width,
            height=height,
            min_dimension=min_dimension,
            mean_brightness=mean_brightness,
            brightness_std=brightness_std,
            contrast=contrast,
            is_low_contrast=is_low_contrast,
            noise_level=noise_level,
            has_noise=has_noise,
            estimated_char_height=estimated_char_height,
            is_small_font=is_small_font,
            is_dark_background=is_dark_background,
            has_gradient=has_gradient
        )


class SmartScaleStrategy:
    """智能放大策略"""
    
    TARGET_CHAR_HEIGHT = 15
    MAX_SCALE_FACTOR = 4.0
    SAFE_MIN_SIDE_LEN = 800
    
    def calculate_scale_factor(self, features: ImageFeatures) -> float:
        """计算安全的放大倍数
        
        Args:
            features: 图像特征
            
        Returns:
            安全的放大倍数
        """
        if not features.is_small_font:
            return 1.0
        
        char_based_scale = self.TARGET_CHAR_HEIGHT / features.estimated_char_height
        scale_factor = min(char_based_scale, self.MAX_SCALE_FACTOR)
        
        return scale_factor
    
    def scale_image(self, image: Image.Image, 
                    scale_factor: float) -> Image.Image:
        """放大图像
        
        Args:
            image: 原始图像
            scale_factor: 放大倍数
            
        Returns:
            放大后的图像
        """
        if scale_factor <= 1.0:
            return image
        
        new_size = (
            int(image.size[0] * scale_factor),
            int(image.size[1] * scale_factor)
        )
        
        return image.resize(new_size, Image.LANCZOS)


@dataclass
class PreprocessConfig:
    """预处理配置参数"""

    scale_factor: float = 1.0
    denoise_enabled: bool = True
    denoise_method: str = "median"
    denoise_kernel_size: int = 3
    contrast_enabled: bool = True
    contrast_method: str = "simple"
    contrast_factor: float = 2.0
    clahe_clip_limit: float = 2.0
    sharpness_enabled: bool = True
    sharpness_factor: float = 2.0
    sharpness_iterations: int = 2
    binarization_method: str = "fixed"
    binarization_threshold: int = 130
    binarization_block_size: int = 11
    binarization_c: int = 2
    morphology_enabled: bool = False
    morphology_method: str = "close"
    morphology_kernel_size: int = 1

    @classmethod
    def chinese(cls, scale_factor: float = 1.0) -> 'PreprocessConfig':
        """中文/游戏界面预处理配置

        流程：智能放大→中值滤波→灰度→对比度增强→锐化→二值化
        等价于原 _preprocess_chinese
        """
        return cls(
            scale_factor=scale_factor,
            denoise_enabled=True,
            denoise_method="median",
            denoise_kernel_size=3,
            contrast_enabled=True,
            contrast_method="simple",
            contrast_factor=2.5,
            sharpness_enabled=True,
            sharpness_factor=2.0,
            sharpness_iterations=2,
            binarization_method="fixed",
            binarization_threshold=130,
        )

    @classmethod
    def standard(cls) -> 'PreprocessConfig':
        """标准预处理配置

        流程：灰度→对比度增强→锐化→二值化
        等价于原 _preprocess_standard
        """
        return cls(
            scale_factor=1.0,
            denoise_enabled=False,
            contrast_enabled=True,
            contrast_method="simple",
            contrast_factor=1.5,
            sharpness_enabled=True,
            sharpness_factor=1.5,
            sharpness_iterations=1,
            binarization_method="fixed",
            binarization_threshold=128,
        )

    @classmethod
    def adaptive(cls) -> 'PreprocessConfig':
        """自适应预处理配置

        流程：灰度→CLAHE对比度增强→自适应二值化
        等价于原 _preprocess_adaptive
        """
        return cls(
            scale_factor=1.0,
            denoise_enabled=False,
            contrast_enabled=True,
            contrast_method="clahe",
            clahe_clip_limit=2.0,
            sharpness_enabled=False,
            binarization_method="adaptive",
            binarization_block_size=11,
            binarization_c=2,
        )


class AutoConfigSelector:
    """自动配置选择器"""
    
    def __init__(self):
        self._analyzer = ImageFeatureAnalyzer()
        self._scale_strategy = SmartScaleStrategy()
    
    def select_config(self, image: Image.Image) -> PreprocessConfig:
        """自动选择最佳预处理配置
        
        Args:
            image: 原始图像
            
        Returns:
            最佳预处理配置
        """
        features = self._analyzer.analyze(image)
        config = PreprocessConfig()
        
        config.scale_factor = self._scale_strategy.calculate_scale_factor(features)
        
        # 按优先级处理：低优先级先执行，高优先级后执行覆盖
        # 优先级：噪点 > 低对比度 > 深色背景 > 渐变背景 > 小字体
        
        if features.is_small_font:
            config.sharpness_factor = 2.5
            config.sharpness_iterations = 3
            config.denoise_method = "bilateral"
        
        if features.has_gradient:
            config.contrast_method = "clahe"
            config.clahe_clip_limit = 2.5
            config.binarization_method = "adaptive"
        
        if features.is_dark_background:
            config.contrast_factor = 3.0
            config.binarization_method = "adaptive"
        
        if features.is_low_contrast:
            config.contrast_method = "clahe"
            config.clahe_clip_limit = 3.0
            config.binarization_method = "adaptive"
            config.binarization_block_size = 15
            config.binarization_c = 3
        
        if features.has_noise:
            config.denoise_enabled = True
            config.denoise_method = "median"
            config.denoise_kernel_size = 5
        
        return config


class PreprocessExecutor:
    """预处理执行器"""
    
    def __init__(self):
        self._scale_strategy = SmartScaleStrategy()
    
    def execute(self, image: Image.Image, 
                config: PreprocessConfig) -> Image.Image:
        """执行预处理
        
        Args:
            image: 原始图像
            config: 预处理配置
            
        Returns:
            预处理后的图像
        """
        if config.scale_factor > 1.0:
            image = self._scale_strategy.scale_image(image, config.scale_factor)
        
        img_array = np.array(image)
        
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array.copy()
        
        if config.denoise_enabled:
            if config.denoise_method == "median":
                gray = cv2.medianBlur(gray, config.denoise_kernel_size)
            elif config.denoise_method == "gaussian":
                gray = cv2.GaussianBlur(gray, (config.denoise_kernel_size,) * 2, 0)
            elif config.denoise_method == "bilateral":
                gray = cv2.bilateralFilter(gray, 9, 75, 75)
        
        if config.contrast_enabled:
            if config.contrast_method == "clahe":
                clahe = cv2.createCLAHE(
                    clipLimit=config.clahe_clip_limit,
                    tileGridSize=(8, 8)
                )
                gray = clahe.apply(gray)
            else:
                pil_image = Image.fromarray(gray)
                enhancer = ImageEnhance.Contrast(pil_image)
                pil_image = enhancer.enhance(config.contrast_factor)
                gray = np.array(pil_image)
        
        if config.sharpness_enabled:
            pil_image = Image.fromarray(gray)
            for _ in range(config.sharpness_iterations):
                pil_image = ImageEnhance.Sharpness(pil_image).enhance(config.sharpness_factor)
            gray = np.array(pil_image)

        if config.binarization_method == "adaptive":
            gray = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, config.binarization_block_size, config.binarization_c
            )
        elif config.binarization_method == "otsu":
            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, gray = cv2.threshold(gray, config.binarization_threshold, 255, cv2.THRESH_BINARY)

        if config.morphology_enabled and config.morphology_kernel_size > 1:
            kernel = np.ones((config.morphology_kernel_size, config.morphology_kernel_size), np.uint8)
            if config.morphology_method == "close":
                gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            elif config.morphology_method == "open":
                gray = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
            elif config.morphology_method == "dilate":
                gray = cv2.dilate(gray, kernel)
            elif config.morphology_method == "erode":
                gray = cv2.erode(gray, kernel)

        return Image.fromarray(gray)


CHAR_WIDTH_FACTORS = {
    'chinese': 2.0,
    'fullwidth': 2.0,
    'uppercase': 1.2,
    'lowercase': 1.0,
    'digit': 1.0,
    'space': 0.5,
    'punctuation': 0.6,
    'other': 1.0,
}


def get_char_width_factor(char: str) -> float:
    """获取字符宽度系数
    
    Args:
        char: 单个字符
        
    Returns:
        字符宽度系数
    """
    if '\u4e00' <= char <= '\u9fff':
        return CHAR_WIDTH_FACTORS['chinese']
    
    if '\uff00' <= char <= '\uffef':
        return CHAR_WIDTH_FACTORS['fullwidth']
    
    if char.isupper():
        return CHAR_WIDTH_FACTORS['uppercase']
    
    if char.islower():
        return CHAR_WIDTH_FACTORS['lowercase']
    
    if char.isdigit():
        return CHAR_WIDTH_FACTORS['digit']
    
    if char.isspace():
        return CHAR_WIDTH_FACTORS['space']
    
    if char in '.,;:!?\'"()[]{}<>@#$%^&*-+=_|\\/`~':
        return CHAR_WIDTH_FACTORS['punctuation']
    
    return CHAR_WIDTH_FACTORS['other']


def calculate_keyword_position(text: str, keyword: str, 
                               box: np.ndarray) -> Tuple[int, int]:
    """基于字符实际宽度精确计算关键词位置
    
    Args:
        text: 完整文本
        keyword: 关键词
        box: 文本框坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        
    Returns:
        关键词中心坐标 (x, y)
    """
    keyword_idx = text.lower().find(keyword.lower())
    if keyword_idx == -1:
        center_x = int((box[0][0] + box[2][0]) / 2)
        center_y = int((box[0][1] + box[2][1]) / 2)
        return (center_x, center_y)
    
    char_widths = [get_char_width_factor(char) for char in text]
    total_width = sum(char_widths)
    
    start_width = sum(char_widths[:keyword_idx])
    
    keyword_widths = [get_char_width_factor(char) for char in keyword]
    keyword_width = sum(keyword_widths)
    
    center_width = start_width + keyword_width / 2
    center_ratio = center_width / total_width
    
    box_left = box[0][0]
    box_right = box[2][0]
    box_top = box[0][1]
    box_bottom = box[2][1]
    box_width = box_right - box_left
    box_height = box_bottom - box_top
    
    x = int(box_left + box_width * center_ratio)
    y = int(box_top + box_height / 2)
    
    return (x, y)


class LRUCache:
    """线程安全的 LRU 缓存，支持 TTL 过期和 O(1) 淘汰"""

    def __init__(self, max_size: int = 200, ttl: float = 3.0):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存结果

        Args:
            key: 缓存键

        Returns:
            缓存的结果，未命中或过期返回 None
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() - entry['time'] < self._ttl:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return entry['result']
                del self._cache[key]
            self._misses += 1
        return None

    def set(self, key: str, result: Any):
        """设置缓存结果

        Args:
            key: 缓存键
            result: 结果
        """
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = {'result': result, 'time': time.time()}
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)  # O(1) 淘汰最旧

    def clear(self):
        """清空缓存和统计"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl": self._ttl,
            }


@singleton
class OCRManager:
    """OCR管理器

    封装RapidOCR功能，提供文字识别和数字识别。
    支持图像预处理和多语言识别。
    使用单例模式，线程安全。
    带结果缓存机制，避免重复识别。
    """
    _engine: Optional[RapidOCR] = None
    _available: bool = True
    _unavailable_reason: str = ""

    CHINESE_LANGS = {"chi_sim", "chi_tra"}

    DEFAULT_CACHE_TTL = 3.0
    MAX_CACHE_SIZE = 200

    def __init__(self):
        if not self._available:
            return

        self._cache = LRUCache(max_size=self.MAX_CACHE_SIZE, ttl=self.DEFAULT_CACHE_TTL)
        self._auto_config_selector = AutoConfigSelector()
        self._preprocess_executor = PreprocessExecutor()

        try:
            self._engine = RapidOCR(
                params={
                    "Det.limit_side_len": 736,
                    "Det.limit_type": "max"
                }
            )
            
            if self._engine is None:
                raise RuntimeError("RapidOCR 引擎创建失败，返回 None")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._engine = None
            OCRManager._available = False
            OCRManager._unavailable_reason = str(e)

    @classmethod
    def initialize(cls):
        """初始化OCR引擎（在应用启动时调用）"""
        return cls()

    @classmethod
    def instance(cls):
        """获取OCRManager单例实例"""
        return cls()

    @classmethod
    def set_unavailable(cls, reason: str):
        """设置OCR不可用
        
        Args:
            reason: 不可用原因
        """
        cls._available = False
        cls._unavailable_reason = reason

    @classmethod
    def is_available(cls) -> bool:
        """检查OCR是否可用
        
        Returns:
            是否可用
        """
        return cls._available

    @classmethod
    def get_unavailable_reason(cls) -> str:
        """获取OCR不可用原因
        
        Returns:
            不可用原因
        """
        return cls._unavailable_reason

    def _compute_cache_key(self, image: Image.Image, **kwargs) -> str:
        """计算缓存键（使用感知哈希替代全图 MD5）

        Args:
            image: PIL图像
            **kwargs: 额外参数

        Returns:
            缓存键字符串
        """
        try:
            import imagehash
            img_hash = str(imagehash.phash(image, hash_size=8))
        except Exception:
            try:
                img_bytes = np.array(image).tobytes()
                img_hash = hashlib.md5(img_bytes).hexdigest()[:16]
            except Exception:
                img_hash = str(id(image))
        
        params_str = str(sorted(kwargs.items()))
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        return f"{img_hash}_{params_hash}"

    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """获取缓存结果

        Args:
            cache_key: 缓存键

        Returns:
            缓存的结果，未命中返回None
        """
        return self._cache.get(cache_key)

    def _set_cached_result(self, cache_key: str, result: Any):
        """设置缓存结果

        Args:
            cache_key: 缓存键
            result: 结果
        """
        self._cache.set(cache_key, result)

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            包含 hits/misses/hit_rate/size 的字典
        """
        return self._cache.get_stats()

    def _preprocess_image(self, image: Image.Image, language: str = "eng",
                          preprocess_mode: str = "normal") -> Image.Image:
        """图像预处理

        Args:
            image: 原始图像
            language: OCR语言 (已废弃，保留参数兼容)
            preprocess_mode: 预处理模式
                - normal: 标准预处理
                - game: 游戏界面预处理（智能放大+增强）
                - adaptive: 自适应预处理
                - auto: 自动调优预处理

        Returns:
            预处理后的图像
        """
        if preprocess_mode == "game":
            features = self._auto_config_selector._analyzer.analyze(image)
            scale_factor = self._auto_config_selector._scale_strategy.calculate_scale_factor(features)
            config = PreprocessConfig.chinese(scale_factor=scale_factor)
        elif preprocess_mode == "adaptive":
            config = PreprocessConfig.adaptive()
        elif preprocess_mode == "auto":
            config = self._auto_config_selector.select_config(image)
        else:
            config = PreprocessConfig.standard()

        return self._preprocess_executor.execute(image, config)

    def recognize_with_boxes(self, image: Image.Image, language: str = "eng",
                             preprocess_mode: str = "normal",
                             use_cache: bool = True) -> Optional[list]:
        """执行OCR识别并返回带文本框的原始结果

        Args:
            image: PIL.Image 图像
            language: OCR语言
            preprocess_mode: 预处理模式
            use_cache: 是否使用缓存

        Returns:
            OCR 结果列表 [(text, box, confidence), ...]，失败返回 None
        """
        try:
            if not self._available or self._engine is None:
                return None

            cache_key = None
            if use_cache:
                cache_key = self._compute_cache_key(
                    image, language=language, preprocess_mode=preprocess_mode,
                    method="recognize_with_boxes"
                )
                cached = self._get_cached_result(cache_key)
                if cached is not None:
                    return cached

            processed = self._preprocess_image(image, language, preprocess_mode)
            img_array = np.array(processed)

            result = self._engine(img_array)
            if result is None or result.boxes is None or len(result.boxes) == 0:
                return None

            boxes_result = []
            for i, text in enumerate(result.txts):
                if text and i < len(result.boxes):
                    confidence = result.scores[i] if result.scores and i < len(result.scores) else 0.0
                    boxes_result.append((text, result.boxes[i], confidence))

            if cache_key:
                self._set_cached_result(cache_key, boxes_result)
            return boxes_result

        except Exception as e:
            _logger.error(f"OCR识别(带位置)异常: {e}", exc_info=True)
            return None

    def recognize(self, image: Image.Image, keywords: str = None,
                  language: str = "eng",
                  preprocess_mode: str = "normal",
                  region: Tuple[int, int, int, int] = None,
                  search_direction: str = "top-left",
                  use_cache: bool = True) -> Tuple[bool, Optional[Tuple[int, int]], str]:
        """执行OCR识别

        Args:
            image: PIL.Image 图像
            keywords: 关键词（逗号分隔）
            language: OCR语言
            preprocess_mode: 预处理模式
            region: 已废弃，保留参数兼容。区域偏移由调用方处理
            search_direction: 识别起点 (top-left/top-right/bottom-left/bottom-right)
            use_cache: 是否使用缓存

        Returns:
            (是否找到, 位置坐标, 所有识别文本) 元组
            注意：位置坐标为相对坐标，不含区域偏移，调用方需自行叠加region偏移
        """
        try:
            if not self._available:
                return False, None, ""
            
            if self._engine is None:
                return False, None, ""
            
            cache_key = None
            if use_cache:
                cache_key = self._compute_cache_key(
                    image, keywords=keywords, language=language,
                    preprocess_mode=preprocess_mode, region=region,
                    search_direction=search_direction
                )
                cached = self._get_cached_result(cache_key)
                if cached is not None:
                    return cached
            
            processed = self._preprocess_image(image, language, preprocess_mode)
            
            img_array = np.array(processed)
            
            result = self._engine(img_array)
            
            if result is None:
                return False, None, ""
            
            if result.boxes is None or len(result.boxes) == 0:
                return False, None, ""
            
            all_text = " ".join(result.txts) if result.txts else ""
            
            if keywords:
                keyword_list = [k.strip().lower() for k in keywords.split(",")]
                
                all_matches = []
                
                for i, text in enumerate(result.txts):
                    if not text:
                        continue
                    
                    text_lower = text.lower()
                    for keyword in keyword_list:
                        keyword_idx = text_lower.find(keyword)
                        
                        if keyword_idx != -1:
                            box = result.boxes[i]
                            
                            x, y = calculate_keyword_position(text, keyword, box)
                            
                            if image.size != processed.size:
                                scale_x = image.size[0] / processed.size[0]
                                scale_y = image.size[1] / processed.size[1]
                                x = int(x * scale_x)
                                y = int(y * scale_y)

                            all_matches.append((x, y))
                
                if all_matches:
                    from bt_utils.direction import sort_positions_by_direction
                    sorted_matches = sort_positions_by_direction(all_matches, search_direction)
                    result_data = (True, sorted_matches[0], all_text)
                    if cache_key:
                        self._set_cached_result(cache_key, result_data)
                    return result_data
                
                result_data = (False, None, all_text)
                if cache_key:
                    self._set_cached_result(cache_key, result_data)
                return result_data
            
            result_data = (True, None, all_text)
            if cache_key:
                self._set_cached_result(cache_key, result_data)
            return result_data
        
        except Exception as e:
            _logger.error(f"OCR识别异常: {e}", exc_info=True)
            return False, None, ""

    def recognize_number(self, image: Image.Image, language: str = "eng",
                         preprocess_mode: str = "normal",
                         extract_mode: str = "无规则",
                         extract_pattern: str = "",
                         min_confidence: float = 0.5) -> Tuple[bool, Optional[float], str]:
        """识别数字

        Args:
            image: PIL.Image 图像
            language: OCR语言
            preprocess_mode: 预处理模式
            extract_mode: 提取模式 (无规则/x/y/自定义)
            extract_pattern: 自定义提取模式（使用*作为通配符）
            min_confidence: 最小置信度 (RapidOCR自动过滤低置信度结果)

        Returns:
            (是否识别成功, 数字值, 所有识别文本) 元组
        """
        result = self.recognize_number_with_position(image, language, preprocess_mode, extract_mode, extract_pattern, min_confidence)
        return result[0], result[1], result[2]
    
    def recognize_number_with_position(self, image: Image.Image, language: str = "eng",
                                        preprocess_mode: str = "normal",
                                        extract_mode: str = "无规则",
                                        extract_pattern: str = "",
                                        min_confidence: float = 0.5,
                                        search_direction: str = "top-left",
                                        use_cache: bool = True) -> Tuple[bool, Optional[float], str, Optional[Tuple[int, int]]]:
        """识别数字（带位置）

        Args:
            image: PIL.Image 图像
            language: OCR语言
            preprocess_mode: 预处理模式
            extract_mode: 提取模式 (无规则/x/y/自定义)
            extract_pattern: 自定义提取模式（使用*作为通配符）
            min_confidence: 最小置信度 (RapidOCR自动过滤低置信度结果)
            search_direction: 识别起点 (top-left/top-right/bottom-left/bottom-right)
            use_cache: 是否使用缓存

        Returns:
            (是否识别成功, 数字值, 所有识别文本, 位置坐标) 元组
        """
        try:
            if not self._available:
                return False, None, "", None
            
            if self._engine is None:
                return False, None, "", None
            
            cache_key = None
            if use_cache:
                cache_key = self._compute_cache_key(
                    image, language=language, preprocess_mode=preprocess_mode,
                    extract_mode=extract_mode, extract_pattern=extract_pattern,
                    min_confidence=min_confidence, method="number",
                    search_direction=search_direction
                )
                cached = self._get_cached_result(cache_key)
                if cached is not None:
                    return cached
            
            processed = self._preprocess_image(image, language, preprocess_mode)
            
            img_array = np.array(processed)
            
            result = self._engine(img_array)
            
            if result is None or result.txts is None or len(result.txts) == 0:
                return False, None, "", None
            
            all_text = " ".join(result.txts)
            
            all_number_data = []
            
            if result.boxes is not None and len(result.boxes) > 0:
                for i, box in enumerate(result.boxes):
                    center_x = int((box[0][0] + box[2][0]) / 2)
                    center_y = int((box[0][1] + box[2][1]) / 2)
                    
                    if image.size != processed.size:
                        scale_x = image.size[0] / processed.size[0]
                        scale_y = image.size[1] / processed.size[1]
                        center_x = int(center_x * scale_x)
                        center_y = int(center_y * scale_y)
                    
                    if result.txts and i < len(result.txts):
                        text = result.txts[i]
                        extracted = self._extract_number(text, extract_mode, extract_pattern)
                        if extracted is not None:
                            all_number_data.append((center_x, center_y, extracted))
            
            if all_number_data:
                from bt_utils.direction import sort_positions_by_direction
                
                positions = [(d[0], d[1]) for d in all_number_data]
                sorted_positions = sort_positions_by_direction(positions, search_direction)
                
                first_pos = sorted_positions[0]
                extracted_value = None
                for x, y, val in all_number_data:
                    if x == first_pos[0] and y == first_pos[1]:
                        extracted_value = val
                        break
                
                result_data = (True, extracted_value, all_text, first_pos)
                if cache_key:
                    self._set_cached_result(cache_key, result_data)
                return result_data
            
            result_data = (False, None, all_text, None)
            if cache_key:
                self._set_cached_result(cache_key, result_data)
            return result_data
        
        except Exception as e:
            _logger.error(f"OCR数字识别异常: {e}", exc_info=True)
            return False, None, "", None

    def _extract_number(self, text: str, extract_mode: str,
                        extract_pattern: str) -> Optional[float]:
        """从文本中提取数字

        Args:
            text: 识别文本
            extract_mode: 提取模式
            extract_pattern: 自定义模式

        Returns:
            提取的数字，失败返回None
        """
        text = text.strip()
        
        if extract_mode == "无规则":
            numbers = re.findall(r'-?\d+\.?\d*', text)
            if numbers:
                try:
                    return float(numbers[0])
                except ValueError:
                    return None
        
        elif extract_mode == "x/y":
            match = re.search(r'(-?\d+\.?\d*)\s*/\s*-?\d+\.?\d*', text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return None
        
        elif extract_mode == "自定义" and extract_pattern:
            pattern_parts = extract_pattern.split('*')
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts
                prefix_idx = text.find(prefix)
                if prefix_idx != -1:
                    remaining = text[prefix_idx + len(prefix):]
                    suffix_idx = remaining.find(suffix) if suffix else len(remaining)
                    if suffix_idx != -1 or not suffix:
                        number_text = remaining[:suffix_idx] if suffix else remaining
                        numbers = re.findall(r'-?\d+\.?\d*', number_text)
                        if numbers:
                            try:
                                return float(numbers[0])
                            except ValueError:
                                return None
        
        return None

    def get_all_text(self, image: Image.Image, language: str = "eng",
                     preprocess_mode: str = "normal",
                     psm: int = None, oem: int = None,
                     use_cache: bool = True) -> str:
        """获取所有识别文本

        返回值使用换行符分隔各文本行，以便调用方按行处理。
        recognize/recognize_number 使用空格分隔，仅用于日志展示。

        Args:
            image: PIL.Image 图像
            language: OCR语言
            preprocess_mode: 预处理模式
            psm: 已废弃
            oem: 已废弃
            use_cache: 是否使用缓存

        Returns:
            识别文本（换行分隔）
        """
        try:
            if not self._available:
                return ""

            if self._engine is None:
                return ""

            cache_key = None
            if use_cache:
                cache_key = self._compute_cache_key(
                    image, language=language, preprocess_mode=preprocess_mode,
                    method="get_all_text"
                )
                cached = self._get_cached_result(cache_key)
                if cached is not None:
                    return cached

            processed = self._preprocess_image(image, language, preprocess_mode)

            img_array = np.array(processed)

            result = self._engine(img_array)

            if result is None or result.txts is None or len(result.txts) == 0:
                return ""

            text = "\n".join(result.txts)

            if cache_key:
                self._set_cached_result(cache_key, text)
            return text

        except Exception as e:
            _logger.error(f"OCR获取文本异常: {e}", exc_info=True)
            return ""

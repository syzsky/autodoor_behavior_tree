from PIL import Image
from typing import Tuple


class ScreenshotManager:
    """截图管理器

    提供全屏和区域截图功能，使用单例模式。
    内部委托给 ScreenService 实现。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_full_screenshot(self) -> Image.Image:
        """获取全屏截图

        Returns:
            PIL.Image 截图对象
        """
        from bt_utils.screen_service import ScreenService
        return ScreenService.capture_screen()

    def get_region_screenshot(self, region: Tuple[int, int, int, int]) -> Image.Image:
        """获取区域截图

        Args:
            region: 截图区域 (left, top, right, bottom)

        Returns:
            PIL.Image 截图对象
        """
        from bt_utils.screen_service import ScreenService
        return ScreenService.capture_screen(region=region)

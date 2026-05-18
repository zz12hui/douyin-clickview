"""浏览器生命周期管理 —— 启动、创建上下文、关闭。"""

import logging
from typing import Optional

from patchright.async_api import async_playwright, Playwright, Browser, BrowserContext

from douyin_clickview.config import AppConfig
from douyin_clickview.browser.stealth import StealthEnhancer

logger = logging.getLogger(__name__)


class BrowserManager:
    """管理 Patchright 浏览器实例。"""

    def __init__(self, config: AppConfig):
        self._config = config
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._persistent = False

    async def launch(self) -> None:
        """启动浏览器。如有 user_data_dir 则使用持久化上下文。"""
        logger.info(
            "启动浏览器 (headless=%s, channel=%s)",
            self._config.headless,
            self._config.browser_channel or "default",
        )
        self._playwright = await async_playwright().start()

        launch_kwargs: dict = {
            "headless": self._config.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
            ],
        }
        if self._config.browser_channel:
            launch_kwargs["channel"] = self._config.browser_channel
        if self._config.proxy:
            launch_kwargs["proxy"] = {"server": self._config.proxy}

        if self._config.user_data_dir:
            # 持久化上下文：直接获得 BrowserContext，cookie/存储持久化
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=self._config.user_data_dir,
                **launch_kwargs,
                **StealthEnhancer.context_kwargs(
                    proxy=self._config.proxy
                ),
            )
            self._context.set_default_timeout(
                int(self._config.navigation_timeout * 1000)
            )
            self._persistent = True
            logger.info("持久化浏览器上下文已创建 (profile: %s)", self._config.user_data_dir)
        else:
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
            logger.info("浏览器已启动")

    async def create_context(self) -> BrowserContext:
        """创建独立的浏览器上下文。持久模式下直接返回已有上下文。"""
        if self._persistent and self._context:
            return self._context

        if not self._browser:
            raise RuntimeError("浏览器尚未启动，请先调用 launch()")

        ctx_kwargs = StealthEnhancer.context_kwargs(
            proxy=self._config.proxy
        )
        ctx_kwargs["viewport"] = {
            "width": self._config.viewport_width,
            "height": self._config.viewport_height,
        }
        ctx_kwargs["device_scale_factor"] = self._config.device_scale_factor

        self._context = await self._browser.new_context(**ctx_kwargs)
        self._context.set_default_timeout(
            int(self._config.navigation_timeout * 1000)
        )
        return self._context

    async def close_context(self, context: BrowserContext) -> None:
        """安全关闭上下文。持久模式下不关闭（复用）。"""
        if self._persistent:
            return
        try:
            await context.close()
        except Exception as e:
            logger.debug("关闭上下文时出错: %s", e)

    async def close(self) -> None:
        """关闭浏览器和 Playwright。"""
        if self._context and not self._persistent:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            await self._browser.close()
            logger.info("浏览器已关闭")
        if self._playwright:
            await self._playwright.stop()

    @property
    def is_ready(self) -> bool:
        if self._persistent and self._context:
            return True
        return self._browser is not None and self._browser.is_connected()

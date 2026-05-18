"""人类行为模拟 —— 无状态的动作函数集合。"""

import random
import asyncio
import logging

from patchright.async_api import Page, TimeoutError as PlaywrightTimeout

from douyin_clickview.errors import CaptchaError, PageStructureError

logger = logging.getLogger(__name__)


class PageActions:
    """在抖音视频页面上模拟人类操作。"""

    # --- 选择器定义（多级备选，应对页面结构变更） ---

    CAPTCHA_INDICATORS = [
        "iframe[src*='captcha']",
        "iframe[src*='verify']",
        "div[class*='captcha']",
        'text=请完成安全验证',
    ]

    VIDEO_SELECTORS = [
        "video",
        "div[class*='xgplayer']",
        "[data-e2e='video-player']",
    ]

    COMMENT_SECTION_SELECTORS = [
        "div[class*='comment']",
        "section[class*='comment']",
    ]

    COMMENT_ITEM_SELECTORS = [
        "[data-e2e='comment-item']",
        "div[class*='comment-item']",
        "div[class*='commentItem']",
    ]

    USER_AVATAR_SELECTORS = [
        "a[class*='avatar']",
        "img[class*='avatar']",
        "[data-e2e='user-avatar']",
    ]

    LOGIN_CLOSE_SELECTORS = [
        # 关闭按钮
        "[aria-label='关闭']",
        "div[class*='close']",
        "span[class*='close']",
        "[class*='close-btn']",
        "svg[class*='close']",
        # 跳过/暂不登录文字
        "text=跳过",
        "text=暂不登录",
        "text=稍后再说",
        "text=以后再说",
        # 取消按钮
        "text=取消",
        'button:has-text("取消")',
    ]

    # --- 动作方法 ---

    @staticmethod
    async def check_for_captcha(page: Page, timeout: float = 1.0) -> bool:
        """检测页面是否有验证码。不再抛出异常，仅返回 True/False。
        抖音的验证 iframe 是浮层，内容已在下方加载，不应因此放弃访问。
        """
        await page.wait_for_timeout(1000)
        for selector in PageActions.CAPTCHA_INDICATORS:
            try:
                el = await page.wait_for_selector(
                    selector, timeout=int(timeout * 1000)
                )
                if el:
                    logger.warning("检测到验证浮层: %s，尝试继续...", selector)
                    return True
            except PlaywrightTimeout:
                continue
        return False

    @staticmethod
    async def dismiss_login_and_popups(page: Page) -> int:
        """自动关闭登录弹窗和各类遮罩。返回关闭的弹窗数量。"""
        dismissed = 0
        # 先尝试 ESC 键
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except Exception:
            pass
        for selector in PageActions.LOGIN_CLOSE_SELECTORS:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    try:
                        await el.click(delay=50)
                    except Exception:
                        await el.dispatch_event("click")
                    logger.debug("已关闭弹窗: %s", selector)
                    dismissed += 1
                    await asyncio.sleep(0.2)
            except Exception:
                continue
        return dismissed

    @staticmethod
    async def random_delay(
        page: Page, min_s: float = 0.8, max_s: float = 2.5
    ) -> None:
        """在页面上下文中等待一段随机时长。"""
        delay = random.uniform(min_s, max_s)
        await page.wait_for_timeout(int(delay * 1000))

    @staticmethod
    async def navigate_to_video(
        page: Page, url: str, timeout: float = 45.0
    ) -> None:
        """导航到视频页面并等待内容稳定。"""
        logger.debug("导航到: %s", url)
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=int(timeout * 1000),
        )
        # 短暂等待让页面渲染
        await page.wait_for_timeout(3000)
        await PageActions.check_for_captcha(page)

    @staticmethod
    async def wait_for_video_container(
        page: Page, timeout: float = 8.0
    ) -> bool:
        """等待视频元素出现。超时返回 False。"""
        for selector in PageActions.VIDEO_SELECTORS:
            try:
                await page.wait_for_selector(
                    selector, state="visible", timeout=int(timeout * 1000)
                )
                logger.debug("视频元素出现: %s", selector)
                return True
            except PlaywrightTimeout:
                continue
        return False

    @staticmethod
    async def micro_interactions(
        page: Page, duration_seconds: float
    ) -> None:
        """在观看期间执行微小的类人交互（微滚动、轻触）。"""
        elapsed = 0.0
        while elapsed < duration_seconds:
            chunk = random.uniform(0.8, 2.0)
            await page.wait_for_timeout(int(chunk * 1000))
            elapsed += chunk

            # 偶尔微滚动
            if random.random() < 0.3:
                await page.evaluate(
                    f"window.scrollBy(0, {random.randint(-20, 30)})"
                )

            # 偶尔点击
            if random.random() < 0.15:
                await page.mouse.click(
                    random.randint(100, 300),
                    random.randint(200, 600),
                )

    @staticmethod
    async def scroll_to_comments(page: Page) -> bool:
        """分步滚动到评论区。"""
        for _ in range(random.randint(2, 4)):
            amount = random.randint(200, 500)
            await page.evaluate(f"window.scrollBy(0, {amount})")
            await PageActions.random_delay(page, 0.3, 0.8)
        return True

    @staticmethod
    async def click_random_comment(page: Page) -> bool:
        """找到并随机点击一条可见评论。"""
        for selector in PageActions.COMMENT_ITEM_SELECTORS:
            try:
                items = await page.query_selector_all(selector)
                if items:
                    target = random.choice(items)
                    await target.click(delay=random.randint(50, 200))
                    await PageActions.random_delay(page, 1.0, 2.0)
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    async def view_user_profile(page: Page) -> bool:
        """点击用户头像进入主页，短暂浏览后返回。"""
        for selector in PageActions.USER_AVATAR_SELECTORS:
            try:
                avatar = await page.wait_for_selector(
                    selector, timeout=3000
                )
                if avatar:
                    await avatar.click(delay=random.randint(50, 150))
                    await PageActions.random_delay(page, 1.5, 3.0)
                    await page.go_back(wait_until="domcontentloaded")
                    await PageActions.random_delay(page, 0.5, 1.5)
                    return True
            except (PlaywrightTimeout, Exception):
                continue
        return False

    @staticmethod
    async def simulate_next_video(page: Page) -> None:
        """模拟手指上滑切换到下一个视频。"""
        viewport = await page.evaluate(
            "({width: window.innerWidth, height: window.innerHeight})"
        )
        center_x = viewport["width"] / 2
        start_y = viewport["height"] * 0.7
        end_y = viewport["height"] * 0.2

        # 多步平滑滑动
        await page.mouse.move(center_x, start_y)
        await page.mouse.down()
        steps = 5
        for i in range(1, steps + 1):
            y = start_y + (end_y - start_y) * (i / steps)
            await page.mouse.move(center_x, int(y))
            await asyncio.sleep(0.05)
        await page.mouse.up()
        await PageActions.random_delay(page, 1.0, 2.0)

    # --- 图文 (note) 动作 ---

    NOTE_CONTAINER_SELECTORS = [
        "div[class*='note-detail-container']",
        "img[src*='douyinpic']",
        "img[class*='slide']",
        "div[class*='swiper']",
    ]

    @staticmethod
    async def wait_for_note_container(
        page: Page, timeout: float = 3.0
    ) -> bool:
        """等待图文容器出现。使用 attached 而非 visible（登录浮层可能遮挡）。"""
        for selector in PageActions.NOTE_CONTAINER_SELECTORS:
            try:
                await page.wait_for_selector(
                    selector, state="attached", timeout=int(timeout * 1000)
                )
                logger.debug("图文元素出现: %s", selector)
                return True
            except PlaywrightTimeout:
                continue
        return False

    @staticmethod
    async def swipe_image_left(page: Page) -> None:
        """模拟鼠标左滑，切换到下一张图片。"""
        viewport = await page.evaluate(
            "({width: window.innerWidth, height: window.innerHeight})"
        )
        center_y = viewport["height"] / 2
        start_x = viewport["width"] * 0.7
        end_x = viewport["width"] * 0.2

        await page.mouse.move(start_x, center_y)
        await page.mouse.down()
        steps = 5
        for i in range(1, steps + 1):
            x = start_x + (end_x - start_x) * (i / steps)
            await page.mouse.move(int(x), int(center_y))
            await asyncio.sleep(0.05)
        await page.mouse.up()
        await PageActions.random_delay(page, 0.5, 1.5)

    @staticmethod
    async def browse_images(
        page: Page, duration_seconds: float
    ) -> None:
        """浏览图文：观看首图后随机左滑若干次。"""
        # 先观看首图
        await page.wait_for_timeout(int(duration_seconds * 1000))
        # 随机左滑 1-5 次
        swipes = random.randint(1, 5)
        for _ in range(swipes):
            await PageActions.swipe_image_left(page)
            # 每张图片观看一段随机时间
            delay = random.uniform(1.0, max(1.5, duration_seconds))
            await page.wait_for_timeout(int(delay * 1000))
        logger.debug("图文浏览完成: %d 次滑动", swipes)

    @staticmethod
    async def close_page(page: Page) -> None:
        """安全关闭页面。"""
        try:
            await page.close()
        except Exception:
            pass

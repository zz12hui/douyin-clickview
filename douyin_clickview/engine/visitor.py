"""单次访问编排器 —— 按顺序执行所有模拟动作。"""

import asyncio
import random
import logging
from datetime import datetime

from patchright.async_api import BrowserContext, TimeoutError as PlaywrightTimeout

from douyin_clickview.config import AppConfig
from douyin_clickview.engine.stats import VisitResult
from douyin_clickview.browser.actions import PageActions
from douyin_clickview.errors import (
    CaptchaError,
    NetworkError,
    RateLimitError,
    PageStructureError,
    BrowserError,
)
from douyin_clickview.url_parser import URLSourceType
from douyin_clickview.utils.helpers import jitter_value

logger = logging.getLogger(__name__)


class SingleVisitor:
    """编排一次完整的抖音视频访问序列。"""

    def __init__(
        self,
        context: BrowserContext,
        config: AppConfig,
        visit_number: int,
        video_url: str,
        source_type: URLSourceType = URLSourceType.FULL_VIDEO,
    ):
        self._context = context
        self._config = config
        self._visit_number = visit_number
        self._video_url = video_url
        self._source_type = source_type
        self._actions_completed: list[str] = []

    async def execute(self) -> VisitResult:
        """执行完整访问并返回结果。

        核心阶段（导航→观看）受 visit_timeout 限制，超时则中止。
        观看后的步骤（评论、主页、滑动）失败不影响 success 判定，
        因为浏览量在 watch 阶段已计入。
        """
        start_time = datetime.now()
        page = None

        try:
            page = await self._context.new_page()

            # --- 核心阶段：导航 + 观看，必须在超时内完成 ---
            is_note = self._source_type == URLSourceType.FULL_NOTE

            async def _core() -> None:
                # 1. 导航到页面
                await PageActions.navigate_to_video(
                    page, self._video_url, self._config.navigation_timeout
                )
                self._record("navigate")

                # 1.5 关闭登录弹窗
                dismissed = await PageActions.dismiss_login_and_popups(page)
                if dismissed > 0:
                    self._record(f"dismiss_login_{dismissed}")

                if is_note:
                    # 2. 等待图文容器
                    found = await PageActions.wait_for_note_container(page)
                    if not found:
                        raise PageStructureError("note container", self._video_url)
                    self._record("wait_note")

                    # 3. 浏览图片（含观看停顿 + 左右滑动）
                    await PageActions.browse_images(
                        page, self._config.watch_seconds
                    )
                    self._record("browse_images")
                else:
                    # 2. 等待视频元素
                    found = await PageActions.wait_for_video_container(page)
                    if not found:
                        raise PageStructureError("video container", self._video_url)
                    self._record("wait_video")

                    # 2.5 再次检查登录弹窗
                    dismissed = await PageActions.dismiss_login_and_popups(page)
                    if dismissed > 0:
                        self._record(f"dismiss_login_{dismissed}")

                    # 3. 观看（含微交互，带随机抖动）
                    jittered = jitter_value(
                        self._config.watch_seconds, self._config.watch_jitter
                    )
                    await PageActions.micro_interactions(page, jittered)
                    self._record("watch")

            await asyncio.wait_for(_core(), timeout=self._config.visit_timeout)

            # --- 非关键阶段：失败不影响 success 判定 ---
            try:
                if self._config.comment_interaction:
                    await PageActions.scroll_to_comments(page)
                    self._record("scroll_comments")
                    await PageActions.random_delay(
                        page, *self._config.action_delay_range
                    )

                    clicked = await PageActions.click_random_comment(page)
                    if clicked:
                        self._record("click_comment")
                        await PageActions.random_delay(
                            page, *self._config.action_delay_range
                        )

                if self._config.profile_interaction:
                    viewed = await PageActions.view_user_profile(page)
                    if viewed:
                        self._record("view_profile")
                        await PageActions.random_delay(
                            page, *self._config.action_delay_range
                        )
            except Exception as e:
                logger.warning(
                    "Visit #%d 互动步骤失败 (不影响浏览量): %s",
                    self._visit_number, e,
                )

            try:
                await PageActions.simulate_next_video(page)
                self._record("swipe_next")
            except Exception as e:
                logger.warning(
                    "Visit #%d swipe_next 失败 (浏览量已计入): %s",
                    self._visit_number, e,
                )

            elapsed = (datetime.now() - start_time).total_seconds()
            return VisitResult(
                visit_number=self._visit_number,
                video_id="",
                success=True,
                duration_seconds=elapsed,
                actions_completed=self._actions_completed,
            )

        except asyncio.TimeoutError:
            return self._failure(
                start_time,
                f"Timeout: visit exceeded {self._config.visit_timeout}s limit",
            )
        except CaptchaError as e:
            return self._failure(start_time, f"CAPTCHA: {e}")
        except (NetworkError, TimeoutError, PlaywrightTimeout) as e:
            return self._failure(start_time, f"Network/Timeout: {e}")
        except RateLimitError as e:
            return self._failure(start_time, f"RateLimit: {e}")
        except PageStructureError as e:
            return self._failure(start_time, f"PageStructure: {e}")
        except BrowserError as e:
            return self._failure(start_time, f"Browser: {e}")
        except Exception as e:
            logger.error("未预期的错误 (visit #%d): %s", self._visit_number, e)
            return self._failure(
                start_time, f"Unexpected: {type(e).__name__}: {e}"
            )
        finally:
            if page:
                await PageActions.close_page(page)

    def _record(self, action: str) -> None:
        self._actions_completed.append(action)

    def _failure(
        self, start_time: datetime, error_str: str
    ) -> VisitResult:
        elapsed = (datetime.now() - start_time).total_seconds()
        return VisitResult(
            visit_number=self._visit_number,
            video_id="",
            success=False,
            duration_seconds=elapsed,
            error=error_str,
            actions_completed=self._actions_completed,
        )

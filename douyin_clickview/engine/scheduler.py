"""任务调度器 —— 管理完整的访问序列（并发）。"""

import random
import asyncio
import logging
from datetime import datetime
from typing import Optional

from douyin_clickview.config import AppConfig
from douyin_clickview.url_parser import ParsedVideoUrl
from douyin_clickview.engine.stats import VisitStatistics, VisitResult
from douyin_clickview.engine.visitor import SingleVisitor
from douyin_clickview.browser.manager import BrowserManager
from douyin_clickview.display.progress import ProgressDisplay

logger = logging.getLogger(__name__)

NON_RETRYABLE = ("PageStructure", "VideoNotFound")


class Scheduler:
    """管理访问调度、重试和进度跟踪（支持并发）。"""

    def __init__(
        self,
        config: AppConfig,
        parsed_url: ParsedVideoUrl,
    ):
        self._config = config
        self._parsed_url = parsed_url
        self._stats = VisitStatistics(total=config.visit_count)
        self._browser_manager = BrowserManager(config)
        self._interrupted = False
        self._stats_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._display: Optional[ProgressDisplay] = None
        self._active_visits: dict[int, str] = {}

    async def run(self) -> VisitStatistics:
        """并发执行所有访问。"""
        self._stats.start_time = datetime.now()

        try:
            await self._browser_manager.launch()
            context = await self._browser_manager.create_context()

            async with ProgressDisplay(
                self._config, self._parsed_url
            ) as display:
                self._display = display
                display.set_concurrency(self._config.concurrency)

                # 初始化所有访问的状态
                for i in range(1, self._config.visit_count + 1):
                    self._active_visits[i] = "PENDING"

                tasks = [
                    self._worker(context, visit_num)
                    for visit_num in range(1, self._config.visit_count + 1)
                ]

                try:
                    await asyncio.gather(*tasks)
                except KeyboardInterrupt:
                    self._interrupted = True
                    logger.info("收到中断信号，取消剩余任务...")
                    for t in tasks:
                        t.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

            await self._browser_manager.close_context(context)

        except KeyboardInterrupt:
            self._interrupted = True
            logger.info("收到中断信号，正在优雅退出...")
        except Exception as e:
            logger.error("致命错误: %s", e)
            raise
        finally:
            self._stats.end_time = datetime.now()
            await self._browser_manager.close()

        return self._stats

    async def _worker(self, context, visit_num: int) -> None:
        """并发 worker：获取信号量后执行一次访问。"""
        if self._interrupted:
            return

        async with self._semaphore:
            if self._interrupted:
                return

            try:
                self._active_visits[visit_num] = "RUNNING"
                self._display.set_current(visit_num, "RUNNING")
                logger.info(
                    "--- Visit #%d/%d ---",
                    visit_num,
                    self._config.visit_count,
                )

                result = await self._execute_with_retry(context, visit_num)

                async with self._stats_lock:
                    self._stats.record_result(result)
                    status = (
                        "SUCCESS"
                        if result.success
                        else f"FAIL: {result.error}"
                    )
                    self._active_visits[visit_num] = status
                    self._display.update(self._stats, self._active_visits)

                self._display.set_current(visit_num, status)
                logger.info(
                    "Visit #%d: %s (%.1fs)",
                    visit_num,
                    "OK" if result.success else f"FAIL",
                    result.duration_seconds,
                )

                if not self._interrupted:
                    wait = random.uniform(*self._config.visit_interval_range)
                    await asyncio.sleep(wait)

            except Exception as e:
                logger.error("Visit #%d 未预期错误: %s", visit_num, e)
                result = VisitResult(
                    visit_number=visit_num,
                    video_id=self._parsed_url.video_id,
                    success=False,
                    duration_seconds=0,
                    error=f"Worker: {type(e).__name__}: {e}",
                )
                async with self._stats_lock:
                    self._stats.record_result(result)
                    self._active_visits[visit_num] = f"FAIL: {result.error}"
                    self._display.update(self._stats, self._active_visits)

    async def _execute_with_retry(
        self,
        context,
        visit_num: int,
    ) -> VisitResult:
        """执行单次访问，带指数退避重试。"""
        last_result: Optional[VisitResult] = None

        for attempt in range(self._config.max_retries):
            visitor = SingleVisitor(
                context=context,
                config=self._config,
                visit_number=visit_num,
                video_url=self._parsed_url.canonical_url,
                source_type=self._parsed_url.source_type,
            )
            result = await visitor.execute()

            if result.success:
                return result

            last_result = result

            # 不可重试的错误
            if result.error and any(
                result.error.startswith(prefix)
                for prefix in NON_RETRYABLE
            ):
                logger.warning(
                    "不可重试错误 (visit #%d): %s", visit_num, result.error
                )
                return result

            # 计算退避
            if attempt < self._config.max_retries - 1:
                delay = (
                    self._config.retry_base_delay * (2 ** attempt)
                    + random.uniform(0, 1.0)
                )
                logger.info(
                    "Visit #%d 第 %d 次失败: %s，%.1fs 后重试...",
                    visit_num, attempt + 1, result.error, delay,
                )
                await asyncio.sleep(delay)

        return last_result or VisitResult(
            visit_number=visit_num,
            video_id=self._parsed_url.video_id,
            success=False,
            duration_seconds=0,
            error="All retries exhausted",
        )

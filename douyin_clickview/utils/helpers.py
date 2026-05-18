"""工具函数：随机延迟、ID验证、指数退避重试。"""

import random
import asyncio
import logging
from typing import Callable, Awaitable, TypeVar, Optional

from douyin_clickview.errors import NetworkError, RateLimitError

logger = logging.getLogger(__name__)
T = TypeVar("T")


def random_delay(min_s: float = 0.5, max_s: float = 2.0) -> float:
    """返回一个随机延迟秒数（均匀分布）。"""
    return random.uniform(min_s, max_s)


def jitter_value(value: float, fraction: float = 0.2) -> float:
    """对基准值施加 ±fraction 的随机抖动。"""
    return value * random.uniform(1.0 - fraction, 1.0 + fraction)


def validate_video_id(vid: str) -> bool:
    """验证是否为有效的 19 位抖音视频 ID。"""
    return bool(vid) and len(vid) == 19 and vid.isdigit()


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """配置结构化日志。"""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
        datefmt="%H:%M:%S",
    )


async def retry_with_backoff(
    coro_factory: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> T:
    """通用指数退避重试包装器。

    Args:
        coro_factory: 零参数异步可调用对象，每次调用返回结果
        max_retries: 最大尝试次数（含首次）
        base_delay: 基础延迟秒数，每次重试翻倍
    Returns:
        调用成功时的结果
    Raises:
        最后一次的异常（如果所有重试均失败）
    """
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return await coro_factory()
        except (NetworkError, RateLimitError, TimeoutError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1.0)
                logger.info(
                    "第 %d 次尝试失败: %s，%.1fs 后重试...",
                    attempt + 1, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                raise
    assert last_exc is not None
    raise last_exc

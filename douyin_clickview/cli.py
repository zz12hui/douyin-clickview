"""CLI 入口 —— 交互式问答 + 主流程编排。"""

import sys
import asyncio
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm
from rich.text import Text

from douyin_clickview import __version__
from douyin_clickview.config import ConfigLoader, AppConfig
from douyin_clickview.url_parser import URLParser
from douyin_clickview.engine.scheduler import Scheduler
from douyin_clickview.display.config_view import show_config
from douyin_clickview.display.report import FinalReport
from douyin_clickview.errors import ClickViewError, URLParseError
from douyin_clickview.utils.helpers import setup_logging

console = Console()


def _print_banner() -> None:
    """打印启动横幅。"""
    banner = Text(
        f"\n  douyin-clickview v{__version__}\n"
        "  抖音视频访问模拟工具\n",
        style="bold cyan",
    )
    console.print(banner)


def _ask_params(argv_url: Optional[str]) -> dict:
    """交互式提问核心参数。返回可构建 AppConfig 的字典。"""
    params: dict = {}

    # 1. 视频链接
    if argv_url:
        console.print(f"  视频链接: [dim]{argv_url}[/dim]")
        params["video_input"] = argv_url
    else:
        params["video_input"] = Prompt.ask(
            "  视频链接", default=""
        )
        if not params["video_input"].strip():
            console.print("[red]错误: 视频链接不能为空[/red]")
            sys.exit(1)

    # 2. 访问次数
    params["visit_count"] = IntPrompt.ask(
        "  访问次数", default=10
    )

    # 3. 观看秒数
    params["watch_seconds"] = FloatPrompt.ask(
        "  观看秒数", default=3.0
    )

    # 4. 并发线程
    params["concurrency"] = IntPrompt.ask(
        "  并发线程", default=2
    )

    # 5. 是否开启评论/主页互动
    if Confirm.ask("  是否开启评论/主页互动?", default=False):
        params["comment_interaction"] = True
        params["profile_interaction"] = True

    console.print()
    return params


def main() -> None:
    """入口函数（支持命令行传入 URL 位置参数）。"""
    argv_url = sys.argv[1] if len(sys.argv) > 1 else None

    _print_banner()

    try:
        params = _ask_params(argv_url)
        asyncio.run(_run(params))
    except URLParseError as e:
        console.print(f"\n[red]链接解析失败: {e}[/red]")
        sys.exit(1)
    except ClickViewError as e:
        console.print(f"\n[red]运行错误: {e}[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消[/yellow]")
        sys.exit(0)


async def _run(params: dict) -> None:
    """异步主流程。"""
    # 1. 构建配置（使用交互参数，不加载配置文件）
    config = AppConfig(**params)

    # 2. 配置日志
    setup_logging(config.log_level, config.log_file)

    # 3. 解析视频链接
    parsed_url = await URLParser.parse(config.video_input)

    # 4. 展示配置
    show_config(config, parsed_url)

    # 5. 执行访问
    scheduler = Scheduler(config, parsed_url)
    stats = await scheduler.run()

    # 6. 输出报告
    console.print(FinalReport.text(stats, parsed_url))

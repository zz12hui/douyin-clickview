"""配置可视化 —— 开始运行前展示当前生效的配置。"""

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from douyin_clickview.config import AppConfig
    from douyin_clickview.url_parser import ParsedVideoUrl


def show_config(config: "AppConfig", video: "ParsedVideoUrl") -> None:
    """使用 rich.Panel 展示核心配置摘要。"""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()

    table.add_row("视频 ID", video.video_id)
    table.add_row("访问次数", str(config.visit_count))
    table.add_row("观看秒数", f"{config.watch_seconds:.0f}s")
    table.add_row("并发线程", str(config.concurrency))
    table.add_row("headless", str(config.headless))
    table.add_row("评论/主页互动", "开" if config.comment_interaction else "关")
    table.add_row("滑动切换视频", "开（默认）")

    console = Console()
    console.print()
    console.print(Panel(table, title="运行配置", border_style="dim"))
    console.print()

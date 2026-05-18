"""Rich 实时终端进度展示 —— 支持并发访问显示（中文）。"""

from typing import TYPE_CHECKING, Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.progress_bar import ProgressBar

if TYPE_CHECKING:
    from douyin_clickview.config import AppConfig
    from douyin_clickview.url_parser import ParsedVideoUrl
    from douyin_clickview.engine.stats import VisitStatistics


class ProgressDisplay:
    """使用 rich.Live 实时刷新终端表格。"""

    def __init__(
        self,
        config: "AppConfig",
        video_info: "ParsedVideoUrl",
    ):
        self._total = config.visit_count
        self._video_info = video_info
        self._output_format = config.output_format
        self._console = Console()
        self._concurrency = config.concurrency
        self._live: Optional[Live] = None
        self._current: dict = {"num": 0, "status": "等待"}

    async def __aenter__(self) -> "ProgressDisplay":
        if self._output_format == "text":
            self._live = Live(
                self._render(),
                console=self._console,
                refresh_per_second=8,
                screen=False,
            )
            self._live.__enter__()
        return self

    async def __aexit__(self, *args) -> None:
        if self._live:
            self._live.__exit__(*args)

    def set_concurrency(self, n: int) -> None:
        self._concurrency = n

    def set_current(self, visit_num: int, status: str) -> None:
        status_map = {
            "INIT": "初始化", "RUNNING": "运行中",
            "SUCCESS": "成功", "PENDING": "等待",
        }
        self._current = {
            "num": visit_num,
            "status": status_map.get(status, status),
        }

    def update(
        self,
        stats: "VisitStatistics",
        active_visits: Optional[dict] = None,
    ) -> None:
        if self._live:
            self._live.update(self._render(stats, active_visits))

    def _render(
        self,
        stats: Optional["VisitStatistics"] = None,
        active_visits: Optional[dict] = None,
    ) -> Table:
        if stats is None:
            from douyin_clickview.engine.stats import VisitStatistics
            stats = VisitStatistics(total=self._total)

        grid = Table.grid(padding=(1, 2))
        grid.add_column(justify="left", style="bold")
        grid.add_column(justify="right")

        title = Text("douyin-clickview", style="bold cyan")
        grid.add_row(title)
        vid_display = self._video_info.video_id[:19]
        grid.add_row(Text(f"视频: {vid_display}", style="dim"))
        grid.add_row(Text("─" * 50, style="dim"))

        pct = stats.completed / max(stats.total, 1)
        bar = ProgressBar(
            total=stats.total,
            completed=stats.completed,
            width=40,
        )
        grid.add_row(Text("进度:", style="bold"), "")
        grid.add_row("", bar)
        grid.add_row(
            "",
            Text(
                f"{stats.completed}/{stats.total}  ({pct * 100:.0f}%)",
                style="dim",
            ),
        )
        grid.add_row(Text("─" * 50, style="dim"))

        inner = Table.grid(padding=(0, 2))
        inner.add_column(justify="left", style="bold")
        inner.add_column(justify="left")
        inner.add_column(justify="left", style="bold")
        inner.add_column(justify="left")

        inner.add_row(
            "总数:", str(stats.total),
            "线程:", str(self._concurrency),
        )
        inner.add_row(
            "已完成:", str(stats.completed),
            "已耗时:", f"{stats.elapsed.total_seconds():.1f}s",
        )
        inner.add_row(
            "剩余:", str(stats.remaining),
            "预计剩余:",
            f"{stats.eta.total_seconds():.1f}s"
            if stats.eta
            else "-",
        )

        elapsed = stats.elapsed.total_seconds()
        rate = f"{stats.completed / elapsed:.2f}次/s" if elapsed > 0 else "-"
        inner.add_row(
            "成功:", f"[green]{stats.successful}[/green]",
            "速率:", f"{rate}",
        )
        inner.add_row(
            "失败:", f"[red]{stats.failed}[/red]",
            "平均耗时:",
            f"{stats.avg_duration:.1f}s"
            if stats.avg_duration
            else "-",
        )

        grid.add_row(inner)

        if active_visits:
            grid.add_row(Text("─" * 50, style="dim"))
            running = [
                f"#{num}:{status[:4]}"
                for num, status in sorted(active_visits.items())
                if status == "RUNNING"
            ]
            if running:
                grid.add_row(
                    Text("活跃: " + " ".join(running), style="yellow")
                )

        if stats.error_counts:
            grid.add_row(Text("─" * 50, style="dim"))
            parts = [
                f"[red]{k}: {v}[/red]"
                for k, v in stats.error_counts.most_common(3)
            ]
            grid.add_row(
                Text("错误: " + " | ".join(parts), style="dim")
            )

        return Table(title=None, show_header=False, border_style="dim")

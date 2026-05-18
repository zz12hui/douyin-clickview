"""最终报告生成器 —— text / JSON 格式（中文）。"""

import json
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from douyin_clickview.engine.stats import VisitStatistics
    from douyin_clickview.url_parser import ParsedVideoUrl


class FinalReport:
    """生成运行结束后的汇总报告。"""

    @staticmethod
    def text(
        stats: "VisitStatistics", video_url: "ParsedVideoUrl"
    ) -> str:
        """生成中文文本报告。"""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan", width=14)
        table.add_column()

        table.add_row("视频 ID", video_url.video_id)
        table.add_row("来源类型", video_url.source_type.value)
        table.add_row("")

        table.add_row("总访问次数", str(stats.total))
        table.add_row("已完成", str(stats.completed))
        table.add_row("成功", f"[green]{stats.successful}[/green]")
        table.add_row("失败", f"[red]{stats.failed}[/red]")
        table.add_row("成功率", f"{stats.success_rate:.1f}%")
        table.add_row("")

        table.add_row("总耗时", f"{stats.elapsed.total_seconds():.1f}s")
        if stats.avg_duration:
            table.add_row("平均耗时", f"{stats.avg_duration:.1f}s/次")

        if stats.error_counts:
            table.add_row("")
            table.add_row("错误分类", "")
            for error_type, count in stats.error_counts.most_common():
                table.add_row("", f"[red]{error_type}: {count} 次[/red]")

        console = Console()
        console.print()
        console.print(Panel(table, title="访问报告", border_style="cyan"))
        return ""

    @staticmethod
    def json_report(
        stats: "VisitStatistics", video_url: "ParsedVideoUrl"
    ) -> str:
        """生成 JSON 格式报告（供程序化消费）。"""
        from douyin_clickview import __version__

        report = {
            "tool": "douyin-clickview",
            "version": __version__,
            "video_id": video_url.video_id,
            "source_type": video_url.source_type.value,
            "canonical_url": video_url.canonical_url,
            "statistics": {
                "total": stats.total,
                "completed": stats.completed,
                "successful": stats.successful,
                "failed": stats.failed,
                "success_rate_pct": round(stats.success_rate, 2),
                "elapsed_seconds": round(
                    stats.elapsed.total_seconds(), 2
                ),
                "avg_duration_seconds": (
                    round(stats.avg_duration, 2)
                    if stats.avg_duration
                    else None
                ),
                "error_counts": dict(stats.error_counts),
            },
            "results": [
                {
                    "visit": r.visit_number,
                    "success": r.success,
                    "duration_seconds": round(r.duration_seconds, 2),
                    "error": r.error,
                    "actions": r.actions_completed,
                }
                for r in stats.results
            ],
        }
        return json.dumps(report, indent=2, ensure_ascii=False)

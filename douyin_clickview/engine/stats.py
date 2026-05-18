"""访问统计数据模型。"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import Counter
from typing import Optional, List


@dataclass
class VisitResult:
    """单次访问的结果。"""

    visit_number: int
    video_id: str
    success: bool
    duration_seconds: float
    error: Optional[str] = None
    actions_completed: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class VisitStatistics:
    """聚合统计信息。"""

    total: int = 0
    completed: int = 0
    successful: int = 0
    failed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_counts: "Counter[str]" = field(default_factory=Counter)
    visit_durations: List[float] = field(default_factory=list)
    results: List[VisitResult] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return self.total - self.completed

    @property
    def elapsed(self) -> timedelta:
        if self.start_time:
            end = self.end_time or datetime.now()
            return end - self.start_time
        return timedelta(0)

    @property
    def eta(self) -> Optional[timedelta]:
        if self.completed > 0 and self.elapsed.total_seconds() > 0:
            avg = self.elapsed.total_seconds() / self.completed
            return timedelta(seconds=avg * self.remaining)
        return None

    @property
    def success_rate(self) -> float:
        if self.completed == 0:
            return 0.0
        return self.successful / self.completed * 100

    @property
    def avg_duration(self) -> Optional[float]:
        if self.visit_durations:
            return sum(self.visit_durations) / len(self.visit_durations)
        return None

    def record_result(self, result: VisitResult) -> None:
        """记录一次访问结果并更新所有计数器。"""
        self.completed += 1
        self.results.append(result)
        if result.success:
            self.successful += 1
        else:
            self.failed += 1
            if result.error:
                category = (
                    result.error.split(":")[0]
                    if ":" in result.error
                    else result.error
                )
                self.error_counts[category] += 1
        if result.duration_seconds > 0:
            self.visit_durations.append(result.duration_seconds)

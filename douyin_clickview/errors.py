"""douyin-clickview 异常层次结构。"""

from typing import Optional


class ClickViewError(Exception):
    """所有工具异常的基类。"""


class URLParseError(ClickViewError):
    """无法解析的抖音链接。"""

    def __init__(self, input_text: str, reason: str = ""):
        self.input_text = input_text
        self.reason = reason
        msg = f"无法解析链接: {input_text[:80]}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class NetworkError(ClickViewError):
    """网络连接问题（超时、DNS、连接拒绝）。"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class CaptchaError(ClickViewError):
    """检测到抖音验证码/WAF 挑战。"""

    def __init__(self, message: str = "检测到验证码或 WAF 安全挑战"):
        super().__init__(message)


class RateLimitError(ClickViewError):
    """触发频率限制 / 429 Too Many Requests。"""

    def __init__(self, retry_after: Optional[float] = None):
        self.retry_after = retry_after
        msg = "触发限流"
        if retry_after:
            msg += f"，建议等待 {retry_after:.0f}s"
        super().__init__(msg)


class PageStructureError(ClickViewError):
    """页面结构变更，选择器无法匹配。"""

    def __init__(self, element: str, url: str = ""):
        self.element = element
        self.url = url
        super().__init__(f"页面元素未找到: {element}")


class BrowserError(ClickViewError):
    """浏览器级别故障（崩溃、上下文损坏）。"""


class VideoNotFoundError(ClickViewError):
    """视频已删除、私密或链接失效。"""

    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(f"视频不存在或已失效: {video_id}")


class ConfigError(ClickViewError):
    """配置无效或缺失。"""


class VisitInterruptedError(ClickViewError):
    """用户中断（Ctrl+C）"""

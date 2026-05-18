"""抖音视频链接解析器 —— 支持 6 种输入格式。"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx

from douyin_clickview.errors import URLParseError, NetworkError
from douyin_clickview.utils.helpers import validate_video_id

logger = logging.getLogger(__name__)

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
    "Mobile/15E148 Safari/604.1"
)


class URLSourceType(Enum):
    SHORT_LINK = "short_link"
    FULL_VIDEO = "full_video"
    SHARE_LINK = "share_link"
    RAW_ID = "raw_id"
    MIXED_TEXT = "mixed_text"
    FULL_NOTE = "full_note"


@dataclass
class ParsedVideoUrl:
    """解析后的视频链接信息。"""

    original_input: str
    video_id: str
    canonical_url: str
    source_type: URLSourceType
    redirect_chain: list[str] = field(default_factory=list)


class URLParser:
    """解析各种格式的抖音视频链接。"""

    SHORT_LINK_RE = re.compile(
        r"https?://v\.douyin\.com/([a-zA-Z0-9_-]+)"
    )
    FULL_VIDEO_RE = re.compile(
        r"https?://(?:www\.)?douyin\.com/video/(\d{19})"
    )
    SHARE_VIDEO_RE = re.compile(
        r"https?://(?:www\.)?iesdouyin\.com/share/video/(\d{19})"
    )
    SHARE_NOTE_RE = re.compile(
        r"https?://(?:www\.)?iesdouyin\.com/share/note/(\d{19})"
    )
    FULL_NOTE_RE = re.compile(
        r"https?://(?:www\.)?douyin\.com/note/(\d{19})"
    )
    RAW_ID_RE = re.compile(r"^(\d{19})$")
    URL_IN_TEXT_RE = re.compile(r"https?://[^\s]+")

    DOUYIN_VIDEO_URL = "https://www.douyin.com/video/{video_id}"
    DOUYIN_NOTE_URL = "https://www.douyin.com/note/{note_id}"

    @staticmethod
    def extract_url_from_text(text: str) -> Optional[str]:
        """从混合文本（中文、emoji、空格）中提取第一条 URL。"""
        match = URLParser.URL_IN_TEXT_RE.search(text)
        if match:
            return match.group(0).rstrip("/")
        return None

    @staticmethod
    async def follow_short_link(short_url: str, timeout: float = 10.0) -> str:
        """跟随 v.douyin.com 短链的 302 重定向，返回最终 URL。"""
        logger.info("跟随短链重定向: %s", short_url)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    short_url,
                    follow_redirects=False,
                    headers={"User-Agent": MOBILE_UA},
                )
                location = response.headers.get("Location")
                if location:
                    if location.startswith("/"):
                        location = f"https://v.douyin.com{location}"
                    logger.debug("短链重定向到: %s", location)

                    if "iesdouyin.com" in location:
                        response2 = await client.get(
                            location,
                            follow_redirects=False,
                            headers={"User-Agent": MOBILE_UA},
                        )
                        loc2 = response2.headers.get("Location")
                        if loc2:
                            return loc2
                    return location
                if "douyin.com/video/" in str(response.url):
                    return str(response.url)
                raise URLParseError(
                    short_url, "短链重定向失败: 未找到 Location 头"
                )
        except httpx.TimeoutException:
            raise NetworkError(f"短链重定向超时: {short_url}")
        except httpx.RequestError as e:
            raise NetworkError(f"短链重定向网络错误: {e}")

    @staticmethod
    def extract_video_id_from_url(url: str) -> Optional[str]:
        """从已知 URL 格式中提取 19 位视频 ID。"""
        for pattern in [URLParser.FULL_VIDEO_RE, URLParser.SHARE_VIDEO_RE]:
            match = pattern.search(url)
            if match:
                vid = match.group(1)
                if validate_video_id(vid):
                    return vid
        return None

    @staticmethod
    def extract_note_id_from_url(url: str) -> Optional[str]:
        """从已知 URL 格式中提取 19 位图文 ID。"""
        for pattern in [URLParser.FULL_NOTE_RE, URLParser.SHARE_NOTE_RE]:
            match = pattern.search(url)
            if match:
                nid = match.group(1)
                if validate_video_id(nid):
                    return nid
        return None

    @classmethod
    async def parse(cls, input_text: str) -> ParsedVideoUrl:
        """完整解析流水线。"""
        cleaned = input_text.strip()

        # 1. 纯 19 位数字
        if cls.RAW_ID_RE.match(cleaned):
            vid = cleaned
            return ParsedVideoUrl(
                original_input=input_text,
                video_id=vid,
                canonical_url=cls.DOUYIN_VIDEO_URL.format(video_id=vid),
                source_type=URLSourceType.RAW_ID,
            )

        # 2. 提取 URL
        url = cls.extract_url_from_text(cleaned)
        if not url:
            raise URLParseError(input_text, "未从输入中找到有效 URL")

        # 3. 短链处理
        short_match = cls.SHORT_LINK_RE.search(url)
        if short_match:
            final_url = await cls.follow_short_link(url)
            vid = cls.extract_video_id_from_url(final_url)
            if vid:
                return ParsedVideoUrl(
                    original_input=input_text,
                    video_id=vid,
                    canonical_url=cls.DOUYIN_VIDEO_URL.format(video_id=vid),
                    source_type=URLSourceType.SHORT_LINK,
                    redirect_chain=[url, final_url],
                )
            nid = cls.extract_note_id_from_url(final_url)
            if nid:
                return ParsedVideoUrl(
                    original_input=input_text,
                    video_id=nid,
                    canonical_url=cls.DOUYIN_NOTE_URL.format(note_id=nid),
                    source_type=URLSourceType.FULL_NOTE,
                    redirect_chain=[url, final_url],
                )
            raise URLParseError(input_text, f"短链重定向后未找到视频或图文ID: {final_url}")

        # 4. 完整视频页 / 分享链接
        vid = cls.extract_video_id_from_url(url)
        if vid:
            src_type = (
                URLSourceType.SHARE_LINK
                if "iesdouyin.com" in url
                else URLSourceType.FULL_VIDEO
            )
            return ParsedVideoUrl(
                original_input=input_text,
                video_id=vid,
                canonical_url=cls.DOUYIN_VIDEO_URL.format(video_id=vid),
                source_type=src_type,
            )

        # 5. 图文页
        nid = cls.extract_note_id_from_url(url)
        if nid:
            return ParsedVideoUrl(
                original_input=input_text,
                video_id=nid,
                canonical_url=cls.DOUYIN_NOTE_URL.format(note_id=nid),
                source_type=URLSourceType.FULL_NOTE,
            )

        raise URLParseError(input_text, f"无法识别的链接格式: {url}")

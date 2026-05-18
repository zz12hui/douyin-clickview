"""URL 解析器测试 —— 覆盖所有输入格式。"""

import pytest

from douyin_clickview.url_parser import URLParser, ParsedVideoUrl, URLSourceType
from douyin_clickview.errors import URLParseError


def test_extract_url_from_plain_text():
    """从包含中文和换行的文本中提取 URL。"""
    text = "复制此链接，打开看看 https://v.douyin.com/abc123/ 太有趣了！"
    result = URLParser.extract_url_from_text(text)
    assert result == "https://v.douyin.com/abc123"


def test_extract_url_from_share_text():
    """从分享口令中提取 URL。"""
    text = (
        "0.05 09/23 III:/ e@B.tE #国庆 https://v.douyin.com/DGHl69ciWp4/"
        " 复制此链接，打开Dou音搜索"
    )
    result = URLParser.extract_url_from_text(text)
    assert "v.douyin.com" in result


def test_extract_url_no_url():
    """无 URL 时返回 None。"""
    assert URLParser.extract_url_from_text("大家好这是视频") is None


def test_extract_video_id_full():
    """从完整 douyin.com/video/ URL 提取 ID。"""
    url = "https://www.douyin.com/video/7456789012345678901"
    vid = URLParser.extract_video_id_from_url(url)
    assert vid == "7456789012345678901"


def test_extract_video_id_share():
    """从 iesdouyin.com/share/video/ URL 提取 ID。"""
    url = "https://www.iesdouyin.com/share/video/7456789012345678901/?region=CN"
    vid = URLParser.extract_video_id_from_url(url)
    assert vid == "7456789012345678901"


def test_extract_video_id_invalid_length():
    """非19位数字不匹配。"""
    assert URLParser.extract_video_id_from_url(
        "https://www.douyin.com/video/12345"
    ) is None


def test_raw_id_pattern():
    """纯19位数字匹配。"""
    assert URLParser.RAW_ID_RE.match("7456789012345678901") is not None
    assert URLParser.RAW_ID_RE.match("12345") is None


@pytest.mark.asyncio
async def test_parse_raw_id():
    """解析纯19位数字。"""
    result = await URLParser.parse("7456789012345678901")
    assert result.source_type == URLSourceType.RAW_ID
    assert result.video_id == "7456789012345678901"
    assert result.canonical_url == (
        "https://www.douyin.com/video/7456789012345678901"
    )


@pytest.mark.asyncio
async def test_parse_full_url():
    """解析完整视频链接。"""
    result = await URLParser.parse(
        "https://www.douyin.com/video/7456789012345678901"
    )
    assert result.source_type == URLSourceType.FULL_VIDEO
    assert result.video_id == "7456789012345678901"


@pytest.mark.asyncio
async def test_parse_invalid():
    """无效输入抛出 URLParseError。"""
    with pytest.raises(URLParseError):
        await URLParser.parse("这不是链接")


@pytest.mark.asyncio
async def test_parse_share_url():
    """解析 iesdouyin.com 分享链接。"""
    result = await URLParser.parse(
        "https://www.iesdouyin.com/share/video/7456789012345678901/?region=CN"
    )
    assert result.source_type in (URLSourceType.SHARE_LINK, URLSourceType.FULL_VIDEO)
    assert result.video_id == "7456789012345678901"


def test_extract_note_id_from_url():
    """从完整 note URL 提取 ID。"""
    nid = URLParser.extract_note_id_from_url(
        "https://www.douyin.com/note/7640767164639278565"
    )
    assert nid == "7640767164639278565"


def test_extract_note_id_from_share():
    """从 iesdouyin share/note URL 提取 ID。"""
    nid = URLParser.extract_note_id_from_url(
        "https://www.iesdouyin.com/share/note/7640767164639278565/?region=CN"
    )
    assert nid == "7640767164639278565"


@pytest.mark.asyncio
async def test_parse_note_url():
    """解析完整图文链接。"""
    result = await URLParser.parse(
        "https://www.douyin.com/note/7640767164639278565"
    )
    assert result.source_type == URLSourceType.FULL_NOTE
    assert result.video_id == "7640767164639278565"
    assert "/note/" in result.canonical_url


@pytest.mark.asyncio
async def test_parse_share_note_url():
    """解析 iesdouyin 分享图文链接。"""
    result = await URLParser.parse(
        "https://www.iesdouyin.com/share/note/7640767164639278565/?region=CN"
    )
    assert result.source_type == URLSourceType.FULL_NOTE
    assert result.video_id == "7640767164639278565"

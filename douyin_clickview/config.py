"""配置管理 —— Pydantic 模型 + 多源加载（CLI > 文件 > 环境变量 > 默认值）。"""

import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """应用配置模型。"""

    # --- 核心参数 ---
    video_input: str = Field(..., description="抖音链接、短链接、分享链接或纯19位ID")
    visit_count: int = Field(
        default=10, ge=1, le=10000, description="模拟访问次数"
    )
    watch_seconds: float = Field(
        default=3.0, ge=0.5, le=300.0, description="每个视频观看秒数"
    )

    # --- 浏览器参数 ---
    headless: bool = Field(default=False, description="无头模式运行浏览器")
    browser_type: Literal["chromium"] = "chromium"
    browser_channel: Optional[str] = Field(
        default=None, description="浏览器通道: chrome/chromium，推荐 chrome"
    )
    user_data_dir: Optional[str] = Field(
        default=None, description="持久化 profile 路径，复用 cookie/登录态"
    )
    viewport_width: int = Field(default=1920, ge=320, le=3840)
    viewport_height: int = Field(default=1080, ge=480, le=2160)
    device_scale_factor: float = Field(default=1.0)
    locale: str = "zh-CN"
    timezone_id: str = "Asia/Shanghai"

    # --- 行为参数 ---
    comment_interaction: bool = Field(
        default=False, description="访问期间点击评论"
    )
    profile_interaction: bool = Field(
        default=False, description="访问期间查看用户主页"
    )
    action_delay_range: list[float] = Field(
        default=[0.8, 2.5],
        description="自动化动作之间的最小/最大延迟（秒）",
    )
    watch_jitter: float = Field(
        default=0.2,
        ge=0.0, le=0.5,
        description="观看时长的随机抖动比例",
    )

    # --- 网络参数 ---
    proxy: Optional[str] = Field(default=None, description="代理URL")
    connect_timeout: float = Field(default=15.0, ge=5.0)
    navigation_timeout: float = Field(default=20.0, ge=10.0)

    # --- 超时控制 ---
    visit_timeout: float = Field(
        default=30.0, ge=5.0, le=300.0,
        description="单次访问总超时秒数，超出则中止并计为失败"
    )

    # --- 重试参数 ---
    max_retries: int = Field(default=1, ge=1, le=10, description="每次访问最大尝试次数（1=不重试）")
    retry_base_delay: float = Field(default=2.0, ge=0.5)

    # --- 间隔 ---
    visit_interval_range: list[float] = Field(
        default=[3.0, 8.0],
        description="每次访问之间的最小/最大间隔（秒）",
    )

    # --- 并发 ---
    concurrency: int = Field(default=2, ge=1, le=20, description="并发访问数")

    # --- 输出 ---
    output_format: Literal["text", "json", "quiet"] = "text"
    log_level: str = "INFO"
    log_file: Optional[str] = None

    @field_validator("action_delay_range", "visit_interval_range")
    @classmethod
    def validate_range(cls, v: list[float]) -> list[float]:
        if len(v) != 2 or v[0] > v[1]:
            raise ValueError("必须为 [min, max] 且 min <= max")
        return v

    @field_validator("video_input")
    @classmethod
    def video_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("video_input 不能为空")
        return v


class ConfigLoader:
    """多源配置加载器。

    优先级（高→低）：
    1. CLI 参数
    2. 配置文件（YAML）
    3. 环境变量（DY_前缀）
    4. Pydantic 默认值
    """

    ENV_PREFIX = "DY_"
    CONFIG_SEARCH_PATHS = [
        "config.yaml",
        "~/.douyin-clickview.yaml",
    ]

    _ENV_MAP = {
        "DY_VIDEO_INPUT": "video_input",
        "DY_VISIT_COUNT": ("visit_count", int),
        "DY_WATCH_SECONDS": ("watch_seconds", float),
        "DY_HEADLESS": ("headless", lambda v: v.lower() in ("1", "true", "yes")),
        "DY_VIEWPORT_WIDTH": ("viewport_width", int),
        "DY_VIEWPORT_HEIGHT": ("viewport_height", int),
        "DY_COMMENT_INTERACTION": (
            "comment_interaction",
            lambda v: v.lower() in ("1", "true", "yes"),
        ),
        "DY_PROFILE_INTERACTION": (
            "profile_interaction",
            lambda v: v.lower() in ("1", "true", "yes"),
        ),
        "DY_PROXY": "proxy",
        "DY_MAX_RETRIES": ("max_retries", int),
        "DY_OUTPUT_FORMAT": "output_format",
        "DY_LOG_LEVEL": "log_level",
        "DY_LOG_FILE": "log_file",
        "DY_CONCURRENCY": ("concurrency", int),
    }

    @classmethod
    def load(
        cls,
        cli_kwargs: Optional[dict] = None,
        config_path: Optional[Path] = None,
    ) -> AppConfig:
        """合并所有配置源并返回 AppConfig 实例。"""
        merged: dict = cls._from_env()
        merged.update(cls._from_config_file(config_path))
        if cli_kwargs:
            merged.update(cls._clean_cli_kwargs(cli_kwargs))
        return AppConfig(**merged)

    @classmethod
    def _from_env(cls) -> dict:
        """从环境变量加载以 DY_ 开头的配置。"""
        result: dict = {}
        for env_key, spec in cls._ENV_MAP.items():
            value = os.environ.get(env_key)
            if value is None:
                continue
            if isinstance(spec, tuple):
                field_name, converter = spec
                try:
                    result[field_name] = converter(value)
                except (ValueError, TypeError):
                    continue
            else:
                result[spec] = value
        return result

    @classmethod
    def _from_config_file(cls, config_path: Optional[Path]) -> dict:
        """加载 YAML 配置文件。"""
        paths = [config_path] if config_path else []
        if not paths:
            paths = [
                Path(p).expanduser() for p in cls.CONFIG_SEARCH_PATHS
            ]
        for path in paths:
            if not path or not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        return {
                            k: v
                            for k, v in data.items()
                            if v is not None
                        }
            except (yaml.YAMLError, OSError):
                continue
        return {}

    @staticmethod
    def _clean_cli_kwargs(kwargs: dict) -> dict:
        """过滤 CLI 参数，转义 kebab-case 为 snake_case。"""
        result: dict = {}
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "no_comment":
                result["comment_interaction"] = not value
            elif key == "no_profile":
                result["profile_interaction"] = not value
            elif key == "count":
                result["visit_count"] = value
            elif key == "watch":
                result["watch_seconds"] = value
            elif key == "max_retries":
                result["max_retries"] = value
            elif key == "config_path":
                continue  # 不是配置字段
            elif not key.startswith("_"):
                result[key] = value
        return result

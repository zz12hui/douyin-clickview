"""浏览器上下文参数 —— 设置 viewport / locale / geolocation 等。
Patchright 在协议层处理反检测（Runtime.enable 隔离、Console API 禁用等），
此模块仅负责非隐身相关的 context 配置。
"""

from typing import Optional


class StealthEnhancer:
    """提供 BrowserContext 的桌面 Chrome 参数。"""

    @staticmethod
    def context_kwargs(proxy: Optional[str] = None) -> dict:
        """返回模拟桌面 Chrome 的 BrowserContext 参数。
        注意：不设置自定义 UA，由 Patchright 使用原生 Chrome UA 以保持指纹一致。
        """
        kwargs: dict = {
            "viewport": {"width": 1920, "height": 1080},
            "device_scale_factor": 1.0,
            "is_mobile": False,
            "has_touch": False,
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
            "geolocation": {"latitude": 39.9042, "longitude": 116.4074},
            "permissions": [],
            "color_scheme": "light",
            "reduced_motion": "no-preference",
        }
        if proxy:
            kwargs["proxy"] = {"server": proxy}
        return kwargs

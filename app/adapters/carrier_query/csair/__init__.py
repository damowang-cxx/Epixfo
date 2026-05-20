"""南方航空（CZ）唐翼货运官网爬虫，移植自 spider/tang 项目。

仅暴露给上层 adapter 使用，不应在其他位置直接 import。
"""

from app.adapters.carrier_query.csair.captcha import CaptchaFailed
from app.adapters.carrier_query.csair.client import AwbAmbiguous, AwbNotFound, query_awb

__all__ = [
    "AwbAmbiguous",
    "AwbNotFound",
    "CaptchaFailed",
    "query_awb",
]

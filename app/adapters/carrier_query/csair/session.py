import re

import requests

AWB_PAGE_URL = "https://tang.csair.com/WebFace/Tang.WebFace.Cargo/AgentAwbBrower.aspx?menuID=1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# TODO: 后续迁移到 CarrierQueryConfig.config_json，由数据库下发
VERIFY_AUTH_HEADER = "dGFuZzp0YW5nMTIz"

_VIEWSTATE_FIELDS = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__VIEWSTATEENCRYPTED")


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
    )
    return s


def fetch_viewstate(session: requests.Session, timeout: int = 20) -> dict[str, str]:
    r = session.get(AWB_PAGE_URL, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    html = r.text

    fields: dict[str, str] = {}
    for name in _VIEWSTATE_FIELDS:
        m = re.search(
            rf'name="{re.escape(name)}"[^>]*value="([^"]*)"',
            html,
        )
        if m:
            fields[name] = m.group(1)

    if "__VIEWSTATE" not in fields:
        raise RuntimeError("无法从首页提取 __VIEWSTATE，页面结构可能已变更")

    return fields

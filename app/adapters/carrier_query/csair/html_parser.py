"""解析运单查询响应 HTML。

四块数据 + 节点状态（按浏览器抓包的真实 HTML 结构）：

1. 订舱信息：table#gvBookInfo（可能多行；订舱号/航程/出发站/到达站/航班号/日期/件数/重量/体积/订舱性质）
2. 运单信息：awbLbl 是空 span，真数据在它后面的 sibling table（运单号/承运人/航程/品名/件数/重量/体积）
3. 货物状态：table#gvCargoState（时间/城市/航班号/状态/件数/重量）
4. 货物组装：table#gvCombine（时间/城市/状态/件数/重量）

节点状态：img0..img4 的 src 文件名约定 -> 末位 0=done, 1=in_progress, 2=pending
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

_MILESTONE_LABELS = ["received", "loaded", "departed", "arrived", "delivered"]
_MILESTONE_IDS = [
    "ctl00_ContentPlaceHolder1_img0",
    "ctl00_ContentPlaceHolder1_img1",
    "ctl00_ContentPlaceHolder1_img2",
    "ctl00_ContentPlaceHolder1_img3",
    "ctl00_ContentPlaceHolder1_img4",
]

_BOOKING_FIELDS = [
    "bookingNo", "route", "fromStation", "toStation",
    "flight", "flightDate", "pieces", "weight", "volume", "bookingType",
]
_AWB_FIELDS = [
    "awbNo", "carrier", "route", "commodity", "totalPieces", "totalWeightKg", "totalVolume",
]
_CARGO_STATE_FIELDS = ["time", "city", "flight", "status", "pieces", "weight"]
_COMBINE_FIELDS = ["time", "city", "status", "pieces", "weight"]

_DATE_CN_RE = re.compile(r"(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}:\d{2}(?::\d{2})?)")


def _text(node: Any) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _normalize_time(value: str) -> str:
    """`2026年05月10日 13:58:55` -> `2026-05-10 13:58:55`；不匹配就原样返回。"""
    if not value:
        return value
    m = _DATE_CN_RE.search(value)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}"
    return value


def _rows_by_position(table: Tag | None, fields: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if table is None:
        return out
    for tr in table.find_all("tr"):
        if tr.find("th"):
            continue
        cells = tr.find_all("td")
        if not cells:
            continue
        values = [_text(c) for c in cells]
        rec: dict[str, str] = {}
        for i, key in enumerate(fields):
            rec[key] = values[i] if i < len(values) else ""
        out.append(rec)
    return out


def _milestone_status_from_src(src: str) -> str:
    """末位 0=完成(绿), 1=进行中(红), 2=未操作(灰)。"""
    if not src:
        return "unknown"
    name = src.rsplit("/", 1)[-1].lower()
    m = re.match(r"^\d{2}(\d)\.gif$", name)
    if not m:
        return "unknown"
    return {"0": "done", "1": "in_progress", "2": "pending"}.get(m.group(1), "unknown")


def _parse_booking(soup: BeautifulSoup) -> list[dict[str, str]]:
    return _rows_by_position(soup.find(id="ctl00_ContentPlaceHolder1_gvBookInfo"), _BOOKING_FIELDS)


def _parse_awb_summary(soup: BeautifulSoup) -> dict[str, str] | None:
    """awbLbl 是空占位 span；真正的数据在它后面紧跟的 sibling table 里。"""
    span = soup.find(id="ctl00_ContentPlaceHolder1_awbLbl")
    if not span:
        return None
    table = span.find_next("table")
    if not table:
        return None
    rows = _rows_by_position(table, _AWB_FIELDS)
    return rows[0] if rows else None


def _parse_cargo_state(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows = _rows_by_position(soup.find(id="ctl00_ContentPlaceHolder1_gvCargoState"), _CARGO_STATE_FIELDS)
    for r in rows:
        r["time"] = _normalize_time(r.get("time", ""))
    return rows


def _parse_combine(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows = _rows_by_position(soup.find(id="ctl00_ContentPlaceHolder1_gvCombine"), _COMBINE_FIELDS)
    for r in rows:
        r["time"] = _normalize_time(r.get("time", ""))
    return rows


def _parse_milestones(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for label, img_id in zip(_MILESTONE_LABELS, _MILESTONE_IDS):
        img = soup.find(id=img_id)
        src = img.get("src", "") if img else ""
        out[label] = {"status": _milestone_status_from_src(src), "src": src}
    return out


def parse_result(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    err_node = soup.find(id="ctl00_ContentPlaceHolder1_lblErrorInfo")
    err_text = _text(err_node)

    return {
        "booking": _parse_booking(soup),
        "awbInfo": _parse_awb_summary(soup),
        "milestones": _parse_milestones(soup),
        "cargoState": _parse_cargo_state(soup),
        "combine": _parse_combine(soup),
        "errorInfo": err_text or None,
    }

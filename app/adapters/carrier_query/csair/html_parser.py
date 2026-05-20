"""解析运单查询响应 HTML。

四块数据 + 节点状态（按浏览器抓包的真实 HTML 结构）：

1. 订舱信息：table#gvBookInfo（可能多行；订舱号/航程/出发站/到达站/航班号/日期/件数/重量/体积/订舱性质）
2. 运单信息：awbLbl 是空 span，真数据在其后的某个 sibling table（运单号/承运人/航程/品名/件数/重量/体积）
3. 货物状态：table#gvCargoState（时间/城市/航班号/状态/件数/重量）
4. 货物组装：table#gvCombine（时间/城市/状态/件数/重量）

节点状态：img0..img4 的 src 文件名约定 -> 末位 0=done, 1=in_progress, 2=pending

解析采用 **header-driven** 策略：读取 `<th>` 表头文本，通过中/英文映射表得到列索引 → 字段名的对应关系，再按列索引取 `<td>`。
这样能同时兼容中文页面和英文页面（南航唐翼货运站点支持中英文切换，列顺序也可能微调）。
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

_DATE_CN_RE = re.compile(r"(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}:\d{2}(?::\d{2})?)")


# ---- 中英文表头 → 标准字段名映射 ----

_AWB_HEADER_MAP: dict[str, str] = {
    "运单号": "awbNo",
    "AWB No": "awbNo",
    "AWB No.": "awbNo",
    "AWB Number": "awbNo",
    "AWBNo": "awbNo",
    "AWB": "awbNo",
    "承运人": "carrier",
    "Carrier": "carrier",
    "航程": "route",
    "Route": "route",
    "Routing": "route",
    "货物品名": "commodity",
    "品名": "commodity",
    "Description": "commodity",
    "Commodity": "commodity",
    "Goods": "commodity",
    "Goods Description": "commodity",
    "总件数": "totalPieces",
    "件数": "totalPieces",
    "Pieces": "totalPieces",
    "Total Pieces": "totalPieces",
    "Pcs": "totalPieces",
    "总重量(KG)": "totalWeightKg",
    "总重量": "totalWeightKg",
    "Weight(KG)": "totalWeightKg",
    "Weight (KG)": "totalWeightKg",
    "Total Weight(KG)": "totalWeightKg",
    "Total Weight (KG)": "totalWeightKg",
    "Weight": "totalWeightKg",
    "Total Weight": "totalWeightKg",
    "总体积": "totalVolume",
    "体积": "totalVolume",
    "Volume": "totalVolume",
    "Total Volume": "totalVolume",
}

_BOOKING_HEADER_MAP: dict[str, str] = {
    "订舱号": "bookingNo",
    "Booking No": "bookingNo",
    "Booking No.": "bookingNo",
    "Booking Number": "bookingNo",
    "BookingNo": "bookingNo",
    "订舱航程": "route",
    "航程": "route",
    "Route": "route",
    "Routing": "route",
    "出发站": "fromStation",
    "From": "fromStation",
    "From Station": "fromStation",
    "Origin": "fromStation",
    "到达站": "toStation",
    "To": "toStation",
    "To Station": "toStation",
    "Destination": "toStation",
    "航班号": "flight",
    "Flight": "flight",
    "Flight No": "flight",
    "Flight No.": "flight",
    "航班日期": "flightDate",
    "Flight Date": "flightDate",
    "Date": "flightDate",
    "件数": "pieces",
    "Pieces": "pieces",
    "Pcs": "pieces",
    "重量": "weight",
    "Weight": "weight",
    "Weight(KG)": "weight",
    "Weight (KG)": "weight",
    "体积": "volume",
    "Volume": "volume",
    "订舱性质": "bookingType",
    "Booking Type": "bookingType",
    "Type": "bookingType",
}

_CARGO_STATE_HEADER_MAP: dict[str, str] = {
    "操作时间": "time",
    "操作时间 (当地时间)": "time",
    "操作时间(当地时间)": "time",
    "时间": "time",
    "Time": "time",
    "Local Time": "time",
    "Operation Time": "time",
    "操作城市": "city",
    "城市": "city",
    "City": "city",
    "Station": "city",
    "航班号": "flight",
    "Flight": "flight",
    "Flight No": "flight",
    "货物状态": "status",
    "状态": "status",
    "Status": "status",
    "Description": "status",
    "件数": "pieces",
    "Pieces": "pieces",
    "Pcs": "pieces",
    "重量": "weight",
    "Weight": "weight",
    "Weight(KG)": "weight",
    "Weight (KG)": "weight",
}

_COMBINE_HEADER_MAP: dict[str, str] = {
    "操作时间": "time",
    "操作时间 当前时区": "time",
    "操作时间(当前时区)": "time",
    "时间": "time",
    "Time": "time",
    "Operation Time": "time",
    "操作城市": "city",
    "城市": "city",
    "City": "city",
    "Station": "city",
    "货物状态": "status",
    "状态": "status",
    "Status": "status",
    "件数": "pieces",
    "Pieces": "pieces",
    "Pcs": "pieces",
    "重量": "weight",
    "Weight": "weight",
    "Weight(KG)": "weight",
    "Weight (KG)": "weight",
}


# ---- 通用工具 ----

def _text(node: Any) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _normalize_header(text: str) -> str:
    """对表头做大小写 / 空白归一，方便和映射表 key 对照。"""
    if not text:
        return ""
    return re.sub(r"\s+", "", text).strip().lower()


def _normalize_time(value: str) -> str:
    """`2026年05月10日 13:58:55` -> `2026-05-10 13:58:55`；不匹配就原样返回。"""
    if not value:
        return value
    m = _DATE_CN_RE.search(value)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}"
    return value


def _build_index_to_key(table: Tag, header_map: dict[str, str]) -> dict[int, str]:
    """把 `<th>` 表头文本 → 标准字段名，返回 column_index → field_key。"""
    normalized_map = {_normalize_header(k): v for k, v in header_map.items()}
    headers = [_text(th) for th in table.find_all("th")]
    out: dict[int, str] = {}
    for i, header in enumerate(headers):
        key = normalized_map.get(_normalize_header(header))
        if key and i not in out:
            out[i] = key
    return out


def _rows_by_header(table: Tag | None, header_map: dict[str, str]) -> list[dict[str, str]]:
    """根据 `<th>` 表头驱动读取每一行 `<td>`，按映射表归一字段名。"""
    if table is None:
        return []
    index_to_key = _build_index_to_key(table, header_map)
    if not index_to_key:
        return []
    out: list[dict[str, str]] = []
    for tr in table.find_all("tr"):
        if tr.find("th"):
            continue
        cells = tr.find_all("td")
        if not cells:
            continue
        rec: dict[str, str] = {}
        for i, cell in enumerate(cells):
            key = index_to_key.get(i)
            if key:
                rec[key] = _text(cell)
        if rec:
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


# ---- 各分区解析 ----

def _parse_booking(soup: BeautifulSoup) -> list[dict[str, str]]:
    table = soup.find(id="ctl00_ContentPlaceHolder1_gvBookInfo")
    return _rows_by_header(table, _BOOKING_HEADER_MAP)


def _table_matches_awb_summary(table: Tag) -> bool:
    """根据表头判断是否运单摘要表：必须同时出现 `运单号 / AWB` 与 `承运人 / Carrier`。"""
    headers = {_normalize_header(_text(th)) for th in table.find_all("th")}
    has_awb = bool(headers & {"运单号", "awbno", "awbno.", "awbnumber", "awb"})
    has_carrier = bool(headers & {"承运人", "carrier"})
    return has_awb and has_carrier


def _find_awb_summary_table(soup: BeautifulSoup) -> Tag | None:
    # 优先：awbLbl span 之后的第一张匹配表
    span = soup.find(id="ctl00_ContentPlaceHolder1_awbLbl")
    if span:
        candidate = span.find_next("table")
        while candidate is not None:
            if _table_matches_awb_summary(candidate):
                return candidate
            candidate = candidate.find_next("table")
    # 兜底：全文档扫一遍
    for table in soup.find_all("table"):
        if _table_matches_awb_summary(table):
            return table
    return None


def _parse_awb_summary(soup: BeautifulSoup) -> dict[str, str] | None:
    table = _find_awb_summary_table(soup)
    if table is None:
        return None
    rows = _rows_by_header(table, _AWB_HEADER_MAP)
    return rows[0] if rows else None


def _parse_cargo_state(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows = _rows_by_header(soup.find(id="ctl00_ContentPlaceHolder1_gvCargoState"), _CARGO_STATE_HEADER_MAP)
    for r in rows:
        r["time"] = _normalize_time(r.get("time", ""))
    return rows


def _parse_combine(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows = _rows_by_header(soup.find(id="ctl00_ContentPlaceHolder1_gvCombine"), _COMBINE_HEADER_MAP)
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

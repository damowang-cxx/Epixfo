"""南方航空航班动态查询（NewActiveFlightQuery.aspx）。

给定 `航班号 + 起飞日期`，返回该航班对应航段的精确时间表：
- 起飞时间：计划 / 实际
- 到达时间：计划 / 实际

与运单查询（AgentAwbBrower.aspx）同站点 / 同 session / 同款滑块验证码，因此可以
复用 [session.py](session.py) 的 `build_session` / `fetch_viewstate` 与
[captcha.py](captcha.py) 的 `pass_captcha`。

返回的 dict 列表（每个航段一行）已经把 HTML 表格里的 `MM-DD HHMM` 拼成 ISO `datetime`，
年份依据 caller 传入的 `flight_date` 推断（含跨日 / 跨年场景）。
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup

from app.adapters.carrier_query.csair.captcha import pass_captcha
from app.adapters.carrier_query.csair.session import ACTIVE_FLIGHT_URL, fetch_viewstate
from app.core.config import settings

logger = logging.getLogger("epixfo.csair.active_flight")

# `MM-DD HHMM` 整体，HHMM 4 位连写
_DATETIME_RE = re.compile(r"^(\d{1,2})-(\d{1,2})\s+(\d{2})(\d{2})$")

# `GdResult` 数据行按列位置（南航 GridView，前 8 列已稳定验证；
# 8 之后的列在不同视图下顺序不一致，本期只关心前 8 列+航班号+航段）：
COL_FLIGHT_NO = 0
COL_LEG = 1
COL_DEP_PLAN = 2
COL_DEP_EST = 3
COL_DEP_ACTUAL = 4
COL_ARR_PLAN = 5
COL_ARR_EST = 6
COL_ARR_ACTUAL = 7
MIN_DATA_COLUMNS = 8


def query_active_flight(
    session: requests.Session,
    flight_no: str,
    flight_date: date,
    dep_station: str | None = None,
    arr_station: str | None = None,
    debug_dir: Any | None = None,
) -> list[dict[str, Any]]:
    """查询某航班在某起飞日期的精确时间表。

    抛出 `CaptchaFailed` / `requests.RequestException` / `RuntimeError`，
    由 caller 决定要不要降级。
    """
    flight_no = (flight_no or "").strip().upper()
    if not flight_no:
        raise ValueError("flight_no is required")

    logger.info("query active flight %s on %s", flight_no, flight_date.isoformat())

    viewstate = fetch_viewstate(session, url=ACTIVE_FLIGHT_URL)
    img_id = pass_captcha(
        session,
        referer_url=ACTIVE_FLIGHT_URL,
        debug_label="active_flight_captcha",
        debug_dir=debug_dir,
    )

    form: dict[str, str] = {
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$btnQuery",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "ctl00$ContentPlaceHolder1$txtFdep": dep_station or "",
        "ctl00$ContentPlaceHolder1$txtFdest": arr_station or "",
        "ctl00$ContentPlaceHolder1$txtFlightNo": flight_no,
        "ctl00$ContentPlaceHolder1$txtFlightDepTime": flight_date.strftime("%Y-%m-%d"),
        "ctl00$ContentPlaceHolder1$selectTime": "00:01-24:00",
        "ctl00$ContentPlaceHolder1$txtImgId": img_id,
    }
    for k in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__VIEWSTATEENCRYPTED"):
        if k in viewstate:
            form[k] = viewstate[k]

    r = session.post(
        ACTIVE_FLIGHT_URL,
        data=form,
        headers={
            "Referer": ACTIVE_FLIGHT_URL,
            "Origin": "https://tang.csair.com",
        },
        timeout=30,
    )
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding

    active_debug_dir = debug_dir or (settings.csair_captcha_debug_dir if settings.csair_captcha_debug else None)
    if active_debug_dir:
        from pathlib import Path

        debug_path = Path(active_debug_dir)
        debug_path.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        (debug_path / f"active_flight_{flight_no}_{flight_date}_{ts}.html").write_text(
            r.text, encoding="utf-8"
        )

    rows = parse_active_flight_result(r.text, flight_date)
    if active_debug_dir:
        from pathlib import Path
        import json

        debug_path = Path(active_debug_dir)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        (debug_path / f"active_flight_{flight_no}_{flight_date}_{ts}.json").write_text(
            json.dumps(
                {
                    "flight_no": flight_no,
                    "flight_date": flight_date.isoformat(),
                    "dep_station": dep_station,
                    "arr_station": arr_station,
                    "row_count": len(rows),
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    logger.info(
        "active_flight_parse flight=%s date=%s rows=%d",
        flight_no,
        flight_date.isoformat(),
        len(rows),
    )
    return rows


def parse_active_flight_result(html: str, dep_date: date) -> list[dict[str, Any]]:
    """解析 GdResult 表的所有数据行，返回结构化 dict 列表。"""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find(id="ctl00_ContentPlaceHolder1_GdResult")
    if table is None:
        return []

    out: list[dict[str, Any]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < MIN_DATA_COLUMNS:
            # 跳过分组背景行（如 `<td colspan="12">客机</td>`）
            continue
        values = [_cell_text(c) for c in cells]

        dep_plan_dt = _compose_datetime(values[COL_DEP_PLAN], dep_date)
        dep_actual_dt = _compose_datetime(values[COL_DEP_ACTUAL], dep_date)
        arr_plan_dt = _compose_datetime(values[COL_ARR_PLAN], dep_date, after=dep_plan_dt)
        arr_actual_dt = _compose_datetime(values[COL_ARR_ACTUAL], dep_date, after=dep_actual_dt)

        out.append(
            {
                "flightNo": values[COL_FLIGHT_NO].strip(),
                "leg": values[COL_LEG].strip(),
                # 输出 ISO 字符串而不是 datetime 对象，方便后续序列化到 raw_response JSONB
                "depPlanTime": _to_iso(dep_plan_dt),
                "depActualTime": _to_iso(dep_actual_dt),
                "arrPlanTime": _to_iso(arr_plan_dt),
                "arrActualTime": _to_iso(arr_actual_dt),
            }
        )
    return out


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    # 用空格分隔，与 cz_parser._datetime 的 "%Y-%m-%d %H:%M:%S" 格式匹配
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _cell_text(cell: Any) -> str:
    """读 td 文本，折叠空白；保留 `MM-DD HHMM` 之间的单个空格。"""
    if cell is None:
        return ""
    text = cell.get_text(" ", strip=True)
    # 折叠多空格成单空格，方便正则
    return re.sub(r"\s+", " ", text).strip()


def _compose_datetime(
    cell_value: str,
    dep_date: date,
    after: datetime | None = None,
) -> datetime | None:
    """`MM-DD HHMM` + 参考起飞日期 -> 完整 datetime。

    年份推断：
    - 默认用 `dep_date.year`
    - 若 (MM, DD) 比起飞日期更早，可能是跨年到达 -> 年份 +1
    - 若传了 `after`（如 arr_plan 不能早于 dep_plan），则继续往后调整年份
    """
    if not cell_value:
        return None
    m = _DATETIME_RE.match(cell_value)
    if not m:
        logger.debug("active flight cell %r does not match MM-DD HHMM pattern", cell_value)
        return None
    month, day, hour, minute = (int(g) for g in m.groups())
    candidate = _safe_datetime(dep_date.year, month, day, hour, minute)
    if candidate is None:
        return None

    # 与参考起飞日推断跨年
    if (month, day) < (dep_date.month, dep_date.day) and (dep_date.month - month) > 6:
        candidate = _safe_datetime(dep_date.year + 1, month, day, hour, minute) or candidate

    # 到达不能早于参考起飞时间，否则视为跨日 / 跨年
    if after is not None and candidate < after:
        candidate = candidate + timedelta(days=1)
        # 跨日后如果仍然早于 after（极端情况），再尝试 +1 年
        if candidate < after:
            candidate = _safe_datetime(candidate.year + 1, candidate.month, candidate.day, candidate.hour, candidate.minute) or candidate

    return candidate


def _safe_datetime(year: int, month: int, day: int, hour: int, minute: int) -> datetime | None:
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None

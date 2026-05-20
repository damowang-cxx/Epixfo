from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from app.adapters.carrier_query.csair.active_flight import query_active_flight
from app.adapters.carrier_query.csair.captcha import CaptchaFailed, pass_captcha
from app.adapters.carrier_query.csair.html_parser import parse_result
from app.adapters.carrier_query.csair.session import AWB_PAGE_URL, build_session, fetch_viewstate

logger = logging.getLogger("epixfo.csair.client")

GET_AWB_TYPE_URL = "https://tang.csair.com/WebFace/Tang.WebFace.Cargo/AgentAwbBrower.aspx/GetAwbType"

CN_TZ = timezone(timedelta(hours=8))


class AwbNotFound(Exception):
    pass


class AwbAmbiguous(Exception):
    """国内/国际同号，MVP 不支持，让调用方分两次查。"""


def _call_get_awb_type(session: requests.Session, prefix: str, no: str) -> str:
    r = session.post(
        GET_AWB_TYPE_URL,
        json={"awbPrefix": prefix, "awbNo": no},
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Referer": AWB_PAGE_URL,
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=20,
    )
    r.raise_for_status()
    payload = r.json()
    raw = payload.get("d") if isinstance(payload, dict) and "d" in payload else payload
    return str(raw).strip()


def _submit_query(
    session: requests.Session,
    prefix: str,
    no: str,
    img_id: str,
    is_international: bool,
    viewstate: dict[str, str],
    debug_dir: Path | None = None,
) -> str:
    form = {
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$btnBrow",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "ctl00$ContentPlaceHolder1$txtPrefix": prefix,
        "ctl00$ContentPlaceHolder1$txtNo": no,
        "ctl00$ContentPlaceHolder1$txtImgId": img_id,
        "ctl00$lancode": "zh-cn",
    }
    for k in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__VIEWSTATEENCRYPTED"):
        if k in viewstate:
            form[k] = viewstate[k]
    if is_international:
        form["ctl00$ContentPlaceHolder1$cbIsInter"] = "on"

    r = session.post(
        AWB_PAGE_URL,
        data=form,
        headers={
            "Referer": AWB_PAGE_URL,
            "Origin": "https://tang.csair.com",
        },
        timeout=30,
    )
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding

    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(CN_TZ).strftime("%Y%m%d%H%M%S")
        (debug_dir / f"submit_{prefix}-{no}_{ts}.html").write_text(r.text, encoding="utf-8")

    return r.text


def query_awb(prefix: str, no: str, debug_dir: Path | None = None) -> dict[str, Any]:
    prefix = prefix.strip()
    no = no.strip()
    if not (len(prefix) == 3 and prefix.isdigit()):
        raise ValueError(f"运单前缀必须是 3 位数字，实际：{prefix!r}")
    if not (len(no) == 8 and no.isdigit()):
        raise ValueError(f"运单号必须是 8 位数字，实际：{no!r}")

    logger.info("querying CZ awb %s-%s", prefix, no)

    with build_session() as session:
        viewstate = fetch_viewstate(session)

        awb_type_raw = _call_get_awb_type(session, prefix, no)
        if awb_type_raw.startswith("err"):
            msg = awb_type_raw.split("|", 1)[1] if "|" in awb_type_raw else awb_type_raw
            raise AwbNotFound(f"运单不存在或后端报错：{msg}")

        type_code = awb_type_raw.split("|", 1)[0]
        if type_code == "2":
            raise AwbAmbiguous("国内/国际同单号，MVP 不支持，请分别用国内/国际接口分两次查")
        is_international = type_code == "1"

        img_id = pass_captcha(
            session,
            referer_url=AWB_PAGE_URL,
            debug_label="awb_captcha",
            debug_dir=debug_dir,
        )

        html = _submit_query(session, prefix, no, img_id, is_international, viewstate, debug_dir)

        result = parse_result(html)

        if not result.get("awbInfo") and result.get("errorInfo"):
            raise AwbNotFound(f"查询返回错误信息：{result['errorInfo']}")

        # 给每个 booking 补充精确的起飞 / 到达时间（计划 + 实际）。单条失败仅置 None，不冒泡。
        _enrich_bookings_with_active_flight(session, result.get("booking") or [], debug_dir)

        return {
            "awbNo": f"{prefix}-{no}",
            "awbType": "international" if is_international else "domestic",
            "queriedAt": datetime.now(CN_TZ).isoformat(),
            "booking": result["booking"],
            "awbInfo": result["awbInfo"],
            "milestones": result["milestones"],
            "cargoState": result["cargoState"],
            "combine": result["combine"],
            "errorInfo": result["errorInfo"],
        }


_FLIGHT_NO_RE = re.compile(r"^([A-Za-z]{1,3})\s*0*(\d+)$")


def _enrich_bookings_with_active_flight(
    session: requests.Session,
    bookings: list[dict[str, Any]],
    debug_dir: Path | None,
) -> None:
    """对每条 booking 调一次航班动态查询，回写 4 个时间字段。

    单条 booking 查询失败（captcha / network / 解析）只 log warning，4 字段保持 None。
    """
    for row in bookings:
        # 默认先置 None，便于失败时仍有键
        row.setdefault("depPlanTime", None)
        row.setdefault("depActualTime", None)
        row.setdefault("arrPlanTime", None)
        row.setdefault("arrActualTime", None)

        flight_no = (row.get("flight") or "").strip()
        flight_date_raw = (row.get("flightDate") or "").strip()
        if not flight_no or not flight_date_raw:
            logger.debug("skip active flight: missing flight or flightDate in booking %r", row)
            continue

        flight_date = _parse_date(flight_date_raw)
        if flight_date is None:
            logger.debug("skip active flight: cannot parse date %r", flight_date_raw)
            continue

        from_station = _airport_code(row.get("fromStation"))
        to_station = _airport_code(row.get("toStation"))

        try:
            entries = query_active_flight(
                session,
                flight_no=flight_no,
                flight_date=flight_date,
                dep_station=from_station,
                arr_station=to_station,
                debug_dir=debug_dir,
            )
        except Exception as exc:  # noqa: BLE001  本期就是要降级吞掉
            logger.warning(
                "active flight query failed for %s @ %s: %r",
                flight_no,
                flight_date,
                exc,
            )
            continue

        match = _pick_matching_entry(entries, flight_no, from_station, to_station)
        if match is None:
            logger.info(
                "active_flight_match no match for %s %s-%s",
                flight_no,
                from_station,
                to_station,
            )
            continue
        logger.info(
            "active_flight_match matched %s %s-%s times dep_plan=%s dep_actual=%s arr_plan=%s arr_actual=%s",
            flight_no,
            from_station,
            to_station,
            match.get("depPlanTime"),
            match.get("depActualTime"),
            match.get("arrPlanTime"),
            match.get("arrActualTime"),
        )

        row["depPlanTime"] = match.get("depPlanTime")
        row["depActualTime"] = match.get("depActualTime")
        row["arrPlanTime"] = match.get("arrPlanTime")
        row["arrActualTime"] = match.get("arrActualTime")


def _parse_date(value: str) -> date | None:
    """booking.flightDate 可能是 `2026-05-20` / `2026/05/20` / `2026年05月20日`。"""
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _airport_code(value: str | None) -> str:
    """`广州(CAN)` -> `CAN`；`CAN` -> `CAN`；空 -> ''。"""
    if not value:
        return ""
    m = re.search(r"\(([A-Za-z]{3})\)", value)
    if m:
        return m.group(1).upper()
    stripped = value.strip().upper()
    return stripped if re.fullmatch(r"[A-Z]{3}", stripped) else stripped


def _normalize_flight_no(value: str) -> str:
    """`CZ307` 和 `CZ0307` 都视为相等：去掉数字部分前导 0。"""
    text = (value or "").strip().upper()
    m = _FLIGHT_NO_RE.match(text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return text


def _pick_matching_entry(
    entries: list[dict[str, Any]],
    flight_no: str,
    from_station: str,
    to_station: str,
) -> dict[str, Any] | None:
    """优先 leg + flight_no 双匹配；只有 flight_no 唯一时也直接用。"""
    if not entries:
        return None
    target_flight = _normalize_flight_no(flight_no)
    leg_target = f"{from_station}-{to_station}" if from_station and to_station else None

    flight_matches = [e for e in entries if _normalize_flight_no(e.get("flightNo", "")) == target_flight]
    if leg_target:
        leg_matches = [e for e in flight_matches if (e.get("leg") or "").upper() == leg_target]
        if leg_matches:
            return leg_matches[0]
    if len(flight_matches) == 1:
        return flight_matches[0]
    # 兜底：第一条结果（若整张表只有一条）
    if len(entries) == 1:
        return entries[0]
    return None

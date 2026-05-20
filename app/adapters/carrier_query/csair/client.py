from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

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

        img_id = pass_captcha(session)

        html = _submit_query(session, prefix, no, img_id, is_international, viewstate, debug_dir)

        result = parse_result(html)

        if not result.get("awbInfo") and result.get("errorInfo"):
            raise AwbNotFound(f"查询返回错误信息：{result['errorInfo']}")

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

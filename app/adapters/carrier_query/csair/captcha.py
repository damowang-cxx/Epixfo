"""滑动拼图验证码处理。

三个接口（已通过浏览器抓包确认）：

  1. GET https://aircargo.csair.com/verify/verifyImage/getId
        ?callback=jQuery...&Authorization=dGFuZzp0YW5nMTIz&width=360&height=160
        &timeout=5&errorRange=5&retryCount=5&r=...&_=ts
     -> JSONP `cb({"id":"...","status":200,"message":"请求成功"})`
  2. GET https://aircargo.csair.com/verify/verifyImage/bigImage/{id}    -> 背景图 PNG
  3. GET https://aircargo.csair.com/verify/verifyImage/smallImage/{id}  -> 滑块图 PNG
  4. POST https://tang.csair.com/ValidateImage.ashx?imgid={id}&slidex={x}
     -> {"resultCode": 0} 为通过
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any

import cv2
import numpy as np
import requests

from app.adapters.carrier_query.csair.session import VERIFY_AUTH_HEADER

logger = logging.getLogger("epixfo.csair.captcha")

VERIFY_BASE = "https://aircargo.csair.com"
TANG_BASE = "https://tang.csair.com"
GET_ID_URL = f"{VERIFY_BASE}/verify/verifyImage/getId"
BIG_IMG_URL = f"{VERIFY_BASE}/verify/verifyImage/bigImage"
SMALL_IMG_URL = f"{VERIFY_BASE}/verify/verifyImage/smallImage"
VALIDATE_URL = f"{TANG_BASE}/ValidateImage.ashx"

_REFERER = "https://tang.csair.com/"
_JSONP_RE = re.compile(r"^[\w_$.]*\((.+)\)\s*;?\s*$", re.DOTALL)


class CaptchaFailed(Exception):
    pass


def _getid_headers() -> dict[str, str]:
    return {"Accept": "*/*", "Referer": _REFERER}


def _image_headers() -> dict[str, str]:
    return {"Accept": "image/png,image/*,*/*;q=0.8", "Referer": _REFERER}


def _validate_headers() -> dict[str, str]:
    return {
        "Authorization": VERIFY_AUTH_HEADER,
        "Referer": _REFERER,
        "X-Requested-With": "XMLHttpRequest",
    }


def _getid_params() -> dict[str, Any]:
    """匹配 jquery.verify.js 实际的 query 串。关键：Authorization 在这里而非 header。"""
    ts = int(time.time() * 1000)
    cb = f"jQuery{random.randint(10 ** 19, 10 ** 20 - 1)}_{ts}"
    return {
        "callback": cb,
        "Authorization": VERIFY_AUTH_HEADER,
        "width": 360,
        "height": 160,
        "timeout": 5,
        "errorRange": 5,
        "retryCount": 5,
        "r": random.randint(10 ** 7, 10 ** 8 - 1),
        "_": ts,
    }


def _parse_jsonp(text: str) -> Any:
    s = text.strip()
    try:
        return json.loads(s)
    except ValueError:
        m = _JSONP_RE.match(s)
        if not m:
            raise
        return json.loads(m.group(1))


def fetch_captcha_payload(session: requests.Session, timeout: int = 15) -> dict[str, Any]:
    r = session.get(GET_ID_URL, params=_getid_params(), headers=_getid_headers(), timeout=timeout)
    r.raise_for_status()
    try:
        data = _parse_jsonp(r.text)
    except ValueError as exc:
        raise CaptchaFailed(f"getId 返回无法解析: {r.text[:200]!r}") from exc
    if not isinstance(data, dict):
        raise CaptchaFailed(f"getId 返回非对象: {data!r}")
    if data.get("status") != 200:
        raise CaptchaFailed(f"getId 返回错误: {data}")
    return data


def extract_captcha(session: requests.Session, timeout: int = 15) -> tuple[str, bytes, bytes]:
    payload = fetch_captcha_payload(session, timeout=timeout)
    img_id = payload.get("id")
    if not img_id:
        raise CaptchaFailed(f"getId 响应缺少 id: {payload}")

    bg = session.get(f"{BIG_IMG_URL}/{img_id}", headers=_image_headers(), timeout=timeout)
    bg.raise_for_status()

    sl = session.get(f"{SMALL_IMG_URL}/{img_id}", headers=_image_headers(), timeout=timeout)
    sl.raise_for_status()

    return str(img_id), bg.content, sl.content


def solve_slide(bg_bytes: bytes, slider_bytes: bytes) -> int:
    bg = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if bg is None:
        raise CaptchaFailed("背景图解码失败")

    slider_rgba = cv2.imdecode(np.frombuffer(slider_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if slider_rgba is None:
        raise CaptchaFailed("滑块图解码失败")

    if slider_rgba.ndim == 3 and slider_rgba.shape[2] == 4:
        slider_gray = cv2.cvtColor(slider_rgba[:, :, :3], cv2.COLOR_BGR2GRAY)
        mask = slider_rgba[:, :, 3]
        coords = cv2.findNonZero(mask)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            slider_gray = slider_gray[y:y + h, x:x + w]
    else:
        slider_gray = cv2.cvtColor(slider_rgba, cv2.COLOR_BGR2GRAY) if slider_rgba.ndim == 3 else slider_rgba

    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    bg_edges = cv2.Canny(cv2.GaussianBlur(bg_gray, (3, 3), 0), 50, 150)
    sl_edges = cv2.Canny(slider_gray, 50, 150)

    res = cv2.matchTemplate(bg_edges, sl_edges, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    return int(max_loc[0])


def validate(session: requests.Session, img_id: str, slide_x: int, timeout: int = 15) -> bool:
    r = session.post(
        VALIDATE_URL,
        params={"imgid": img_id, "slidex": slide_x},
        headers=_validate_headers(),
        timeout=timeout,
    )
    if r.status_code != 200:
        return False
    try:
        data = r.json()
    except ValueError:
        return False
    try:
        return int(data.get("resultCode", 1)) == 0
    except (TypeError, ValueError):
        return False


def pass_captcha(session: requests.Session, retries: int = 3, retry_sleep: float = 0.6) -> str:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            img_id, bg, sl = extract_captcha(session)
            slide_x = solve_slide(bg, sl)
            if validate(session, img_id, slide_x):
                return img_id
            logger.debug("captcha validate rejected on attempt %d", attempt)
        except Exception as exc:
            last_err = exc
            logger.debug("captcha attempt %d failed: %r", attempt, exc)
        time.sleep(retry_sleep)

    raise CaptchaFailed(f"滑动验证码 {retries} 次重试均失败（last_err={last_err!r}）")

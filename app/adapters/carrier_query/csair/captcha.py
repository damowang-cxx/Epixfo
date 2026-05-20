"""China Southern slide captcha helpers.

The same captcha service is used by the AWB query page and the ActiveFlight
page, but the validation request is sensitive to page context. Callers should
therefore pass the exact page URL as ``referer_url`` instead of relying on a
site-root referer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import random
import re
import time
from typing import Any

import requests

from app.adapters.carrier_query.csair.session import VERIFY_AUTH_HEADER
from app.core.config import settings

logger = logging.getLogger("epixfo.csair.captcha")

VERIFY_BASE = "https://aircargo.csair.com"
TANG_BASE = "https://tang.csair.com"
GET_ID_URL = f"{VERIFY_BASE}/verify/verifyImage/getId"
BIG_IMG_URL = f"{VERIFY_BASE}/verify/verifyImage/bigImage"
SMALL_IMG_URL = f"{VERIFY_BASE}/verify/verifyImage/smallImage"
VALIDATE_URL = f"{TANG_BASE}/ValidateImage.ashx"
DEFAULT_REFERER = "https://tang.csair.com/"

_JSONP_RE = re.compile(r"^[\w_$.]*\((.+)\)\s*;?\s*$", re.DOTALL)


class CaptchaFailed(Exception):
    pass


@dataclass
class CaptchaValidation:
    slide_x: int
    ok: bool
    status_code: int | None = None
    response_text: str | None = None
    response_json: Any | None = None


def _normalize_referer(referer_url: str | None) -> str:
    return referer_url or DEFAULT_REFERER


def _getid_headers(referer_url: str | None = None) -> dict[str, str]:
    return {"Accept": "*/*", "Referer": _normalize_referer(referer_url)}


def _image_headers(referer_url: str | None = None) -> dict[str, str]:
    return {"Accept": "image/png,image/*,*/*;q=0.8", "Referer": _normalize_referer(referer_url)}


def _validate_headers(referer_url: str | None = None) -> dict[str, str]:
    return {
        "Authorization": VERIFY_AUTH_HEADER,
        "Referer": _normalize_referer(referer_url),
        "X-Requested-With": "XMLHttpRequest",
    }


def _getid_params() -> dict[str, Any]:
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


def fetch_captcha_payload(
    session: requests.Session,
    timeout: int = 15,
    referer_url: str | None = None,
) -> dict[str, Any]:
    r = session.get(GET_ID_URL, params=_getid_params(), headers=_getid_headers(referer_url), timeout=timeout)
    r.raise_for_status()
    try:
        data = _parse_jsonp(r.text)
    except ValueError as exc:
        raise CaptchaFailed(f"getId response cannot be parsed: {r.text[:200]!r}") from exc
    if not isinstance(data, dict):
        raise CaptchaFailed(f"getId response is not an object: {data!r}")
    if data.get("status") != 200:
        raise CaptchaFailed(f"getId returned error: {data}")
    return data


def extract_captcha(
    session: requests.Session,
    timeout: int = 15,
    referer_url: str | None = None,
) -> tuple[str, bytes, bytes]:
    payload = fetch_captcha_payload(session, timeout=timeout, referer_url=referer_url)
    img_id = payload.get("id")
    if not img_id:
        raise CaptchaFailed(f"getId response missing id: {payload}")

    bg = session.get(f"{BIG_IMG_URL}/{img_id}", headers=_image_headers(referer_url), timeout=timeout)
    bg.raise_for_status()

    sl = session.get(f"{SMALL_IMG_URL}/{img_id}", headers=_image_headers(referer_url), timeout=timeout)
    sl.raise_for_status()

    return str(img_id), bg.content, sl.content


def solve_slide(bg_bytes: bytes, slider_bytes: bytes) -> int:
    import cv2
    import numpy as np

    bg = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if bg is None:
        raise CaptchaFailed("background image decode failed")

    slider_rgba = cv2.imdecode(np.frombuffer(slider_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if slider_rgba is None:
        raise CaptchaFailed("slider image decode failed")

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


def validate_detail(
    session: requests.Session,
    img_id: str,
    slide_x: int,
    timeout: int = 15,
    referer_url: str | None = None,
) -> CaptchaValidation:
    try:
        r = session.post(
            VALIDATE_URL,
            params={"imgid": img_id, "slidex": slide_x},
            headers=_validate_headers(referer_url),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return CaptchaValidation(slide_x=slide_x, ok=False, response_text=f"{type(exc).__name__}: {exc}")

    data: Any | None = None
    try:
        data = r.json()
    except ValueError:
        pass

    ok = False
    if r.status_code == 200 and isinstance(data, dict):
        try:
            ok = int(data.get("resultCode", 1)) == 0
        except (TypeError, ValueError):
            ok = False

    return CaptchaValidation(
        slide_x=slide_x,
        ok=ok,
        status_code=r.status_code,
        response_text=r.text[:500],
        response_json=data,
    )


def validate(
    session: requests.Session,
    img_id: str,
    slide_x: int,
    timeout: int = 15,
    referer_url: str | None = None,
) -> bool:
    return validate_detail(session, img_id, slide_x, timeout=timeout, referer_url=referer_url).ok


def pass_captcha(
    session: requests.Session,
    retries: int = 3,
    retry_sleep: float = 0.6,
    referer_url: str | None = None,
    debug_label: str = "captcha",
    offset_range: int | None = None,
    debug_dir: str | Path | None = None,
) -> str:
    referer = _normalize_referer(referer_url)
    offsets = settings.csair_captcha_offset_range if offset_range is None else offset_range
    offsets = max(0, int(offsets))

    last_err: Exception | None = None
    last_validations: list[CaptchaValidation] = []

    for attempt in range(1, retries + 1):
        img_id: str | None = None
        bg: bytes | None = None
        sl: bytes | None = None
        raw_slide_x: int | None = None
        validations: list[CaptchaValidation] = []
        debug_written = False

        try:
            img_id, bg, sl = extract_captcha(session, referer_url=referer)
            raw_slide_x = solve_slide(bg, sl)
            logger.info(
                "%s attempt=%d img_id=%s raw_slide_x=%s referer=%s",
                debug_label,
                attempt,
                img_id,
                raw_slide_x,
                referer,
            )

            for slide_x in _offset_candidates(raw_slide_x, offsets):
                validation = validate_detail(session, img_id, slide_x, referer_url=referer)
                validations.append(validation)
                if validation.ok:
                    logger.info(
                        "%s passed attempt=%d img_id=%s raw_slide_x=%s final_slide_x=%s offset=%s",
                        debug_label,
                        attempt,
                        img_id,
                        raw_slide_x,
                        slide_x,
                        slide_x - raw_slide_x,
                    )
                    _write_debug(
                        debug_label=debug_label,
                        attempt=attempt,
                        img_id=img_id,
                        referer_url=referer,
                        raw_slide_x=raw_slide_x,
                        validations=validations,
                        bg=bg,
                        sl=sl,
                        debug_dir=debug_dir,
                    )
                    debug_written = True
                    return img_id

            last_validations = validations
            logger.debug("%s validate rejected on attempt %d", debug_label, attempt)
        except Exception as exc:
            last_err = exc
            logger.debug("%s attempt %d failed: %r", debug_label, attempt, exc)
        finally:
            if not debug_written:
                _write_debug(
                    debug_label=debug_label,
                    attempt=attempt,
                    img_id=img_id,
                    referer_url=referer,
                    raw_slide_x=raw_slide_x,
                    validations=validations,
                    bg=bg,
                    sl=sl,
                    debug_dir=debug_dir,
                )

        time.sleep(retry_sleep)

    rejection_summary = [
        {"slide_x": item.slide_x, "status_code": item.status_code, "response_json": item.response_json}
        for item in last_validations[-5:]
    ]
    raise CaptchaFailed(
        f"slide captcha failed after {retries} attempts "
        f"(debug_label={debug_label}, last_err={last_err!r}, last_rejections={rejection_summary!r})"
    )


def _offset_candidates(raw_slide_x: int, offset_range: int) -> list[int]:
    candidates = [raw_slide_x]
    for delta in range(1, offset_range + 1):
        candidates.append(raw_slide_x - delta)
        candidates.append(raw_slide_x + delta)
    return [max(0, item) for item in candidates]


def _write_debug(
    *,
    debug_label: str,
    attempt: int,
    img_id: str | None,
    referer_url: str,
    raw_slide_x: int | None,
    validations: list[CaptchaValidation],
    bg: bytes | None,
    sl: bytes | None,
    debug_dir: str | Path | None,
) -> None:
    if not (settings.csair_captcha_debug or debug_dir):
        return

    base_dir = Path(debug_dir or settings.csair_captcha_debug_dir)
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", debug_label).strip("_") or "captcha"
    stamp = int(time.time() * 1000)
    prefix = f"{stamp}_{safe_label}_attempt{attempt}"
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        if bg is not None:
            (base_dir / f"{prefix}_big.png").write_bytes(bg)
        if sl is not None:
            (base_dir / f"{prefix}_small.png").write_bytes(sl)
        metadata = {
            "debug_label": debug_label,
            "attempt": attempt,
            "img_id": img_id,
            "referer_url": referer_url,
            "get_id_url": GET_ID_URL,
            "big_image_url": f"{BIG_IMG_URL}/{img_id}" if img_id else None,
            "small_image_url": f"{SMALL_IMG_URL}/{img_id}" if img_id else None,
            "validate_url": VALIDATE_URL,
            "raw_slide_x": raw_slide_x,
            "validations": [asdict(item) for item in validations],
        }
        (base_dir / f"{prefix}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("captcha debug write failed: %r", exc)

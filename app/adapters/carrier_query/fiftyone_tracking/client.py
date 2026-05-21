from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)


class FiftyOneTrackingAircargoError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        url: str | None = None,
        response_body: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.url = url
        self.response_body = response_body


@dataclass(frozen=True)
class AirWaybillNumber:
    digits: str
    prefix: str
    serial_number: str
    formatted: str


@dataclass(frozen=True)
class VerifySignature:
    signature: str
    cookie_value: str
    timestamp_ms: int


class FiftyOneTrackingAircargoClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        cache_dir: str | Path | None = None,
        cache_ttl_seconds: int | None = None,
        timeout_seconds: int | None = None,
        lang: str | None = None,
        allow_stale_on_error: bool | None = None,
        session: requests.Session | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.base_url = (base_url or settings.fiftyone_tracking_base_url).rstrip("/")
        self.cache_dir = Path(cache_dir or settings.fiftyone_tracking_cache_dir)
        self.cache_ttl_seconds = (
            settings.fiftyone_tracking_cache_ttl_seconds
            if cache_ttl_seconds is None
            else cache_ttl_seconds
        )
        self.timeout_seconds = (
            settings.fiftyone_tracking_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        self.lang = lang or settings.fiftyone_tracking_lang
        self.allow_stale_on_error = (
            settings.fiftyone_tracking_allow_stale_on_error
            if allow_stale_on_error is None
            else allow_stale_on_error
        )
        self.session = session or requests.Session()
        self.user_agent = user_agent

    def query(
        self,
        awb_input: str,
        *,
        use_cache: bool = True,
        force_refresh: bool = False,
        cache_ttl_seconds: int | None = None,
        cache_dir: str | Path | None = None,
        allow_stale_on_error: bool | None = None,
        lang: str | None = None,
    ) -> dict[str, Any]:
        awb = normalize_air_waybill(awb_input)
        resolved_cache_dir = Path(cache_dir or self.cache_dir)
        resolved_ttl = self.cache_ttl_seconds if cache_ttl_seconds is None else cache_ttl_seconds
        stale_allowed = self.allow_stale_on_error if allow_stale_on_error is None else allow_stale_on_error
        cache_path = resolved_cache_dir / f"{awb.digits}.json"

        if use_cache and not force_refresh:
            cached = _read_fresh_cache(cache_path, resolved_ttl)
            if cached is not None:
                return _mark_cache_hit(cached, cache_path, stale=False)

        try:
            fetched_at = _utc_now_iso()
            query_lang = lang or self.lang
            verify_raw = self.verify(awb.formatted, lang=query_lang)
            supported_items = _to_array(_get_path(verify_raw, "data.support"))
            supported_item = _find_supported_item(supported_items, awb.formatted)
            tracking_raw = None

            if supported_item:
                tracking_raw = self.fetch_tracking_data(
                    track_number=supported_item.get("track_number") or awb.formatted,
                    validate=supported_item.get("validate"),
                    timestamp=supported_item.get("time"),
                    lang=query_lang,
                )

            result = _normalize_query_result(
                awb=awb,
                fetched_at=fetched_at,
                verify_raw=verify_raw,
                tracking_raw=tracking_raw,
                cache_path=cache_path,
                cache_ttl_seconds=resolved_ttl,
            )
            if use_cache:
                _write_cache(cache_path, result)
            return result
        except Exception as exc:
            if use_cache and stale_allowed and not force_refresh:
                cached = _read_any_cache(cache_path)
                if cached is not None:
                    return _mark_cache_hit(
                        cached,
                        cache_path,
                        stale=True,
                        error=_serialize_error(exc),
                    )
            raise

    def verify(self, formatted_awb: str, *, lang: str | None = None, timestamp_ms: int | None = None) -> dict[str, Any]:
        query_lang = lang or self.lang
        timestamp = int(timestamp_ms or time.time() * 1000)
        signed = build_verify_signature(formatted_awb, timestamp)
        self.session.cookies.set("51tracking", signed.cookie_value)
        response_body = self._fetch_text(
            "GET",
            f"{self.base_url}/aircargo/track",
            params={
                "action": "Verify",
                "num": formatted_awb,
                "lang": query_lang,
                "t": str(timestamp),
                "v": signed.signature,
            },
            headers={
                "accept": "*/*",
                "referer": self.build_referer(formatted_awb, query_lang),
            },
        )
        parsed = _parse_json_response(response_body)

        if not isinstance(parsed, dict) or int(parsed.get("code") or 0) != 200:
            raise FiftyOneTrackingAircargoError(
                f"51tracking Verify returned {parsed.get('code') if isinstance(parsed, dict) else 'an unexpected response'}.",
                response_body=parsed,
            )
        return parsed

    def fetch_tracking_data(
        self,
        *,
        track_number: str,
        validate: str | None,
        timestamp: int | str | None,
        lang: str | None = None,
    ) -> dict[str, Any]:
        if not track_number or not validate or not timestamp:
            raise TypeError("track_number, validate, and timestamp are required.")
        query_lang = lang or self.lang
        response_body = self._fetch_text(
            "GET",
            f"{self.base_url}/aircargo/api",
            params={
                "action": "Tracking",
                "num": track_number,
                "v": validate,
                "t": str(timestamp),
                "lang": query_lang,
                "source": "web",
            },
            headers={
                "accept": "*/*",
                "referer": self.build_referer(track_number, query_lang),
            },
        )
        parsed = _parse_tracking_response(response_body)
        if not isinstance(parsed, dict):
            raise FiftyOneTrackingAircargoError(
                "51tracking Tracking returned an unexpected response.",
                response_body=response_body,
            )
        return parsed

    def build_referer(self, formatted_awb: str, lang: str | None = None) -> str:
        query_lang = lang or self.lang
        path_prefix = "/aircargo" if query_lang == "en" else f"/aircargo/{query_lang}"
        return f"{self.base_url}{path_prefix}/{_remove_separators(formatted_awb)}"

    def _fetch_text(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str] | None = None,
    ) -> str:
        request_headers = self._build_headers(headers)
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                headers=request_headers,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise FiftyOneTrackingAircargoError(f"Request failed: {url}", url=url) from exc

        body = response.text
        if not response.ok:
            raise FiftyOneTrackingAircargoError(
                f"51tracking returned HTTP {response.status_code}.",
                status=response.status_code,
                url=str(response.url),
                response_body=body,
            )
        return body

    def _build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "accept-language": "zh-CN,zh;q=0.9",
            "user-agent": self.user_agent,
            "x-requested-with": "XMLHttpRequest",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers


def normalize_air_waybill(value: str) -> AirWaybillNumber:
    raw = str(value or "").strip()
    digits = re.sub(r"[\s-]+", "", raw)
    match = re.fullmatch(r"(\d{3})(\d{8})", digits)
    if not match:
        raise ValueError(f"Expected an 11 digit air waybill number, received: {value!r}")
    prefix, serial_number = match.group(1), match.group(2)
    return AirWaybillNumber(
        digits=f"{prefix}{serial_number}",
        prefix=prefix,
        serial_number=serial_number,
        formatted=f"{prefix}-{serial_number}",
    )


def build_verify_signature(track_number: str, timestamp_ms: int | None = None) -> VerifySignature:
    timestamp = int(timestamp_ms or time.time() * 1000)
    context = "51tracking"
    timestamp_seconds = timestamp // 1000
    cookie_seed = str(timestamp // 888)
    cookie_value = _md5(cookie_seed[-6:] + _md5(context))
    signature = _md5(
        f"{_md5(context)}::{_md5(track_number)}:{_md5(timestamp_seconds)}:{_md5(_md5('Verify'))}"
    )
    return VerifySignature(
        signature=signature,
        cookie_value=cookie_value,
        timestamp_ms=timestamp,
    )


def query_fiftyone_tracking_aircargo(awb: str, **options: Any) -> dict[str, Any]:
    client = FiftyOneTrackingAircargoClient(
        base_url=options.get("base_url"),
        cache_dir=options.get("cache_dir"),
        cache_ttl_seconds=options.get("cache_ttl_seconds"),
        timeout_seconds=options.get("timeout_seconds"),
        lang=options.get("lang"),
        allow_stale_on_error=options.get("allow_stale_on_error"),
        session=options.get("session"),
    )
    return client.query(
        awb,
        use_cache=options.get("use_cache", True),
        force_refresh=options.get("force_refresh", False),
        cache_ttl_seconds=options.get("cache_ttl_seconds"),
        cache_dir=options.get("cache_dir"),
        allow_stale_on_error=options.get("allow_stale_on_error"),
        lang=options.get("lang"),
    )


def _normalize_query_result(
    *,
    awb: AirWaybillNumber,
    fetched_at: str,
    verify_raw: dict[str, Any],
    tracking_raw: dict[str, Any] | None,
    cache_path: Path,
    cache_ttl_seconds: int,
) -> dict[str, Any]:
    tracking_record = _find_tracking_record(tracking_raw, awb.formatted)
    return_data = tracking_record.get("return_data") if isinstance(tracking_record, dict) else None
    order = (
        _normalize_order(
            awb=awb,
            tracking_raw=tracking_raw or {},
            tracking_record=tracking_record,
            return_data=return_data,
        )
        if isinstance(return_data, dict)
        else None
    )

    return {
        "carrier": _get_path(order, "airline.name") if order else None,
        "source": "51tracking-aircargo",
        "awb": awb.digits,
        "formattedAwb": awb.formatted,
        "found": bool(order),
        "fetchedAt": fetched_at,
        "totalCount": 1 if order else 0,
        "orders": [order] if order else [],
        "cache": {
            "hit": False,
            "stale": False,
            "path": str(cache_path),
            "ttlSeconds": cache_ttl_seconds,
            "fetchedAt": fetched_at,
        },
        "raw": {
            "verify": verify_raw,
            "tracking": tracking_raw,
        },
    }


def _normalize_order(
    *,
    awb: AirWaybillNumber,
    tracking_raw: dict[str, Any],
    tracking_record: dict[str, Any],
    return_data: dict[str, Any],
) -> dict[str, Any]:
    events = [_normalize_event(event) for event in _to_array(return_data.get("track_info"))]
    flights = _normalize_flights(return_data)
    airline = _normalize_airline(tracking_record.get("air_info") or {})
    latest_event = events[0] if events else None
    return {
        "awb": awb.digits,
        "formattedAwb": tracking_record.get("track_number") or awb.formatted,
        "status": {
            "number": return_data.get("status_number"),
            "code": return_data.get("awb_status") or return_data.get("status"),
            "substatus": return_data.get("awb_substatus") or return_data.get("substatus"),
            "description": return_data.get("data_status"),
            "substatusDescription": return_data.get("data_substatus"),
            "latestEvent": return_data.get("last_event"),
        },
        "route": {
            "origin": _normalize_station(return_data.get("origin"), return_data.get("origin_name")),
            "destination": _normalize_station(return_data.get("destination"), return_data.get("destination_name")),
            "waypoints": _to_array(return_data.get("flight_way_station")),
        },
        "cargo": {
            "weight": return_data.get("weight"),
            "pieces": return_data.get("piece"),
            "volume": return_data.get("volume"),
        },
        "airline": airline,
        "flights": flights,
        "events": events,
        "latestEvent": latest_event,
        "source": return_data.get("source") or tracking_record.get("source") or tracking_raw.get("source"),
        "metadata": {
            "whetherPay": tracking_record.get("whether_pay"),
            "normal": tracking_raw.get("normal"),
            "lang": tracking_raw.get("lang"),
            "functionTrace": tracking_raw.get("function"),
        },
        "raw": tracking_record,
    }


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": event.get("status"),
        "time": event.get("actual_date") or event.get("plan_date"),
        "actualTime": event.get("actual_date"),
        "plannedTime": event.get("plan_date"),
        "event": event.get("event"),
        "station": event.get("station"),
        "flightNumber": event.get("flight_number"),
        "weight": event.get("weight"),
        "pieces": event.get("piece"),
        "checkpointStatus": event.get("checkpoint_status"),
        "substatus": event.get("substatus"),
        "checkpointStatusDescription": event.get("info_checkpoint_status"),
        "substatusDescription": event.get("info_substatus"),
        "raw": event,
    }


def _normalize_flights(return_data: dict[str, Any]) -> list[dict[str, Any]]:
    flight_info_new = _to_array(return_data.get("flight_info_new"))
    if flight_info_new:
        return [
            {
                "flightNumber": flight.get("flight_number"),
                "departStation": flight.get("depart_station"),
                "arrivalStation": flight.get("arrival_station"),
                "plannedDepartTime": flight.get("plan_depart_time"),
                "plannedArrivalTime": flight.get("plan_arrival_time"),
                "departTime": flight.get("depart_time"),
                "arrivalTime": flight.get("arrival_time"),
                "weight": flight.get("weight"),
                "pieces": flight.get("piece"),
                "status": flight.get("status"),
                "raw": flight,
            }
            for flight in flight_info_new
            if isinstance(flight, dict)
        ]

    flight_info = return_data.get("flight_info") or {}
    if not isinstance(flight_info, dict):
        return []
    return [
        {
            "flightNumber": flight_number,
            "departStation": flight.get("depart_station"),
            "arrivalStation": flight.get("arrival_station"),
            "plannedDepartTime": flight.get("plan_depart_time"),
            "plannedArrivalTime": flight.get("plan_arrival_time"),
            "departTime": flight.get("depart_time"),
            "arrivalTime": flight.get("arrival_time"),
            "raw": flight,
        }
        for flight_number, flight in flight_info.items()
        if isinstance(flight, dict)
    ]


def _normalize_airline(air_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": air_info.get("name"),
        "url": air_info.get("url"),
        "trackUrl": air_info.get("track_url"),
        "raw": air_info,
    }


def _normalize_station(code: Any, name: Any) -> dict[str, Any] | None:
    if code in (None, "") and name in (None, ""):
        return None
    return {
        "code": code,
        "name": name or code,
    }


def _parse_tracking_response(text: str) -> Any:
    match = re.search(r"###([\s\S]*)###", str(text or ""))
    return _parse_json_response(match.group(1) if match else text)


def _parse_json_response(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def _find_supported_item(items: list[Any], formatted_awb: str) -> dict[str, Any] | None:
    dict_items = [item for item in items if isinstance(item, dict)]
    return next((item for item in dict_items if item.get("track_number") == formatted_awb), None) or (
        dict_items[0] if dict_items else None
    )


def _find_tracking_record(tracking_raw: dict[str, Any] | None, formatted_awb: str) -> dict[str, Any] | None:
    if not isinstance(tracking_raw, dict):
        return None
    candidate = tracking_raw.get(formatted_awb) or tracking_raw.get(_remove_separators(formatted_awb))
    if isinstance(candidate, dict):
        return candidate
    return next((value for value in tracking_raw.values() if isinstance(value, dict) and "return_data" in value), None)


def _read_fresh_cache(cache_path: Path, ttl_seconds: int) -> dict[str, Any] | None:
    cached = _read_any_cache(cache_path)
    if cached is None:
        return None
    fetched_at = _get_path(cached, "cache.fetchedAt") or cached.get("fetchedAt")
    if not fetched_at:
        return None
    try:
        fetched_ts = _parse_iso_to_epoch(str(fetched_at))
    except ValueError:
        return None
    if ttl_seconds < 0 or time.time() - fetched_ts <= ttl_seconds:
        return cached
    return None


def _read_any_cache(cache_path: Path) -> dict[str, Any] | None:
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return cached if isinstance(cached, dict) else None


def _write_cache(cache_path: Path, value: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_name(f"{cache_path.name}.{time.time_ns()}.tmp")
    temp_path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(cache_path)


def _mark_cache_hit(
    cached: dict[str, Any],
    cache_path: Path,
    *,
    stale: bool,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    marked = {
        **cached,
        "cache": {
            **(cached.get("cache") or {}),
            "hit": True,
            "stale": stale,
            "path": str(cache_path),
        },
    }
    if error is not None:
        marked["cache"]["error"] = error
    return marked


def _serialize_error(error: Exception) -> dict[str, Any]:
    return {
        "name": type(error).__name__,
        "message": str(error),
        "status": getattr(error, "status", None),
        "responseBody": getattr(error, "response_body", None),
    }


def _get_path(value: Any, path_expression: str) -> Any:
    current = value
    for key in path_expression.split("."):
        if current is None:
            return None
        if isinstance(current, list):
            if not key.isdigit():
                return None
            index = int(key)
            current = current[index] if index < len(current) else None
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _to_array(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _remove_separators(value: Any) -> str:
    return re.sub(r"[\s-]+", "", str(value or ""))


def _md5(value: Any) -> str:
    return hashlib.md5(str(value).encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso_to_epoch(value: str) -> float:
    from datetime import datetime

    text = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text).timestamp()

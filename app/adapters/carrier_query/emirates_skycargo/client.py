from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


class EmiratesSkyCargoError(Exception):
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


@dataclass
class _TokenState:
    access_token: str | None = None
    expires_at: float = 0


class EmiratesSkyCargoClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        cache_dir: str | Path | None = None,
        cache_ttl_seconds: int | None = None,
        timeout_seconds: int | None = None,
        session: requests.Session | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.base_url = (base_url or settings.emirates_skycargo_base_url).rstrip("/")
        self.cache_dir = Path(cache_dir or settings.emirates_skycargo_cache_dir)
        self.cache_ttl_seconds = (
            settings.emirates_skycargo_cache_ttl_seconds
            if cache_ttl_seconds is None
            else cache_ttl_seconds
        )
        self.timeout_seconds = (
            settings.emirates_skycargo_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        self.session = session or requests.Session()
        self.user_agent = user_agent
        self._token = _TokenState()

    def query(
        self,
        awb_input: str,
        *,
        use_cache: bool = True,
        force_refresh: bool = False,
        cache_ttl_seconds: int | None = None,
        cache_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        awb = normalize_awb_for_query(awb_input)
        resolved_cache_dir = Path(cache_dir or self.cache_dir)
        resolved_ttl = self.cache_ttl_seconds if cache_ttl_seconds is None else cache_ttl_seconds
        cache_path = resolved_cache_dir / f"{awb}.json"

        if use_cache and not force_refresh:
            cached = _read_fresh_cache(cache_path, resolved_ttl)
            if cached is not None:
                cached["cache"] = {
                    **(cached.get("cache") or {}),
                    "hit": True,
                    "path": str(cache_path),
                }
                return cached

        fetched_at = _utc_now_iso()
        summary_raw = self.search_orders(awb)
        summary_orders = _to_array(_get_path(summary_raw, "data.order"))
        details: list[dict[str, Any]] = []

        for summary_order in summary_orders:
            booking_reference = _find_booking_reference_number(summary_order)
            if not booking_reference:
                details.append(
                    {
                        "bookingReferenceNumber": None,
                        "error": "Missing bookingReferenceNumber in summary response.",
                        "raw": None,
                    }
                )
                continue

            try:
                detail_raw = self.fetch_order_details(booking_reference)
                details.append({"bookingReferenceNumber": booking_reference, "raw": detail_raw})
            except Exception as exc:
                details.append(
                    {
                        "bookingReferenceNumber": booking_reference,
                        "error": str(exc),
                        "raw": None,
                    }
                )

        result = _normalize_query_result(
            awb=awb,
            fetched_at=fetched_at,
            summary_raw=summary_raw,
            details=details,
            cache_path=cache_path,
            cache_ttl_seconds=resolved_ttl,
        )

        if use_cache:
            _write_cache(cache_path, result)

        return result

    def search_orders(self, awb_input: str) -> dict[str, Any]:
        awb = normalize_awb_for_query(awb_input)
        url = f"{self.base_url}/api/order/services/cargo/v1/orders/actions/search?view=summary"
        payload = {
            "orderFilter": {
                "airCapacity": {
                    "documentNumbers": [awb],
                    "includeItinerary": False,
                }
            },
            "pageRequest": {
                "page": 1,
                "pageSize": 10,
            },
        }
        return self._fetch_json(
            "POST",
            url,
            json_payload=payload,
            headers={"content-type": "application/json"},
            auth=True,
        )

    def fetch_order_details(self, booking_reference_number: str) -> dict[str, Any]:
        reference = str(booking_reference_number or "").strip()
        if not reference:
            raise ValueError("bookingReferenceNumber is required.")
        url = f"{self.base_url}/api/order/services/cargo/v1/orders/{requests.utils.quote(f'b{reference}')}"
        return self._fetch_json("GET", url, auth=True)

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        now = time.time()
        if not force_refresh and self._token.access_token and now < self._token.expires_at:
            return self._token.access_token

        token_info = self.fetch_guest_token()
        access_token = token_info.get("access_token") or _get_path(token_info, "data.access_token")
        expires_in_seconds = int(token_info.get("expires_in") or _get_path(token_info, "data.expires_in") or 899)
        if not access_token:
            raise EmiratesSkyCargoError(
                "Guest token response did not contain access_token.",
                response_body=token_info,
            )

        self._token = _TokenState(
            access_token=str(access_token),
            expires_at=time.time() + max(expires_in_seconds - 60, 60),
        )
        return self._token.access_token

    def fetch_guest_token(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/uaa/guest/oauth/token?productName=offerandorder"
        data = {
            "tenant": "EK",
            "client_id": "mercator",
            "client_secret": "",
        }
        return self._fetch_json(
            "POST",
            url,
            data=data,
            headers={"content-type": "application/x-www-form-urlencoded"},
            auth=False,
        )

    def _fetch_json(
        self,
        method: str,
        url: str,
        *,
        json_payload: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        auth: bool = False,
    ) -> dict[str, Any]:
        attempts = 2 if auth else 1
        last_error: EmiratesSkyCargoError | None = None

        for attempt in range(attempts):
            request_headers = self._build_headers(
                headers,
                auth=auth,
                force_token_refresh=attempt > 0,
            )
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=request_headers,
                    json=json_payload,
                    data=data,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise EmiratesSkyCargoError(f"Request failed: {url}", url=url) from exc

            response_body = _parse_json_response(response.text)
            if response.status_code == 401 and auth and attempt == 0:
                self._token = _TokenState()
                continue
            if not response.ok:
                last_error = EmiratesSkyCargoError(
                    f"Emirates SkyCargo returned HTTP {response.status_code}.",
                    status=response.status_code,
                    url=url,
                    response_body=response_body,
                )
                break

            return response_body if isinstance(response_body, dict) else {"data": response_body}

        if last_error is not None:
            raise last_error
        raise EmiratesSkyCargoError(f"Request failed: {url}", url=url)

    def _build_headers(
        self,
        extra_headers: dict[str, str] | None = None,
        *,
        auth: bool,
        force_token_refresh: bool,
    ) -> dict[str, str]:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "origin": self.base_url,
            "referer": f"{self.base_url}/app/offerandorder/",
            "user-agent": self.user_agent,
            "x-referer": "https://EK",
        }
        if extra_headers:
            headers.update(extra_headers)
        if auth:
            headers["authorization"] = f"Bearer {self.get_access_token(force_refresh=force_token_refresh)}"
        return headers


def normalize_awb_for_query(value: str) -> str:
    awb = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(awb) != 11:
        raise ValueError(f"Expected an 11 digit AWB number, received: {value!r}")
    return awb


def query_emirates_skycargo(awb: str, **options: Any) -> dict[str, Any]:
    client = EmiratesSkyCargoClient(
        base_url=options.get("base_url"),
        cache_dir=options.get("cache_dir"),
        cache_ttl_seconds=options.get("cache_ttl_seconds"),
        timeout_seconds=options.get("timeout_seconds"),
        session=options.get("session"),
    )
    return client.query(
        awb,
        use_cache=options.get("use_cache", True),
        force_refresh=options.get("force_refresh", False),
        cache_ttl_seconds=options.get("cache_ttl_seconds"),
        cache_dir=options.get("cache_dir"),
    )


def _normalize_query_result(
    *,
    awb: str,
    fetched_at: str,
    summary_raw: dict[str, Any],
    details: list[dict[str, Any]],
    cache_path: Path,
    cache_ttl_seconds: int,
) -> dict[str, Any]:
    summary_orders = _to_array(_get_path(summary_raw, "data.order"))
    orders = []
    for index, summary_order in enumerate(summary_orders):
        detail = details[index] if index < len(details) else {}
        orders.append(_normalize_order(summary_order, detail.get("raw"), detail))

    return {
        "carrier": "EK",
        "source": "emirates-skycargo",
        "awb": awb,
        "found": bool(orders),
        "fetchedAt": fetched_at,
        "totalCount": _get_path(summary_raw, "data.pageInfo.totalCount") or len(orders),
        "orders": orders,
        "cache": {
            "hit": False,
            "path": str(cache_path),
            "ttlSeconds": cache_ttl_seconds,
            "fetchedAt": fetched_at,
        },
        "raw": {
            "summary": summary_raw,
            "details": [detail.get("raw") for detail in details],
            "detailErrors": [
                {
                    "bookingReferenceNumber": detail.get("bookingReferenceNumber"),
                    "error": detail.get("error"),
                }
                for detail in details
                if detail.get("error")
            ],
        },
    }


def _normalize_order(summary_order: dict[str, Any], detail_raw: dict[str, Any] | None, detail_meta: dict[str, Any]) -> dict[str, Any]:
    detail_order_items = _to_array(_get_path(detail_raw, "data.orderItems.orderItem"))
    summary_order_items = _to_array(_get_path(summary_order, "orderItems.orderItem"))
    order_items = detail_order_items or summary_order_items
    primary_item = order_items[0] if order_items else {}
    primary_air_capacity = _get_path(primary_item, "productInfo.airCapacity") or {}
    summary_air_capacity = (
        _get_path(summary_order, "productInfo.airCapacity")
        or _get_path(summary_order, "airCapacity")
        or {}
    )
    air_capacity = primary_air_capacity if primary_air_capacity else summary_air_capacity
    cargo_info = _get_path(air_capacity, "cargoInfo") or _get_path(summary_air_capacity, "cargoInfo") or {}
    document_info = _get_path(air_capacity, "documentInfo") or _get_path(summary_air_capacity, "documentInfo") or {}
    reference = primary_item.get("reference") or summary_order.get("reference") or summary_order.get("referenceInfo") or {}
    milestones = []
    for order_item_index, item in enumerate(order_items):
        for milestone in _to_array(_get_path(item, "fulfillmentInfo.serviceInfo.milestone")):
            normalized = _normalize_milestone(milestone, order_item_index)
            if normalized is not None:
                milestones.append(normalized)
    latest_milestone = next((item for item in milestones if item.get("latestMilestone")), None)
    if latest_milestone is None:
        latest_milestone = _normalize_milestone(_pick_value(summary_order, ["latestMilestone", "milestone"]), None)

    return {
        "bookingReferenceNumber": detail_meta.get("bookingReferenceNumber") or _find_booking_reference_number(summary_order),
        "jobReferenceNumber": reference.get("jobReferenceNumber"),
        "awbReferenceNumber": reference.get("awbReferenceNumber"),
        "orderStatus": _pick_value(summary_order, ["orderStatus", "status", "state"]),
        "document": _normalize_document(document_info),
        "route": {
            "origin": _normalize_location(air_capacity.get("origin") or summary_air_capacity.get("origin")),
            "destination": _normalize_location(air_capacity.get("destination") or summary_air_capacity.get("destination")),
        },
        "cargo": {
            "cargoReference": cargo_info.get("cargoReference"),
            "cargoCategory": cargo_info.get("cargoCategory"),
            "goodsDescription": cargo_info.get("goodsDescription"),
            "commodityCode": cargo_info.get("commodityCode"),
            "quantityInfo": _to_array(cargo_info.get("quantityInfo")),
            "customsInformation": cargo_info.get("customsInformation") or {},
            "additionalInfo": _to_array(cargo_info.get("additionalInfo")),
            "harmonizedCommodityCode": cargo_info.get("hamonizedCommodityCode")
            or cargo_info.get("harmonizedCommodityCode")
            or [],
        },
        "product": _get_path(air_capacity, "product.product") or air_capacity.get("product"),
        "journeyTime": _get_path(air_capacity, "offerItinerary.journeyTime"),
        "itinerary": _to_array(_get_path(air_capacity, "offerItinerary.itinerary")),
        "milestones": milestones,
        "latestMilestone": latest_milestone,
        "isPartShipment": primary_item.get("isPartShipment", summary_order.get("isPartShipment")),
        "orderSource": primary_item.get("orderSource", summary_order.get("orderSource")),
        "routes": _to_array(air_capacity.get("routes")),
        "participants": _to_array(air_capacity.get("participant")),
        "orderItems": [_normalize_order_item(item) for item in order_items],
        "raw": {
            "summary": summary_order,
            "details": detail_raw,
        },
    }


def _normalize_order_item(item: dict[str, Any]) -> dict[str, Any]:
    air_capacity = _get_path(item, "productInfo.airCapacity") or {}
    cargo_info = _get_path(air_capacity, "cargoInfo") or {}
    return {
        "orderSource": item.get("orderSource"),
        "isPartShipment": item.get("isPartShipment"),
        "document": _normalize_document(air_capacity.get("documentInfo") or {}),
        "route": {
            "origin": _normalize_location(air_capacity.get("origin")),
            "destination": _normalize_location(air_capacity.get("destination")),
        },
        "cargo": {
            "cargoReference": cargo_info.get("cargoReference"),
            "cargoCategory": cargo_info.get("cargoCategory"),
            "goodsDescription": cargo_info.get("goodsDescription"),
            "commodityCode": cargo_info.get("commodityCode"),
            "quantityInfo": _to_array(cargo_info.get("quantityInfo")),
            "customsInformation": cargo_info.get("customsInformation") or {},
        },
        "product": _get_path(air_capacity, "product.product") or air_capacity.get("product"),
        "journeyTime": _get_path(air_capacity, "offerItinerary.journeyTime"),
        "itinerary": _to_array(_get_path(air_capacity, "offerItinerary.itinerary")),
        "milestones": [
            item
            for item in (
                _normalize_milestone(milestone, None)
                for milestone in _to_array(_get_path(item, "fulfillmentInfo.serviceInfo.milestone"))
            )
            if item is not None
        ],
        "raw": item,
    }


def _normalize_document(document_info: dict[str, Any]) -> dict[str, Any]:
    prefix = document_info.get("documentPrefix") or document_info.get("prefix")
    number = document_info.get("documentNumber") or document_info.get("number")
    document_type = document_info.get("documentType") or document_info.get("type")
    return {
        "prefix": prefix,
        "number": number,
        "type": document_type,
        "formatted": f"{prefix}-{number}" if prefix and number else None,
    }


def _normalize_milestone(milestone: Any, order_item_index: int | None) -> dict[str, Any] | None:
    if not isinstance(milestone, dict):
        return None
    code = _get_path(milestone, "code.code") or (milestone.get("code") if isinstance(milestone.get("code"), str) else None)
    description = _get_path(milestone, "code.description") or milestone.get("description")
    status_date = milestone.get("statusDate")
    achieved = _get_path(status_date, "achieved") if isinstance(status_date, dict) else status_date
    achieved_utc = _get_path(status_date, "achievedUTC") if isinstance(status_date, dict) else milestone.get("achievedUTC")
    return {
        "code": code,
        "description": description,
        "station": _normalize_location(milestone.get("station")),
        "achieved": achieved,
        "achievedUTC": achieved_utc,
        "latestMilestone": bool(milestone.get("latestMilestone")),
        "importStatusMessage": milestone.get("importStatusMessage"),
        "exportStatusMessage": milestone.get("exportStatusMessage"),
        "statusData": milestone.get("statusData"),
        "id": milestone.get("id"),
        "orderItemIndex": order_item_index,
        "raw": milestone,
    }


def _normalize_location(location: Any) -> dict[str, Any] | None:
    if not location:
        return None
    if isinstance(location, str):
        return {"code": location}
    if not isinstance(location, dict):
        return None
    return {
        "code": location.get("code"),
        "name": location.get("name") or location.get("description"),
        "description": location.get("description"),
        "raw": location,
    }


def _find_booking_reference_number(summary_order: dict[str, Any]) -> str:
    first_order_item = (_to_array(_get_path(summary_order, "orderItems.orderItem")) or [{}])[0]
    value = _pick_value(
        summary_order,
        [
            "reference.bookingReferenceNumber",
            "referenceInfo.bookingReferenceNumber",
            "bookingReferenceNumber",
            "orderItems.orderItem.0.reference.bookingReferenceNumber",
            "productInfo.airCapacity.cargoInfo.cargoReference",
            "airCapacity.cargoInfo.cargoReference",
            "cargoInfo.cargoReference",
        ],
    ) or _pick_value(
        first_order_item,
        [
            "reference.bookingReferenceNumber",
            "productInfo.airCapacity.cargoInfo.cargoReference",
        ],
    )
    return "" if value is None else str(value).strip()


def _read_fresh_cache(cache_path: Path, ttl_seconds: int) -> dict[str, Any] | None:
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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


def _write_cache(cache_path: Path, value: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_name(f"{cache_path.name}.{time.time_ns()}.tmp")
    temp_path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(cache_path)


def _parse_json_response(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


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


def _pick_value(value: dict[str, Any], paths: list[str]) -> Any:
    for path in paths:
        candidate = _get_path(value, path)
        if candidate not in (None, ""):
            return candidate
    return None


def _to_array(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso_to_epoch(value: str) -> float:
    from datetime import datetime

    text = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text).timestamp()

from __future__ import annotations

import asyncio
import logging

import requests

from app.adapters.carrier_query.base import CarrierQueryResult
from app.adapters.carrier_query.fiftyone_tracking import (
    FiftyOneTrackingAircargoError,
    normalize_air_waybill,
    query_fiftyone_tracking_aircargo,
)
from app.adapters.carrier_query.normalizers import normalizer_registry
from app.models.enums import CarrierQueryMethod, QueryStatus
from app.utils.waybill_utils import normalize_waybill_no, validate_waybill_no

logger = logging.getLogger("epixfo.adapter.general")


class GeneralAdapter:
    adapter_code = "general_adapter"
    carrier_code = "UNKNOWN"
    query_method = CarrierQueryMethod.PROTOCOL

    async def query(self, waybill_no: str) -> CarrierQueryResult:
        if not validate_waybill_no(waybill_no):
            return self._failed(
                "invalid_waybill_no",
                f"运单号格式无效：{waybill_no!r}",
            )

        normalized = normalize_waybill_no(waybill_no)
        try:
            query_awb = normalize_air_waybill(normalized).digits
        except ValueError as exc:
            return self._failed("invalid_waybill_no", str(exc))

        try:
            raw = await asyncio.to_thread(query_fiftyone_tracking_aircargo, query_awb)
        except FiftyOneTrackingAircargoError as exc:
            error_code = "network_error" if exc.status is None else f"http_{exc.status}"
            return self._failed(error_code, str(exc))
        except requests.RequestException as exc:
            return self._failed("network_error", str(exc))
        except Exception as exc:
            logger.exception("unexpected error querying general adapter %s", waybill_no)
            return self._failed("unknown_error", f"{type(exc).__name__}: {exc}")

        if not raw.get("found"):
            return CarrierQueryResult(
                status=QueryStatus.FAILED,
                carrier_code=self.carrier_code,
                adapter_code=self.adapter_code,
                query_method=self.query_method,
                raw_response=raw,
                error_code="awb_not_found",
                error_message=f"51tracking 未查询到运单：{normalized}",
            )

        normalizer = normalizer_registry.get(self.adapter_code)
        if normalizer is None:
            return self._failed(
                "normalizer_not_found",
                f"No normalizer registered for adapter_code={self.adapter_code!r}",
            )

        normalized_raw = normalizer.normalize(raw)
        cache = raw.get("cache") or {}
        cache_error = cache.get("error") or {}
        stale = bool(cache.get("stale"))
        return CarrierQueryResult(
            status=QueryStatus.PARTIAL_SUCCESS if stale else QueryStatus.SUCCESS,
            carrier_code=self.carrier_code,
            adapter_code=self.adapter_code,
            query_method=self.query_method,
            raw_response=normalized_raw,
            error_code="stale_cache" if stale else None,
            error_message=cache_error.get("message") if stale and isinstance(cache_error, dict) else None,
        )

    def _failed(self, error_code: str, error_message: str) -> CarrierQueryResult:
        return CarrierQueryResult(
            status=QueryStatus.FAILED,
            carrier_code=self.carrier_code,
            adapter_code=self.adapter_code,
            query_method=self.query_method,
            error_code=error_code,
            error_message=error_message,
        )

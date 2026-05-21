from __future__ import annotations

import asyncio
import logging

import requests

from app.adapters.carrier_query.base import CarrierQueryResult
from app.adapters.carrier_query.emirates_skycargo import (
    EmiratesSkyCargoError,
    normalize_awb_for_query,
    query_emirates_skycargo,
)
from app.adapters.carrier_query.normalizers import normalizer_registry
from app.models.enums import CarrierQueryMethod, QueryStatus
from app.utils.waybill_utils import normalize_waybill_no, validate_waybill_no

logger = logging.getLogger("epixfo.adapter.ek")


class EKAdapter:
    adapter_code = "ek_adapter"
    carrier_code = "EK"
    query_method = CarrierQueryMethod.PROTOCOL

    async def query(self, waybill_no: str) -> CarrierQueryResult:
        if not validate_waybill_no(waybill_no):
            return self._failed(
                "invalid_waybill_no",
                f"提单号格式无效：{waybill_no!r}",
            )

        normalized = normalize_waybill_no(waybill_no)
        try:
            query_awb = normalize_awb_for_query(normalized)
        except ValueError as exc:
            return self._failed("invalid_waybill_no", str(exc))

        try:
            raw = await asyncio.to_thread(query_emirates_skycargo, query_awb)
        except EmiratesSkyCargoError as exc:
            error_code = "network_error" if exc.status is None else f"http_{exc.status}"
            return self._failed(error_code, str(exc))
        except requests.RequestException as exc:
            return self._failed("network_error", str(exc))
        except Exception as exc:
            logger.exception("unexpected error querying EK %s", waybill_no)
            return self._failed("unknown_error", f"{type(exc).__name__}: {exc}")

        if not raw.get("found"):
            return CarrierQueryResult(
                status=QueryStatus.FAILED,
                carrier_code=self.carrier_code,
                adapter_code=self.adapter_code,
                query_method=self.query_method,
                raw_response=raw,
                error_code="awb_not_found",
                error_message=f"Emirates SkyCargo 未查询到提单：{normalized}",
            )

        normalizer = normalizer_registry.get(self.adapter_code)
        if normalizer is None:
            return self._failed(
                "normalizer_not_found",
                f"No normalizer registered for adapter_code={self.adapter_code!r}",
            )

        normalized_raw = normalizer.normalize(raw)
        detail_errors = ((raw.get("raw") or {}).get("detailErrors") or [])
        status = QueryStatus.PARTIAL_SUCCESS if detail_errors else QueryStatus.SUCCESS

        return CarrierQueryResult(
            status=status,
            carrier_code=self.carrier_code,
            adapter_code=self.adapter_code,
            query_method=self.query_method,
            raw_response=normalized_raw,
            error_code="detail_partial_failed" if detail_errors else None,
            error_message="部分 Emirates 明细查询失败，已保留可用数据。" if detail_errors else None,
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

from __future__ import annotations

import asyncio
import logging
import re

import requests

from app.adapters.carrier_query.base import CarrierQueryResult
from app.adapters.carrier_query.csair import AwbAmbiguous, AwbNotFound, CaptchaFailed, query_awb
from app.adapters.carrier_query.normalizers import normalizer_registry
from app.models.enums import CarrierQueryMethod, QueryStatus
from app.utils.waybill_utils import normalize_waybill_no, validate_waybill_no

logger = logging.getLogger("epixfo.adapter.cz")

_WAYBILL_SPLIT_RE = re.compile(r"^(\d{3})-(\d{8})$")


class CZAdapter:
    adapter_code = "cz_adapter"
    carrier_code = "CZ"
    query_method = CarrierQueryMethod.HYBRID

    async def query(self, waybill_no: str) -> CarrierQueryResult:
        if not validate_waybill_no(waybill_no):
            return self._failed(
                error_code="invalid_waybill_no",
                error_message=f"运单号格式无效：{waybill_no!r}",
            )

        normalized = normalize_waybill_no(waybill_no)
        match = _WAYBILL_SPLIT_RE.match(normalized)
        if not match:
            return self._failed(
                error_code="invalid_waybill_no",
                error_message=f"无法拆分运单号：{waybill_no!r}",
            )

        prefix, serial = match.group(1), match.group(2)

        try:
            raw = await asyncio.to_thread(query_awb, prefix, serial)
        except AwbNotFound as exc:
            return self._failed("awb_not_found", str(exc))
        except AwbAmbiguous as exc:
            return self._failed("awb_ambiguous", str(exc))
        except CaptchaFailed as exc:
            return self._failed("captcha_failed", str(exc))
        except requests.RequestException as exc:
            return self._failed("network_error", str(exc))
        except Exception as exc:
            logger.exception("unexpected error querying CZ %s", waybill_no)
            return self._failed("unknown_error", f"{type(exc).__name__}: {exc}")

        normalizer = normalizer_registry.get(self.adapter_code)
        if normalizer is None:
            return self._failed(
                "normalizer_not_found",
                f"No normalizer registered for adapter_code={self.adapter_code!r}",
            )

        normalized_raw = normalizer.normalize(raw)

        return CarrierQueryResult(
            status=QueryStatus.SUCCESS,
            carrier_code=self.carrier_code,
            adapter_code=self.adapter_code,
            query_method=self.query_method,
            raw_response=normalized_raw,
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

import hashlib
import re
from decimal import Decimal


WAYBILL_PATTERN = re.compile(r"^\d{3}-?\d{8}$")


def normalize_waybill_no(waybill_no: str) -> str:
    clean = waybill_no.strip().replace(" ", "")
    if "-" not in clean and len(clean) == 11:
        clean = f"{clean[:3]}-{clean[3:]}"
    return clean


def validate_waybill_no(waybill_no: str) -> bool:
    return bool(WAYBILL_PATTERN.match(waybill_no.strip().replace(" ", "")))


def carrier_prefix_from_waybill(waybill_no: str) -> str:
    return normalize_waybill_no(waybill_no)[:3]


def event_hash(*parts: object) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def decimal_or_none(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))

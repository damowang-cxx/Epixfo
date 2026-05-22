from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.waybill_service import WaybillService


def _make_service(get_contact_fn):
    service = WaybillService.__new__(WaybillService)
    service.db = None
    service.repo = None
    service.carriers = None
    service.alerts = None
    service.consignees = SimpleNamespace(get_contact=get_contact_fn)
    return service


def test_resolve_consignee_snapshot_none_returns_none() -> None:
    service = _make_service(lambda _id: None)
    assert service._resolve_consignee_snapshot(None) is None


def test_resolve_consignee_snapshot_returns_id_and_name() -> None:
    fake_consignee = SimpleNamespace(name="Mission Freight BV")
    fake_contact = SimpleNamespace(id=42, name="Mission Freight AMS", consignee=fake_consignee)
    service = _make_service(lambda cid: fake_contact if cid == 42 else None)

    result = service._resolve_consignee_snapshot(42)

    assert result == (42, "Mission Freight AMS")


def test_resolve_consignee_snapshot_falls_back_to_company_name() -> None:
    fake_consignee = SimpleNamespace(name="Mission Freight BV")
    fake_contact = SimpleNamespace(id=43, name="", consignee=fake_consignee)
    service = _make_service(lambda cid: fake_contact if cid == 43 else None)

    result = service._resolve_consignee_snapshot(43)

    assert result == (43, "Mission Freight BV")


def test_resolve_consignee_snapshot_raises_when_contact_missing() -> None:
    service = _make_service(lambda _id: None)
    with pytest.raises(HTTPException) as exc_info:
        service._resolve_consignee_snapshot(999)
    assert "consignee_contact_not_found" in str(exc_info.value.detail)


def test_resolve_consignee_snapshot_truncates_long_names() -> None:
    """收件人名超过 255 字符时应截断，避免溢出 air_waybills.consignee 长度。"""
    long_name = "X" * 300
    fake_contact = SimpleNamespace(id=1, name=long_name, consignee=SimpleNamespace(name="Company"))
    service = _make_service(lambda _id: fake_contact)

    _id, snapshot = service._resolve_consignee_snapshot(1)
    assert len(snapshot) == 255


def test_resolve_consignee_snapshot_handles_orphan_contact() -> None:
    """consignee 关系若懒加载未取到（极端情况），快照为空串而非异常。"""
    fake_contact = SimpleNamespace(id=2, name="", consignee=None)
    service = _make_service(lambda _id: fake_contact)

    _id, snapshot = service._resolve_consignee_snapshot(2)
    assert _id == 2
    assert snapshot == ""

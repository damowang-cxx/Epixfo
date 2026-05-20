from types import SimpleNamespace

import pytest

from fastapi import HTTPException

from app.services.waybill_service import WaybillService


def _make_service(get_agent_fn):
    service = WaybillService.__new__(WaybillService)
    service.db = None
    service.repo = None
    service.alerts = None
    service.carriers = SimpleNamespace(get_agent=get_agent_fn)
    return service


def test_resolve_agent_snapshot_returns_none_for_none_input() -> None:
    service = _make_service(lambda agent_id: None)
    assert service._resolve_agent_snapshot(None, "CZ") is None


def test_resolve_agent_snapshot_returns_id_and_name_pair() -> None:
    fake_agent = SimpleNamespace(id=42, agent_name="代理ABC", carrier_code="CZ")
    service = _make_service(lambda agent_id: fake_agent if agent_id == 42 else None)

    result = service._resolve_agent_snapshot(42, "CZ")

    assert result == (42, "代理ABC")


def test_resolve_agent_snapshot_raises_when_agent_missing() -> None:
    service = _make_service(lambda agent_id: None)
    with pytest.raises(HTTPException) as exc_info:
        service._resolve_agent_snapshot(999, "CZ")
    assert "carrier_agent_not_found" in str(exc_info.value.detail)


def test_resolve_agent_snapshot_raises_on_carrier_code_mismatch() -> None:
    fake_agent = SimpleNamespace(id=1, agent_name="代理X", carrier_code="MU")
    service = _make_service(lambda agent_id: fake_agent)

    with pytest.raises(HTTPException) as exc_info:
        service._resolve_agent_snapshot(1, "CZ")
    assert "carrier_agent_carrier_mismatch" in str(exc_info.value.detail)


def test_resolve_agent_snapshot_skips_carrier_check_when_carrier_code_none() -> None:
    """运单还没识别出 carrier_code 时（如 UNKNOWN），不强制校验。"""
    fake_agent = SimpleNamespace(id=1, agent_name="代理X", carrier_code="MU")
    service = _make_service(lambda agent_id: fake_agent)

    result = service._resolve_agent_snapshot(1, None)

    assert result == (1, "代理X")

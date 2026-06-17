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
    assert service._resolve_agent_snapshot(None) is None


def test_resolve_agent_snapshot_returns_id_and_name_pair() -> None:
    fake_agent = SimpleNamespace(id=42, agent_name="代理ABC")
    service = _make_service(lambda agent_id: fake_agent if agent_id == 42 else None)

    result = service._resolve_agent_snapshot(42)

    assert result == (42, "代理ABC")


def test_resolve_agent_snapshot_raises_when_agent_missing() -> None:
    service = _make_service(lambda agent_id: None)
    with pytest.raises(HTTPException) as exc_info:
        service._resolve_agent_snapshot(999)
    assert "carrier_agent_not_found" in str(exc_info.value.detail)


def test_resolve_agent_snapshot_allows_agent_across_carriers() -> None:
    fake_agent = SimpleNamespace(id=1, agent_name="代理X")
    service = _make_service(lambda agent_id: fake_agent)

    result = service._resolve_agent_snapshot(1)

    assert result == (1, "代理X")

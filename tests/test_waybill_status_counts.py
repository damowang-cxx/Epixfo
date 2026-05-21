"""[app/services/waybill_service.py](app/services/waybill_service.py)
`WaybillService.status_counts` 单元测试。

注入桩 repo + 跳过 `PermissionService.filter_waybill_query`（不影响计数逻辑本身）。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.models.enums import WaybillLifecycleStatus
from app.services.waybill_service import WaybillService


def _make_service(counts: dict[WaybillLifecycleStatus, int]) -> WaybillService:
    service = WaybillService.__new__(WaybillService)
    service.db = None
    service.alerts = None
    service.carriers = None
    service.repo = SimpleNamespace(
        base_query=lambda: object(),
        count_by_status=lambda _query: counts,
    )
    return service


def test_status_counts_returns_all_11_statuses() -> None:
    """部分状态有数据时，返回值应包含 11 个状态全集，缺失为 0。"""
    repo_counts = {
        WaybillLifecycleStatus.CREATED: 3,
        WaybillLifecycleStatus.MONITORING: 5,
        WaybillLifecycleStatus.DEPARTED: 1,
    }
    service = _make_service(repo_counts)

    with patch(
        "app.services.waybill_service.PermissionService.filter_waybill_query",
        side_effect=lambda query, _user: query,
    ):
        result = service.status_counts(current_user=SimpleNamespace())

    assert len(result) == len(list(WaybillLifecycleStatus))
    assert len(result) == 11

    by_status = {item.status: item.count for item in result}
    assert by_status[WaybillLifecycleStatus.CREATED] == 3
    assert by_status[WaybillLifecycleStatus.MONITORING] == 5
    assert by_status[WaybillLifecycleStatus.DEPARTED] == 1
    # 缺失状态全部为 0
    assert by_status[WaybillLifecycleStatus.WAITING_MONITOR] == 0
    assert by_status[WaybillLifecycleStatus.VOIDED] == 0
    assert by_status[WaybillLifecycleStatus.CLOSED] == 0


def test_status_counts_order_matches_enum() -> None:
    """返回顺序必须与 WaybillLifecycleStatus 枚举一致，便于前端按固定顺序渲染卡片。"""
    service = _make_service({})

    with patch(
        "app.services.waybill_service.PermissionService.filter_waybill_query",
        side_effect=lambda query, _user: query,
    ):
        result = service.status_counts(current_user=SimpleNamespace())

    expected_order = [s for s in WaybillLifecycleStatus]
    actual_order = [item.status for item in result]
    assert actual_order == expected_order


def test_status_counts_empty_repo_returns_all_zero() -> None:
    service = _make_service({})
    with patch(
        "app.services.waybill_service.PermissionService.filter_waybill_query",
        side_effect=lambda query, _user: query,
    ):
        result = service.status_counts(current_user=SimpleNamespace())
    assert all(item.count == 0 for item in result)

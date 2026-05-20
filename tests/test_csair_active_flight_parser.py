"""[app/adapters/carrier_query/csair/active_flight.py](app/adapters/carrier_query/csair/active_flight.py) 单元测试。

固定一段用户提供的真实 GdResult HTML 防止回归。
"""

from __future__ import annotations

from datetime import date

from app.adapters.carrier_query.csair.active_flight import (
    parse_active_flight_result,
)


# 用户提供的真实样本（CZ307 / CAN-AMS / 05-20 起飞）
_REAL_HTML = """
<html><body>
<table id="ctl00_ContentPlaceHolder1_GdResult" border="1">
    <tbody>
        <tr align="center" style="background-color:#FFF7C8;">
            <td align="left" colspan="12">客机</td>
        </tr>
        <tr align="center" style="background-color:AliceBlue;">
            <td>CZ307       </td>
            <td>CAN-AMS</td>
            <td>05-20 0020</td>
            <td></td>
            <td>05-20 0026</td>
            <td>05-20 0535</td>
            <td></td>
            <td>05-20 0547</td>
            <td>359  </td>
            <td></td>
            <td></td>
            <td>已到达</td>
        </tr>
    </tbody>
</table>
</body></html>
"""


def test_parse_real_html_returns_one_row() -> None:
    rows = parse_active_flight_result(_REAL_HTML, dep_date=date(2026, 5, 20))
    assert len(rows) == 1


def test_parse_real_html_basic_fields() -> None:
    row = parse_active_flight_result(_REAL_HTML, dep_date=date(2026, 5, 20))[0]
    assert row["flightNo"] == "CZ307"
    assert row["leg"] == "CAN-AMS"


def test_parse_real_html_composed_iso_times() -> None:
    """关键回归：4 个时间字段都合成出来。"""
    row = parse_active_flight_result(_REAL_HTML, dep_date=date(2026, 5, 20))[0]
    assert row["depPlanTime"] == "2026-05-20 00:20:00"
    assert row["depActualTime"] == "2026-05-20 00:26:00"
    assert row["arrPlanTime"] == "2026-05-20 05:35:00"
    assert row["arrActualTime"] == "2026-05-20 05:47:00"


def test_parse_empty_cells_become_none() -> None:
    html = """
    <table id="ctl00_ContentPlaceHolder1_GdResult">
        <tr>
            <td>CZ307</td><td>CAN-AMS</td>
            <td>05-20 0020</td><td></td><td></td>
            <td>05-20 0535</td><td></td><td></td>
            <td>359</td><td>计划</td><td></td><td></td>
        </tr>
    </table>
    """
    row = parse_active_flight_result(html, dep_date=date(2026, 5, 20))[0]
    assert row["depPlanTime"] == "2026-05-20 00:20:00"
    assert row["depActualTime"] is None  # 实际起飞时间未提供
    assert row["arrPlanTime"] == "2026-05-20 05:35:00"
    assert row["arrActualTime"] is None


def test_parse_handles_overnight_arrival() -> None:
    """跨日：起飞 23:50，到达 02:30（次日）。"""
    html = """
    <table id="ctl00_ContentPlaceHolder1_GdResult">
        <tr>
            <td>CZ307</td><td>CAN-AMS</td>
            <td>05-20 2350</td><td></td><td>05-20 2350</td>
            <td>05-21 0230</td><td></td><td>05-21 0230</td>
            <td>359</td><td>已到达</td><td></td><td></td>
        </tr>
    </table>
    """
    row = parse_active_flight_result(html, dep_date=date(2026, 5, 20))[0]
    assert row["depPlanTime"] == "2026-05-20 23:50:00"
    assert row["arrPlanTime"] == "2026-05-21 02:30:00"
    assert row["arrActualTime"] == "2026-05-21 02:30:00"


def test_parse_handles_year_crossing() -> None:
    """跨年：起飞 12-31，到达 01-01。"""
    html = """
    <table id="ctl00_ContentPlaceHolder1_GdResult">
        <tr>
            <td>CZ307</td><td>CAN-AMS</td>
            <td>12-31 2330</td><td></td><td>12-31 2335</td>
            <td>01-01 0400</td><td></td><td>01-01 0410</td>
            <td>359</td><td>已到达</td><td></td><td></td>
        </tr>
    </table>
    """
    row = parse_active_flight_result(html, dep_date=date(2026, 12, 31))[0]
    assert row["depPlanTime"] == "2026-12-31 23:30:00"
    assert row["arrPlanTime"] == "2027-01-01 04:00:00"
    assert row["arrActualTime"] == "2027-01-01 04:10:00"


def test_parse_skips_group_header_row() -> None:
    """`<td colspan="12">客机</td>` 这种 1-cell 行必须跳过。"""
    rows = parse_active_flight_result(_REAL_HTML, dep_date=date(2026, 5, 20))
    assert len(rows) == 1  # 只有 1 行数据，分组行被过滤


def test_parse_returns_empty_when_table_missing() -> None:
    rows = parse_active_flight_result("<html><body><p>no table</p></body></html>", dep_date=date(2026, 5, 20))
    assert rows == []

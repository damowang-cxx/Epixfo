from __future__ import annotations

from datetime import date
from pathlib import Path

import requests

import pytest

from app.adapters.carrier_query.csair import active_flight, client
from app.adapters.carrier_query.csair.captcha import CaptchaFailed


@pytest.fixture(autouse=True)
def _disable_active_flight_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(active_flight.settings, "csair_captcha_debug", False)


def _active_flight_html() -> str:
    return """
    <input id="ctl00_ContentPlaceHolder1_txtFlightDepTime" value="2026-05-20" />
    <table id="ctl00_ContentPlaceHolder1_GdResult">
        <tr><td colspan="12">客机</td></tr>
        <tr>
            <td>CZ307</td><td>CAN-AMS</td>
            <td>05-20 0020</td><td></td><td>05-20 0026</td>
            <td>05-20 0535</td><td></td><td>05-20 0547</td>
            <td>359</td><td></td><td></td><td>已到达</td>
        </tr>
    </table>
    """


class _Response:
    status_code = 200
    text = _active_flight_html()
    apparent_encoding = "utf-8"
    encoding = "utf-8"

    def raise_for_status(self) -> None:
        return None


def test_query_active_flight_uses_active_flight_referer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(active_flight, "fetch_viewstate", lambda session, url=None: {"__VIEWSTATE": "v"})

    def fake_pass_captcha(session, referer_url=None, debug_label="", debug_dir=None):
        captured["referer_url"] = referer_url
        captured["debug_label"] = debug_label
        return "img-1"

    monkeypatch.setattr(active_flight, "pass_captcha", fake_pass_captcha)

    class Session:
        def post(self, url, data=None, headers=None, timeout=None):
            captured["post_url"] = url
            captured["form"] = data
            captured["headers"] = headers
            return _Response()

    rows = active_flight.query_active_flight(
        Session(),
        "CZ307",
        date(2026, 5, 20),
        debug_dir=tmp_path,
    )

    assert captured["referer_url"] == active_flight.ACTIVE_FLIGHT_URL
    assert captured["debug_label"] == "active_flight_captcha"
    assert captured["headers"]["Referer"] == active_flight.ACTIVE_FLIGHT_URL
    assert captured["form"]["__EVENTTARGET"] == ""
    assert captured["form"]["ctl00$ContentPlaceHolder1$txtImgId"] == "img-1"
    assert captured["form"]["ctl00$ContentPlaceHolder1$txtFlightDepTime"] == "2026-05-20"
    assert captured["form"]["ctl00$ContentPlaceHolder1$btnQuery"] == "查询"
    assert captured["form"]["ctl00$lancode"] == "zh-cn"
    assert rows[0]["depPlanTime"] == "2026-05-20 00:20:00"
    assert list(tmp_path.glob("*_submit.json"))
    assert list(tmp_path.glob("*_response.html"))
    assert list(tmp_path.glob("*_rows.json"))


def test_query_active_flight_writes_submit_error_debug(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(active_flight, "fetch_viewstate", lambda session, url=None: {"__VIEWSTATE": "v"})
    monkeypatch.setattr(active_flight, "pass_captcha", lambda *args, **kwargs: "img-1")

    class Session:
        def post(self, url, data=None, headers=None, timeout=None):
            raise requests.ConnectionError("connection closed")

    with pytest.raises(requests.ConnectionError):
        active_flight.query_active_flight(
            Session(),
            "CZ307",
            date(2026, 5, 20),
            debug_dir=tmp_path,
        )

    assert list(tmp_path.glob("*_submit.json"))
    error_files = list(tmp_path.glob("*_submit_error.json"))
    assert error_files
    assert "connection closed" in error_files[0].read_text(encoding="utf-8")


def test_query_active_flight_rejects_response_for_wrong_selected_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(active_flight, "fetch_viewstate", lambda session, url=None: {"__VIEWSTATE": "v"})
    monkeypatch.setattr(active_flight, "pass_captcha", lambda *args, **kwargs: "img-1")

    class WrongDateResponse(_Response):
        text = """
        <input id="ctl00_ContentPlaceHolder1_txtFlightDepTime" value="2026-05-21" />
        <table id="ctl00_ContentPlaceHolder1_GdResult">
            <tr><td>CZ307</td><td>CAN-AMS</td><td>05-21 0020</td><td></td><td></td><td>05-21 0535</td><td></td><td></td></tr>
        </table>
        """

    class Session:
        def post(self, url, data=None, headers=None, timeout=None):
            return WrongDateResponse()

    with pytest.raises(RuntimeError, match="selected date mismatch"):
        active_flight.query_active_flight(
            Session(),
            "CZ307",
            date(2026, 5, 20),
            debug_dir=tmp_path,
        )

    assert list(tmp_path.glob("*_date_mismatch.json"))


def test_active_flight_captcha_failure_keeps_main_booking(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query_active_flight(*args, **kwargs):
        raise CaptchaFailed("active flight captcha failed")

    monkeypatch.setattr(client, "query_active_flight", fake_query_active_flight)

    bookings = [
        {
            "flight": "CZ307",
            "flightDate": "2026-05-20",
            "fromStation": "CAN",
            "toStation": "AMS",
        }
    ]

    client._enrich_bookings_with_active_flight(object(), bookings, debug_dir=None)

    assert bookings[0]["depPlanTime"] is None
    assert bookings[0]["depActualTime"] is None
    assert bookings[0]["arrPlanTime"] is None
    assert bookings[0]["arrActualTime"] is None


def test_enrich_queries_cz_segments_and_skips_other_carriers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, date, str, str]] = []

    def fake_query_active_flight(session, flight_no, flight_date, dep_station=None, arr_station=None, debug_dir=None):
        calls.append((flight_no, flight_date, dep_station, arr_station))
        return [
            {
                "flightNo": flight_no,
                "leg": f"{dep_station}-{arr_station}",
                "depPlanTime": f"{flight_date.isoformat()} 01:00:00",
                "depActualTime": f"{flight_date.isoformat()} 01:10:00",
                "arrPlanTime": f"{flight_date.isoformat()} 05:00:00",
                "arrActualTime": f"{flight_date.isoformat()} 05:20:00",
            }
        ]

    monkeypatch.setattr(client, "query_active_flight", fake_query_active_flight)

    bookings = [
        {"flight": "CZ307", "flightDate": "2026-05-01", "fromStation": "CAN", "toStation": "AMS"},
        {"flight": "CZ345", "flightDate": "2026-05-02", "fromStation": "PKX", "toStation": "AMS"},
        {"flight": "KL898", "flightDate": "2026-05-03", "fromStation": "AMS", "toStation": "JFK"},
    ]

    client._enrich_bookings_with_active_flight(object(), bookings, debug_dir=None)

    assert calls == [
        ("CZ307", date(2026, 5, 1), "CAN", "AMS"),
        ("CZ345", date(2026, 5, 2), "PKX", "AMS"),
    ]
    assert bookings[0]["depPlanTime"] == "2026-05-01 01:00:00"
    assert bookings[1]["depPlanTime"] == "2026-05-02 01:00:00"
    assert bookings[2]["depPlanTime"] is None


def test_enrich_distinguishes_same_flight_by_date_and_leg(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, date, str, str]] = []

    def fake_query_active_flight(session, flight_no, flight_date, dep_station=None, arr_station=None, debug_dir=None):
        calls.append((flight_no, flight_date, dep_station, arr_station))
        return [
            {
                "flightNo": flight_no,
                "leg": f"{dep_station}-{arr_station}",
                "depPlanTime": f"{flight_date.isoformat()} 02:00:00",
                "depActualTime": None,
                "arrPlanTime": None,
                "arrActualTime": None,
            }
        ]

    monkeypatch.setattr(client, "query_active_flight", fake_query_active_flight)

    bookings = [
        {"flight": "CZ307", "flightDate": "2026-05-01", "fromStation": "CAN", "toStation": "AMS"},
        {"flight": "CZ307", "flightDate": "2026-05-02", "fromStation": "CAN", "toStation": "AMS"},
        {"flight": "CZ307", "flightDate": "2026-05-02", "fromStation": "CAN", "toStation": "AMS"},
    ]

    client._enrich_bookings_with_active_flight(object(), bookings, debug_dir=None)

    assert calls == [
        ("CZ307", date(2026, 5, 1), "CAN", "AMS"),
        ("CZ307", date(2026, 5, 2), "CAN", "AMS"),
    ]
    assert bookings[0]["depPlanTime"] == "2026-05-01 02:00:00"
    assert bookings[1]["depPlanTime"] == "2026-05-02 02:00:00"
    assert bookings[2]["depPlanTime"] == "2026-05-02 02:00:00"


def test_query_awb_keeps_booking_when_awb_info_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client, "build_session", lambda: _SessionContext())
    monkeypatch.setattr(client, "fetch_viewstate", lambda session: {"__VIEWSTATE": "v"})
    monkeypatch.setattr(client, "_call_get_awb_type", lambda session, prefix, no: "1")
    monkeypatch.setattr(client, "pass_captcha", lambda *args, **kwargs: "img-1")
    monkeypatch.setattr(client, "_submit_query", lambda *args, **kwargs: "<html></html>")

    def fake_parse_result(html: str):
        return {
            "booking": [
                {
                    "bookingNo": "63100251",
                    "flight": "CZ307",
                    "flightDate": "2026-05-01",
                    "fromStation": "CAN",
                    "toStation": "AMS",
                }
            ],
            "awbInfo": None,
            "milestones": {},
            "cargoState": [],
            "combine": [],
            "errorInfo": "运单信息不存在",
        }

    monkeypatch.setattr(client, "parse_result", fake_parse_result)
    monkeypatch.setattr(
        client,
        "query_active_flight",
        lambda *args, **kwargs: [
            {
                "flightNo": "CZ307",
                "leg": "CAN-AMS",
                "depPlanTime": "2026-05-01 01:00:00",
                "depActualTime": None,
                "arrPlanTime": None,
                "arrActualTime": None,
            }
        ],
    )

    result = client.query_awb("784", "83706910")

    assert result["awbInfo"] is None
    assert result["errorInfo"] == "运单信息不存在"
    assert result["booking"][0]["depPlanTime"] == "2026-05-01 01:00:00"


class _SessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return None

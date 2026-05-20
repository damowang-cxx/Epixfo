from __future__ import annotations

from datetime import date

import pytest

from app.adapters.carrier_query.csair import active_flight, client
from app.adapters.carrier_query.csair.captcha import CaptchaFailed


def _active_flight_html() -> str:
    return """
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


def test_query_active_flight_uses_active_flight_referer(monkeypatch: pytest.MonkeyPatch) -> None:
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

    rows = active_flight.query_active_flight(Session(), "CZ307", date(2026, 5, 20))

    assert captured["referer_url"] == active_flight.ACTIVE_FLIGHT_URL
    assert captured["debug_label"] == "active_flight_captcha"
    assert captured["headers"]["Referer"] == active_flight.ACTIVE_FLIGHT_URL
    assert captured["form"]["ctl00$ContentPlaceHolder1$txtImgId"] == "img-1"
    assert rows[0]["depPlanTime"] == "2026-05-20 00:20:00"


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

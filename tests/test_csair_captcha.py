from __future__ import annotations

import pytest

from app.adapters.carrier_query.csair import captcha


class _Response:
    def __init__(self, text: str = "", status_code: int = 200, payload=None):
        self.text = text
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status={self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_fetch_captcha_payload_uses_page_referer(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Session:
        def get(self, url, params=None, headers=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            return _Response('jQuery_x({"id":"abc","status":200,"message":"ok"})')

    monkeypatch.setattr(captcha, "_getid_params", lambda: {"callback": "jQuery_x"})

    payload = captcha.fetch_captcha_payload(
        Session(),
        referer_url="https://tang.csair.com/WebFace/Tang.WebFace.ActiveFlight/NewActiveFlightQuery.aspx?menuID=1",
    )

    assert payload["id"] == "abc"
    assert captured["headers"]["Referer"].endswith("NewActiveFlightQuery.aspx?menuID=1")


def test_validate_detail_uses_page_referer() -> None:
    captured: dict[str, object] = {}

    class Session:
        def post(self, url, params=None, headers=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return _Response('{"resultCode":0}', payload={"resultCode": 0})

    result = captcha.validate_detail(
        Session(),
        "img-1",
        123,
        referer_url="https://tang.csair.com/WebFace/Tang.WebFace.Cargo/AgentAwbBrower.aspx?menuID=1",
    )

    assert result.ok is True
    assert captured["params"] == {"imgid": "img-1", "slidex": 123}
    assert captured["headers"]["Referer"].endswith("AgentAwbBrower.aspx?menuID=1")


def test_pass_captcha_tries_positive_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    monkeypatch.setattr(captcha, "extract_captcha", lambda session, referer_url=None: ("img-1", b"big", b"small"))
    monkeypatch.setattr(captcha, "solve_slide", lambda bg, sl: 10)

    def fake_validate_detail(session, img_id, slide_x, timeout=15, referer_url=None):
        calls.append(slide_x)
        return captcha.CaptchaValidation(slide_x=slide_x, ok=slide_x == 11)

    monkeypatch.setattr(captcha, "validate_detail", fake_validate_detail)

    assert captcha.pass_captcha(object(), retries=1, retry_sleep=0, offset_range=2) == "img-1"
    assert calls == [10, 9, 11]


def test_pass_captcha_tries_negative_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    monkeypatch.setattr(captcha, "extract_captcha", lambda session, referer_url=None: ("img-1", b"big", b"small"))
    monkeypatch.setattr(captcha, "solve_slide", lambda bg, sl: 10)

    def fake_validate_detail(session, img_id, slide_x, timeout=15, referer_url=None):
        calls.append(slide_x)
        return captcha.CaptchaValidation(slide_x=slide_x, ok=slide_x == 8)

    monkeypatch.setattr(captcha, "validate_detail", fake_validate_detail)

    assert captcha.pass_captcha(object(), retries=1, retry_sleep=0, offset_range=2) == "img-1"
    assert calls == [10, 9, 11, 8]


def test_pass_captcha_raises_with_rejection_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(captcha, "extract_captcha", lambda session, referer_url=None: ("img-1", b"big", b"small"))
    monkeypatch.setattr(captcha, "solve_slide", lambda bg, sl: 10)
    monkeypatch.setattr(
        captcha,
        "validate_detail",
        lambda session, img_id, slide_x, timeout=15, referer_url=None: captcha.CaptchaValidation(
            slide_x=slide_x,
            ok=False,
            status_code=200,
            response_json={"resultCode": 1},
        ),
    )

    with pytest.raises(captcha.CaptchaFailed) as exc:
        captcha.pass_captcha(object(), retries=1, retry_sleep=0, offset_range=1, debug_label="active_flight_captcha")

    assert "active_flight_captcha" in str(exc.value)
    assert "last_rejections" in str(exc.value)

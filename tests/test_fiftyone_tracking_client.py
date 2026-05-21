import json
from pathlib import Path

import pytest
import requests

from app.adapters.carrier_query.fiftyone_tracking import (
    FiftyOneTrackingAircargoClient,
    build_verify_signature,
    normalize_air_waybill,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fiftyone_tracking_aircargo_sample.json"


class _Response:
    def __init__(self, text: str, *, ok: bool = True, status_code: int = 200, url: str = "https://example.test") -> None:
        self.text = text
        self.ok = ok
        self.status_code = status_code
        self.url = url


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.cookies = requests.cookies.RequestsCookieJar()

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        next_response = self.responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response


def _load_sample() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_normalize_air_waybill_and_signature_are_stable() -> None:
    awb = normalize_air_waybill(" 784-83633734 ")
    assert awb.digits == "78483633734"
    assert awb.formatted == "784-83633734"

    signature = build_verify_signature("784-83633734", 1779347612000)
    assert signature.cookie_value == "4998103c82d8e6dbf417150d1771ce60"
    assert signature.signature == "88fd848086958e100a4ee1063156269c"


def test_query_runs_verify_and_tracking_requests(tmp_path: Path) -> None:
    verify = {"code": 200, "message": "Success", "data": {"support": [{"track_number": "784-83633734", "validate": "abc", "time": 123}]}}
    tracking = {
        "784-83633734": {
            "track_number": "784-83633734",
            "return_data": {
                "status_number": 1,
                "weight": "10",
                "piece": "2",
                "origin": "CAN",
                "destination": "AMS",
                "track_info": [],
                "flight_info_new": [],
            },
            "air_info": {"name": "China Southern"},
        }
    }
    session = _Session([
        _Response(json.dumps(verify)),
        _Response(f"###{json.dumps(tracking)}###"),
    ])
    client = FiftyOneTrackingAircargoClient(session=session, cache_dir=tmp_path, cache_ttl_seconds=-1)

    result = client.query("78483633734", use_cache=False)

    assert result["found"] is True
    assert result["orders"][0]["route"]["origin"]["code"] == "CAN"
    assert len(session.requests) == 2
    assert session.requests[0][2]["params"]["action"] == "Verify"
    assert session.requests[1][2]["params"]["action"] == "Tracking"


def test_query_returns_cache_hit_without_network(tmp_path: Path) -> None:
    cached = _load_sample()
    cache_path = tmp_path / "78483633734.json"
    cache_path.write_text(json.dumps(cached), encoding="utf-8")
    session = _Session([AssertionError("network should not be called")])
    client = FiftyOneTrackingAircargoClient(session=session, cache_dir=tmp_path, cache_ttl_seconds=-1)

    result = client.query("78483633734")

    assert result["cache"]["hit"] is True
    assert result["cache"]["stale"] is False
    assert session.requests == []


def test_query_returns_stale_cache_when_live_request_fails(tmp_path: Path) -> None:
    cached = _load_sample()
    cached["cache"]["fetchedAt"] = "2020-01-01T00:00:00Z"
    cache_path = tmp_path / "78483633734.json"
    cache_path.write_text(json.dumps(cached), encoding="utf-8")
    session = _Session([requests.ConnectionError("timeout")])
    client = FiftyOneTrackingAircargoClient(session=session, cache_dir=tmp_path, cache_ttl_seconds=1)

    result = client.query("78483633734")

    assert result["cache"]["hit"] is True
    assert result["cache"]["stale"] is True
    assert result["cache"]["error"]["message"].startswith("Request failed:")


def test_query_unsupported_awb_returns_not_found_shape(tmp_path: Path) -> None:
    verify = {"code": 200, "message": "Success", "data": {"support": []}}
    session = _Session([_Response(json.dumps(verify))])
    client = FiftyOneTrackingAircargoClient(session=session, cache_dir=tmp_path)

    result = client.query("99912345678", use_cache=False)

    assert result["found"] is False
    assert result["orders"] == []

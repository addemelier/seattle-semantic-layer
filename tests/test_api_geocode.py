"""GET /api/geocode with the City locator stubbed by respx (permit-api spec)."""

import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from permitmap.app.config import Config
from permitmap.app.main import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "geocoder_candidates_sample.json"
URL = "https://locator.example.test/GeocodeServer/findAddressCandidates"


@pytest.fixture
def client(tmp_path):
    app = create_app(Config(lake_catalog=str(tmp_path / "none.sqlite"), geocoder_url=URL))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample():
    return json.loads(FIXTURE.read_text())


@respx.mock
def test_good_match(client, sample):
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=sample))
    r = client.get("/api/geocode", params={"q": "  1234 Sample Ave N  "})
    assert r.status_code == 200
    assert r.json() == {"lat": 47.634567, "lon": -122.345678,
                        "matched_address": "1234 SAMPLE AVE N, SEATTLE, WA, 98109", "score": 100}
    sent = route.calls.last.request.url.params
    assert sent["SingleLine"] == "1234 Sample Ave N"
    assert sent["outSR"] == "4326"
    assert sent["f"] == "json"


@respx.mock
def test_weak_match_404(client, sample):
    weak = dict(sample, candidates=[dict(sample["candidates"][1], score=62)])
    respx.get(URL).mock(return_value=httpx.Response(200, json=weak))
    r = client.get("/api/geocode", params={"q": "1234 Sample Ave"})
    assert r.status_code == 404
    assert r.json()["error"]


@respx.mock
def test_no_candidates_404(client):
    respx.get(URL).mock(return_value=httpx.Response(200, json={"candidates": []}))
    assert client.get("/api/geocode", params={"q": "nowhere"}).status_code == 404


@respx.mock
def test_timeout_502(client):
    respx.get(URL).mock(side_effect=httpx.ReadTimeout("timed out"))
    r = client.get("/api/geocode", params={"q": "1234 Sample Ave"})
    assert r.status_code == 502
    assert r.json()["error"]


@respx.mock
def test_arcgis_error_body_502(client):
    respx.get(URL).mock(return_value=httpx.Response(
        200, json={"error": {"code": 400, "message": "Unable to complete operation."}}))
    assert client.get("/api/geocode", params={"q": "1234 Sample Ave"}).status_code == 502


@respx.mock
def test_http_error_502(client):
    respx.get(URL).mock(return_value=httpx.Response(500, text="boom"))
    assert client.get("/api/geocode", params={"q": "1234 Sample Ave"}).status_code == 502


@respx.mock
def test_malformed_json_502(client):
    respx.get(URL).mock(return_value=httpx.Response(200, text="<html>not json</html>"))
    assert client.get("/api/geocode", params={"q": "1234 Sample Ave"}).status_code == 502


@respx.mock
@pytest.mark.parametrize("q", ["ab", "  ab  ", "x" * 201, ""])
def test_query_length_400(client, q):
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"candidates": []}))
    assert client.get("/api/geocode", params={"q": q}).status_code == 400
    assert not route.called


@respx.mock
def test_query_bounds_ok(client, sample):
    respx.get(URL).mock(return_value=httpx.Response(200, json=sample))
    assert client.get("/api/geocode", params={"q": "abc"}).status_code == 200
    assert client.get("/api/geocode", params={"q": "x" * 200}).status_code == 200

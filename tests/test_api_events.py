"""POST /api/events (engagement-events delta), with fakeredis."""

import json
import time
from datetime import datetime, timezone

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient

from permitmap.app.config import Config
from permitmap.app.main import create_app
from permitmap.events import STREAM, hash_ip

SID = "0123456789abcdef0123456789abcdef"
UA = "pytest-agent/1.0"


def _app(tmp_path, r=None, **cfg):
    return create_app(Config(lake_catalog=str(tmp_path / "none.sqlite"), **cfg), redis_client=r)


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def client(tmp_path, r):
    with TestClient(_app(tmp_path, r)) as c:
        yield c


def _entries(r):
    return [fields for _, fields in r.xrange(STREAM)]


def test_valid_permit_click(client, r):
    resp = client.post("/api/events", headers={"User-Agent": UA},
                       json={"event_type": "permit_click", "session_id": SID,
                             "permit_id": "6999001-CN", "lat": 47.61, "lon": -122.33})
    assert resp.status_code == 204
    assert resp.content == b""
    [e] = _entries(r)
    assert e["permit_id"] == "6999001-CN"
    assert e["user_agent"] == UA
    assert "ip" not in e


@pytest.mark.parametrize("body", [
    {"event_type": "page_view", "session_id": SID},
    {"event_type": "search", "session_id": "ABC"},
    {"event_type": "search", "session_id": SID.upper()},
    {"event_type": "search", "session_id": SID, "search_text": "x" * 201},
    {"event_type": "search", "session_id": SID, "ip": "1.2.3.4"},
    {"event_type": "search", "session_id": SID, "user_agent": "me"},
    {"event_type": "filter_change", "session_id": SID, "filters": {"valuation": ["1"]}},
    {"event_type": "filter_change", "session_id": SID, "filters": {"stage": "issued"}},
    {"event_type": "map_move", "session_id": SID, "lat": "47.6", "lon": -122.3},
    {"event_type": "permit_click", "session_id": SID, "permit_id": "x" * 65},
    {"event_type": "search", "session_id": SID, "referrer": "x" * 501},
    ["not", "an", "object"],
])
def test_bad_events_are_400_and_write_nothing(client, r, body):
    assert client.post("/api/events", json=body).status_code == 400
    assert _entries(r) == []


def test_unexpected_field_is_named(client):
    resp = client.post("/api/events", json={"event_type": "search", "session_id": SID, "ip": "1.2.3.4"})
    assert "ip" in resp.json()["error"]


def test_body_over_2kb_is_413(client, r):
    body = json.dumps({"event_type": "search", "session_id": SID, "referrer": "x" * 3000})
    assert len(body) > 3000
    resp = client.post("/api/events", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 413
    assert _entries(r) == []


def test_no_redis_is_503_disabled(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        resp = c.post("/api/events", json={"event_type": "search", "session_id": SID})
    assert resp.status_code == 503
    assert resp.json() == {"error": "events disabled"}


class _DownRedis:
    def xadd(self, *a, **kw):
        raise redis.exceptions.ConnectionError("down")


def test_redis_down_is_503_unavailable(tmp_path):
    with TestClient(_app(tmp_path, _DownRedis())) as c:
        resp = c.post("/api/events", json={"event_type": "search", "session_id": SID})
    assert resp.status_code == 503
    assert resp.json() == {"error": "events unavailable"}


def test_unreachable_redis_url_answers_fast(tmp_path):
    # Real client, nothing listening: connection refused well within a second.
    app = _app(tmp_path, redis_url="redis://127.0.0.1:1/0")
    with TestClient(app) as c:
        t = time.monotonic()
        resp = c.post("/api/events", json={"event_type": "search", "session_id": SID})
        assert time.monotonic() - t < 2
    assert resp.status_code == 503 and resp.json() == {"error": "events unavailable"}


def test_trusted_proxy_uses_left_most_forwarded_ip(tmp_path, r, monkeypatch):
    monkeypatch.setenv("EVENT_IP_SALT", "pepper")
    with TestClient(_app(tmp_path, r, trust_proxy=True)) as c:
        resp = c.post("/api/events", json={"event_type": "search", "session_id": SID},
                      headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    assert resp.status_code == 204
    today = datetime.now(timezone.utc).date().isoformat()
    [e] = _entries(r)
    assert e["ip_hash"] == hash_ip("203.0.113.9", "pepper", today)


def test_untrusted_proxy_header_ignored(tmp_path, r, monkeypatch):
    monkeypatch.setenv("EVENT_IP_SALT", "pepper")
    with TestClient(_app(tmp_path, r)) as c:
        c.post("/api/events", json={"event_type": "search", "session_id": SID},
               headers={"X-Forwarded-For": "203.0.113.9"})
    today = datetime.now(timezone.utc).date().isoformat()
    [e] = _entries(r)
    assert e["ip_hash"] != hash_ip("203.0.113.9", "pepper", today)
    assert e["ip_hash"] == hash_ip("testclient", "pepper", today)


def test_config_from_env():
    cfg = Config.from_env({"REDIS_URL": "redis://localhost:6379/0", "PERMITMAP_TRUST_PROXY": "1"})
    assert cfg.redis_url == "redis://localhost:6379/0" and cfg.trust_proxy is True
    cfg = Config.from_env({"PERMITMAP_TRUST_PROXY": "true"})
    assert cfg.redis_url is None and cfg.trust_proxy is False

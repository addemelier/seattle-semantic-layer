from datetime import datetime, timezone

import fakeredis
import pytest

from permitmap.events import STREAM, record_event

IP = "203.0.113.42"
DAY1 = datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc)
DAY1_LATER = datetime(2026, 10, 5, 23, 59, tzinfo=timezone.utc)
DAY2 = datetime(2026, 10, 6, 0, 1, tzinfo=timezone.utc)


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def salted(monkeypatch):
    monkeypatch.setenv("EVENT_IP_SALT", "test-salt")


def _entries(r):
    return [fields for _id, fields in r.xrange(STREAM)]


def test_records_event_and_returns_id(r):
    eid = record_event(r, "search", "sess-1", search_text="1234 NW 65th St", now=DAY1)
    [e] = _entries(r)
    assert e["event_id"] == eid
    assert e["event_type"] == "search"
    assert e["session_id"] == "sess-1"
    assert e["search_text"] == "1234 NW 65th St"
    assert e["ts"] == DAY1.isoformat()


@pytest.mark.parametrize("etype", ["search", "permit_click", "filter_change", "map_move", "list_open"])
def test_all_allowed_types(r, etype):
    record_event(r, etype, "s")
    assert r.xlen(STREAM) == 1


def test_unknown_event_type_rejected(r):
    with pytest.raises(ValueError):
        record_event(r, "purchase", "sess-1")
    assert r.xlen(STREAM) == 0


def test_map_position_is_coarsened(r):
    record_event(r, "map_move", "s", lat=47.668123, lon=-122.384567)
    [e] = _entries(r)
    assert e["lat"] == "47.668"
    assert e["lon"] == "-122.385"


def test_optional_fields(r):
    record_event(r, "permit_click", "s", permit_id="6999003-CN", filters={"stage": ["issued"]},
                 user_agent="UA/1.0", referrer="https://example.org/")
    [e] = _entries(r)
    assert e["permit_id"] == "6999003-CN"
    assert e["filters"] == '{"stage": ["issued"]}'
    assert e["user_agent"] == "UA/1.0"
    assert e["referrer"] == "https://example.org/"
    assert "search_text" not in e


def test_same_ip_same_day_equal_hash_and_no_raw_ip(r, salted):
    record_event(r, "search", "a", ip=IP, now=DAY1)
    record_event(r, "search", "b", ip=IP, now=DAY1_LATER)
    e1, e2 = _entries(r)
    assert e1["ip_hash"] == e2["ip_hash"]
    assert len(e1["ip_hash"]) == 64
    for e in (e1, e2):
        assert all(IP not in str(k) and IP not in str(v) for k, v in e.items())


def test_same_ip_next_day_different_hash(r, salted):
    record_event(r, "search", "a", ip=IP, now=DAY1)
    record_event(r, "search", "a", ip=IP, now=DAY2)
    e1, e2 = _entries(r)
    assert e1["ip_hash"] != e2["ip_hash"]


def test_no_salt_discards_ip(r, monkeypatch):
    monkeypatch.delenv("EVENT_IP_SALT", raising=False)
    record_event(r, "search", "a", ip=IP, now=DAY1)
    [e] = _entries(r)
    assert "ip_hash" not in e
    assert all(IP not in str(v) for v in e.values())


def test_xadd_uses_approximate_maxlen(r, monkeypatch):
    calls = []
    real = r.xadd

    def spy(name, fields, **kw):
        calls.append((name, kw))
        return real(name, fields, **kw)

    monkeypatch.setattr(r, "xadd", spy)
    record_event(r, "search", "a")
    assert calls == [(STREAM, {"maxlen": 1_000_000, "approximate": True})]

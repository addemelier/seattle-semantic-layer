"""Anonymous engagement events, written live to a Redis Stream.

No login and no raw IPs. If an IP is given, only SHA-256(salt + UTC date + IP)
is stored, so the same visitor hashes the same within a UTC day and differently
across days. The salt comes from env EVENT_IP_SALT; with no salt the IP is
discarded and ip_hash is left out.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

STREAM = "events:v1"
MAXLEN = 1_000_000
EVENT_TYPES = frozenset({"search", "permit_click", "filter_change", "map_move", "list_open"})

# Every field an event can carry, in a fixed order (the drain uses this as its schema).
FIELDS = (
    "event_id", "ts", "event_type", "session_id", "search_text", "lat", "lon",
    "filters", "permit_id", "user_agent", "referrer", "ip_hash",
)


def hash_ip(ip: str, salt: str, day: str) -> str:
    """SHA-256 hex of salt + UTC date (YYYY-MM-DD) + IP."""
    return hashlib.sha256(f"{salt}{day}{ip}".encode()).hexdigest()


def record_event(
    r: Any,
    event_type: str,
    session_id: str,
    *,
    search_text: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    filters: dict | None = None,
    permit_id: str | None = None,
    user_agent: str | None = None,
    referrer: str | None = None,
    ip: str | None = None,
    now: datetime | None = None,
) -> str:
    """Validate an event, XADD it to events:v1 and return its event_id.

    Raises ValueError (and writes nothing) for an unknown event type or a missing session id.
    Null fields are left out of the stream entry.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type {event_type!r}; allowed: {sorted(EVENT_TYPES)}")
    if not session_id:
        raise ValueError("session_id is required")

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    salt = os.environ.get("EVENT_IP_SALT") or None
    ip_hash = hash_ip(ip, salt, now.date().isoformat()) if (ip and salt) else None

    event = {
        "event_id": uuid.uuid4().hex,
        "ts": now.isoformat(),
        "event_type": event_type,
        "session_id": session_id,
        "search_text": search_text,
        "lat": None if lat is None else repr(round(float(lat), 3)),
        "lon": None if lon is None else repr(round(float(lon), 3)),
        "filters": None if filters is None else json.dumps(filters, sort_keys=True),
        "permit_id": permit_id,
        "user_agent": user_agent,
        "referrer": referrer,
        "ip_hash": ip_hash,
    }
    fields = {k: v for k, v in event.items() if v is not None}
    r.xadd(STREAM, fields, maxlen=MAXLEN, approximate=True)
    return event["event_id"]

"""How fresh the permit data is, from lake.bronze.ingest_runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import duckdb

from permitmap.app.config import STALE_AFTER_HOURS


def data_freshness(cursor: duckdb.DuckDBPyConnection, now: datetime) -> tuple[str | None, bool | None]:
    """Return (data_as_of, data_fresh).

    data_as_of is the finish time (UTC, ISO 8601 with Z) of the latest accepted ingest
    run, or None when there is none (fixture data, or no ingest_runs table yet).
    data_fresh is whether that is within STALE_AFTER_HOURS of `now`, or None.
    """
    try:
        row = cursor.execute(
            "SELECT max(finished_at) FROM lake.bronze.ingest_runs WHERE status = 'accepted'"
        ).fetchone()
    except duckdb.Error:
        return None, None
    if row is None or row[0] is None:
        return None, None
    finished = row[0].replace(tzinfo=timezone.utc)  # stored as naive UTC
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    fresh = now - finished <= timedelta(hours=STALE_AFTER_HOURS)
    return finished.strftime("%Y-%m-%dT%H:%M:%SZ"), fresh

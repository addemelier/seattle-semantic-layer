"""One ingest run: fetch → load/check → swap → log to lake.bronze.ingest_runs."""

from __future__ import annotations

import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from permitmap.app.config import Config
from permitmap.ingest.load import INGEST_RUNS, ensure_ingest_runs, load_snapshot
from permitmap.ingest.socrata import FetchFailed, fetch_pages
from permitmap.lake import connect_lake


@dataclass(frozen=True)
class RunResult:
    run_id: str
    started_at: datetime
    finished_at: datetime
    rows_fetched: int
    rows_valid: int
    rows_quarantined: int
    status: str  # "accepted" or "rejected"
    reason: str | None

    def summary(self) -> str:
        line = (f"ingest {self.status}: run {self.run_id}, fetched {self.rows_fetched}, "
                f"valid {self.rows_valid}, quarantined {self.rows_quarantined}")
        return f"{line} ({self.reason})" if self.reason else line


class IngestRejected(Exception):
    """The run was rejected (and logged); bronze and gold were left unchanged."""

    def __init__(self, result: RunResult):
        super().__init__(result.reason)
        self.result = result


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_ingest(config: Config, client: httpx.Client | None = None, *, page_size: int = 50000,
               sleep: Callable[[float], None] = time.sleep) -> RunResult:
    """Pull the full snapshot and swap it into bronze, or reject it.

    Every run appends one row to lake.bronze.ingest_runs. Raises IngestRejected
    after logging a rejected run.
    """
    run_id = str(uuid.uuid4())
    started = _utcnow()
    own_client = client is None
    client = client or httpx.Client()
    con = connect_lake(config.lake_catalog, config.lake_data)
    try:
        ensure_ingest_runs(con)
        with tempfile.TemporaryDirectory(prefix="permitmap-ingest-") as tmp:
            try:
                paths = fetch_pages(client, config.socrata_url, Path(tmp), page_size=page_size,
                                    sleep=sleep)
            except FetchFailed as e:
                fetched = valid = quarantined = 0
                accepted, reason = False, f"fetch failed: {e}"
            else:
                out = load_snapshot(con, paths, run_id)
                fetched, valid, quarantined = out.rows_fetched, out.rows_valid, out.rows_quarantined
                accepted, reason = out.accepted, out.reason
        result = RunResult(run_id, started, _utcnow(), fetched, valid, quarantined,
                           "accepted" if accepted else "rejected", reason)
        con.execute(f"INSERT INTO {INGEST_RUNS} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [result.run_id, result.started_at, result.finished_at, result.rows_fetched,
                     result.rows_valid, result.rows_quarantined, result.status, result.reason])
    finally:
        con.close()
        if own_client:
            client.close()
    if not accepted:
        raise IngestRejected(result)
    return result

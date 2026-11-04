"""Guarded load of a pulled snapshot into lake.bronze.sdci_building_permits.

The pull lands in a side table first. It is swapped into bronze (valid rows) and
the quarantine table (malformed rows) in one transaction only when every required
column is present and the valid row count is at least 90% of the last accepted
run. Otherwise the side table is dropped and bronze is left untouched.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb

from permitmap.ingest.columns import REQUIRED_COLUMNS

BRONZE = "lake.bronze.sdci_building_permits"
INCOMING = "lake.bronze.sdci_building_permits__incoming"
QUARANTINE = "lake.bronze.sdci_building_permits_quarantine"
INGEST_RUNS = "lake.bronze.ingest_runs"
MIN_SHARE_OF_BASELINE = 0.9

_REASON_SQL = """
    CASE
        WHEN trim(coalesce(permitnum, '')) = '' THEN 'blank_permitnum'
        WHEN (trim(coalesce(latitude, '')) <> '' AND try_cast(trim(latitude) AS DOUBLE) IS NULL)
          OR (trim(coalesce(longitude, '')) <> '' AND try_cast(trim(longitude) AS DOUBLE) IS NULL)
            THEN 'bad_coordinates'
    END
"""


@dataclass(frozen=True)
class LoadOutcome:
    accepted: bool
    rows_fetched: int
    rows_valid: int
    rows_quarantined: int
    reason: str | None = None


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def ensure_ingest_runs(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS lake.bronze")
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {INGEST_RUNS} (
            run_id VARCHAR, started_at TIMESTAMP, finished_at TIMESTAMP,
            rows_fetched BIGINT, rows_valid BIGINT, rows_quarantined BIGINT,
            status VARCHAR, reason VARCHAR
        )""")


def last_accepted_valid_rows(con: duckdb.DuckDBPyConnection) -> int | None:
    row = con.execute(f"""
        SELECT rows_valid FROM {INGEST_RUNS}
        WHERE status = 'accepted' ORDER BY finished_at DESC LIMIT 1""").fetchone()
    return None if row is None else row[0]


def _land_incoming(con: duckdb.DuckDBPyConnection, csv_paths: Sequence[Path]) -> list[str]:
    """Create the side table with lower-cased, trimmed column names; return them."""
    paths = [str(p) for p in csv_paths]
    reader = "read_csv(?, header = true, all_varchar = true, union_by_name = true)"
    source_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {reader}", [paths]).fetchall()]
    cols = [c.strip().lower() for c in source_cols]
    select = ", ".join(f"{_q(s)} AS {_q(c)}" for s, c in zip(source_cols, cols))
    con.execute(f"DROP TABLE IF EXISTS {INCOMING}")
    con.execute(f"CREATE TABLE {INCOMING} AS SELECT {select} FROM {reader}", [paths])
    return cols


def load_snapshot(con: duckdb.DuckDBPyConnection, csv_paths: Sequence[Path],
                  run_id: str) -> LoadOutcome:
    """Check the pulled pages and swap them into bronze, or reject and change nothing."""
    ensure_ingest_runs(con)
    cols = _land_incoming(con, csv_paths)
    try:
        fetched = con.execute(f"SELECT count(*) FROM {INCOMING}").fetchone()[0]

        missing = [c for c in REQUIRED_COLUMNS if c not in cols]
        if missing:
            reason = f"missing columns: {', '.join(missing)}; present: {', '.join(cols)}"
            return LoadOutcome(False, fetched, 0, 0, reason)

        valid, quarantined = con.execute(f"""
            SELECT count(*) FILTER (WHERE r IS NULL), count(*) FILTER (WHERE r IS NOT NULL)
            FROM (SELECT {_REASON_SQL} AS r FROM {INCOMING})""").fetchone()

        baseline = last_accepted_valid_rows(con)
        if baseline is not None:
            minimum = math.ceil(MIN_SHARE_OF_BASELINE * baseline)
            if valid < minimum:
                reason = (f"shrink: {valid} valid rows vs {baseline} last accepted "
                          f"(min {minimum})")
                return LoadOutcome(False, fetched, valid, quarantined, reason)

        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"CREATE OR REPLACE TABLE {BRONZE} AS "
                        f"SELECT * FROM {INCOMING} WHERE ({_REASON_SQL}) IS NULL")
            con.execute(f"CREATE OR REPLACE TABLE {QUARANTINE} AS "
                        f"SELECT *, ?::VARCHAR AS run_id, {_REASON_SQL} AS quarantine_reason "
                        f"FROM {INCOMING} WHERE ({_REASON_SQL}) IS NOT NULL", [run_id])
            con.execute(f"DROP TABLE {INCOMING}")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        return LoadOutcome(True, fetched, valid, quarantined, None)
    finally:
        con.execute(f"DROP TABLE IF EXISTS {INCOMING}")

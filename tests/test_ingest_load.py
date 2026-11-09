"""Guarded bronze load: column check, quarantine, shrink check, idempotence."""

import csv
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from permitmap.ingest.load import (BRONZE, INGEST_RUNS, QUARANTINE, ensure_ingest_runs,
                                   load_snapshot)
from permitmap.lake import connect_lake

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdci_building_permits_sample.csv"


@pytest.fixture
def con(tmp_path):
    c = connect_lake(tmp_path / "catalog.sqlite", tmp_path / "files")
    yield c
    c.close()


def _fixture_rows() -> tuple[list[str], list[dict]]:
    with FIXTURE.open(newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames), list(reader)


def _write(path: Path, header: list[str], rows: list[dict]) -> Path:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=header, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    path.write_text(buf.getvalue())
    return path


def _generated(tmp_path: Path, n: int) -> Path:
    header, rows = _fixture_rows()
    base = rows[0]
    out = [{**base, "permitnum": f"G{i:05d}-CN"} for i in range(n)]
    return _write(tmp_path / f"gen-{n}.csv", header, out)


def _count(con, table: str) -> int:
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def _log_accepted(con, rows_valid: int) -> None:
    ensure_ingest_runs(con)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    con.execute(f"INSERT INTO {INGEST_RUNS} VALUES (?, ?, ?, ?, ?, 0, 'accepted', NULL)",
                [str(uuid.uuid4()), now, now, rows_valid, rows_valid])


def test_first_run_accepted(con):
    out = load_snapshot(con, [FIXTURE], "r1")
    assert out.accepted and out.reason is None
    assert out.rows_fetched == out.rows_valid == _count(con, BRONZE) == 41
    assert out.rows_quarantined == _count(con, QUARANTINE) == 0
    tables = {r[0] for r in con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE database_name = 'lake'").fetchall()}
    assert "sdci_building_permits__incoming" not in tables


def test_missing_column_rejected(con, tmp_path):
    load_snapshot(con, [FIXTURE], "r1")
    header, rows = _fixture_rows()
    bad = _write(tmp_path / "bad.csv", [h for h in header if h != "statuscurrent"], rows[:5])
    out = load_snapshot(con, [bad], "r2")
    assert not out.accepted
    present = ", ".join(h for h in header if h != "statuscurrent")
    assert out.reason == f"missing columns: statuscurrent; present: {present}"
    assert _count(con, BRONZE) == 41
    assert con.execute(f"SELECT count(*) FROM {BRONZE} WHERE statuscurrent IS NOT NULL").fetchone()[0] > 0


def test_shrink_rejected(con, tmp_path):
    load_snapshot(con, [_generated(tmp_path, 1000)], "r1")
    _log_accepted(con, 1000)
    out = load_snapshot(con, [_generated(tmp_path, 850)], "r2")
    assert not out.accepted
    assert out.reason == "shrink: 850 valid rows vs 1000 last accepted (min 900)"
    assert _count(con, BRONZE) == 1000


def test_normal_shrink_accepted(con, tmp_path):
    load_snapshot(con, [_generated(tmp_path, 1000)], "r1")
    _log_accepted(con, 1000)
    out = load_snapshot(con, [_generated(tmp_path, 950)], "r2")
    assert out.accepted
    assert _count(con, BRONZE) == 950


def _with_bad_rows(tmp_path: Path) -> Path:
    header, rows = _fixture_rows()
    extra = [{**rows[0], "permitnum": "  "}, {**rows[1], "permitnum": "BAD-LAT", "latitude": "n/a"},
             {**rows[2], "permitnum": "NO-LOC", "latitude": "", "longitude": ""}]
    return _write(tmp_path / "mixed.csv", header, rows + extra)


def test_quarantine(con, tmp_path):
    out = load_snapshot(con, [_with_bad_rows(tmp_path)], "r1")
    assert out.accepted
    assert (out.rows_fetched, out.rows_valid, out.rows_quarantined) == (44, 42, 2)
    q = dict(con.execute(f"SELECT coalesce(trim(permitnum), ''), quarantine_reason FROM {QUARANTINE}").fetchall())
    assert q == {"": "blank_permitnum", "BAD-LAT": "bad_coordinates"}
    assert con.execute(f"SELECT DISTINCT run_id FROM {QUARANTINE}").fetchall() == [("r1",)]
    bronze_ids = {r[0] for r in con.execute(f"SELECT permitnum FROM {BRONZE}").fetchall()}
    assert "BAD-LAT" not in bronze_ids and None not in bronze_ids
    assert "NO-LOC" in bronze_ids  # blank coordinates are kept (A5)


def test_rerun_is_idempotent(con, tmp_path):
    path = _with_bad_rows(tmp_path)
    load_snapshot(con, [path], "r1")
    first = (_count(con, BRONZE), _count(con, QUARANTINE))
    load_snapshot(con, [path], "r2")
    assert (_count(con, BRONZE), _count(con, QUARANTINE)) == first == (42, 2)


def test_multiple_pages(con, tmp_path):
    header, rows = _fixture_rows()
    a = _write(tmp_path / "page-0000.csv", header, rows[:20])
    b = _write(tmp_path / "page-0001.csv", header, rows[20:])
    assert load_snapshot(con, [a, b], "r1").rows_valid == 41

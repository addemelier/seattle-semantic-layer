"""Data freshness in /api/config and /healthz (permit-api delta)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from permitmap.app.config import Config
from permitmap.app.main import create_app
from permitmap.ingest.load import INGEST_RUNS, ensure_ingest_runs
from permitmap.lake import connect_lake

REPO = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)


def _client(catalog: Path, files: Path) -> TestClient:
    app = create_app(Config(lake_catalog=str(catalog), lake_data=str(files)))
    app.state.now = lambda: NOW
    return TestClient(app)


def test_fixture_lake_has_no_freshness():
    catalog = REPO / "data" / "lake" / "catalog.sqlite"
    if not catalog.exists():
        pytest.fail("lake not built: run load_fixture and dbt build first")
    with _client(catalog, REPO / "data" / "lake" / "files") as c:
        cfg = c.get("/api/config").json()
        assert cfg["data_as_of"] is None and cfg["data_fresh"] is None
        h = c.get("/healthz")
        assert h.status_code == 200
        assert h.json() == {"status": "ok", "data_as_of": None, "data_fresh": None}


@pytest.fixture
def lake(tmp_path):
    """A temp lake with a gold table and an empty ingest_runs; returns a run logger."""
    catalog, files = tmp_path / "catalog.sqlite", tmp_path / "files"
    con = connect_lake(catalog, files)
    con.execute("CREATE SCHEMA lake.gold")
    con.execute("CREATE TABLE lake.gold.fct_open_permits AS SELECT 'P1' AS permit_num")
    ensure_ingest_runs(con)
    con.close()

    def log(status: str, hours_ago: float) -> None:
        c = connect_lake(catalog, files)
        finished = (NOW - timedelta(hours=hours_ago)).replace(tzinfo=None)
        c.execute(f"INSERT INTO {INGEST_RUNS} VALUES ('r', ?, ?, 1, 1, 0, ?, NULL)",
                  [finished, finished, status])
        c.close()

    return catalog, files, log


def test_fresh_run(lake):
    catalog, files, log = lake
    log("accepted", 2)
    with _client(catalog, files) as c:
        cfg = c.get("/api/config").json()
        assert cfg["data_as_of"] == "2026-11-04T13:00:00Z"
        assert cfg["data_fresh"] is True


def test_stale_run_is_still_healthy(lake):
    catalog, files, log = lake
    log("accepted", 40)
    with _client(catalog, files) as c:
        assert c.get("/api/config").json()["data_fresh"] is False
        h = c.get("/healthz")
        assert h.status_code == 200
        assert h.json() == {"status": "ok", "data_as_of": "2026-11-02T23:00:00Z", "data_fresh": False}


def test_newer_rejected_run_ignored(lake):
    catalog, files, log = lake
    log("accepted", 2)
    log("rejected", 1)
    with _client(catalog, files) as c:
        assert c.get("/api/config").json()["data_as_of"] == "2026-11-04T13:00:00Z"


def test_empty_ingest_runs_is_null(lake):
    catalog, files, _ = lake
    with _client(catalog, files) as c:
        cfg = c.get("/api/config").json()
        assert (cfg["data_as_of"], cfg["data_fresh"]) == (None, None)

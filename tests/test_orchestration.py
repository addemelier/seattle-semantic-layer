"""Dagster definitions: schedule, job shape, and an in-process run on a temp lake."""

from pathlib import Path

import httpx
import respx
from dagster import AssetKey

from permitmap.app.config import Config
from permitmap.ingest.load import INGEST_RUNS
from permitmap.lake import connect_lake
from permitmap.orchestration.definitions import BRONZE_ASSET, defs

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdci_building_permits_sample.csv"
URL = "https://socrata.test/resource/76t5-zqzr.csv"
BRONZE = AssetKey(BRONZE_ASSET)
GOLD = AssetKey(["gold", "fct_open_permits"])


def test_defs_load():
    assert defs.resolve_job_def("daily_permits_refresh") is not None


def test_schedule():
    s = defs.resolve_schedule_def("daily_permits_refresh_schedule")
    assert s.cron_schedule == "0 5 * * *"
    assert s.execution_timezone == "America/Los_Angeles"
    assert s.job_name == "daily_permits_refresh"
    assert s.default_status.value == "RUNNING"


def _ancestors(graph, key: AssetKey) -> set[AssetKey]:
    seen: set[AssetKey] = set()
    todo = [key]
    while todo:
        for parent in graph.get(todo.pop()).parent_keys:
            if parent not in seen:
                seen.add(parent)
                todo.append(parent)
    return seen


def test_job_contains_bronze_upstream_of_gold():
    job = defs.resolve_job_def("daily_permits_refresh")
    selected = job.asset_layer.selected_asset_keys
    assert {BRONZE, GOLD} <= set(selected)
    assert BRONZE in _ancestors(defs.resolve_asset_graph(), GOLD)


def test_job_run_on_temp_lake(tmp_path, monkeypatch):
    catalog, files = tmp_path / "catalog.sqlite", tmp_path / "files"
    monkeypatch.setenv("PERMITMAP_LAKE_CATALOG", str(catalog))
    monkeypatch.setenv("PERMITMAP_LAKE_DATA", str(files))
    monkeypatch.setenv("PERMITMAP_SOCRATA_URL", URL)
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(200, text=FIXTURE.read_text()))
        result = defs.resolve_job_def("daily_permits_refresh").execute_in_process()
    assert result.success
    con = connect_lake(catalog, files)
    try:
        runs = con.execute(f"SELECT status, rows_valid FROM {INGEST_RUNS}").fetchall()
        gold = con.execute("SELECT count(*) FROM lake.gold.fct_open_permits").fetchone()[0]
    finally:
        con.close()
    assert runs == [("accepted", 41)]
    assert gold > 0
    assert Config.from_env().lake_catalog == str(catalog)

"""The app picks up the lake when it appears (permit-api delta, design A8)."""

import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from permitmap.app.config import Config
from permitmap.app.main import create_app
from permitmap.load_fixture import load_fixture

REPO = Path(__file__).resolve().parent.parent
BOX = "-122.46,47.48,-122.22,47.76"  # all of Seattle


def _build_lake(catalog: Path, files: Path) -> None:
    load_fixture(catalog=catalog, files=files)
    env = {**os.environ, "PERMITMAP_LAKE_CATALOG": str(catalog)}
    subprocess.run(
        ["dbt", "build", "--project-dir", "dbt", "--profiles-dir", "dbt",
         "-s", "+fct_open_permits", "--quiet"],
        cwd=REPO, env=env, check=True,
    )


def _ids(body: dict) -> set[str]:
    return {f["properties"]["permit_id"] for f in body["features"]}


def test_app_picks_up_lake_created_after_start(tmp_path):
    catalog, files = tmp_path / "lake" / "catalog.sqlite", tmp_path / "lake" / "files"
    app = create_app(Config(lake_catalog=str(catalog), lake_data=str(files)))
    with TestClient(app) as c:
        assert c.get("/healthz").status_code == 503
        assert c.get("/api/permits", params={"bbox": BOX}).status_code == 503
        cfg = c.get("/api/config")
        assert cfg.status_code == 200
        assert cfg.json()["data_as_of"] is None and cfg.json()["data_fresh"] is None
        assert not catalog.exists(), "the app must never create a catalog"

        _build_lake(catalog, files)

        assert c.get("/healthz").status_code == 200
        r = c.get("/api/permits", params={"bbox": BOX})
        assert r.status_code == 200
        assert len(r.json()["features"]) > 0


INSERT_SCRIPT = """
import sys
from permitmap.lake import connect_lake
con = connect_lake(sys.argv[1], sys.argv[2])
con.execute(
    "INSERT INTO lake.gold.fct_open_permits (permit_id, address, work_type, stage, "
    "status_raw, applied_date, latitude, longitude) VALUES "
    "('XPROC-1', '1 TEST ST', 'new_building', 'issued', 'Issued', DATE '2026-11-01', "
    "47.62, -122.34)"
)
con.close()
"""


def test_commit_from_another_process_is_visible(tmp_path):
    catalog, files = tmp_path / "lake" / "catalog.sqlite", tmp_path / "lake" / "files"
    _build_lake(catalog, files)
    app = create_app(Config(lake_catalog=str(catalog), lake_data=str(files)))
    with TestClient(app) as c:
        first = c.get("/api/permits", params={"bbox": BOX})
        assert first.status_code == 200
        assert "XPROC-1" not in _ids(first.json())

        subprocess.run([sys.executable, "-c", INSERT_SCRIPT, str(catalog), str(files)],
                       cwd=REPO, check=True)

        second = c.get("/api/permits", params={"bbox": BOX})
        assert second.status_code == 200
        assert "XPROC-1" in _ids(second.json())

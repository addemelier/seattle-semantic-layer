"""First-pull bootstrap (deployment spec "A fresh server gets real data on its own")."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from permitmap.deploy import bootstrap
from permitmap.ingest.load import INGEST_RUNS, ensure_ingest_runs
from permitmap.lake import connect_lake
from permitmap.load_fixture import load_fixture

REPO = Path(__file__).resolve().parent.parent
REAL_RUN = subprocess.run


class _Done:
    def __init__(self, returncode):
        self.returncode = returncode


@pytest.fixture
def lake(tmp_path, monkeypatch):
    catalog, files = tmp_path / "lake" / "catalog.sqlite", tmp_path / "lake" / "files"
    monkeypatch.setenv("PERMITMAP_LAKE_CATALOG", str(catalog))
    monkeypatch.setenv("PERMITMAP_LAKE_DATA", str(files))
    return catalog, files


@pytest.fixture
def launches(monkeypatch):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return _Done(0)

    monkeypatch.setattr(subprocess, "run", run)
    return calls


def _log_run(catalog, files, status):
    con = connect_lake(catalog, files)
    ensure_ingest_runs(con)
    con.execute(f"INSERT INTO {INGEST_RUNS} VALUES ('r', now(), now(), 1, 1, 0, ?, NULL)",
                [status])
    con.close()


def _is_ingest(cmd):
    return cmd == [sys.executable, "-m", "permitmap.ingest"]


def test_no_catalog_launches_ingest(lake, launches):
    catalog, _ = lake
    assert bootstrap.main() == 0
    assert len(launches) == 1 and _is_ingest(launches[0])
    assert not catalog.exists(), "bootstrap must not create a catalog itself"


def test_fixture_lake_without_ingest_runs_launches(lake, launches):
    catalog, files = lake
    load_fixture(catalog=catalog, files=files)
    assert bootstrap.main() == 0
    assert len(launches) == 1 and _is_ingest(launches[0])


def test_only_rejected_run_launches(lake, launches):
    catalog, files = lake
    _log_run(catalog, files, "rejected")
    assert bootstrap.main() == 0
    assert len(launches) == 1


def test_accepted_run_skips(lake, launches, capsys):
    catalog, files = lake
    _log_run(catalog, files, "rejected")
    _log_run(catalog, files, "accepted")
    assert bootstrap.main() == 0
    assert launches == []
    assert "bootstrap: accepted run exists, skipping" in capsys.readouterr().out


def test_failed_ingest_still_returns_0(lake, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Done(1))
    assert bootstrap.main() == 0


def test_raising_subprocess_still_returns_0(lake, monkeypatch, capsys):
    def boom(cmd, **kw):
        raise OSError("no such interpreter")

    monkeypatch.setattr(subprocess, "run", boom)
    assert bootstrap.main() == 0
    assert "starting the daemon anyway" in capsys.readouterr().out


def test_dagster_yaml_loads(tmp_path):
    cfg = yaml.safe_load((REPO / "deploy" / "dagster.yaml").read_text())
    cfg["storage"]["sqlite"]["base_dir"] = str(tmp_path / "storage")
    cfg["local_artifact_storage"]["config"]["base_dir"] = str(tmp_path / "artifacts")
    home = tmp_path / "home"
    home.mkdir()
    (home / "dagster.yaml").write_text(yaml.safe_dump(cfg))
    env = {**os.environ, "DAGSTER_HOME": str(home)}
    res = REAL_RUN([sys.executable, "-c",
                    "from dagster import DagsterInstance; DagsterInstance.get()"],
                   env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr

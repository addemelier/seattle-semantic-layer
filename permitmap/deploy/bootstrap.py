"""Run the first real pull when the lake has never had an accepted ingest run.

Usage: python -m permitmap.deploy.bootstrap   (run by deploy/entrypoint-daemon.sh)

Design D5 and A9: on a fresh server the daemon pulls once before starting the
schedule. Whatever happens, this exits 0 so the daemon (and the 5:00am schedule)
always starts.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb

from permitmap.app.config import Config
from permitmap.ingest.load import INGEST_RUNS
from permitmap.lake import connect_lake

REPO = Path(__file__).resolve().parents[2]
CONTAINER_APP_DIR = Path("/app")


def needs_bootstrap(config: Config) -> bool:
    """True when there is no catalog, no ingest_runs table, or no accepted run in it."""
    # Never create a catalog here: only open one that already exists.
    if not Path(config.lake_catalog).is_file():
        return True
    con = connect_lake(config.lake_catalog, config.lake_data)
    try:
        try:
            row = con.execute(
                f"SELECT count(*) FROM {INGEST_RUNS} WHERE status = 'accepted'").fetchone()
        except duckdb.CatalogException:
            return True  # lake exists but ingest_runs doesn't
        return row[0] == 0
    finally:
        con.close()


def _workdir() -> Path:
    return CONTAINER_APP_DIR if (CONTAINER_APP_DIR / "permitmap").is_dir() else REPO


def main() -> int:
    try:
        config = Config.from_env()
        if not needs_bootstrap(config):
            print("bootstrap: accepted run exists, skipping")
            return 0
        print("bootstrap: no accepted ingest run yet, running the first pull")
        res = subprocess.run([sys.executable, "-m", "permitmap.ingest"], cwd=_workdir())
        if res.returncode == 0:
            print("bootstrap: first pull accepted and built")
        else:
            print(f"bootstrap: first pull exited {res.returncode}; "
                  "see lake.bronze.ingest_runs; the 5:00am schedule will retry")
    except Exception as e:  # noqa: BLE001 - never stop the daemon (A9)
        print(f"bootstrap: failed ({type(e).__name__}: {e}); starting the daemon anyway")
    return 0


if __name__ == "__main__":
    sys.exit(main())

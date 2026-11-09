"""Run one ingest, then rebuild silver and gold: python -m permitmap.ingest

Exits 1 when the pull is rejected or dbt fails; prints the run summary.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx

from permitmap.app.config import Config
from permitmap.ingest.pipeline import IngestRejected, run_ingest

REPO = Path(__file__).resolve().parents[2]
DBT_DIR = REPO / "dbt"


def run_dbt(config: Config) -> bool:
    """dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits, on config's lake."""
    from dbt.cli.main import dbtRunner

    previous = os.environ.get("PERMITMAP_LAKE_CATALOG")
    os.environ["PERMITMAP_LAKE_CATALOG"] = Path(config.lake_catalog).resolve().as_posix()
    try:
        res = dbtRunner().invoke(["build", "--project-dir", str(DBT_DIR),
                                  "--profiles-dir", str(DBT_DIR), "-s", "+fct_open_permits"])
    finally:
        if previous is None:
            os.environ.pop("PERMITMAP_LAKE_CATALOG", None)
        else:
            os.environ["PERMITMAP_LAKE_CATALOG"] = previous
    return bool(res.success)


def main(argv: Sequence[str] | None = None, *, config: Config | None = None,
         client: httpx.Client | None = None, page_size: int = 50000,
         sleep: Callable[[float], None] = time.sleep) -> int:
    config = config or Config.from_env()
    try:
        result = run_ingest(config, client, page_size=page_size, sleep=sleep)
    except IngestRejected as e:
        print(e.result.summary())
        return 1
    print(result.summary())
    if not run_dbt(config):
        print("dbt build failed; bronze holds the new pull, gold the previous build")
        return 1
    print("dbt build succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

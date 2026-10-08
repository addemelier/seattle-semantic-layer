"""Load the synthetic SDCI permits fixture into lake.bronze.sdci_building_permits.

Usage: python -m permitmap.load_fixture

Every column is loaded as VARCHAR (bronze keeps the source as-is). The table is
replaced on each run, so the load is idempotent.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from permitmap.lake import connect_lake

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO / "tests" / "fixtures" / "sdci_building_permits_sample.csv"
DEFAULT_CATALOG = REPO / "data" / "lake" / "catalog.sqlite"
DEFAULT_FILES = REPO / "data" / "lake" / "files"


def load_fixture(csv_path: Path = DEFAULT_CSV, catalog: Path = DEFAULT_CATALOG,
                 files: Path = DEFAULT_FILES) -> int:
    con = connect_lake(catalog, files)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS lake.bronze")
        con.execute("DROP TABLE IF EXISTS lake.bronze.sdci_building_permits")
        con.execute(
            "CREATE TABLE lake.bronze.sdci_building_permits AS "
            "SELECT * FROM read_csv(?, header = true, all_varchar = true)",
            [str(csv_path)],
        )
        return con.execute("SELECT count(*) FROM lake.bronze.sdci_building_permits").fetchone()[0]
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--files", type=Path, default=DEFAULT_FILES)
    args = parser.parse_args()
    n = load_fixture(args.csv, args.catalog, args.files)
    print(f"loaded {n} rows into lake.bronze.sdci_building_permits")


if __name__ == "__main__":
    main()

"""Offline DuckLake connection helper.

DuckLake and sqlite_scanner are loaded from PyPI wheels (duckdb-extension-*),
so no request to extensions.duckdb.org is ever made.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
from duckdb_extensions import import_extension

_EXTENSIONS = ("sqlite_scanner", "ducklake")


def load_extensions(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """Install the bundled extension wheels into DuckDB's local extension dir, then load them."""
    for name in _EXTENSIONS:
        import_extension(name)
        if con is not None:
            con.load_extension(name)


def connect_lake(catalog_path: str | Path, data_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection with DuckLake attached as `lake`.

    The catalog is a SQLite file; data files are written under `data_path`.
    Parent directories are created if missing.
    """
    catalog_path = Path(catalog_path)
    data_path = Path(data_path)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    load_extensions(con)
    con.execute(
        f"ATTACH 'ducklake:sqlite:{catalog_path.as_posix()}' AS lake "
        f"(DATA_PATH '{data_path.as_posix()}/')"
    )
    return con

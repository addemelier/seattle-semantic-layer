"""REQUIRED_COLUMNS must cover every source column the staging model reads."""

import re
from pathlib import Path

from permitmap.ingest.columns import REQUIRED_COLUMNS

STAGING = Path(__file__).resolve().parent.parent / "dbt" / "models" / "staging" / "stg_sdci__building_permits.sql"

# Words in the select list that are SQL or output aliases, not source columns.
_NOT_SOURCE = {"trim", "try_cast", "as", "integer", "decimal", "date", "double", "lower", "nullif",
               "select", "from", "source", "with"}


def _source_columns() -> set[str]:
    sql = re.sub(r"--[^\n]*", "", STAGING.read_text())
    select = sql.split("select", 2)[2].rsplit("from", 1)[0]  # the final select list
    cols = set()
    for line in select.splitlines():
        expr = line.strip().rstrip(",")
        if not expr:
            continue
        expr = re.split(r"\s+as\s+(?=\w+$)", expr)[0]  # drop the output alias
        expr = re.sub(r"'[^']*'", "", expr)
        cols |= {w for w in re.findall(r"[a-z_][a-z0-9_]*", expr) if w not in _NOT_SOURCE}
    return cols


def test_staging_columns_are_required():
    cols = _source_columns()
    assert len(cols) >= 20, cols  # parser sanity check
    assert cols <= set(REQUIRED_COLUMNS), sorted(cols - set(REQUIRED_COLUMNS))


def test_required_columns_unique_and_lowercase():
    assert len(set(REQUIRED_COLUMNS)) == len(REQUIRED_COLUMNS)
    assert all(c == c.strip().lower() for c in REQUIRED_COLUMNS)

"""Checks fct_open_permits in the built lake.

Run after: python -m permitmap.load_fixture && dbt build ... -s +fct_open_permits
"""

from pathlib import Path

import pytest

from permitmap.lake import connect_lake

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "data" / "lake" / "catalog.sqlite"
FILES = REPO / "data" / "lake" / "files"

CLOSED = ("completed", "expired", "closed", "canceled", "cancelled", "withdrawn")

GOLD_COLUMNS = [
    "permit_id", "address", "description", "work_type", "stage", "status_raw",
    "applied_date", "issued_date", "expires_date", "valuation_usd",
    "housing_units_added", "housing_units_removed", "contractor", "permit_url",
    "latitude", "longitude",
]


@pytest.fixture(scope="module")
def con():
    if not CATALOG.exists():
        pytest.fail("lake not built: run load_fixture and dbt build first")
    c = connect_lake(CATALOG, FILES)
    yield c
    c.close()


def _one(con, permit_id):
    return con.execute(
        "SELECT work_type, stage, status_raw, applied_date::varchar "
        "FROM lake.gold.fct_open_permits WHERE permit_id = ?", [permit_id]
    ).fetchall()


def test_exact_gold_columns(con):
    cols = [r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_catalog = 'lake' AND table_schema = 'gold' "
        "AND table_name = 'fct_open_permits' ORDER BY ordinal_position"
    ).fetchall()]
    assert cols == GOLD_COLUMNS


def test_no_closed_statuses(con):
    n = con.execute(
        f"SELECT count(*) FROM lake.gold.fct_open_permits "
        f"WHERE lower(trim(status_raw)) IN {CLOSED}"
    ).fetchone()[0]
    assert n == 0


def test_duplicate_permit_appears_once_latest_record(con):
    rows = _one(con, "6999002-CN")
    assert len(rows) == 1
    assert rows[0][3] == "2025-06-15"
    assert rows[0][1] == "issued"


def test_dadu_on_new_permit_is_adu(con):
    rows = _one(con, "6999003-CN")
    assert rows == [("adu", "in_review", "Reviews In Process", rows[0][3])]


def test_other_adu_spellings(con):
    for pid in ("6999004-CN", "6999005-CN", "6999006-CN"):
        assert _one(con, pid)[0][0] == "adu", pid


def test_word_containing_adu_is_not_adu(con):
    assert _one(con, "6999008-CN")[0][0] == "addition_alteration"


def test_unknown_status_kept(con):
    rows = _one(con, "6999001-CN")
    assert len(rows) == 1 and rows[0][2] == "Pending Something"


def test_whitespace_status_variants(con):
    statuses = {r[0] for r in con.execute(
        "SELECT status_raw FROM lake.gold.fct_open_permits").fetchall()}
    assert "  issued " in statuses
    assert "COMPLETED" not in statuses


def test_demolition_and_new_building_present(con):
    types = {r[0] for r in con.execute(
        "SELECT DISTINCT work_type FROM lake.gold.fct_open_permits").fetchall()}
    assert {"adu", "demolition", "new_building", "addition_alteration"} <= types

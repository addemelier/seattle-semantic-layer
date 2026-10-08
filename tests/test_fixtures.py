"""Checks that the synthetic fixtures cover the cases the pipeline must handle."""

import csv
import json
import re
from collections import Counter
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

EXPECTED_COLUMNS = (
    "permitnum,permitclass,permitclassmapped,permittypemapped,permittypedesc,description,"
    "housingunitsremoved,housingunitsadded,estprojectcost,applieddate,issueddate,expiresdate,"
    "completeddate,statuscurrent,originaladdress1,originalcity,originalstate,originalzip,"
    "contractorcompanyname,link,latitude,longitude"
).split(",")

CLOSED = {"completed", "expired", "closed", "canceled", "cancelled", "withdrawn"}
KNOWN_OPEN = {
    "application accepted", "reviews in process", "awaiting information", "corrections required",
    "additional info requested", "ready for issuance", "issued", "reviews completed", "scheduled",
    "inspections completed",
}
ADU_RE = re.compile(r"\b(a?adu|dadu)\b", re.IGNORECASE)


def _rows():
    with open(FIXTURES / "sdci_building_permits_sample.csv", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def test_columns_exact():
    fieldnames, _ = _rows()
    assert fieldnames == EXPECTED_COLUMNS


def test_row_count_about_forty():
    _, rows = _rows()
    assert 35 <= len(rows) <= 50


def test_all_known_statuses_present():
    _, rows = _rows()
    statuses = {r["statuscurrent"].strip().lower() for r in rows}
    assert CLOSED <= statuses
    assert KNOWN_OPEN <= statuses


def test_one_unknown_status():
    _, rows = _rows()
    unknown = {r["statuscurrent"] for r in rows
               if r["statuscurrent"].strip().lower() not in CLOSED | KNOWN_OPEN}
    assert unknown == {"Pending Something"}


def test_duplicate_permitnum():
    _, rows = _rows()
    dupes = [n for n, c in Counter(r["permitnum"] for r in rows).items() if c > 1]
    assert len(dupes) >= 1


def test_adu_descriptions():
    _, rows = _rows()
    descs = [r["description"] for r in rows]
    adu = [d for d in descs if ADU_RE.search(d) or "accessory dwelling" in d.lower()]
    assert len(adu) >= 3
    assert any(re.search(r"\bdadu\b", d, re.I) for d in descs)
    assert any(re.search(r"\badu\b", d, re.I) for d in descs)
    assert any("accessory dwelling unit" in d.lower() for d in descs)


def test_demolition_and_new_types():
    _, rows = _rows()
    assert any("demolition" in (r["permittypemapped"] + r["permittypedesc"]).lower() for r in rows)
    assert any(r["permittypedesc"] == "New" for r in rows)


def test_coordinates_in_seattle_box():
    _, rows = _rows()
    for r in rows:
        assert 47.49 <= float(r["latitude"]) <= 47.74
        assert -122.44 <= float(r["longitude"]) <= -122.24


def test_neighborhoods():
    gj = json.loads((FIXTURES / "neighborhoods_sample.geojson").read_text())
    names = [f["properties"]["neighborhood_name"] for f in gj["features"]]
    assert sorted(names) == ["Ballard", "Beacon Hill", "Capitol Hill"]
    for f in gj["features"]:
        assert f["geometry"]["type"] == "Polygon"
        ring = f["geometry"]["coordinates"][0]
        assert len(ring) == 5 and ring[0] == ring[-1]


def test_readme_says_synthetic_and_unverified():
    text = (FIXTURES / "README.md").read_text().lower()
    assert "synthetic" in text and "unverified" in text

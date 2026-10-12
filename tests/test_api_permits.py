"""GET /api/permits against the fixture lake (permit-api spec)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from permitmap.app import permits
from permitmap.app.config import Config
from permitmap.app.main import create_app

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "data" / "lake" / "catalog.sqlite"
FILES = REPO / "data" / "lake" / "files"

SEATTLE = "-122.46,47.48,-122.22,47.76"
# Box over central Seattle / Queen Anne / Eastlake in the fixtures.
BOX = "-122.37,47.60,-122.31,47.65"
CLOSED = {"completed", "expired", "closed", "canceled", "cancelled", "withdrawn"}
GOLD_FIELDS = set(permits.PROPERTY_COLUMNS)


@pytest.fixture(scope="module")
def client():
    if not CATALOG.exists():
        pytest.fail("lake not built: run load_fixture and dbt build first")
    with TestClient(create_app(Config(lake_catalog=str(CATALOG), lake_data=str(FILES)))) as c:
        yield c


def _ids(body):
    return {f["properties"]["permit_id"] for f in body["features"]}


def test_box_includes_and_excludes(client):
    r = client.get("/api/permits", params={"bbox": BOX})
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    ids = _ids(body)
    assert ids == {"6999009-CN", "6999011-CN", "6999006-CN", "6900015-CN", "6999005-CN", "6900006-CN"}
    # just outside the box on one side each
    assert not ids & {"6999001-CN", "6900009-CN", "6999013-CN", "6900018-CN"}
    for f in body["features"]:
        assert f["geometry"]["type"] == "Point"
        lon, lat = f["geometry"]["coordinates"]
        assert -122.37 <= lon <= -122.31 and 47.60 <= lat <= 47.65
        assert set(f["properties"]) == GOLD_FIELDS
        assert "latitude" not in f["properties"] and "longitude" not in f["properties"]


def test_box_edges_inclusive(client):
    # A degenerate box exactly on one permit's coordinates.
    r = client.get("/api/permits", params={"bbox": "-122.329241,47.604047,-122.329241,47.604047"})
    assert _ids(r.json()) == {"6999009-CN"}


def test_seattle_wide_has_no_closed(client):
    body = client.get("/api/permits", params={"bbox": SEATTLE}).json()
    assert len(body["features"]) > 20
    for f in body["features"]:
        assert f["properties"]["status_raw"].strip().lower() not in CLOSED
    assert "6900000-CN" not in _ids(body)  # Completed in the fixture


def test_ordering_and_iso_dates(client):
    feats = client.get("/api/permits", params={"bbox": SEATTLE}).json()["features"]
    dates = [f["properties"]["applied_date"] for f in feats]
    non_null = [d for d in dates if d is not None]
    assert non_null == sorted(non_null, reverse=True)
    assert dates[: len(non_null)] == non_null  # nulls last
    for f in feats:
        for k in ("applied_date", "issued_date", "expires_date"):
            v = f["properties"][k]
            assert v is None or (len(v) == 10 and v[4] == "-" and v[7] == "-")


@pytest.mark.parametrize("bbox", [
    None, "", "-122.4,47.5,-122.3", "-122.4,47.5,-122.3,47.6,1", "a,b,c,d",
    "-122.3,47.5,-122.4,47.6",   # min lon > max lon
    "-122.4,47.6,-122.3,47.5",   # min lat > max lat
    "-190,47.5,-122.3,47.6", "-122.4,-95,-122.3,47.6", "-122.4,47.5,181,47.6",
    "nan,47.5,-122.3,47.6",
])
def test_malformed_bbox_400(client, bbox):
    params = {} if bbox is None else {"bbox": bbox}
    r = client.get("/api/permits", params=params)
    assert r.status_code == 400
    assert "bbox" in r.json()["error"]


def test_only_adus(client):
    feats = client.get("/api/permits", params={"bbox": SEATTLE, "work_type": "adu"}).json()["features"]
    assert feats
    assert {f["properties"]["work_type"] for f in feats} == {"adu"}


def test_multi_value_filters(client):
    feats = client.get("/api/permits", params={
        "bbox": SEATTLE, "stage": "issued", "work_type": "adu,new_building"}).json()["features"]
    assert feats
    for f in feats:
        assert f["properties"]["stage"] == "issued"
        assert f["properties"]["work_type"] in {"adu", "new_building"}


def test_unknown_stage_400(client):
    r = client.get("/api/permits", params={"bbox": SEATTLE, "stage": "finaled"})
    assert r.status_code == 400


def test_unknown_work_type_400(client):
    r = client.get("/api/permits", params={"bbox": SEATTLE, "work_type": "garage"})
    assert r.status_code == 400


def test_empty_stage_returns_nothing(client):
    r = client.get("/api/permits?bbox=" + SEATTLE + "&stage=")
    assert r.status_code == 200
    assert r.json()["features"] == []


def test_not_truncated_on_fixtures(client):
    assert client.get("/api/permits", params={"bbox": SEATTLE}).json()["truncated"] is False


def test_truncated_when_capped(client, monkeypatch):
    full = client.get("/api/permits", params={"bbox": SEATTLE}).json()["features"]
    monkeypatch.setattr(permits, "MAX_FEATURES", 3)
    body = client.get("/api/permits", params={"bbox": SEATTLE}).json()
    assert body["truncated"] is True
    assert [f["properties"]["permit_id"] for f in body["features"]] == \
        [f["properties"]["permit_id"] for f in full[:3]]

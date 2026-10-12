"""Basic app wiring: health, config, page and vendored MapLibre."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from permitmap.app.config import DEFAULT_STYLE_URL, Config
from permitmap.app.main import create_app

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "data" / "lake" / "catalog.sqlite"
FILES = REPO / "data" / "lake" / "files"
VENDOR_JS = "/static/vendor/maplibre-gl-4.7.1/maplibre-gl.js"


@pytest.fixture(scope="module")
def client():
    if not CATALOG.exists():
        pytest.fail("lake not built: run load_fixture and dbt build first")
    with TestClient(create_app(Config(lake_catalog=str(CATALOG), lake_data=str(FILES)))) as c:
        yield c


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_healthz_503_without_catalog(tmp_path):
    missing = tmp_path / "nope" / "catalog.sqlite"
    app = create_app(Config(lake_catalog=str(missing), lake_data=str(tmp_path / "files")))
    with TestClient(app) as c:
        assert c.get("/healthz").status_code == 503
    assert not missing.exists()


def test_config_default(client):
    assert client.get("/api/config").json() == {"style_url": DEFAULT_STYLE_URL}
    assert DEFAULT_STYLE_URL == "https://tiles.openfreemap.org/styles/positron"


def test_config_override(tmp_path):
    app = create_app(Config(lake_catalog=str(tmp_path / "x.sqlite"),
                            style_url="/static/blank-style.json"))
    with TestClient(app) as c:
        assert c.get("/api/config").json() == {"style_url": "/static/blank-style.json"}


def test_config_from_env():
    cfg = Config.from_env({"PERMITMAP_STYLE_URL": "https://example.test/s.json", "PERMITMAP_PORT": "9001"})
    assert cfg.style_url == "https://example.test/s.json"
    assert cfg.port == 9001
    assert Config.from_env({}).style_url == DEFAULT_STYLE_URL


def test_index_references_vendored_maplibre(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert VENDOR_JS in r.text


def test_vendored_js_served(client):
    r = client.get(VENDOR_JS)
    assert r.status_code == 200
    assert "MapLibre" in r.text[:500]

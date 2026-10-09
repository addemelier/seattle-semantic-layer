"""Headless-browser harness for the permit map (design.md Build notes).

Builds the fixture lake if missing, starts the app with uvicorn in a background
thread on a free port with the blank map style, and launches Chromium headless.
Set PW_CHROMIUM_PATH to use a preinstalled Chromium; never run `playwright install`.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from permitmap.app.config import Config
from permitmap.app.main import create_app

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "data" / "lake" / "catalog.sqlite"
FILES = REPO / "data" / "lake" / "files"


def _build_lake() -> None:
    subprocess.run([sys.executable, "-m", "permitmap.load_fixture"], cwd=REPO, check=True)
    subprocess.run(["dbt", "build", "--project-dir", "dbt", "--profiles-dir", "dbt",
                    "-s", "+fct_open_permits"], cwd=REPO, check=True)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url():
    if not CATALOG.exists():
        _build_lake()
    os.environ["PERMITMAP_STYLE_URL"] = "/static/blank-style.json"
    os.environ["PERMITMAP_LAKE_CATALOG"] = str(CATALOG)
    os.environ["PERMITMAP_LAKE_DATA"] = str(FILES)
    app = create_app(Config.from_env())
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(url + "/healthz", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError("app did not become healthy")
    yield url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        kwargs = {"headless": True}
        if os.environ.get("PW_CHROMIUM_PATH"):
            kwargs["executable_path"] = os.environ["PW_CHROMIUM_PATH"]
        b = p.chromium.launch(**kwargs)
        yield b
        b.close()


@pytest.fixture
def context(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    yield ctx
    ctx.close()


@pytest.fixture
def page(context):
    return context.new_page()


def wait_for_map(page) -> None:
    page.wait_for_function("window.permitMap && window.permitMap.loaded()", timeout=15000)


def wait_for_pins(page) -> None:
    """Wait until the latest permits fetch has been drawn."""
    page.wait_for_function("document.body.dataset.permits === 'ready'", timeout=15000)


def open_map(page, base_url: str, hash_: str = "") -> None:
    page.goto(base_url + "/" + hash_)
    wait_for_map(page)
    wait_for_pins(page)


RENDERED_IDS_JS = """() => {
  const feats = window.permitMap.queryRenderedFeatures({layers: ['permits']});
  return [...new Set(feats.map(f => f.properties.permit_id))].sort();
}"""

RENDERED_FEATURES_JS = """() => {
  const seen = new Map();
  for (const f of window.permitMap.queryRenderedFeatures({layers: ['permits']})) {
    seen.set(f.properties.permit_id, f.properties);
  }
  return [...seen.values()];
}"""

BBOX_JS = """() => {
  const b = window.permitMap.getBounds();
  return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(6)).join(',');
}"""

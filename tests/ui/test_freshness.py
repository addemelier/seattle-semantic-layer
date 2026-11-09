"""Data freshness label (permit-map delta), with /api/config stubbed per case."""

import json

from conftest import wait_for_map


def _open_with_config(page, base_url, data_as_of, data_fresh):
    def handle(route):
        cfg = {"style_url": "/static/blank-style.json", "data_as_of": data_as_of,
               "data_fresh": data_fresh}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(cfg))

    page.route("**/api/config", handle)
    page.goto(base_url + "/")
    wait_for_map(page)
    label = page.locator("#freshness")
    label.wait_for(state="visible")
    return label


def test_fresh(page, base_url):
    label = _open_with_config(page, base_url, "2026-11-03T13:05:00Z", True)
    assert label.inner_text() == "Permits as of Nov 3"
    assert "stale" not in (label.get_attribute("class") or "")


def test_stale(page, base_url):
    label = _open_with_config(page, base_url, "2026-11-03T13:05:00Z", False)
    assert label.inner_text() == "Permits as of Nov 3, may be out of date"
    color = label.evaluate("el => getComputedStyle(el).color")
    assert color == "rgb(217, 119, 6)"  # #D97706


def test_sample_data(page, base_url):
    label = _open_with_config(page, base_url, None, None)
    assert label.inner_text() == "Sample data"


def test_label_is_bottom_left_and_clear_of_controls(page, base_url):
    label = _open_with_config(page, base_url, None, None)
    box = label.bounding_box()
    vp = page.viewport_size
    assert box["x"] < vp["width"] / 2 and box["y"] > vp["height"] / 2
    controls = page.locator("#controls").bounding_box()
    assert box["y"] > controls["y"] + controls["height"]

"""Pins, zoom gate and URL view (permit-map spec)."""

import httpx

from conftest import BBOX_JS, RENDERED_IDS_JS, open_map, wait_for_map, wait_for_pins

VIEW = "#14/47.61/-122.33"


def test_pins_match_api(page, base_url):
    open_map(page, base_url, VIEW)
    rendered = page.evaluate(RENDERED_IDS_JS)
    bbox = page.evaluate(BBOX_JS)
    api = httpx.get(base_url + "/api/permits", params={"bbox": bbox}).json()
    expected = sorted(f["properties"]["permit_id"] for f in api["features"])
    assert len(expected) >= 2
    assert rendered == expected
    assert page.locator("#status").is_hidden()
    legend = page.locator("#legend").inner_text()
    assert "In review" in legend and "Issued" in legend


def test_zoomed_out_shows_message_and_no_pins(page, base_url):
    requests = []
    page.on("request", lambda r: requests.append(r.url) if "/api/permits" in r.url else None)
    open_map(page, base_url, "#10/47.6062/-122.3321")
    assert page.evaluate(RENDERED_IDS_JS) == []
    status = page.locator("#status")
    assert status.is_visible()
    assert status.inner_text() == "Zoom in to see permits"
    assert requests == []


def test_default_view_is_seattle_zoom_12(page, base_url):
    open_map(page, base_url)
    c = page.evaluate("[permitMap.getCenter().lng, permitMap.getCenter().lat, permitMap.getZoom()]")
    assert abs(c[0] - -122.3321) < 1e-4 and abs(c[1] - 47.6062) < 1e-4 and abs(c[2] - 12) < 1e-6


def test_url_restores_view(context, base_url):
    first = context.new_page()
    open_map(first, base_url, "#15.5/47.6168/-122.3243")
    url = first.url
    assert "#15.5/47.6168/-122.3243" in url
    first.close()

    second = context.new_page()
    second.goto(url)
    wait_for_map(second)
    wait_for_pins(second)
    c = second.evaluate("[permitMap.getCenter().lng, permitMap.getCenter().lat, permitMap.getZoom()]")
    assert abs(c[0] - -122.3243) < 1e-4
    assert abs(c[1] - 47.6168) < 1e-4
    assert abs(c[2] - 15.5) < 1e-6


def test_truncation_note(page, base_url):
    page.route("**/api/permits*", lambda route: route.fulfill(
        json={"type": "FeatureCollection", "features": [], "truncated": True}))
    open_map(page, base_url, VIEW)
    assert "most recent 2,000 permits" in page.locator("#status").inner_text()

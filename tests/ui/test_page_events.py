"""The map page sends engagement events (engagement-events spec delta).

/api/events is intercepted with page.route; the geocoder is mocked as in test_search.py.
"""

import json

import httpx

from conftest import open_map

VIEW = "#14/47.61/-122.33"
FAR_VIEW = "#10/47.61/-122.33"
POINT = {"lat": 47.634567, "lon": -122.345678,
         "matched_address": "1234 SAMPLE AVE N, SEATTLE, WA, 98109", "score": 100}
GPC = "Object.defineProperty(navigator, 'globalPrivacyControl', {get: () => true})"
PIN = "6999009-CN"


def _capture(page, status=204):
    sent = []

    def handle(route):
        sent.append(json.loads(route.request.post_data))
        route.fulfill(status=status, body="" if status == 204 else '{"error": "events unavailable"}',
                      content_type="application/json")

    page.route("**/api/events", handle)
    return sent


def _of(sent, kind):
    return [e for e in sent if e["event_type"] == kind]


def _settle(page, ms=600):
    page.wait_for_timeout(ms)


def _wait_for(page, sent, kind, n=1, timeout_ms=5000):
    waited = 0
    while len(_of(sent, kind)) < n and waited < timeout_ms:
        page.wait_for_timeout(100)
        waited += 100
    return _of(sent, kind)


def _mock_geocoder(page, status, body):
    page.route("**/api/geocode*", lambda route: route.fulfill(status=status, json=body))


def _search(page, q):
    page.evaluate("delete document.body.dataset.search")
    page.fill("#search input[name=q]", q)
    page.press("#search input[name=q]", "Enter")
    page.wait_for_function("['done', 'not_found', 'unavailable'].includes(document.body.dataset.search)",
                           timeout=15000)


def _pin(base_url, permit_id=PIN):
    feats = httpx.get(base_url + "/api/permits",
                      params={"bbox": "-122.46,47.48,-122.22,47.76"}).json()["features"]
    return next(f for f in feats if f["properties"]["permit_id"] == permit_id)


def _click_pin(page, feature):
    lon, lat = feature["geometry"]["coordinates"]
    xy = page.evaluate("([lon, lat]) => { const p = permitMap.project([lon, lat]); return [p.x, p.y]; }",
                       [lon, lat])
    box = page.locator("#map").bounding_box()
    page.mouse.click(box["x"] + xy[0], box["y"] + xy[1])
    page.locator("#permit-panel").wait_for(state="visible", timeout=5000)


def _pan(page, dx=40):
    page.evaluate("dx => permitMap.panBy([dx, 0], {duration: 0})", dx)


def test_successful_search(page, base_url):
    sent = _capture(page)
    open_map(page, base_url, VIEW)
    _mock_geocoder(page, 200, POINT)
    _search(page, "  1234 Sample Ave N ")
    events = _wait_for(page, sent, "search")
    _settle(page)
    events = _of(sent, "search")
    assert len(events) == 1
    e = events[0]
    assert e["search_text"] == "1234 Sample Ave N"
    assert e["lat"] == POINT["lat"] and e["lon"] == POINT["lon"]
    assert len(e["session_id"]) == 32


def test_not_found_search(page, base_url):
    sent = _capture(page)
    open_map(page, base_url, VIEW)
    _mock_geocoder(page, 404, {"error": "address not found in Seattle"})
    _search(page, "999 Nowhere St")
    _wait_for(page, sent, "search")
    _settle(page)
    events = _of(sent, "search")
    assert len(events) == 1
    assert events[0]["search_text"] == "999 Nowhere St"
    assert "lat" not in events[0] and "lon" not in events[0]


def test_permit_click(page, base_url):
    f = _pin(base_url)
    sent = _capture(page)
    open_map(page, base_url, VIEW)
    _click_pin(page, f)
    _wait_for(page, sent, "permit_click")
    _settle(page, 300)
    clicks = _of(sent, "permit_click")
    assert len(clicks) == 1
    assert clicks[0]["permit_id"] == PIN
    lon, lat = f["geometry"]["coordinates"]
    assert abs(clicks[0]["lat"] - lat) < 1e-6 and abs(clicks[0]["lon"] - lon) < 1e-6


def test_filter_change(page, base_url):
    sent = _capture(page)
    open_map(page, base_url, VIEW)
    page.locator("#filters input[value=issued]").set_checked(False)
    changes = _wait_for(page, sent, "filter_change")
    assert len(changes) == 1
    assert changes[0]["filters"]["stage"] == ["in_review"]
    assert changes[0]["filters"]["work_type"] == ["new_building", "addition_alteration",
                                                  "demolition", "adu"]


def test_map_move_throttled(page, base_url):
    sent = _capture(page)
    open_map(page, base_url, VIEW)
    _settle(page, 2200)  # let any move from the initial load fall outside the window
    sent.clear()
    for _ in range(3):
        _pan(page)
        page.wait_for_timeout(150)
    _settle(page, 800)
    moves = _of(sent, "map_move")
    assert len(moves) <= 1
    assert len(moves) == 1  # the first pan after a quiet period is sent
    center = page.evaluate("[permitMap.getCenter().lat, permitMap.getCenter().lng]")
    assert abs(moves[0]["lat"] - center[0]) < 0.01 and abs(moves[0]["lon"] - center[1]) < 0.01


def test_no_map_move_when_zoomed_out(page, base_url):
    sent = _capture(page)
    open_map(page, base_url, FAR_VIEW)
    _settle(page, 2200)
    sent.clear()
    _pan(page)
    _settle(page, 800)
    assert _of(sent, "map_move") == []


def test_gpc_sends_nothing(page, base_url):
    page.add_init_script(GPC)
    f = _pin(base_url)
    sent = _capture(page)
    open_map(page, base_url, VIEW)
    assert page.evaluate("permitEvents.enabled") is False
    _click_pin(page, f)
    page.locator("#filters input[value=issued]").set_checked(False)
    _pan(page)
    _mock_geocoder(page, 200, POINT)
    _search(page, "1234 Sample Ave N")
    _settle(page, 1000)
    assert sent == []


def test_store_down_map_keeps_working(page, base_url):
    f = _pin(base_url)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sent = _capture(page, status=503)
    open_map(page, base_url, VIEW)
    _click_pin(page, f)
    assert page.locator("#permit-panel [data-field=address]").inner_text() == f["properties"]["address"]
    page.get_by_role("button", name="Close").click()

    _mock_geocoder(page, 200, POINT)
    _search(page, "1234 Sample Ave N")
    assert page.evaluate("document.body.dataset.search") == "done"
    lon, lat = page.evaluate("[permitMap.getCenter().lng, permitMap.getCenter().lat]")
    assert abs(lon - POINT["lon"]) < 1e-4 and abs(lat - POINT["lat"]) < 1e-4
    _settle(page)
    assert _of(sent, "search") and _of(sent, "permit_click")  # they were sent, and failed

    status = page.locator("#status")
    assert status.is_hidden() or status.inner_text().strip() == ""
    assert errors == []

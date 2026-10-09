"""Address search with a 1,000 ft ring (permit-map spec). The geocoder is mocked in the browser."""

import math

from conftest import open_map

VIEW = "#13/47.62/-122.34"
POINT = {"lat": 47.634567, "lon": -122.345678,
         "matched_address": "1234 SAMPLE AVE N, SEATTLE, WA, 98109", "score": 100}
POINT2 = {"lat": 47.6062, "lon": -122.3321,
          "matched_address": "500 SAMPLE ST, SEATTLE, WA, 98104", "score": 100}


def _haversine_m(lon1, lat1, lon2, lat2):
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _mock_geocoder(page, status, body):
    page.unroute("**/api/geocode*")
    page.route("**/api/geocode*", lambda route: route.fulfill(status=status, json=body))


def _search(page, q="1234 Sample Ave N"):
    page.evaluate("delete document.body.dataset.search")
    page.fill("#search input[name=q]", q)
    page.press("#search input[name=q]", "Enter")
    page.wait_for_function("['done', 'not_found', 'unavailable'].includes(document.body.dataset.search)",
                           timeout=15000)


def _view(page):
    return page.evaluate("[permitMap.getCenter().lng, permitMap.getCenter().lat, permitMap.getZoom()]")


def _ring(page):
    return page.evaluate("permitMap.getSource('search-ring').serialize().data")


def test_search_success_ring_and_replace(page, base_url):
    open_map(page, base_url, VIEW)
    _mock_geocoder(page, 200, POINT)
    _search(page)
    lon, lat, zoom = _view(page)
    assert abs(lon - POINT["lon"]) < 1e-4 and abs(lat - POINT["lat"]) < 1e-4
    assert abs(zoom - 16) < 1e-6
    assert page.locator(".search-marker").count() == 1

    ring = _ring(page)
    assert len(ring["features"]) == 1
    coords = ring["features"][0]["geometry"]["coordinates"][0]
    assert len(coords) == 65 and coords[0] == coords[-1]
    for x, y in coords:
        assert abs(_haversine_m(POINT["lon"], POINT["lat"], x, y) - 304.8) <= 2
    assert page.evaluate("permitMap.getLayer('search-ring').type") == "line"

    _mock_geocoder(page, 200, POINT2)
    _search(page, "500 Sample St")
    assert page.locator(".search-marker").count() == 1
    ring = _ring(page)
    assert len(ring["features"]) == 1
    x, y = ring["features"][0]["geometry"]["coordinates"][0][0]
    assert abs(_haversine_m(POINT2["lon"], POINT2["lat"], x, y) - 304.8) <= 2
    lon, lat, _ = _view(page)
    assert abs(lon - POINT2["lon"]) < 1e-4 and abs(lat - POINT2["lat"]) < 1e-4


def test_not_found_leaves_map(page, base_url):
    open_map(page, base_url, VIEW)
    before = _view(page)
    _mock_geocoder(page, 404, {"error": "address not found in Seattle"})
    _search(page)
    assert page.locator("#status").inner_text() == "Address not found in Seattle"
    assert _view(page) == before
    assert page.locator(".search-marker").count() == 0


def test_unavailable_leaves_map(page, base_url):
    open_map(page, base_url, VIEW)
    before = _view(page)
    _mock_geocoder(page, 502, {"error": "address search is unavailable right now"})
    _search(page)
    assert page.locator("#status").inner_text() == "Address search is unavailable right now"
    assert _view(page) == before


def test_network_error_leaves_map(page, base_url):
    open_map(page, base_url, VIEW)
    before = _view(page)
    page.route("**/api/geocode*", lambda route: route.abort())
    _search(page)
    assert page.locator("#status").inner_text() == "Address search is unavailable right now"
    assert _view(page) == before

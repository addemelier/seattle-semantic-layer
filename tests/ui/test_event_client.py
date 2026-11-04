"""Browser event client: session ID rules, privacy signals and the POST it makes."""

import json
import re
import time

from conftest import wait_for_map

HEX32 = re.compile(r"^[0-9a-f]{32}$")
GPC = "Object.defineProperty(navigator, 'globalPrivacyControl', {get: () => true})"


def _capture(page, status=204):
    sent = []

    def handle(route):
        sent.append(json.loads(route.request.post_data))
        route.fulfill(status=status, body="")

    page.route("**/api/events", handle)
    return sent


def _open(page, base_url):
    page.goto(base_url + "/")
    wait_for_map(page)


def test_session_id_is_stable_across_reload(page, base_url):
    _capture(page)
    _open(page, base_url)
    first = page.evaluate("permitEvents.sessionId()")
    assert HEX32.match(first)
    page.reload()
    wait_for_map(page)
    assert page.evaluate("permitEvents.sessionId()") == first


def test_id_renewed_after_31_days(page, base_url):
    old = "a" * 32
    last = int((time.time() - 31 * 86400) * 1000)
    page.add_init_script(
        f"localStorage.setItem('permitmap.session', JSON.stringify({{id: '{old}', last: {last}}}))")
    _capture(page)
    _open(page, base_url)
    new = page.evaluate("permitEvents.sessionId()")
    assert HEX32.match(new) and new != old


def test_id_kept_after_3_days(page, base_url):
    old = "b" * 32
    last = int((time.time() - 3 * 86400) * 1000)
    page.add_init_script(
        f"localStorage.setItem('permitmap.session', JSON.stringify({{id: '{old}', last: {last}}}))")
    _capture(page)
    _open(page, base_url)
    assert page.evaluate("permitEvents.sessionId()") == old


def test_storage_throwing_still_works(page, base_url):
    page.add_init_script(
        "Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }})")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _capture(page)
    _open(page, base_url)
    a = page.evaluate("permitEvents.sessionId()")
    assert HEX32.match(a)
    assert page.evaluate("permitEvents.sessionId()") == a  # same for the page load
    assert errors == []


def test_gpc_disables_sending(page, base_url):
    page.add_init_script(GPC)
    sent = _capture(page)
    _open(page, base_url)
    assert page.evaluate("permitEvents.enabled") is False
    page.evaluate("permitEvents.send('map_move', {lat: 47.6, lon: -122.3})")
    page.wait_for_timeout(300)
    assert sent == []


def test_send_posts_one_event(page, base_url):
    sent = _capture(page)
    _open(page, base_url)
    assert page.evaluate("permitEvents.enabled") is True
    with page.expect_request("**/api/events"):
        result = page.evaluate("permitEvents.send('map_move', {lat: 47.6, lon: -122.3})")
    assert result is None
    page.wait_for_timeout(200)
    assert len(sent) == 1
    e = sent[0]
    assert e["event_type"] == "map_move"
    assert e["session_id"] == page.evaluate("permitEvents.sessionId()")
    assert (e["lat"], e["lon"]) == (47.6, -122.3)
    assert set(e) <= {"event_type", "session_id", "lat", "lon", "referrer"}


def test_failed_send_is_silent(page, base_url):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _capture(page, status=503)
    _open(page, base_url)
    page.evaluate("permitEvents.send('search', {search_text: 'x'})")
    page.wait_for_timeout(300)
    assert errors == []

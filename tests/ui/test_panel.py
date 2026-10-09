"""Permit detail panel (permit-map spec)."""

import httpx

from conftest import open_map

VIEW = "#14/47.61/-122.33"


def _permit(base_url, permit_id):
    feats = httpx.get(base_url + "/api/permits",
                      params={"bbox": "-122.46,47.48,-122.22,47.76"}).json()["features"]
    return next(f for f in feats if f["properties"]["permit_id"] == permit_id)


def _click_permit(page, feature):
    lon, lat = feature["geometry"]["coordinates"]
    xy = page.evaluate("([lon, lat]) => { const p = permitMap.project([lon, lat]); return [p.x, p.y]; }",
                       [lon, lat])
    box = page.locator("#map").bounding_box()
    page.mouse.click(box["x"] + xy[0], box["y"] + xy[1])
    page.locator("#permit-panel").wait_for(state="visible", timeout=5000)


def test_click_pin_opens_panel(page, base_url):
    f = _permit(base_url, "6999009-CN")
    open_map(page, base_url, VIEW)
    _click_permit(page, f)
    panel = page.locator("#permit-panel")
    assert panel.get_attribute("role") == "dialog"
    assert panel.get_attribute("aria-label") == f["properties"]["address"]
    assert panel.locator("[data-field=address]").inner_text() == f["properties"]["address"]
    link = panel.locator("a.panel-link")
    assert link.get_attribute("href") == f["properties"]["permit_url"]
    assert link.get_attribute("target") == "_blank"
    assert link.get_attribute("rel") == "noopener"
    assert panel.locator("[data-field=valuation_usd]").inner_text() == "$85,000"
    assert panel.locator("[data-field=stage]").inner_text() == "In review"
    assert panel.locator("[data-field=work_type]").inner_text() == "Demolition"


def test_missing_valuation_and_contractor(page, base_url):
    f = _permit(base_url, "6999014-CN")
    assert f["properties"]["valuation_usd"] is None
    open_map(page, base_url, VIEW)
    _click_permit(page, f)
    panel = page.locator("#permit-panel")
    assert panel.locator("[data-field=valuation_usd]").inner_text() == "Not stated"
    assert panel.locator("[data-field=contractor]").inner_text() == "Not listed"


def test_close_hides_panel(page, base_url):
    open_map(page, base_url, VIEW)
    _click_permit(page, _permit(base_url, "6999009-CN"))
    page.get_by_role("button", name="Close").click()
    assert page.locator("#permit-panel").is_hidden()


def test_phone_bottom_sheet(browser, base_url):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    try:
        page = ctx.new_page()
        open_map(page, base_url, VIEW)
        _click_permit(page, _permit(base_url, "6999009-CN"))
        box = page.locator("#permit-panel").bounding_box()
        assert box["y"] >= 0.4 * 844
        assert abs(box["y"] + box["height"] - 844) < 2  # anchored to the bottom
    finally:
        ctx.close()

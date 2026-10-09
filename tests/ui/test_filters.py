"""Stage and work-type filters (permit-map spec)."""

from conftest import RENDERED_FEATURES_JS, open_map, wait_for_pins

VIEW = "#13/47.63/-122.34"
WORK_TYPES = ("new_building", "addition_alteration", "demolition", "adu")


def _rendered(page):
    return page.evaluate(RENDERED_FEATURES_JS)


def _set(page, value, checked):
    box = page.locator(f"#filters input[value={value}]")
    if box.is_checked() != checked:
        box.set_checked(checked)
        wait_for_pins(page)


def test_all_checked_on_load_with_labels(page, base_url):
    open_map(page, base_url, VIEW)
    boxes = page.locator("#filters input[type=checkbox]")
    assert boxes.count() == 6
    for i in range(6):
        assert boxes.nth(i).is_checked()
    text = page.locator("#filters").inner_text()
    for label in ("In review", "Issued", "New building", "Addition / alteration", "Demolition", "ADU"):
        assert label in text


def test_adu_only(page, base_url):
    open_map(page, base_url, VIEW)
    before = _rendered(page)
    assert any(f["work_type"] == "adu" for f in before)
    for wt in WORK_TYPES:
        if wt != "adu":
            _set(page, wt, False)
    after = _rendered(page)
    assert after
    assert {f["work_type"] for f in after} == {"adu"}
    assert len(after) < len(before)


def test_uncheck_issued_then_restore(page, base_url):
    open_map(page, base_url, VIEW)
    before = _rendered(page)
    assert {f["stage"] for f in before} == {"in_review", "issued"}
    _set(page, "issued", False)
    mid = _rendered(page)
    assert mid and {f["stage"] for f in mid} == {"in_review"}
    _set(page, "issued", True)
    assert len(_rendered(page)) == len(before)


def test_group_all_unchecked_shows_nothing(page, base_url):
    open_map(page, base_url, VIEW)
    seen = []
    page.on("request", lambda r: seen.append(r.url) if "/api/permits" in r.url else None)
    _set(page, "in_review", False)
    _set(page, "issued", False)
    assert _rendered(page) == []
    assert "stage=&" in seen[-1] or seen[-1].endswith("stage=")

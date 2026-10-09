# Tasks: permit-map-v0

Every task runs offline. Read design.md "Decisions" and "Build notes" first. In the build sandbox, export `PW_CHROMIUM_PATH=/opt/pw-browsers/chromium` before UI tests. Never run `playwright install`.

## 1. App skeleton

- [x] 1.1 Add `fastapi`, `uvicorn`, `httpx` to dependencies and `playwright==1.56.0`, `respx` to dev extras in `pyproject.toml`, and fix packaging so subpackages and `static/**` are included (Build notes). Create `permitmap/app/__init__.py`, `permitmap/app/config.py` (frozen dataclass from env, defaults in Build notes), `permitmap/app/main.py` (`create_app(config) -> FastAPI` that opens the lake once, mounts `/static`, serves `index.html` at `/`, and implements `/healthz` and `/api/config`), and `permitmap/app/__main__.py` (runs uvicorn). Vendor MapLibre 4.7.1 into `permitmap/app/static/vendor/maplibre-gl-4.7.1/` via `npm pack` (design A3). Add `permitmap/app/static/blank-style.json` and a placeholder `index.html` that loads the vendored MapLibre. Write `tests/test_app_basics.py` (FastAPI `TestClient`): `/healthz` is 200 on a built lake and 503 when the catalog path doesn't exist; `/api/config` returns the default and an overridden style URL; `/` returns HTML that references the vendored JS; the vendored JS is served with 200.
  - Verify: `pip install -e '.[dev]' && python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/test_app_basics.py -q`

## 2. Permits API

- [x] 2.1 Create `permitmap/app/permits.py` with the bbox/filter parsing and query (Build notes: parameterized SQL, ordering, 2,001-row cap trick, ISO dates) and wire `GET /api/permits` in `main.py`. Write `tests/test_api_permits.py` covering every `permit-api` scenario for permits: box includes/excludes the right fixture permits; Seattle-wide box has no closed statuses; every malformed-bbox case is 400; `work_type=adu` returns only ADUs; `stage=finaled` is 400; `stage=` returns zero features; `truncated` is false on fixtures, and true when the cap is monkeypatched to 3.
  - Verify: `python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/test_api_permits.py -q`

## 3. Geocode API

- [x] 3.1 Create `permitmap/app/geocode.py` (`async def geocode(client, url, q) -> Match | None`, raising a `GeocoderUnavailable` error on timeout/HTTP error/ArcGIS error body/malformed JSON) and wire `GET /api/geocode` in `main.py`. Create the synthetic `tests/fixtures/geocoder_candidates_sample.json` (two candidates, scores 100 and 71, inside Seattle) and note it in `tests/fixtures/README.md`. Write `tests/test_api_geocode.py` with `respx`: good match → 200 with lat/lon/matched_address/score and the request carried `SingleLine`, `outSR=4326`, `f=json`; best score 62 → 404; no candidates → 404; timeout → 502; ArcGIS `{"error": ...}` body → 502; `q` of 2 chars or 201 chars → 400.
  - Verify: `python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/test_api_geocode.py -q`

## 4. Map and pins

- [ ] 4.1 Build `permitmap/app/static/index.html`, `style.css`, `app.js`. Full-window map, initial view and `hash: true` (A5), style URL from `/api/config`, `window.permitMap` (A7). On `moveend` (debounced, abortable) at zoom ≥ 12 fetch `/api/permits` for the visible bounds into source `permits` / circle layer `permits` colored by stage (A8); below 12 clear pins and show "Zoom in to see permits" in `#status`; show the truncation note when `truncated`. Legend with "In review" and "Issued". Create `tests/ui/conftest.py` (Build notes harness) and `tests/ui/test_pins.py`: opening `/#14/<lat>/<lon>` over fixture permits renders as many `permits` features as the API returns for that view; `/#10/47.6062/-122.3321` shows the zoom-in message and zero rendered pins; reopening the same URL in a new page restores center and zoom.
  - Verify: `export PW_CHROMIUM_PATH=${PW_CHROMIUM_PATH:-/opt/pw-browsers/chromium} && python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/ui/test_pins.py -q`

## 5. Detail panel

- [ ] 5.1 Add the `#permit-panel` (Build notes markup) to the page: clicking a pin fills it with the fields in the `permit-map` spec (USD formatting via `Intl.NumberFormat`, "Not stated", "Not listed", city link with `target="_blank" rel="noopener"`), close button hides it, and below 640 px it renders as a bottom sheet no taller than 60% of the viewport. Write `tests/ui/test_panel.py`: clicking a fixture pin opens the panel with that permit's address and a link equal to its `permit_url`; a fixture permit with null valuation shows "Not stated" (add or pick such a fixture row; if adding, update `tests/test_fixtures.py` counts accordingly); Close hides it; at a 390×844 viewport the panel's top is below 40% of viewport height.
  - Verify: `export PW_CHROMIUM_PATH=${PW_CHROMIUM_PATH:-/opt/pw-browsers/chromium} && python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/ui/test_panel.py -q`

## 6. Filters

- [ ] 6.1 Add the filter control (stage and work-type checkboxes with the spec labels, all checked on load). Any change re-fetches with `stage`/`work_type` params; when every box in a group is unchecked, send the empty parameter so no pins show. Write `tests/ui/test_filters.py`: unchecking all work types but ADU leaves only rendered features with `work_type = adu` and fewer than before; unchecking "Issued" leaves only `in_review` pins; re-checking restores the original count.
  - Verify: `export PW_CHROMIUM_PATH=${PW_CHROMIUM_PATH:-/opt/pw-browsers/chromium} && python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/ui/test_filters.py -q`

## 7. Search, ring and README

- [ ] 7.1 Add the `#search` form: submit calls `/api/geocode`; on 200 fly to the point at zoom 16, place a `.search-marker`, draw the 304.8 m ring in source/layer `search-ring` (Build notes), replacing any previous one; on 404 show "Address not found in Seattle"; on 502/network error show "Address search is unavailable right now"; in both failure cases the map does not move. Add a "Run it locally" section to `README.md` (build the fixture lake, `python -m permitmap.app`, open `http://127.0.0.1:8000`). Write `tests/ui/test_search.py` using Playwright `page.route("**/api/geocode*")` to return a fixed fixture point: success centers the map within 1e-4° of it at zoom 16, exactly one marker and one ring exist, and the ring's vertices are 304.8 m ± 2 m from the center (haversine in the test); a second search leaves still exactly one marker and ring; mocked 404 and 502 show their messages and the center is unchanged.
  - Verify: `export PW_CHROMIUM_PATH=${PW_CHROMIUM_PATH:-/opt/pw-browsers/chromium} && python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/ui/test_search.py -q && python -m pytest -q`

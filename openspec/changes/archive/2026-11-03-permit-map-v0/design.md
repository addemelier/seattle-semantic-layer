# Design: permit-map-v0

Design session 2026-10-09. The PM approved the shape as "the first pass". No open questions block building.

## Context

`lake.gold.fct_open_permits` is built from synthetic fixtures by `python -m permitmap.load_fixture` and dbt (see `openspec/specs/open-permits`). The DuckLake catalog is at `data/lake/catalog.sqlite` with data files in `data/lake/files/`, and is opened with `permitmap.lake.connect_lake()`. No web code exists yet. The build sandbox can't reach `data.seattle.gov`, the city GIS servers or tile hosts. It can reach PyPI and the npm registry, and has headless Chromium at `/opt/pw-browsers/chromium`.

## Goals / Non-Goals

**Goals:** a page the PM would use while looking at a house. It runs locally with one command on the fixture lake, and every behavior in the specs is checked by an offline test.

**Non-goals:** see the proposal's "Out of scope". Also: no JS framework, bundler or Node toolchain at runtime, and no styling polish beyond what the specs need.

## Decisions (PM, 2026-10-09)

| # | Decision | Reason |
|---|---|---|
| D1 | **Scope of v0** is pins by stage, the detail panel, stage and work-type filters, address search and a 1,000 ft ring. The list view, valuation and applied-within filters, and event wiring are deferred. | The smallest thing the PM would actually use. Everything else is additive. |
| D2 | **Geocoding uses the City of Seattle's public address locator**, called by the API and not by the browser. Results need score ≥ 80. | Free, no key, and Seattle-only, so there are fewer wrong-city matches than with Nominatim. Calling it server-side keeps the URL swappable. |
| D3 | **Basemap: OpenFreeMap Positron** (`https://tiles.openfreemap.org/styles/positron`), configurable. | Free, no account and no key. The light style makes colored pins stand out. |
| D4 | **UI proof is a Playwright smoke test** in headless Chromium with a blank map style and a mocked geocoder. | Lets the builder prove the clicks work with no network access. The PM reviews the look in the PR. |

## Decisions (agent, accepted by the PM with the design)

| # | Decision | Reason |
|---|---|---|
| A1 | **FastAPI app in `permitmap/app/`** serves static files and the API. Run it with `python -m permitmap.app` (uvicorn, host from `PERMITMAP_HOST` default `127.0.0.1`, port from `PERMITMAP_PORT` default `8000`). | Matches the stack in CLAUDE.md. One process. |
| A2 | **Plain HTML, CSS and JS, no build step.** Files: `permitmap/app/static/index.html`, `app.js`, `style.css`. | Nothing to install on the VPS or Pi, and the PM can read it. |
| A3 | **MapLibre GL JS 4.7.1 is committed** under `permitmap/app/static/vendor/maplibre-gl-4.7.1/` (`maplibre-gl.js`, `maplibre-gl.css`, `LICENSE.txt`), taken from `npm pack maplibre-gl@4.7.1`. | Works offline in tests and on the server. No CDN dependency. |
| A4 | **Server-side bbox query with a 2,000-feature cap.** No client-side dataset. | Seattle has tens of thousands of open permits. Querying the viewport keeps responses small on phones. |
| A5 | **The view is kept in the URL** through MapLibre's `hash: true`. | Gives "send a friend a link to this spot" for free, and tests can open a known view. |
| A6 | **Below zoom 12, no permit requests** are made and the zoom-in message shows. | Avoids city-wide requests. Below 12 the pins are unreadable anyway. |
| A7 | **The test hook is `window.permitMap`.** The page exposes the map object. The pin layer id is `permits`, the ring layer id is `search-ring`, and the marker element has class `search-marker`. | Tests can query rendered features and click pins by projected pixel. |
| A8 | **Colors:** in_review `#D97706` (amber), issued `#2563EB` (blue). Pins are circles with radius 6 and a 1.5 px white stroke. The ring is a 2 px `#111827` line with no fill. | Readable on Positron and distinguishable for common color-vision deficiencies (amber versus blue). |

## Build notes (for the builder; decisions already made)

- **Config** comes from environment variables with defaults:
  - `PERMITMAP_LAKE_CATALOG` defaults to `data/lake/catalog.sqlite`.
  - `PERMITMAP_LAKE_DATA` defaults to `data/lake/files`.
  - `PERMITMAP_STYLE_URL` defaults to the D3 URL.
  - `PERMITMAP_GEOCODER_URL` defaults to `https://gisdata.seattle.gov/cosgis/rest/services/locators/MultiRoles/GeocodeServer/findAddressCandidates`.

  Put them all in `permitmap/app/config.py` as one frozen dataclass read once at startup.
- **DB access:** open one connection at startup with `connect_lake()`, and use `con.cursor()` per request. Use parameterized SQL only, never string-formatted values. Filter on `latitude`/`longitude` columns with `BETWEEN`.
- **Permits ordering and cap:** `ORDER BY applied_date DESC NULLS LAST, permit_id LIMIT 2001`. If 2,001 rows come back, return 2,000 with `truncated: true`. Dates serialize as ISO `YYYY-MM-DD` strings, and nulls stay `null`.
- **Geocoder call:** `GET <url>?SingleLine=<q>&outSR=4326&maxLocations=5&f=json`, using `httpx` with a 5-second timeout. The response shape is ArcGIS standard: `candidates[]` with `address`, `score` and `location{x: lon, y: lat}`. Take the highest score. An ArcGIS `error` object in a 200 body counts as an upstream failure (502).
- **Geocoder test fixture:** `tests/fixtures/geocoder_candidates_sample.json` (synthetic; say so in `tests/fixtures/README.md`). Tests stub the HTTP call with `respx` or `httpx.MockTransport`, and never use the network.
- **The 1,000 ft ring** is computed in the browser as a 64-point polygon of radius 304.8 m around the point (equirectangular approximation is fine at this scale). It's added as a GeoJSON source `search-ring` with a line layer.
- **Moving the map:** debounce `moveend` by 250 ms, and cancel an in-flight request with `AbortController` when a new one starts.
- **Blank test style:** `permitmap/app/static/blank-style.json` is `{"version": 8, "sources": {}, "layers": [{"id": "bg", "type": "background", "paint": {"background-color": "#f8f8f8"}}]}`.
- **UI test harness (`tests/ui/conftest.py`):**
  - Build the fixture lake if it's missing.
  - Start the app with uvicorn in a background thread on a free port, with `PERMITMAP_STYLE_URL=/static/blank-style.json`.
  - Launch Chromium with `executable_path=os.environ.get("PW_CHROMIUM_PATH")` when set. In the build sandbox set `PW_CHROMIUM_PATH=/opt/pw-browsers/chromium`. Do not run `playwright install`.
  - Pin `playwright==1.56.0`. It was verified on 2026-10-09 to launch that binary headless with WebGL on.
  - Wait for the map with `page.wait_for_function("window.permitMap && window.permitMap.loaded()")`.
- **Clicking a pin in tests:** use `permitMap.project([lon, lat])` to get pixel coordinates, then `page.mouse.click`.
- **Packaging:** change `[tool.setuptools]` in `pyproject.toml` so subpackages and `static/**` are included (`packages.find` with `include = ["permitmap*"]`, plus `package-data`).
- **The detail panel** is a `<aside id="permit-panel">` with `role="dialog"` and an `aria-label` set to the address. The close button has `aria-label="Close"`. The search box is a `<form id="search">` with `<input name="q">`. The message area is `<div id="status" role="status">`.

## Facts found (2026-10-09)

- The City of Seattle locator `locators/MultiRoles/GeocodeServer` is public (ArcGIS Server 11.3) and fetchable from outside the sandbox. Its single-line parameter name wasn't confirmed. `SingleLine` is the ArcGIS default. If it fails on the server, the fix is a one-line change to the parameter name, made in a follow-up.
- The OpenFreeMap style URLs are `https://tiles.openfreemap.org/styles/{liberty,positron}`. They need no key, and their attribution comes from the style.
- In the sandbox, `playwright==1.56.0` with `executable_path=/opt/pw-browsers/chromium` launches headless with WebGL on. The npm registry is reachable (`maplibre-gl@4.7.1` resolves).

## Risks / Trade-offs

- **Third-party runtime dependencies** (OpenFreeMap, the city geocoder): if either goes down, the map or search degrades but the app stays up. The style URL and geocoder URL are both configuration, so swapping one is not a code change.
- **The 2,000 cap hides older permits in dense areas at zoom 12–13.** The truncation note makes this visible. Clustering is a later change if it bothers the PM.
- **Fixture coordinates are synthetic,** so UI tests prove behavior, not real-world density.

## Open questions (do not block this change)

1. Should the list view (sorted by distance) come next, or engagement-event wiring? Decide in the next design session.
2. If the city locator's parameter name turns out wrong on the server, is switching to Nominatim acceptable, or should we keep the city locator? (Default: keep the city locator and fix the parameter.)

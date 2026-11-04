# Design: page-engagement-events

Design session 2026-11-03 (evening), second change of the night. No open questions block building.

## Context

`permitmap/events.py: record_event(r, event_type, session_id, ...)` validates the type, coarsens coordinates to 3 decimals, hashes the IP with `EVENT_IP_SALT` and the UTC date (or drops it when no salt is set), and `XADD`s to `events:v1`. `permitmap/drain_events.py` moves the stream to Parquet. Both are tested with `fakeredis`. The app (`permitmap/app/main.py`, `create_app(config)`) has no Redis connection and the page sends nothing.

`live-permits-ingest` (approved earlier tonight) edits some of the same files. This change is written against today's `main` and doesn't depend on it.

## Goals / Non-Goals

**Goals:** every search, pin click, filter change and settled map view from the page lands on `events:v1`, anonymously, with no effect on the map if Redis is slow or missing.

**Non-goals:** see the proposal's "Out of scope".

## Decisions (PM, 2026-11-03)

| # | Decision | Reason |
|---|---|---|
| D1 | **Keep the search text exactly as typed** (up to 200 characters). | Most useful for seeing what people look for and for debugging searches that miss. The PM accepted that an exact address plus a same-day visitor hash can point to someone's home. |
| D2 | **One session ID per browser, renewed after 30 days idle**, kept in `localStorage`. | Shows whether a friend sent the link comes back. |

## Decisions (agent, accepted by the PM with the design)

| # | Decision | Reason |
|---|---|---|
| A1 | **Honor Global Privacy Control and Do Not Track** by sending nothing. | Cheap, and consistent with "anonymous, no login." |
| A2 | **Fire-and-forget sends** with `fetch(..., {keepalive: true})`; errors are swallowed, nothing awaits them. | Analytics must never slow or break the map; `keepalive` lets a click event finish if the user navigates to the city permit page. |
| A3 | **Events off when `REDIS_URL` is unset**: the endpoint answers 503 and the page ignores it. | Local runs on fixtures need no Redis. |
| A4 | **Redis socket timeouts of 0.5 s** for connect and read. | A down Redis answers 503 in about a second instead of hanging a worker. |
| A5 | **Client IP:** `request.client.host`, or the left-most `X-Forwarded-For` address only when `PERMITMAP_TRUST_PROXY=1`. | Behind Coolify's proxy the real visitor IP is in the header; trusting it by default would let anyone forge it. Deployment sets the flag. |
| A6 | **`map_move` only at zoom ≥ 12, once the map settles, at most once per 2 s.** | Matches the zoom gate for pins and keeps the stream from filling with drag noise. |
| A7 | **`referrer` comes from `document.referrer` in the browser**, not the `Referer` header. | The header would always be the map page itself; the browser value says where the visitor came from. |
| A8 | **No `list_open` events** until a list view exists. | Nothing to send. |

## Build notes (for the builder; decisions already made)

- **Config:** add `redis_url: str | None` (env `REDIS_URL`, default `None`) and `trust_proxy: bool` (env `PERMITMAP_TRUST_PROXY == "1"`, default `False`) to `permitmap/app/config.py`.
- **Redis client:** `create_app(config, redis_client=None)`. If `redis_client` is passed (tests use `fakeredis.FakeRedis()`), use it; else if `config.redis_url`, create `redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)` once at startup without connecting; else events are disabled. Store on `app.state.redis`.
- **Endpoint** in new `permitmap/app/events_api.py` (`register(app)` called from `main.py`): read the raw body; over 2,048 bytes → 413. Parse JSON; a non-object → 400. Allowed keys exactly `event_type, session_id, search_text, lat, lon, filters, permit_id, referrer`; anything else → 400 naming the field. Validate per the spec delta (session ID regex `^[0-9a-f]{32}$`; `lat`/`lon` must be JSON numbers when present; `filters` keys only `stage`, `work_type`, each a list of strings). Then call `record_event(r, ..., user_agent=<header, truncated to 300>, ip=<A5>)`. `ValueError` → 400; any `redis.exceptions.RedisError` → 503 `{"error": "events unavailable"}`; disabled → 503 `{"error": "events disabled"}`; success → 204 with no body.
- **Client** in new `permitmap/app/static/events.js`, loaded in `index.html` before `app.js`. Exposes `window.permitEvents = { send(type, fields), sessionId(), enabled }`.
  - `enabled` is false when `navigator.globalPrivacyControl === true` or `navigator.doNotTrack === "1"` or `window.doNotTrack === "1"`.
  - Session: `localStorage` key `permitmap.session` holding `{"id": "...", "last": <ms epoch>}`. New ID when missing, unparsable or `now - last > 30 days`; update `last` on each send. ID = `crypto.randomUUID().replace(/-/g, "")`. Wrap every storage access in try/catch and fall back to an in-memory ID.
  - `send` posts `{event_type, session_id, referrer: document.referrer.slice(0, 500) || undefined, ...fields}` as JSON with `keepalive: true`, `.catch(() => {})`, and returns nothing.
- **Hooks in `app.js`:**
  - `search`: in the geocode `.then`, send once per submit with `search_text` = the trimmed input; include `lat`/`lon` on a 200, omit them on 404 or 502 or network error.
  - `permit_click`: where the panel opens from a pin click, with `permit_id` and the feature's coordinates.
  - `filter_change`: on the filter form's `change`, with `filters` = `{stage: [...], work_type: [...]}` of checked values.
  - `map_move`: on `moveend` at zoom ≥ 12, throttled to one send per 2,000 ms, with the map center.
- **UI tests** capture events with `page.route("**/api/events", ...)`, recording each request's JSON and fulfilling with 204 (or 503 for the "store down" test). Simulate GPC with `page.add_init_script("Object.defineProperty(navigator, 'globalPrivacyControl', {get: () => true})")`. Test the 30-day rule by seeding `localStorage` with `last` set 31 days back via `add_init_script` before load.

## Risks

- **Rebase with live-permits-ingest.** Both edit `main.py`, `config.py`, `index.html`, `app.js` and `README.md`. The edits are additive and in different places; whichever PR merges second needs a rebase.
- **D1 privacy trade-off.** Exact addresses are stored. If the app gets real traffic, revisit dropping the house number before adding accounts or sharing event data.

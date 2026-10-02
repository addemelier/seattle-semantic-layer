# Design: permit-map-destination

Grill-me session, 2026-10-02. This change resets the project's destination (D1–D22) and builds the first, offline slice (see "Build notes").

## Decisions (PM, 2026-10-02)

| # | Decision | Reason |
|---|---|---|
| D1 | **The product is a live, shareable Redfin-style map of Seattle permits.** The user opens the map, clicks an open permit and sees its details. dbt bronze/silver/gold and a semantic layer are built in service of the app. | The PM wants to build something he would use himself and that brings in data. |
| D2 | **The three-way LLM accuracy benchmark is dropped.** It is no longer a goal, a gate or a README headline. | It was inspiration; the app is what's interesting. |
| D3 | **The user is a neighbor or homebuyer, and specifically the PM himself.** Design choices are judged by "would I use this when looking at a house?" | Builds for a real user who is always available. |
| D4 | **"Open permit" = any permit not in an expired, finaled/completed or closed state.** This includes applied, in review, issued and inspections in progress: anything that could still get built. | The user wants to know what could change near an address. |
| D5 | **v1 data is D2 (SDCI building permits) plus D4 (neighborhood geography).** D1 licenses and D3 food inspections are out of scope. | One source to ingest, model and map. |
| D6 | **It's a live app, not a static site.** It starts on paid hosting at a modest monthly cost and migrates later to the PM's Raspberry Pi. | It needs to be shareable, with live engagement capture. |
| D7 | **Permit data refreshes daily. User and engagement data is captured live.** | Daily is enough for permits; engagement is the part that's live. |
| D8 | **Orchestration is a Dagster job, run either on the Raspberry Pi or on a Dagster Cloud instance (resolved by D13).** | Moves ingest off the build sandbox. |
| D9 | **Map UX:** an address search zooms to the address with a 1,000 ft ring. Pins are colored by stage (In review / Issued / Under inspection). Filters: stage, work type (new building, addition/alteration, demolition, ADU), minimum valuation, applied-within. Clicking a pin opens a side panel with address, description, work type, stage, applied/issued/last-inspection dates, declared valuation, units added/removed, contractor and a link to the city permit page. A list view shows the permits in view, sorted by distance. | Exactly what the PM wants when looking at a house. |
| D10 | **Engagement = anonymous product analytics, no login.** Anyone can use search. Capture broadly ("vacuum it up"): searches, permit clicks, filter use and similar events. Accounts, watchlists and alerts come later, only if people beyond the PM use it. | Learn whether anyone uses it before building auth. |
| D11 | **Stack preferences:** the most modern data tooling available. DuckDB is preferred. Avoid Postgres. Use Redis (or a Redis-compatible store) to broaden the PM's data vocabulary. The PM is not versed in web hosting, so pick the simplest deploy and upkeep. | PM preference. |
| D12 | **Hosting budget is $15–20/mo** if that buys meaningfully easier deployment and upkeep. A later migration to the Raspberry Pi stays a goal. | PM preference. |
| D13 | **Dagster OSS** runs in the same deployment as the app, with a daily schedule. | Simple ETL; no Dagster Cloud needed. |
| D14 | **Repo identity:** archive `docs/product-brief.md` and `docs/eval-questions.md` to `docs/archive/` (they can come back later). Rename the repo. Rewrite the README and CLAUDE.md for the new destination. | The old destination is dropped (D2). |
| D15 | **v1 finish line:** the PM can send a friend a URL; they search an address, see open permits on a map, click one and get details. Permit data refreshes daily with no manual step, and engagement events are captured live. Post-v1: Pi migration, accounts, alerts. | Accepted as proposed. |
| D16 | **Redis 8 does two jobs:** (1) it's the live event inbox, as a Redis Stream that a drain step moves to Parquet; (2) it caches hot API responses (cache is a later change). AOF persistence is on in deployment. No Postgres anywhere. | Live capture without Postgres; broadens the PM's vocabulary (streams, consumer groups, TTL). |
| D17 | **Hosting:** one small Hetzner ARM VPS running Coolify, with the whole stack in one Docker Compose file. The same setup moves to the Raspberry Pi later. The PM does the account and server setup himself from a runbook (later change). | Cheapest and simplest to keep the shared disk between Dagster and the app; rehearses the Pi move. |
| D18 | **Event payload:** what is clicked and searched matters most. Store event type, search text, map position rounded to ~100 m, filters, permit clicked, random session id, user agent, referrer and timestamp. IP is optional for the PM; since it's easy, store only a daily-salted SHA-256 hash and **never the raw IP**. No event data is ever committed. | The PM mainly wants clicks; the hash gives unique-visitor counts at no privacy cost. |
| D19 | **Storage: DuckLake with a SQLite catalog** for bronze/silver/gold. Pre-decided fallback: if dbt-duckdb cannot target DuckLake cleanly, use a single DuckDB file and say so in the PR. Don't block. | "Most modern" option the PM chose; the fallback avoids a stall. |
| D20 | **Clean slate:** the PM's other, similar repo (built without specs or agents) is dropped. The PM archives it on GitHub himself; it's outside this session's access. Rename this repo (proposed: `seattle-permit-map`); the PM does it in GitHub settings, because the scheduled routines are pinned to the current name. | Move forward with this attempt only. |
| D21 | **v1 target date: 2026-11-13** (6 weeks). | Accepted. |
| D22 | **Build-time data is a committed synthetic fixture** that uses the SDCI building-permits column names. The first real Socrata pull happens on the VPS and validates the names. | The build sandbox can't reach `data.seattle.gov` (403), and every task needs an offline verification command. |

## Facts found

- The cloud build sandbox gets HTTP 403 from `data.seattle.gov` **and** from `extensions.duckdb.org`, so `INSTALL ducklake` fails there.
- DuckLake works offline via PyPI: `pip install duckdb==1.5.5 duckdb-extensions duckdb-extension-ducklake duckdb-extension-sqlite_scanner`, then `from duckdb_extensions import import_extension; import_extension("ducklake"); import_extension("sqlite_scanner")`, then `ATTACH 'ducklake:sqlite:<catalog.sqlite>' AS lake (DATA_PATH '<dir>/')`. Verified in-session on 2026-10-02. Keep the `duckdb` pin equal to the extension packages' version.
- SDCI building-permit column names used for the fixture are **unverified** (from memory of the Socrata dataset `76t5-zqzr`): `permitnum, permitclass, permitclassmapped, permittypemapped, permittypedesc, description, housingunitsremoved, housingunitsadded, estprojectcost, applieddate, issueddate, expiresdate, completeddate, statuscurrent, originaladdress1, originalcity, originalstate, originalzip, contractorcompanyname, link, latitude, longitude`.

## Build notes (for the builder; decisions already made)

- **Status sets.** Closed: `completed, expired, closed, canceled, cancelled, withdrawn`. Known open: `application accepted, reviews in process, awaiting information, corrections required, additional info requested, ready for issuance, issued, reviews completed, scheduled, inspections completed`. Compare on `lower(trim(statuscurrent))`. Anything else counts as open and is reported by a `warn`-severity dbt test.
- **work_type.** ADU if `description` matches (case-insensitive) `\b(a?adu|dadu)\b` or contains `accessory dwelling`. Otherwise `demolition` if `permittypemapped` or `permittypedesc` contains `demolition`. Otherwise `new_building` if `permittypedesc` = `New` or `permittypemapped` contains `new`. Otherwise `addition_alteration`.
- **Dedupe:** one row per `permitnum`, keeping the latest `applieddate` and breaking ties by the latest `issueddate`.
- **Paths:** DuckLake catalog `data/lake/catalog.sqlite`, data files `data/lake/files/`, event landing `data/landing/events/date=YYYY-MM-DD/part-<first-stream-id>.parquet`. The whole of `data/` is gitignored.
- **Redis stream** `events:v1`, approximate `MAXLEN ~ 1000000`, consumer group `drainer`. Salt from env `EVENT_IP_SALT`; if unset, ip_hash is null and the IP is discarded.
- **Tests** use `fakeredis`; no real Redis is needed at build time.
- **dbt profile** lives at `dbt/profiles.yml` (no secrets), target `fixture`.

## CLAUDE.md replacement text (task 1)

Replace the paragraph under the H1 (it starts "A public benchmark showing...") with:

> A live, shareable Redfin-style map of open Seattle building permits: search an address, see what could get built nearby, click a permit for details. The dbt medallion (DuckLake) and a semantic layer are built to serve the app; anonymous engagement events flow back into the same warehouse. Built on Seattle open data.

Replace the whole `## Project constraints` section body with:

> - **Storage:** DuckLake (SQLite catalog) via DuckDB. No Postgres.
> - **Stack:** Python 3.11+, dbt-core + dbt-duckdb, Dagster OSS, FastAPI, MapLibre front end, Redis 8 (event stream + cache). One Docker Compose file, arm64 and amd64.
> - **Hosting:** Hetzner ARM VPS with Coolify; later a Raspberry Pi. Budget ≤ $20/mo. Builders never touch hosting accounts or credentials.
> - **Data:** Seattle Open Data via Socrata (SODA) only, refreshed daily by Dagster on the server. Ingest is idempotent and quarantines malformed rows. Build-time verification uses committed fixtures in `tests/fixtures/`, never the network.
> - **Engagement data:** anonymous; never store raw IPs; never commit event data.
> - **User:** the PM, as a neighbor or homebuyer. When in doubt, ask "would he use this when looking at a house?"
> - Public repo hygiene: personal accounts only, no employer names, code, schemas or naming conventions from anywhere else.

## Open questions (do not block this change)

1. **"Under inspection" stage (D9):** the building-permits dataset has no inspection dates. Options: add the SDCI inspections dataset later, or drop the third stage. Decide in a future design session. This change ships `in_review` / `issued` only.
2. Neighborhood geography source for D4 (Community Reporting Areas or the neighborhood atlas), needed for the spatial-join change.

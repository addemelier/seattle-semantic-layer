> **NEXT QUESTION (session paused mid-grill, 2026-10-02):** round 4 is open: Redis's role (events stream and cache), hosting provider, what event fields are captured (IPs, search text), gold storage format (DuckDB file or DuckLake), what "the other attempt" to clean out refers to, and the v1 date. Not APPROVED; do not build.

# Design: permit-map-destination

Grill-me session, 2026-10-02. This change resets the project's destination. No build tasks yet.

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

## Facts found

- The cloud build sandbox gets HTTP 403 from `data.seattle.gov`, so unattended builders cannot pull live Socrata data unless that domain is allowlisted.

## Open questions (round 4)

1. Redis's role: event stream, cache, or both; Redis or Valkey
2. Hosting provider within $15–20/mo
3. Event payload and privacy: raw IPs, searched address text
4. Gold storage: a single DuckDB file or DuckLake
5. What "the other attempt" to clean out refers to; who renames the repo, and the new name
6. v1 target date

> **NEXT QUESTION (session paused mid-grill, 2026-10-02):** round 3 is open: detail panel and interactions, what "engagement data" means, app stack, hosting and budget, where Dagster runs, repo identity, and the v1 finish line. Not APPROVED; do not build.

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
| D8 | **Orchestration is a Dagster job, run either on the Raspberry Pi or on a Dagster Cloud instance (open, see round 3).** | Moves ingest off the build sandbox. |

## Facts found

- The cloud build sandbox gets HTTP 403 from `data.seattle.gov`, so unattended builders cannot pull live Socrata data unless that domain is allowlisted.

## Open questions (round 3)

1. Detail panel contents, search and filters
2. What "user data and engagement" means: anonymous analytics, or accounts, saved permits and alerts
3. App stack
4. Hosting provider, monthly budget, domain
5. Where Dagster runs, and whether builders test against committed fixtures
6. Repo identity: rename, what happens to the old brief and eval docs, CLAUDE.md rewrite
7. v1 finish line and date

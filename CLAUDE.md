# seattle-semantic-layer — working agreement

A live, shareable Redfin-style map of open Seattle building permits: search an address, see what could get built nearby, click a permit for details. The dbt medallion (DuckLake) and a semantic layer are built to serve the app; anonymous engagement events flow back into the same warehouse. Built on Seattle open data.

The human on this repo is the **product manager**. He designs and approves; agents implement. There are two modes, and every session is in exactly one of them.

---

## Mode 1 — Design session (human present, ~30 min)

Goal: leave the session with a change that is **specified well enough to build without asking him anything.**

1. **Read first:** `openspec/specs/` (what exists), `openspec/changes/` (what's in flight, including any `BLOCKED.md`), `docs/product-brief.md`, `docs/eval-questions.md`. Open the session with a 3-line status: what's built, what's in flight, any blocked questions waiting on him. Answer blocked questions before starting anything new.
2. **Shape the idea** with the `brainstorming` skill. Pick its path honestly; most changes here are *Bounded*.
3. **Stress-test it** with `/grill-me` when he asks, or when a design has unresolved decisions. Every decision he makes goes into the change's `design.md`.
4. **Write the change with OpenSpec**, not with brainstorming's own outputs:
   - **Override:** where `brainstorming` says to write `docs/superpowers/specs/...` and invoke `writing-plans`, instead run `/opsx:propose` and put the design into the OpenSpec change (`proposal.md`, `design.md`, `specs/`, `tasks.md`). Do not create `docs/superpowers/`.
5. **Tasks must be agent-sized** (see "Task rules" below). If a task needs a judgment call, the call is made now, in `design.md`, not left for the builder.
6. **Approval:** when he says the change is approved, create an empty file `openspec/changes/<change-id>/APPROVED` and commit. That file is the only signal the builder acts on.

Sessions are short. If time runs out mid-design, commit what exists without `APPROVED` and note the next question at the top of `design.md`.

---

## Mode 2 — Build run (unattended)

Triggered on a schedule. No human is watching. Do not ask questions; there is no one to answer.

1. Find the **oldest** change directory that contains `APPROVED`, has unchecked tasks in `tasks.md`, and has **no** `BLOCKED.md`. If none, stop and report "nothing approved to build."
2. Create or reuse branch `build/<change-id>` from `main`.
3. Implement tasks **in order** with `/opsx:apply`. After each task: run its verification command, check it off in `tasks.md`, commit (`<change-id>: <task>`).
4. **Never edit** `proposal.md`, `design.md` or `specs/` in build mode. The spec is the PM's. If the spec is wrong, impossible, or ambiguous, that is a blocker, not a judgment call.
5. **On a blocker:** write `openspec/changes/<change-id>/BLOCKED.md` containing: the task, what you tried, the exact decision needed, and your recommended answer with one-line reasoning. Commit, stop work on that change, and move to the next approved change if one exists.
6. **Finish:** push the branch and open (or update) one PR per change. PR description = tasks done, verification output, anything surprising. When all tasks are checked and verified, say so in the PR; the PM merges and runs `/opsx:archive`.
7. Budget: stop after ~60 minutes of work or 8 tasks, whichever comes first. Partial progress committed is fine.

---

## Task rules (for writing `tasks.md`)

- One task ≈ 15–45 minutes of agent work, one concern, one commit.
- Every task ends with a **verification command** that exits 0 on success (`dbt build -s ...`, `pytest tests/...`, `python -m harness --dry-run`). No command, no task.
- No task requires credentials, paid services, or network access beyond the public open-data APIs and package registries.
- Name files and models in the task; don't make the builder invent structure.

---

## Project constraints

- **Storage:** DuckLake (SQLite catalog) via DuckDB. No Postgres.
- **Stack:** Python 3.11+, dbt-core + dbt-duckdb, Dagster OSS, FastAPI, MapLibre front end, Redis 8 (event stream + cache). One Docker Compose file, arm64 and amd64.
- **Hosting:** Hetzner ARM VPS with Coolify; later a Raspberry Pi. Budget ≤ $20/mo. Builders never touch hosting accounts or credentials.
- **Data:** Seattle Open Data via Socrata (SODA) only, refreshed daily by Dagster on the server. Ingest is idempotent and quarantines malformed rows. Build-time verification uses committed fixtures in `tests/fixtures/`, never the network.
- **Engagement data:** anonymous; never store raw IPs; never commit event data.
- **User:** the PM, as a neighbor or homebuyer. When in doubt, ask "would he use this when looking at a house?"
- Public repo hygiene: personal accounts only, no employer names, code, schemas or naming conventions from anywhere else.

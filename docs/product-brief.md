# Product brief

## The claim

Teams bolt an LLM onto their warehouse and it confidently returns wrong numbers. The fix isn't the model; it's upstream, in the semantic layer. This repo proves that with a benchmark anyone can rerun.

## The headline deliverable

An accuracy table at the top of the README: the same 30 business questions, the same model, the same prompt, three different contexts.

| Configuration | What the model sees |
|---|---|
| Raw | The raw source schema |
| Gold | A cleaned, documented gold layer (consistent entities, column-level descriptions) |
| Gold + semantic model | Gold plus metric definitions, synonyms, join paths, allowed filters and refusal rules |

Expected shape (to be replaced by whatever actually happens): roughly 11/30 → 20/30 → 28/30. Cleaning the warehouse gets most of the Tier 2 gains; only the semantic model gets Tier 3 (correct refusals) off zero.

Under the table: two failure transcripts showing the generated SQL going wrong at the raw tier.

## Data

| # | Dataset | Source | Why |
|---|---|---|---|
| D1 | Business license tax certificates | City of Seattle open data | Lifecycle ambiguity (open vs. active vs. issued) |
| D2 | Building permits | Seattle SDCI | Status and date ambiguity (applied / issued / completed) |
| D3 | Food establishment inspections | King County | Grain trap: one row per inspection, not per business |
| D4 | Neighborhood geography | Seattle neighborhood atlas / Community Reporting Areas | Makes "in Ballard" mean something |

Open question carried from planning: which geography system is canonical for D4 (the other becomes a synonym set). Eval Q26 depends on it.

## Architecture

```
Socrata APIs → ingest (Python, idempotent, quarantine bad rows) → Parquet landing
  → dbt on DuckDB: bronze → silver → gold (fully documented)
  → semantic model (dbt semantic layer / MetricFlow YAML; Cortex Analyst YAML committed for parity)
  → MCP server exposing gold + semantic layer as tools
  → eval harness: question → config → generated SQL → result → compare to reference → log
Dagster orchestrates ingest → dbt → eval.
```

## Scope tiers

- **Tier 1, must ship:** ingest with quarantine and idempotent rerun · dbt medallion with documented gold · dbt tests · semantic model YAML · eval harness with the three-way comparison · README with the results table.
- **Tier 2, high value:** MCP server · Dagster orchestration · Elementary data-quality report · write-up post.
- **Tier 3, if fun:** Parquet partition-pruning benchmark · msgspec parse benchmark · model-ready feature table · dbt docs on GitHub Pages.

The eval harness is non-negotiable. Tier 1 minus the MCP server still makes the argument.

## README order

1. The results table, above the fold
2. What this is, in two sentences
3. One architecture diagram
4. Why the semantic layer is the product (three paragraphs)
5. Run it yourself: clone + one command
6. Data quality: quarantine, idempotency, tests
7. Snowflake parity (linked)
8. What changes at 60TB

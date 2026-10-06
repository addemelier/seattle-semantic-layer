# Eval question set — v1 (draft, PM to review)

30 questions, each run three ways (raw / gold / gold + semantic model) with an identical prompt. **Status: draft.** Cut or rewrite any question whose reference answer can't be defended.

## Scoring

- **Correct** = matches the reference answer computed from the documented definition. Off-by-a-definition is wrong.
- **Refusal questions** score correct only if the system declines **and names the ambiguity**. A confident number is a fail even if it matches one reading.
- Run each question 3× and take the majority.
- Log generated SQL for every run.

## Tier 1 — Unambiguous (8)

The baseline must not be a strawman: raw should get most of these.

| # | Question | Reference definition |
|---|---|---|
| 1 | How many business license tax certificates are in the dataset? | Row count, D1 |
| 2 | How many building permits were issued in 2024? | D2, issued date year = 2024 |
| 3 | What was the lowest inspection score recorded in 2024? | D3, min score, inspection year = 2024 |
| 4 | Which ZIP code has the most business licenses on record? | D1, group by ZIP, count |
| 5 | How many distinct food establishments appear in the inspection data? | D3, distinct establishment id, **not** row count |
| 6 | What is the average building permit valuation for permits issued in 2024? | D2, mean valuation, issued 2024 |
| 7 | How many inspections happened in each month of 2024? | D3, count by month |
| 8 | What are the five most common permit types? | D2, group by type, count |

## Tier 2 — Business-meaning ambiguity (16)

| # | Question | Ambiguity | Semantic-layer resolution |
|---|---|---|---|
| 9 | How many new restaurants opened in Ballard last year? | What counts as a restaurant; what "opened" means; what "Ballard" is | `restaurant` = defined NAICS set; `opened` = first license issue date; Ballard = D4 polygon, not ZIP |
| 10 | Which neighborhoods had the biggest jump in permit activity? | Count or valuation; baseline; filed or issued | Count of permits issued; YoY % vs prior full year; D4 neighborhood |
| 11 | How many active businesses are there in Seattle? | Licensed vs unexpired vs renewed | Status in active set **and** expiry in future |
| 12 | What's the worst-performing neighborhood for food safety? | Mean, median, failure rate, critical count | Share of inspections with ≥1 red/critical violation, min 30 inspections |
| 13 | How long does it take to get a building permit? | To issue or final; mean or median; which types | Median days application → issued, issued permits only |
| 14 | Are restaurant openings up or down this year? | As Q9, plus partial year | As Q9, YTD vs prior-year YTD |
| 15 | Which neighborhood has the most restaurants per capita? | No population data | Must state the missing input |
| 16 | How many businesses closed last year? | Closure isn't recorded | Expired and not renewed within 90 days; labelled inferred |
| 17 | Average time between food inspections per establishment? | Per establishment vs per interval; routine vs follow-up | Mean gap between routine inspections, per establishment then averaged |
| 18 | Which permit types take longest to approve? | As Q13 plus small-n | As Q13, min 20 permits per type |
| 19 | How much construction investment happened in Capitol Hill last year? | Declared vs actual; issued vs completed; geography | Sum of declared valuation on permits issued, D4; labelled declared |
| 20 | Which businesses have the most permits? | No shared key D1↔D2 | Documented entity-resolution rule; labelled approximate |
| 21 | What share of restaurants passed their most recent inspection? | "Passed" isn't a field | No red/critical violations on latest inspection per establishment |
| 22 | Is food safety improving? | Measure, period, volume | Trend in the Q12 metric, rolling 12 months, ≥3 years |
| 23 | Which neighborhood is growing fastest? | Businesses, permits or valuation | `growth` = YoY change in new business licenses; alternatives named |
| 24 | How many food trucks are there? | Mobile vendor categories in D1 and D3 | Defined category set, deduplicated across sources |

## Tier 3 — Should refuse (6)

| # | Question | Why it must refuse |
|---|---|---|
| 25 | What's our worst-performing category? | "Worst", "performing" and "category" all undefined |
| 26 | How many businesses are in the U District? | No single official boundary; must ask which definition |
| 27 | Did the new health regulations work? | No regulation data; causal question |
| 28 | Which restaurant is the best? | Inspection score is compliance, not quality |
| 29 | How many people work at these businesses? | No employment data |
| 30 | Compare Seattle to Portland on permit activity | Only Seattle loaded |

## Open questions

1. Is there any usable key between D1 (licenses) and D3 (food establishments), or is Q24 also name matching?
2. Canonical geography for D4: Community Reporting Areas or the neighborhood atlas? (Q26 depends on it.)
3. Which questions can't be defended? Cut them. 24 defensible beats 30 hedged.

## Build order

1. Hand-write all reference answers as SQL against gold and commit them **before** any model run.
2. Harness: one Python module; question → config → SQL → result → compare → log; keep every transcript.
3. Run raw first. Same prompt at all three tiers.
4. Publish the table with two failure transcripts.

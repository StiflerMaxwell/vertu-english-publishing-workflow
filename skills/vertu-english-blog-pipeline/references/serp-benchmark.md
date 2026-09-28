# Post-selection SERP Benchmark

Contract: `serp-benchmark-v1`

## Purpose and position

Run this gate after the unchanged traffic scorer selects a candidate and before evidence-pack research, outlining or drafting. Candidate-time SERP observations help score a likely gap; this deeper benchmark turns the exact selected query and intent into a writing brief.

It may block, reframe or replace a selected direction. It may not silently change the query, alter the existing score or copy ranking pages.

## Source requirements

Use an authorised SERP provider or a reproducible browser research export. Do not make direct Google-result scraping a workflow dependency.

The normalised input must preserve:

- exact query, market, language, device, source method and observation time;
- at least five ranked result summaries with title, URL, rank and snippet;
- at least three HTTP-200, independently hosted body extracts with headings and word count;
- observed format type and value objects where available.

Thin, inaccessible or mismatched evidence is `SERP_BENCHMARK_SOURCE_BLOCKED`.

## Required outputs

For every selected article write:

- `serp-benchmark.json`
- `ranking-page-anatomy.json`
- `content-differentiation-brief.md`

Run:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_serp_benchmark.py \
  --input <normalised-serp-export.json> \
  --selected-query '<query>' \
  --selected-intent '<intent>' \
  --proposed-query '<query>' \
  --proposed-intent '<intent>' \
  --original-value-delta '<concrete article-specific value>' \
  --benchmark-output serp-benchmark.json \
  --anatomy-output ranking-page-anatomy.json \
  --brief-output content-differentiation-brief.md
```

## Verdicts

- `BENCHMARK_PASS`: evidence passes and the article has a concrete original-value delta. Continue to the evidence pack.
- `BENCHMARK_REFRAME`: the proposed query or intent differs materially. Return to normal candidate scoring.
- `BENCHMARK_REPLACE`: the direction merely repeats ranking coverage or offers only generic “more comprehensive” value. Select a distinct eligible replacement.
- `SERP_BENCHMARK_SOURCE_BLOCKED`: source coverage or exact context is invalid. Stop drafting that candidate.

## Original-value rule

The delta must name a deliverable a reader can use, such as a verified decision matrix, market-by-market comparison, source-backed timeline, cost/risk calculation, ownership checklist or original evidence synthesis. Vague quality claims are invalid.

Observe structure and missing coverage, not prose. Never copy wording, paragraph order, proprietary data, images or unsupported claims. The final article must cite its own primary evidence.

## QA handoff

The three outputs and their exact benchmark fingerprint are part of the production preflight bundle under `qa-handoff-v1`. Independent QA must verify that the final article visibly implements the declared original-value delta. Missing, mismatched or unimplemented evidence creates required finding `SERP_DIFFERENTIATION_MISMATCH`.

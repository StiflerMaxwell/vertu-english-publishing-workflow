# Direct Content Factor Model — v1.2

Use this contract when building and scoring serious topic candidates. It exposes 32 direct, source-backed factors instead of treating the seven production dimensions as the only visible signals.

## Activation boundary

The direct-factor model remains shadow-only for the production default:

- contract: `content-factor-model-v1`;
- score source: `computed_factor_v1_shadow`;
- factor count: 32;
- weight total: 100;
- minimum diagnostic coverage: 70%;
- production score, demand verdict, vetoes, eligibility, selection order and publication authority remain unchanged.

The active production score remains `computed_v3_12_0`. Do not use the shadow score to rescue or reject a production candidate.

The explicitly approved two-batch paired trial in `hybrid-factor-trial.md` may calculate `computed_hybrid_v3_16_0_trial` as a non-publishing challenger over the exact same candidate pool. It does not change the production default, and only the legacy control portfolio may continue downstream.

## Direct factor registry

| Factor | Weight | Raw value |
|---|---:|---|
| `keyword_planner_avg_monthly_searches` | 6 | searches |
| `keyword_planner_recent_searches` | 4 | searches |
| `keyword_planner_growth_pct` | 3 | percentage |
| `keyword_planner_stability` | 2 | ratio |
| `gsc_candidate_clicks` | 4 | clicks |
| `gsc_candidate_impressions` | 4 | impressions |
| `gsc_candidate_ctr` | 3 | ratio |
| `gsc_candidate_growth_pct` | 2 | percentage |
| `demand_provider_family_count` | 4 | count |
| `demand_market_count` | 3 | count |
| `official_trends_interest` | 4 | 0..100 |
| `official_trends_growth_pct` | 3 | percentage |
| `official_trends_market_count` | 2 | count |
| `official_trends_freshness_hours` | 2 | hours |
| `trend_persistence_periods` | 2 | count |
| `editorial_independent_coverage_count` | 2 | count |
| `editorial_community_velocity` | 1 | 0..100 |
| `primary_source_freshness_hours` | 2 | hours |
| `historical_discover_cluster_clicks` | 5 | clicks |
| `historical_discover_cluster_ctr` | 4 | ratio |
| `historical_search_cluster_clicks` | 4 | clicks |
| `historical_search_cluster_ctr` | 3 | ratio |
| `historical_ga4_engagement_rate` | 2 | ratio |
| `historical_cluster_growth_pct` | 2 | percentage |
| `serp_weak_result_count` | 3 | count |
| `serp_freshness_gap_days` | 2 | days |
| `sanity_exact_intent_overlap_count` | 5 | count |
| `cannibalisation_safety` | 3 | ratio |
| `visual_specificity_checks_passed` | 3 | count |
| `reader_decision_checks_passed` | 3 | count |
| `original_value_checks_passed` | 5 | count |
| `vertu_right_to_win_checks_passed` | 3 | count |

The scorer owns each factor's deterministic linear, inverse-linear or logarithmic transform. Candidate builders must not supply normalised values.

## Mandatory extraction step

Run the central extractor after the raw candidate and source artifacts exist and before the traffic scorer:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_content_factor_extractor.py \
  --input candidates.json \
  --output candidates-with-factors.json \
  --summary factor-extraction.json \
  --keyword-planner keyword-planner-expansion.json \
  --targeted-gsc targeted-gsc-demand.json \
  --realtime-trends realtime-trends.json \
  --source-velocity source-velocity.json \
  --sanity-inventory sanity-inventory.json
```

The extractor contract is `content-factor-extractor-v1`. It imports the scorer's factor registry so the factor count, names and transforms cannot drift between extraction and scoring. It must emit exactly 32 evidence rows per candidate and a fingerprinted `factor-extraction.json` summary with per-factor source states.

The input candidate may also carry these raw, provenance-bound blocks when produced upstream:

- `historical_cluster_metrics`: Discover clicks/CTR, Search clicks/CTR, GA4 engagement rate, compared-period growth and an evidence reference;
- `serp_metrics`: reproducible weak-result count, freshness-gap days and an evidence reference;
- `primary_source_published_at`: verified primary-source publication time;
- market-level demand evidence in the candidate's provider metrics.

An aggregate `dimension_evidence.*.score_100` is not a raw input for these factors and must not be reverse-engineered into one.

## Evidence contract

Every available factor requires `status=AVAILABLE`, `raw_value`, `observed_at` and at least one item in `evidence_refs`. A candidate-provided `score_100` is invalid. Count-based editorial factors must link to the booleans or evidence objects that produced the count.

Use exactly one source state:

- `AVAILABLE`: valid raw measurement and provenance;
- `SOURCE_UNAVAILABLE`: the authorised source or required raw artifact could not be read;
- `INSUFFICIENT_SAMPLE`: the source was read but lacks enough rows, periods or observations for this factor;
- `NOT_APPLICABLE`: the factor truthfully does not apply, such as official real-time Trends factors for a candidate with no exact official trend match.

`NOT_APPLICABLE` is excluded from the coverage denominator. `SOURCE_UNAVAILABLE`, `INSUFFICIENT_SAMPLE` and omitted `MISSING` factors add no score and reduce applicable coverage. Do not use zero, a guessed value or a stale prose summary.

```json
{
  "direct_factor_evidence": {
    "keyword_planner_avg_monthly_searches": {
      "status": "AVAILABLE",
      "raw_value": 8100,
      "observed_at": "2026-08-25T01:16:26Z",
      "evidence_refs": ["artifact://keyword-planner#query"]
    }
  }
}
```

## Output and retention

The extractor emits 32 raw evidence rows per candidate plus `factor-extraction.json`. The traffic gate then emits all 32 scored factor rows, `observed_weighted_score`, `coverage_normalized_score`, applicable and available weights, weighted coverage, source states and validation errors inside `traffic-demand.json`. No network service or new credential is introduced by the extractor.

Factor count is not proof of quality. Before production activation, measure source coverage, missingness, stability, correlation, leakage and association with executed Discover, Search and GA4 outcomes. Remove redundant or non-predictive factors. Activation requires replay safety, the existing performance-learning threshold, the Skill evolution scorecard and explicit authority.

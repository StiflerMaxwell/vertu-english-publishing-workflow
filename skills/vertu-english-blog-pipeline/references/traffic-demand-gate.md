# Traffic Demand Gate — v3.8.0

Use this contract before selecting or drafting an article. Its purpose is to prove that a candidate has a plausible Search or Discover acquisition path. It does not promise ranking or recommendation.

## Candidate evidence

Every serious candidate must record:

- candidate ID, title, slug, non-News section, outcome lane, portfolio bucket, dominant intent, and entities;
- each demand provider's status, observation window, fetch time, evidence reference, metrics, normalised score, and positive/negative interpretation;
- historical VERTU/GSC fit, trend velocity or timeliness, SERP gap, Discover story, original information gain, and VERTU right-to-win evidence;
- existing inventory overlap, cannibalisation risk, query boundary, cluster role, outbound internal destination, and inbound-link candidates;
- vetoes, validation errors, computed score, demand verdict, and selection verdict.
- one trend class from `REALTIME_HOT | RISING_SEARCH | EVERGREEN_SEARCH`, target markets and the evidence required by `realtime-trends.md`.
- one separate editorial signal from `EDITORIAL_BREAKOUT | CURRENT_CONFIRMED | NONE`, with the evidence required by `editorial-intelligence.md`.
- one audience-fit lane from `PREMIUM_DECISION_CORE | ADJACENT | EXPLORATION_CANDIDATE`; promote `EXPLORATION_CANDIDATE` to `EXPLORATION` only after the normal demand gate passes. Record mass recognisability, concrete decision intent, finalised historical cluster evidence and niche risk.

Allowed source states are `AVAILABLE` and `SOURCE_UNAVAILABLE`. An unavailable source requires a reason and fetch time. Never replace an unavailable metric with zero.

## Minimum demand rules

- `Search-first`: require at least two independent positive providers from different acquisition evidence systems. Accepted providers are candidate-level finalised GSC query/page evidence, official Google Trends comparison evidence, and authorised Google Ads Keyword Planner evidence. SERP observations, editorial/social velocity, primary-source recency and broad historical cluster adjacency are supporting evidence, not Search-demand providers.
- `Discover-first`: require a current-interest provider, historical VERTU cluster evidence, and a concrete feed-readable visual story.
- `Authority-first`: require at least one positive traffic provider and use `TEST`, not `STRONG`; limit authority/exploration to the soft portfolio allocation. In automatic runs, `TEST` is approved only by the active automation or standing-approval profile explicitly allowing authority experiments. Otherwise hold it for article-specific user approval.

Official primary-source timeliness can support Discover current interest. It does not substitute for Search demand on a Search-first candidate.

A verified `EDITORIAL_BREAKOUT` can support Discover current interest when the primary source, independent coverage or community velocity, broad reader consequence and visual story all pass. It cannot satisfy a Search-first provider minimum and cannot create `REALTIME_HOT`.

The user-approved premium/business strategy is candidate-pool and portfolio guidance only. It cannot satisfy any provider minimum. A `PREMIUM_DECISION_CORE` candidate still needs the same Search-first, Discover-first or Authority-first evidence as any other candidate.

## Score contract

| Dimension | Weight |
|---|---:|
| Market demand from positive providers | 25 |
| Historical VERTU/GSC fit | 20 |
| Trend velocity or timeliness | 15 |
| SERP/content gap | 15 |
| Discover story and packaging | 10 |
| Original information gain | 10 |
| VERTU right to win | 5 |

Every non-market dimension uses a bounded `score_100` plus at least one evidence reference and observation time. The reusable scorer calculates the weighted final score:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_content_traffic_gate.py score \
  --input candidates.json \
  --output traffic-demand.json \
  --max-articles 10 \
  --trend-mode realtime_hot
```

Selection requires computed score at least 80, `STRONG` or approved `TEST` demand verdict, no validation error, and no veto. A per-run script must never supply the final score.

For historical VERTU/GSC fit, reward the exact or adjacent reader cluster and decision pattern, not the presence of premium vocabulary. Evidence that commercial-airline cabin decisions performed well does not automatically support private aviation, generic hotels, yachts or all luxury travel. Preserve the narrowest supported boundary.

Historical cluster adjacency and candidate-level GSC demand are different fields. Cluster adjacency can score historical fit. It counts as a positive demand provider only when finalised GSC query/page evidence maps to the candidate's same normalised query and intent. Score a piece of evidence once and never add points for the audience-fit lane itself.

When a validated durable `performance-learning-v1` artifact exists, pass it with `--learning-priors`. When a validated, unexpired `performance-learning-provisional-v1` artifact exists, pass it with `--provisional-learning-priors`. The scorer first calculates normal eligibility, then applies both layers with one combined `-3..+3` cap to `selection_priority_score` for portfolio ordering. A 72-hour provisional prior may contribute at most one point and a 7-day provisional prior at most two. The raw score, demand verdict and vetoes remain unchanged. Missing, expired or invalid learning evidence is not a scoring failure; record it and continue without the affected layer.

## Source usage

### GSC

Use finalised data. Read query and page together, then add country and device when they materially change the opportunity. Record the recent 28-day change and the comparable prior window. Search Analytics may return top rows rather than an exhaustive export; record this limitation.

### Google Trends

Use the official Trends API Alpha when authorised. Otherwise use the official Trending Now RSS, CSV or a reproducible UI export and record geography, timeframe, access method and fetch time. Do not call a third-party trend estimate an official Google value. API unavailability does not permit skipping an accessible official public fallback.

A candidate labelled `REALTIME_HOT` must contain a positive `google_trends_realtime` or `google_trends_trending_now` signal with publication run ID, snapshot fingerprint, non-blank market, exact trend query, age no greater than 24 hours, positive approximate traffic, valid news confirmation, exact official Google URL and source method, plus a current verified primary source. The scorer must reconcile every declared market and metric against the same run's fingerprinted `realtime-trends.json`, `trend-market-map.json` and `hotness-gate.json`, require exact derivative contents, and live-fetch both the official feed and primary source; a flag or arbitrary evidence string is insufficient. Otherwise veto `unverified_realtime_hot_label`.

The deterministic scorer caps trend velocity at 100 for `REALTIME_HOT`, 75 for `RISING_SEARCH` and 45 for `EVERGREEN_SEARCH`.

### Keyword Planner

Use average monthly searches, geography, language, network, competition, and observation date only when the current Google Ads identity has authorised access. If unavailable, use `SOURCE_UNAVAILABLE`; do not infer a volume range.

### SERP and inventory

Inspect result types, current top-result freshness and authority, and whether VERTU already satisfies the intent. Reject duplicate intent, cannibalisation without a consolidation plan, angles that only differ by date or wording, and `no_defensible_content_gap` candidates that add no concrete information gain.

## Portfolio selection

Use these soft targets after every candidate independently passes:

- about 50% proven or adjacent demand;
- about 30% rising current interest;
- up to 20% controlled exploration or VERTU authority.

Keep no more than three articles dominated by one entity, reject duplicate intent, preserve meaningful topic diversity, and keep automatic content out of `news` and `/news/`. `max_articles` is a ceiling. Report `NO_TOPIC` slots when the evidence does not support the full maximum.

When enough candidates independently pass, prefer roughly 50–70% `PREMIUM_DECISION_CORE` across at least three distinct clusters, 20–30% `ADJACENT`, and no more than 20% `EXPLORATION`. This preference is applied after normal eligibility and before final portfolio ordering; it never creates a score adjustment.

## Cluster support

For every selected article, record:

- `cluster_role`: opportunity page, supporting page, update, or controlled test;
- `query_boundary`: what this page owns and what adjacent pages own;
- at least one relevant outbound internal destination;
- up to three existing pages that could naturally link to the new page;
- distribution risk when no relevant inbound source exists.

Producing an inbound-link proposal does not authorise a mutation to an existing article.

## Mature feedback

Run mature checkpoints through the deterministic classifier:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_content_traffic_gate.py classify-72h \
  --input performance/<slug>/72h.json \
  --output performance/<slug>/diagnosis.json
```

A mature sample-gate-passing checkpoint must receive a concrete diagnosis. Use repeated recent 72-hour and 7-day signals as expiring provisional ordering evidence only after the governed 48-hour promotion check. Promote only qualifying 28-day cohorts or verified experiments to durable scoring priors.

Apply `performance-learning.md`: a durable cohort prior requires at least three mature D+28 articles across two publication runs, unless a controlled experiment has a verified outcome. One spike never becomes a durable prior.

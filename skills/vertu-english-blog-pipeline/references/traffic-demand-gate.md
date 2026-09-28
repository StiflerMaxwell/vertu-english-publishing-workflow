# Traffic Demand Gate — v3.20.0

Use this contract before selecting or drafting an article. Its purpose is to prove that a candidate has a plausible Search or Discover acquisition path. It does not promise ranking or recommendation.

## Candidate evidence

Every serious candidate must record:

- candidate ID, title, slug, non-News section, outcome lane, portfolio bucket, dominant intent, and entities;
- each demand provider's status, observation window, fetch time, evidence reference, metrics, normalised score, and positive/negative interpretation;
- historical VERTU/GSC fit, trend velocity or timeliness, SERP gap, Discover story, original information gain, and VERTU right-to-win evidence;
- existing inventory overlap, cannibalisation risk, query boundary, cluster role, outbound internal destination, and inbound-link candidates;
- raw `direct_factor_evidence` for all 32 shadow factors, emitted by the central extractor with explicit available, source-unavailable, insufficient-sample and not-applicable states;
- vetoes, validation errors, computed score, demand verdict, and selection verdict.
- a fingerprint-valid `brand-mindset-fit-v1` result with `PASS`, `CORE_MINDSPACE | QUALIFIED_ADJACENT`, matched dimensions, rationale, evidence references, conflicts and expansion round.
- one trend class from `REALTIME_HOT | RISING_SEARCH | EVERGREEN_SEARCH`, target markets and the evidence required by `realtime-trends.md`.
- one separate editorial signal from `EDITORIAL_BREAKOUT | CURRENT_CONFIRMED | NONE`, with the evidence required by `editorial-intelligence.md`.
- one audience-fit lane from `PREMIUM_DECISION_CORE | ADJACENT | EXPLORATION_CANDIDATE`; promote `EXPLORATION_CANDIDATE` to `EXPLORATION` only after the normal demand gate passes. Record mass recognisability, concrete decision intent, finalised historical cluster evidence and niche risk.
- optional `d2tr_context` with an exact market and explicit topic-category, editorial-format-group, format-type or content-category mapping. This independent context is never a Search-demand provider and never creates a Google trend class.

Demand-provider source states remain governed by their source contracts. Direct-factor source states are `AVAILABLE | SOURCE_UNAVAILABLE | INSUFFICIENT_SAMPLE | NOT_APPLICABLE`; every non-available factor requires a reason and observation time. Never replace an unavailable metric with zero.

## Minimum demand rules

- `Search-first`: require at least two independent positive providers from different acquisition evidence systems. Accepted providers are candidate-level finalised GSC query/page evidence, official Google Trends comparison evidence, and authorised Google Ads Keyword Planner evidence. SERP observations, editorial/social/YouTube velocity, primary-source recency and broad historical cluster adjacency are supporting evidence, not Search-demand providers.
- `Discover-first`: require a current-interest provider, historical VERTU cluster evidence, and a concrete feed-readable visual story.
- `Authority-first`: require at least one positive traffic provider and use `TEST`, not `STRONG`; limit authority/exploration to the soft portfolio allocation. In automatic runs, `TEST` is approved only by the active automation or standing-approval profile explicitly allowing authority experiments. Otherwise hold it for article-specific user approval.

Official primary-source timeliness can support Discover current interest. It does not substitute for Search demand on a Search-first candidate.

A verified `EDITORIAL_BREAKOUT` can support Discover current interest when the primary source, independent coverage or community velocity, broad reader consequence and visual story all pass. It cannot satisfy a Search-first provider minimum and cannot create `REALTIME_HOT`.

The permanent brand-mindset gate is an eligibility prerequisite, not a demand provider. A `CORE_MINDSPACE` or `QUALIFIED_ADJACENT` candidate still needs the same Search-first, Discover-first or Authority-first evidence as any other candidate. `HOLD`, `REJECT` and `UNQUALIFIED` rows never enter scoring.

Provider independence is evaluated by acquisition-system family. Provider aliases, a `current_interest` signal derived from the same Keyword Planner artifact, or multiple views of one GSC export remain one family. The scorer may retain same-family supporting context, but it may not create an additional Search-demand provider.

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

Every non-market production dimension uses a bounded `score_100` plus at least one evidence reference and observation time. Before the reusable scorer, run the central 32-factor extractor:

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

Then calculate the weighted production and shadow outputs:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_content_traffic_gate.py score \
  --input candidates-with-factors.json \
  --output traffic-demand.json \
  --max-articles 10 \
  --trend-mode realtime_hot \
  --require-brand-mindset-gate \
  --brand-mindset-profile recovery
```

Selection requires a valid brand-mindset `PASS`, computed score at least 80, `STRONG` or approved `TEST` demand verdict, no validation error, and no veto. A per-run script must never supply the final score.

The active scorer emits `score_source=computed_v3_12_0`, `positive_demand_provider_families`, `demand_signal_qualifications` and one selected market-demand score per qualified family. Preserve these fields in `traffic-demand.json`; provider labels alone are not evidence of independence.

It also emits `direct_factor_model` using `content-factor-model-v1` and `computed_factor_v1_shadow`. This flat 32-factor diagnostic requires raw values and provenance, rejects candidate-authored `score_100`, reports applicable and available weighted coverage, and cannot change the production score, demand verdict, vetoes, eligibility, selection priority or portfolio. Coverage below 70% is `INSUFFICIENT_FACTOR_COVERAGE` and suppresses the diagnostic score. Read `direct-factor-model.md` completely before preparing candidate inputs.

For historical VERTU/GSC fit, reward the exact or adjacent reader cluster and decision pattern, not the presence of premium vocabulary. Evidence that commercial-airline cabin decisions performed well does not automatically support private aviation, generic hotels, yachts or all luxury travel. Preserve the narrowest supported boundary.

Historical cluster adjacency and candidate-level GSC demand are different fields. Cluster adjacency can score historical fit. It counts as a positive demand provider only when finalised GSC query/page evidence maps to the candidate's same normalised query and intent. Score a piece of evidence once and never add points for the audience-fit lane itself.

When a validated durable `performance-learning-v1` artifact exists, pass it with `--learning-priors`. When a validated, unexpired `performance-learning-provisional-v1` artifact exists, pass it with `--provisional-learning-priors`. When a valid `d2tr-discover-context-v1` artifact observed within eight hours exists, pass it with `--d2tr-market-context`. The scorer first calculates normal eligibility, then applies all ordering layers with one combined `-3..+3` cap to `selection_priority_score`. A 72-hour provisional prior may contribute at most one point, a 7-day provisional prior at most two, and exact D2TR market-context matches at most two. The raw score, demand verdict, Google trend class and vetoes remain unchanged. Missing, blocked, stale or unmatched D2TR context yields zero adjustment and never a penalty.

### Independent D2TR market context

Collect D2TR's public Discover volatility, format-group volatility, topic volatility, format interest and category heatmap three times daily at `00:00`, `08:00` and `16:00` Asia/Hong_Kong. Preserve each immutable snapshot and its fingerprint in the canonical Base `Discover 趋势快照` table and locally under `output/vertu-signals/trend-monitor/`. Delete only dedicated snapshot rows and local snapshot directories older than 30 rolling days; retain automation-ledger and monitoring receipts.

D2TR is an independent source and explicitly not official Google data. It may strengthen portfolio ordering only after a candidate already has score `>=80`, a passing demand verdict, no veto and a passing pre-draft Discover forecast. Award at most `+2` for a multi-dimensional breakout and at most `+1` for one strong or two moderate exact context matches. Require fresh source-generation timestamps and explicit candidate mappings. D2TR cannot create a demand provider, `RISING_SEARCH`, `REALTIME_HOT`, eligibility or veto relief.

## Source usage

### GSC

Use finalised data. Read query and page together, then add country and device when they materially change the opportunity. Record the recent 28-day change and the comparable prior window. Search Analytics may return top rows rather than an exhaustive export; record this limitation.

Qualify candidate-level GSC demand against the newest available finalised window in this order: recent, annual, generic. The selected window counts only when clicks are at least 3 or impressions are at least 100. If the recent window exists but is smaller, preserve it as `AVAILABLE` with `qualification_status=INSUFFICIENT_SAMPLE`; do not fall back to a larger annual window to manufacture demand. The annual or generic window is used only when the more recent fields are absent.

### Google Trends

Use the official Trends API Alpha when authorised. Otherwise use the official Trending Now RSS, CSV or a reproducible UI export and record geography, timeframe, access method and fetch time. Do not call a third-party trend estimate an official Google value. API unavailability does not permit skipping an accessible official public fallback.

A candidate labelled `REALTIME_HOT` must contain a positive `google_trends_realtime` or `google_trends_trending_now` signal with publication run ID, snapshot fingerprint, non-blank market, exact trend query, age no greater than 24 hours, positive approximate traffic, valid news confirmation, exact official Google URL and source method, plus a current verified primary source. The scorer must reconcile every declared market and metric against the same run's fingerprinted `realtime-trends.json`, `trend-market-map.json` and `hotness-gate.json`, require exact derivative contents, and live-fetch both the official feed and primary source; a flag or arbitrary evidence string is insufficient. Otherwise veto `unverified_realtime_hot_label`.

The deterministic scorer caps trend velocity at 100 for `REALTIME_HOT`, 75 for `RISING_SEARCH` and 45 for `EVERGREEN_SEARCH`.

### Keyword Planner

Use average monthly searches, geography, language, network, competition, and observation date only when the current Google Ads identity has authorised access. If unavailable, use `SOURCE_UNAVAILABLE`; do not infer a volume range.

### SERP and inventory

Inspect result types, current top-result freshness and authority, and whether VERTU already satisfies the intent. Reject duplicate intent, cannibalisation without a consolidation plan, angles that only differ by date or wording, and `no_defensible_content_gap` candidates that add no concrete information gain.

The scoring-stage observation is not the final writing benchmark. After a candidate passes the unchanged production scorer, apply `serp-benchmark.md` to the exact selected query, market, language and device. The post-selection benchmark may return the candidate to scoring or require replacement, but it never edits the already computed score.

## Portfolio selection

Use these soft targets after every candidate independently passes:

- recovery: about 80% `CORE_MINDSPACE`, no more than 20% `QUALIFIED_ADJACENT`;
- stable: 60–80% core, no more than 40% adjacent;
- automatic exploration: zero.

Keep no more than three articles dominated by one entity, reject duplicate intent, preserve meaningful topic diversity, and keep automatic content out of `news` and `/news/`. `max_articles` is normally a ceiling. The named `vertu-10` profile is the explicit exception: it applies the two-phase current-interest then evergreen supply contract in `evergreen-quota-fallback.md` and replaces downstream blockers until ten articles pass, while this traffic gate remains unchanged. Only exhausted two-phase supply or a truthful hard blocker may return `DAILY_QUOTA_BLOCKED`; never manufacture eligibility or `NO_TOPIC` success.

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

A mature sample-gate-passing checkpoint must receive a concrete diagnosis. Use repeated recent 72-hour and 7-day signals as expiring provisional ordering evidence only after the governed twice-daily review check. Promote only qualifying 28-day cohorts or verified experiments to durable scoring priors.

Apply `performance-learning.md`: a durable cohort prior requires at least three mature D+28 articles across two publication runs, unless a controlled experiment has a verified outcome. One spike never becomes a durable prior.

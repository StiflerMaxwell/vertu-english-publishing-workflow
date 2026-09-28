# Realtime Trends Contract

Use this contract whenever the run discovers topics automatically or describes content as hot, trending, breaking, rising or current.

## Source hierarchy and fallback

1. Use the authorised Google Trends API Alpha when configured.
2. Otherwise fetch the official Google Trends Trending Now public RSS, CSV or reproducible UI export.
3. Do not stop at `SOURCE_UNAVAILABLE` for the API while an official public method is reachable.
4. Treat Google News and official primary sources as event confirmation, not as search-volume providers.
5. Treat GSC as VERTU audience evidence and Keyword Planner as durable demand evidence. Neither can create a real-time-hot label by itself.

Use the deterministic collector:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_google_trends_realtime.py \
  --run-id "$publication_run_id" \
  --output realtime-trends.json \
  --market-map-output trend-market-map.json \
  --hotness-gate-output hotness-gate.json \
  --markets US GB AU CA AE SA SG HK IN
```

Record method, geography, observation time, trend publication time, age, approximate traffic bucket, related news, and per-market failures. Never store credentials.

## Market contract

| Tier | Markets | Purpose |
|---|---|---|
| Core English | US, GB, AU, CA | English Search and Discover acquisition |
| Premium global mobility | AE, SA, SG, HK | High-value luxury, travel, privacy and ownership relevance |
| Scale reach | IN | Large existing VERTU Search and Discover reach, evaluated separately for qualified value |

Before topic selection, query finalised 28-day GSC by country and write `geo-audience-baseline.json`. Raw click scale does not automatically outrank commercial or audience fit.

## Trend classes

Every serious candidate must declare exactly one class.

### `REALTIME_HOT`

Require all of:

- an official Google Trends Trending Now/API record observed within 24 hours;
- an explicit target market;
- positive approximate traffic or API interest evidence;
- at least one related news item plus a current primary source before drafting;
- a VERTU-relevant reader consequence and a non-generic visual;
- no stale-event, traffic-only or outside-authority veto.

Only this class may be described as a real-time hot topic.

### `RISING_SEARCH`

Use when current-period interest is demonstrably above a prior period or normal baseline, but no qualifying Trending Now record exists. Preserve the compared periods and provider using `growth_pct`, `current_period_value` versus `previous_period_value`, `recent_month_searches` versus `average_monthly_searches`, or `current_interest` versus `baseline_interest`. Without one of these comparisons, veto `unverified_rising_search_label`. Do not call it a real-time hot topic.

### `EVERGREEN_SEARCH`

Use when GSC and/or Keyword Planner support durable demand without a current surge. It may be valuable Search content, but receipts and reports must say evergreen rather than hot.

## Deterministic scoring safeguards

- `REALTIME_HOT`: trend-velocity cap 100.
- `RISING_SEARCH`: trend-velocity cap 75.
- `EVERGREEN_SEARCH`: trend-velocity cap 45.
- `REALTIME_HOT` without verified official Google evidence receives `unverified_realtime_hot_label`.
- Missing or invalid trend class is a validation error.
- Search-first still requires two independent positive demand providers.
- Discover-first still requires current interest, historical audience support and a concrete visual story.

Use `scripts/vertu_content_traffic_gate.py --trend-mode realtime_hot` when the requested portfolio prioritises current traffic. This mode front-loads verified real-time and rising candidates but never lowers the score threshold or fills weak slots. Under `vertu-10`, insufficient bounded current-interest supply starts `EVERGREEN_FALLBACK`; absence of `REALTIME_HOT` evidence must not stop qualifying evergreen publication or cause evergreen content to be mislabelled as hot.

## Required artifacts and receipt

Write before candidate scoring:

- `geo-audience-baseline.json`;
- `realtime-trends.json`;
- `trend-market-map.json`;
- `hotness-gate.json`.

For each selected article, record trend class, markets, source method, observation time, age, approximate traffic, news confirmation and evidence reference. The completion receipt must report the counts of `REALTIME_HOT`, `RISING_SEARCH` and `EVERGREEN_SEARCH`. If real-time evidence is absent, explicitly state that the batch is not a hot-content portfolio.

The collector writes the deterministic `run_id` and a SHA-256 snapshot fingerprint into all three trend artifacts. Do not edit or regenerate one artifact independently. The scorer must receive `--realtime-trends realtime-trends.json --trend-market-map trend-market-map.json --hotness-gate hotness-gate.json` and reject any run-ID or fingerprint mismatch.

For `REALTIME_HOT`, also record the exact `trend_query`, the same snapshot fingerprint, official Google Trends source URL(s), current primary-source URL, HTTP 200 verification, publication time, relation type, relevance terms and observation time. The scorer reconciles every declared market plus age, traffic, news count and source URL to the authoritative snapshot, then re-fetches the official Trends feed and primary URL. The exact trend query must still be present in the official feed, and at least one substantive relevance term must appear in the reachable primary source. A hand-entered official-source flag, blank market, invalid publication date, empty news node, arbitrary Trends URL or syntactic-only primary-source URL is not evidence.

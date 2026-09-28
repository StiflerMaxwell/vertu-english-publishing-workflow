# YouTube Topic Signals

Contract: `youtube-topic-signals-v1`

## Purpose and position

YouTube is an upstream discovery source for audience language, creator breadth and fast-moving interest. Collect it before broad candidate scoring beside editorial and social intelligence.

It is not Google Search demand, official Google Trends, GSC, Keyword Planner, Discover delivery evidence or publication authority.

## Required source contract

Use either:

- the official YouTube Data API with its key resolved from `YOUTUBE_DATA_API_KEY` or macOS Keychain service `vertu-youtube-data-api`; or
- a reproducible normalised export that preserves query, market, video ID, channel ID, publication time, views and available engagement metrics.

Never store an API key, private account data or raw private response text in prompts, command arguments, source files, artifacts or Base. Environment resolution takes priority; Keychain is the local fallback. Receipts may record only `environment`, `macos_keychain` or `SOURCE_UNAVAILABLE`, never the credential value.

Run:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_youtube_topic_signals.py \
  --run-id <publication_run_id> \
  --input <normalised-youtube-export.json> \
  --output youtube-topic-signals.json
```

The first phase is `SHADOW_ONLY`. A valid artifact must state all of the following as false:

- `may_create_search_demand`
- `may_create_realtime_hot`
- `may_create_rising_search`
- `may_change_raw_score`
- `may_change_eligibility`
- `may_waive_veto`

## Signal semantics

- `YOUTUBE_BREAKOUT`: recent multi-video, multi-channel activity with material measured view velocity.
- `YOUTUBE_RISING`: smaller but still independently distributed recent activity.
- `NONE`: source available but the bounded thresholds did not pass.
- `SOURCE_UNAVAILABLE`: no valid in-window evidence.

These labels may expand candidate language and support a Discover current-interest narrative. They never satisfy a Search-first provider minimum and never change `REALTIME_HOT | RISING_SEARCH | EVERGREEN_SEARCH`.

## Candidate mapping

Map a signal only before scoring and only when the exact query/topic boundary is explicit. Preserve:

- query and market;
- observation window;
- video and independent-channel counts;
- total views, median and p75 views per hour;
- engagement ratio when available;
- source URLs and snapshot fingerprint.

Do not infer a mapping after seeing a candidate score. Do not add points in v3.18.0. Missing or weak YouTube evidence has zero penalty.

## Review and promotion

Only a governed experiment with mature Search/Discover outcomes may propose future source authority or score effects. Until such an experiment passes the normal Skill-evolution vector and approval gates, the collector remains discovery-only.

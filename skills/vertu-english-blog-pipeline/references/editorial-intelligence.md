# Editorial Intelligence Upstream Contract

Use this contract for every automatic or manually requested current-topic portfolio. It catches major launches and fast editorial breakouts before search-only tools fully reflect them.

## Mandatory same-day inputs

Before broad candidate creation, locate the latest successful outputs for the current local date from:

- Hermes `vertu-fetch-rss-daily`, normally around 03:00, covering Hacker News, AI News, Simon Willison, TechCrunch, The Verge and VentureBeat;
- Hermes `vertu-process-raw-content`, normally around 05:00, containing the editor-ranked most important, insightful and practical stories;
- the preceding Hermes X/social collection when referenced by the synthesis.

Prefer job names and successful run metadata over hard-coded output filenames. Record each run ID, source path, completion time and freshness. Expected same-day output older than 12 hours is stale unless the event is still inside the configured source window.

If a required upstream output is missing, empty or failed, write `EDITORIAL_INTELLIGENCE_UNAVAILABLE` with the reason. Do not invent an all-clear result.

## Role in traffic selection

These feeds are discovery and editorial-velocity providers. They do not provide Google search volume and cannot independently satisfy a Search-first two-provider rule or the `REALTIME_HOT` label.

They may establish `EDITORIAL_BREAKOUT` for a Discover-first candidate when all of the following hold:

1. a current primary source is reachable and supports the event;
2. at least two independent reputable publishers cover the same material event, or one reputable publisher is paired with a strong public community signal;
3. the event has a broad consumer, executive, privacy, ownership or technology consequence relevant to VERTU readers;
4. the article can add an original value object and a concrete feed-readable visual;
5. the live VERTU inventory does not already satisfy the same intent.

Strong community evidence normally means one of:

- Hacker News at least 300 points or at least 150 comments;
- Reddit at least 500 net votes with substantive discussion;
- a Techmeme-style multi-publisher cluster;
- equivalent measured cross-platform acceleration with recorded timestamps.

Thresholds are triage evidence, not guarantees. Preserve the measured values and observation time.

## Required artifacts

Write `editorial-intelligence.json` with upstream run metadata, selected feed items, publishers, URLs, timestamps and source states.

Write `source-velocity.json` for serious current candidates:

```json
{
  "candidate_id": "",
  "editorial_signal": "EDITORIAL_BREAKOUT | CURRENT_CONFIRMED | NONE",
  "primary_source": {"url": "", "verified_at": "", "status": "AVAILABLE"},
  "independent_coverage": [],
  "community_signals": [],
  "first_observed_at": "",
  "latest_observed_at": "",
  "broad_reader_consequence": "",
  "visual_subject": "",
  "inventory_overlap": "",
  "verdict": "PASS | HOLD | REJECT"
}
```

The Google trend class remains a separate field governed by `realtime-trends.md`. A candidate may be `EDITORIAL_BREAKOUT` while its Google trend class is `RISING_SEARCH` or `EVERGREEN_SEARCH`. Never translate editorial velocity into an official Google metric.

## Cluster packaging

For a material event, prefer a compact cluster over unrelated volume:

- one event/opportunity page owns what changed and why it matters;
- up to two support pages may own distinct comparison, cost, implementation, privacy or buyer-decision queries;
- every page declares its query boundary, canonical intent, outbound cluster link and intended publication order;
- no support page may merely repeat the event with a different headline;
- publish the event page first, then support pages after the canonical and internal-link target are live.

Reject the cluster when the support pages cannot stand alone as useful search answers.

# VERTU Content Performance Monitoring Contract

Updated: 2026-07-29 — daily pulse and 48-hour promotion cadence

## Objective

Turn each published VERTU Signals article into a measured content experiment:

```text
publish -> observe -> diagnose -> propose one controlled change -> approve -> verify -> feed learning into topic selection
```

The monitor optimises qualified organic traffic from Google Discover and Search. It does not treat raw pageviews as the sole success metric and does not automatically mutate Sanity.

## Scope and safety

- Scan only runs whose `handoff.json` state is `PUBLISHED`.
- Include only canonical non-News VERTU Signals URLs.
- Read GSC Discover, GSC Search, GA4 and live page health; never expose credentials.
- Treat GA4 data as preliminary inside 48 hours and GSC data as immature until the latest available metric date covers the observation window.
- Never interpret unavailable or delayed data as zero performance.
- Never change a slug or canonical URL as a routine optimisation.
- Create a mutation preview and an article-specific approval request before any Sanity update.
- Change one major variable at a time unless correcting a factual or technical defect.
- Keep the previous title, description, hero, intro and Sanity `_rev` in the experiment ledger.

## GA4 measurement contract

- Read the GA4 Data API metadata timezone and record it with every metric snapshot. Build a separate half-open observation window for each article from its publication timestamp to the checkpoint; use `dateHourMinute` minute filters rather than one shared calendar-date range.
- Use `screenPageViews` grouped by `pagePath` for article views. Use `sessions`, `engagedSessions` and `engagementRate` grouped by `landingPage` for sessions that began on the article. Do not mix these scopes.
- Average engagement time is `userEngagementDuration / activeUsers` for the filtered window. `averageSessionDuration` is a different session metric and must never be labelled as average engagement time.
- If the property metadata rejects `returningUsers`, store a null with `NOT_DIRECTLY_AVAILABLE` status. Qualified journeys remain null until the qualifying event mapping is verified. Missing values are never zero.
- Record the query dimensions, metrics, minute window, source freshness and calculation method in the local timestamped supplement and the Feishu content-review row.

## Checkpoints

### Daily pulse: rolling cohort health

Run every day for every live non-News article published or materially republished in the preceding 35 days, even when no milestone checkpoint is due.

- Verify HTTP/canonical/indexability, hero delivery, visible authorship and schema for newly published articles and any page whose last pulse was not healthy.
- Read the latest finalised GSC Search and Discover state and the available GA4 state. Record source freshness and keep unavailable data null.
- Compare the latest completed metric date with the previous pulse and same-age cohort. Surface only new technical, delivery, demand, CTR, query-coverage or engagement anomalies.
- Write one immutable run-level `daily-pulse/YYYY-MM-DD.json` plus article pulse rows or supplements where state changed.
- Record `DAILY_HEALTHY`, `DAILY_WATCH`, `DATA_NOT_MATURE` or `SOURCE_BLOCKED`; a healthy pulse is still a completed audited run.
- Do not create a Sanity mutation from the daily pulse. Material editorial proposals still require milestone evidence, the sample gate and the existing approval path.

### T+24h: delivery and early engagement

Verify HTTP 200, canonical, indexability, hero delivery, image dimensions, `max-image-preview:large`, visible byline, `BlogPosting.author`, and structured data. Read preliminary GA4 page views, sessions, engaged sessions, engagement rate and average engagement time.

Allowed diagnosis: `TECHNICAL_BLOCKER`, `DELIVERY_OK`, or `EARLY_ENGAGEMENT_WATCH`.

Do not make an editorial performance judgement from GSC at this point. A technical blocker creates an urgent fix proposal; all other results wait for mature evidence.

### T+72h: initial Discover and Search signal

Run only when the latest GSC metric date covers the required dates. Read Discover and Search independently by canonical URL. Compare impressions, clicks and CTR with the same-age topic-cluster cohort and the article's pre-publication forecast.

Allowed diagnosis: `SEARCH_CTR_OPPORTUNITY`, `CONTENT_COVERAGE_OPPORTUNITY`, `DISCOVER_PACKAGING_OPPORTUNITY`, `SEARCH_INTENT_OPPORTUNITY`, `NO_MATURE_SIGNAL`, `PROMISING`, or `WINNER_WATCH`.

A mature checkpoint that passes either sample gate must receive a specific opportunity or positive-signal diagnosis. It must not remain generic `INSUFFICIENT_DATA`. Use the deterministic classifier in `scripts/vertu_content_traffic_gate.py` and record the benchmark source.

Do not change title or hero when impressions are below the adaptive sample gate. The default gate is the larger of 300 Discover impressions and the cluster's same-age lower quartile; for Search use the larger of 100 impressions and the cluster lower quartile.

### D+7: first optimisation decision

Read Discover clicks, impressions and CTR; Search clicks, impressions, CTR, queries and position; GA4 engagement; and qualified product or concierge journeys where measurement exists.

Choose at most one primary action:

| Evidence pattern | Primary action |
|---|---|
| Healthy impressions, CTR materially below same-age cluster median | Propose a title or hero test, not both |
| Search position 1-10 with weak query CTR | Propose title/meta alignment |
| Search impressions exist but position/content coverage is weak | Propose section expansion or internal links |
| CTR is healthy but engagement is below cohort lower quartile | Propose intro, structure or promise-matching revision |
| Engagement is strong but impressions are weak | Hold or improve distribution/internal links; do not rewrite blindly |
| Top-quartile CTR and engagement | Preserve the page and extract a topic/format learning |

### D+28: mature review and portfolio learning

Classify each article as `WINNER`, `PROMISING`, `SEARCH_BUILDER`, `UNDERPERFORMER`, `INSUFFICIENT_DATA`, or `TECHNICAL_FAILURE`. Compare against the prior 28-day topic-cluster median and the same publication cohort. Check query cannibalisation, returning users, assisted product/concierge journeys and any approved experiment outcome.

Feed validated learnings into the next `discover-baseline.json`, but never clone a successful article or turn one spike into a permanent rule.

## Learning and skill-evolution handoff

The daily monitor produces daily pulses and checkpoint evidence; it does not directly rewrite the publishing skill. A separate learning and Skill release run executes twice daily and applies the canonical durable `performance-learning-v1` plus provisional `performance-learning-provisional-v1` contracts. The faster cadence surfaces observations sooner but does not reduce evidence maturity:

- one mature T+72h result remains an `OBSERVATION`;
- repeated recent T+72h or D+7 patterns may become expiring `CANDIDATE_PRIOR` ordering evidence;
- only repeated mature D+28 outcomes across at least three articles and two publication runs, or one verified controlled experiment, can become `DURABLE_PRIOR`;
- planned checkpoint files, missing execution timestamps, `DATA_NOT_MATURE`, `SOURCE_BLOCKED` and null future metrics are rejected inputs;
- provisional and durable priors can change only portfolio ordering after normal candidate eligibility, with one combined `-3..+3` cap;
- priors cannot change raw scores, bypass vetoes, create demand evidence or create a hot label.

Write immutable 48-hour snapshots under `output/vertu-signals/learning/YYYY-MM-DD/<execution-id>/`. Maintain durable state at `output/vertu-signals/learning/active-performance-priors.json` and provisional state at `output/vertu-signals/learning/provisional-performance-priors.json`. Record every proposal, activation, expiry, rejection and rollback in canonical Base `Skill Change Log`.

Twice daily, validate the preceding 35-day daily-pulse window and the 90-day mature-evidence comparison window, replay proposed changes against historical candidates, run tests, expire stale or reversed priors and execute the Skill release gate. This increases observation speed only; it does not reduce the mature evidence required for promotion. Version only material, tested changes; otherwise record `NO_PROMOTION` and `NO_SKILL_CHANGE` and preserve the current version. Structural changes to weights, thresholds, vetoes, source authority, publication authority or QA boundaries require explicit approval.

Maintain a read-only current-state projection over immutable checkpoint rows.
The logical key is `Article Key + checkpoint` plus exact Source Rev when that
field is available. Update only lifecycle metadata and the replacement pointer;
never rewrite clicks, impressions, CTR, GA4 metrics, diagnoses or source state.

## Diagnosis rules

- Use relative cohort and topic-cluster baselines before absolute thresholds.
- Require a mature metric date and a minimum sample before judging CTR.
- Separate Discover from Search because they have different timing and intent.
- Compare articles at the same age after publication.
- Label confidence as `LOW`, `MEDIUM`, or `HIGH`.
- A recommendation must cite the exact evidence, expected effect, risk, and verification window.
- Wait at least seven days between non-critical major edits to the same article.

## Artifacts

For each article, write:

```text
performance/<slug>/24h.json
performance/<slug>/72h.json
performance/<slug>/7d.json
performance/<slug>/28d.json
performance/<slug>/diagnosis.json
performance/<slug>/change-proposal.md
performance/<slug>/experiment-ledger.json
daily-pulse/YYYY-MM-DD.json
```

The run root also receives `performance-summary.md` with winners, risks, due actions, data freshness and blocked sources. Historical checkpoint files are immutable; a retry writes a timestamped supplement instead of overwriting evidence.

## Feishu Base system of record

- Base: `VERTU 内容与 SEO 运营闭环`
- Base token: `${FEISHU_BASE_TOKEN}`
- URL: `${FEISHU_BASE_URL}`
- Local schema map: `${VERTU_PDCA_ROOT}/output/vertu-signals/performance-monitor-base.json`

The Base is the long-term system of record. Its tables are:

- `文章资产`: one mutable current-state row per canonical article, keyed by `Article Key`;
- `发布批次`: one immutable row per daily or repair publication run, linked to its articles;
- `QA Runs`: one immutable quality decision per exact document revision and skill version;
- `Findings 修改建议`: immutable QA findings and their repair lifecycle;
- `Skill Change Log`: writing and QA policy history;
- `内容复盘`: the collaboration view for checkpoint evidence and QA follow-up;
- `节点复盘`: exactly one immutable row per deterministic `复盘ID`;
- `修改实验`: one row per proposed change, carrying approval and verification lifecycle;
- `监控运行`: one immutable row per automation execution, including quiet runs and failures;
- `项目任务`, `证据与基线`, `项目发布与回读`, `规则与字典`: sitewide SEO diagnosis and release-governance tables.

The former QA and sitewide SEO Base applications are read-only archives after the 2026-07-16 cutover. All three content automations write only to this canonical Base.

Every monitor execution must create a `监控运行` row. Each due article creates exactly one `节点复盘` row for its deterministic `复盘ID`. Before creating it, perform an exact `复盘ID` lookup across the whole table:

- zero matches: create the checkpoint and immediately read it back;
- one match: do not create another row; verify all immutable evidence fields match and only reconcile missing `关联文章` linkage;
- more than one match: stop that checkpoint write, record `DUPLICATE_CHECKPOINT_BLOCKED`, and route the duplicate set to audited maintenance;
- a retry is a distinct checkpoint only when its `复盘ID` includes the retry timestamp or other deterministic retry identity.

The Base CLI `record-upsert` command does not upsert by business key, so a pre-write lookup is mandatory. `NO_DUE_CHECKPOINT`, `DATA_NOT_MATURE`, `SOURCE_BLOCKED` and `NO_ACTIONABLE_CHANGE` are still recorded. When an article is first discovered, create it in `文章资产`; otherwise update only its latest status fields after looking up the exact `Article Key`. A supported change proposal creates a `修改实验` row and links it to the article.

Never overwrite historical metric evidence or a monitor-run row. Use deterministic execution and checkpoint IDs plus exact pre-write lookups to prevent duplicates. A network retry must re-read by `复盘ID` before deciding whether another create is necessary; never retry a create blindly. If Base writing fails, preserve all local artifacts, record `FEISHU_BASE_WRITE_FAILED` locally, retry up to three times with bounded backoff, and notify after the third consecutive failure.

The earlier Feishu document `VERTU 内容发布表现监控台账` is retained only as an overview/archive pointer and is not the operational tracker.

## Notification policy

Notify Codex only when one of these is true:

- a technical release blocker is detected;
- a checkpoint produces a medium/high-confidence action;
- an approved experiment reaches its verification date;
- a data source has failed three consecutive runs;
- the D+28 portfolio review is complete.

Routine `DELIVERY_OK`, immature GSC data and `INSUFFICIENT_DATA` results remain quiet and are recorded locally.

## Production-change boundary

The monitor may automatically prepare a revised title, meta description, hero brief, intro patch, internal-link patch or freshness update. It may not apply those changes to Sanity until approval identifies the current canonical URL, document ID or run ID and the mutation preview has been checked against the latest `_rev`.

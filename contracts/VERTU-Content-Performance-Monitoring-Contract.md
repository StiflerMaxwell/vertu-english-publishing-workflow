# VERTU Content Performance Monitoring Contract

Updated: 2026-08-06 — three daily pulses, D2TR market context and 30-day trend retention

## Objective

Turn each published VERTU Signals article into a measured content experiment:

```text
publish -> observe -> diagnose -> propose one controlled change -> approve -> verify -> feed learning into topic selection
```

The monitor optimises qualified organic traffic from Google Discover and Search. It does not treat raw pageviews as the sole success metric and does not automatically mutate Sanity.

## Scope and safety

- Scan only runs whose `handoff.json` state is `PUBLISHED`.
- If a current run's handoff state is stale or missing, classify it `PUBLISHED_RECONCILED` only when the same run has timestamped published articles, `run-summary.json status=SUCCESS`, and all matching live-verification gates pass. Record the handoff drift for repair; this is evidence reconciliation, not publication authority.
- Discover the rolling cohort from current local run artifacts with `scripts/vertu_content_monitor_runtime.py`; never substitute a frozen inventory snapshot.
- Runs through 2026-07-11 with missing first-generation artifacts use `LEGACY_EVIDENCE_EXCEPTION`, remain visible in audit, and are excluded from checkpoint and learning eligibility unless exact evidence is repaired without invention.
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

### Eight-hour pulse: rolling cohort health and Discover-market context

Run at `00:00`, `08:00` and `16:00` Asia/Hong_Kong for every live non-News article published or materially republished in the preceding 35 days, even when no milestone checkpoint is due.

Every invocation executes a bounded, checkpoint-balanced queue of due milestones. Reporting `due_now` without either executing the bounded queue or recording the exact source/identity blocker is not a completed monitoring run.

- Verify HTTP/canonical/indexability, hero delivery, visible authorship and schema for newly published articles and any page whose last pulse was not healthy.
- Read the latest finalised GSC Search and Discover state and the available GA4 state. Record source freshness and keep unavailable data null.
- Compare the latest completed metric date with the previous pulse and same-age cohort. Surface only new technical, delivery, demand, CTR, query-coverage or engagement anomalies.
- Write one immutable run-level `daily-pulse/YYYY-MM-DD/<execution-id>.json` per morning/evening invocation plus article pulse rows or supplements where state changed; never overwrite the first pulse with the second.
- Record `DAILY_HEALTHY`, `DAILY_WATCH`, `DATA_NOT_MATURE` or `SOURCE_BLOCKED`; a healthy pulse is still a completed audited run.
- Do not create a Sanity mutation from the daily pulse. Material editorial proposals still require milestone evidence, the sample gate and the existing approval path.

At every pulse, collect D2TR's five public Discover context endpoints for the configured markets. Write immutable local `d2tr-snapshot.json` and `d2tr-market-context.json` artifacts and one Base summary row per market/endpoint. D2TR is an independent source: it cannot replace GSC, official Google Trends or Keyword Planner, and cannot create Search demand, `RISING_SEARCH` or `REALTIME_HOT`. It may only reorder normally eligible candidates within the producer's governed cap.

Retain dedicated D2TR snapshot evidence for 30 rolling days. Cleanup may delete only expired rows from `Discover 趋势快照` and expired date directories under `output/vertu-signals/trend-monitor/`. It must preserve automation-ledger rows, monitor-run receipts, aggregate run summaries and all article performance checkpoints. Every cleanup writes a local receipt with the cutoff, exact deleted record IDs and removed paths.

### T+24h: delivery and early engagement

Verify HTTP 200, canonical, indexability, hero delivery, image dimensions, `max-image-preview:large`, visible byline, `BlogPosting.author`, and structured data. Read preliminary GA4 page views, sessions, engaged sessions, engagement rate and average engagement time.

Allowed diagnosis: `TECHNICAL_BLOCKER`, `DELIVERY_OK`, or `EARLY_ENGAGEMENT_WATCH`.

Do not make an editorial performance judgement from GSC at this point. A technical blocker creates an urgent fix proposal; all other results wait for mature evidence.

Record live crawl, robots, noindex and canonical proxies for the future LLM panel when available. These are technical proxies only and do not prove model indexation.

### T+72h: initial Discover and Search signal

Run only when the latest GSC metric date covers the required dates. Read Discover and Search independently by canonical URL. Compare impressions, clicks and CTR with the same-age topic-cluster cohort and the article's pre-publication forecast.

Allowed diagnosis: `SEARCH_CTR_OPPORTUNITY`, `CONTENT_COVERAGE_OPPORTUNITY`, `DISCOVER_PACKAGING_OPPORTUNITY`, `SEARCH_INTENT_OPPORTUNITY`, `NO_MATURE_SIGNAL`, `PROMISING`, or `WINNER_WATCH`.

A mature checkpoint that passes either sample gate must receive a specific opportunity or positive-signal diagnosis. It must not remain generic `INSUFFICIENT_DATA`. Use the deterministic classifier in `scripts/vertu_content_traffic_gate.py` and record the benchmark source.

Do not change title or hero when impressions are below the adaptive sample gate. The default gate is the larger of 300 Discover impressions and the cluster's same-age lower quartile; for Search use the larger of 100 impressions and the cluster lower quartile.

Run the first standard `llm-visibility-diagnosis-v1` panel through the dedicated read-only `vertu-llm` stage when a validated panel source is available. Preserve provider, model/version, prompt ID, market and observation time. One missing citation is not an indexation verdict.

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

Repeat the same LLM prompt/model panel for comparable citation and brand-mention observations. Prompt or model-version drift invalidates direct before/after comparison and must remain explicit.

### D+28: mature review and portfolio learning

Classify each article as `WINNER`, `PROMISING`, `SEARCH_BUILDER`, `UNDERPERFORMER`, `INSUFFICIENT_DATA`, or `TECHNICAL_FAILURE`. Compare against the prior 28-day topic-cluster median and the same publication cohort. Check query cannibalisation, returning users, assisted product/concierge journeys and any approved experiment outcome.

Feed validated learnings into the next `discover-baseline.json`, but never clone a successful article or turn one spike into a permanent rule.

Compare the mature LLM panel with T+72h and D+7. Repeated stable evidence may propose a GEO experiment, but it cannot directly activate a prior, repair, Sanity mutation or Skill change.

## Learning and skill-evolution handoff

The monitor produces three daily pulses plus checkpoint evidence; it does not directly rewrite the publishing skill. A separate learning and Skill release run executes twice daily and applies the canonical durable `performance-learning-v1` plus provisional `performance-learning-provisional-v1` contracts. Same-day acceleration may become an observation or manual experiment candidate but not a durable prior:

- one mature T+72h result remains an `OBSERVATION`;
- repeated recent T+72h or D+7 patterns may become expiring `CANDIDATE_PRIOR` ordering evidence;
- only repeated mature D+28 outcomes across at least three articles and two publication runs, or one verified controlled experiment, can become `DURABLE_PRIOR`;
- planned checkpoint files, missing execution timestamps, `DATA_NOT_MATURE`, `SOURCE_BLOCKED` and null future metrics are rejected inputs;
- provisional and durable priors can change only portfolio ordering after normal candidate eligibility, with one combined `-3..+3` cap;
- priors cannot change raw scores, bypass vetoes, create demand evidence or create a hot label.

Write immutable twice-daily snapshots under `output/vertu-signals/learning/YYYY-MM-DD/<execution-id>/`. Maintain durable state at `output/vertu-signals/learning/active-performance-priors.json` and provisional state at `output/vertu-signals/learning/provisional-performance-priors.json`. Record every proposal, activation, expiry, rejection and rollback in canonical Base `Skill Change Log`.

When a run proposes a material Skill or governing-process change, also generate `skill-scorecard-input.json` and deterministic `skill-scorecard.json`. Keep structural diagnostics, paired before/after comparison and mature production outcomes separate. A high absolute score never authorises keep, promotion or production action; replay regressions force revert, and traffic-affecting promotion requires mature D+28 or verified-experiment evidence plus the existing manual activation boundary.

Twice daily, validate the preceding 35-day pulse window and the 90-day mature-evidence comparison window, replay material proposed changes against historical candidates, run tests, expire stale or reversed priors and execute the Skill release gate. Version only material, tested changes; otherwise record `NO_PROMOTION` and `NO_SKILL_CHANGE` and preserve the current version. Structural changes to weights, thresholds, vetoes, source authority, publication authority or QA boundaries require explicit approval.

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
performance/<slug>/llm/72h/crawl-access.json
performance/<slug>/llm/72h/llm-citation-observations.json
performance/<slug>/llm/72h/llm-visibility-diagnosis.json
performance/<slug>/llm/7d/llm-visibility-diagnosis.json
performance/<slug>/llm/28d/llm-visibility-diagnosis.json
daily-pulse/YYYY-MM-DD/<execution-id>.json
trend-monitor/YYYY-MM-DD/<execution-id>/d2tr-snapshot.json
trend-monitor/YYYY-MM-DD/<execution-id>/d2tr-market-context.json
trend-monitor/YYYY-MM-DD/<execution-id>/base-handoff.json
trend-monitor/YYYY-MM-DD/<execution-id>/retention-cleanup.json
trend-monitor/latest-d2tr-market-context.json
```

The run root also receives `performance-summary.md` with winners, risks, due actions, data freshness and blocked sources. Historical checkpoint files are immutable; a retry writes a timestamped supplement instead of overwriting evidence.

Every new checkpoint carries the canonical learning context: `publication_run_id`, `article_key`, cluster, intent, outcome lane, trend class, section and portfolio bucket. Missing historical context may remain an observation but cannot generate broad section, trend or portfolio priors. A mandatory GA4 or GSC query failure is `SOURCE_BLOCKED` and retryable; only mature source-complete evidence may enter learning.

The local GA4 client defaults to the official REST transport (`VERTU_GA4_TRANSPORT=rest`) because the production workstation's HTTPS proxy path does not reliably carry gRPC. A caller may explicitly select a supported transport, but an unsupported value is a hard configuration error. Transport choice does not change the read-only metric contract or observation windows.

## Feishu Base system of record

- Base: `VERTU 内容与 SEO 运营闭环`
- Base token: `${FEISHU_BASE_TOKEN}`
- URL: `${FEISHU_RESOURCE_URL}`
- Local schema map: `${VERTU_PDCA_ROOT}/output/vertu-signals/performance-monitor-base.json`

The Base is the long-term system of record. Its tables are:

- `文章资产`: one mutable current-state row per canonical article, keyed by `Article Key`;
- `发布批次`: one immutable row per daily or repair publication run, linked to its articles;
- `QA Runs`: one immutable quality decision per exact handoff identity: QA Run ID, document/revision, policy hash/profile, producer bundle/version and release-gate role;
- `Findings 修改建议`: immutable QA findings and their repair lifecycle;
- `Skill Change Log`: writing and QA policy history;
- `内容复盘`: the collaboration view for checkpoint evidence, QA follow-up and stage-specific `LLM诊断` observations with panel identity, coverage and immutable fingerprint; raw private model responses are prohibited;
- `节点复盘`: exactly one immutable row per deterministic `复盘ID`;
- `修改实验`: one row per proposed change, carrying approval and verification lifecycle;
- `监控运行`: one immutable row per automation execution, including quiet runs and failures;
- `Discover 趋势快照`: one immutable summary row per D2TR execution, market and endpoint, retained for 30 rolling days;
- `项目任务`, `证据与基线`, `项目发布与回读`, `规则与字典`: sitewide SEO diagnosis and release-governance tables.

The former QA and sitewide SEO Base applications are read-only archives after the 2026-07-16 cutover. All three content automations write only to this canonical Base.

Every monitor execution must create a `监控运行` row. Each due article creates exactly one `节点复盘` row for its deterministic `复盘ID`. Before creating it, perform an exact `复盘ID` lookup across the whole table:

- zero matches: create the checkpoint and immediately read it back;
- one match: do not create another row; verify all immutable evidence fields match and only reconcile missing `关联文章` linkage;
- more than one match: stop that checkpoint write, record `DUPLICATE_CHECKPOINT_BLOCKED`, and route the duplicate set to audited maintenance;
- a retry is a distinct checkpoint only when its `复盘ID` includes the retry timestamp or other deterministic retry identity.

After every checkpoint write and exact readback, compute the current-state projection for the logical key `Article Key + 检查节点`, adding `Source Rev` when that live field exists. Exactly one source-complete row with the latest execution time becomes `证据有效性=CURRENT`; earlier source-complete rows become `SUPERSEDED` and point `取代复盘ID` to the current row. Rows that cannot satisfy the node maturity/source gate become `HISTORICAL` only when no eligible current row exists. Projection writes may change only `证据有效性` and `取代复盘ID`; every metric, diagnosis, timestamp and immutable `复盘ID` remains unchanged. A missing lifecycle field is `SCHEMA_BLOCKED`, never a guessed write or silent success.

The Base CLI `record-upsert` command does not upsert by business key, so a pre-write lookup is mandatory. `NO_DUE_CHECKPOINT`, `DATA_NOT_MATURE`, `SOURCE_BLOCKED` and `NO_ACTIONABLE_CHANGE` are still recorded. When an article is first discovered, create it in `文章资产`; otherwise update only its latest status fields after looking up the exact `Article Key`. A supported change proposal creates a `修改实验` row and links it to the article.

Never overwrite historical metric evidence or a monitor-run row. Use deterministic execution and checkpoint IDs plus exact pre-write lookups to prevent duplicates. A network retry must re-read by `复盘ID` before deciding whether another create is necessary; never retry a create blindly. If Base writing fails, preserve all local artifacts, record `FEISHU_BASE_WRITE_FAILED` locally, retry up to three times with bounded backoff, and notify after the third consecutive failure.

The Phase 1 handoff implementation is `scripts/vertu_content_monitor_base_handoff.py`. It always writes a local manifest first. Production `--apply` requires a same-execution canonical start-ledger receipt in `运行中`; a mismatched execution ID is a hard stop. It writes and reads back one monitor-run row and one deterministic checkpoint observation per local result. `SOURCE_BLOCKED` and `DATA_NOT_MATURE` observations may be recorded with null metrics for audit visibility. T+24h may be source-complete but remains a technical/preliminary observation; only source-complete mature 72h/7d/28d checkpoints are learning-eligible. Experiment activation remains manual and the handoff performs zero Sanity mutations.

Use `scripts/vertu_content_monitor_audit.py start` before metrics execution and `finish` only after the Base handoff decision. The start command reconciles exactly one `运行中` row by deterministic execution ID and writes a local receipt consumed by the handoff. The finish command updates that same row to one terminal state and reads it back; it never creates a second execution row on retry.

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

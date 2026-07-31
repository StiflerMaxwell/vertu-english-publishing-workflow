# Automation Contract — Traffic Acquisition v3.8.0

This contract makes the pipeline safe for Codex recurring automation and manual runs.

## Scheduled defaults

```yaml
mode: auto_discovery
source_window_hours: 72
max_articles: 10
minimum_articles: 0
candidate_target: 30
target_outcome: discover_and_search
trend_mode: balanced
trend_markets: [US, GB, AU, CA, AE, SA, SG, HK, IN]
delivery: local_draft
approval_required: true
production_publish: false
notification_target: codex
```

A scheduled run may discover, research, select, and write without routine questions. It may not publish to production without a separate article-specific approval event.

### Optional standing publication profile

A deployment may configure a named standing approval profile through
`VERTU_STANDING_APPROVAL_PROFILE`. The public template does not grant one and
remains draft-only by default. Any configured profile is a narrow exception to
the scheduled default above, not a general publication permission.

Required behaviour:

- scope authority to the new run created by the configured publishing automation; never reuse it for repairs, historical drafts, another automation or another section;
- publish only articles individually scoring at least 80 with QA `PASS`, `DISCOVER_READY`, image `PASS`, author preflight `PASS`, live link verification and no veto;
- require `editorial-intelligence.json`, `source-velocity.json` and `traffic-demand.json` with a computed v3.5 score, passing demand verdict, provider-level evidence and no validation error; a hand-authored final score is not publication evidence;
- require `geo-audience-baseline.json`, `realtime-trends.json`, `trend-market-map.json` and `hotness-gate.json` before scoring;
- require the current validated durable `performance-learning-v1` fingerprint and provisional `performance-learning-provisional-v1` fingerprint before scoring, or explicitly record `NO_DURABLE_LESSON`, `NO_PROVISIONAL_LESSON`, `LEARNING_PRIORS_UNAVAILABLE` or `PROVISIONAL_LEARNING_PRIORS_UNAVAILABLE`;
- classify every serious candidate as `PREMIUM_DECISION_CORE | ADJACENT | EXPLORATION_CANDIDATE`; only a controlled test that passes the normal demand gate becomes `EXPLORATION`. Record mass recognisability, concrete decision intent, historical cluster evidence and niche risk;
- treat the user-approved premium/business strategy as candidate-pool and portfolio guidance, never as a demand provider, raw-score change, trend label or veto waiver;
- pass active durable and unexpired provisional priors to the scorer only as post-eligibility portfolio ordering with one combined `-3..+3` cap; never let them change raw score, demand evidence, vetoes or trend labels;
- fetch official Trending Now RSS/CSV/UI evidence when API Alpha is unavailable; never skip all Google Trends collection merely because the API is not configured;
- prohibit the `REALTIME_HOT` label unless the v3.5.0 scorer receives all three same-run fingerprinted trend artifacts, reconciles the exact query, every non-blank market and all reported metrics to that snapshot, and confirms official market-level evidence plus a current verified primary source;
- require the latest same-day Hermes RSS and editorial-synthesis outputs before broad candidate creation; an `EDITORIAL_BREAKOUT` must reconcile to `source-velocity.json` and remains distinct from official Google demand evidence;
- allow fewer than ten articles and `NO_TOPIC`; never publish filler to satisfy volume;
- keep the permanent automatic `news` and `/news/` veto;
- query current Sanity schema, slug conflicts, authors and `_rev` values immediately before the mutation;
- use one idempotent run ID, record the approval profile, mutation preview and transaction ID, and never retry a production mutation blindly;
- after mutation, require HTTP 200, canonical, `og:image`, `max-image-preview:large`, exactly one template-rendered visible linked byline, no in-body `By ...` duplicate, matching `BlogPosting.author`, rendered-link reconciliation and non-News routing;
- if any publication or live verification check fails, stop, preserve evidence and send a blocker notification instead of a success receipt;
- after a fully verified publish, send the vvv group receipt defined in `contracts/VERTU-vvv-Group-Receipt-Template.md` through `scripts/vertu-vvv-notify.ts`, preserve its redacted receipt, and schedule 24h/72h/7d/28d monitoring;
- never use the former WeChat gateway, `WECHAT_*` configuration, nickname routing, group-name routing, or the deprecated WeChat receipt template for VERTU content automations;
- resolve the vvv App Secret only from `VERTU_VVV_APP_SECRET` or macOS Keychain service `vertu-vvv-user-robot`; never store it in prompts, source files, Feishu, run artifacts or logs;
- count group delivery as successful only when the normalized receipt says `SENT`. Preserve `DELIVERY_UNKNOWN` and never retry an ambiguous POST blindly.

## State machine

```text
DISCOVERING
→ SELECTED | NO_TOPIC
→ RESEARCHING
→ WRITING
→ READY_FOR_QA
→ QA_FIX | QA_BLOCKED | QA_PASS
→ DISCOVER_FIX | DISCOVER_REJECT | DISCOVER_READY
→ WAITING_FOR_IMAGE | READY_FOR_APPROVAL
→ SANITY_DRAFT
→ PUBLISHED
```

Write every transition to `handoff.json` with a timestamp.

## Handoff shape

```json
{
  "run_id": "",
  "idempotency_key": "",
  "state": "",
  "topic": "",
  "slug": "",
  "topic_score": 0,
  "draft_path": "",
  "evidence_status": "",
  "product_context_status": "",
  "qa_verdict": null,
  "discover_verdict": null,
  "image_status": "not_started",
  "delivery": "local_draft",
  "approval_required": true,
  "approval_reference": null,
  "last_error": null,
  "next_allowed_action": ""
}
```

## Retry and idempotency

- Reuse the same run directory and key on retry.
- Do not duplicate a run already in `WRITING`, `READY_FOR_QA`, `READY_FOR_APPROVAL`, or `SANITY_DRAFT`.
- Network fetches may retry three times with bounded backoff.
- Never convert a source outage into invented facts.
- After three failures, record `BLOCKED_SOURCE`, preserve artifacts, and report the source.
- Never retry a production mutation blindly; query current state first.

## Approval boundary

These are not publication approval: QA `PASS`, enabled automation, existing Sanity draft, general workflow approval, or approval of another article.

Production approval must identify the current slug, document ID, or run ID. Store the reference in `handoff.json`.

## Sanity delivery

Before mutation:

1. introspect current schema and a representative document;
2. identify body, SEO, image, language, author, section, status, and draft fields;
3. query for the same slug;
4. capture `_id` and `_rev` when updating;
5. build a mutation preview;
6. confirm delivery authority;
7. execute once;
8. query the result and store verification.

Select authors from `author-policy.md` by dominant expertise before drafting. Publishing scripts must reference the approved author ID and must not create, patch, or infer author documents. The route template owns the visible byline; publishing scripts must not inject `ll-author-byline` or any leading `By ...` paragraph into `rawHtml` or Portable Text. Before delivery, require the selected author profile to return HTTP 200 and verify exactly one linked template byline plus `BlogPosting.author.name` and `BlogPosting.author.url`. A route without a linked template byline is `AUTHOR_BLOCKED`.

The production dataset name does not mean a document is published. Use the current draft convention, never historical assumptions.

## Image behaviour

- One hero image only after QA `PASS`.
- Use Codex `image_gen`.
- Base the brief on the final thesis.
- If unavailable, stop at `WAITING_FOR_IMAGE`.
- Attach only after introspecting the current Sanity image field.
- Reject generic abstract heroes even when technically valid.
- Verify at least 1200 px width, more than 300,000 pixels, landscape crop, descriptive alt, relevant `og:image`, and `max-image-preview:large`.

## Batch quality and portfolio rules

- Build `discover-baseline.json` from finalised 365-day GSC data when available.
- Build candidate-level traffic demand evidence using `traffic-demand-gate.md`; record unavailable sources instead of fake zeros.
- Build market-level realtime evidence using `realtime-trends.md`; receipts must separate real-time, rising and evergreen article counts.
- Score at least 30 candidates for a ten-article run.
- `max_articles: 10` is a ceiling, not a quota.
- Use the traffic-weighted soft portfolio contract from `topic-selection.md`; legacy lanes never force filler.
- When enough candidates independently pass, prefer 50–70% premium/business/collector decision-core topics across at least three distinct clusters, 20–30% adjacent topics and no more than 20% exploration.
- No more than three adjacent intents or three articles dominated by one entity.
- Every selected article must independently pass QA and `DISCOVER_READY`.
- Use at least three relevant author desks in a ten-article portfolio when the selected topics genuinely span their scopes; expertise fit overrides distribution.
- If only six articles pass, deliver six and report four `NO_TOPIC` slots.
- Never use volume to compensate for weak evidence, thin content, generic imagery, or low audience fit.

## Suggested Codex automation prompt

```text
Run the project skill vertu-english-blog-pipeline in Discover-first auto_discovery mode.
Read finalised 365-day Google Discover and Search performance before topic selection.
Before candidate creation, query finalised GSC by country and fetch official Google Trends Trending Now evidence for US, GB, AU, CA, AE, SA, SG, HK and IN. Use the public official fallback when API Alpha is unavailable.
For every serious candidate, preserve provider-level GSC, Trends/current-interest, Keyword Planner when authorised, SERP, inventory and cluster-support evidence with source status and fetch time. Label it REALTIME_HOT, RISING_SEARCH or EVERGREEN_SEARCH and never call the latter two real-time hot.
Use a 72-hour current-source window plus durable evergreen demand, score at least 30 candidates, and select up to 10 topics scoring at least 80/100.
Consume the same-day Hermes RSS and editorial synthesis before broad candidate creation, and preserve editorial-intelligence.json plus source-velocity.json.
Calculate scores with the deterministic traffic gate; pass the editorial artifacts for breakout candidates plus durable and unexpired provisional learning priors when valid, reject hand-authored final scores and require the outcome lane's minimum independent demand signals.
Use traffic-weighted soft portfolio targets, preserve diversity, and reject abstract B2B, duplicate-intent, thin-update, and generic-visual topics.
Classify every serious candidate as PREMIUM_DECISION_CORE, ADJACENT or EXPLORATION_CANDIDATE; promote the last lane to EXPLORATION only after normal eligibility. Prefer mass-recognisable premium travel, executive technology/privacy, watches/collecting and familiar luxury-purchase decisions only when they also pass the normal demand gate. Reject premium-label-only, niche-affluence-without-demand and no-defensible-content-gap topics.
Fetch the current Feishu VERTU product knowledge base when a product or service is relevant.
Produce substantial content at the depth required by its type, with at least one article-specific value object and reader-visible evidence.
Count unique link destinations rather than anchor tags, preserve authoritative PDF evidence, reconcile the final body against the evidence pack and link plan, and verify approved links in the rendered canonical HTML after any authorised delivery.
Run independent editorial QA and the separate Discover readiness gate.
After both pass, create a concrete, non-generic, Discover-compliant 16:9 image brief and image.
Verify visible authorship, BlogPosting.author, og:image, max-image-preview:large, and canonical URL before delivery.
Produce the complete local draft artifact package under output/vertu-signals and a 24h/72h/7d/28d performance plan.
Do not mutate Sanity production and do not publish.
Finish with run state, paths, portfolio, scores, QA verdicts, Discover verdicts, blockers, and next allowed action.
```

Set cadence, start time, project, notification target, and whether `sanity_draft` is allowed when the actual automation is created.

## Monitoring

Report duration by stage, source failures, candidate counts, audience-fit distribution, premium-label/niche-demand vetoes, product-KB revision, QA outcome, image outcome, delivery outcome, unique internal/external destination counts, broken-link count, and rendered-link reconciliation. `NO_TOPIC` is a valid editorial result, not a system failure.

For published content, use one daily monitor that scans the rolling 35-day `PUBLISHED` cohort on every invocation. Always write a daily pulse, then execute any due milestone checkpoints. Schedule read-only measurements at daily, 24 hours, 72 hours, 7 days, and 28 days:

- `daily`: current live-page health, latest finalised GSC state, available GA4 state, newly emerging query/CTR/coverage anomalies, and milestone due-status for every article in scope;
- `24h`: technical delivery and preliminary GA4 only;
- `72h`: initial GSC Discover/Search after the metric-date maturity gate;
- `7d`: one evidence-backed optimisation proposal at most;
- `28d`: mature classification, cannibalisation, experiment verification, and portfolio learning.

Use `${VERTU_PDCA_ROOT}/docs/03-运行/VERTU-Content-Performance-Monitoring-Contract.md` when available. Missing or delayed data is `DATA_NOT_MATURE`, never zero. The monitor may create a mutation preview but may not mutate Sanity without article-specific approval and a fresh `_rev`. Feed mature results into future baselines without overwriting historical runs.

A mature 72-hour page that passes the Search or Discover sample gate must receive a concrete CTR, coverage, packaging, intent, promising, or winner-watch diagnosis. It must not remain generic `INSUFFICIENT_DATA`. Generate at most one major-variable proposal at 7 days and promote only verified 28-day experiment outcomes to durable topic priors.

Run a separate learning and Skill release automation at least once every 48 hours after the daily monitor. It reads daily pulses plus the full executed checkpoint history, writes immutable `learning-snapshot.json`, rejects placeholders/immature/blocked inputs, records proposals and expiries in `Skill Change Log`, writes `provisional-performance-priors.json` from recent repeated 72h/7d evidence, and updates `active-performance-priors.json` only for replay-validated durable priors. Apply only material, tested non-structural changes automatically, keep structural changes approval-gated, and record `NO_PROMOTION` and `NO_SKILL_CHANGE` without a version bump when nothing qualifies.

# Automation Contract — Traffic Acquisition v3.20.0

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

### Optional standing publication profile example: `vertu-10`

An operator may separately approve a narrowly scoped recurring publication profile.
This public document records its required gates, not an existing grant of authority.
Follow `docs/CURRENT-OPERATING-PROFILE.md` at the package root for the five-count
example; historical ten-count wording below has no independent quantity or
permission authority. Without deployment-specific approval, stay draft-only.

Required behaviour:

- before any protected local pointer, canonical Base, Sanity, or Skill release mutation, write a `vertu-content-loop-runtime-v1` manifest and acquire exact write scopes through `scripts/vertu_content_loop_runtime.py`; preserve the acquire/release receipts and keep the Base start ledger independently mandatory;
- configure positive runtime limits for wall-clock time, child tasks, candidates and attempts per scope; `PAUSED`, `COLLISION_BLOCKED`, `BUDGET_BLOCKED`, `ATTEMPT_LIMIT`, `STATE_INVALID` or `RELEASE_INCOMPLETE` is a blocker and may not be bypassed with a fresh execution ID;
- set `required_publish_count: 10`, `minimum_articles: 10`, `max_articles: 10`, `candidate_supply_phases: [HOT_PRIMARY, EVERGREEN_FALLBACK]`, per-phase cumulative targets `[30, 60, 90, 120]`, and `max_candidates: 240` for this named profile;
- scope authority to the new run created by `vertu-10`; never reuse it for repairs, historical drafts, another automation or another section;
- publish only articles individually scoring at least 80 with QA `PASS`, `DISCOVER_READY`, image `PASS`, author preflight `PASS`, live link verification and no veto;
- require `editorial-intelligence.json`, `source-velocity.json` and `traffic-demand.json` with `score_source=computed_v3_12_0`, passing demand verdict, provider-family qualification, raw source metrics and no validation error; a hand-authored final score is not publication evidence;
- require `geo-audience-baseline.json`, `realtime-trends.json`, `trend-market-map.json` and `hotness-gate.json` before scoring;
- require the current validated durable `performance-learning-v1` fingerprint and provisional `performance-learning-provisional-v1` fingerprint before scoring, or explicitly record `NO_DURABLE_LESSON`, `NO_PROVISIONAL_LESSON`, `LEARNING_PRIORS_UNAVAILABLE` or `PROVISIONAL_LEARNING_PRIORS_UNAVAILABLE`;
- run `brand-mindset-fit-v1` before traffic scoring and require `PASS` plus `CORE_MINDSPACE | QUALIFIED_ADJACENT`; preserve all three semantic dimensions, evidence, conflict vetoes and fingerprint. Automatic exploration is disabled and no score, trend, prior or quota may rescue a held/rejected row;
- treat the user-approved premium/business strategy as candidate-pool and portfolio guidance, never as a demand provider, raw-score change, trend label or veto waiver;
- read and validate `active-discover-recovery-profile.json` before broad candidate creation when present; an active `discover-recovery-editorial-strategy-v1` profile may shape candidate-pool composition only, must write its fingerprint and pool plan, expires after at most seven days without self-renewal, and has zero demand, score, trend-label, eligibility, veto, QA, publication or learned-prior authority;
- pass active durable and unexpired provisional priors to the scorer only as post-eligibility portfolio ordering with one combined `-3..+3` cap; never let them change raw score, demand evidence, vetoes or trend labels;
- fetch official Trending Now RSS/CSV/UI evidence when API Alpha is unavailable; never skip all Google Trends collection merely because the API is not configured;
- prohibit the `REALTIME_HOT` label unless the active scorer receives all three same-run fingerprinted trend artifacts, reconciles the exact query, every non-blank market and all reported metrics to that snapshot, and confirms official market-level evidence plus a current verified primary source;
- require the latest same-day Hermes RSS and editorial-synthesis outputs before broad candidate creation; an `EDITORIAL_BREAKOUT` must reconcile to `source-velocity.json` and remains distinct from official Google demand evidence;
- collect `youtube-topic-signals-v1` before scoring when a valid official/reproducible source exists; keep it shadow-only with zero demand, trend-label, score, eligibility, veto or ordering authority;
- after legacy production selection and before research/writing, require exact-query `serp-benchmark-v1` outputs and `BENCHMARK_PASS`; reframe returns to scoring and blocked/duplicate value requires replacement;
- require at least ten fully live-verified current-run articles; when the current-interest eligible pool is short, expand `HOT_PRIMARY` to 120, then start an independently fingerprinted `EVERGREEN_FALLBACK` pool and expand it through 30/60/90/120 with the unchanged traffic gate;
- replace an article blocked by drafting, QA, Discover, image, author, publication, live verification or canonical Base handoff with a distinct eligible candidate; never count the blocked article towards the quota;
- preserve all score, demand, forecast, evidence, diversity, duplicate-intent, non-News, QA, image, author, link, live and Base gates under quota pressure; never publish filler or relabel rejected evidence;
- after both 120-candidate phase boundaries are exhausted below ten, or a truthful hard source/runtime/publication blocker prevents safe continuation, return `DAILY_QUOTA_BLOCKED` with exact phase fingerprints and a source/manual/unexpected terminal mapping; reaching the hot boundary alone returns `SWITCH_TO_EVERGREEN`, and `NO_TOPIC` is not successful completion for `vertu-10`;
- require independent QA to run the active editorial-safeguards validator over every final article and the complete current batch; duplicate VERTU/Concierge integration or a template-dependent meaningful heading fingerprint is blocking, while `BODY_VISUAL_MISSING` remains warning-only in phase one;
- keep the permanent automatic `news` and `/news/` veto;
- query current Sanity schema, slug conflicts, authors and `_rev` values immediately before the mutation;
- use one idempotent run ID, record the approval profile, mutation preview and transaction ID, and never retry a production mutation blindly;
- after mutation, require HTTP 200, canonical, `og:image`, `max-image-preview:large`, exactly one template-rendered visible linked byline, no in-body `By ...` duplicate, matching `BlogPosting.author`, rendered-link reconciliation and non-News routing;
- if any publication or live verification check fails, stop, preserve evidence and send a blocker notification instead of a success receipt;
- after a fully verified publish, send the vvv group receipt defined in `docs/03-运行/VERTU-vvv-Group-Receipt-Template.md` through `scripts/vertu-vvv-notify.ts`, preserve its redacted receipt, and schedule 24h/72h/7d/28d monitoring;
- never use the former WeChat gateway, `WECHAT_*` configuration, nickname routing, group-name routing, or the deprecated WeChat receipt template for VERTU content automations;
- resolve the vvv App Secret only from `VERTU_VVV_APP_SECRET` or macOS Keychain service `vertu-vvv-user-robot`; never store it in prompts, source files, Feishu, run artifacts or logs;
- count group delivery as successful only when the normalized receipt says `SENT`. Preserve `DELIVERY_UNKNOWN` and never retry an ambiguous POST blindly.

## State machine

```text
DISCOVERING
→ BRAND_GATE_PASS | BRAND_GATE_HOLD | BRAND_GATE_REJECT | EXPAND_REQUIRED
→ SWITCH_TO_EVERGREEN | EVERGREEN_DISCOVERING | EXPAND_REQUIRED
→ SELECTED | DAILY_QUOTA_BLOCKED
→ SERP_BENCHMARK_PASS | SERP_REFRAME | SERP_REPLACE | SERP_SOURCE_BLOCKED
→ RESEARCHING
→ WRITING
→ READY_FOR_QA
→ QA_FIX | QA_BLOCKED | QA_PASS
→ DISCOVER_FIX | DISCOVER_REJECT | DISCOVER_READY
→ WAITING_FOR_IMAGE | READY_FOR_APPROVAL
→ SANITY_DRAFT
→ PUBLISHED | REPLACEMENT_REQUIRED
→ QUOTA_COMPLETE
```

Write every transition to `handoff.json` with a timestamp.

Read `${VERTU_PDCA_ROOT}/docs/03-运行/VERTU-QA-Handoff-Contract.md` before any QA or publication transition. New production runs use `qa-handoff-v1`; independent component version numbers do not need to match, but their compatibility matrix and exact identities must.

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
  "qa_handoff_contract_version": "qa-handoff-v1",
  "producer_skill": {
    "id": "vertu-english-blog-pipeline",
    "version": "3.20.0"
  },
  "brand_mindset_gate": {
    "contract_version": "brand-mindset-fit-v1",
    "verdict": "PASS",
    "brand_mindset_class": "CORE_MINDSPACE",
    "fingerprint": ""
  },
  "youtube_signal_fingerprint": null,
  "serp_benchmark_fingerprint": null,
  "draft_bundle_sha256": null,
  "qa_handoffs": {
    "preflight": null,
    "prepublish": null,
    "postpublish_audit": null
  },
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

- Reuse the same deterministic local loop execution ID and owned write scopes on retry. Do not invent a new execution to evade a collision, attempt ceiling or budget.
- Acquire exact mutation scopes before protected writes and release only scopes owned by the exact execution. `RELEASE_INCOMPLETE` is `HANDOFF_INCOMPLETE`.
- Reuse the same run directory and key on retry.
- Do not duplicate a run already in `WRITING`, `READY_FOR_QA`, `READY_FOR_APPROVAL`, or `SANITY_DRAFT`.
- Network fetches may retry three times with bounded backoff.
- Never convert a source outage into invented facts.
- After three failures, record `BLOCKED_SOURCE`, preserve artifacts, and report the source.
- Never retry a production mutation blindly; query current state first.

## Approval boundary

These are not publication approval: QA `PASS`, enabled automation, existing Sanity draft, general workflow approval, or approval of another article.

Production approval must identify the current slug, document ID, or run ID. Store the reference in `handoff.json`.

For a new automatic production run, approval never substitutes for compatible QA evidence. Require:

- R0 `preflight` PASS bound to the exact draft bundle;
- R1 `prepublish` PASS bound to the exact Sanity Draft revision;
- no critical veto or unresolved critical/required Finding;
- R2 `postpublish_audit` bound to the exact published revision before the full chain reports success.

Each handoff records its immutable QA Run ID, Base QA record ID, policy ID/version/hash/profile, result fingerprint and compatibility status. Never select a QA result merely because it is the latest PASS.

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
- Build explicit brand-mindset evidence with `brand-mindset-gate.md`, then candidate-level traffic demand evidence using `traffic-demand-gate.md`; record unavailable sources instead of fake zeros.
- Build raw direct-factor evidence with `scripts/vertu_content_factor_extractor.py` using `direct-factor-model.md`; require 32 explicit rows per candidate plus a fingerprinted `factor-extraction.json`, and preserve the shadow output and coverage without using it to change production decisions.
- Build market-level realtime evidence using `realtime-trends.md`; receipts must separate real-time, rising and evergreen article counts.
- For the named `vertu-10` profile, apply `daily-publishing-quota-v2`: score `HOT_PRIMARY` through 30/60/90/120, then independently generate and score `EVERGREEN_FALLBACK` through 30/60/90/120 until ten cumulative eligible directions exist or both bounded phases are exhausted.
- `required_publish_count: 10` is a hard completion condition for `vertu-10`; the current `max_articles: 10` makes the daily result exactly ten when successful.
- Use the traffic-weighted soft portfolio contract from `topic-selection.md`; gate classes never force filler.
- When enough candidates independently pass, prefer about 80% core in recovery mode or 60–80% core in stable mode; cap adjacent accordingly and allow no automatic exploration.
- No more than three adjacent intents or three articles dominated by one entity.
- Every selected article must independently pass QA and `DISCOVER_READY`.
- Use at least three relevant author desks in a ten-article portfolio when the selected topics genuinely span their scopes; expertise fit overrides distribution.
- If an article fails a downstream gate, retain the failure evidence and select a distinct eligible replacement. If no eligible replacement remains, expand the active phase or start evergreen fallback. Only exhausted two-phase supply or a truthful hard blocker may report `DAILY_QUOTA_BLOCKED`; do not claim partial success as quota completion.
- Never use volume to compensate for weak evidence, thin content, generic imagery, or low audience fit.

## Suggested Codex automation prompt

```text
Run the project skill vertu-english-blog-pipeline in Discover-first auto_discovery mode.
Before any protected mutation, read loop-runtime-governance.md, acquire exact write scopes with the deterministic loop runtime, enforce runtime/child-task/candidate/attempt limits, and preserve acquire/release receipts. A local ALLOW receipt does not replace the Base start ledger or any editorial/publication gate.
Read finalised 365-day Google Discover and Search performance before topic selection.
Before candidate creation, query finalised GSC by country and fetch official Google Trends Trending Now evidence for US, GB, AU, CA, AE, SA, SG, HK and IN. Use the public official fallback when API Alpha is unavailable.
Collect YouTube topic signals from the official API or a reproducible export when available. Keep them shadow-only: they may support discovery but may not create demand, hot/rising labels, score points, eligibility or veto relief.
For every serious candidate, preserve provider-level GSC, Trends/current-interest, Keyword Planner when authorised, SERP, inventory and cluster-support evidence with source status and fetch time. Label it REALTIME_HOT, RISING_SEARCH or EVERGREEN_SEARCH and never call the latter two real-time hot.
Use a 72-hour current-source window plus durable evergreen demand. For `vertu-10`, require at least 10 fully live-verified articles. Run `HOT_PRIMARY` through cumulative 30/60/90/120 current-interest candidates. If cumulative eligible supply remains below ten, start an independent `EVERGREEN_FALLBACK` pool from current GSC, Keyword Planner and live inventory evidence and expand it through 30/60/90/120. Use `daily-publishing-quota-v2`, independent pool fingerprints and a cumulative runtime candidate limit of 240. Select only topics scoring at least 80/100 with every normal gate intact, and replace any downstream blocker with a distinct eligible candidate.
Consume the same-day Hermes RSS and editorial synthesis before broad candidate creation, and preserve editorial-intelligence.json plus source-velocity.json.
Run the permanent brand-mindset gate before scoring and retain `brand-mindset-candidates.json` plus `brand-mindset-summary.json`. Pass only valid gate results to the central 32-factor extractor and retain `candidates-with-factors.json` plus `factor-extraction.json`. Then calculate scores with `--require-brand-mindset-gate`; pass the editorial artifacts for breakout candidates plus durable and unexpired provisional learning priors when valid, reject hand-authored final scores, qualify candidate GSC against the latest available finalised-window sample floor, deduplicate demand by acquisition-system family, and require the outcome lane's minimum independent demand signals. The 32-factor output remains shadow-only.
Use traffic-weighted soft portfolio targets, preserve diversity, and reject abstract B2B, duplicate-intent, thin-update, and generic-visual topics.
After the legacy scorer selects a topic, run the exact-query post-selection SERP benchmark before evidence-pack research or writing. Require BENCHMARK_PASS and a concrete differentiation brief; return reframed intent to scoring and replace blocked or non-original directions.
Classify every serious candidate as CORE_MINDSPACE or QUALIFIED_ADJACENT before scoring. Prefer mass-recognisable premium travel, executive technology/privacy, watches/collecting and familiar luxury-purchase decisions only when they also pass the normal demand gate. Reject commodity-lifestyle mismatch, forced brand association, price-only luxury, premium-label-only, niche-affluence-without-demand and no-defensible-content-gap topics.
Fetch the current Feishu VERTU product knowledge base when a product or service is relevant.
Produce substantial content at the depth required by its type, with at least one article-specific value object and reader-visible evidence.
Count unique link destinations rather than anchor tags, preserve authoritative PDF evidence, reconcile the final body against the evidence pack and link plan, and verify approved links in the rendered canonical HTML after any authorised delivery.
Run independent editorial QA, including duplicate VERTU/Concierge integration and batch heading-fingerprint safeguards, then the separate Discover readiness gate. Record long buyer/comparison drafts without a descriptive in-body evidence visual as a non-blocking first-phase warning.
After both pass, create a concrete, non-generic, Discover-compliant 16:9 image brief and image.
Verify visible authorship, BlogPosting.author, og:image, max-image-preview:large, and canonical URL before delivery.
Produce the complete local draft artifact package under output/vertu-signals and a 24h/72h/7d/28d performance plan.
After live publication and Base handoff, run the read-only LLM visibility panel at 72h/7d/28d when available. Preserve model, prompt, market and timestamp context; never infer non-indexation from one missing citation.
Do not mutate Sanity production and do not publish.
Finish with run state, paths, portfolio, scores, QA verdicts, Discover verdicts, blockers, and next allowed action.
```

Set cadence, start time, project, notification target, and whether `sanity_draft` is allowed when the actual automation is created.

## Monitoring

Report duration by stage, runtime acquire/release decisions, mutation scopes, budgets, attempts, source failures, candidate rounds, replacement reasons, eligible/selected/live counts, audience-fit distribution, premium-label/niche-demand vetoes, product-KB revision, QA outcome, image outcome, delivery outcome, unique internal/external destination counts, broken-link count, and rendered-link reconciliation. `NO_TOPIC` remains valid for profiles whose minimum is zero; it is not successful completion for `vertu-10`, where exhausted supply below ten is `DAILY_QUOTA_BLOCKED`.

For published content, use one daily monitor that scans the rolling 35-day `PUBLISHED` cohort on every invocation. Always write a daily pulse, then execute any due milestone checkpoints. Schedule read-only measurements at daily, 24 hours, 72 hours, 7 days, and 28 days:

- `daily`: current live-page health, latest finalised GSC state, available GA4 state, newly emerging query/CTR/coverage anomalies, and milestone due-status for every article in scope;
- `24h`: technical delivery and preliminary GA4 only;
- `72h`: initial GSC Discover/Search after the metric-date maturity gate;
- `7d`: one evidence-backed optimisation proposal at most;
- `28d`: mature classification, cannibalisation, experiment verification, and portfolio learning.

Use `${VERTU_PDCA_ROOT}/docs/03-运行/VERTU-Content-Performance-Monitoring-Contract.md` when available. Missing or delayed data is `DATA_NOT_MATURE`, never zero. The monitor may create a mutation preview but may not mutate Sanity without article-specific approval and a fresh `_rev`. Feed mature results into future baselines without overwriting historical runs.

A mature 72-hour page that passes the Search or Discover sample gate must receive a concrete CTR, coverage, packaging, intent, promising, or winner-watch diagnosis. It must not remain generic `INSUFFICIENT_DATA`. Generate at most one major-variable proposal at 7 days and promote only verified 28-day experiment outcomes to durable topic priors.

Run a separate learning and Skill release automation twice daily after the corresponding monitor pulse. First run the read-only loop audit and preserve `loop-health.json`; expired claims, orphan locks, malformed locks or running executions with missing claims remain a visible `DEGRADED` state. The learning job reads daily pulses plus the full executed checkpoint history, writes immutable `learning-snapshot.json`, rejects placeholders/immature/blocked inputs, records proposals and expiries in `Skill 学习与进化` (`CONFIGURE_TBL`, formerly `Skill Change Log`), writes `provisional-performance-priors.json` from recent repeated 72h/7d evidence, and updates `active-performance-priors.json` only for replay-validated durable priors. Same-day spikes are observations or manual experiment candidates, never durable priors. Every material Skill or governing-process proposal must produce a complete 60-row vector, an exact `skill-evolution-factor-evaluation-v1` artifact and a fingerprinted `skill-evolution-scorecard-v2`; only `PROMOTION_CANDIDATE` may enter the scorecard's structural, paired, replay and production gates. Apply only material, tested non-structural changes automatically, keep structural changes and low-risk experiments approval-gated, and record `NO_PROMOTION` and `NO_SKILL_CHANGE` without a version bump when nothing qualifies.

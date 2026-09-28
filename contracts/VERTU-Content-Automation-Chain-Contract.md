# VERTU Content Automation Chain Contract

Updated: 2026-08-24

## Objective

Turn the three recurring Codex automations into one auditable content lifecycle:

```text
vertu-10 daily publish
→ independent live-revision QA and queue routing
→ exception-only blocker resolution and standing-authority matching
→ vertu-2 repair, R2 QA, publish and live verification
→ vertu performance monitoring
→ daily performance pulse
→ governed learning and Skill release check twice daily
→ validated learning consumed by the next vertu-10 topic-selection run
```

The automations remain separate executors, but the single canonical Feishu Base `VERTU 内容与 SEO 运营闭环` (`${FEISHU_BASE_TOKEN}`) and immutable local artifacts are their shared state machine. A downstream automation must consume the upstream state instead of independently rediscovering or silently ignoring it.

## Single entry and mandatory audit trail

The canonical Base URL is the only operational entry point:

`${FEISHU_RESOURCE_URL}`

The former QA and sitewide SEO Bases are read-only archives. No automation may queue, repair, publish, reconcile or write new operational records there.

Every invocation of `vertu-10`, `vertu-2`, `vertu-3` (VERTU 阻塞分诊与自动授权), `vertu`, `vertu-llm` and `vertu-skill` must create or reconcile one run row in `自动化运行日志` (`CONFIGURE_TBL`) using deterministic `执行ID = automation_id + trigger_or_scheduled_time`. Before any queue or production mutation, the run row must exist with `执行状态=运行中`. At completion it must be updated to exactly one terminal state: `成功`, `部分成功`, `无可执行项`, `数据未成熟`, `来源阻塞`, `人工阻塞` or `失败`.

The run row records the automation, stage, trigger/start/end times, input summary, scanned/processed/success/blocked counts, material operations, upstream execution ID, downstream handoff state, local evidence path, external transaction IDs, receipt status, retry count and exact blocker when applicable. It must not contain credentials or private source text.

Every material decision and external mutation must also retain its domain evidence:

- `vertu-10`: `发布批次`, `文章资产`, exact-revision `QA Runs` and local publish/live-verification artifacts;
- `vertu-3`: exact-revision authorisation decisions, queue transitions, exception-only owner decisions and local resolver artifacts;
- `vertu-2`: intake `QA Runs`, `Findings 修改建议`, queue states, Draft/rollback/R2 evidence and a repair `发布批次` for every verified republish;
- `vertu`: `监控运行`, `节点复盘`, `内容复盘`, `修改实验` and local metric/query evidence.

Before a protected local pointer, canonical Base, Sanity or Skill-release mutation,
the executor must also acquire the exact write scopes through
`vertu-content-loop-runtime-v1`. `ALLOW` is only local collision/budget authority;
it never replaces the canonical Base start ledger or any traffic, QA, Discover,
publication or live-verification gate. `PAUSED`, `COLLISION_BLOCKED`,
`BUDGET_BLOCKED`, `ATTEMPT_LIMIT` and `STATE_INVALID` permit zero requested
production mutations. Every terminal run must write an owner-checked release receipt;
`RELEASE_INCOMPLETE` maps to `HANDOFF_INCOMPLETE`.

No-op outcomes are still auditable outcomes. `NO_TOPIC`, `NO_PUBLISHED_ARTICLE`, `NO_QUEUED_ITEMS` and `NO_DUE_CHECKPOINT` map to `无可执行项` except where a named automation profile has a stricter delivery contract. For `vertu-10` v3.20+, `HOT_PRIMARY` runs through bounded 30/60/90/120; if cumulative eligibility is below ten, an independently fingerprinted `EVERGREEN_FALLBACK` runs through its own 30/60/90/120. The two phases share a 240-candidate runtime ceiling and must either deliver ten fully gated articles or terminate truthfully after both phases or a hard blocker; quota pressure never lowers a gate. `DATA_NOT_MATURE` maps to `数据未成熟`; source failure maps to `来源阻塞`; manual approval/evidence boundaries map to `人工阻塞`. A missing run receipt, runtime release receipt or domain handoff is `HANDOFF_INCOMPLETE`, never silent success.

If the initial run-ledger write fails, retry at most three times with bounded backoff, write `BASE_AUDIT_WRITE_FAILED` locally and prohibit production publication or repair mutation for that invocation. Always emit a visible Codex receipt and preserve a local `run-summary.json`, including no-op and blocked runs.

## Automations and ownership

| Automation | Schedule | Produces | Consumes |
|---|---|---|---|
| `vertu-10` | Daily 09:00 Asia/Hong_Kong | Ten fully gated live-verified non-News posts; hot/rising supply first, independent evergreen fallback second; truthful blocker only after both phases or a hard source/runtime/publication failure, plus QA evidence, article assets, monitoring plan, loop receipts and vvv group receipt | Mature monitoring/experiment learnings, GSC baseline, live inventory, product KB |
| `vertu-llm` | Daily intake, due-driven at T+72h, D+7 and D+28 after live handoff | Read-only model/prompt/market citation observations, crawl proxies and LLM visibility diagnosis | Live canonical article identity and validated normalised model-panel observations |
| `vertu-2` | Daily 14:30 and 17:30 Asia/Hong_Kong | Independent live-revision QA, safe repair Drafts, R2 QA and verified republish evidence | New or changed published revisions plus QA Runs with an exact valid repair authorisation and `自动修复发布状态=待执行` |
| `vertu-3` | Daily 15:30 Asia/Hong_Kong | Deterministic blocker triage, Base-only governance cleanup, standing-authority queue decisions and owner exceptions | Current-policy exact-revision QA Runs and Findings not yet terminalised |
| `vertu` | Daily 19:00 Asia/Hong_Kong | Rolling 35-day daily pulse, 24h/72h/7d/28d checkpoints, diagnoses, controlled proposals, experiment verification, portfolio learning | Published and repaired revisions registered in `文章资产` and local `PUBLISHED` handoffs |
| `vertu-skill` | Daily at 10:30 and 21:30 Asia/Hong_Kong | Immutable learning snapshot, expiring provisional priors, durable promotion and Skill release gate, Skill Change Log proposals, replay evidence, rollback state, `NO_PROMOTION` or `NO_SKILL_CHANGE` | Daily pulses, executed mature checkpoints, verified experiments and prior Skill versions |

## Shared identity and idempotency

The normative production/QA envelope is `docs/03-运行/VERTU-QA-Handoff-Contract.md` (`qa-handoff-v1`). Producer and QA versions are independent but must be compatible under that contract.

Every article transition must carry these exact identifiers:

- `publication_run_id`: the upstream `vertu-10` or repair publication run ID;
- `article_key`: normalised canonical slug;
- `sanity_doc_id`;
- `source_rev`: the exact revision evaluated or published;
- `qa_run_id`: immutable QA review identity;
- `canonical_url`.
- `producer_skill_id + producer_skill_version`;
- `draft_bundle_sha256`;
- `serp_benchmark_fingerprint + original_value_delta` for producer 3.18.0+;
- `qa_policy_id + qa_policy_version + qa_policy_hash + evaluation_profile`;
- `qa_handoff_contract_version + release_gate_role + source_identity_type + qa_result_fingerprint`.

The revision identity is `sanity_doc_id + source_rev`; the QA identity is that revision plus policy hash/profile, and the release identity additionally binds the producer artifact bundle and immutable QA Run. Never reuse a QA or repair decision for a different revision, policy, artifact bundle or gate role. Retries must reuse their deterministic execution ID and must not duplicate a production mutation.

## Stage A: daily publication handoff

After each `vertu-10` article passes all publication and live-page gates:

1. Upsert one current-state row in canonical Base `文章资产` using `article_key` and create/link the immutable `发布批次` row.
2. Register exact T+24h, T+72h, D+7 and D+28 due times.
3. Persist or reconcile the independent QA result in the same canonical Base `QA Runs` table for the exact `qa-handoff-v1` identity, including QA Run ID, policy hash/profile, producer version, bundle fingerprint and `sanity_doc_id + source_rev` where present.
4. A publication PASS uses `Patch Action=no_patch_needed` and records that no repair queue is needed for that revision.
5. Preserve the local QA, Discover, image, author, link, mutation and live-verification artifacts.
6. Register due-driven T+72h, D+7 and D+28 LLM visibility observations; these are read-only and do not authorise repair, publication or learning promotion.
7. Emit a visible receipt even when fewer than ten articles publish.

All group receipts from `vertu-10`, `vertu-2`, `vertu`, `vertu-llm` and `vertu-skill` use the
vvv user-robot channel defined in
`docs/03-运行/VERTU-vvv-Group-Receipt-Template.md`. The legacy WeChat gateway,
`WECHAT_*` configuration and name-based group routing are prohibited for this
content chain. Codex remains a visible secondary receipt surface. Every vvv
attempt stores a redacted `vvv-notification.json`; only `status=SENT` counts as
successful group delivery, and `DELIVERY_UNKNOWN` must not be retried blindly.

Failure to complete either article/publication or QA handoff inside the canonical Base is `HANDOFF_INCOMPLETE`; publication success must not be reported as a fully completed chain.

## Stage B: QA intake and repair routing

`vertu-2` has two phases and must not start with only the repair queue. The
separate resolver between its afternoon executions is governed by
`docs/03-运行/VERTU-Repair-Autonomy-Contract.md`
(`repair-authorisation-v1`). It may classify and queue, but may never mutate
Sanity or publish.

### Phase 1: intake QA

1. Read authenticated, live, non-News Sanity revisions published or changed during the rolling seven-day window.
2. Reconcile them against canonical Base `QA Runs` by explicit `qa_run_id` when publication-bound, otherwise by `sanity_doc_id + source_rev + qa_policy_hash + evaluation_profile`; free-text Skill version is not an identity key.
3. Run independent QA for every missing current revision and write immutable QA Runs and Findings.
4. Route each result provisionally:
   - `PASS + no_patch_needed` → no repair; keep published and monitorable.
   - `FIX + low_risk_patch_allowed` with no restricted fields, no human-confirmation Finding and executable exact locators → `待执行` under standing chain approval `vertu-content-chain-user-2026-07-16`.
   - `FIX + manual_review_before_patch` → resolver intake with the missing decision/evidence stated.
   - `BLOCK + rewrite_required` → resolver intake; it may qualify only as a bounded, performance-protected non-restricted rewrite.
   - `BLOCK + blocked_no_patch` → `人工阻塞`.

The standing chain approval is deliberately narrow. It does not authorise restricted claims, product facts, prices, specifications, materials, privacy/security promises, medical claims, author/schema changes, slug/canonical changes or unsupported rewrites.

### Phase 1.5: blocker resolver

1. Reconcile duplicate/incomplete Base lineage without changing historical QA verdicts, Findings or Sanity.
2. Evaluate at most 200 non-terminal current-revision candidates per invocation with `scripts/vertu_repair_authorisation.py` and the exact QA Run, Source Rev, Finding set and profile `vertu-repair-autonomy-user-2026-08-13-v1`; persist a deterministic continuation cursor when backlog remains.
3. Automatically queue only exact reversible low-risk patches, removal or neutralisation of unsupported wording with no replacement fact, and bounded non-restricted rewrites whose performance guard passes.
4. Put only true exceptions into `负责人决策=待冉城菖决策`. The owner approves by setting that one field to `批准执行` or `批准中性重写`, or rejects/requests evidence with `拒绝执行` or `需要补证据`.
5. The resolver writes `待执行` only after exact Base readback of the decision ID, standing profile, Source Rev and queue status. It does not write a Sanity Draft and does not publish.
6. News routing, revision conflict, incompatible QA identity, missing locator, failed performance guard and unsupported destructive action remain non-executable regardless of quota pressure.

### Phase 2: repair executor

1. Consume at most ten `待执行` rows only when the exact resolver decision or legacy narrow standing-chain decision is present; lock each as `执行中` and re-fetch the live revision.
2. Stop on revision conflict or locator failure.
3. Repair the actual Sanity Draft and preserve a rollback snapshot.
4. Run independent R2 QA on the changed Draft and create a new linked QA Run.
5. Publish only after R2 `PASS`, exact revision checks and live-page verification.
6. Set the originating queue row to `已发布`, record before/after revisions and mark only verified Findings resolved.
7. Refresh the performance Base article revision and create experiment-verification due dates without overwriting the original publication checkpoints.

`NO_QUEUED_ITEMS` is valid only after both intake QA and queue routing have run. It means no safe authorised repair remains, not merely that nobody manually populated the queue.

## Stage C: performance monitoring and feedback

For the rolling 35-day cohort every day, and for every due original-publication or repair-experiment checkpoint:

1. Build the cohort dynamically from current local publication packages. Never import a frozen inventory. Prefer `handoff.state=PUBLISHED`; use `PUBLISHED_RECONCILED` only from same-run publish timestamp, successful run summary and exact live PASS evidence. Isolate incomplete runs through 2026-07-11 as `LEGACY_EVIDENCE_EXCEPTION`.
2. Write a daily pulse with current live health, latest finalised GSC, available GA4, source freshness and newly changed anomaly state.
3. Execute a bounded checkpoint-balanced queue and read exact-window GA4 plus mature GSC Discover/Search data for each due milestone. Merely listing due work is incomplete.
4. Build and apply the audited Base manifest with `scripts/vertu_content_monitor_base_handoff.py`. It requires the same execution's canonical start-ledger receipt, writes exactly one immutable `节点复盘` observation per deterministic `复盘ID`, reconciles current `文章资产` state and creates one `监控运行` record in the canonical Base. Search the whole table by exact `复盘ID` before every create; one existing match is a verified no-op/reconciliation, and multiple matches block the checkpoint write for audited maintenance. After write/readback, project rows sharing `Article Key + 检查节点` and, when present, `Source Rev` into `CURRENT | SUPERSEDED | HISTORICAL` using only the lifecycle fields `证据有效性` and `取代复盘ID`. Never overwrite historical metrics. Blocked and immature observations remain visible but are excluded from learning and cannot become `CURRENT`.
5. For an evidence-backed optimisation, write one `修改实验` proposal and link its article, checkpoint evidence, QA Run and current revision. Low-risk experiments remain `待审批`; this phase does not auto-approve them.
6. Monitoring never directly mutates Sanity. A low-risk proposal enters QA intake; restricted or major changes remain approval-blocked.
7. D+28 and verified experiment outcomes must be summarised as cluster learning that the next `vertu-10` run reads before candidate scoring.
8. For due T+72h, D+7 and D+28 articles, the dedicated `vertu-llm` stage records model, model version, prompt, market, observation time, citation and brand-mention states plus live crawl/canonical proxies. One missing citation never proves non-indexation. First-phase output is read-only and cannot mutate Sanity or create a prior.

Every monitoring execution emits a visible receipt containing scanned runs/articles, due/completed/blocked counts, GA4 and GSC freshness, Base rows written, next due time and artifact path. Quiet success may say `NO_ACTIONABLE_CHANGE`, but must not be visually empty.

## Stage D: governed learning and skill evolution

1. Scan checkpoint artifacts and keep only executed, completed and mature 72h/7d/28d evidence.
2. Deduplicate retries by article and checkpoint; reject planned placeholders, immature windows and source-blocked metrics explicitly.
3. Join each checkpoint to the canonical production context from selected candidate, cluster-support and published-run artifacts. Partial context may remain an observation but may not create broad priors.
4. Classify evidence as `OBSERVATION`, expiring `CANDIDATE_PRIOR` or `DURABLE_PRIOR` while preserving the raw diagnosis.
5. Twice daily, create or refresh a provisional prior only from recent repeated mature 72h/7d evidence; same-day spikes remain observations. Expire a prior after eight days unless a new governed run still supports it.
6. Require at least three mature D+28 articles across two publication runs, or one verified controlled experiment, before activating a durable prior.
7. Replay proposed priors against historical candidate portfolios. Reject changes that reduce traffic-gate compliance, diversity or holdout quality.
8. Apply provisional and durable priors only after eligibility with one combined `-3..+3` ordering adjustment.
9. Write immutable local evidence, one `自动化运行日志` row and one `Skill Change Log` row per proposal, activation, expiry, rejection or rollback.
10. For each material Skill/process proposal, write a fingerprinted three-layer `skill-scorecard.json`. Structural diagnostics are triage-only; paired review controls keep/revert; replay regressions force revert; traffic-affecting promotion waits for mature D+28 or verified-experiment outcomes and manual activation.
10. Twice daily, run tests, Skill validation and historical replay when a material proposal exists, then execute the versioned Skill release gate. Apply material replay-safe non-structural changes, record `NO_PROMOTION` and `NO_SKILL_CHANGE` when nothing qualifies, and keep structural rubric, authority or safety changes explicitly approval-gated.
11. The next `vertu-10` run records both learning fingerprints and matched prior IDs. Invalid, absent or expired evidence becomes an explicit unavailable/ignored state, never an inferred rule.

## Failure and recovery

- A failed downstream stage must retain the upstream identifiers and evidence.
- Feishu write failures retry at most three times with bounded backoff, then record `FEISHU_BASE_WRITE_FAILED` locally.
- Source outages use `SOURCE_BLOCKED`; immature GSC uses `DATA_NOT_MATURE`; neither becomes zero.
- A stale revision becomes `REVISION_CONFLICT` and is re-routed to fresh intake QA.
- Production mutations are never retried blindly.
- Historical QA Runs, Findings, checkpoints and experiment snapshots are immutable.

## Acceptance checks

1. A new `vertu-10` publication is visible in canonical Base `文章资产`, `发布批次` and `QA Runs` with the same document/revision identity.
2. `vertu-2` discovers missing current-revision QA before checking `待执行`.
3. Eligible low-risk, neutralisation-only and bounded protected rewrites enter `待执行` with an exact authorisation record; only true exceptions enter `负责人决策=待冉城菖决策`.
4. A successful repair creates R2 QA, verified publication evidence and new experiment-monitoring dates.
5. Monitoring writes concrete metrics or explicit maturity/source states and always emits a visible receipt.
6. The next daily topic-selection run reads mature cluster and experiment outcomes.
7. No automatic article is assigned to `news` or `/news/`.
8. Every automation invocation resolves to exactly one `自动化运行日志` row and one local run summary, including no-op and failure outcomes.
9. Every active learned prior is fingerprinted, replay-validated, bounded, reversible and recorded in `Skill Change Log`; review checks run twice daily while mature promotion thresholds remain unchanged.
10. Every new publication-authorising QA result is `COMPATIBLE` under `qa-handoff-v1`; monitoring never chooses an arbitrary latest PASS.
11. Producer 3.18.0+ publications have a `BENCHMARK_PASS` SERP fingerprint inside the exact QA bundle, and post-publication LLM diagnosis remains a separate read-only feedback identity.
11. Resolver decisions are deterministic under `repair-authorisation-v1`, never authorise Sanity directly and can be replayed from the exact QA Run, Source Rev, Finding set and approval profile.

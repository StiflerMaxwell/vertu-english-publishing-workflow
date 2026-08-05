# VERTU Content Automation Chain Contract

Updated: 2026-07-29

## Objective

Turn the three recurring Codex automations into one auditable content lifecycle:

```text
vertu-10 daily publish
→ independent live-revision QA and queue routing
→ vertu-2 repair, R2 QA, publish and live verification
→ vertu performance monitoring
→ daily performance pulse
→ governed learning and Skill release observation twice daily
→ validated learning consumed by the next vertu-10 topic-selection run
```

The automations remain separate executors, but one configured canonical Feishu
Base and immutable local artifacts are their shared state machine. Resolve the
Base through `FEISHU_BASE_TOKEN` and the deployment-specific schema map. A
downstream automation must consume the upstream state instead of independently
rediscovering or silently ignoring it.

## Single entry and mandatory audit trail

The Base identified by `FEISHU_BASE_TOKEN` and `FEISHU_BASE_URL` is the only
operational entry point.

The former QA and sitewide SEO Bases are read-only archives. No automation may queue, repair, publish, reconcile or write new operational records there.

Every invocation of `vertu-10`, `vertu-2`, `vertu` and `vertu-skill` must create
or reconcile one run row in the configured Automation Runs table using
deterministic `执行ID = automation_id + trigger_or_scheduled_time`. Before any
production mutation, the run row must exist with `执行状态=运行中`. At completion
it must be updated to exactly one terminal state: `成功`, `部分成功`, `无可执行项`,
`数据未成熟`, `来源阻塞`, `人工阻塞` or `失败`.

The run row records the automation, stage, trigger/start/end times, input summary, scanned/processed/success/blocked counts, material operations, upstream execution ID, downstream handoff state, local evidence path, external transaction IDs, receipt status, retry count and exact blocker when applicable. It must not contain credentials or private source text.

Every material decision and external mutation must also retain its domain evidence:

- `vertu-10`: `发布批次`, `文章资产`, exact-revision `QA Runs` and local publish/live-verification artifacts;
- `vertu-2`: intake `QA Runs`, `Findings 修改建议`, queue states, Draft/rollback/R2 evidence and a repair `发布批次` for every verified republish;
- `vertu`: `监控运行`, `节点复盘`, `内容复盘`, `修改实验` and local metric/query evidence.

No-op outcomes are still auditable outcomes. `NO_TOPIC`, `NO_PUBLISHED_ARTICLE`, `NO_QUEUED_ITEMS` and `NO_DUE_CHECKPOINT` map to `无可执行项`; `DATA_NOT_MATURE` maps to `数据未成熟`; source failure maps to `来源阻塞`; manual approval/evidence boundaries map to `人工阻塞`. A missing run receipt or missing domain handoff is `HANDOFF_INCOMPLETE`, never silent success.

If the initial run-ledger write fails, retry at most three times with bounded backoff, write `BASE_AUDIT_WRITE_FAILED` locally and prohibit production publication or repair mutation for that invocation. Always emit a visible Codex receipt and preserve a local `run-summary.json`, including no-op and blocked runs.

## Automations and ownership

| Automation | Schedule | Produces | Consumes |
|---|---|---|---|
| `vertu-10` | Daily 09:00 Asia/Hong_Kong | New live-verified non-News posts, QA evidence, article assets, monitoring plan, vvv group receipt | Mature monitoring/experiment learnings, GSC baseline, live inventory, product KB |
| `vertu-2` | Daily 14:30 Asia/Hong_Kong | Independent live-revision QA, Findings, queue classification, safe repair Drafts, R2 QA, verified republish evidence | New or changed published revisions plus QA Runs where `自动修复发布状态=待执行` |
| `vertu` | Daily 19:00 Asia/Hong_Kong | Rolling 35-day daily pulse, 24h/72h/7d/28d checkpoints, diagnoses, controlled proposals, experiment verification, portfolio learning | Published and repaired revisions registered in `文章资产` and local `PUBLISHED` handoffs |
| `vertu-skill` | Twice daily at 10:30 and 21:30 Asia/Hong_Kong | Immutable learning snapshot, expiring provisional priors, durable promotion and Skill release gate, Skill Change Log proposals, replay evidence, rollback state, `NO_PROMOTION` or `NO_SKILL_CHANGE` | Daily pulses, executed mature checkpoints, verified experiments and prior Skill versions |

## Shared identity and idempotency

Every article transition must carry these exact identifiers:

- `publication_run_id`: the upstream `vertu-10` or repair publication run ID;
- `article_key`: normalised canonical slug;
- `sanity_doc_id`;
- `source_rev`: the exact revision evaluated or published;
- `qa_run_id`: immutable QA review identity;
- `canonical_url`.

The revision identity is `sanity_doc_id + source_rev`. Never reuse a QA or repair decision for a different revision. Retries must reuse their deterministic execution ID and must not duplicate a production mutation.

## Stage A: daily publication handoff

After each `vertu-10` article passes all publication and live-page gates:

1. Upsert one current-state row in canonical Base `文章资产` using `article_key` and create/link the immutable `发布批次` row.
2. Register exact T+24h, T+72h, D+7 and D+28 due times.
3. Persist or reconcile the independent QA result in the same canonical Base `QA Runs` table for the exact `sanity_doc_id + source_rev`.
4. A publication PASS uses `Patch Action=no_patch_needed` and records that no repair queue is needed for that revision.
5. Preserve the local QA, Discover, image, author, link, mutation and live-verification artifacts.
6. Emit a visible receipt even when fewer than ten articles publish.

All group receipts from `vertu-10`, `vertu-2`, `vertu` and `vertu-skill` use the
vvv user-robot channel defined in
`docs/03-运行/VERTU-vvv-Group-Receipt-Template.md`. The legacy WeChat gateway,
`WECHAT_*` configuration and name-based group routing are prohibited for this
content chain. Codex remains a visible secondary receipt surface. Every vvv
attempt stores a redacted `vvv-notification.json`; only `status=SENT` counts as
successful group delivery, and `DELIVERY_UNKNOWN` must not be retried blindly.

Failure to complete either article/publication or QA handoff inside the canonical Base is `HANDOFF_INCOMPLETE`; publication success must not be reported as a fully completed chain.

## Stage B: QA intake and repair routing

`vertu-2` has two phases and must not start with only the repair queue.

### Phase 1: intake QA

1. Read authenticated, live, non-News Sanity revisions published or changed during the rolling seven-day window.
2. Reconcile them against canonical Base `QA Runs` by `sanity_doc_id + source_rev + skill_version`.
3. Run independent QA for every missing current revision and write immutable QA Runs and Findings.
4. Route each result:
   - `PASS + no_patch_needed` → no repair; keep published and monitorable.
   - `FIX + low_risk_patch_allowed` with no restricted fields, no human-confirmation Finding and executable exact locators → `待执行` only when a deployment-specific repair approval profile is configured.
   - `FIX + manual_review_before_patch` → `人工阻塞` with the missing decision/evidence stated.
   - `BLOCK + rewrite_required` → `人工阻塞`; a rewrite is not a low-risk patch.
   - `BLOCK + blocked_no_patch` → `人工阻塞`.

The standing chain approval is deliberately narrow. It does not authorise restricted claims, product facts, prices, specifications, materials, privacy/security promises, medical claims, author/schema changes, slug/canonical changes or unsupported rewrites.

### Phase 2: repair executor

1. Consume at most ten `待执行` rows, lock each as `执行中`, and re-fetch the live revision.
2. Stop on revision conflict or locator failure.
3. Repair the actual Sanity Draft and preserve a rollback snapshot.
4. Run independent R2 QA on the changed Draft and create a new linked QA Run.
5. Publish only after R2 `PASS`, exact revision checks and live-page verification.
6. Set the originating queue row to `已发布`, record before/after revisions and mark only verified Findings resolved.
7. Refresh the performance Base article revision and create experiment-verification due dates without overwriting the original publication checkpoints.

`NO_QUEUED_ITEMS` is valid only after both intake QA and queue routing have run. It means no safe authorised repair remains, not merely that nobody manually populated the queue.

## Stage C: performance monitoring and feedback

For the rolling 35-day cohort every day, and for every due original-publication or repair-experiment checkpoint:

1. Write a daily pulse with current live health, latest finalised GSC, available GA4, source freshness and newly changed anomaly state.
2. Read exact-window GA4 and mature GSC Discover/Search data for due milestones.
3. Write exactly one immutable `节点复盘` per deterministic `复盘ID`, plus `内容复盘`, current `文章资产` state and one `监控运行` record in the canonical Base. Search the whole table by exact `复盘ID` before every create; one existing match is a verified no-op/reconciliation, and multiple matches block the checkpoint write for audited maintenance.
4. For an evidence-backed optimisation, write one `修改实验` proposal and link its article, checkpoint evidence, QA Run and current revision.
5. Monitoring never directly mutates Sanity. A low-risk proposal enters QA intake; restricted or major changes remain approval-blocked.
6. D+28 and verified experiment outcomes must be summarised as cluster learning that the next `vertu-10` run reads before candidate scoring.

Every monitoring execution emits a visible receipt containing scanned runs/articles, due/completed/blocked counts, GA4 and GSC freshness, Base rows written, next due time and artifact path. Quiet success may say `NO_ACTIONABLE_CHANGE`, but must not be visually empty.

## Stage D: governed learning and skill evolution

1. Scan checkpoint artifacts and keep only executed, completed and mature 72h/7d/28d evidence.
2. Deduplicate retries by article and checkpoint; reject planned placeholders, immature windows and source-blocked metrics explicitly.
3. Classify evidence as `OBSERVATION`, expiring `CANDIDATE_PRIOR` or `DURABLE_PRIOR`.
4. Twice daily, create or refresh a provisional prior only from recent repeated mature 72h/7d evidence; expire it after eight days unless a new governed run still supports it.
5. Require at least three mature D+28 articles across two publication runs, or one verified controlled experiment, before activating a durable prior.
6. Replay proposed priors against historical candidate portfolios. Reject changes that reduce traffic-gate compliance, diversity or holdout quality.
7. Apply provisional and durable priors only after eligibility with one combined `-3..+3` ordering adjustment.
8. Write immutable local evidence, one `自动化运行日志` row and one `Skill Change Log` row per proposal, activation, expiry, rejection or rollback.
9. Twice daily, run tests, Skill validation and historical replay, then execute the versioned Skill release gate. The shorter observation cadence does not shorten promotion maturity: traffic-affecting changes still require mature D+28 evidence or a verified controlled experiment. Apply material replay-safe non-structural changes, record `NO_PROMOTION` and `NO_SKILL_CHANGE` when nothing qualifies, and keep structural rubric, authority or safety changes explicitly approval-gated.

Checkpoint history is immutable. A monitoring handoff may update only the
configured lifecycle and replacement-pointer fields to maintain exactly one
`CURRENT` observation per logical article/checkpoint identity; all older valid
rows become `SUPERSEDED`, and blocked or immature rows remain `HISTORICAL`.
10. The next `vertu-10` run records both learning fingerprints and matched prior IDs. Invalid, absent or expired evidence becomes an explicit unavailable/ignored state, never an inferred rule.

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
3. Eligible low-risk FIX rows enter `待执行`; restricted/manual rows enter `人工阻塞` with reasons.
4. A successful repair creates R2 QA, verified publication evidence and new experiment-monitoring dates.
5. Monitoring writes concrete metrics or explicit maturity/source states and always emits a visible receipt.
6. The next daily topic-selection run reads mature cluster and experiment outcomes.
7. No automatic article is assigned to `news` or `/news/`.
8. Every automation invocation resolves to exactly one `自动化运行日志` row and one local run summary, including no-op and failure outcomes.
9. Every active learned prior is fingerprinted, replay-validated, bounded, reversible and recorded in `Skill Change Log`; observation checks run twice daily while promotion maturity remains unchanged.

# QA Tracking Contract

## Current Operational Tracker

- System: Feishu Base
- Base name: `VERTU 内容与 SEO 运营闭环`
- Base token: `${FEISHU_BASE_TOKEN}`
- QA Runs table: `${FEISHU_QA_RUNS_TABLE_ID}`
- Findings table: `${FEISHU_FINDINGS_TABLE_ID}`
- Skill Change Log table: `${FEISHU_SKILL_CHANGE_LOG_TABLE_ID}`
- Content review table: `${FEISHU_CHECKPOINTS_TABLE_ID}`
- Publication runs table: `${FEISHU_PUBLICATION_RUNS_TABLE_ID}`
- Historical trackers are read-only archives. Operators must supply their own
  current canonical tracker; this package contains no archive identifiers.

## QA Runs Write Contract

Shared production/QA identity contract: `${VERTU_PDCA_ROOT}/docs/03-运行/VERTU-QA-Handoff-Contract.md` (`qa-handoff-v1`). Component versions remain independent; Base records their compatibility.

Create one new record per source revision and review round. Required fields:

- `文章标题`
- `文章 URL`
- `QA Run ID`
- `Skill Version`
- `QA Policy ID`
- `QA Policy Version`
- `QA Policy Hash`
- `Evaluation Profile`
- `QA Identity Status`
- `QA Handoff Contract Version`
- `Producer Skill ID`
- `Producer Skill Version`
- `Publication Run ID`
- `Article Key`
- `Draft Bundle SHA256`
- `SERP Benchmark Fingerprint`
- `Original Value Delta`
- `Source Identity Type`
- `Release Gate Role`
- `Compatibility Status`
- `QA Result Fingerprint`
- `复核轮次`
- `上一轮 QA Run ID` when applicable
- `Sanity Doc ID`
- `Source Rev`
- `目标关键词`
- `内容类型`
- `市场`
- `最终决策`
- `评分`
- `评分明细`
- `风险等级`
- `是否 BLOCK`
- `Critical Veto`
- `Patch Action`
- `问题总数`
- `下一步动作`
- `审核时间`

Repair/publication execution fields on the same QA Run row:

- `自动修复发布状态`
- `发布前 Rev`
- `发布后 Rev`
- `发布时间`
- `发布执行记录`

`最终决策` remains the immutable decision of that QA Run. Do not use it as a mutable repair workflow status.

Do not overwrite an earlier QA Run when the content or `_rev` changes.

Identity contract:

- New QA identity key: `Sanity Doc ID + Source Rev + QA Policy Hash + Evaluation Profile`.
- Compute `QA Policy Hash` from the ordered stable labels and bytes of `SKILL.md`, `references/qa-tracking-contract.md`, `scripts/vertu_qa_policy.py`, `scripts/vertu_editorial_safeguards.py`, and `docs/03-运行/VERTU-QA-Handoff-Contract.md`. Absolute workspace paths must not affect the hash.
- `Skill Version` remains reader-facing lineage but is not sufficient for deterministic identity.
- Historical rows whose exact policy bytes/profile cannot be proven use `LEGACY_POLICY_UNVERIFIED`; do not invent a current hash for them.
- Duplicate historical `QA Run ID` values use `DUPLICATE_QA_RUN_ID`; preserve every row and decision.
- Current-policy rows use `CURRENT_POLICY` only when all four identity fields and the exact current policy hash are present.
- Current production-chain rows additionally require `Compatibility Status=COMPATIBLE`, exact producer/handoff identity and a matching `QA Result Fingerprint`.
- Historical rows without a provable shared handoff use `Compatibility Status=LEGACY_UNVERIFIED`; do not change their verdict, score or Findings.

## Findings Write Contract

Create one record per finding and link it through `关联 QA Run`. Required fields:

Deterministic editorial safeguard Findings use the stable categories `DUPLICATE_VERTU_CONCIERGE_INTEGRATION`, `TEMPLATE_DEPENDENT_DRAFT`, `BODY_VISUAL_MISSING`, and `SERP_DIFFERENTIATION_MISMATCH`. The first, second and fourth are `必修` and remain release-blocking until a changed source revision receives a new PASS. `BODY_VISUAL_MISSING` is `建议` and non-blocking during the first-phase measurement window.

- `Patch ID`
- `QA Run ID`
- `关联 QA Run`
- `文章标题`
- `Sanity Doc ID`
- `问题标题`
- `位置`
- `严重级别`
- `问题分类`
- `证据标签`
- `问题描述`
- `修改建议`
- `Before`
- `After`
- `需要人工确认`
- `负责人`
- `执行代理`
- `SLA策略`
- `SLA起算时间`
- `截止时间`
- `处理状态`
- `复核结果`
- `来源链接` when available
- `审核备注` when needed

SLA contract:

- `负责人` is the accountable business owner; `执行代理` is the repair or review agent. They must not be inferred from an unrelated article author or QA reviewer.
- Active `致命` findings use `critical_24h`; active `必修` findings use `required_72h`; active `建议` findings use `recommended_7d`.
- `SLA起算时间` is the finding creation or governed intake time. `截止时间` is derived from that timestamp and the selected SLA policy.
- Resolved historical findings use `closed_exempt`; do not fabricate a past deadline for them.
- Missing active SLA fields are a governance blocker. Overdue findings escalate to the accountable owner while the execution agent remains responsible for diagnosis, repair and evidence readback.

## Rerun Rules

1. Re-fetch the article URL and current Sanity `_rev`.
2. Create a new `qa_run_id`; increment `复核轮次`.
3. Set `上一轮 QA Run ID` to the previous run.
4. Write new findings; do not edit previous findings to match the new result.
5. Update prior finding handling statuses only when a human or verified rerun establishes resolution.
6. Keep PASS/FIX/BLOCK and the skill version that produced each historical run.

## Automated Repair And Publication Queue

State meanings:

- `未入队`: QA exists but no automated repair/publication execution was requested.
- `待执行`: authorised queue item; automation may fetch the current Sanity document and linked Findings.
- `执行中`: the automation has locked the item and recorded the current pre-publish revision.
- `修复后复核`: an actual Sanity Draft changed and a new QA Run is being created or evaluated.
- `已发布`: the new QA Run is PASS, the repaired revision was published, and the live canonical URL passed verification.
- `人工阻塞`: evidence, ownership, restricted-claim confirmation, source identifiers, or safe repair semantics require a human decision.
- `执行失败`: a technical write, publication, or live-verification operation failed; the execution log must contain the retryable reason.

Execution rules:

1. Consume only `待执行`; set `执行中` before mutation work.
2. Re-fetch the authenticated Sanity document and compare its current `_rev` with the queued `Source Rev`.
3. Repair an actual Sanity Draft. A local Markdown or patch-plan artifact does not change the queue to `修复后复核`.
4. Run QA against the changed Draft and create a new QA Run with the previous QA Run ID as parent.
5. Publish only when the new QA Run is PASS and no critical/required or human-confirmation Finding remains unresolved.
6. After publication, re-fetch the Sanity document, verify the canonical live URL, and write `发布前 Rev`, `发布后 Rev`, `发布时间`, and `发布执行记录`.
7. Only then set the queue to `已发布` and mark resolved original Findings `已验证`.
8. Preserve the original QA Run decision, score, source revision, findings, and skill version.

## Skill Feedback Rules

Record proposed or implemented QA rule changes in `Skill Change Log`. Changes require traceable source QA Run IDs and must distinguish:

- false positive;
- false negative;
- missing field or workflow step;
- scoring calibration;
- compliance clarification;
- schema or integration defect.

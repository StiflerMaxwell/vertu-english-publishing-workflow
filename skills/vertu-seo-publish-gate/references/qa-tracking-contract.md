# QA Tracking Contract

## Current Operational Tracker

- System: Feishu Base
- Base name: `VERTU 内容与 SEO 运营闭环`
- Base token: `${FEISHU_BASE_TOKEN}`
- QA Runs table: `${FEISHU_QA_RUNS_TABLE_ID}`
- Findings table: `${FEISHU_FINDINGS_TABLE_ID}`
- Skill Change Log table: `${FEISHU_SKILL_CHANGE_LOG_TABLE_ID}`
- Content review table: `${FEISHU_CONTENT_REVIEW_TABLE_ID}`
- Publication runs table: `${FEISHU_PUBLICATION_RUNS_TABLE_ID}`
- Any former tracker configured as an archive is read-only. Automated QA and
  repair execution must not write there.

## QA Runs Write Contract

Create one new record per source revision and review round. Required fields:

- `文章标题`
- `文章 URL`
- `QA Run ID`
- `Skill Version`
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

## Findings Write Contract

Create one record per finding and link it through `关联 QA Run`. Required fields:

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
- `处理状态`
- `复核结果`
- `来源链接` when available
- `审核备注` when needed

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

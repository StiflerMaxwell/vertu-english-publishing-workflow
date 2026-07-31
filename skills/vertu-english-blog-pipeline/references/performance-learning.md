# Performance Learning and Skill Evolution Contract

Use this contract for every automatic topic-selection run and every scheduled content retrospective. Its purpose is to turn real publishing outcomes into governed, reversible improvements without overfitting one article or weakening the traffic gate.

## Evidence levels

| Level | Minimum evidence | Allowed effect |
|---|---|---|
| `OBSERVATION` | Executed, mature 72-hour checkpoint | Briefing context only; no score or eligibility effect |
| `CANDIDATE_PRIOR` | At least three recent mature 72-hour articles across two runs, or at least two recent mature 7-day articles across two runs, with directional agreement | Each prior is bounded by its evidence level and the provisional layer is capped to `-2..+2` among already eligible candidates |
| `DURABLE_PRIOR` | At least three mature 28-day articles across two publication runs, or one verified controlled experiment | Bounded `-3..+3` portfolio-priority adjustment after eligibility |

Never promote a planned checkpoint, `DATA_NOT_MATURE`, `SOURCE_BLOCKED`, missing execution timestamp, null future metric, unverified prose summary or one isolated spike.

## User-approved editorial strategies

Keep explicit user strategy separate from governed performance priors.

- A user may direct the pipeline to generate more candidates from a named audience or editorial lane immediately.
- Record that instruction as `USER_APPROVED_EDITORIAL_STRATEGY`, including its scope, date and exact guardrails.
- Apply it to candidate generation, audience-fit classification and soft portfolio mix only.
- Do not encode it as a `DURABLE_PRIOR`, score adjustment, demand provider, trend label or veto waiver before the normal evidence gate passes.
- Preserve counterexamples and the narrowest supported cluster boundary. A commercial-airline cabin result does not prove private aviation or generic luxury travel.
- At 72 hours classify the observation, at 7 days test persistence, and at 28 days submit it to the normal cohort/replay promotion process.

## Active artifacts

Read the durable artifact:

`${VERTU_PDCA_ROOT}/output/vertu-signals/learning/active-performance-priors.json`

Also read the provisional artifact:

`${VERTU_PDCA_ROOT}/output/vertu-signals/learning/provisional-performance-priors.json`

Require for durable priors:

- `contract_version: performance-learning-v1`;
- a valid `snapshot_fingerprint`;
- `status: ACTIVE | NO_DURABLE_LESSON`;
- each active prior to identify scope, adjustment, evidence counts, confidence and rollback condition;
- at least three D+28 articles across two publication runs, or one verified experiment, for every `DURABLE_PRIOR`.

Require for provisional priors:

- `contract_version: performance-learning-provisional-v1`;
- a valid `snapshot_fingerprint`;
- `status: ACTIVE | NO_PROVISIONAL_LESSON`;
- every active prior to use `learning_level: CANDIDATE_PRIOR`;
- at least three mature 72-hour articles across two publication runs with directional agreement of at least 0.67, or two mature 7-day articles across two publication runs with directional agreement of at least 0.75;
- source evidence executed in the preceding 14 days;
- an activation time, expiry time and rollback condition;
- a maximum absolute adjustment of one for 72-hour evidence or two for 7-day evidence;
- UTC activation and expiry timestamps; the prior is ignored when `now >= expires_at`;
- expiry after eight days unless a new governed 48-hour run refreshes it with still-valid evidence.

If validation fails, record `LEARNING_PRIORS_INVALID` or `PROVISIONAL_LEARNING_PRIORS_INVALID` and continue without the affected layer. Never rebuild priors from a Markdown summary or a previous model's claims.

## Daily consumption

Before candidate scoring:

1. read both active artifacts and record their fingerprints;
2. preserve each candidate's normal computed score, demand verdict and vetoes;
3. ignore expired provisional priors;
4. apply learned adjustment only after eligibility;
5. cap the provisional layer to `-2..+2`, then cap the combined provisional-plus-durable adjustment to `-3..+3`;
6. record matched prior IDs, levels and the final selection-priority score;
7. preserve portfolio diversity and event-cluster caps.

A prior may not:

- raise a sub-80 candidate into eligibility;
- waive a veto or validation error;
- create or substitute a demand provider;
- create `REALTIME_HOT`, `RISING_SEARCH` or editorial-breakout evidence;
- authorise publication or Sanity mutation;
- encourage cloning a successful page.

## 48-hour promotion check

Run at least once every 48 hours after the daily monitor:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_content_learning_flywheel.py \
  --root ${VERTU_PDCA_ROOT}/output/vertu-signals \
  --execution-id "$execution_id" \
  --output learning/YYYY-MM-DD/$execution_id/learning-snapshot.json \
  --active-output learning/active-performance-priors.json \
  --provisional-output learning/provisional-performance-priors.json
```

The job must:

- deduplicate retries by article and checkpoint, keeping the latest executed evidence;
- report every rejected input by reason;
- aggregate same-age Search, Discover and GA4 outcomes by cluster, intent, title pattern, trend class, section and portfolio bucket;
- aggregate `PREMIUM_DECISION_CORE | ADJACENT | EXPLORATION` separately and retain mass-recognisability, decision-intent and niche-risk boundaries;
- generate expiring provisional priors only from recent repeated mature 72-hour or 7-day evidence;
- expire or replace provisional priors whose evidence or activation window is stale;
- preserve the existing durable promotion threshold;
- replay proposed priors against historical candidate portfolios;
- reject any proposal that lowers gate compliance, portfolio diversity or holdout quality;
- write `NO_PROMOTION` when neither a provisional nor durable rule qualifies, write `NO_DURABLE_LESSON` when only provisional evidence qualifies, and preserve the last valid durable `ACTIVE` pointer unchanged;
- write one canonical Base `自动化运行日志` row and one `Skill Change Log` row per proposed, activated, expired, rejected or rolled-back change.

## 48-hour skill release

On every 48-hour run:

1. collect the preceding 35 days of daily pulses plus all mature 72h/7d/28d evidence, and retain a 90-day comparison window;
2. compare active priors with holdout cohorts and verified experiments;
3. expire or roll back reversed priors;
4. consolidate repeated structural proposals;
5. run scorer tests, skill validation and a historical replay;
6. bump the patch version only for material data/wording/process changes that pass all checks, or the minor version for an explicitly approved contract change;
7. record old rule, new rule, evidence, replay result, implementation time, active skill version and rollback condition in `Skill Change Log`.

If no material and replay-safe change qualifies, preserve the current Skill version and record `NO_SKILL_CHANGE`; never create a cosmetic version bump. Data-only provisional or durable priors and non-structural operational clarifications may activate automatically when every deterministic gate passes. Structural changes to rubric weights, thresholds, vetoes, source authority, publication authority or QA boundaries remain proposals until explicitly approved.

## Canonical Base

Use only the configured canonical Base and its `Skill Change Log` table. Resolve
both identifiers from the deployment-specific schema map; never embed them in
the Skill.

Record:

- deterministic Change ID and execution ID;
- evidence level, scope and sample size;
- confidence and source paths;
- old rule and proposed/new rule;
- bounded adjustment;
- replay result;
- state: proposed, accepted, implemented or rejected;
- skill version, activation time, expiry and rollback condition.

Never overwrite historical change records. Use a new Change ID for a revised proposal or rollback.

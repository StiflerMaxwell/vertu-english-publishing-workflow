# Skill Evolution Scorecard

Use this contract for every proposed change to the VERTU English publishing Skill or its governing process. It adapts paired before/after evaluation to VERTU's real objective: qualified Search and Discover traffic with reliable production delivery.

## Boundary

The scorecard evaluates a Skill change. It does not score article candidates and does not replace `vertu_content_traffic_gate.py`.

Never let the scorecard:

- create demand evidence or a `REALTIME_HOT` / `RISING_SEARCH` label;
- make a topic with raw score below 80 eligible;
- waive a source, duplication, non-News, QA, Discover, image, author, link or publication veto;
- approve an experiment or mutate Sanity;
- turn a 24-hour or isolated 72-hour spike into a durable rule.

## Three independent layers

Do not combine the layers into one total.

### 1. Structural diagnostic — triage only

Score each dimension from 0 to 100 and attach at least one evidence reference:

| Dimension | Weight |
| --- | ---: |
| Workflow executability | 15 |
| Failure and rollback clarity | 15 |
| Evidence and lineage | 15 |
| Permissions and manual approval | 10 |
| Test coverage | 15 |
| Historical replay | 20 |
| Documentation, runtime and maintenance | 10 |

A diagnostic score below 70 rejects the candidate before comparative evaluation. A score of 70 or more is not a keep decision.

### 2. Same-rubric paired comparison — keep/revert signal

Compare the exact before and after Skill versions under one fingerprinted rubric.

- Use an odd number of at least three unique judge executions.
- Every judge records `AFTER_BETTER`, `BEFORE_BETTER` or `TIE` with evidence.
- A strict majority for `BEFORE_BETTER` requires revert.
- A strict majority for `AFTER_BETTER` passes only this layer.
- A split or tie is `INCONCLUSIVE` and requires manual review.

`NOT_REQUIRED` is allowed only for explicitly approved governance infrastructure that does not affect traffic decisions. It is not allowed for scoring weights, thresholds, source authority, vetoes, QA boundaries or publication authority.

### 3. Mature production outcome — promotion signal

Traffic-affecting changes require either:

- at least three mature D+28 articles across at least two publication runs; or
- one verified controlled experiment.

Score each outcome dimension from 0 to 100 with source-complete evidence:

| Dimension | Weight |
| --- | ---: |
| 72h/7d/28d directional consistency | 25 |
| Search and Discover lift | 20 |
| GA4 engagement and qualified journeys | 15 |
| Cross-run stability | 15 |
| Winner coverage | 10 |
| Diversity and cannibalisation | 5 |
| QA, publishing and Base reliability | 10 |

- `>=75`: promotion-eligible after every other gate passes;
- `60–74`: manual review;
- `<60`: revert required.

Promotion eligibility is not activation authority. Structural Skill changes and low-risk experiments remain manually approved.

## Replay hard gate

Replay every candidate against a fingerprinted historical candidate set plus a holdout cohort. Require:

- deterministic test pass;
- zero demand, source-integrity, non-News, QA, publication-authority or other hard-gate regression;
- no material portfolio-diversity or holdout-quality regression;
- exact before/after Skill versions and evidence paths.

Any hard-gate regression overrides all scores and returns `REVERT_REQUIRED`.

## Deterministic runtime

Build one input manifest using contract `skill-evolution-scorecard-input-v1`, then run:

```bash
python3 scripts/vertu_skill_evolution_scorecard.py \
  --input <run-path>/skill-scorecard-input.json \
  --output <run-path>/skill-scorecard.json \
  --observed-at <iso-8601-time>
```

The output contract is `skill-evolution-scorecard-v1`. Preserve its input and scorecard fingerprints. Do not edit a generated scorecard by hand.

## Release decisions

- `REJECTED`: structural diagnostic failed.
- `REVERT_REQUIRED`: before version won, replay failed/regressed or mature production outcome failed.
- `MANUAL_REVIEW`: comparison, replay or production result is inconclusive.
- `PENDING_MATURITY`: early evidence exists but durable evidence does not.
- `PROMOTION_ELIGIBLE`: all required gates passed; activation authority remains separate.
- `IMPLEMENTED_BY_APPROVAL`: explicit governance-only bootstrap, with tests and replay, that does not alter traffic decisions.

## Feishu audit

Use only canonical Base `VERTU 内容与 SEO 运营闭环`, table `Skill Change Log` (`${FEISHU_SKILL_CHANGE_LOG_TABLE_ID}`). Search exact `Change ID` first.

Record:

- Change ID, execution ID and change class;
- diagnostic score, paired verdict, production outcome score and release decision;
- scorecard fingerprint, evidence paths and sample size;
- old/new rule, replay result and rollback condition;
- Skill version, lifecycle state and implementation/expiry time.

Immutable local artifacts are the evidence source of truth. Base is the operational control plane. A materially revised proposal receives a new Change ID; do not overwrite historical evidence.

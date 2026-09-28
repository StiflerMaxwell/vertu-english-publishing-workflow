# Skill Evolution Factor Vector — v1

Contract: `skill-evolution-factor-vector-v1`.

This contract measures whether a change to the VERTU publishing Skill improved the system. It is separate from the 32 candidate/topic factors: candidate factors help choose what to write; these factors judge whether changing the workflow produced durable improvement.

## Core rule

Never sum the 60 factors into one total. Every change must predeclare a small set of target factors and guardrail factors before reading the result. Evaluate those factors at their declared maturity windows, then pass the evidence to the existing paired-review, replay and production-maturity gates.

Every factor row is mandatory and uses exactly one state:

- `AVAILABLE`: a verified numeric measurement exists; zero may be a real value;
- `SOURCE_UNAVAILABLE`: required source or instrumentation is unavailable; value is null;
- `INSUFFICIENT_SAMPLE`: source exists but the cohort is not decision-grade; value is null;
- `NOT_APPLICABLE`: the factor does not apply to this change; value is null.

Omission is invalid. Unavailable evidence is never converted to zero.

## The 60 factors

| ID | Factor | What it calculates | Normal maturity |
|---|---|---|---|
| F01 | Search click lift | Finalised Search-click change against a comparable baseline | 28d |
| F02 | Search impression lift | Finalised Search-impression change | 28d |
| F03 | Search CTR lift | Search CTR percentage-point change | 28d |
| F04 | Search position improvement | Baseline position minus treatment position | 28d |
| F05 | Discover click lift | Finalised Discover-click change | 28d |
| F06 | Discover impression lift | Finalised Discover-impression change | 28d |
| F07 | Discover CTR lift | Discover CTR percentage-point change | 28d |
| F08 | Search hit rate | Cohort share passing its Search success gate | 28d |
| F09 | Discover hit rate | Cohort share passing its Discover success gate | 28d |
| F10 | GA4 sessions lift | Landing-session change | 7d |
| F11 | Engaged sessions lift | Engaged-session change | 7d |
| F12 | Engagement rate lift | Engagement-rate percentage-point change | 7d |
| F13 | Average engagement time lift | Average engagement-time change | 7d |
| F14 | Returning-user rate lift | Returning-user rate change | 28d |
| F15 | Qualified journey lift | Verified qualified product/service journey change | 28d |
| F16 | Commerce-assisted conversion lift | Verified content-assisted conversion change | 28d |
| F17 | 72h to 7d persistence | Positive 72h results still positive at 7d | 7d |
| F18 | 7d to 28d persistence | Positive 7d results still positive at 28d | 28d |
| F19 | Cross-run directional agreement | Agreement across publication runs | 28d |
| F20 | Cross-cluster agreement | Agreement across content clusters | 28d |
| F21 | Cross-intent agreement | Agreement across search/decision intents | 28d |
| F22 | Cross-title-pattern agreement | Agreement across title-pattern groups | 28d |
| F23 | Cross-trend-class agreement | Agreement across hot/rising/evergreen classes | 28d |
| F24 | Cross-market agreement | Agreement across declared markets | 28d |
| F25 | Holdout lift | Treatment improvement relative to untouched holdout | 28d |
| F26 | Unseen-entity generalisation | Effect retained on entities unseen during rule development | 28d |
| F27 | Winner capture recall | Mature winners captured by the changed Skill | 28d |
| F28 | Loser avoidance precision | Deprioritised candidates becoming mature losers | 28d |
| F29 | Outcome variance reduction | Relative reduction in outcome variance | 28d |
| F30 | Cannibalisation delta | Change in verified query/page cannibalisation | 28d |
| F31 | Selection churn | Selection change from immaterial input variation | runtime |
| F32 | Rule coverage | Material changes with declared targets, guardrails and maturity | runtime |
| F33 | Sample adequacy | Evaluated cohorts satisfying declared sample gates | 28d |
| F34 | Source-complete ratio | Accepted source-complete checkpoints / actionable inputs | runtime |
| F35 | Context-lineage completeness | Accepted checkpoints with complete publication/context lineage | runtime |
| F36 | Evidence freshness | Hours since newest accepted evidence | runtime |
| F37 | Missing-data ratio | Blocked or immature actionable inputs / actionable inputs | runtime |
| F38 | Usable evidence yield | Accepted checkpoints / all inspected inputs | runtime |
| F39 | Candidate-pool identity integrity | Accepted evidence with exact publication-run identity | runtime |
| F40 | Baseline comparability | Treatment observations with valid same-age baselines | 28d |
| F41 | Effect confidence | Predeclared confidence measure for observed effect | 28d |
| F42 | Confounder penalty | Share/severity of uncontrolled confounders | 28d |
| F43 | Replay determinism | Identical-input replays with identical outputs | runtime |
| F44 | Provider agreement | Agreement among independent acquisition-system families | 28d |
| F45 | Hypothesis direction match | Target factors moving in their predeclared direction | 28d |
| F46 | Causal attribution strength | Attribution after holdout/baseline/confounder checks | 28d |
| F47 | QA pass-rate delta | Independent first-pass QA pass-rate change | 7d |
| F48 | QA blocker or defect-rate delta | Blocker/material-defect rate change | 7d |
| F49 | Live-verification pass rate | Attempted publications passing every live check | runtime |
| F50 | Base handoff completion rate | Domain decisions with complete exact-record lineage | runtime |
| F51 | Automation execution success rate | Governed executions ending in truthful success | 7d |
| F52 | Retry convergence | Retryable failures resolved within bounded attempts | 7d |
| F53 | Scope collision or stale-lock rate | Executions blocked by collision/stale ownership | 7d |
| F54 | Rollback or reversal rate | Promoted changes later reversed or rolled back | 90d |
| F55 | Notification precision | Receipts representing distinct actionable/terminal events | 7d |
| F56 | Time to mature evidence | Activation-to-first decision-grade evidence | 28d |
| F57 | Learning cost efficiency | Decision-grade learning per measured compute/labour cost | 28d |
| F58 | Human intervention rate | Low-risk governed executions needing manual intervention | 7d |
| F59 | Skill version drift incidence | Producer/QA/automation executions with incompatible versions | runtime |
| F60 | Promotion survival at D28 and D90 | Promoted changes valid at both later reviews | 90d |

## Required change hypothesis

Before evidence collection, write:

```json
{
  "change_id": "deterministic-change-id",
  "before_version": "3.15.1",
  "after_version": "3.17.0",
  "hypothesis": {
    "target_factors": [
      {"factor_id": "F35", "expected_direction": "INCREASE", "threshold": 0.05}
    ],
    "guardrail_factors": [
      {"factor_id": "F48", "expected_direction": "NO_HARM", "threshold": 0.0}
    ],
    "maturity_windows": ["runtime", "7d", "28d"]
  }
}
```

Targets and guardrails may not overlap. Unknown or duplicated factor IDs fail closed. Do not change the hypothesis after reading outcome data; a materially revised hypothesis receives a new Change ID.

Target direction must match the factor definition: `HIGHER_BETTER` targets use `INCREASE`, `LOWER_BETTER` targets use `DECREASE`, and guardrails use `NO_HARM`. Contextual factors require a separate explicit comparator contract before they can be selected.

## Generation

Use:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_skill_evolution_factors.py \
  --input <skill-evolution-factor-input.json> \
  --output <skill-evolution-factors.json>
```

The output includes exactly 60 rows, status counts, registry/cohort/source fingerprints and `global_score_allowed=false`. The bootstrap is `SHADOW_ONLY` and has no production effect.

## Exact-vector evaluation

After the vector exists, write `skill-evolution-factor-evaluation-input.json` under contract `skill-evolution-factor-evaluation-input-v1`. Bind it to the exact Change ID, execution ID, before/after versions and vector fingerprint; declare `evaluation_window`, `activation_state`, `affects_traffic_decisions`, `production_level` and non-empty evidence references. Then run:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_skill_evolution_factor_evaluator.py \
  --vector <skill-evolution-factors.json> \
  --input <skill-evolution-factor-evaluation-input.json> \
  --output <skill-evolution-factor-evaluation.json>
```

The evaluator checks only the predeclared target and guardrail rows. `SOURCE_UNAVAILABLE` becomes `SOURCE_BLOCKED`; `INSUFFICIENT_SAMPLE` or an unreached maturity window becomes `CONTINUE_OBSERVING`; any mature guardrail breach becomes `REVERT_REQUIRED`; mature target failure becomes `NO_EFFECT`. Passing traffic factors at 7d require a governed experiment, while D+28 or a verified experiment may become `PROMOTION_CANDIDATE`. The evaluator never activates a Skill rule or experiment.

## Decision boundary

The factor vector supplies observations and its evaluator supplies a bounded hypothesis decision. Promotion still requires:

1. valid target and guardrail observations at the declared maturity;
2. same-rubric paired comparison and deterministic replay where applicable;
3. no regression in existing traffic, quality, diversity, QA, publication or lineage gates;
4. mature D+28 evidence across the governed cohort or one verified controlled experiment for traffic-affecting changes;
5. the active `skill-evolution-scorecard-v2` consuming the exact `skill-evolution-factor-evaluation-v1` fingerprint and the required approval.

Fast 24h/72h evidence may trigger investigation, rollback protection or a controlled experiment. It may not permanently promote a Skill rule.

## Canonical Base

Write one immutable row per factor observation to `Skill 进化因子观测`. Use deterministic observation identity from Change ID, execution ID, factor ID and vector fingerprint. Keep `Skill 学习与进化` (`CONFIGURE_TBL`, formerly `Skill Change Log`) as the change-level summary. Never place credentials, private source text or unredacted tokens in either table.

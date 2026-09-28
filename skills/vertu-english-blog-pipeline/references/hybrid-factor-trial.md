# Hybrid Factor Score Paired Trial — v1

Use this contract only while the immutable configuration at `${VERTU_PDCA_ROOT}/output/vertu-signals/learning/factor-score-paired-trial-config.json` is valid and `ACTIVE`.

## Boundary

- Trial ID: `hybrid-factor-80-20-two-batch-20260825`.
- Register exactly two unique future `vertu-10` publication runs.
- Control: `factor_score_mode=legacy`, `score_source=computed_v3_12_0`.
- Challenger: `factor_score_mode=hybrid_trial`, `score_source=computed_hybrid_v3_16_0_trial`.
- Only the control portfolio may continue to writing, QA, Image Gen or publication.
- The challenger may reorder or reject candidates in its own evidence artifact, but cannot replace, add, draft or publish an article.
- A third unique run is `TRIAL_CAP_REACHED` and requests zero trial mutations.

This is an explicitly approved low-risk paired observation, not activation of the hybrid score as the production default.

## Required run artifacts

After extracting all 32 factors, run the traffic gate twice over the exact same candidate pool and source artifacts:

```bash
python3 scripts/vertu_content_traffic_gate.py score \
  <normal scorer arguments> \
  --factor-score-mode legacy \
  --output <run-path>/candidate-scores-legacy.json

python3 scripts/vertu_content_traffic_gate.py score \
  <the exact same normal scorer arguments> \
  --factor-score-mode hybrid_trial \
  --output <run-path>/candidate-scores-hybrid.json
```

Require matching `candidate_pool_fingerprint`, candidate count, trend mode, realtime snapshot, source artifacts and priors. Then register the pair:

```bash
python3 scripts/vertu_factor_score_paired_trial.py register \
  --config ${VERTU_PDCA_ROOT}/output/vertu-signals/learning/factor-score-paired-trial-config.json \
  --legacy <run-path>/candidate-scores-legacy.json \
  --hybrid <run-path>/candidate-scores-hybrid.json \
  --publication-run-id <publication-run-id> \
  --observed-at <iso-8601-time> \
  --registry-root ${VERTU_PDCA_ROOT}/output/vertu-signals \
  --output <run-path>/factor-score-paired-trial.json
```

`REGISTERED_WITH_REGRESSION` remains evidence but is not permission to use the challenger. `INVALID` fails the trial registration while leaving the normal control workflow unchanged. `TRIAL_CAP_REACHED` ends further registrations.

## Outcome review

At the source-mature 72-hour and 7-day checkpoints, attach GSC Discover/Search and GA4 evidence to the registered common control candidates. Missing or delayed sources remain `DATA_NOT_MATURE` or `SOURCE_BLOCKED`, never zero.

Compare control and challenger rank ordering only for common candidates that were actually published under the control. Preserve selected-set differences separately; an unpublished challenger-only candidate has no production outcome and cannot be treated as a loss or win.

After both registered runs reach source-complete 7-day review, build the same-rubric paired review required by `skill-evolution-scorecard.md`. Do not promote the hybrid score from 72-hour evidence alone. Production-default activation still requires the governed scorecard, replay safety, mature evidence and explicit authority.

# Discover Recovery Editorial Strategy v1

This reference governs a temporary, explicitly user-approved candidate-generation strategy when finalised Google Search Console Discover performance falls sharply. It is not a learned prior and has no scoring or publication authority.

## Active pointer

Read `${VERTU_PDCA_ROOT}/output/vertu-signals/learning/active-discover-recovery-profile.json` after `discover-baseline.json` and before broad candidate generation.

Require:

- `contract_version=discover-recovery-editorial-strategy-v1`;
- `state=ACTIVE`;
- `authority_basis=USER_APPROVED_EDITORIAL_STRATEGY`;
- a valid fingerprint and source `discover-pulse-v1` fingerprint;
- approval and expiry timestamps no more than seven days apart;
- current time before `expires_at`;
- every non-candidate-generation authority flag false.

Invalid, missing, inactive or expired evidence has zero effect. Record `RECOVERY_PROFILE_UNAVAILABLE | INACTIVE | EXPIRED | STATE_INVALID` and continue with the standing strategy.

## Candidate-pool effect

The profile may shape the serious candidate pool before scoring:

- prefer VERTU-relevant decision/comparison intents with clear alternatives, stakes and reader-visible value objects;
- prefer executive AI, privacy, security and mobile-technology decisions with broad reader relevance;
- reserve 10–20% of candidate-generation effort for verified current events when usable sources exist;
- reserve no more than 10% for controlled exploration;
- exclude generic household, kitchen, mattress and weakly related wellbeing directions from the default recovery pool;
- put observed categories declining by at least 80% on cooldown unless the exact candidate has material new evidence and independently passes every unchanged normal gate.

These percentages are soft pool-construction guidance. They are not selected-article or publication quotas. Never manufacture candidates, publish filler or lower a gate to satisfy the mix.

Write `discover-recovery-profile.json` and `candidate-pool-plan.json` into the run directory. Record the profile fingerprint on every serious candidate generated under it.

## Immutable authority boundary

The profile may not:

- create or qualify Search demand;
- change `computed_v3_12_0`, raw score or `selection_priority_score`;
- create `REALTIME_HOT`, `RISING_SEARCH` or `EDITORIAL_BREAKOUT`;
- change eligibility or waive a veto;
- relax duplicate, evidence, Discover, QA, image, author, link, live or Base gates;
- force VERTU/Concierge insertion;
- change section routing or authorise `/news/`;
- create a provisional or durable learned prior;
- renew or extend itself.

## Measurement and rollback

Register exact T+72h, D+7 and D+28 observations for runs that use the profile. T+72h is directional only. D+7 may support a separate renewal proposal. D+28 or a verified experiment is required for durable learning.

On expiry, guardrail breach, invalid fingerprint or explicit rollback, stop using the pointer without rewriting historical runs. Preserve the exact profile and outcomes in local artifacts and canonical Base.

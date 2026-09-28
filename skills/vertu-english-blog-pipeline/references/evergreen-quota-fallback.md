# Daily Hot-to-Evergreen Quota Fallback — v1

Contract: `daily-publishing-quota-v2`.

This contract applies only to the named `vertu-10` production profile. It makes ten fully live-verified current-run articles the hard daily completion condition while keeping every topic, editorial, QA and publication gate unchanged.

## Supply phases

Use the phases in this exact order:

1. `HOT_PRIMARY`: evaluate verified `REALTIME_HOT` and `RISING_SEARCH` candidates through cumulative 30, 60, 90 and 120 serious-candidate rounds.
2. `EVERGREEN_FALLBACK`: when cumulative eligible supply remains below ten after `HOT_PRIMARY` reaches 120, generate an independent evergreen Search pool through its own cumulative 30, 60, 90 and 120 rounds.
3. `DOWNSTREAM_REPLACEMENT`: after selection, replace any article blocked by SERP, evidence, drafting, QA, Discover, image, author, publication, live or Base handoff using an unselected cumulative eligible candidate; expand the active phase when no replacement remains.

Stop candidate generation as soon as ten cumulative eligible directions exist. Do not require a hot article when the official evidence does not support one. A valid evergreen article counts identically towards the daily quota after every downstream gate passes, but it must always be reported as `EVERGREEN_SEARCH`, never hot.

## Independent evergreen generation

Build the fallback pool from the current run's authorised evidence:

- candidate-level finalised GSC query/page and country evidence;
- authorised Google Ads Keyword Planner ideas and metrics;
- live authenticated Sanity inventory, exact-intent overlap and seven-day duplicate checks;
- configured markets and market-specific query variants with a real reader distinction;
- permanent `brand-mindset-fit-v1` core or qualified-adjacent clusters;
- current SERP gaps and durable reader decisions.

Every fallback candidate must declare a distinct normalised query, intent, entity or market boundary, `supply_phase=EVERGREEN_FALLBACK`, `trend_class=EVERGREEN_SEARCH`, source references and the exact evergreen-pool fingerprint before scoring. Do not relabel a rejected hot/current candidate without material new evidence or a genuinely different query/intent boundary.

Keyword Planner volume alone is not enough for a Search-first pass. The unchanged acquisition-system-family rule still requires two independent positive demand families. Historical cluster adjacency, D2TR, YouTube and SERP observations remain supporting context only.

## Unchanged gates

Fallback may not:

- lower score 80 or change `computed_v3_12_0`;
- create or substitute demand evidence;
- change the brand-mindset gate or waive any veto;
- weaken duplicate/cannibalisation, evidence, diversity or Discover forecast checks;
- skip the exact-query SERP benchmark or article-specific differentiation;
- bypass independent QA, Discover readiness, Image Gen, author, non-News, link, live or canonical Base handoff checks;
- force VERTU or Concierge insertion;
- use YouTube, D2TR or learned priors to create eligibility.

## Runtime and quota artifacts

The producer runtime limit is `max_candidates=240`, made of two independently bounded 120-candidate phases. Usage remains cumulative under one deterministic execution ID.

After initial selection and every expansion, phase switch or replacement, validate `daily-quota-state.json` with `scripts/vertu_daily_publishing_quota.py` using:

- `contract_version=daily-publishing-quota-v2`;
- `supply_phase`;
- both phase expansion-target arrays;
- current phase target;
- SHA-256 pool fingerprints for every phase already started;
- cumulative eligible, selected and live-verified article keys;
- exact candidate lineage with phase, trend class and pool fingerprint;
- immutable blocker rows;
- `gates_preserved=true`.

`SWITCH_TO_EVERGREEN` means start the fallback phase and is not terminal. `DAILY_QUOTA_BLOCKED` is permitted only after both 120-candidate phases are exhausted or a truthful source/runtime/publication blocker prevents further safe work. It never authorises filler.

## Receipt

Report hot and evergreen candidate counts, eligible/selected/live counts by phase, phase fingerprints, transition times, replacement reasons, trend classes, provider-family states and the final quota state. Preserve the same information in the canonical Base run and publication lineage.

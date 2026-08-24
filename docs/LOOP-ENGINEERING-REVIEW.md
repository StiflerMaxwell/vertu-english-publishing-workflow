# Loop Engineering review and VERTU adaptation

Review date: 2026-08-24.

Reference project: [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering), reviewed at commit `a6b41ab0351d67ffe3a77370a7f5807de7562ad6`.

## What is useful

Loop Engineering frames reliable agents as an operating system built from a
schedule, isolated work, reusable skills, connectors, a maker/checker split and
durable state. Its strongest contribution to this workflow is not another
prompting style; it is explicit loop ownership, finite budgets, visible state
and honest failure handling.

The VERTU workflow already has stronger domain-specific controls than the
reference project in several areas:

- candidate-level Search/Discover evidence and deterministic traffic scoring;
- exact-revision producer/QA identity through `qa-handoff-v1`;
- independent QA, Discover, image, author, link and live-page gates;
- canonical Feishu Base lineage and explicit non-News routing.

The missing layer was cross-loop orchestration. Producer, monitor, repair,
trend and learning jobs could all be individually safe while still colliding,
retrying the same blocked work or consuming excessive candidate/review effort.

## What v3.14 adopts

- A small local state spine that is read at run start and updated at release.
- One owner for each mutation scope.
- Positive wall-clock, child-task, candidate and attempt budgets.
- An operator kill switch.
- Atomic leases with stale-claim evidence and owner-checked release.
- A health audit for expired, orphaned, malformed or incomplete loop state.

## What it deliberately does not copy

- No generic autonomous code-fixing loop controls content publication.
- No worktree is treated as isolation for Sanity or Feishu. Exact document
  revision, deterministic Base identity and live readback remain the real
  isolation boundary for content operations.
- No verifier is allowed to share the producer's decision authority.
- No local state file replaces canonical Base.
- No readiness score can waive a traffic, QA, Discover or publication gate.

## Evidence from the current VERTU run history

From 2026-08-11 through 2026-08-24, the named daily profile completed fourteen
consecutive ten-article portfolios (140 live, handed-off articles). Candidate
pools ranged from 60 to 178 and no selected article in those runs had verified
`REALTIME_HOT` evidence. Recent monitor pulses repeatedly ended
`SOURCE_BLOCKED`, including unavailable GA4/GSC/D2TR inputs and failed Base
handoff observations.

That means production throughput is stable, while fast feedback and runtime
efficiency are not. v3.14 therefore changes orchestration, not traffic weights:
it caps repeated work, exposes collisions and stale loops, and prevents a
successful publishing receipt from hiding an unhealthy feedback plane.

## Next controlled phase

1. Wire each local automation to emit an acquire and release receipt.
2. Run loop audit before the twice-daily learning/release check.
3. Track candidate count, runtime, blocked retries and stale-claim count for
   seven days.
4. Repair GA4/GSC/D2TR/Base monitor connectivity separately; orchestration
   cannot manufacture missing evidence.
5. Consider automatic suppression of repeated identical source-block receipts
   only after deterministic failure fingerprints are available. Preserve one
   visible changed-state receipt and never silence a new blocker.

This document is an architectural adaptation and contains no copied source code
from the reference project.

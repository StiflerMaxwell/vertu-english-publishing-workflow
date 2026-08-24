# Architecture

## Gate sequence

1. **Local loop guard** — declare runtime budgets and acquire exact mutation
   scopes. Pause, collision, budget, attempt or state failure blocks writes.
2. **Run audit** — create or reconcile one deterministic execution row in the
   canonical Feishu Base. Production is prohibited when this fails.
3. **Traffic evidence** — query finalised GSC, Google Trends, Keyword Planner
   when authorised, editorial intelligence and live Sanity inventory.
4. **Deterministic selection** — score at least 30 candidates. Demand, score,
   veto and pre-draft Discover checks all remain independent.
   Acquisition-system families count once, and candidate GSC must pass the
   configured sample floor before it can count as a positive provider.
5. **Editorial production** — research primary sources, build claim and link
   ledgers, retrieve product knowledge when relevant, then draft.
6. **Independent QA** — the QA Skill returns PASS, FIX or BLOCK. It cannot
   directly publish. It also evaluates duplicate brand integration, batch
   heading fingerprints and non-blocking body-visual coverage.
7. **Discover and image gates** — require `DISCOVER_READY`, then generate and
   verify an article-specific hero through Codex Image Gen.
8. **Run-scoped publication** — introspect the live Sanity schema and revision,
   preview the exact mutation, then publish only individually passing articles.
9. **Live verification** — require canonical, image, author, schema, links and
   non-News routing to reconcile against the rendered page.
10. **Canonical handoff** — persist article assets, immutable publication batch
   and exact-revision QA records in one Feishu Base.
11. **Receipt and monitoring** — send one vvv receipt, schedule 24h/72h/7d/28d
    checks and keep every terminal state visible.
12. **Governed learning** — build provisional and durable priors from mature
    evidence. Learning can reorder already eligible candidates by at most three
    points; it cannot manufacture demand or waive a gate.
13. **Runtime audit and release** — report stale/orphaned claims and release
    only scopes owned by the exact execution. Local release and Base
    terminalisation must both reconcile.
14. **Skill release scorecard** — keep structural diagnostics separate from
    paired before/after review, historical replay and mature production
    outcomes. A good code score is not proof of traffic lift.

## Separation of responsibilities

The editorial Skill owns topic selection, research and writing. The QA Skill
owns review evidence. Codex Image Gen owns image generation. A run-scoped
executor owns Sanity mutation. Monitoring is read-only. This separation
prevents the content generator from self-approving or hiding failed gates.

## Identity and lineage

The shared chain identity is:

```text
publication_run_id
  + article_key
  + Sanity document ID
  + exact published source revision
  + QA run ID
  + canonical URL
```

Every Feishu record, local artifact and live verification result must preserve
this lineage.

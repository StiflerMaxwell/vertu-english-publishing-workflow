# Daily-five quality-first profile — public reference

This public handoff example targets five quality articles per day. The bundled
producer is a sanitised adaptation of upstream 3.20.0; its historical references
to a ten-article standing profile do not grant any permission to users of this
repository. For this example, five supersedes those quantity references while
every eligibility, evidence, QA and safety requirement remains in force.

## Creator defaults

- `target_article_count=5`, `max_articles=5`, `minimum_articles=0`.
- `required_publish_count=0`, `delivery=local_draft`, `production_publish=false`.
- Scheduler template: INACTIVE; example cadence 09:00 Asia/Hong_Kong.
- Submit fewer drafts with an explicit blocker rather than low-quality filler.
- One genuine reader question and one evidence-backed value object per article.
- Independent substantive `quality-review.md` before formal QA. READY is not PASS.
- Current primary sources for prices, dates, capabilities and specifications.
- Suitable official product photography requires verified rights; generated
  concepts must not invent product details and retain the authorised image gate.

## Optional administrator-authorised production deployment

An administrator must separately configure systems, schema maps, exact scope,
approval profile, policy fingerprints and live checks. Only that deployment may
set `required_publish_count=5`, `minimum_articles=5`, `max_articles=5`.

Before each run, reconcile authenticated published inventory and the canonical
ledger. Already-published and manual recovery articles consume the same five
daily slots. Retries never start another five-article batch. Old drafts need
fresh demand, facts, inventory, SERP and exact-revision QA.

HOT_PRIMARY and independently generated EVERGREEN_FALLBACK retain cumulative
30/60/90/120 rounds each and a combined ceiling of 240. Do not invent exhausted
supply or weaken a gate to reach five. Hard blockers and genuine shortfalls
remain explicit. Publication success requires live verification and complete
handoff, not merely a successful CMS request.

Production approvals, author registries, configured recipients, runtime state,
article evidence, credentials and analytics do not transfer with this package.
No installed template should inherit an upstream user's approval or task ID.

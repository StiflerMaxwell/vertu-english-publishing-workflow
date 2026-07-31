# Changelog

## 0.4.0 - 2026-07-13

Source QA Runs:

- `SEOQA-20260713-004`
- `SEOQA-20260713-007`
- `SEOQA-20260713-008`

Changes:

- Added an explicit Feishu-driven repair and publication handoff contract.
- Separated immutable QA decisions from mutable repair/publication execution state.
- Required real Sanity Draft repair, a new QA review round, PASS, publication evidence, and live canonical verification before an item can be marked published.
- Prohibited treating local Markdown proposals as completed repairs.
- Added tracked pre-publish revision, post-publish revision, publish time, and execution evidence fields.

Change control:

- Old behaviour: the repair automation stopped at local proposal packs and could not represent the intended repair-and-publish workflow.
- New behaviour: the QA skill remains an independent non-publishing gate while a separate Feishu-authorised executor may repair the actual Draft and publish only after the new QA Run passes.
- Risk impact: enables the requested automation without allowing the QA gate itself to self-approve or rewrite historical QA evidence.
- Decision owner: Max.
- Implementation date: 2026-07-13.

## 0.3.1 - 2026-07-13

Source QA Runs:

- `SEOQA-20260713-001`
- `SEOQA-20260713-002`

Changes:

- Normalised the final redirected host and trailing slash before comparing live article URLs with sitemap entries.
- Prevented `www.vertu.com` canonical URLs that redirect to `vertu.com` from being reported as false sitemap absences.

Change control:

- Old behaviour: literal URL comparison could report two live, indexed pages as absent from the sitemap.
- New behaviour: follow redirects and compare normalised final URLs.
- Risk impact: removes a discovery false positive without changing content scores or Sanity permissions.
- Decision owner: Max.
- Implementation date: 2026-07-13.

## 0.3.0 - 2026-07-13

Source QA Runs:

- `SEOQA-20260713-001`
- `SEOQA-20260713-002`

Changes:

- Added a mandatory published-inventory discovery gate for batch, catch-up, and scheduled QA.
- Required authenticated read-only Sanity discovery and prohibited treating unauthenticated/public results as the complete publication count.
- Made `publishedAt` the primary publication-window field and prohibited `coalesce(publishedAt, _createdAt)` as publication evidence.
- Limited `_updatedAt` to changed-revision discovery with a second live publication signal.
- Added live HTTP 200, sitemap/indexability, noindex separation, and document-revision deduplication checks.
- Added inventory evidence totals so undercounts and discovery defects remain auditable.

Change control:

- Old behaviour: the recent-publication query could rely on the public Sanity result and undercount protected published documents.
- New behaviour: authenticated read-only discovery is required, followed by live URL and sitemap verification.
- Risk impact: reduces false negatives in batch QA without expanding Sanity write permissions.
- Decision owner: Max.
- Implementation date: 2026-07-13.

## 0.2.0 - 2026-07-10

Source QA Runs:

- `SEOQA-20260710-001`
- `SEOQA-20260710-002`
- `SEOQA-20260710-003`

Changes:

- Added mandatory QA tracking writeback with article URL, Sanity document ID, source revision, skill version, and review round.
- Added immutable rerun history through `parent_qa_run_id` and new QA Runs per changed source revision.
- Added context-aware hard-red handling so clear negations and disclaimers are not blocked by term match alone.
- Preserved blocking for affirmative medical/product claims and unverified VERTU health, privacy, security, or referral capabilities.
- Moved selector and locator fields into each patch item, where Writer validation actually consumes them.
- Made BLOCK Patch Plans explicitly non-executable with empty patches by default.
- Added evidence fields to patch items and fixed the malformed forbidden-operations code fence.
- Added Skill Change Log and semantic versioning rules.

## 0.1.1 - 2026-07-10

- Added untrusted-input handling, evidence labels, restricted health terms, Patch Actions, and Sanity locator/revision safeguards.

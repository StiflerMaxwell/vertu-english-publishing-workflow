# Changelog

## 0.7.0 - 2026-08-05

Changes:

- Added a deterministic final-body safeguard for duplicate VERTU/Concierge integration sections.
- Added batch-level meaningful H2–H4 fingerprint comparison with common Sources, verdict and Related VERTU headings excluded.
- Added first-phase measurement of missing in-body evidence visuals for long buyer/comparison drafts; this remains a recommended, non-blocking warning.
- Added the safeguard source to the workspace-independent QA policy hash and `qa-handoff-v1` unresolved-finding accounting.
- Replayed the validator over 66 recent article artifacts: three duplicate-integration blockers, zero template-pair false positives and 66 body-visual warnings.

Change control:

- Old behaviour: duplicated brand-service sections and repeated batch outlines depended on manual detection, while body-visual absence was not measured.
- New behaviour: exact final bodies and batch structure receive deterministic evidence before an authorising QA PASS.
- Risk impact: closes measured editorial false negatives without making the unvalidated body-visual hypothesis a release gate.
- Decision owner: project maintainer.
- Default execution agent: Codex.
- Implementation date: 2026-08-05.

## 0.5.0 - 2026-08-04

Source governance tasks:

- `SEO-056`
- `SEO-057`

Changes:

- Added policy-aware QA identity using Sanity Doc ID, Source Rev, QA Policy Hash and Evaluation Profile.
- Added non-destructive legacy and duplicate QA identity audit states.
- Added deterministic restricted-term context routing where literal matches are recall, not verdicts.
- Added regression coverage for travel/transaction use of `treat`, affirmative medical claims and negation/disclaimer context.
- Made the policy fingerprint workspace-path independent and expanded it to cover the deterministic classifier source.
- Made affirmative medical context outrank coincident non-medical vocabulary and unrelated earlier-clause negation.

Change control:

- Old behaviour: free-text Skill versions could hide policy/profile drift, and a literal hard-red match could still be treated as a critical verdict.
- New behaviour: policy bytes and evaluation profile define QA identity; restricted terms require an explicit context classification before a block.
- Risk impact: removes a proven false positive without weakening affirmative medical, security, privacy or product-claim vetoes.
- Decision owner: project maintainer.
- Default execution agent: Codex.
- Implementation date: 2026-08-04.

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
- Decision owner: project maintainer.
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
- Decision owner: project maintainer.
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
- Decision owner: project maintainer.
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

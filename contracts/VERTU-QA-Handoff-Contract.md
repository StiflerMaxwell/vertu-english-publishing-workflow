# VERTU Production and Independent QA Handoff Contract

Contract version: `qa-handoff-v1`

## Purpose

This is the shared source of truth between the VERTU English producer, the independent SEO publish gate, the publication executor and performance monitoring. The executors remain independent. They exchange a narrow, immutable identity envelope so a result created under one policy or revision cannot be reused under another.

## Supported compatibility

| Component | Compatible versions | Role |
| --- | --- | --- |
| Producer | `vertu-english-blog-pipeline >=3.10.0,<4.0.0` | Creates the artifact package and consumes QA results |
| QA | `vertu-seo-publish-gate >=0.6.0,<1.0.0` | Independently evaluates the exact supplied source identity |
| Handoff | `qa-handoff-v1` | Shared identity and compatibility envelope |

Component versions are intentionally independent. Matching version numbers are not required; a compatible handoff contract and exact policy identity are required.

Current verified pair after the 2026-08-05 stability release: producer `3.11.0`, QA `0.7.0`, handoff `qa-handoff-v1`. Older versions inside the compatible ranges remain valid only for their exact historical policy and source identity.

## Required identity

Every new handoff records:

- `publication_run_id`, `article_key`, canonical URL, non-News section, language and markets;
- producer Skill ID and version;
- `draft_bundle_sha256` over the reviewed `article.md`, `seo.json`, `claim-ledger.json`, `link-plan.json`, `evidence-pack.md`, `product-context.json` and `editorial-changes.md`, with explicit absent statuses where the production contract permits absence;
- source identity type and exact Sanity document/revision when present;
- immutable QA Run ID and canonical Base QA record ID;
- QA policy ID, version, workspace-independent hash and evaluation profile;
- verdict, score, patch action, critical veto, unresolved critical/required counts and `qa_result_fingerprint`;
- release-gate role and computed compatibility status.

## Release-gate roles

| Role | Source identity | Meaning |
| --- | --- | --- |
| `preflight` | `artifact_bundle` | Independent QA of the exact local package before image or CMS work |
| `prepublish` | `sanity_draft_revision` | Independent QA of the exact Sanity Draft revision before publication |
| `postpublish_audit` | `published_revision` | Exact published-revision reconciliation after live verification |

For a new automatic production run, `preflight` and `prepublish` must be `PASS`, compatible, `no_patch_needed`, free of critical vetoes and free of unresolved critical/required findings. `postpublish_audit` must reconcile the exact published revision before the full automation chain can report success.

## Compatibility states

- `COMPATIBLE`: every required identity and gate condition matches.
- `LEGACY_UNVERIFIED`: historical evidence whose exact handoff identity cannot be proven; read-only observation only.
- `VERSION_MISMATCH`: producer, QA or contract version is outside the supported matrix.
- `ARTIFACT_MISMATCH`: the reviewed draft-bundle fingerprint differs.
- `REVISION_MISMATCH`: Sanity document or revision differs.
- `TRACKING_INCOMPLETE`: a required run, record, policy, result or finding field is absent.

Only `COMPATIBLE` may authorise a new production mutation. Historical `LEGACY_UNVERIFIED` evidence is never rewritten into a current PASS and cannot create a learned prior or waive a gate.

## Canonical Base fields

New QA Runs persist:

- `QA Handoff Contract Version`
- `Producer Skill ID`
- `Producer Skill Version`
- `Publication Run ID`
- `Article Key`
- `Draft Bundle SHA256`
- `Source Identity Type`
- `Release Gate Role`
- `Compatibility Status`
- `QA Result Fingerprint`

The immutable QA decision remains in the same QA Run. A new revision or policy hash creates a new QA Run.

## Monitoring rule

Monitoring resolves the QA Run ID explicitly bound by the publication handoff and verifies its document, revision and PASS state. It may recognise a single exact legacy revision for read-only historical linkage, but it may not pick the latest PASS from multiple candidates and may not treat legacy linkage as current release authority.

## Failure handling

- Fail new publication closed on any non-compatible status.
- Do not retry a production mutation to repair a handoff mismatch.
- Preserve local evidence and canonical Base rows.
- Use `HANDOFF_INCOMPLETE` when postpublication QA/Base reconciliation is missing.
- Fix the identity or create a fresh QA Run; never edit an old verdict to fit a new revision.

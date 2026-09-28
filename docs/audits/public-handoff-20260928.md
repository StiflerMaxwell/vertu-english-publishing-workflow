# Public handoff validation — 2026-09-28

## Public scope

This release is a separately sanitised 3.20.0 producer / 0.8.0 QA reference
package. It adds Chinese creator onboarding, a submission template and an
inactive daily-five draft example. It does not inherit deployment credentials,
approvals, author IDs, internal addresses, analytics, run state or private history.

## Verification performed before the first public branch commit

- 290 Python tests passed, including clean-home package QA and missing-config
  diagnostic handoff tests.
- Four notification tests passed with synthetic configuration; preview does not
  send, missing credentials fail, and the transport is not called without a secret.
- All 22 Python runtime CLI help checks and Python compilation passed.
- All 65 checked relative onboarding and producer reference links resolved.
- Eight QA runtime safeguard probes passed with authorises_release=false.
- Public bundle scan passed across all candidate Git files. The scanner covers
  private hosts, machine paths, deployed author references, opaque resource IDs,
  secret shapes and sensitive configuration fields, and prints no matched values.
- A separate local source-ID comparison found zero occurrences of the ten
  identified opaque resource IDs. No source identifier list is included here.
- Frozen pnpm installation passed; package fingerprints are recomputed for the
  sanitised bytes, not reused from any deployment.
- Non-EOF whitespace checks passed; upstream trailing blank lines are preserved.

## Packaging adaptations

QA resolves the public package's five sources and computes a new policy hash.
The LLM diagnostic emits null Base targets and MISSING_CONFIGURATION unless an
authorised adapter supplies its own mapping; even then authorises_write=false.
Normal schema and Google metric names are retained, not treated as resource IDs.
Historical source quantity wording is explicitly overridden by the public
daily-five example, with every normal quality and safety gate unchanged.

## Limits

No live CMS, analytics, Feishu or production scheduler readiness is asserted.
No production article, message or access permission was changed. GitHub CI and
remote default-branch status are evidenced by the release PR, not inferred from
these local checks. Earlier public Git history is unchanged; current-tree
sanitisation does not erase old commits, third-party forks or cached copies.

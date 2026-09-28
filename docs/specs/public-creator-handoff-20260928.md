# Public creator handoff release

## User-requested scope

Publish a separately sanitised edition of the current content-production
workflow for creator handover. The public repository remains a reusable
reference package, never a mirror of the private deployment or its history.
The existing private repository and its private-distribution gate are unchanged.

## Included behaviour

- Current producer 3.20.0 and independent QA 0.8.0 reusable policies and tools.
- Chinese creator SOP, submission template, five-article quality-first example.
- Local package QA with fresh policy hashes and no inherited release authority.
- Draft-only, inactive scheduler template and environment-only integration
  configuration. Missing configuration must fail before any external write.

## Exclusions / transformations

Remove credentials, internal hosts/URLs, tenant and object identifiers, deployed
author IDs, user-home paths, scheduler instances, run records, analytics exports,
employee evaluations and private release history. Replace configuration with
documented placeholders, not concealed HTML or comments. Keep public licensing,
attribution, quality gates and failure handling. Do not copy private Git history.

## Acceptance

- Tests pass with no private local installation or live credentials.
- Release scanner covers tracked files and rejects secret/identifier patterns,
  private artifacts and populated configuration.
- No private object identifier from the source appears in the new public tree
  or the new branch commits; audit output includes paths/counts only.
- Relative onboarding links, CLI usage, Python compilation and hashes pass.
- GitHub CI passes, public main is read back, and anonymous access succeeds.
- Publication, CMS changes, live scheduler changes and history rewriting are
  outside this release.

## Failure / rollback

Do not commit or push until sanitisation checks pass. Uncertain content is
excluded, not published for later cleanup. Revert the public release commit to
roll back documentation/tools; it does not affect running production systems.
If old public history contains internal identifiers, disclose the remaining
history limitation separately rather than claiming it was erased.

OpenSpec CLI is unavailable; this uses the existing docs/specs structure and
does not claim OpenSpec CLI validation.

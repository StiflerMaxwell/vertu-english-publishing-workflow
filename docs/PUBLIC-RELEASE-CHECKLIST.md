# Public release checklist

This checklist defines the acceptance boundary for publishing the repository
as open source.

Current release: public sanitised producer 3.20.0 / QA 0.8.0, with Chinese
creator handoff and a daily-five draft-only example. Run these checks on each
new release; previous checkmarks are not evidence for a changed tree.

## Required

- [x] Apache License 2.0 and trademark notice are present.
- [x] README describes the repository as open source and links contribution,
      security and architecture documentation.
- [x] Production credentials, tenant tokens, table/view/field identifiers,
      bot application IDs, channel IDs and private object URLs are absent.
- [x] Runtime integrations fail closed when required configuration is missing.
- [x] Example configuration uses environment-variable placeholders only.
- [x] Python tests, bundle validation and whitespace checks pass.
- [x] GitHub default branch contains the validated release tree.
- [x] Repository visibility is `PUBLIC` and can be read without authentication.

## Current release checks

```bash
python3 -m pytest scripts/tests skills/vertu-seo-publish-gate/tests --import-mode=importlib
python3 scripts/validate_bundle.py
pnpm test:notification
shasum -a 256 -c MANIFEST.sha256
```

The validator checks all Git release candidates, including new untracked files,
for private paths/hosts, quoted opaque resource identifiers, deployed author
references, secret patterns, private distribution artifacts and populated
example credentials. It never prints matched values. The private source-to-public
comparison is performed locally and must not upload the private identifier list.

Sanitisation removes values from file contents, not merely from visibility or
`.gitignore`. The public tree has its own manifest and fresh QA policy hash; it
must never claim byte identity with a private deployment.

This release updates the current tree only. It does not rewrite earlier Git
history or remove third-party clones/caches. Historical internal resource
references are not authentication credentials, but their removal from history
would require a separate coordinated maintenance operation.

## Non-goals

The release does not publish production data, generated articles, analytics
exports, CMS mutation adapters, private author registries or deployment
credentials. Installing the repository does not grant production authority.

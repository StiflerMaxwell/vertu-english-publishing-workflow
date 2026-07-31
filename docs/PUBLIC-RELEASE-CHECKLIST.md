# Public release checklist

This checklist defines the acceptance boundary for publishing the repository
as open source.

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

## Non-goals

The release does not publish production data, generated articles, analytics
exports, CMS mutation adapters, private author registries or deployment
credentials. Installing the repository does not grant production authority.

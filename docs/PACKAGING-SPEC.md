# Packaging specification

## Goal

Create an open-source, portable and auditable repository for the reusable
VERTU English publishing workflow without copying production credentials,
tenant identifiers, private run artifacts or machine-specific session state.

## Included

- canonical editorial Skill v3.14.0 and every active reference;
- independent SEO QA Skill v0.7.1 and its tracking contract;
- deterministic demand scoring, realtime Trends, monitoring handoff,
  QA-identity, daily quota, local loop runtime, Skill scorecard and
  learning-flywheel scripts;
- script unit tests;
- sanitised `vertu-10` automation template;
- chain, monitoring and vvv receipt contracts;
- canonical Base schema-map example;
- installation, operations and security documentation.

## Excluded

- `.env`, service-account JSON, tokens, cookies and Keychain values;
- production Base/table/view/field IDs, bot/channel IDs and private object URLs;
- generated article drafts, hero images, evidence packs and run summaries;
- machine-specific Codex thread IDs and scheduler timestamps;
- historical Skill references that point to legacy local authentication files;
- per-run Sanity executors containing hard-coded run IDs or document sets;
- proprietary external platform implementations such as Codex Image Gen,
  Sanity, Feishu, GSC, GA4 and Google Ads.

Publication executors are deliberately run-scoped. They must be generated from
the current schema and approved document set, then discarded or preserved only
as immutable run evidence. A reusable static publisher would weaken the
revision and schema safety contract.

## Acceptance checks

- all packaged Python test suites pass;
- all packaged CLI entry points return usage successfully;
- no machine-specific user-home path remains;
- no known secret-value pattern is present;
- no production tenant or notification identifier pattern is present;
- the automation template contains no thread ID or instance timestamps;
- the active reference index resolves to packaged files;
- the repository is public on GitHub;
- the remote default branch contains the validated commit.

## Rollback

No production system reads directly from this package until it is explicitly
installed. Roll back an installation by restoring the previous installed Skill
directory and automation template from its local backup.

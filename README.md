# VERTU English Publishing Workflow

Open-source, auditable packaging of the VERTU English content workflow.

This repository contains the reusable workflow definition, deterministic traffic
and learning tools, independent SEO QA gate, automation template, monitoring
contracts, and notification sender used by the VERTU publishing chain.

Current packaged versions:

- editorial pipeline: `vertu-english-blog-pipeline` v3.14.0
- independent SEO QA gate: `vertu-seo-publish-gate` v0.7.1
- automation profile: `vertu-10`, daily at 09:00 Asia/Hong_Kong

The repository is designed as a reference implementation. It contains no
production tenant identifiers, credentials, analytics exports or CMS mutation
authority. Operators must supply their own integrations and configuration.

## What the workflow does

```text
GSC + Google Trends + editorial intelligence + live inventory
  -> acquire bounded local loop mutation scopes
  -> qualify demand by independent acquisition-system family
  -> require a minimum candidate-level GSC sample
  -> score at least 30 candidates
  -> select only demand-qualified topics
  -> research and write original articles
  -> independent SEO QA
  -> Discover readiness
  -> Codex Image Gen
  -> run-scoped Sanity preview and publication
  -> live-page verification
  -> canonical Feishu Base handoff
  -> vvv group receipt
  -> 24h / 72h / 7d / 28d monitoring
  -> governed performance-learning priors
  -> loop-health audit and owner-checked scope release
  -> paired review + replay + mature production scorecard
```

The editorial Skill does not self-approve. QA, image generation, production
mutation, live verification, and monitoring remain separate gates.

## Repository map

- `skills/vertu-english-blog-pipeline/` — topic selection, demand scoring,
  research, writing, evidence, links, authorship and handoff contracts.
- `skills/vertu-seo-publish-gate/` — independent PASS/FIX/BLOCK QA contract.
- `scripts/` — deterministic traffic scorer, Google Trends collector, governed
  learning flywheel, quota/runtime guards and vvv notification sender.
- `automation/vertu-10.template.toml` — sanitised scheduler template.
- `contracts/` — automation-chain, performance-monitoring and group-receipt
  contracts.
- `config/performance-monitor-base.example.json` — canonical Base schema map.
- `templates/github-actions/package-ci.yml` — optional package CI workflow.
- `docs/` — installation, architecture, operations and release scope.

Architecture and governance:

- [Feishu governance and self-evolving Skills](docs/FEISHU-MAINTENANCE-AND-SKILL-EVOLUTION.md)
- [Loop Engineering review and VERTU adaptation](docs/LOOP-ENGINEERING-REVIEW.md)
- [Public release checklist](docs/PUBLIC-RELEASE-CHECKLIST.md)

## Safety boundaries

- Automatic content must never use the `news` section or a `/news/` URL.
- Ten articles remains a ceiling for ordinary profiles. The named `vertu-10`
  profile is the explicit exception: it requires ten fully live-verified,
  handed-off articles through bounded 30/60/90/120 candidate expansion without
  lowering any editorial or publication gate.
- Protected pointer, Base, Sanity and Skill-release mutations require a local
  runtime `ALLOW` receipt plus the normal canonical Base start ledger. Pause,
  collision, budget, attempt, state and release failures remain explicit.
- A production mutation requires a successful start-audit record, exact
  run-scoped document IDs, fresh schema/revision checks and a mutation preview.
- Published success requires HTTP 200, exact canonical, linked institutional
  byline, matching schema author, verified image and rendered-link reconciliation.
- Missing Feishu handoff is `HANDOFF_INCOMPLETE`, never silent success.
- Missing or delayed analytics is `DATA_NOT_MATURE` or `SOURCE_BLOCKED`, never
  zero.
- Candidate GSC can support positive demand only when its newest finalised
  window has at least 3 clicks or 100 impressions; smaller samples remain
  visible but do not satisfy provider independence.
- Duplicate brand/concierge integration sections and materially repeated batch
  outlines are QA blockers. Missing in-body evidence visuals are warning-only
  until a controlled experiment validates a hard gate.
- Checkpoint history remains immutable while lifecycle metadata identifies one
  current observation per logical article/checkpoint key.
- Secrets are resolved at runtime only. This repository contains no secret
  values or production output artifacts.

## Quick start

See [Installation](docs/INSTALL.md), then run:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 scripts/validate_bundle.py
python3 scripts/vertu_content_loop_runtime.py --help
pnpm install
pnpm notify:preview -- --body-file ./path/to/message.txt
```

The notification preview does not send a group message.

## Contributing and security

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a change.
- Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) in project spaces.
- Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Licence and trademarks

The code and documentation are available under the
[Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution and
trademark boundaries. The licence does not grant rights to VERTU trademarks,
brand assets, production credentials or private data.

## Release integrity

`MANIFEST.sha256` is generated from tracked package files before release. Re-run
the bundle validator after any Skill, contract, script, or automation change.

Package metadata keeps `private: true` only to prevent accidental publication
to the npm registry; it does not change the Apache-2.0 repository licence.

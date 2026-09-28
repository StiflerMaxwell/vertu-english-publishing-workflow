# VERTU English Publishing Workflow

## 内容创作交接入口（2026-09-28）

**先读 [中文创作与交付 SOP](docs/CONTENT-CREATOR-HANDOFF.zh-CN.md)，再复制 [单篇交稿模板](templates/creator-submission.md)。**

本仓库公开可读。完整覆盖选题、查证、英文写作、独立编辑/QA、配图、
授权发布验收与复盘。创作者可先交稿，不需要生产凭据。

- [每日 5 篇、质量优先示例配置](docs/CURRENT-OPERATING-PROFILE.md)
- [管理员安装和权限配置](docs/INSTALL.md)
- [脱敏范围和发布验收](docs/PUBLIC-RELEASE-CHECKLIST.md)

这是独立脱敏的公开参考包，不是内部运行环境的镜像。原始业务资料、
内部地址、资源 ID、运行记录和凭据均不随包提供；替换配置后仍须重新验证权限与门禁。

Open-source, auditable packaging of the VERTU English content workflow.

This repository contains the reusable workflow definition, deterministic traffic
and learning tools, independent SEO QA gate, automation template, monitoring
contracts, and notification sender used by the VERTU publishing chain.

Current packaged versions:

- editorial pipeline: `vertu-english-blog-pipeline` v3.20.0 (sanitised edition)
- independent SEO QA gate: `vertu-seo-publish-gate` v0.8.0 (package-local identity)
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
  -> exact-query SERP benchmark and original-value brief
  -> research and write original articles
  -> independent substantive editor, then independent SEO QA
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
- The current example targets five quality articles per day; manual recovery
  counts toward the same daily cap. The template remains inactive and draft-only.
  See [profile precedence](docs/CURRENT-OPERATING-PROFILE.md) for historical
  ten-count wording retained in upstream contracts. No quota can weaken a gate.
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
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
python3 -m pytest scripts/tests skills/vertu-seo-publish-gate/tests --import-mode=importlib
python3 scripts/validate_bundle.py
python3 scripts/vertu_content_loop_runtime.py --help
pnpm install
pnpm test:notification
```

Notification tests use synthetic configuration and make no external request.
The real notifier requires your own configuration even for preview.

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

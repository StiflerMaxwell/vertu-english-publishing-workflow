# Installation

Creators start with the [Chinese SOP](CONTENT-CREATOR-HANDOFF.zh-CN.md) and
submit drafts through their team's authorised channel. The administrator setup
below is not required merely to read the guide or write an article.

## Requirements

- Python 3.11 or newer (3.12 recommended);
- Node.js 20 or newer;
- pnpm 11;
- authenticated access to the required Sanity, Feishu, GSC and GA4 systems;
- Codex with Image Gen for production hero generation;
- the target project's production publication adapter.

## Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
pnpm install
python3 -m pytest scripts/tests skills/vertu-seo-publish-gate/tests --import-mode=importlib
python3 scripts/validate_bundle.py
pnpm test:notification
```

These are offline package checks. They do not prove live integration access.

## Set the project root

```bash
export VERTU_PDCA_ROOT=/absolute/path/to/vertu-pdca
```

Copy `.env.example` to a local secret-management workflow. Do not create or
commit a populated `.env` inside this repository.

Every Feishu Base/table/view ID and every notification app/channel/endpoint is
deployment-specific. Supply them through environment variables or a generated
local configuration file that remains untracked.

Documentation uses `${VERTU_PDCA_ROOT}`, `${HOME}`, `${FEISHU_RESOURCE_URL}`
and `${AUTHOR_*_ID}` as placeholders. Configure actual paths and resources before
execution; Markdown/JSON placeholders do not expand themselves. The packaged
contracts live under `contracts/`, while a deployed PDCA checkout may use
`docs/03-运行/`. Map these explicitly without inventing missing source files.
QA uses package-local sources when `.public-workflow-package` is present and
computes a fresh hash. Do not reuse a production or another package's QA PASS.
Outside this package, inspect the installed QA source paths before enabling it.

The LLM diagnostic CLI emits an unconfigured, non-authorising Base handoff.
An authorised adapter may call `build_base_handoff_row(..., integration_config=...)`
with `base_token`, `checkpoint_table_id` and `article_table_id` from its own
protected configuration. Missing or literal placeholders produce null targets
and MISSING_CONFIGURATION; even configured output does not authorise a write.

## Install the Skills

Hermes editorial Skill:

```bash
mkdir -p "${HOME}/.hermes/skills/content"
cp -R skills/vertu-english-blog-pipeline \
  "${HOME}/.hermes/skills/content/vertu-english-blog-pipeline"
```

Independent QA Skill:

```bash
mkdir -p "${HOME}/.openclaw/workspace/skills"
cp -R skills/vertu-seo-publish-gate \
  "${HOME}/.openclaw/workspace/skills/vertu-seo-publish-gate"
```

Back up an existing installed directory before replacing it. Installation does
not grant production authority.

## Install the automation

Read [profile precedence](CURRENT-OPERATING-PROFILE.md). Leave the supplied
template INACTIVE and draft-only until all administrator readiness checks pass.

Copy `automation/vertu-10.template.toml` to the scheduler's automation
directory, then verify:

- `VERTU_PDCA_ROOT` and scheduler working directory;
- the canonical Base schema map;
- the standing approval profile, if any;
- the vvv app ID, channel ID and HTTPS endpoint;
- the automation time zone and recurrence;
- the production adapter's live preview contract.

Do not add a Codex thread ID to the repository template.

## Optional GitHub Actions CI

The package includes `templates/github-actions/package-ci.yml`. Copy it to
`.github/workflows/package-ci.yml` using a GitHub credential authorised to
manage Actions workflow files.

## Runtime credentials

Use environment variables or a platform secret store. On macOS, the vvv secret
may be stored in Keychain:

```bash
security add-generic-password \
  -s vertu-vvv-user-robot \
  -a "${VERTU_VVV_APP_ID}" \
  -w
```

The command prompts for the value and does not place it on the command line.

Google metric collection additionally needs `google-analytics-data`,
`google-api-python-client` and `google-auth` installed in the operator's runtime;
these live integrations are optional and are not needed for offline unit tests.

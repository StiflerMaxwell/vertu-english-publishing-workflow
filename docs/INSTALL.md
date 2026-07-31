# Installation

## Requirements

- Python 3.10 or newer;
- Node.js 20 or newer;
- pnpm 11;
- authenticated access to the required Sanity, Feishu, GSC and GA4 systems;
- Codex with Image Gen for production hero generation;
- the target project's production publication adapter.

## Install dependencies

```bash
pnpm install
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 scripts/validate_bundle.py
```

## Set the project root

```bash
export VERTU_PDCA_ROOT=/absolute/path/to/vertu-pdca
```

Copy `.env.example` to a local secret-management workflow. Do not create or
commit a populated `.env` inside this repository.

Every Feishu Base/table/view ID and every notification app/channel/endpoint is
deployment-specific. Supply them through environment variables or a generated
local configuration file that remains untracked.

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

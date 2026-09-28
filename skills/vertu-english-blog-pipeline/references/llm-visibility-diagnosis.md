# Post-publication LLM Visibility Diagnosis

Contract: `llm-visibility-diagnosis-v1`

## Purpose and position

This is a post-publication feedback diagnostic. Run it only after HTTP/live verification and canonical Base handoff. It does not participate in candidate scoring, writing authority, QA PASS or publication.

The first phase is read-only. It may create an observation or a governed experiment proposal, but it may not mutate Sanity, activate a prior or change the Skill.

## Observation panel

A dedicated diagnostic agent or connector supplies normalised observations. Preserve for every row:

- provider, model and model version;
- prompt ID and market;
- observation time and source status;
- citation URLs only, without raw private response text;
- whether VERTU was mentioned.

Also preserve live crawl/indexability proxies: HTTP status, robots access, noindex and canonical match. These proxies do not prove inclusion in a model index.

Run:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_llm_visibility_diagnose.py \
  --input <normalised-llm-panel.json> \
  --output-dir performance/<slug>/llm/<checkpoint>/ \
  --base-handoff-output performance/<slug>/llm/<checkpoint>/base-handoff-row.json
```

## Outputs

- `crawl-access.json`
- `llm-citation-observations.json`
- `llm-visibility-diagnosis.json`
- `base-handoff-row.json` (`llm-visibility-base-handoff-v1`)

Record model coverage, prompt coverage, market coverage, citation rate, exact-canonical citation rate, brand-mention rate, prompt variance and immutable fingerprints.

## States

- `CITATION_OBSERVED`
- `NO_CITATION_OBSERVED`
- `CRAWL_BLOCKED`
- `INDEXABILITY_PROXY_PASS`
- `PROMPT_VARIANCE_HIGH`
- `SOURCE_UNAVAILABLE`

One missing citation never means “not indexed”. A model response is prompt-, model-, market- and time-specific. Preserve nulls and source blockers instead of manufacturing zeros.

## Checkpoints and action boundary

- T+24h: crawl, canonical and technical proxy only; model panel is optional and preliminary.
- T+72h: first standard model/prompt panel.
- D+7: repeat the same panel for controlled comparison.
- D+28: mature comparison eligible for a governed experiment proposal.

Repeated stable evidence may create a `GEO Visibility`, `Citation Coverage` or `Crawler Access` Finding. Only a predeclared experiment with mature evidence may flow into Skill evolution. No direct repair or score effect is allowed in v3.18.0.

The dedicated automation ID is `vertu-llm`. It runs once daily and processes only due T+72h, D+7 and D+28 checkpoints. The handoff payload is upserted by deterministic `复盘ID`; the diagnostic script itself does not write Base.

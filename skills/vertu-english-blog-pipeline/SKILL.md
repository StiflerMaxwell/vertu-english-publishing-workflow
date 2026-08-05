---
name: vertu-english-blog-pipeline
description: Research, demand-score, select, and write original English VERTU Signals articles for vertu.com. Prioritises evidence-backed premium, business, collector and executive decisions with broad reader demand, using candidate-level GSC and trend evidence, the live Feishu product knowledge base, VERTU editorial voice, and automation-safe handoffs. QA, Image Gen, and publishing are separate downstream capabilities.
---

# VERTU English Blog Pipeline

Current contract version: `3.11.0`.

This is the canonical Discover-first workflow for selecting and writing original English VERTU Signals articles. Its business outcome is qualified organic traffic from Google Discover and Search, with relevant VERTU discovery and product journeys as downstream value.

```text
Read candidate-level Discover and Search demand
→ find a topic VERTU has the right to discuss
→ build an evidence-backed original angle
→ write a substantial, visual, useful article in VERTU Signals voice
→ pass editorial QA and a separate Discover readiness gate
→ hand the draft to Image Gen and publishing stages
```

## Ownership and boundaries

This skill owns:

- source discovery and candidate collection;
- topic scoring and selection;
- search-intent, content-gap, and cannibalisation checks;
- rolling GSC Discover/Search baselines and topic-cluster performance evidence;
- research, source validation, and evidence packs;
- retrieval of approved VERTU product knowledge;
- outlining, drafting, SEO metadata, links, and claim ledgers;
- automation-safe artifacts and handoffs.

This skill does **not** own:

- the QA rubric or QA scoring logic;
- image model configuration or image API credentials;
- Sanity schema definitions;
- production publishing authority;
- site-wide technical SEO fixes outside the article and publication workflow.

Downstream capabilities remain separate:

- **QA:** configured article QA skill. The current default is `~/.openclaw/workspace/skills/vertu-seo-publish-gate/SKILL.md`. Do not copy its rubric into this skill.
- **Image:** Codex `image_gen`. Do not call MiniMax, legacy image HTTP endpoints, or a silent fallback provider.
- **Publishing:** Sanity draft/publish operation after fresh schema introspection and explicit authority.

The shared identity boundary is `${VERTU_PDCA_ROOT}/contracts/VERTU-QA-Handoff-Contract.md` (`qa-handoff-v1`). Production and QA keep independent versions and responsibilities, but every new production transition must validate the same producer version, draft-bundle fingerprint, QA policy hash/profile, immutable QA Run ID and exact Sanity revision where present.

## Outcome hierarchy

1. Help a real VERTU-relevant reader make a decision or understand a timely change.
2. Build on VERTU's demonstrated audience fit in premium travel, executive technology and privacy, watches and collecting, and familiar luxury purchase decisions.
3. Earn Discover recommendation potential through timeliness, story, originality, and compelling imagery.
4. Capture durable non-brand Search demand through clear intent satisfaction.
5. Lead qualified readers towards relevant VERTU products, services, or brand authority without forced promotion.

Traffic is the measurement outcome, not permission to mass-produce search-engine-first content. Google people-first and spam policies remain hard constraints.

## Safety defaults

Unless the run input explicitly says otherwise:

```yaml
mode: auto_discovery
language: en-GB
max_articles: 10
minimum_articles: 0
target_outcome: discover_and_search
delivery: local_draft
approval_required: true
production_publish: false
```

Hard rules:

1. Never publish to production merely because an article is complete.
2. Never create a Sanity mutation before the configured QA skill returns `PASS`.
3. `FIX` returns to writing. `BLOCK` stops the run.
4. Never infer product specifications, prices, availability, materials, capabilities, medical claims, security guarantees, or release dates.
5. Never force a VERTU product into an unrelated topic.
6. Never create multiple articles from near-identical search intent in the same run.
7. Scheduled automation defaults to a reviewable draft, not autonomous publication.
8. `max_articles` is a ceiling, not a quota. Never fill a batch with low-potential content.
9. A batch must pass portfolio diversity checks; do not publish ten adjacent AI/privacy/governance articles.
10. Editorial QA `PASS` is necessary but not sufficient. The article must also be `DISCOVER_READY`.
11. Reserve `/news/` for first-party VERTU announcements, company statements, verified VERTU product launches, events, and media-safe corporate updates. Third-party technology events and competitor announcements must be framed as independent editorial analysis and routed to `/ai-tools/`, `/guides/`, or `/lifestyle/`.
12. Authorship is expertise-first and transparent. Never invent individual people or credentials; use the approved institutional editorial desks in `references/author-policy.md`.
13. Never accept a hand-authored final topic score. Calculate it with the active deterministic traffic gate and preserve the full score breakdown, provider-family qualification and raw source metrics.
14. Search-first selection requires two independent positive demand signals. Discover-first selection requires current-interest evidence, historical VERTU cluster evidence, and a concrete visual story.
15. Never describe a topic as hot or real-time from GSC, Keyword Planner, social engagement, or editorial feeds alone. Apply `references/realtime-trends.md` and require verified official Google Trends evidence for `REALTIME_HOT`.
16. Before broad candidate generation, consume the same-day Hermes intelligence chain defined in `references/editorial-intelligence.md`. Treat it as mandatory discovery and breakout evidence, not as Google search-volume evidence.
17. A verified `EDITORIAL_BREAKOUT` may qualify a Discover-first candidate even when Google Trends has not surfaced it, but the article must retain a truthful Google trend class and must never be called `REALTIME_HOT` without official Google evidence.
18. Read both governed performance-learning snapshots before candidate scoring. Recent repeated mature 72h/7d evidence may create an expiring provisional prior; durable D+28 or verified-experiment evidence may create a durable prior. Both may reorder only already eligible candidates.
19. A learned prior may never change raw eligibility, waive a veto, create a demand provider, create `REALTIME_HOT`, or make the combined provisional-plus-durable adjustment exceed three portfolio-priority points.
20. Planned checkpoint files, `DATA_NOT_MATURE`, `SOURCE_BLOCKED`, null future checkpoints and unverified prose summaries are not learning evidence.
21. Run a read-only daily performance pulse for the rolling 35-day published cohort even when no milestone checkpoint is due. A quiet daily pulse is evidence, not an empty run.
22. Run the governed review and Skill release check twice daily. Fast 24h/72h signals may create observations or manual experiment candidates, but only mature evidence may promote a rule. Version only material, tested and replay-safe changes; when evidence is insufficient, record `NO_PROMOTION` and `NO_SKILL_CHANGE` and preserve the current version.
23. Apply the user-approved premium/business decision strategy during candidate generation and portfolio framing. Classify serious candidates as `PREMIUM_DECISION_CORE | ADJACENT | EXPLORATION_CANDIDATE`; only a normally eligible controlled test becomes `EXPLORATION`.
24. `Luxury`, `high-end`, `business`, price, celebrity ownership or exclusivity are not demand providers. Generic luxury lists and narrow affluent services still require normal demand evidence and may not receive eligibility, trend labels or veto relief from the audience-fit classification.
25. New production runs require a `COMPATIBLE` `qa-handoff-v1`. `LEGACY_UNVERIFIED`, version, artifact, revision or tracking mismatch evidence may be observed historically but may not authorise a new mutation.
26. Count Search demand by independent acquisition-system family, not by provider label. GSC, official Google Trends and Google Ads Keyword Planner are separate families; aliases or derived views of the same upstream dataset count once.
27. A positive candidate-level GSC signal counts for demand only when the newest available finalised window has at least three clicks or at least 100 impressions. Preserve smaller samples as `AVAILABLE/INSUFFICIENT_SAMPLE`; never convert them to zero or fall back to an older window merely to pass the gate.
28. Before QA handoff, a final article may contain at most one VERTU/Concierge integration section. Independent QA must also compare meaningful final heading fingerprints across the batch. Duplicate integration or template-dependent structure is a required fix; missing in-body evidence visuals remain a measured, non-blocking warning during the first phase.

## Run modes

| Mode | Use | Default result |
|---|---|---|
| `manual_topic` | User provides a topic, keyword, source, or thesis | Validate and write one draft |
| `auto_discovery` | Scheduled or requested topic discovery | Build a performance-informed portfolio and write up to the approved maximum |
| `revision` | Revise an existing draft from feedback | Updated draft plus change log |
| `publish_approved` | Publish an explicitly approved, current `PASS` draft | Sanity mutation plus verification |

`publish_approved` requires an explicit approval reference, the latest QA report, the exact document/slug, and a fresh `_rev` or equivalent conflict check.

## Run input

Accept a partial input contract and apply the safety defaults:

```yaml
mode: manual_topic | auto_discovery | revision | publish_approved
topic: optional string
primary_keyword: optional string
source_urls: optional list
source_window_hours: 72
target_section: ai-tools
language: en-GB
max_articles: 10
minimum_articles: 0
target_outcome: discover_and_search
trend_mode: balanced | realtime_hot | evergreen
trend_markets: [US, GB, AU, CA, AE, SA, SG, HK, IN]
delivery: local_draft | sanity_draft | production
approval_required: true
approval_reference: optional string
notification_target: codex | vvv_channel_and_codex | feishu | none
```

Choose safe defaults for missing polish fields. Stop only when a missing field changes publication authority, regulated claims, or the selected topic.

## Pipeline

### Stage 0 — Run manifest

Create:

```text
${VERTU_PDCA_ROOT}/output/vertu-signals/YYYY-MM-DD/<slug-or-run-id>/
```

Write `run.json` first. Record mode, wall-clock timestamp, source window, delivery, approval state, and an idempotency key. The key should include UTC date, selected slug, and a hash of the source set. Retries resume the same run.

### Stage 1 — Performance baseline and topic discovery

Read [references/topic-selection.md](references/topic-selection.md) completely.
Read [references/traffic-demand-gate.md](references/traffic-demand-gate.md) completely.
Read [references/realtime-trends.md](references/realtime-trends.md) completely.
Read [references/editorial-intelligence.md](references/editorial-intelligence.md) completely.
Read [references/performance-learning.md](references/performance-learning.md) completely.
Read [references/skill-evolution-scorecard.md](references/skill-evolution-scorecard.md) completely when evaluating or releasing a Skill/process change.

Before discovering topics, query finalised GSC data for the previous 365 days when access is available: Discover and Search page performance, top topic clusters, title/intent patterns, recent 28-day changes, and high-impression low-CTR opportunities. Store `discover-baseline.json`. Never expose credentials. If unavailable, mark `PERFORMANCE_BASELINE_UNAVAILABLE`.

Before broad candidate creation, locate and read the latest successful same-day Hermes RSS intelligence run and the downstream editorial synthesis. Write `editorial-intelligence.json` and `source-velocity.json`. If the expected runs are absent or stale, record `EDITORIAL_INTELLIGENCE_UNAVAILABLE`; do not silently continue as though the feed was checked.

Inputs may include the performance baseline, a user topic, the mandatory Hermes intelligence chain, the latest Cipher feed, official announcements, primary documentation, research papers, current GSC/GA4 evidence, and the existing VERTU article inventory.

Read `${VERTU_PDCA_ROOT}/output/vertu-signals/learning/active-performance-priors.json` when present. Verify its `performance-learning-v1` contract and fingerprint. Record its fingerprint and active-prior count in `run.json` and `traffic-demand.json`. If absent or invalid, use `LEARNING_PRIORS_UNAVAILABLE`; do not reconstruct active rules from prose.

Also read `${VERTU_PDCA_ROOT}/output/vertu-signals/learning/provisional-performance-priors.json` when present. Verify its `performance-learning-provisional-v1` contract, fingerprint, activation and expiry. Record its fingerprint, active count and ignored expired count. If absent or invalid, use `PROVISIONAL_LEARNING_PRIORS_UNAVAILABLE`; never refresh or recreate a provisional prior from prose.

Apply the standing user-approved editorial strategy separately from governed learned priors. Prioritise mass-recognisable premium decisions in commercial-airline cabins and airport services, executive phones/privacy/business technology, watches/collecting/craft, and familiar luxury purchases when they also have a concrete choice and normal demand evidence. Record `audience_fit_lane`, `mass_recognisability`, `decision_intent`, `historical_cluster_evidence`, and `niche_risk` in `cluster-support.json`, `traffic-demand.json`, and each topic brief. Do not generalise commercial-airline success to private aviation, yachts, ultra-niche services or generic luxury. Historical cluster adjacency may score audience fit but is a Search-demand provider only when finalised candidate-level GSC query/page evidence matches the same normalised intent. Score the underlying evidence once; the lane itself adds no points.

Before candidate creation, query finalised 28-day GSC by country and fetch Google Trends Trending Now for the configured markets. Prefer API Alpha when authorised; otherwise use the official public RSS, CSV or reproducible UI export. Pass the deterministic `publication_run_id` into the collector and write `geo-audience-baseline.json`, `realtime-trends.json`, `trend-market-map.json`, and `hotness-gate.json`. The three trend artifacts must share the run ID and snapshot fingerprint. An unavailable API is not permission to skip an accessible official public fallback.

For every serious candidate, collect candidate-level demand evidence rather than relying only on the portfolio baseline. Record GSC query/page evidence and recent change, Google Trends/current-interest evidence, Keyword Planner volume when authorised, SERP gap evidence, inventory overlap, source status, observation window, evidence reference, fetch time, target market and one of `REALTIME_HOT | RISING_SEARCH | EVERGREEN_SEARCH`. Missing sources remain `SOURCE_UNAVAILABLE`; they are never converted to zero demand.

For unstable information, browse and verify current facts. Prefer primary sources and record publication date separately from event date.

### Stage 2 — Score and select

Validate and score serious candidates with the active traffic-demand, editorial-intelligence, realtime-trends and performance-learning contracts. Calculate the final score with `${VERTU_PDCA_ROOT}/scripts/vertu_content_traffic_gate.py`; do not type a final score into a per-run script. Require `score_source=computed_v3_10_0`, retain `demand_signal_qualifications`, and reject a Search-first candidate unless at least two qualified acquisition-system families remain after GSC sample qualification and same-family deduplication. Pass `--editorial-intelligence editorial-intelligence.json --source-velocity source-velocity.json` whenever any candidate declares `EDITORIAL_BREAKOUT`. Pass `--learning-priors ${VERTU_PDCA_ROOT}/output/vertu-signals/learning/active-performance-priors.json` when the durable snapshot validates and `--provisional-learning-priors ${VERTU_PDCA_ROOT}/output/vertu-signals/learning/provisional-performance-priors.json` when the provisional snapshot validates. Use `--trend-mode realtime_hot --realtime-trends realtime-trends.json --trend-market-map trend-market-map.json --hotness-gate hotness-gate.json` when the run promises a hot portfolio so every hot query, market and metric is reconciled against the same fingerprinted run snapshot. The scorer must live-recheck the official Trends feed and primary source before accepting the hot label; source-check failure is a veto, not an invitation to reuse self-declared metadata. Learning priors apply only after normal eligibility and their combined adjustment may change portfolio ordering by at most three points. GSC or Keyword Planner may prove durable demand but cannot make an article `REALTIME_HOT`. A topic needs a passing demand verdict, a computed `80/100`, no veto, and a pre-draft `discover_forecast=PASS`; this forecast is provisional and is not the final post-draft `DISCOVER_READY` verdict. Score at least 30 viable candidates for a ten-article run. Selection is a portfolio decision, not ten independent headline decisions.

Produce `candidates.json`, `traffic-demand.json`, `portfolio-plan.json`, `cluster-support.json`, and one `topic-brief.md` per selected article. Treat the legacy content lanes as diversity guidance rather than publication quotas. When enough candidates independently pass, target roughly 50–70% `PREMIUM_DECISION_CORE` across at least three distinct clusters, 20–30% `ADJACENT`, and no more than 20% `EXPLORATION`; traffic evidence, entity/intent caps and `NO_TOPIC` override these soft targets. Target proven demand, rising interest, verified editorial breakouts, and controlled exploration without lowering the threshold. When one event supports several useful pages, use one event/opportunity page plus no more than two distinct search-intent support pages; define query boundaries and publication order before drafting. If fewer than ten pass, publish fewer than ten; do not generate filler.

### Stage 3 — Evidence pack

Research before outlining. For every source record title, URL, publisher/author, published date, event date, primary/secondary status, supported claims, uncertainties, and citation suitability.

Produce `evidence-pack.md`. Every source-needing statement in the draft must map to this file or the product context pack.

### Stage 4 — VERTU product context

Read [references/product-knowledge.md](references/product-knowledge.md) completely.

Canonical source:

`${VERTU_PRODUCT_KB_URL}`

Fetch it fresh whenever the article mentions a VERTU product, service, Hermes Agent, VPS, craftsmanship, privacy, health/wellness, price, availability, or specifications. Extract only relevant sections and live-verify volatile fields.

Produce `product-context.json` with the Feishu revision and fetch timestamp. If no product is naturally relevant, record that and do not inject one.

### Stage 5 — Argument and outline

Read [references/writing-contract.md](references/writing-contract.md) completely.
Read [references/author-policy.md](references/author-policy.md) completely.

The outline must identify dominant intent, audience-fit lane, mass-recognisable subject, concrete premium/business/collector decision when applicable, a one-sentence thesis, incremental value, evidence required by each section, VERTU's legitimate perspective, and the earned conclusion.

Produce `outline.md`. Select the author by dominant topic expertise before drafting and record the author ID and assignment reason. Do not draft until the outline forms an argument rather than a list.

### Stage 6 — Draft for depth and decision value

Use the installed `seo-content-writer` when available for intent alignment, metadata, and evidence boundaries. This VERTU-specific contract overrides generic formulas.

Produce `article.md`, `seo.json`, `claim-ledger.json`, and `link-plan.json`. Normal depth ranges are 1,000–1,500 words for timely news-to-insight, 1,200–1,800 for practical explainers, 1,600–2,600 for buyer guides/comparisons, and 2,200–3,200 for pillar/collector guides. These are editorial ranges, not Google ranking factors; shorter work may pass when complete, and padded work fails.

The link plan must implement the selected topic's cluster boundary. Record at least one relevant outbound internal destination and up to three genuinely relevant existing pages that could provide contextual inbound links. If no suitable inbound source exists, record `DISTRIBUTION_RISK`; never manufacture an unrelated link. Historical-page link mutations still require their own scoped authority.

The link plan must count unique destinations rather than anchor tags. Two anchors pointing to the same normalised URL are one source. Reader-useful authoritative PDFs count as evidence links; image assets and schema-only URLs do not. Before handoff, reconcile `evidence-pack.md`, `link-plan.json`, the final article body, and the claim ledger so approved reader-facing evidence is not lost during conversion.

Every article needs at least one article-specific value object: an evidence-backed comparison table, decision matrix, timeline, checklist, original synthesis, verified product matrix, or clearly sourced data summary. Do not append a formulaic FAQ unless real reader questions support it.

Use at most one article-specific VERTU/Concierge integration section. A second brand-service section is not additional relevance; consolidate it before QA. For long buyer/comparison articles, plan at least one descriptive in-body evidence visual such as a sourced diagram, route/cabin map, annotated comparison or original chart when rights and factual accuracy permit. The hero does not count as an in-body visual. If no defensible body visual is available, record an article-specific editorial exception rather than adding decoration.

### Stage 7 — Editorial pass

Run the available `humanizer`/editorial pass. It may improve rhythm, specificity, transitions, and natural voice. It must not change numbers, dates, names, prices, specifications, quotes, source meaning, approved terminology, qualifiers, URLs, or claim labels.

Reconcile edits against the claim ledger and produce `editorial-changes.md`.

### Stage 8 — Independent QA and Discover readiness

Fingerprint the exact reviewed artifact bundle with `scripts/vertu_qa_handoff.py bundle-fingerprint`, then hand that fingerprint and the draft artifacts to the configured QA skill. This skill only consumes the independent result:

The independent QA run must execute its active editorial-safeguards validator against every final article and the complete current batch. Store `editorial-safeguards.json` with the QA evidence. `DUPLICATE_VERTU_CONCIERGE_INTEGRATION` and `TEMPLATE_DEPENDENT_DRAFT` are unresolved required findings and return the article to writing. `BODY_VISUAL_MISSING` is recorded as a recommended warning only during the first phase and cannot by itself block publication.

```text
PASS  → continue
FIX   → return to Stage 6 with the fix list
BLOCK → stop and report the veto
```

Store `qa-report.md`, `qa-handoff-preflight.json`, the immutable QA Run ID/Base record ID, policy version/hash/profile, result fingerprint and verdict in `handoff.json`. Validate it as `release_gate_role=preflight`, `source_identity.type=artifact_bundle`, and `compatibility_status=COMPATIBLE`. Do not generate an image or mutate Sanity before this R0 preflight `PASS`.

After QA `PASS`, produce `discover-readiness.json` covering historical cluster evidence, timeliness, title/preview, originality/story, concrete reader decision, image specificity, and portfolio diversity. Use only `DISCOVER_READY | DISCOVER_FIX | DISCOVER_REJECT`. Only `DISCOVER_READY` continues.

### Stage 9 — Image Gen

After both `PASS` and `DISCOVER_READY`, create `image-brief.md` from the final thesis. Use Codex `image_gen` for one article-specific 16:9 hero image with a concrete subject and feed-readable focal point. Reject generic black-and-gold technology backgrounds, abstract glass panels, generic robots, text-heavy art, and logos as heroes. Product-led articles must use approved official imagery or clearly non-literal scenes; never generate a false VERTU configuration.

Verify at least 1200 px width, more than 300,000 pixels, landscape crop, descriptive alt, relevant `og:image`/schema image, and `max-image-preview:large`. Produce `visual-verification.json`.

If `image_gen` is unavailable, mark `WAITING_FOR_IMAGE`. Do not silently switch providers.

### Stage 10 — Delivery

Read [references/automation-contract.md](references/automation-contract.md) before automated delivery.

- `local_draft`: stop with the artifact package.
- `sanity_draft`: introspect the live schema, create/update a draft only, verify by query, then run independent R1 QA against that exact Draft revision.
- `production`: only in `publish_approved` mode or the narrow standing `vertu-10` current-run profile, with compatible R0 preflight and R1 prepublish QA `PASS` evidence.

Before production publication, write and validate `qa-handoff-prepublish.json` with `release_gate_role=prepublish`, `source_identity.type=sanity_draft_revision`, the exact Draft document ID/revision and the same `draft_bundle_sha256`. Fail closed on a contract, producer, policy, artifact, revision, QA Run or unresolved-finding mismatch. After publication and live verification, reconcile `qa-handoff-postpublish.json` with `release_gate_role=postpublish_audit` and the exact published revision; missing compatible R2 evidence makes the chain `HANDOFF_INCOMPLETE`, never silent success.

Never trust a historical Sanity body shape. Introspect body, SEO, image, language, section, author, status, and draft conventions before mutation. Publishing scripts must reference a pre-existing approved author and must never create or reshape an author as a side effect. Confirm the public author profile returns HTTP 200, the visible byline links to it, and `BlogPosting.author` matches; missing or broken authorship is a release blocker. The page template owns the visible byline: do not prepend a second `By ...` paragraph to `rawHtml` or Portable Text. If the live section template does not provide a visible linked author, return `AUTHOR_BLOCKED` instead of compensating with an in-body byline. Produce `author-verification.json`.

After any approved production delivery, inspect the final rendered canonical page rather than only the Sanity document. Require every approved internal and external destination to be present in reader-visible HTML, every replaced URL to be absent, no confirmed broken links, and at least one meaningful contextual internal link unless an explicit article-specific exception is recorded. Use a browser-compatible retry for suspicious 4xx responses before declaring a link broken. Store the result in `link-verification.json`; failure is a release defect and must not be reported as successful delivery.

### Stage 11 — Handoff

Report selected topic and score, thesis, reader, draft path and slug, evidence/product-context status, QA verdict, image status, delivery status, blockers, approval required, and the exact next allowed action.

### Stage 12 — Performance feedback

For published articles, run one read-only daily pulse for the rolling 35-day cohort and preserve milestone measurements at 24 hours, 72 hours, 7 days, and 28 days. Use the reusable monitoring contract at `${VERTU_PDCA_ROOT}/contracts/VERTU-Content-Performance-Monitoring-Contract.md` when available.

Build the cohort dynamically with `${VERTU_PDCA_ROOT}/scripts/vertu_content_monitor_runtime.py`; never import a frozen inventory snapshot. Prefer `handoff.state=PUBLISHED`. When that state is stale or absent, accept `PUBLISHED_RECONCILED` only when the same run has a timestamped `publish-result.json`, `run-summary.json status=SUCCESS`, and every corresponding live-verification result passes. Record the drift for repair. Runs through 2026-07-11 with missing first-generation evidence use `LEGACY_EVIDENCE_EXCEPTION` and are excluded from checkpoint and learning eligibility rather than blocking the current cohort.

- `daily`: verify the rolling cohort is live, read the latest finalised GSC/available GA4 state, surface new technical, delivery, demand or packaging anomalies, and record a visible pulse even when no milestone is due.
- `24h`: verify delivery, canonical/indexability, image, authorship/schema, and preliminary GA4 engagement. Do not judge GSC performance yet.
- `72h`: wait for GSC metric-date maturity, then read the first Discover/Search signal.
- `7d`: make the first evidence-backed optimisation decision and propose at most one major variable change.
- `28d`: classify the mature result, check cannibalisation, verify experiments, and feed validated portfolio learnings into future baselines.

Track Discover clicks/impressions/CTR by canonical URL, Search clicks/impressions/CTR/queries/position, and GA4 engagement and qualified product journeys when available. Compare articles at the same age against topic-cluster and publication-cohort baselines. Missing or delayed data is `DATA_NOT_MATURE`, never zero. Historical checkpoints are immutable. Execute a bounded checkpoint-balanced queue on every monitoring run; reporting due work without executing the bounded queue or recording its exact source/identity blocker is incomplete. A failed mandatory GSC or GA4 query is `SOURCE_BLOCKED` and retryable.

After local checkpoint execution, build the canonical Base manifest with `${VERTU_PDCA_ROOT}/scripts/vertu_content_monitor_base_handoff.py`. Production `--apply` requires the same execution's canonical start-ledger receipt in `运行中` and rejects an execution-ID mismatch. The handoff performs exact business-key lookups, creates or reconciles one `监控运行` row and deterministic `节点复盘` observations, then reads them back. `SOURCE_BLOCKED` and `DATA_NOT_MATURE` remain audit observations with null metrics. T+24h is technical/preliminary only; learning eligibility starts with source-complete mature 72h/7d/28d evidence. The handoff performs no Sanity mutation and does not approve experiments.

Run mature 72-hour checkpoints through `${VERTU_PDCA_ROOT}/scripts/vertu_content_traffic_gate.py classify-72h`. A mature checkpoint that passes a Search or Discover sample gate must not remain generic `INSUFFICIENT_DATA`; classify the concrete CTR, coverage, packaging, positive-signal, or intent opportunity. Preliminary 72-hour and 7-day results may inform the next run, but only verified 28-day experiments become durable scoring priors. A user-approved editorial strategy may shape the candidate pool immediately, but it remains separate from the governed learned adjustment and may not be presented as a durable causal conclusion.

Run the governed learning and Skill release job in `references/performance-learning.md` twice daily. It must deduplicate checkpoint retries, reject planned/immature/blocked inputs, refresh or expire provisional priors, write an immutable snapshot, test and replay every proposed change, and store each proposal, activation, expiry, rejection or rollback in canonical Base `Skill Change Log`. Route every material Skill or governing-process change through `references/skill-evolution-scorecard.md`: absolute structural scores are diagnostic only, same-rubric paired comparison controls keep/revert, and traffic-affecting changes require mature production outcomes before promotion eligibility. A same-day traffic spike is an observation, not automatically a permanent skill rule, and a run without material evidence must not force a version bump.

The monitor may prepare a title, meta, hero, introduction, content, internal-link, or freshness change proposal. It must not mutate Sanity without article-specific approval, a mutation preview, and a fresh `_rev` conflict check. Label preliminary data and do not turn one spike into a permanent rule.

Persist monitoring only to the canonical Feishu Base `VERTU 内容与 SEO 运营闭环` (`${FEISHU_BASE_TOKEN}`) using user identity and the current `lark-base` contract. Use `文章资产` for current article state, immutable `节点复盘` rows for each checkpoint, `修改实验` for approval and verification lineage, and immutable `监控运行` rows for every automation execution. Record quiet outcomes such as `NO_DUE_CHECKPOINT`, `DATA_NOT_MATURE`, and `NO_ACTIONABLE_CHANGE`. Never overwrite historical checkpoint/run rows. If a Base write fails, keep the local evidence and report `FEISHU_BASE_WRITE_FAILED` after bounded retries.

## Artifact contract

```text
run.json
editorial-intelligence.json
source-velocity.json
discover-baseline.json
geo-audience-baseline.json
realtime-trends.json
trend-market-map.json
hotness-gate.json
candidates.json
traffic-demand.json
portfolio-plan.json
cluster-support.json
topic-brief.md
evidence-pack.md
product-context.json
outline.md
article.md
seo.json
claim-ledger.json
link-plan.json
editorial-changes.md
discover-readiness.json
image-brief.md
visual-verification.json
author-verification.json
qa-report.md
qa-handoff-preflight.json
qa-handoff-prepublish.json
qa-handoff-postpublish.json
handoff.json
performance-plan.json
performance/<slug>/24h.json
performance/<slug>/72h.json
performance/<slug>/7d.json
performance/<slug>/28d.json
performance/<slug>/diagnosis.json
performance/<slug>/change-proposal.md
performance/<slug>/experiment-ledger.json
learning-snapshot.json
active-performance-priors.json
provisional-performance-priors.json
skill-scorecard-input.json
skill-scorecard.json
```

Missing optional stages must have an explicit status in `handoff.json`.

## Completion

A writing run is complete when every selected topic has auditable candidate-level demand evidence, a truthful trend class and market, an explicit audience-fit lane with its evidence and niche risk, a computed score and passing demand verdict or truthfully returned `NO_TOPIC`; the portfolio is diverse and traffic-weighted; each article has a defensible thesis, original value, sufficient depth, a concrete reader decision, a cluster support plan, and a non-generic visual concept; claims are traceable; product facts were checked; QA is `PASS`; Discover readiness is explicit; draft, metadata, links, author, image, and ledger agree; performance measurement is scheduled; and no unauthorized production action occurred.

## Active references

- [Topic selection](references/topic-selection.md)
- [Traffic demand gate](references/traffic-demand-gate.md)
- [Realtime trends](references/realtime-trends.md)
- [Editorial intelligence](references/editorial-intelligence.md)
- [Performance learning](references/performance-learning.md)
- [Skill evolution scorecard](references/skill-evolution-scorecard.md)
- [Product knowledge](references/product-knowledge.md)
- [Writing contract](references/writing-contract.md)
- [Author policy](references/author-policy.md)
- [Automation contract](references/automation-contract.md)
- [Reference index](references/README.md)

---
name: vertu-english-blog-pipeline
description: Research, demand-score, select, and write original English VERTU Signals articles for vertu.com. Prioritises evidence-backed premium, business, collector and executive decisions with broad reader demand, using candidate-level GSC and trend evidence, the live Feishu product knowledge base, VERTU editorial voice, and automation-safe handoffs. QA, Image Gen, and publishing are separate downstream capabilities.
---

# VERTU English Blog Pipeline

Current contract version: `3.20.0`.

Public packaging notice: this is a sanitised adaptation, not a byte-identical
deployment snapshot. Internal locations and identifiers are placeholders.
Read `docs/CURRENT-OPERATING-PROFILE.md` at the package root: its daily-five
example overrides historical quantity wording below, not safety gates. No
upstream standing approval, scheduled job or publication authority is inherited.

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

The shared identity boundary is `${VERTU_PDCA_ROOT}/docs/03-运行/VERTU-QA-Handoff-Contract.md` (`qa-handoff-v1`). Production and QA keep independent versions and responsibilities, but every new production transition must validate the same producer version, draft-bundle fingerprint, QA policy hash/profile, immutable QA Run ID and exact Sanity revision where present.

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
8. `max_articles` is normally a ceiling, not a quota. Never fill a batch with low-potential content. The named `vertu-10` standing profile is the explicit exception: it requires at least ten fully live-verified articles and fulfils that requirement through bounded candidate expansion and downstream replacement, never by weakening a gate.
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
21. Run a read-only performance and Discover-market pulse three times daily at `00:00`, `08:00`, and `16:00` Asia/Hong_Kong for the rolling 35-day published cohort even when no milestone checkpoint is due. Collect the public D2TR Discover market context at each pulse, retain its dedicated snapshot evidence for 30 rolling days, and preserve the run receipt after snapshot cleanup. A quiet pulse is evidence, not an empty run.
22. Run the governed review and Skill release check twice daily. Fast 24h/72h signals may create observations or manual experiment candidates, but only mature evidence may promote a rule. Version only material, tested and replay-safe changes; when evidence is insufficient, record `NO_PROMOTION` and `NO_SKILL_CHANGE` and preserve the current version.
23. Apply the permanent user-approved brand-mindset prerequisite in `references/brand-mindset-gate.md` before traffic scoring. Only `CORE_MINDSPACE | QUALIFIED_ADJACENT` candidates with a valid `brand-mindset-fit-v1` `PASS` may enter scoring; automatic exploration is disabled.
24. `Luxury`, `high-end`, `business`, price, celebrity ownership or exclusivity are not demand providers. Generic luxury lists and narrow affluent services still require normal demand evidence and may not receive eligibility, trend labels or veto relief from the audience-fit classification.
25. New production runs require a `COMPATIBLE` `qa-handoff-v1`. `LEGACY_UNVERIFIED`, version, artifact, revision or tracking mismatch evidence may be observed historically but may not authorise a new mutation.
26. Count Search demand by independent acquisition-system family, not by provider label. GSC, official Google Trends and Google Ads Keyword Planner are separate families; aliases or derived views of the same upstream dataset count once.
27. A positive candidate-level GSC signal counts for demand only when the newest available finalised window has at least three clicks or at least 100 impressions. Preserve smaller samples as `AVAILABLE/INSUFFICIENT_SAMPLE`; never convert them to zero or fall back to an older window merely to pass the gate.
28. Before QA handoff, a final article may contain at most one VERTU/Concierge integration section. Independent QA must also compare meaningful final heading fingerprints across the batch. Duplicate integration or template-dependent structure is a required fix; missing in-body evidence visuals remain a measured, non-blocking warning during the first phase.
29. D2TR is an independent Discover-market observation source, not official Google Trends, GSC or Search-volume evidence. It may add only a bounded `0..2` portfolio-ordering adjustment to candidates that already passed the normal score, demand, veto and forecast gates; it may not create demand, create `REALTIME_HOT`, waive a veto or penalise a candidate when unavailable. Durable/provisional learning plus D2TR context share one combined `-3..+3` ordering cap.
30. Apply `references/evergreen-quota-fallback.md` to the `vertu-10` profile. Evaluate a `HOT_PRIMARY` pool through cumulative 30/60/90/120 rounds; when fewer than ten cumulative eligible directions remain, start a separately generated `EVERGREEN_FALLBACK` pool through its own 30/60/90/120 rounds. The two phases have independent fingerprints and share a 240-candidate runtime ceiling. If drafting, QA, Discover, image, author, publication, live verification or Base handoff blocks an article, select a distinct eligible replacement and continue. `NO_TOPIC` is not successful completion; only exhausted two-phase supply or a truthful hard blocker may return `DAILY_QUOTA_BLOCKED`, with every gate unchanged.
31. Before any protected local pointer, canonical Base, Sanity, or Skill release mutation, apply `references/loop-runtime-governance.md` and acquire the exact mutation scopes with `scripts/vertu_content_loop_runtime.py`. `PAUSED`, `COLLISION_BLOCKED`, `BUDGET_BLOCKED`, `ATTEMPT_LIMIT`, `STATE_INVALID`, or a failed Base start ledger means zero protected production mutations. A local `ALLOW` receipt never replaces the normal demand, QA, Discover, image, author, revision, live or handoff gates.
32. Extract all 32 raw, source-backed signals in `references/direct-factor-model.md` for every serious candidate with `scripts/vertu_content_factor_extractor.py` before traffic scoring. The extractor must emit one explicit row per factor using `AVAILABLE | SOURCE_UNAVAILABLE | INSUFFICIENT_SAMPLE | NOT_APPLICABLE`; omission is invalid and unavailable evidence never becomes zero. The production default remains shadow-only. During the explicitly approved two-batch trial in `references/hybrid-factor-trial.md`, calculate a non-publishing hybrid challenger over the exact same candidate pool; only the legacy control may continue downstream. Never invent a factor or accept candidate-authored normalised scores.
33. Judge every material Skill or governing-process proposal with the 60-row `skill-evolution-factor-vector-v1` in `references/skill-evolution-factor-vector.md`. Predeclare target factors, guardrail factors, expected direction and maturity before reading outcomes; emit every row with an explicit source state and null unavailable values. Never calculate a global factor total. Evaluate the exact vector with `skill-evolution-factor-evaluation-v1`, then require `skill-evolution-scorecard-v2` to consume that exact fingerprint. A selected-factor source block, immature sample, target miss or guardrail breach must remain explicit. Only `PROMOTION_CANDIDATE` may continue through replay, paired-review, production-maturity and approval gates; neither the vector nor evaluator may select topics, alter priors, waive gates, mutate Sanity or activate a rule.
34. Treat `youtube-topic-signals-v1` as upstream discovery context only. It may expand audience language and current-interest candidate directions, but it may not create Search demand, `REALTIME_HOT`, `RISING_SEARCH`, raw score, eligibility, veto relief or portfolio points. Missing YouTube evidence has zero penalty.
35. After the legacy production scorer selects a topic and before research or drafting, run the exact-query `serp-benchmark-v1` gate in `references/serp-benchmark.md`. Only `BENCHMARK_PASS` continues. `BENCHMARK_REFRAME` returns to Stage 2, `BENCHMARK_REPLACE` selects a distinct eligible replacement, and `SERP_BENCHMARK_SOURCE_BLOCKED` stops drafting that candidate.
36. Treat `llm-visibility-diagnosis-v1` as read-only post-publication feedback. One missing citation never proves non-indexation. LLM observations may not select topics, alter scores or priors, authorise publication, mutate Sanity or change the Skill without a later mature governed experiment.
37. When a valid, unexpired `discover-recovery-editorial-strategy-v1` pointer is active, apply `references/discover-recovery-profile.md` before broad candidate creation. It may shape candidate generation and portfolio framing only; it may not create demand, change raw or priority scores, create trend labels, change eligibility, waive vetoes, relax any downstream gate, create a learned prior or authorise publication. Its pool targets are never publication quotas, and it expires without self-renewal.
38. A high score, search volume, official trend, D2TR/YouTube signal, learning prior or quota pressure may never rescue `HOLD`, `UNQUALIFIED`, `COMMODITY_LIFESTYLE_MISMATCH`, `FORCED_BRAND_ASSOCIATION`, `PRICE_ONLY_LUXURY_LABEL` or `OUTSIDE_BRAND_MINDSPACE`. Ambiguity fails closed. Weakening this permanent boundary requires explicit user approval or mature governed Skill evolution; same-day traffic cannot relax it.

## Run modes

| Mode | Use | Default result |
|---|---|---|
| `manual_topic` | User provides a topic, keyword, source, or thesis | Validate and write one draft |
| `auto_discovery` | Scheduled or requested topic discovery | Build a performance-informed portfolio up to the approved maximum; the named `vertu-10` profile also enforces its ten-live-article minimum |
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

Read [references/loop-runtime-governance.md](references/loop-runtime-governance.md) completely.

Create:

```text
${VERTU_PDCA_ROOT}/output/vertu-signals/YYYY-MM-DD/<slug-or-run-id>/
```

Write `run.json` first. Record mode, wall-clock timestamp, source window, delivery, approval state, and an idempotency key. The key should include UTC date, selected slug, and a hash of the source set. Retries resume the same run.

Before a protected local pointer, canonical Base, Sanity, or Skill release mutation, write `loop-runtime-manifest.json` with `contract_version=vertu-content-loop-runtime-v1`, deterministic execution identity, loop type, mode, exact write scopes, lease, usage, limits and per-scope attempts. Acquire the scopes with `${VERTU_PDCA_ROOT}/scripts/vertu_content_loop_runtime.py` and preserve `loop-runtime-acquire.json`. Continue protected mutations only on `ALLOW`; `READ_ONLY_ALLOW` authorises read-only work only. Keep the canonical Base start-ledger gate independently mandatory.

### Stage 1 — Performance baseline and topic discovery

Read [references/topic-selection.md](references/topic-selection.md) completely.
Read [references/brand-mindset-gate.md](references/brand-mindset-gate.md) completely.
Read [references/traffic-demand-gate.md](references/traffic-demand-gate.md) completely.
Read [references/evergreen-quota-fallback.md](references/evergreen-quota-fallback.md) completely for the named `vertu-10` profile.
Read [references/direct-factor-model.md](references/direct-factor-model.md) completely.
Read [references/hybrid-factor-trial.md](references/hybrid-factor-trial.md) completely while its immutable configuration is active.
Read [references/realtime-trends.md](references/realtime-trends.md) completely.
Read [references/editorial-intelligence.md](references/editorial-intelligence.md) completely.
Read [references/youtube-topic-signals.md](references/youtube-topic-signals.md) completely.
Read [references/discover-recovery-profile.md](references/discover-recovery-profile.md) completely when its active pointer exists.
Read [references/performance-learning.md](references/performance-learning.md) completely.
Read [references/skill-evolution-factor-vector.md](references/skill-evolution-factor-vector.md) completely when evaluating or releasing a Skill/process change.
Read [references/skill-evolution-scorecard.md](references/skill-evolution-scorecard.md) completely when evaluating or releasing a Skill/process change.

Before discovering topics, query finalised GSC data for the previous 365 days when access is available: Discover and Search page performance, top topic clusters, title/intent patterns, recent 28-day changes, and high-impression low-CTR opportunities. Store `discover-baseline.json`. Never expose credentials. If unavailable, mark `PERFORMANCE_BASELINE_UNAVAILABLE`.

Before broad candidate creation, locate and read the latest successful same-day Hermes RSS intelligence run and the downstream editorial synthesis. Write `editorial-intelligence.json` and `source-velocity.json`. If the expected runs are absent or stale, record `EDITORIAL_INTELLIGENCE_UNAVAILABLE`; do not silently continue as though the feed was checked.

Collect or read the current `youtube-topic-signals-v1` snapshot before scoring when an official API or reproducible export is available. Write `youtube-topic-signals.json`, preserve its source state and fingerprint, and predeclare every candidate mapping before the score is known. The first-phase artifact is `SHADOW_ONLY`: it may add candidate language and supporting Discover current-interest context, but it contributes no demand provider, hot/rising label, raw score, eligibility, veto relief or ordering points. If unavailable, record `YOUTUBE_SIGNALS_UNAVAILABLE` and continue with zero effect.

Inputs may include the performance baseline, a user topic, the mandatory Hermes intelligence chain, the latest Cipher feed, official announcements, primary documentation, research papers, current GSC/GA4 evidence, and the existing VERTU article inventory.

Read `${VERTU_PDCA_ROOT}/output/vertu-signals/learning/active-performance-priors.json` when present. Verify its `performance-learning-v1` contract and fingerprint. Record its fingerprint and active-prior count in `run.json` and `traffic-demand.json`. If absent or invalid, use `LEARNING_PRIORS_UNAVAILABLE`; do not reconstruct active rules from prose.

Also read `${VERTU_PDCA_ROOT}/output/vertu-signals/learning/provisional-performance-priors.json` when present. Verify its `performance-learning-provisional-v1` contract, fingerprint, activation and expiry. Record its fingerprint, active count and ignored expired count. If absent or invalid, use `PROVISIONAL_LEARNING_PRIORS_UNAVAILABLE`; never refresh or recreate a provisional prior from prose.

Read `${VERTU_PDCA_ROOT}/output/vertu-signals/learning/active-discover-recovery-profile.json` when present. Validate `discover-recovery-editorial-strategy-v1`, its fingerprint, explicit user-approval basis, seven-day maximum lifetime, expiry and zero-authority flags. When active, write the exact profile into the run as `discover-recovery-profile.json`, write `candidate-pool-plan.json`, and attach its fingerprint to every serious candidate generated under it. Prefer VERTU-relevant decision/comparison and executive AI/privacy/security/mobile directions, retain a bounded verified current-event lane, and keep generic household/kitchen/mattress/weak-wellbeing directions outside the default recovery pool. Treat observed category cooldowns as candidate-generation guidance only: material new evidence may reintroduce an exact intent, but the unchanged deterministic gate still decides eligibility. Invalid, inactive, expired or absent evidence has zero effect and must remain explicit.

Apply the standing user-approved editorial strategy separately from governed learned priors. Prioritise mass-recognisable premium decisions in commercial-airline cabins and airport services, executive phones/privacy/business technology, watches/collecting/craft, and familiar luxury purchases when they also have a concrete choice and normal demand evidence. Apply `references/brand-mindset-gate.md` to every lead before it becomes a serious scored candidate. Record the gate class, all three semantic dimensions, rationale, conflicts, evidence references, fingerprint and expansion round alongside `audience_fit_lane`, `mass_recognisability`, `decision_intent`, `historical_cluster_evidence`, and `niche_risk`. Do not generalise commercial-airline success to private aviation, yachts, ultra-niche services or generic luxury. Historical cluster adjacency may score audience fit but is a Search-demand provider only when finalised candidate-level GSC query/page evidence matches the same normalised intent. Score the underlying evidence once; the gate class itself adds no points.

Before candidate creation, query finalised 28-day GSC by country and fetch Google Trends Trending Now for the configured markets. Prefer API Alpha when authorised; otherwise use the official public RSS, CSV or reproducible UI export. Pass the deterministic `publication_run_id` into the collector and write `geo-audience-baseline.json`, `realtime-trends.json`, `trend-market-map.json`, and `hotness-gate.json`. The three trend artifacts must share the run ID and snapshot fingerprint. An unavailable API is not permission to skip an accessible official public fallback.

Also read `${VERTU_PDCA_ROOT}/output/vertu-signals/trend-monitor/latest-d2tr-market-context.json`, the fingerprinted active pointer to the newest valid `d2tr-discover-context-v1` artifact. Require observation and source-generation age no greater than eight hours. Record its execution ID, source snapshot fingerprint, context fingerprint, market states and age in `run.json` and `traffic-demand.json`. Each candidate that wants this context must declare an exact `d2tr_context` market plus one or more explicit topic-category, editorial-format-group, format-type or content-category mappings. Never infer a mapping from a title after scoring. If no valid fresh snapshot or exact mapping exists, use zero D2TR adjustment without penalising the candidate.

For every serious candidate, collect candidate-level demand evidence rather than relying only on the portfolio baseline. Record GSC query/page evidence and recent change, Google Trends/current-interest evidence, Keyword Planner volume when authorised, SERP gap evidence, inventory overlap, source status, observation window, evidence reference, fetch time, target market and one of `REALTIME_HOT | RISING_SEARCH | EVERGREEN_SEARCH`. Preserve raw historical-cluster, primary-source publication-time and reproducible SERP metrics when they exist; do not substitute the seven aggregate dimension scores for these raw values.

For unstable information, browse and verify current facts. Prefer primary sources and record publication date separately from event date.

### Stage 2 — Score and select

Run `${VERTU_PDCA_ROOT}/scripts/vertu_brand_mindset_gate.py` over every cumulative lead pool before traffic scoring. Write `brand-mindset-candidates.json` and `brand-mindset-summary.json`; only fingerprint-valid `PASS` rows continue. Then run `${VERTU_PDCA_ROOT}/scripts/vertu_content_factor_extractor.py` once over that full serious-candidate pool. Write `candidates-with-factors.json` and `factor-extraction.json`, and require `content-factor-extractor-v1`, exactly 32 factor rows per candidate, source paths, observation time and a snapshot fingerprint. The extractor derives raw values only from run artifacts and deterministic check booleans; it does not calculate the production score. A missing source becomes an explicit state, never a guessed value or zero.

Apply `references/direct-factor-model.md` to `candidates-with-factors.json` alongside the existing traffic gate. Preserve `computed_factor_v1_shadow` and weighted coverage in `traffic-demand.json`; the production-default shadow output cannot rescue, reject, reorder or publish a candidate until governed activation. If weighted diagnostic coverage is below 70%, emit `INSUFFICIENT_FACTOR_COVERAGE` and no mature diagnostic conclusion.

While the immutable paired-trial configuration remains active and fewer than two unique publication runs are registered, apply `references/hybrid-factor-trial.md`. Run the scorer twice with identical candidate and source inputs: write `candidate-scores-legacy.json` using `--factor-score-mode legacy` and `candidate-scores-hybrid.json` using `--factor-score-mode hybrid_trial`. Register both with `scripts/vertu_factor_score_paired_trial.py` as `factor-score-paired-trial.json`. Only `candidate-scores-legacy.json` may supply the production portfolio; the challenger is comparison evidence and has zero writing or publication authority. A mismatch or trial regression never weakens or replaces the normal legacy workflow.

Validate and score serious candidates with the active brand-mindset, traffic-demand, editorial-intelligence, realtime-trends, D2TR market-context and performance-learning contracts. Calculate the final score with `${VERTU_PDCA_ROOT}/scripts/vertu_content_traffic_gate.py --require-brand-mindset-gate --brand-mindset-profile recovery|stable`; do not type a final score into a per-run script. Require `score_source=computed_v3_12_0`, retain `demand_signal_qualifications`, and reject a Search-first candidate unless at least two qualified acquisition-system families remain after GSC sample qualification and same-family deduplication. Pass `--editorial-intelligence editorial-intelligence.json --source-velocity source-velocity.json` whenever any candidate declares `EDITORIAL_BREAKOUT`. Pass `--learning-priors ${VERTU_PDCA_ROOT}/output/vertu-signals/learning/active-performance-priors.json` when the durable snapshot validates, `--provisional-learning-priors ${VERTU_PDCA_ROOT}/output/vertu-signals/learning/provisional-performance-priors.json` when the provisional snapshot validates, and `--d2tr-market-context d2tr-market-context.json` when the context snapshot is fresh and valid. Use `--trend-mode realtime_hot --realtime-trends realtime-trends.json --trend-market-map trend-market-map.json --hotness-gate hotness-gate.json` for `HOT_PRIMARY`; use the same unchanged scorer with truthful `EVERGREEN_SEARCH` classifications for `EVERGREEN_FALLBACK`. The scorer must live-recheck the official Trends feed and primary source before accepting a hot label. Learning priors and D2TR context apply only after normal eligibility and share one combined ordering adjustment capped at three points. GSC or Keyword Planner may prove durable demand but cannot make an article `REALTIME_HOT`; D2TR cannot prove either demand or the hot label. A topic needs a brand-mindset `PASS`, a passing demand verdict, a computed `80/100`, no veto, and a pre-draft `discover_forecast=PASS`. For `vertu-10`, evaluate current-interest leads through 30/60/90/120, then independently generated evergreen leads through 30/60/90/120 when cumulative eligible supply remains below ten. Selection is a portfolio decision, not ten independent headline decisions.

Produce `candidates.json`, `brand-mindset-candidates.json`, `brand-mindset-summary.json`, `traffic-demand.json`, `portfolio-plan.json`, `cluster-support.json`, and one `topic-brief.md` per selected article. During recovery prefer about 80% `CORE_MINDSPACE` and cap `QUALIFIED_ADJACENT` at 20%; in stable mode prefer 60–80% core and cap adjacent at 40%. These are soft portfolio preferences after all normal gates, not quotas. Automatic exploration is disabled. Preserve entity, intent and title-structure diversity and the seven-day duplicate check. When one event supports several useful pages, use one event/opportunity page plus no more than two distinct search-intent support pages; define query boundaries and publication order before drafting.

For the named `vertu-10` profile, write `daily-quota-state.json` under `daily-publishing-quota-v2`. Apply `references/evergreen-quota-fallback.md`: begin with `HOT_PRIMARY` 30/60/90/120 rounds, then start `EVERGREEN_FALLBACK` 30/60/90/120 rounds when cumulative eligible supply is below ten. Generate fallback candidates from current authorised GSC, Keyword Planner, live inventory gaps, configured markets and passing brand-mindset clusters; record independent pool fingerprints and exact candidate lineage. Repeat live Sanity overlap checks and the unmodified deterministic traffic gate on every round. Do not relabel a rejected candidate without material new evidence or a genuinely distinct query/intent boundary. If a downstream article is blocked, preserve its reason and select a distinct eligible replacement. Continue until at least ten articles are fully live verified and handed off or both 120-candidate phases are exhausted. Below ten after two-phase exhaustion is `DAILY_QUOTA_BLOCKED`, never successful `NO_TOPIC`, and must not be repaired by lowering any gate.

### Stage 2.5 — Exact-query SERP benchmark

Read [references/serp-benchmark.md](references/serp-benchmark.md) completely.

For every selected production topic, collect a normalised authorised-provider or reproducible browser SERP export for the exact selected query, market, language and device. Run `${VERTU_PDCA_ROOT}/scripts/vertu_serp_benchmark.py` before evidence-pack research, outlining or drafting. Write `serp-benchmark.json`, `ranking-page-anatomy.json` and `content-differentiation-brief.md`.

Require at least five result summaries, three HTTP-200 independently hosted body extracts and one concrete article-specific original-value delta. `BENCHMARK_PASS` continues to Stage 3. A material query/intent change is `BENCHMARK_REFRAME` and returns to Stage 2 for the unchanged traffic gate. A generic or duplicate value proposition is `BENCHMARK_REPLACE`; thin/mismatched source evidence is `SERP_BENCHMARK_SOURCE_BLOCKED`. Preserve the blocker and use a distinct eligible replacement under the `vertu-10` quota contract. Observe ranking-page anatomy but never copy wording, paragraph order, proprietary data or images.

### Stage 3 — Evidence pack

Research before outlining. For every source record title, URL, publisher/author, published date, event date, primary/secondary status, supported claims, uncertainties, and citation suitability.

Produce `evidence-pack.md`. Every source-needing statement in the draft must map to this file or the product context pack.

### Stage 4 — VERTU product context

Read [references/product-knowledge.md](references/product-knowledge.md) completely.

Canonical source:

`${FEISHU_RESOURCE_URL}`

Fetch it fresh whenever the article mentions a VERTU product, service, Hermes Agent, VPS, craftsmanship, privacy, health/wellness, price, availability, or specifications. Extract only relevant sections and live-verify volatile fields.

Produce `product-context.json` with the Feishu revision and fetch timestamp. If no product is naturally relevant, record that and do not inject one.

### Stage 5 — Argument and outline

Read [references/writing-contract.md](references/writing-contract.md) completely.
Read [references/author-policy.md](references/author-policy.md) completely.

The outline must identify dominant intent, audience-fit lane, mass-recognisable subject, concrete premium/business/collector decision when applicable, a one-sentence thesis, incremental value, evidence required by each section, VERTU's legitimate perspective, and the earned conclusion. It must cite the exact `serp-benchmark.json` fingerprint and translate the required original-value delta from `content-differentiation-brief.md` into named sections and a concrete value object.

Produce `outline.md`. Select the author by dominant topic expertise before drafting and record the author ID and assignment reason. Do not draft until the outline forms an argument rather than a list.

### Stage 6 — Draft for depth and decision value

Use the installed `seo-content-writer` when available for intent alignment, metadata, and evidence boundaries. This VERTU-specific contract overrides generic formulas.

Produce `article.md`, `seo.json`, `claim-ledger.json`, and `link-plan.json`. Normal depth ranges are 1,000–1,500 words for timely news-to-insight, 1,200–1,800 for practical explainers, 1,600–2,600 for buyer guides/comparisons, and 2,200–3,200 for pillar/collector guides. These are editorial ranges, not Google ranking factors; shorter work may pass when complete, and padded work fails.

The link plan must implement the selected topic's cluster boundary. Record at least one relevant outbound internal destination and up to three genuinely relevant existing pages that could provide contextual inbound links. If no suitable inbound source exists, record `DISTRIBUTION_RISK`; never manufacture an unrelated link. Historical-page link mutations still require their own scoped authority.

The link plan must count unique destinations rather than anchor tags. Two anchors pointing to the same normalised URL are one source. Reader-useful authoritative PDFs count as evidence links; image assets and schema-only URLs do not. Before handoff, reconcile `serp-benchmark.json`, `content-differentiation-brief.md`, `evidence-pack.md`, `link-plan.json`, the final article body, and the claim ledger so the declared differentiation and approved reader-facing evidence are not lost during conversion.

Every article needs at least one article-specific value object: an evidence-backed comparison table, decision matrix, timeline, checklist, original synthesis, verified product matrix, or clearly sourced data summary. Do not append a formulaic FAQ unless real reader questions support it.

Use at most one article-specific VERTU/Concierge integration section. A second brand-service section is not additional relevance; consolidate it before QA. For long buyer/comparison articles, plan at least one descriptive in-body evidence visual such as a sourced diagram, route/cabin map, annotated comparison or original chart when rights and factual accuracy permit. The hero does not count as an in-body visual. If no defensible body visual is available, record an article-specific editorial exception rather than adding decoration.

### Stage 7 — Editorial pass

Run the available `humanizer`/editorial pass. It may improve rhythm, specificity, transitions, and natural voice. It must not change numbers, dates, names, prices, specifications, quotes, source meaning, approved terminology, qualifiers, URLs, or claim labels.

Reconcile edits against the claim ledger and produce `editorial-changes.md`.

### Stage 8 — Independent QA and Discover readiness

Fingerprint the exact reviewed artifact bundle with `scripts/vertu_qa_handoff.py bundle-fingerprint`, including `brand-mindset-candidates.json`, `brand-mindset-summary.json`, `serp-benchmark.json`, `ranking-page-anatomy.json` and `content-differentiation-brief.md`, then hand that fingerprint, the exact passing brand-gate identity and the draft artifacts to the configured QA skill. The independent QA policy must verify the exact benchmark fingerprint and whether the final article visibly implements the declared original-value delta. Producer `>=3.19.0` without a passing `brand-mindset-fit-v1` identity is `TRACKING_INCOMPLETE`. This skill only consumes the independent result:

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

Read [references/llm-visibility-diagnosis.md](references/llm-visibility-diagnosis.md) completely.

After live publication and canonical Base handoff, run the read-only LLM visibility diagnostic at T+72h, D+7 and D+28 when a validated model/prompt panel is available; T+24h may record crawl/canonical technical proxies only. Write `crawl-access.json`, `llm-citation-observations.json` and `llm-visibility-diagnosis.json` under `performance/<slug>/llm/<checkpoint>/`. Record `SOURCE_UNAVAILABLE` without blocking normal GSC/GA4 monitoring. A single negative observation may not create an indexation conclusion, repair, prior or Skill change.

For published articles, run one read-only daily pulse for the rolling 35-day cohort and preserve milestone measurements at 24 hours, 72 hours, 7 days, and 28 days. Use the reusable monitoring contract at `${VERTU_PDCA_ROOT}/docs/03-运行/VERTU-Content-Performance-Monitoring-Contract.md` when available.

Build the cohort dynamically with `${VERTU_PDCA_ROOT}/scripts/vertu_content_monitor_runtime.py`; never import a frozen inventory snapshot. Prefer `handoff.state=PUBLISHED`. When that state is stale or absent, accept `PUBLISHED_RECONCILED` only when the same run has a timestamped `publish-result.json`, `run-summary.json status=SUCCESS`, and every corresponding live-verification result passes. Record the drift for repair. Runs through 2026-07-11 with missing first-generation evidence use `LEGACY_EVIDENCE_EXCEPTION` and are excluded from checkpoint and learning eligibility rather than blocking the current cohort.

- `daily`: verify the rolling cohort is live, read the latest finalised GSC/available GA4 state, surface new technical, delivery, demand or packaging anomalies, and record a visible pulse even when no milestone is due.
- `24h`: verify delivery, canonical/indexability, image, authorship/schema, and preliminary GA4 engagement. Do not judge GSC performance yet.
- `72h`: wait for GSC metric-date maturity, then read the first Discover/Search signal.
- `7d`: make the first evidence-backed optimisation decision and propose at most one major variable change.
- `28d`: classify the mature result, check cannibalisation, verify experiments, and feed validated portfolio learnings into future baselines.

Track Discover clicks/impressions/CTR by canonical URL, Search clicks/impressions/CTR/queries/position, and GA4 engagement and qualified product journeys when available. Compare articles at the same age against topic-cluster and publication-cohort baselines. Missing or delayed data is `DATA_NOT_MATURE`, never zero. Historical checkpoints are immutable. Execute a bounded checkpoint-balanced queue on every monitoring run; reporting due work without executing the bounded queue or recording its exact source/identity blocker is incomplete. A failed mandatory GSC or GA4 query is `SOURCE_BLOCKED` and retryable.

After local checkpoint execution, build the canonical Base manifest with `${VERTU_PDCA_ROOT}/scripts/vertu_content_monitor_base_handoff.py`. Production `--apply` requires the same execution's canonical start-ledger receipt in `运行中` and rejects an execution-ID mismatch. The handoff performs exact business-key lookups, creates or reconciles one `监控运行` row and deterministic `节点复盘` observations, then reads them back. `SOURCE_BLOCKED` and `DATA_NOT_MATURE` remain audit observations with null metrics. T+24h is technical/preliminary only; learning eligibility starts with source-complete mature 72h/7d/28d evidence. The handoff performs no Sanity mutation and does not approve experiments.

Run mature 72-hour checkpoints through `${VERTU_PDCA_ROOT}/scripts/vertu_content_traffic_gate.py classify-72h`. A mature checkpoint that passes a Search or Discover sample gate must not remain generic `INSUFFICIENT_DATA`; classify the concrete CTR, coverage, packaging, positive-signal, or intent opportunity. Preliminary 72-hour and 7-day results may inform the next run, but only verified 28-day experiments become durable scoring priors. A user-approved editorial strategy may shape the candidate pool immediately, but it remains separate from the governed learned adjustment and may not be presented as a durable causal conclusion.

Run the governed learning and Skill release job in `references/performance-learning.md` twice daily. Before evaluation, run the read-only loop audit from `references/loop-runtime-governance.md` and preserve `loop-health.json`; a degraded audit must remain visible and cannot be hidden by a successful learning no-op. The learning job must deduplicate checkpoint retries, reject planned/immature/blocked inputs, refresh or expire provisional priors, write an immutable snapshot, test and replay every proposed change, and store each proposal, activation, expiry, rejection or rollback in canonical Base `Skill 学习与进化` (`CONFIGURE_TBL`, formerly `Skill Change Log`). Before reading change outcomes, predeclare its hypothesis and generate the complete shadow `skill-evolution-factor-vector-v1`; preserve all 60 rows locally and in the canonical normalised factor-observation table. Evaluate the exact vector with `scripts/vertu_skill_evolution_factor_evaluator.py` and preserve `skill-evolution-factor-evaluation.json`. Route every material Skill or governing-process change through `references/skill-evolution-scorecard.md`: scorecard v2 must consume the exact evaluation fingerprint; only `PROMOTION_CANDIDATE` continues to structural diagnostics, same-rubric paired comparison, replay and production maturity. A same-day traffic spike is an observation, not automatically a permanent Skill rule, and a run without material evidence must not force a version bump.

At every terminal domain state, release the exact local mutation scopes and preserve `loop-runtime-release.json`. A repeated release may return `ALREADY_RELEASED`. `RELEASE_INCOMPLETE` is `HANDOFF_INCOMPLETE`; never claim the full automation chain completed until local ownership and canonical Base terminalisation both reconcile.

The monitor may prepare a title, meta, hero, introduction, content, internal-link, or freshness change proposal. It must not mutate Sanity without article-specific approval, a mutation preview, and a fresh `_rev` conflict check. Label preliminary data and do not turn one spike into a permanent rule.

Persist monitoring only to the canonical Feishu Base `VERTU SEO 全流程治理与 Skill 自进化` (`${FEISHU_BASE_TOKEN}`) using user identity and the current `lark-base` contract. Use `文章资产` for current article state, immutable `节点复盘` rows for each checkpoint, `修改实验` for approval and verification lineage, and immutable `监控运行` rows for every automation execution. Record quiet outcomes such as `NO_DUE_CHECKPOINT`, `DATA_NOT_MATURE`, and `NO_ACTIONABLE_CHANGE`. Never overwrite historical checkpoint/run rows. If a Base write fails, keep the local evidence and report `FEISHU_BASE_WRITE_FAILED` after bounded retries.

## Artifact contract

```text
run.json
editorial-intelligence.json
source-velocity.json
youtube-topic-signals.json
discover-baseline.json
geo-audience-baseline.json
realtime-trends.json
trend-market-map.json
hotness-gate.json
candidates.json
hot-primary-candidates.json
evergreen-fallback-candidates.json
daily-quota-state.json
brand-mindset-candidates.json
brand-mindset-summary.json
candidates-with-factors.json
factor-extraction.json
candidate-scores-legacy.json
candidate-scores-hybrid.json
factor-score-paired-trial.json
traffic-demand.json
portfolio-plan.json
cluster-support.json
topic-brief.md
serp-benchmark.json
ranking-page-anatomy.json
content-differentiation-brief.md
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
performance/<slug>/llm/<checkpoint>/crawl-access.json
performance/<slug>/llm/<checkpoint>/llm-citation-observations.json
performance/<slug>/llm/<checkpoint>/llm-visibility-diagnosis.json
learning-snapshot.json
active-performance-priors.json
provisional-performance-priors.json
skill-scorecard-input.json
skill-scorecard.json
skill-evolution-factor-input.json
skill-evolution-factors.json
skill-evolution-factor-evaluation-input.json
skill-evolution-factor-evaluation.json
```

Missing optional stages must have an explicit status in `handoff.json`.

## Completion

A writing run is complete when every selected topic has auditable candidate-level demand evidence, a truthful trend class and market, an explicit audience-fit lane with its evidence and niche risk, a computed score and passing demand verdict or a truthful terminal blocker; the portfolio is diverse and traffic-weighted; each article has a defensible thesis, original value, sufficient depth, a concrete reader decision, a cluster support plan, and a non-generic visual concept; claims are traceable; product facts were checked; QA is `PASS`; Discover readiness is explicit; draft, metadata, links, author, image, and ledger agree; performance measurement is scheduled; and no unauthorized production action occurred. The `vertu-10` profile reports success only after at least ten articles are live verified with complete canonical Base lineage.

## Active references

- [Topic selection](references/topic-selection.md)
- [Traffic demand gate](references/traffic-demand-gate.md)
- [Daily hot-to-evergreen quota fallback](references/evergreen-quota-fallback.md)
- [Direct content factor model](references/direct-factor-model.md)
- [Hybrid factor paired trial](references/hybrid-factor-trial.md)
- [Realtime trends](references/realtime-trends.md)
- [Editorial intelligence](references/editorial-intelligence.md)
- [YouTube topic signals](references/youtube-topic-signals.md)
- [Post-selection SERP benchmark](references/serp-benchmark.md)
- [Post-publication LLM visibility diagnosis](references/llm-visibility-diagnosis.md)
- [Performance learning](references/performance-learning.md)
- [Skill evolution factor vector](references/skill-evolution-factor-vector.md)
- [Skill evolution scorecard](references/skill-evolution-scorecard.md)
- [Product knowledge](references/product-knowledge.md)
- [Writing contract](references/writing-contract.md)
- [Author policy](references/author-policy.md)
- [Automation contract](references/automation-contract.md)
- [Reference index](references/README.md)

# Changelog

## 3.11.0 — 2026-08-05

- Counted demand evidence by acquisition-system family so aliases and derived views of one upstream source cannot satisfy an independence requirement twice.
- Required the newest available finalised candidate GSC window to reach at least three clicks or one hundred impressions before it can count as positive demand evidence; smaller samples remain visible as `AVAILABLE/INSUFFICIENT_SAMPLE`.
- Added an independent QA blocker for duplicate VERTU/Concierge integration sections and batch-level meaningful-heading fingerprints.
- Added `BODY_VISUAL_MISSING` as a measured, non-blocking warning for long buyer/comparison drafts pending a controlled experiment.
- Added audited `CURRENT`/`SUPERSEDED`/`HISTORICAL` checkpoint projection without rewriting immutable performance metrics.
- Aligned producer 3.11.0 with independent QA 0.7.0 through `qa-handoff-v1`, deterministic replay and canonical Base readback.

## 3.10.0 — 2026-08-04

- Made `computed_v3_10_0` the deterministic score source and preserved raw score separately from learned ordering adjustments.
- Required candidate-level GSC query/page evidence to match the normalised intent before historical cluster adjacency may support Search demand.
- Kept durable and provisional priors post-eligibility only with one combined `-3..+3` cap.
- Strengthened evidence-pack, final-body and rendered-link reconciliation across the producer/QA handoff.

## 3.9.0 — 2026-08-03

- Added a deterministic three-layer Skill evolution scorecard: structural diagnostics, same-rubric paired comparison and mature production outcomes.
- Made absolute scores triage-only; keep/revert requires paired majority and a fingerprinted historical replay with zero hard-gate regressions.
- Required mature D+28 evidence across at least two runs or a verified controlled experiment before traffic-affecting Skill changes become promotion-eligible.
- Kept structural activation and low-risk experiments manually approved.
- Added machine-readable release states, fingerprints, tests, twice-daily automation instructions and canonical `Skill Change Log` tracking.
- Shortened the review cadence to twice daily so afternoon publications can surface same-evening observations while preserving mature promotion thresholds.
- Activated the governance infrastructure under explicit user approval without promoting a traffic rule or mutating Sanity.

## 3.8.0 — 2026-07-29

- Shortened the governed learning and Skill release check from weekly to every 48 hours.
- Added fingerprinted, expiring provisional priors from recent repeated mature 72-hour or 7-day evidence.
- Limited 72-hour provisional adjustments to one point and 7-day provisional adjustments to two points.
- Applied provisional and durable priors only after normal eligibility with one combined `-3..+3` cap.
- Kept durable promotion unchanged at three mature D+28 articles across two runs or one verified controlled experiment.
- Added automatic provisional expiry, explicit `NO_PROMOTION`, replay and rollback requirements.
- Updated `vertu-10` to consume both durable and provisional learning artifacts.

## 3.7.0 — 2026-07-27

- Added the user-approved premium/business decision strategy to candidate generation and portfolio framing.
- Added `PREMIUM_DECISION_CORE`, `ADJACENT`, and `EXPLORATION` audience-fit lanes with mass-recognisability, concrete decision-intent, historical-cluster and niche-risk evidence.
- Added a soft 50–70% decision-core portfolio preference across at least three distinct VERTU clusters when enough candidates independently pass.
- Added hard boundaries against `premium_label_only` and `niche_affluence_without_demand`; luxury, price and exclusivity cannot create demand or eligibility.
- Kept the strategy separate from governed performance priors: the 2026-07-26 airline-cabin result remains a strong observation until 72h/7d/28d maturity and replay gates pass.
- Clarified forward-test boundaries: pre-gate exploration is `EXPLORATION_CANDIDATE`; historical GSC adjacency is not candidate-level demand; independent Search providers are enumerated; authority `TEST` approval is explicit; `no_defensible_content_gap` is a veto; and the pre-draft Discover forecast is distinct from final `DISCOVER_READY`.

Source evidence: finalised recent-28-day GSC through 2026-07-24; exact first-24-hour GA4 for the 2026-07-26 flight-decision batch; preliminary GSC Discover for the same batch; explicit user approval on 2026-07-27.

## 3.4.0 — 2026-07-22

- Made the same-day Hermes RSS intelligence and editorial synthesis mandatory upstream inputs for current-topic portfolios.
- Added auditable `EDITORIAL_BREAKOUT` evidence without mislabelling community or editorial velocity as official Google Trends demand.
- Added `editorial-intelligence.json` and `source-velocity.json`, deterministic scorer reconciliation, and event-page plus search-support cluster packaging.
- Preserved the existing Google-only `REALTIME_HOT` rule, traffic threshold, non-News boundary, QA separation and production gates.

## 3.3.1 — 2026-07-22

- Added official Google Trends Trending Now RSS/CSV/UI fallback when API Alpha is unavailable.
- Added country-level GSC audience baselines and nine configured trend markets.
- Split candidates into `REALTIME_HOT`, `RISING_SEARCH`, and `EVERGREEN_SEARCH`.
- Added a hard veto for unverified real-time-hot labels.
- Capped trend-velocity scores for rising and evergreen candidates.
- Added auditable trend-market artifacts and trend-class counts to completion receipts.
- Reconciled every hot candidate against the same run's Google Trends snapshot and rejected forged source flags, blank markets, invalid dates and empty news nodes.
- Bound trend artifacts and candidates to publication run ID plus snapshot fingerprint, made all derivative artifacts executable scorer inputs, and made snapshot metrics authoritative.
- Added exact derivative-content validation and live official-feed/primary-source verification before a hot label can pass.

## 3.2.2 — 2026-07-13

- Changed link QA from anchor counts to unique normalised destination counts.
- Counted authoritative PDF documents as reader-facing evidence while continuing to exclude image assets, author links, self-links and schema-only URLs.
- Added evidence-pack/link-plan/final-body reconciliation so approved sources cannot disappear during conversion or publication.
- Added post-delivery verification against rendered canonical HTML, including approved-link presence and stale-link absence.
- Added a browser-compatible retry requirement before suspicious 4xx responses are classified as confirmed broken links.
- Allowed explicit article-specific source-count exceptions while prohibiting decorative links added only to satisfy a number.

Source evidence: production remediation run `link-remediation-2026-07-13-recent-39` covering 39 VERTU articles, 29 revision-locked mutations and 57 link operations.

## 3.2.1 — 2026-07-13

- Added square institutional author-avatar requirements.
- Prohibited invented human portraits, text-heavy avatars and false product configurations.
- Added live author-image and alt-text verification to the release gate.

## 3.2.0 — 2026-07-13

- Added an active institutional editorial-desk author registry with six topic-specific bylines.
- Made author assignment expertise-first, with 14-day usage only as a tie-break.
- Prohibited invented individuals, personal credentials and fake first-hand experience.
- Prohibited article publishing scripts from creating or reshaping author documents.
- Added live HTTP 200 author-profile, visible byline and `BlogPosting.author` release checks.
- Added author distribution guidance for ten-article portfolios.
- Marked the legacy `VERTU Guide Desk` ineligible for new automated assignments.

## 3.0.0 — 2026-07-12

Breaking editorial and automation update based on the 2025-07-10 to 2026-07-09 VERTU Google Discover audit and the user's requirement that qualified traffic and Discover recommendation are the workflow outcome.

- Added a finalised 365-day GSC Discover/Search baseline before topic selection.
- Replaced the generic topic score with a Discover-first 100-point model and an 80-point threshold.
- Added ten-article portfolio diversity rules and a 30-candidate requirement.
- Added vetoes for abstract B2B low-audience topics, batch cluster overload, generic visuals, thin updates, and template-dependent articles.
- Added editorial depth ranges by article type and mandatory article-specific value objects.
- Added a separate `DISCOVER_READY` gate after independent QA.
- Added concrete Discover image requirements and rejected generic black-and-gold technology backgrounds.
- Added visible byline and `BlogPosting.author` verification.
- Added 24-hour, 7-day, and 28-day Discover/Search/GA4 performance feedback.
- Changed scheduled `max_articles` from 1 to 10 while preserving `0–10` output and `NO_TOPIC` rather than filler.

Source evidence: user feedback on the 2026-07-11 ten-article batch; one-year GSC Discover totals and top-page/topic analysis; current Google Discover and people-first documentation.

# Topic Selection Contract — Traffic Acquisition v3.8.0

Topic selection is the highest-leverage stage. The goal is a current or durable reader need where VERTU can add a credible, distinctive perspective and where real performance evidence supports Discover or Search opportunity.

## Required performance baseline

When GSC access is available, read the previous 365 days of finalised Discover and Search data before topic discovery. Store totals, top pages, topic clusters, CTR, recent changes, and high-impression opportunities in `discover-baseline.json`.

Use historical performance as evidence, not a template. Do not clone a successful article, repeat the same intent, or infer causality from one spike.

## VERTU audience-market fit

Apply the user's standing editorial strategy before broad candidate expansion. Classify each serious candidate:

- `PREMIUM_DECISION_CORE`: a mass-recognisable premium, business, executive or collector subject with a concrete choice and demonstrated VERTU audience adjacency;
- `ADJACENT`: relevant to the same audience but with weaker historical fit, narrower recognition or a less direct decision;
- `EXPLORATION`: outside proven VERTU clusters and therefore eligible only as a controlled test after the normal demand gate passes. Before demand validation, record it as `EXPLORATION_CANDIDATE`; do not imply that it has earned a test slot.

Core examples include commercial-airline cabins and airport services, executive phones/privacy/business technology, watches/collecting/craft, and familiar luxury-purchase comparisons. These examples guide candidate creation; they are not pre-approved topics.

For every classification record:

- mass recognisability and the target reader population;
- the exact decision, value, upgrade, ownership, route, seat, fit or how-to-choose intent;
- finalised GSC cluster or adjacent-page evidence;
- candidate-level demand providers;
- niche-risk and cannibalisation notes;
- why the topic is broader or narrower than a previous winner.

Do not classify a topic as core merely because its title contains `luxury`, `high-end`, `business`, `premium`, a large price or an exclusive service. Private aviation, yachts, ultra-niche access, generic hotel lists and abstract B2B remain normal candidates and often require stronger evidence because affluent does not mean broad.

The audience-fit lane shapes candidate generation and portfolio framing. It is not a demand provider, does not change the raw score, and cannot waive a veto.

Keep historical audience fit separate from candidate-level demand. A successful GSC cluster or adjacent page can support the `Historical VERTU/GSC fit` dimension, but it is not a positive demand provider for a new query unless the candidate record contains finalised query/page evidence for that same normalised intent. Score the underlying evidence once; never add a lane bonus for evidence already used in the score.

## Candidate sources

- explicit user ideas and supplied sources;
- the mandatory same-day Hermes RSS and editorial-synthesis chain defined in `editorial-intelligence.md`;
- Cipher's current hot-topic feed, when available;
- primary AI/LLM/technology announcements;
- research papers and official technical documentation;
- cyber.fund and high-quality essays with an original framework;
- current search demand and content-performance evidence;
- questions raised by VERTU customers, products, and services;
- existing VERTU content gaps.

Before using these sources, read `editorial-intelligence.md` and `realtime-trends.md`. Consume the same-day Hermes intelligence chain first, then fetch official Google Trends Trending Now evidence across the configured markets. Do not infer a real-time surge from monthly Keyword Planner volume, broad GSC cluster performance or community engagement.

Read `performance-learning.md` and both active fingerprinted prior artifacts before scoring. Unexpired provisional and durable priors may reorder only candidates that already pass the normal traffic gate; preliminary data and prose summaries cannot create demand.

Do not select from a headline alone. Open the primary source and establish what happened.

## Candidate-level traffic evidence

Read `traffic-demand-gate.md` and `realtime-trends.md` completely. The 365-day baseline establishes audience fit but does not select an individual topic. Every serious candidate must preserve its own GSC, trend/current-interest, Keyword Planner when authorised, SERP, inventory and cluster-support evidence with source status and fetch time.

Every candidate must also declare `REALTIME_HOT`, `RISING_SEARCH` or `EVERGREEN_SEARCH`, plus the relevant markets, and one pre-gate audience-fit lane from `PREMIUM_DECISION_CORE | ADJACENT | EXPLORATION_CANDIDATE`. Only verified official Google Trends evidence observed within 24 hours may support `REALTIME_HOT`.

Separately record `EDITORIAL_BREAKOUT | CURRENT_CONFIRMED | NONE`. A verified editorial breakout can satisfy the current-interest portion of a Discover-first candidate, but it is never a Google demand provider and does not change the candidate's Google trend class.

Do not accept a per-run `topic: 94` or similar final score. Calculate the final value with the reusable deterministic scorer under this v3.8.0 contract and pass the editorial artifacts whenever a breakout is declared. Missing sources remain explicit; missing required evidence rejects or holds the topic. Pass `--learning-priors` for validated durable evidence and `--provisional-learning-priors` for validated unexpired provisional evidence. Preserve the raw computed score separately from `selection_priority_score`; the combined learned adjustment is bounded to `-3..+3` and cannot change eligibility.

## Traffic-acquisition scoring model

| Dimension | Weight | Passing evidence |
|---|---:|---|
| Market demand | 25 | Two independent positive providers for Search-first, or the required Discover evidence pattern |
| Historical VERTU/GSC fit | 20 | GSC supports the cluster, adjacent need, or defensible gap |
| Trend velocity or timeliness | 15 | Rising/seasonal interest or a verified current event exists |
| SERP and content gap | 15 | The result set leaves a concrete answer, decision or freshness gap |
| Discover story and packaging | 10 | A timely consequence and concrete feed-readable visual exist |
| Original information gain | 10 | Adds a verified matrix, calculator, checklist, synthesis or original evidence |
| VERTU right to win | 5 | VERTU has a relevant audience or expertise relationship without forced insertion |

Threshold: `80/100`, plus no veto.

## Vetoes

Reject regardless of score:

- `forced_brand_insertion`: VERTU can only appear as an unrelated promotion;
- `duplicate_intent`: existing VERTU content already satisfies the intent without a material update;
- `weak_evidence`: the article depends on rumours or unverifiable numbers;
- `traffic_only`: selected only because it is trending;
- `outside_authority`: VERTU has no credible expertise or audience relationship;
- `regulated_claim_dependency`: thesis depends on unconfirmed medical, financial, legal, environmental, or security promises;
- `stale_event`: no longer current and no durable evergreen angle exists;
- `no_answer`: title promises certainty unavailable from the evidence.
- `abstract_b2b_low_audience_fit`: an operator, governance, or marketing topic lacks proven VERTU reader demand;
- `batch_cluster_overload`: more than three selected articles share the same entity, intent, or abstract theme;
- `generic_visual_only`: the topic cannot support a relevant, concrete Discover image;
- `thin_update`: a date or model name changed but the reader value did not;
- `template_dependency`: the article only works by adding a generic list, FAQ, or VERTU paragraph.
- `third_party_newsroom_misplacement`: a competitor or third-party announcement is proposed for the VERTU `/news/` section instead of an editorial analysis section.
- `insufficient_demand_evidence`: the candidate does not meet its outcome lane's independent demand-signal rule;
- `untraceable_score`: any final score or dimension lacks the required evidence and observation time;
- `cannibalisation_without_plan`: the candidate overlaps an existing VERTU intent without a consolidation or query-boundary plan.
- `premium_label_only`: luxury, high-end, business, exclusivity or price is the only audience or traffic rationale;
- `niche_affluence_without_demand`: a very small affluent service or purchase lacks the normal candidate-level demand evidence required by its lane.
- `no_defensible_content_gap`: the current result set and VERTU inventory already answer the intent and the proposal adds no concrete information gain.

## Search and content-gap checks

1. Search the dominant query and inspect result types.
2. Classify intent: informational, comparative, transactional, navigational, or mixed.
3. Query the existing Sanity/site inventory by topic, entities, and intent.
4. Record the gap: missing explanation, outdated facts, weak executive framing, absent privacy analysis, or absent product evidence.
5. Define incremental value in one sentence.
6. Check the previous 365-day Discover cluster and the previous 28-day trend.
7. Define the concrete image subject and feed-visible focal point.
8. Record whether the topic is Discover-first, Search-first, or Authority-first.
9. Record provider-level demand evidence and source-unavailable states.
10. Define cluster role, query boundary, outbound destination and inbound-link candidates.
11. Classify audience fit, mass recognisability, concrete decision intent and niche risk.

If the incremental-value sentence is vague, reject or reframe.

Two providers are independent only when they come from different acquisition evidence systems and do not merely repeat the same upstream estimate. Accepted positive Search-first providers are candidate-level finalised GSC query/page evidence, official Google Trends comparison evidence, and authorised Google Ads Keyword Planner evidence. SERP observations, Hermes/editorial velocity, social engagement, historical cluster adjacency and primary-source timeliness are supporting evidence, not independent Search-demand providers.

## Topic brief

`topic-brief.md`:

```markdown
# Topic Brief

- Working title:
- Primary query / reader question:
- Intended reader:
- Audience-fit lane: PREMIUM_DECISION_CORE | ADJACENT | EXPLORATION
- Mass recognisability and audience scale:
- Concrete premium/business/collector decision:
- Historical cluster evidence:
- Niche-risk boundary:
- Event date / freshness window:
- One-sentence thesis:
- Why VERTU has the right to write this:
- Incremental value over existing results:
- Natural product/service connection, if any:
- Primary sources:
- Existing VERTU overlap:
- Discover cluster evidence:
- Search opportunity evidence:
- Demand providers and source states:
- Editorial signal and source-velocity evidence:
- Trend class and target markets:
- Trends observation time, age and approximate traffic:
- Recent 28-day change:
- Keyword Planner evidence or unavailable reason:
- SERP gap evidence:
- Cluster role and query boundary:
- Outbound internal destination:
- Candidate inbound-link sources:
- Concrete reader decision:
- Visual story:
- Outcome lane: Discover-first | Search-first | Authority-first
- Risks / unknowns:
- Computed score and breakdown: 00/100
- Demand verdict: STRONG | TEST | HOLD | REJECT
- Verdict: SELECT | REJECT | HOLD
```

## Automation behaviour

- Score at least three credible candidates when the source pool permits.
- For a ten-article batch, score at least 30 candidates when the source pool permits.
- Select no more than `max_articles`.
- Prefer `NO_TOPIC` over a weak article.
- Do not repeat the same entity or intent within seven days unless a material event occurred.
- Package a material event as one event/opportunity page plus no more than two distinct search-intent support pages. Define query boundaries and publish the event page first.
- Record rejected candidates so later runs do not rediscover the same weak angle without new evidence.

## Traffic-weighted portfolio contract

After every candidate independently passes, use these soft targets:

- about 50% proven or adjacent Search/Discover demand;
- about 30% rising current interest suitable for Discover;
- up to 20% controlled exploration or VERTU authority.

Use consumer-decision, craft, technology, privacy, travel and VERTU authority lanes as diversity guidance, not quotas. Do not force a weak lane to fill a slot. Never select more than three adjacent intents or more than three articles dominated by the same entity. The portfolio should include multiple relevant VERTU interest clusters when enough candidates pass.

When enough candidates independently pass, use a soft audience-fit mix of roughly 50–70% `PREMIUM_DECISION_CORE` across at least three distinct clusters, 20–30% `ADJACENT`, and no more than 20% `EXPLORATION`. This mix never lowers the score or demand threshold. A premium-labelled candidate that fails normally remains rejected even when the core allocation is empty.

When `trend_mode: realtime_hot`, consider verified `REALTIME_HOT` candidates first, then `RISING_SEARCH`, before durable evergreen candidates. Do not lower the score threshold or select traffic-only celebrity, sport, politics or general-news topics outside VERTU audience authority. Report the final trend-class distribution without describing the whole portfolio as hot unless the evidence supports it.

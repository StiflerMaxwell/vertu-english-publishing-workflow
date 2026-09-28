# VERTU Signals Writing Contract

## Editorial purpose

VERTU Signals should help a sophisticated, globally minded reader understand an important change in AI, technology, privacy, craftsmanship, personal productivity, or luxury service.

The article must have a point of view. It must not be a translation, source summary, keyword container, or product advertisement disguised as analysis.

For premium and business themes, make the real reader decision explicit: value, upgrade, route, seat, ownership, fit, privacy, collectability or how to choose. Price and exclusivity alone are not an argument. A narrow affluent service must not be written as though it has mass relevance.

For Discover-first work, the article must also have a story: a timely change, a recognisable object, a collector or buyer decision, a consequence, and a visual subject that can be understood in a feed.

## Voice

Use:

- calm authority supported by specifics;
- intelligent but accessible explanations;
- precise nouns and concrete examples;
- measured confidence and explicit uncertainty;
- an international, executive perspective where relevant;
- UK English (`en-GB`) by default.

Avoid:

- generic phrases such as “where luxury meets innovation”;
- inflated novelty claims;
- breathless affiliate tone;
- repetitive “not just X, but Y” constructions;
- “in today's fast-paced world” openings;
- empty future-of-technology conclusions;
- forced VERTU mentions;
- fake personal experience;
- unsupported rankings, comparisons, reviews, or media mentions.

## Author and section

- Editorial identity comes from the approved registry in `author-policy.md`. Automated work uses transparent institutional editorial desks rather than invented individuals.
- Target route/section: `/ai-tools/` by default.
- Language: `en-GB`.

Section routing policy:

- `/news/` is reserved for first-party VERTU announcements, official company statements, verified VERTU product launches, VERTU events, and media-safe corporate updates.
- Third-party product launches, competitor announcements, and external technology events must not be presented as VERTU newsroom content. Route consumer interpretation to `/guides/`, technology analysis to `/ai-tools/`, and broader cultural or ownership stories to `/lifestyle/`.
- A timely external event remains editorial analysis even when it is sourced from an official third-party newsroom.

Never guess the Sanity author representation from the editorial identity. Assign the author by dominant topic expertise before drafting; use recent usage only as a tie-break between equally suitable desks.

Before delivery, verify a visible byline or editorial identity and `BlogPosting.author`. Publisher-only structured data is incomplete for this workflow.

## Article argument

Every draft must define:

1. one dominant reader question;
2. its audience-fit lane and the narrowest supported reader cluster;
3. one-sentence thesis;
4. why it is worth reading instead of the source material;
5. one legitimate VERTU perspective;
6. one conclusion earned by evidence.

For production-selected work, the argument must also implement the exact `serp-benchmark-v1` fingerprint and original-value delta in `content-differentiation-brief.md`. Ranking-page structure establishes reader expectations; it is not copy material. If the benchmark requires a decision matrix, market comparison, timeline, calculation or checklist, that object must appear substantively in the final article.

Major-section order should matter. If sections can be shuffled without changing the argument, strengthen the through-line or make the article an explicit list.

## Structure patterns

### Explainer

```text
Direct answer → why it matters → how it works → trade-offs → VERTU perspective → implications
```

### Framework analysis

```text
Problem → framework → levels/components → examples → limitations → VERTU application → conclusion
```

### Comparison

```text
Decision context → criteria → evidence-backed comparison → fit → caveats → conclusion
```

### News-to-insight

```text
What happened → what changed → signal vs noise → consequences → VERTU interpretation → what to watch
```

Do not force a scenario opener when a direct answer serves better.

## Evidence behaviour

- Facts, statistics, dates, specifications, prices, quotes, and attributed opinions require sources.
- Product facts must exist in `product-context.json`.
- External facts must exist in `evidence-pack.md`.
- Original analysis must be distinguishable from reported fact.
- Unresolved claims stay `UNKNOWN` in `claim-ledger.json` and out of publishable prose.
- Important sources must appear in the reader-facing article, not only in a hidden evidence pack.
- Normally expose at least three useful primary or authoritative source links for current analysis; use more when comparison depth requires it.
- Count unique normalised destinations, not anchor tags. Different anchor text pointing to the same URL is still one source.
- Reader-useful authoritative PDFs count as evidence. Image assets, author links, self-links, schema-only URLs, and duplicated destinations do not.
- Fewer than three external sources is allowed only when the supported facts and original synthesis justify an explicit article-specific editorial exception; never add decorative links to satisfy a number.
- Reconcile the final article body against `evidence-pack.md` and `link-plan.json` before delivery so approved sources are not lost during Markdown/HTML/Sanity conversion.
- Reconcile the final article body against `serp-benchmark.json` and `content-differentiation-brief.md`; missing or generic implementation of the declared original value is a required QA fix.

## Product integration

Use VERTU only where it adds explanatory value. Prefer one specific product/service connection over several weak mentions.

Preserve required qualifiers such as:

- “where supported”;
- “with user authorisation”;
- “depending on configuration”;
- “for eligible enterprise clients”;
- “requires private deployment”.

Do not weaken them during editing.

## SEO without template writing

Include a descriptive H1, slug, SEO title, meta description, excerpt, clean hierarchy, concise answer-first passage when useful, meaningful internal/external links, and descriptive image alt text.

Add FAQ only when real recurring questions exist. Do not add tables, lists, dates, or word count merely because a generic template expects them.

Use at most one article-specific VERTU/Concierge integration section. Navigation headings such as `Related VERTU reading` do not count, but two explanatory brand/service sections do. Consolidate duplicate integration before handoff.

The final batch must not repeat a materially identical meaningful H2–H4 sequence after normalising years, punctuation and compared entities. Common navigation and evidence headings such as Sources, Final verdict and Related VERTU reading are excluded from the fingerprint; their presence alone must not create a template finding.

## Depth and article-specific value

| Content type | Normal range | Required value object |
|---|---:|---|
| Timely news-to-insight | 1,000–1,500 words | timeline, implications table, or sourced what-changed summary |
| Practical explainer | 1,200–1,800 words | checklist, decision tree, or concrete worked scenario |
| Buyer guide / comparison | 1,600–2,600 words | verified comparison table and fit-by-reader guidance |
| Pillar / collector guide | 2,200–3,200 words | selection methodology, product/brand matrix, and collector or ownership guidance |

These are not Google ranking targets. They stop thin drafts from passing when the topic requires depth. Never pad to reach a number. Every article must contain at least one article-specific value object. Repeating the same FAQ, four-step framework, or three-item list across a batch fails the editorial pass.

For buyer/comparison work at or above 1,500 substantive words, plan at least one descriptive in-body evidence visual when a factual, rights-safe visual adds decision value. The hero image does not count. Until a controlled experiment establishes a release threshold, absence is recorded as `BODY_VISUAL_MISSING` warning rather than a hard failure; an explicit article-specific exception is preferable to decorative imagery.

## Discover preview contract

- The headline captures the essence and concrete benefit without withholding crucial context.
- Avoid misleading curiosity gaps, unsupported superlatives, outrage, and clickbait.
- Use a specific high-resolution image with a clear focal point that remains legible on mobile.
- Avoid generic luxury-tech abstractions, text-heavy art, logos as heroes, and generated product configurations.
- Record proposed `og:image`, alt text, crop-safe focal point, and why the visual is relevant.

## Link plan

Build links dynamically from the current VERTU inventory. For each link record destination, anchor, source section, reader value, and live-verification status. Do not rely on a stale hardcoded link list. Deduplicate by normalised destination and verify the final rendered canonical HTML after delivery, including the absence of any replaced stale URL.

## Required outputs

### `seo.json`

```json
{
  "title": "",
  "seo_title": "",
  "meta_description": "",
  "slug": "",
  "excerpt": "",
  "language": "en-GB",
  "section": "ai-tools",
  "primary_keyword": "",
  "secondary_keywords": [],
  "search_intent": ""
}
```

### `claim-ledger.json`

```json
{
  "claim": "",
  "article_location": "",
  "label": "KB_APPROVED | LIVE_OFFICIAL | PRIMARY_EXTERNAL | USER_PROVIDED | UNKNOWN",
  "source": "",
  "verified_at": "",
  "publishable": false
}
```

## Editorial pass

After drafting, run a human-voice edit and verify factual sentences against the ledger. The final draft must contain no internal prompts, placeholders, tool tokens, hidden instructions, or AI-interface citation markup.

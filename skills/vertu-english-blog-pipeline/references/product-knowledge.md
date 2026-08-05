# Product Knowledge Contract

## Canonical approved source

Primary VERTU product knowledge:

`${VERTU_PRODUCT_KB_URL}`

Title: `VERTU产品知识库（完整版）`

Treat the URL token as a Wiki node token. Resolve it to the current document token before reading.

## Fetch flow

Use user identity for user-owned Feishu resources.

```bash
lark-cli schema wiki.spaces.get_node
lark-cli wiki spaces get_node \
  --params '{"token":"FMgPwM0kFi0sIzkSpkLc4QYsnKq"}' \
  --as user

lark-cli docs +fetch --doc "<resolved_obj_token>" --as user
```

Record node title, Wiki token, object token, revision ID, object edit time, UTC fetch time, and extracted sections.

If Feishu is unavailable, do not substitute the old local Markdown snapshot as current truth. Mark `PRODUCT_KB_UNAVAILABLE`; the snapshot is historical context only.

## What the knowledge base controls

- approved product positioning;
- approved feature descriptions;
- internal specifications, subject to freshness checks;
- brand terminology;
- required availability and authorisation qualifiers;
- product-specific compliance restrictions;
- prohibited claims.

It is not automatically authoritative for volatile public commerce state.

## Live verification required

Verify at run time against official public product/collection pages and, when available, Shopify or Sanity:

- price and currency;
- models, materials, colours, and variants;
- stock and sale status;
- canonical URL and redirects;
- launch or delivery timing;
- regional availability;
- supported apps and services;
- software-version-dependent features.

Attach `verified_at` and the exact live URL.

## Conflict rules

| Conflict | Resolution |
|---|---|
| Feishu messaging vs external article | Feishu controls approved VERTU messaging |
| Feishu commerce fact vs official live store | Official live store controls current public price/availability |
| Feishu spec vs official product page | Surface the conflict; do not silently choose when material |
| VERTU source vs third party | Use VERTU for first-party facts; third party only for attributed independent analysis |
| Missing knowledge-base fact | Omit or request confirmation; never infer |

## Product Context Pack

Create `product-context.json`:

```json
{
  "knowledge_base": {
    "wiki_token": "FMgPwM0kFi0sIzkSpkLc4QYsnKq",
    "revision_id": null,
    "edited_at": null,
    "fetched_at": null
  },
  "products": [
    {
      "name": "",
      "role_in_article": "",
      "approved_positioning": [],
      "verified_specs": [],
      "volatile_facts": [],
      "required_qualifiers": [],
      "prohibited_claims": [],
      "canonical_url": "",
      "live_verified_at": "",
      "sources": []
    }
  ],
  "conflicts": [],
  "human_confirmation": []
}
```

## Evidence labels

- `KB_APPROVED`: present in the current Feishu knowledge base;
- `LIVE_OFFICIAL`: verified on current official VERTU/Shopify/Sanity;
- `PRIMARY_EXTERNAL`: supported by a primary non-VERTU source;
- `USER_PROVIDED`: explicitly supplied for this run;
- `UNKNOWN`: unsafe to establish and must not be written as fact.

Do not promote inference into a product fact.

## Product inclusion

Product mentions must advance the article's argument: a concrete private-AI example, craftsmanship case, authorised executive workflow, supported comparison dimension, or natural reader next step.

Do not append a generic VERTU paragraph. If no product is relevant, use `products: []` and continue with brand-level or editorial analysis.

# VERTU Brand-Mindset Topic Gate — v1

Apply this permanent pre-score contract to every automatic VERTU English topic. It is an eligibility boundary, not a traffic-scoring dimension: it may reject or hold an off-brand candidate before scoring, but it never adds traffic points, creates demand, changes a Google trend label, waives a veto, or authorises QA or publication.

## Required semantic evidence

Every candidate must predeclare `brand_mindset_predeclared=true` and provide all three evidence rows below before its traffic score is known:

1. `audience_overlap`: high-net-worth, executive, collector, premium-experience or closely related VERTU reader overlap;
2. `mindset_overlap`: rarity, identity, craft, privacy, premium service, ownership value or a high-end decision;
3. `editorial_right_to_win`: a credible reason VERTU Signals can add distinctive reader value without a forced product mention.

Each row uses `PASS | FAIL | SOURCE_UNAVAILABLE | INSUFFICIENT_SAMPLE`, a specific rationale and evidence references. At least two rows must be `PASS`. Missing or ambiguous evidence is `HOLD`, never an inferred pass.

Classify passing candidates as:

- `CORE_MINDSPACE`: all three dimensions pass;
- `QUALIFIED_ADJACENT`: exactly two dimensions pass;
- `UNQUALIFIED`: fewer than two pass or a hard conflict exists.

The class does not add points. The normal deterministic traffic score chooses among candidates that already pass this gate.

## Permanent hard conflicts

Reject regardless of search volume, trend velocity, D2TR, YouTube, learning priors or a high legacy score:

- `COMMODITY_LIFESTYLE_MISMATCH`: generic household, refrigerator, television, sofa, mattress, routine kitchen appliance or equivalent commodity ownership content without a genuine premium/identity/collector decision;
- `FORCED_BRAND_ASSOCIATION`: VERTU relevance exists only as a bolted-on promotion;
- `PRICE_ONLY_LUXURY_LABEL`: expensive, exclusive or celebrity-owned is the entire thesis;
- `OUTSIDE_BRAND_MINDSPACE`: no credible VERTU reader, mindset or editorial relationship.

Do not maintain a rigid allow-list. Use semantic evidence and the permanent conflict rules. Commercial aviation is eligible only for premium cabins, airport services or premium travel decisions; generic aviation and private-jet filler remain outside the boundary unless independently commissioned. VERTU product or Concierge insertion is never mandatory.

## Luxury authority stories

For `LUXURY_AUTHORITY_STORY` such as the world's most expensive phones, watches or collector objects, require at least two verified evidence types:

- `VERIFIED_PRICE_OR_TRANSACTION`;
- `MATERIAL_OR_CRAFT`;
- `SCARCITY_OR_OWNERSHIP`.

A price-only list is `REJECT`. Incomplete verification is `HOLD`.

## Portfolio and expansion

Automatic exploration is disabled. After every candidate independently passes this gate and the unchanged traffic gate:

- recovery profile: prefer roughly 80% `CORE_MINDSPACE`, with no more than 20% `QUALIFIED_ADJACENT`;
- stable profile: prefer 60–80% `CORE_MINDSPACE`, with no more than 40% `QUALIFIED_ADJACENT`.

These are soft portfolio preferences, not permission to force ten articles. For `vertu-10`, evaluate cumulative pools of 30, 60, 90 and 120 distinct leads. Apply the gate before scoring in every round. If fewer than ten articles can pass every gate after the 120 boundary, return truthful `DAILY_QUOTA_BLOCKED`; never fill the batch with unrelated topics.

Keep at most three selected articles with the same entity, intent or title structure and run the normal seven-day duplicate/cannibalisation check after every expansion.

## Artifacts and runtime

Run:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_brand_mindset_gate.py \
  --input candidates.json \
  --output brand-mindset-candidates.json \
  --summary brand-mindset-summary.json
```

Require `brand-mindset-fit-v1`, a valid result fingerprint, `PASS`, and `CORE_MINDSPACE | QUALIFIED_ADJACENT` before scoring. Then call the traffic scorer with `--require-brand-mindset-gate` and the active `--brand-mindset-profile` so missing, tampered, held or rejected evidence fails closed.

Record the class, matched dimensions, rationale, conflicts, expansion round, fingerprint and verdict in local run artifacts and canonical Base lineage. The legacy replay tool is audit-only and has no production or repair authority.

## Measurement and change control

- T+72h: directional observation only;
- D+7: comparison checkpoint;
- D+28: durable evaluation.

Do not relax the gate from same-day traffic. Weakening a permanent conflict or semantic threshold requires explicit user approval or a mature governed Skill-evolution decision. Roll back or pause on contract/fingerprint drift, replay failure, unexplained source state, or more than 20% false rejection of clearly core topics in two audited runs. Existing off-brand pages enter the mature D+28 remediation queue; do not mass-delete or rewrite them automatically.

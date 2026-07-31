# VERTU Editorial Author Policy

Authorship must improve trust through accurate editorial identity and topic accountability. Do not invent individual people, personal histories, qualifications, first-hand experiences, or social profiles. The approved automated bylines are transparent institutional VERTU editorial desks.

## Author registry

| Sanity author ID | Display name | Primary scope |
|---|---|---|
| `author-vertu-buyer-guide-desk` | VERTU Buyer Guide Desk | buyer guides, comparisons, product selection and decision frameworks |
| `author-vertu-ai-innovation-desk` | VERTU AI & Innovation Desk | AI agents, software, emerging technology and consumer impact |
| `author-vertu-watch-craft-desk` | VERTU Watch & Craft Desk | watches, craftsmanship, materials, collecting and ownership |
| `author-vertu-privacy-security-desk` | VERTU Privacy & Security Desk | privacy, secure communications and globally mobile executive risk |
| `author-vertu-concierge-travel-desk` | VERTU Concierge & Travel Desk | concierge, premium travel, disruption and global mobility |
| `author-vertu-product-service-desk` | VERTU Product & Service Desk | VERTU products, services, ownership and first-party authority |

The live Sanity author document is authoritative for name, slug, biography and profile URL. Publishing scripts must reference an existing author; they must never create or reshape an author document as a side effect of publishing an article.

`author-vertu-guide-desk` is a legacy compatibility author and is not eligible for new automated assignments.

## Avatar policy

Active automated authors use square institutional avatars, not invented human portraits. Each avatar must be at least 1000 by 1000 pixels, visually distinct at small size, free of text and logos, have descriptive alt text, and avoid false VERTU product configurations. Store the image as the Sanity author document's `image` field. Missing avatar imagery is an author-profile QA failure for new assignments.

## Assignment rule

Author assignment is expertise-first, not random.

1. Classify the selected article by its dominant reader decision and evidence burden.
2. Choose the registry author whose primary scope most directly covers that decision.
3. If two authors are equally suitable, prefer the author used fewer times in the previous 14 days.
4. If still tied, use a stable tie-break based on the article slug so retries keep the same author.
5. Do not use byline rotation to disguise content volume or imply multiple independent human reviewers.
6. Record the assignment reason in `author-verification.json` before drafting is complete.

Default mappings:

- buyer, comparison, shortlist, how-to-choose → `author-vertu-buyer-guide-desk`;
- AI model, agent, software, device technology change → `author-vertu-ai-innovation-desk`;
- watch, leather, gemstone, materials, craft, collector → `author-vertu-watch-craft-desk`;
- privacy, secure phone, communications, threat model, executive mobility → `author-vertu-privacy-security-desk`;
- travel, concierge, disruption, access, itinerary, global lifestyle → `author-vertu-concierge-travel-desk`;
- VERTU product, service, concierge authority, enterprise capability → `author-vertu-product-service-desk`.

For a mixed article, the dominant reader decision wins. A VERTU product mention alone does not force the Product & Service Desk.

## Release checks

Before any Sanity article mutation:

- query the selected author by exact `_id` and confirm `_type == "author"`;
- verify name, slug, job title, expertise summary, bio and canonical profile URL;
- require `expertise` to be a string and `areasOfExpertise` to be an array of strings;
- require a square author image at least 1000 pixels wide with descriptive alt text;
- verify the public profile URL returns HTTP 200;
- verify the visible article byline links to that profile;
- verify the linked byline is rendered by the page template exactly once; article `rawHtml` and Portable Text must not prepend a duplicate `By ...` paragraph;
- verify `BlogPosting.author.name` and `BlogPosting.author.url` match the selected profile;
- store the author `_rev`, assignment reason and live verification time in `author-verification.json`.

An author page returning 404/500, a missing author reference, a subject mismatch, or a schema/type mismatch is `AUTHOR_BLOCKED`. Do not publish until corrected.

## Batch distribution

In a ten-article portfolio, use at least three relevant desks when the portfolio spans their scopes. Do not assign more than four articles to one desk unless fewer than three scopes are genuinely represented. Distribution never overrides expertise fit.

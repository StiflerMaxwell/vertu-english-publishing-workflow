# Packaged Skills

## `vertu-english-blog-pipeline`

Canonical editorial Skill. It owns demand-led topic selection, research,
writing, evidence, links, authorship and downstream handoff. It does not own QA,
Image Gen or production authority.

## `vertu-seo-publish-gate`

Independent SEO QA gate. It produces PASS/FIX/BLOCK evidence and can authorise a
separate executor to repair a Sanity Draft. It never directly publishes.

Keep these Skills separate. Combining them would allow the writer to define and
approve its own quality gate.

The producer also consumes `vertu-content-loop-runtime-v1` for local
coordination. Runtime acquisition never authorises QA or publication; it only
prevents overlapping writers and unbounded attempts.

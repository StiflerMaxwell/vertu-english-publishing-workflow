# Operations

Read [the current five-article profile](CURRENT-OPERATING-PROFILE.md) and
[creator SOP](CONTENT-CREATOR-HANDOFF.zh-CN.md) first. Public examples are inactive
and draft-only; credentials and standing production authority are not included.

## Pre-run

- validate the canonical Base schema map against live tables;
- verify the scheduled command and current working directory;
- verify current Skill and reference versions;
- audit local loop state and confirm the global pause file is absent unless an
  operator intentionally paused mutations;
- confirm GSC/GA4 source availability without exposing credentials;
- confirm the vvv sender can produce a preview receipt;
- confirm production publication still uses a live-schema mutation preview.

## Safe local checks

```bash
python3 -m pytest scripts/tests skills/vertu-seo-publish-gate/tests --import-mode=importlib
python3 scripts/validate_bundle.py
python3 scripts/vertu_google_trends_realtime.py --help
python3 scripts/vertu_content_traffic_gate.py --help
python3 scripts/vertu_content_learning_flywheel.py --help
python3 scripts/vertu_skill_evolution_scorecard.py --help
python3 scripts/vertu_content_monitor_runtime.py --help
python3 scripts/vertu_content_monitor_base_handoff.py --help
python3 scripts/vertu_daily_publishing_quota.py --help
python3 scripts/vertu_content_loop_runtime.py --help
python3 scripts/vertu_d2tr_discover_monitor.py --help
```

Notification preview:

```bash
pnpm notify:preview -- \
  --body-file ./path/to/vvv-receipt-message.txt \
  --receipt-file ./path/to/vvv-notification.preview.json
```

## Production sequence

Production may proceed only after the start ledger exists and all article-level
gates pass. Never interpret a successful Sanity mutation as publication success
until the live page and canonical Base handoff both pass.

Before protected writes, acquire exact mutation scopes through
`vertu_content_loop_runtime.py`. A local `ALLOW` receipt is advisory
coordination, not publication approval. Release only owned scopes after the
terminal domain decision; `RELEASE_INCOMPLETE` is a handoff blocker.

The final receipt must include full, partial, no-op and blocked states. Group
delivery is successful only when the receipt status is `SENT`.

## Performance loop

- 24h: technical and preliminary GA4 check;
- 72h: mature GSC Search/Discover classification when sample gates pass;
- 7d: controlled optimisation and provisional learning;
- 28d: durable portfolio review and governed prior eligibility;
- twice daily: check whether new observations require expiry, rollback or a
  proposal; traffic-affecting promotion still requires mature D+28 or verified
  experiment evidence.

Checkpoint rows are immutable. `CURRENT`, `SUPERSEDED` and `HISTORICAL` are
lifecycle metadata only and must never overwrite the original metrics.

Learning artifacts must preserve fingerprints and evidence lineage. A learned
prior cannot create demand, turn a topic hot, waive QA or clone a winner.

# Operations

## Pre-run

- validate the canonical Base schema map against live tables;
- verify the scheduled command and current working directory;
- verify current Skill and reference versions;
- confirm GSC/GA4 source availability without exposing credentials;
- confirm the vvv sender can produce a preview receipt;
- confirm production publication still uses a live-schema mutation preview.

## Safe local checks

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 scripts/validate_bundle.py
python3 scripts/vertu_google_trends_realtime.py --help
python3 scripts/vertu_content_traffic_gate.py --help
python3 scripts/vertu_content_learning_flywheel.py --help
python3 scripts/vertu_skill_evolution_scorecard.py --help
python3 scripts/vertu_content_monitor_runtime.py --help
python3 scripts/vertu_content_monitor_base_handoff.py --help
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

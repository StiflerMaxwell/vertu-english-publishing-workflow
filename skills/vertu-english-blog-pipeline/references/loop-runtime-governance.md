# Content Loop Runtime Governance — v1

This contract coordinates the local VERTU producer, QA, monitor, repair, trend and learning loops. It adds orchestration safety around the existing domain gates; it does not replace them.

Contract: `vertu-content-loop-runtime-v1`.

## 1. Source of truth

- Canonical Feishu Base remains the operational audit system of record.
- Exact Sanity document revisions, QA identities and live-page evidence remain authoritative for publication decisions.
- `${VERTU_PDCA_ROOT}/output/vertu-signals/control/loop-state.json` is a local current-state pointer used only for coordination.
- `${VERTU_PDCA_ROOT}/output/vertu-signals/control/locks/` contains local advisory write-scope leases.
- A local runtime `ALLOW` receipt is necessary before a protected mutation, but it never proves that a traffic, QA, publication or Base handoff gate passed.

## 2. Loop ownership

Each mutation scope has one owner at a time.

| Loop | Owned mutation scope | Explicitly excluded |
| --- | --- | --- |
| Producer | New current-run article IDs and publication-run lineage | Historical repairs, QA verdicts, monitoring observations |
| QA | QA Runs and Findings for one exact source identity | Sanity publication mutation |
| Monitor | Monitoring-run and checkpoint rows | Sanity content mutation, experiment approval |
| Repair | One queued existing document and its repair execution row | A document currently claimed by producer or another repair |
| Trend | Fingerprinted trend snapshots and active pointer | Search-demand verdicts, article mutation |
| Learning/release | Governed prior pointers and Skill Change Log | Article mutation, veto waiver, demand creation |

Use stable scopes such as:

```text
publication-run:<run-id>
sanity-doc:<document-id>
base-record:<table-role>:<deterministic-business-key>
active-pointer:<pointer-role>
skill-release:<skill-id>
```

Do not place credentials, private source text or tokens in a scope.

## 3. Mandatory startup gate

Before any protected local pointer, canonical Base, Sanity, or Skill release mutation:

1. Derive the deterministic execution ID.
2. Write `loop-runtime-manifest.json` with loop type, mode, write scopes, start time, lease, usage, limits and attempts.
3. Run:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_content_loop_runtime.py acquire \
  --manifest <run-path>/loop-runtime-manifest.json \
  --state ${VERTU_PDCA_ROOT}/output/vertu-signals/control/loop-state.json \
  --locks-dir ${VERTU_PDCA_ROOT}/output/vertu-signals/control/locks \
  --pause-file ${VERTU_PDCA_ROOT}/output/vertu-signals/control/PAUSE_ALL \
  --receipt <run-path>/loop-runtime-acquire.json
```

4. Continue protected mutations only on `ALLOW`.
5. `READ_ONLY_ALLOW` authorises read-only work only; it must never be upgraded to mutation authority inside the run.

The existing canonical Base start-ledger write remains mandatory. If either the local runtime gate or Base start ledger fails, perform zero protected production mutations.

## 4. Required manifest budgets

Every loop declares positive limits and current non-negative usage for:

- `max_runtime_seconds`;
- `max_child_tasks`;
- `max_candidates`;
- `max_attempts_per_scope`.

The named `vertu-10` producer keeps the approved 120-candidate editorial boundary. The runtime budget may stop repeated or concurrent work, but it may not lower the article score threshold, change demand evidence, waive a veto, bypass QA, count an incomplete handoff or redefine daily quota success.

When a limit is reached:

- `BUDGET_BLOCKED`: stop the current attempt and terminalise truthfully;
- `ATTEMPT_LIMIT`: preserve the repeated failure and do not create a fresh execution identity merely to bypass the limit;
- do not start additional child tasks after the decision;
- do not mutate Sanity or canonical Base domain tables beyond the required blocker/audit receipt.

## 5. Collision and lease rules

- `COLLISION_BLOCKED` means another unexpired execution owns at least one requested write scope. Perform zero requested mutations.
- Never delete, overwrite or rename another live execution's claim.
- A structurally valid expired claim may be reclaimed only while the runtime process mutex is held. Record the previous execution ID in the acquire receipt.
- A malformed state or lock is `STATE_INVALID` and fails closed. Preserve it for diagnosis.
- Retrying the same run reuses the deterministic execution ID and the same run directory.
- A changed scope or materially changed source revision requires a new governed manifest and the normal domain preflight.

## 6. Pause and kill switch

The file `${VERTU_PDCA_ROOT}/output/vertu-signals/control/PAUSE_ALL` is the local global mutation kill switch.

While present:

- acquire returns `PAUSED`;
- producer, repair, learning release and pointer mutations stop;
- read-only audit remains allowed;
- do not remove the pause file automatically;
- receipts must state that the operator pause was observed.

## 7. Release and terminalisation

After one terminal domain decision, release the local scopes:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_content_loop_runtime.py release \
  --execution-id <execution-id> \
  --terminal-state <terminal-state> \
  --state ${VERTU_PDCA_ROOT}/output/vertu-signals/control/loop-state.json \
  --locks-dir ${VERTU_PDCA_ROOT}/output/vertu-signals/control/locks \
  --receipt <run-path>/loop-runtime-release.json
```

- Release removes only claims owned by the exact execution.
- A repeated successful release is `ALREADY_RELEASED` and is safe.
- `RELEASE_INCOMPLETE` is a governance blocker. Preserve missing/foreign scope evidence and do not claim the full automation chain completed.
- Update the canonical Base execution row independently; local release is not a substitute for Base terminalisation.

## 8. Health audit and stale work

Run the audit command at least twice daily before the governed learning/release check:

```bash
python3 ${VERTU_PDCA_ROOT}/scripts/vertu_content_loop_runtime.py audit \
  --state ${VERTU_PDCA_ROOT}/output/vertu-signals/control/loop-state.json \
  --locks-dir ${VERTU_PDCA_ROOT}/output/vertu-signals/control/locks \
  --pause-file ${VERTU_PDCA_ROOT}/output/vertu-signals/control/PAUSE_ALL \
  --receipt <run-path>/loop-health.json
```

`DEGRADED` audit findings include expired claims, orphan locks, malformed locks and running executions with missing claims. Audit reports; it does not silently repair malformed evidence or mutate article content.

## 9. Feedback-source degradation

Runtime health and content evidence are separate.

- Repeated GA4/GSC/D2TR/Base source failures remain `SOURCE_BLOCKED`; never convert them to zeros.
- A blocked monitor cannot create provisional or durable learning evidence.
- A producer may continue only using the normal independently positive demand sources that are actually available. It must report unavailable fast-feedback layers and zero adjustment from them.
- Consecutive identical blocker pulses are operational evidence, not ten new repair tasks. Deduplicate by deterministic execution/checkpoint identity and changed failure fingerprint.
- Source recovery must be verified by a successful live query and canonical readback before the source is reported healthy.

## 10. Receipt requirements

Every governed loop records:

- execution and automation IDs;
- loop type and mode;
- requested, acquired, reclaimed and released scopes;
- budget limits and observed usage;
- attempt counts;
- pause/collision/state blockers;
- acquire and release receipt fingerprints;
- canonical Base audit/handoff state;
- terminal domain state.

Never expose credentials in manifests, state, locks, receipts, Base details or notifications.

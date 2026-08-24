import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_content_loop_runtime.py"
SPEC = importlib.util.spec_from_file_location("vertu_content_loop_runtime", MODULE_PATH)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)


NOW = dt.datetime(2026, 8, 24, 4, 0, tzinfo=dt.timezone.utc)


def manifest(**overrides):
    payload = {
        "contract_version": "vertu-content-loop-runtime-v1",
        "execution_id": "vertu-10-20260824T010000Z",
        "automation_id": "vertu-10",
        "loop_type": "producer",
        "mode": "mutating",
        "started_at": "2026-08-24T01:00:00Z",
        "lease_seconds": 3600,
        "write_scopes": ["publication-run:2026-08-24:daily-10"],
        "limits": {
            "max_runtime_seconds": 14400,
            "max_child_tasks": 12,
            "max_candidates": 120,
            "max_attempts_per_scope": 3,
        },
        "usage": {"runtime_seconds": 60, "child_tasks": 0, "candidates": 30},
        "attempts": {},
    }
    payload.update(overrides)
    return payload


class LoopRuntimeTests(unittest.TestCase):
    def paths(self, root):
        return root / "loop-state.json", root / "locks", root / "PAUSE_ALL"

    def test_read_only_loop_creates_no_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            result = runtime.acquire(
                manifest(mode="read_only", write_scopes=[], loop_type="monitor"),
                state_path=state,
                locks_dir=locks,
                pause_file=pause,
                now=NOW,
            )
            self.assertEqual(result["decision"], "READ_ONLY_ALLOW")
            self.assertEqual(list(locks.glob("*.json")), [])

    def test_second_execution_cannot_acquire_active_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            first = runtime.acquire(
                manifest(), state_path=state, locks_dir=locks, pause_file=pause, now=NOW
            )
            second = runtime.acquire(
                manifest(execution_id="repair-20260824T040100Z", automation_id="repair", loop_type="repair"),
                state_path=state,
                locks_dir=locks,
                pause_file=pause,
                now=NOW + dt.timedelta(minutes=1),
            )
            self.assertEqual(first["decision"], "ALLOW")
            self.assertEqual(second["decision"], "COLLISION_BLOCKED")
            self.assertEqual(len(list(locks.glob("*.json"))), 1)

    def test_expired_scope_is_reclaimed_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            runtime.acquire(
                manifest(lease_seconds=60),
                state_path=state,
                locks_dir=locks,
                pause_file=pause,
                now=NOW,
            )
            result = runtime.acquire(
                manifest(execution_id="repair-20260824T040200Z", automation_id="repair", loop_type="repair"),
                state_path=state,
                locks_dir=locks,
                pause_file=pause,
                now=NOW + dt.timedelta(minutes=2),
            )
            self.assertEqual(result["decision"], "ALLOW")
            self.assertEqual(
                result["reclaimed_scopes"][0]["previous_execution_id"],
                "vertu-10-20260824T010000Z",
            )

    def test_pause_file_blocks_all_mutating_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            pause.write_text("operator pause\n", encoding="utf-8")
            result = runtime.acquire(
                manifest(), state_path=state, locks_dir=locks, pause_file=pause, now=NOW
            )
            self.assertEqual(result["decision"], "PAUSED")
            self.assertEqual(list(locks.glob("*.json")), [])

    def test_budget_limit_blocks_before_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            result = runtime.acquire(
                manifest(usage={"runtime_seconds": 60, "child_tasks": 0, "candidates": 120}),
                state_path=state,
                locks_dir=locks,
                pause_file=pause,
                now=NOW,
            )
            self.assertEqual(result["decision"], "BUDGET_BLOCKED")
            self.assertIn("BUDGET_REACHED:candidates", result["blockers"])

    def test_attempt_limit_blocks_before_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            scope = "publication-run:2026-08-24:daily-10"
            result = runtime.acquire(
                manifest(attempts={scope: 3}),
                state_path=state,
                locks_dir=locks,
                pause_file=pause,
                now=NOW,
            )
            self.assertEqual(result["decision"], "ATTEMPT_LIMIT")
            self.assertEqual(list(locks.glob("*.json")), [])

    def test_attempt_limit_does_not_block_idempotent_resume_of_owned_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            scope = "publication-run:2026-08-24:daily-10"
            runtime.acquire(
                manifest(), state_path=state, locks_dir=locks, pause_file=pause, now=NOW
            )
            result = runtime.acquire(
                manifest(attempts={scope: 3}),
                state_path=state,
                locks_dir=locks,
                pause_file=pause,
                now=NOW + dt.timedelta(minutes=1),
            )
            self.assertEqual(result["decision"], "ALLOW")
            self.assertEqual(result["existing_owned_scopes"], [scope])
            lock = json.loads(runtime._scope_path(locks, scope).read_text(encoding="utf-8"))
            self.assertEqual(lock["expires_at"], "2026-08-24T05:01:00Z")

    def test_release_is_owner_checked_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            runtime.acquire(
                manifest(), state_path=state, locks_dir=locks, pause_file=pause, now=NOW
            )
            first = runtime.release(
                "vertu-10-20260824T010000Z",
                "SUCCESS",
                state_path=state,
                locks_dir=locks,
                now=NOW + dt.timedelta(minutes=10),
            )
            second = runtime.release(
                "vertu-10-20260824T010000Z",
                "SUCCESS",
                state_path=state,
                locks_dir=locks,
                now=NOW + dt.timedelta(minutes=11),
            )
            self.assertEqual(first["decision"], "RELEASED")
            self.assertEqual(second["decision"], "ALREADY_RELEASED")
            self.assertEqual(list(locks.glob("*.json")), [])

    def test_audit_flags_orphan_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            locks.mkdir(parents=True)
            scope = "skill:vertu-english-blog-pipeline"
            path = runtime._scope_path(locks, scope)
            path.write_text(
                json.dumps(
                    {
                        "contract_version": "vertu-content-loop-runtime-v1",
                        "scope": scope,
                        "execution_id": "missing-execution",
                        "automation_id": "release",
                        "loop_type": "release",
                        "acquired_at": "2026-08-24T03:00:00Z",
                        "expires_at": "2026-08-24T05:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            result = runtime.audit(
                state_path=state, locks_dir=locks, pause_file=pause, now=NOW
            )
            self.assertEqual(result["decision"], "DEGRADED")
            self.assertEqual(result["orphan_locks"][0]["execution_id"], "missing-execution")

    def test_malformed_lock_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            state, locks, pause = self.paths(root)
            locks.mkdir(parents=True)
            scope = "publication-run:2026-08-24:daily-10"
            runtime._scope_path(locks, scope).write_text("not-json", encoding="utf-8")
            with self.assertRaises(runtime.LoopRuntimeError):
                runtime.acquire(
                    manifest(), state_path=state, locks_dir=locks, pause_file=pause, now=NOW
                )


if __name__ == "__main__":
    unittest.main()

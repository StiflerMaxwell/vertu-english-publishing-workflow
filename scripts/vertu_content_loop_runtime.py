#!/usr/bin/env python3
"""Coordinate bounded local VERTU content loops with atomic scope leases."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


CONTRACT_VERSION = "vertu-content-loop-runtime-v1"
STATE_VERSION = "vertu-content-loop-state-v1"
LOOP_TYPES = {"producer", "qa", "monitor", "repair", "trend", "learning", "release"}
RUN_MODES = {"read_only", "mutating"}
DEFAULT_RETENTION_DAYS = 30
MAX_LEASE_SECONDS = 24 * 60 * 60
EXIT_CODES = {
    "ALLOW": 0,
    "READ_ONLY_ALLOW": 0,
    "RELEASED": 0,
    "ALREADY_RELEASED": 0,
    "HEALTHY": 0,
    "DEGRADED": 1,
    "PAUSED": 3,
    "COLLISION_BLOCKED": 4,
    "RELEASE_INCOMPLETE": 4,
    "BUDGET_BLOCKED": 5,
    "ATTEMPT_LIMIT": 6,
    "STATE_INVALID": 7,
}


class LoopRuntimeError(ValueError):
    """Raised when runtime input or persisted coordination state is unsafe."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise LoopRuntimeError(f"{field} must be a non-empty ISO-8601 string")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise LoopRuntimeError(f"{field} must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise LoopRuntimeError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LoopRuntimeError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_int(value: Any, field: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise LoopRuntimeError(f"{field} must be a positive integer")
    if maximum is not None and value > maximum:
        raise LoopRuntimeError(f"{field} cannot exceed {maximum}")
    return value


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LoopRuntimeError(f"{field} must be a non-negative integer")
    return value


def _normalise_scope(value: Any) -> str:
    scope = _non_empty_string(value, "write_scopes entry")
    if len(scope) > 512:
        raise LoopRuntimeError("write scope cannot exceed 512 characters")
    if any(ord(char) < 32 for char in scope):
        raise LoopRuntimeError("write scope cannot contain control characters")
    return scope


def _scope_path(locks_dir: Path, scope: str) -> Path:
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()
    return locks_dir / f"{digest}.json"


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


@contextmanager
def _runtime_mutex(locks_dir: Path) -> Iterator[None]:
    locks_dir.mkdir(parents=True, exist_ok=True)
    mutex_path = locks_dir / ".runtime.lock"
    with mutex_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _new_state(now: datetime) -> dict[str, Any]:
    return {
        "contract_version": STATE_VERSION,
        "updated_at": _iso(now),
        "executions": {},
    }


def _load_state(path: Path, now: datetime) -> dict[str, Any]:
    if not path.exists():
        return _new_state(now)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LoopRuntimeError(f"state file is unreadable: {path}") from exc
    if not isinstance(payload, dict) or payload.get("contract_version") != STATE_VERSION:
        raise LoopRuntimeError(f"state file must use {STATE_VERSION}")
    executions = payload.get("executions")
    if not isinstance(executions, dict):
        raise LoopRuntimeError("state executions must be an object")
    return payload


def _prune_state(state: dict[str, Any], now: datetime, retention_days: int) -> None:
    cutoff = now - timedelta(days=retention_days)
    executions = state["executions"]
    for execution_id, row in list(executions.items()):
        if not isinstance(row, dict):
            raise LoopRuntimeError(f"state execution is invalid: {execution_id}")
        if row.get("status") == "RUNNING":
            continue
        completed_at = row.get("completed_at")
        if completed_at and _parse_time(completed_at, "completed_at") < cutoff:
            del executions[execution_id]


def _validate_manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LoopRuntimeError("manifest must be a JSON object")
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise LoopRuntimeError(f"contract_version must equal {CONTRACT_VERSION}")
    execution_id = _non_empty_string(payload.get("execution_id"), "execution_id")
    automation_id = _non_empty_string(payload.get("automation_id"), "automation_id")
    loop_type = _non_empty_string(payload.get("loop_type"), "loop_type")
    if loop_type not in LOOP_TYPES:
        raise LoopRuntimeError(f"loop_type must be one of {sorted(LOOP_TYPES)}")
    mode = _non_empty_string(payload.get("mode"), "mode")
    if mode not in RUN_MODES:
        raise LoopRuntimeError(f"mode must be one of {sorted(RUN_MODES)}")
    started_at = _parse_time(payload.get("started_at"), "started_at")
    lease_seconds = _positive_int(
        payload.get("lease_seconds"), "lease_seconds", maximum=MAX_LEASE_SECONDS
    )

    raw_scopes = payload.get("write_scopes", [])
    if not isinstance(raw_scopes, list):
        raise LoopRuntimeError("write_scopes must be a list")
    scopes: list[str] = []
    seen: set[str] = set()
    for value in raw_scopes:
        scope = _normalise_scope(value)
        if scope in seen:
            raise LoopRuntimeError(f"duplicate write scope: {scope}")
        seen.add(scope)
        scopes.append(scope)
    if mode == "mutating" and not scopes:
        raise LoopRuntimeError("mutating mode requires at least one write scope")
    if mode == "read_only" and scopes:
        raise LoopRuntimeError("read_only mode cannot declare write scopes")

    limits = payload.get("limits")
    usage = payload.get("usage")
    attempts = payload.get("attempts", {})
    if not isinstance(limits, dict) or not isinstance(usage, dict):
        raise LoopRuntimeError("limits and usage must be objects")
    if not isinstance(attempts, dict):
        raise LoopRuntimeError("attempts must be an object")

    normalised_limits = {
        "max_runtime_seconds": _positive_int(
            limits.get("max_runtime_seconds"), "limits.max_runtime_seconds"
        ),
        "max_child_tasks": _positive_int(
            limits.get("max_child_tasks"), "limits.max_child_tasks"
        ),
        "max_candidates": _positive_int(
            limits.get("max_candidates"), "limits.max_candidates"
        ),
        "max_attempts_per_scope": _positive_int(
            limits.get("max_attempts_per_scope"), "limits.max_attempts_per_scope"
        ),
    }
    normalised_usage = {
        "runtime_seconds": _non_negative_int(
            usage.get("runtime_seconds"), "usage.runtime_seconds"
        ),
        "child_tasks": _non_negative_int(usage.get("child_tasks"), "usage.child_tasks"),
        "candidates": _non_negative_int(usage.get("candidates"), "usage.candidates"),
    }
    normalised_attempts: dict[str, int] = {}
    for scope, count in attempts.items():
        normal_scope = _normalise_scope(scope)
        normalised_attempts[normal_scope] = _non_negative_int(
            count, f"attempts.{normal_scope}"
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "execution_id": execution_id,
        "automation_id": automation_id,
        "loop_type": loop_type,
        "mode": mode,
        "started_at": _iso(started_at),
        "lease_seconds": lease_seconds,
        "write_scopes": scopes,
        "limits": normalised_limits,
        "usage": normalised_usage,
        "attempts": normalised_attempts,
    }


def _validate_lock(payload: Any, path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("contract_version") != CONTRACT_VERSION:
        raise LoopRuntimeError(f"malformed lock file: {path}")
    scope = _normalise_scope(payload.get("scope"))
    execution_id = _non_empty_string(payload.get("execution_id"), "lock.execution_id")
    expires_at = _parse_time(payload.get("expires_at"), "lock.expires_at")
    if _scope_path(path.parent, scope) != path:
        raise LoopRuntimeError(f"lock fingerprint does not match scope: {path}")
    return {
        **payload,
        "scope": scope,
        "execution_id": execution_id,
        "expires_at_dt": expires_at,
    }


def _read_lock(path: Path) -> dict[str, Any]:
    try:
        return _validate_lock(json.loads(path.read_text(encoding="utf-8")), path)
    except (OSError, json.JSONDecodeError) as exc:
        raise LoopRuntimeError(f"malformed lock file: {path}") from exc


def _budget_blockers(manifest: dict[str, Any]) -> list[str]:
    usage = manifest["usage"]
    limits = manifest["limits"]
    pairs = (
        ("runtime_seconds", "max_runtime_seconds"),
        ("child_tasks", "max_child_tasks"),
        ("candidates", "max_candidates"),
    )
    return [name for name, limit_name in pairs if usage[name] >= limits[limit_name]]


def acquire(
    manifest_payload: dict[str, Any],
    *,
    state_path: Path,
    locks_dir: Path,
    pause_file: Path,
    now: datetime | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> dict[str, Any]:
    now = (now or _utc_now()).astimezone(timezone.utc)
    manifest = _validate_manifest(manifest_payload)
    decision: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "execution_id": manifest["execution_id"],
        "automation_id": manifest["automation_id"],
        "loop_type": manifest["loop_type"],
        "mode": manifest["mode"],
        "observed_at": _iso(now),
        "decision": "ALLOW",
        "acquired_scopes": [],
        "existing_owned_scopes": [],
        "reclaimed_scopes": [],
        "blockers": [],
        "usage": manifest["usage"],
        "limits": manifest["limits"],
    }

    with _runtime_mutex(locks_dir):
        state = _load_state(state_path, now)
        _prune_state(state, now, retention_days)

        if pause_file.exists():
            decision["decision"] = "PAUSED"
            decision["blockers"] = ["GLOBAL_PAUSE_FILE_PRESENT"]
            decision["receipt_fingerprint"] = _fingerprint(decision)
            return decision

        budget_blockers = _budget_blockers(manifest)
        if budget_blockers:
            decision["decision"] = "BUDGET_BLOCKED"
            decision["blockers"] = [f"BUDGET_REACHED:{name}" for name in budget_blockers]
            decision["receipt_fingerprint"] = _fingerprint(decision)
            return decision

        if manifest["mode"] == "read_only":
            decision["decision"] = "READ_ONLY_ALLOW"
            decision["receipt_fingerprint"] = _fingerprint(decision)
            return decision

        execution = state["executions"].get(manifest["execution_id"])
        if execution is not None and not isinstance(execution, dict):
            raise LoopRuntimeError("existing execution state is malformed")
        stored_attempts = dict((execution or {}).get("attempts") or {})

        active_collisions: list[dict[str, str]] = []
        existing_owned: list[str] = []
        owned_locks: dict[str, dict[str, Any]] = {}
        reclaimed: list[dict[str, str]] = []
        for scope in manifest["write_scopes"]:
            path = _scope_path(locks_dir, scope)
            if not path.exists():
                continue
            lock = _read_lock(path)
            if lock["expires_at_dt"] <= now:
                reclaimed.append(
                    {"scope": scope, "previous_execution_id": lock["execution_id"]}
                )
                continue
            if lock["execution_id"] == manifest["execution_id"]:
                existing_owned.append(scope)
                owned_locks[scope] = lock
            else:
                active_collisions.append(
                    {"scope": scope, "owner_execution_id": lock["execution_id"]}
                )
        if active_collisions:
            decision["decision"] = "COLLISION_BLOCKED"
            decision["blockers"] = [
                f"ACTIVE_SCOPE_OWNER:{row['scope']}:{row['owner_execution_id']}"
                for row in active_collisions
            ]
            decision["receipt_fingerprint"] = _fingerprint(decision)
            return decision

        max_attempts = manifest["limits"]["max_attempts_per_scope"]
        exhausted = []
        for scope in manifest["write_scopes"]:
            if scope in existing_owned:
                continue
            count = max(manifest["attempts"].get(scope, 0), stored_attempts.get(scope, 0))
            if count >= max_attempts:
                exhausted.append(scope)
        if exhausted:
            decision["decision"] = "ATTEMPT_LIMIT"
            decision["blockers"] = [f"ATTEMPT_LIMIT:{scope}" for scope in exhausted]
            decision["receipt_fingerprint"] = _fingerprint(decision)
            return decision

        for row in reclaimed:
            _scope_path(locks_dir, row["scope"]).unlink()

        expires_at = now + timedelta(seconds=manifest["lease_seconds"])
        newly_acquired: list[str] = []
        for scope in manifest["write_scopes"]:
            path = _scope_path(locks_dir, scope)
            lock_payload = {
                "contract_version": CONTRACT_VERSION,
                "scope": scope,
                "execution_id": manifest["execution_id"],
                "automation_id": manifest["automation_id"],
                "loop_type": manifest["loop_type"],
                "acquired_at": owned_locks.get(scope, {}).get("acquired_at", _iso(now)),
                "expires_at": _iso(expires_at),
            }
            _atomic_write_json(path, lock_payload)
            if scope in existing_owned:
                continue
            newly_acquired.append(scope)
            stored_attempts[scope] = max(
                manifest["attempts"].get(scope, 0), stored_attempts.get(scope, 0)
            ) + 1

        state["executions"][manifest["execution_id"]] = {
            "automation_id": manifest["automation_id"],
            "loop_type": manifest["loop_type"],
            "mode": manifest["mode"],
            "status": "RUNNING",
            "started_at": manifest["started_at"],
            "acquired_at": (execution or {}).get("acquired_at", _iso(now)),
            "expires_at": _iso(expires_at),
            "write_scopes": manifest["write_scopes"],
            "attempts": stored_attempts,
            "usage": manifest["usage"],
            "limits": manifest["limits"],
        }
        state["updated_at"] = _iso(now)
        _atomic_write_json(state_path, state)

        decision["acquired_scopes"] = newly_acquired
        decision["existing_owned_scopes"] = existing_owned
        decision["reclaimed_scopes"] = reclaimed
        decision["expires_at"] = _iso(expires_at)
        decision["receipt_fingerprint"] = _fingerprint(decision)
        return decision


def release(
    execution_id: str,
    terminal_state: str,
    *,
    state_path: Path,
    locks_dir: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or _utc_now()).astimezone(timezone.utc)
    execution_id = _non_empty_string(execution_id, "execution_id")
    terminal_state = _non_empty_string(terminal_state, "terminal_state")
    result: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "execution_id": execution_id,
        "observed_at": _iso(now),
        "decision": "RELEASED",
        "released_scopes": [],
        "missing_scopes": [],
        "foreign_scopes": [],
        "terminal_state": terminal_state,
    }

    with _runtime_mutex(locks_dir):
        state = _load_state(state_path, now)
        execution = state["executions"].get(execution_id)
        if not isinstance(execution, dict):
            raise LoopRuntimeError(f"execution is not present in state: {execution_id}")
        if execution.get("status") != "RUNNING":
            result["decision"] = "ALREADY_RELEASED"
            result["recorded_terminal_state"] = execution.get("terminal_state")
            result["receipt_fingerprint"] = _fingerprint(result)
            return result

        for scope in execution.get("write_scopes") or []:
            scope = _normalise_scope(scope)
            path = _scope_path(locks_dir, scope)
            if not path.exists():
                result["missing_scopes"].append(scope)
                continue
            lock = _read_lock(path)
            if lock["execution_id"] != execution_id:
                result["foreign_scopes"].append(
                    {"scope": scope, "owner_execution_id": lock["execution_id"]}
                )
                continue
            path.unlink()
            result["released_scopes"].append(scope)

        if result["missing_scopes"] or result["foreign_scopes"]:
            result["decision"] = "RELEASE_INCOMPLETE"
            execution["release_error_at"] = _iso(now)
            execution["release_error"] = {
                "missing_scopes": result["missing_scopes"],
                "foreign_scopes": result["foreign_scopes"],
            }
        else:
            execution["status"] = "COMPLETED"
            execution["terminal_state"] = terminal_state
            execution["completed_at"] = _iso(now)
        state["updated_at"] = _iso(now)
        _atomic_write_json(state_path, state)
        result["receipt_fingerprint"] = _fingerprint(result)
        return result


def audit(
    *,
    state_path: Path,
    locks_dir: Path,
    pause_file: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or _utc_now()).astimezone(timezone.utc)
    with _runtime_mutex(locks_dir):
        state = _load_state(state_path, now)
        active_locks: list[dict[str, str]] = []
        expired_locks: list[dict[str, str]] = []
        orphan_locks: list[dict[str, str]] = []
        malformed_locks: list[str] = []
        lock_owners: dict[str, set[str]] = {}

        for path in sorted(locks_dir.glob("*.json")):
            try:
                lock = _read_lock(path)
            except LoopRuntimeError:
                malformed_locks.append(path.name)
                continue
            row = {
                "scope": lock["scope"],
                "execution_id": lock["execution_id"],
                "expires_at": _iso(lock["expires_at_dt"]),
            }
            if lock["expires_at_dt"] <= now:
                expired_locks.append(row)
            else:
                active_locks.append(row)
            lock_owners.setdefault(lock["execution_id"], set()).add(lock["scope"])
            execution = state["executions"].get(lock["execution_id"])
            if not isinstance(execution, dict) or execution.get("status") != "RUNNING":
                orphan_locks.append(row)

        stale_executions: list[dict[str, Any]] = []
        for execution_id, execution in state["executions"].items():
            if not isinstance(execution, dict):
                raise LoopRuntimeError(f"state execution is invalid: {execution_id}")
            if execution.get("status") != "RUNNING":
                continue
            expires_at = _parse_time(execution.get("expires_at"), "execution.expires_at")
            expected = set(execution.get("write_scopes") or [])
            owned = lock_owners.get(execution_id, set())
            reasons = []
            if expires_at <= now:
                reasons.append("LEASE_EXPIRED")
            if expected - owned:
                reasons.append("CLAIMS_MISSING")
            if reasons:
                stale_executions.append(
                    {
                        "execution_id": execution_id,
                        "reasons": reasons,
                        "missing_scopes": sorted(expected - owned),
                    }
                )

        degraded = any(
            (expired_locks, orphan_locks, malformed_locks, stale_executions)
        )
        decision = "DEGRADED" if degraded else "HEALTHY"
        result = {
            "contract_version": CONTRACT_VERSION,
            "observed_at": _iso(now),
            "decision": decision,
            "paused": pause_file.exists(),
            "active_locks": active_locks,
            "expired_locks": expired_locks,
            "orphan_locks": orphan_locks,
            "malformed_locks": malformed_locks,
            "stale_executions": stale_executions,
            "execution_count": len(state["executions"]),
        }
        result["receipt_fingerprint"] = _fingerprint(result)
        return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LoopRuntimeError(f"unable to read JSON input: {path}") from exc
    if not isinstance(payload, dict):
        raise LoopRuntimeError(f"JSON input must be an object: {path}")
    return payload


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(path, payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire_parser = subparsers.add_parser("acquire", help="Acquire loop write scopes")
    acquire_parser.add_argument("--manifest", required=True)
    acquire_parser.add_argument("--state", required=True)
    acquire_parser.add_argument("--locks-dir", required=True)
    acquire_parser.add_argument("--pause-file", required=True)
    acquire_parser.add_argument("--receipt", required=True)
    acquire_parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)

    release_parser = subparsers.add_parser("release", help="Release owned write scopes")
    release_parser.add_argument("--execution-id", required=True)
    release_parser.add_argument("--terminal-state", required=True)
    release_parser.add_argument("--state", required=True)
    release_parser.add_argument("--locks-dir", required=True)
    release_parser.add_argument("--receipt", required=True)

    audit_parser = subparsers.add_parser("audit", help="Audit local loop state")
    audit_parser.add_argument("--state", required=True)
    audit_parser.add_argument("--locks-dir", required=True)
    audit_parser.add_argument("--pause-file", required=True)
    audit_parser.add_argument("--receipt", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    receipt_path = Path(args.receipt)
    try:
        if args.command == "acquire":
            if args.retention_days <= 0:
                raise LoopRuntimeError("retention-days must be positive")
            result = acquire(
                _read_json(Path(args.manifest)),
                state_path=Path(args.state),
                locks_dir=Path(args.locks_dir),
                pause_file=Path(args.pause_file),
                retention_days=args.retention_days,
            )
        elif args.command == "release":
            result = release(
                args.execution_id,
                args.terminal_state,
                state_path=Path(args.state),
                locks_dir=Path(args.locks_dir),
            )
        else:
            result = audit(
                state_path=Path(args.state),
                locks_dir=Path(args.locks_dir),
                pause_file=Path(args.pause_file),
            )
    except LoopRuntimeError as exc:
        result = {
            "contract_version": CONTRACT_VERSION,
            "observed_at": _iso(_utc_now()),
            "decision": "STATE_INVALID",
            "blockers": [str(exc)],
        }
        result["receipt_fingerprint"] = _fingerprint(result)
        try:
            _write_receipt(receipt_path, result)
        except OSError:
            pass
        print(f"loop runtime failed: {exc}", file=sys.stderr)
        return EXIT_CODES["STATE_INVALID"]

    _write_receipt(receipt_path, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return EXIT_CODES.get(result["decision"], 7)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Register immutable control/challenger topic-score pairs for two live batches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import tempfile
from typing import Any


CONFIG_CONTRACT = "factor-score-paired-trial-config-v1"
RUN_CONTRACT = "factor-score-paired-run-v1"
CONTROL_MODE = "legacy"
CONTROL_SCORE_SOURCE = "computed_v3_12_0"
CHALLENGER_MODE = "hybrid_trial"
CHALLENGER_SCORE_SOURCE = "computed_hybrid_v3_16_0_trial"
COUNTED_STATUSES = {"REGISTERED", "REGISTERED_WITH_REGRESSION"}


class TrialError(ValueError):
    """Raised when a paired-trial artifact cannot be trusted."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any, excluded: set[str] | None = None) -> str:
    excluded = excluded or set()
    if isinstance(value, dict):
        value = {key: item for key, item in value.items() if key not in excluded}
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrialError(f"{label} unreadable:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise TrialError(f"{label} must be a JSON object:{path}")
    return value


def _atomic_write(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        temporary = pathlib.Path(handle.name)
    os.replace(temporary, path)


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrialError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_config(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("contract_version") != CONFIG_CONTRACT:
        raise TrialError(f"config contract_version must be {CONFIG_CONTRACT}")
    expected_fingerprint = _fingerprint(config, {"config_fingerprint"})
    if config.get("config_fingerprint") != expected_fingerprint:
        raise TrialError("config_fingerprint mismatch")
    if config.get("status") != "ACTIVE":
        raise TrialError("trial config must be ACTIVE")
    target = config.get("target_run_count")
    if isinstance(target, bool) or not isinstance(target, int) or target != 2:
        raise TrialError("target_run_count must be exactly 2")
    control = config.get("control") or {}
    challenger = config.get("challenger") or {}
    if control != {
        "factor_score_mode": CONTROL_MODE,
        "score_source": CONTROL_SCORE_SOURCE,
        "production_authority": True,
    }:
        raise TrialError("control contract mismatch")
    if challenger != {
        "factor_score_mode": CHALLENGER_MODE,
        "score_source": CHALLENGER_SCORE_SOURCE,
        "production_authority": False,
    }:
        raise TrialError("challenger contract mismatch")
    return config


def initialise_config(args: argparse.Namespace) -> dict[str, Any]:
    config = {
        "contract_version": CONFIG_CONTRACT,
        "trial_id": _require_text(args.trial_id, "trial_id"),
        "status": "ACTIVE",
        "observed_at": _require_text(args.observed_at, "observed_at"),
        "target_run_count": 2,
        "control": {
            "factor_score_mode": CONTROL_MODE,
            "score_source": CONTROL_SCORE_SOURCE,
            "production_authority": True,
        },
        "challenger": {
            "factor_score_mode": CHALLENGER_MODE,
            "score_source": CHALLENGER_SCORE_SOURCE,
            "production_authority": False,
        },
        "checkpoint_plan": ["72h", "7d"],
        "promotion_boundary": "MANUAL_REVIEW_AND_MATURE_EVIDENCE_REQUIRED",
        "canonical_default_changed": False,
    }
    config["config_fingerprint"] = _fingerprint(config)
    if args.output.exists():
        existing = _read_json(args.output, "existing config")
        if existing != config:
            raise TrialError("immutable trial config already exists with different content")
        return {
            **config,
            "operation_status": "ALREADY_INITIALISED",
            "output": str(args.output),
        }
    _atomic_write(args.output, config)
    return {**config, "operation_status": "INITIALISED", "output": str(args.output)}


def _selected_rows(payload: dict[str, Any], label: str) -> list[dict[str, Any]]:
    rows = payload.get("selected")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise TrialError(f"{label}.selected must be a list of objects")
    ids = [_require_text(row.get("candidate_id"), f"{label}.candidate_id") for row in rows]
    if len(ids) != len(set(ids)):
        raise TrialError(f"{label}.selected contains duplicate candidate IDs")
    return rows


def _validate_score_output(
    payload: dict[str, Any], mode: str, score_source: str, label: str
) -> list[dict[str, Any]]:
    if payload.get("factor_score_mode") != mode:
        raise TrialError(f"{label}.factor_score_mode must be {mode}")
    if payload.get("score_source") != score_source:
        raise TrialError(f"{label}.score_source must be {score_source}")
    candidate_count = payload.get("candidate_count")
    if isinstance(candidate_count, bool) or not isinstance(candidate_count, int):
        raise TrialError(f"{label}.candidate_count must be an integer")
    _require_text(payload.get("candidate_pool_fingerprint"), f"{label}.candidate_pool_fingerprint")
    rows = _selected_rows(payload, label)
    for row in rows:
        if row.get("eligible") is not True:
            raise TrialError(f"{label} selected an ineligible candidate")
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or score < 80:
            raise TrialError(f"{label} selected a candidate below the 80-point gate")
    return rows


def _existing_trial_runs(
    registry_root: pathlib.Path, trial_id: str
) -> dict[str, tuple[pathlib.Path, dict[str, Any]]]:
    found: dict[str, tuple[pathlib.Path, dict[str, Any]]] = {}
    if not registry_root.exists():
        return found
    for path in registry_root.rglob("factor-score-paired-trial.json"):
        try:
            value = _read_json(path, "paired run")
        except TrialError:
            continue
        if value.get("contract_version") != RUN_CONTRACT:
            continue
        if value.get("trial_id") != trial_id or value.get("status") not in COUNTED_STATUSES:
            continue
        run_id = str(value.get("publication_run_id") or "").strip()
        if not run_id:
            continue
        if run_id in found and found[run_id][1] != value:
            raise TrialError(f"conflicting immutable paired runs for {run_id}")
        found[run_id] = (path, value)
    return found


def _score_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, 1):
        component = row.get("hybrid_factor_component") or {}
        result.append(
            {
                "candidate_id": row["candidate_id"],
                "title": row.get("title"),
                "rank": rank,
                "score": row.get("score"),
                "legacy_score": row.get("legacy_score"),
                "hybrid_score": row.get("hybrid_score"),
                "factor_coverage_weight_pct": component.get("coverage_weight_pct"),
                "effective_factor_score": component.get("effective_factor_score"),
            }
        )
    return result


def register_pair(args: argparse.Namespace) -> dict[str, Any]:
    config = _validate_config(_read_json(args.config, "trial config"))
    legacy = _read_json(args.legacy, "legacy output")
    hybrid = _read_json(args.hybrid, "hybrid output")
    legacy_rows = _validate_score_output(
        legacy, CONTROL_MODE, CONTROL_SCORE_SOURCE, "legacy"
    )
    hybrid_rows = _validate_score_output(
        hybrid, CHALLENGER_MODE, CHALLENGER_SCORE_SOURCE, "hybrid"
    )
    if legacy.get("candidate_count") != hybrid.get("candidate_count"):
        raise TrialError("candidate_count mismatch")
    if legacy.get("candidate_pool_fingerprint") != hybrid.get(
        "candidate_pool_fingerprint"
    ):
        raise TrialError("candidate_pool_fingerprint mismatch")
    if legacy.get("trend_mode") != hybrid.get("trend_mode"):
        raise TrialError("trend_mode mismatch")

    publication_run_id = _require_text(
        args.publication_run_id, "publication_run_id"
    )
    trial_id = config["trial_id"]
    existing = _existing_trial_runs(args.registry_root, trial_id)
    legacy_sha = _file_sha256(args.legacy)
    hybrid_sha = _file_sha256(args.hybrid)
    if publication_run_id in existing:
        existing_path, existing_value = existing[publication_run_id]
        if (
            (existing_value.get("control") or {}).get("input_sha256") != legacy_sha
            or (existing_value.get("challenger") or {}).get("input_sha256")
            != hybrid_sha
        ):
            raise TrialError("registered publication run has different scorer inputs")
        return {
            "status": "ALREADY_REGISTERED",
            "trial_id": trial_id,
            "publication_run_id": publication_run_id,
            "slot": existing_value.get("slot"),
            "existing_path": str(existing_path),
        }

    if len(existing) >= config["target_run_count"]:
        result = {
            "contract_version": RUN_CONTRACT,
            "status": "TRIAL_CAP_REACHED",
            "trial_id": trial_id,
            "publication_run_id": publication_run_id,
            "observed_at": _require_text(args.observed_at, "observed_at"),
            "registered_run_count": len(existing),
            "target_run_count": config["target_run_count"],
            "production_score_mode": CONTROL_MODE,
            "requested_production_mutations": 0,
        }
        result["artifact_fingerprint"] = _fingerprint(result)
        _atomic_write(args.output, result)
        return result

    slot = len(existing) + 1
    legacy_scored = _score_rows(legacy_rows)
    hybrid_scored = _score_rows(hybrid_rows)
    legacy_rank = {row["candidate_id"]: row["rank"] for row in legacy_scored}
    hybrid_rank = {row["candidate_id"]: row["rank"] for row in hybrid_scored}
    legacy_ids = list(legacy_rank)
    hybrid_ids = list(hybrid_rank)
    shared = [candidate_id for candidate_id in legacy_ids if candidate_id in hybrid_rank]
    regressions: list[str] = []
    if int(hybrid.get("no_topic_slots") or 0) > int(legacy.get("no_topic_slots") or 0):
        regressions.append("CHALLENGER_SUPPLY_REGRESSION")
    if (hybrid.get("direct_factor_model_summary") or {}).get(
        "production_decisions_affected"
    ) not in {0, None}:
        regressions.append("CHALLENGER_PRODUCTION_BOUNDARY_VIOLATION")

    result = {
        "contract_version": RUN_CONTRACT,
        "status": "REGISTERED_WITH_REGRESSION" if regressions else "REGISTERED",
        "trial_id": trial_id,
        "slot": slot,
        "target_run_count": config["target_run_count"],
        "publication_run_id": publication_run_id,
        "observed_at": _require_text(args.observed_at, "observed_at"),
        "config_fingerprint": config["config_fingerprint"],
        "candidate_pool_fingerprint": legacy["candidate_pool_fingerprint"],
        "candidate_count": legacy["candidate_count"],
        "control": {
            "factor_score_mode": CONTROL_MODE,
            "score_source": CONTROL_SCORE_SOURCE,
            "production_authority": True,
            "input_path": str(args.legacy),
            "input_sha256": legacy_sha,
            "selected": legacy_scored,
        },
        "challenger": {
            "factor_score_mode": CHALLENGER_MODE,
            "score_source": CHALLENGER_SCORE_SOURCE,
            "production_authority": False,
            "input_path": str(args.hybrid),
            "input_sha256": hybrid_sha,
            "selected": hybrid_scored,
        },
        "comparison": {
            "selected_set_equal": set(legacy_ids) == set(hybrid_ids),
            "selected_order_equal": legacy_ids == hybrid_ids,
            "shared_selected_ids": shared,
            "control_only_ids": [value for value in legacy_ids if value not in hybrid_rank],
            "challenger_only_ids": [value for value in hybrid_ids if value not in legacy_rank],
            "rank_shifts": [
                {
                    "candidate_id": candidate_id,
                    "control_rank": legacy_rank[candidate_id],
                    "challenger_rank": hybrid_rank[candidate_id],
                    "challenger_minus_control": hybrid_rank[candidate_id]
                    - legacy_rank[candidate_id],
                }
                for candidate_id in shared
            ],
            "regressions": regressions,
        },
        "publication_authority": "CONTROL_ONLY",
        "challenger_can_publish": False,
        "checkpoint_plan": config["checkpoint_plan"],
        "promotion_boundary": config["promotion_boundary"],
        "requested_production_mutations": 0,
    }
    result["artifact_fingerprint"] = _fingerprint(result)
    _atomic_write(args.output, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--output", type=pathlib.Path, required=True)
    init_parser.add_argument("--trial-id", required=True)
    init_parser.add_argument("--observed-at", required=True)

    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--config", type=pathlib.Path, required=True)
    register_parser.add_argument("--legacy", type=pathlib.Path, required=True)
    register_parser.add_argument("--hybrid", type=pathlib.Path, required=True)
    register_parser.add_argument("--publication-run-id", required=True)
    register_parser.add_argument("--observed-at", required=True)
    register_parser.add_argument("--registry-root", type=pathlib.Path, required=True)
    register_parser.add_argument("--output", type=pathlib.Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = initialise_config(args) if args.command == "init" else register_pair(args)
    except TrialError as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

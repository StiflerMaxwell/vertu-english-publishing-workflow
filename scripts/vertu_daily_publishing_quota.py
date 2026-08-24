#!/usr/bin/env python3
"""Validate the bounded daily publication quota for the vertu-10 workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "daily-publishing-quota-v1"
DEFAULT_EXPANSION_TARGETS = (30, 60, 90, 120)


class QuotaStateError(ValueError):
    """Raised when quota state is structurally unsafe or inconsistent."""


def _unique_strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise QuotaStateError(f"{field} must be a list")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise QuotaStateError(f"{field} entries must be non-empty strings")
        key = item.strip()
        if key in seen:
            raise QuotaStateError(f"{field} contains duplicate article key: {key}")
        seen.add(key)
        cleaned.append(key)
    return cleaned


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise QuotaStateError(f"{field} must be a positive integer")
    return value


def evaluate_quota_state(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise QuotaStateError("input must be a JSON object")
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise QuotaStateError(
            f"contract_version must equal {CONTRACT_VERSION}"
        )
    execution_id = payload.get("execution_id")
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise QuotaStateError("execution_id must be a non-empty string")
    if payload.get("gates_preserved") is not True:
        raise QuotaStateError("gates_preserved must be true")

    required = _positive_int(payload.get("required_publish_count", 10), "required_publish_count")
    max_articles = _positive_int(payload.get("max_articles", 10), "max_articles")
    if max_articles < required:
        raise QuotaStateError("max_articles cannot be below required_publish_count")

    raw_targets = payload.get("expansion_targets", list(DEFAULT_EXPANSION_TARGETS))
    if not isinstance(raw_targets, list) or not raw_targets:
        raise QuotaStateError("expansion_targets must be a non-empty list")
    expansion_targets = [_positive_int(item, "expansion_targets") for item in raw_targets]
    if expansion_targets != sorted(set(expansion_targets)):
        raise QuotaStateError("expansion_targets must be strictly increasing")
    current_target = _positive_int(payload.get("current_candidate_target"), "current_candidate_target")
    if current_target not in expansion_targets:
        raise QuotaStateError("current_candidate_target must be an expansion target")

    eligible = _unique_strings(payload.get("eligible_article_keys", []), "eligible_article_keys")
    selected = _unique_strings(payload.get("selected_article_keys", []), "selected_article_keys")
    live = _unique_strings(payload.get("live_verified_article_keys", []), "live_verified_article_keys")
    eligible_set = set(eligible)
    selected_set = set(selected)
    live_set = set(live)
    if not selected_set.issubset(eligible_set):
        raise QuotaStateError("selected articles must be eligible")
    if not live_set.issubset(selected_set):
        raise QuotaStateError("live-verified articles must be selected")
    if len(selected) > max_articles or len(live) > max_articles:
        raise QuotaStateError("selected/live counts exceed max_articles")

    blocked = payload.get("blocked_articles", [])
    if not isinstance(blocked, list):
        raise QuotaStateError("blocked_articles must be a list")
    blocked_keys: list[str] = []
    normalized_blockers: list[dict[str, str]] = []
    for item in blocked:
        if not isinstance(item, dict):
            raise QuotaStateError("blocked_articles entries must be objects")
        key = item.get("article_key")
        stage = item.get("stage")
        reason = item.get("reason")
        if not all(isinstance(value, str) and value.strip() for value in (key, stage, reason)):
            raise QuotaStateError("each blocker requires article_key, stage and reason")
        if key in blocked_keys:
            raise QuotaStateError(f"duplicate blocked article key: {key}")
        blocked_keys.append(key)
        normalized_blockers.append(
            {"article_key": key.strip(), "stage": stage.strip(), "reason": reason.strip()}
        )

    current_index = expansion_targets.index(current_target)
    next_target = (
        expansion_targets[current_index + 1]
        if current_index + 1 < len(expansion_targets)
        else None
    )
    expansion_available = next_target is not None
    replacement_pool_count = len(eligible_set - selected_set - set(blocked_keys))

    if len(live) >= required:
        state = "COMPLETE"
        next_action = "TERMINALISE_SUCCESS"
    elif normalized_blockers and (replacement_pool_count > 0 or expansion_available):
        state = "REPLACEMENT_REQUIRED"
        next_action = "SELECT_REPLACEMENT"
    elif len(eligible) < required and expansion_available:
        state = "EXPAND_REQUIRED"
        next_action = "EXPAND_CANDIDATE_POOL"
    elif len(selected) < required and replacement_pool_count > 0:
        state = "REPLACEMENT_REQUIRED"
        next_action = "SELECT_REPLACEMENT"
    elif len(selected) >= required:
        state = "PRODUCTION_IN_PROGRESS"
        next_action = "CONTINUE_DOWNSTREAM_GATES"
    elif expansion_available:
        state = "EXPAND_REQUIRED"
        next_action = "EXPAND_CANDIDATE_POOL"
    else:
        state = "DAILY_QUOTA_BLOCKED"
        next_action = "TERMINALISE_BLOCKER"

    return {
        "contract_version": CONTRACT_VERSION,
        "execution_id": execution_id.strip(),
        "state": state,
        "next_action": next_action,
        "required_publish_count": required,
        "max_articles": max_articles,
        "current_candidate_target": current_target,
        "next_candidate_target": next_target,
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "live_verified_count": len(live),
        "blocked_count": len(normalized_blockers),
        "replacement_pool_count": replacement_pool_count,
        "gates_preserved": True,
        "blocked_articles": normalized_blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Quota-state JSON input")
    parser.add_argument("--output", required=True, help="Decision JSON output")
    args = parser.parse_args()

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = evaluate_quota_state(payload)
    except (OSError, json.JSONDecodeError, QuotaStateError) as exc:
        print(f"quota validation failed: {exc}", file=sys.stderr)
        return 2

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

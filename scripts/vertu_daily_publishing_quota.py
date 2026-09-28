#!/usr/bin/env python3
"""Validate the bounded daily publication quota for the vertu-10 workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CONTRACT_VERSION = "daily-publishing-quota-v2"
LEGACY_CONTRACT_VERSION = "daily-publishing-quota-v1"
DEFAULT_EXPANSION_TARGETS = (30, 60, 90, 120)
SUPPLY_PHASES = ("HOT_PRIMARY", "EVERGREEN_FALLBACK")
PRE_DISCOVERY_BLOCKERS = {
    "QA_POLICY_VERSION_MISMATCH", "QA_RUNTIME_CHECK_FAILED", "BASE_AUDIT_WRITE_FAILED",
    "PAUSED", "COLLISION_BLOCKED", "BUDGET_BLOCKED", "ATTEMPT_LIMIT", "STATE_INVALID",
    "GSC_SOURCE_BLOCKED", "AUTHENTICATED_INVENTORY_UNAVAILABLE",
    "AUTHOR_BLOCKED",
}

INSTITUTIONAL_AUTHOR_URLS = frozenset(
    f"https://vertu.com/authors/vertu-{desk}-desk" for desk in (
        "buyer-guide", "ai-innovation", "watch-craft", "privacy-security",
        "concierge-travel", "product-service",
    )
)


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


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value.strip()) != 64:
        raise QuotaStateError(f"{field} must be a 64-character SHA-256 hex string")
    cleaned = value.strip().lower()
    if any(char not in "0123456789abcdef" for char in cleaned):
        raise QuotaStateError(f"{field} must be a SHA-256 hex string")
    return cleaned


def _normalise_common(payload: dict[str, Any]) -> dict[str, Any]:
    execution_id = payload.get("execution_id")
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise QuotaStateError("execution_id must be a non-empty string")
    if payload.get("gates_preserved") is not True:
        raise QuotaStateError("gates_preserved must be true")

    required = _positive_int(payload.get("required_publish_count", 10), "required_publish_count")
    max_articles = _positive_int(payload.get("max_articles", 10), "max_articles")
    if max_articles < required:
        raise QuotaStateError("max_articles cannot be below required_publish_count")

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
        key = key.strip()
        if key in blocked_keys:
            raise QuotaStateError(f"duplicate blocked article key: {key}")
        blocked_keys.append(key)
        normalized_blockers.append(
            {"article_key": key, "stage": stage.strip(), "reason": reason.strip()}
        )

    return {
        "execution_id": execution_id.strip(),
        "required": required,
        "max_articles": max_articles,
        "eligible": eligible,
        "selected": selected,
        "live": live,
        "eligible_set": eligible_set,
        "selected_set": selected_set,
        "blocked_keys": blocked_keys,
        "normalized_blockers": normalized_blockers,
    }


def _evaluate_v1(payload: dict[str, Any]) -> dict[str, Any]:
    common = _normalise_common(payload)
    execution_id = common["execution_id"]
    required = common["required"]
    max_articles = common["max_articles"]

    raw_targets = payload.get("expansion_targets", list(DEFAULT_EXPANSION_TARGETS))
    if not isinstance(raw_targets, list) or not raw_targets:
        raise QuotaStateError("expansion_targets must be a non-empty list")
    expansion_targets = [_positive_int(item, "expansion_targets") for item in raw_targets]
    if expansion_targets != sorted(set(expansion_targets)):
        raise QuotaStateError("expansion_targets must be strictly increasing")
    current_target = _positive_int(payload.get("current_candidate_target"), "current_candidate_target")
    if current_target not in expansion_targets:
        raise QuotaStateError("current_candidate_target must be an expansion target")

    eligible = common["eligible"]
    selected = common["selected"]
    live = common["live"]
    eligible_set = common["eligible_set"]
    selected_set = common["selected_set"]
    blocked_keys = common["blocked_keys"]
    normalized_blockers = common["normalized_blockers"]

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
        "contract_version": LEGACY_CONTRACT_VERSION,
        "execution_id": execution_id,
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


def _phase_targets(payload: dict[str, Any]) -> dict[str, list[int]]:
    raw = payload.get(
        "phase_expansion_targets",
        {phase: list(DEFAULT_EXPANSION_TARGETS) for phase in SUPPLY_PHASES},
    )
    if not isinstance(raw, dict) or set(raw) != set(SUPPLY_PHASES):
        raise QuotaStateError(
            "phase_expansion_targets must contain HOT_PRIMARY and EVERGREEN_FALLBACK"
        )
    normalised: dict[str, list[int]] = {}
    for phase in SUPPLY_PHASES:
        values = raw.get(phase)
        if not isinstance(values, list) or not values:
            raise QuotaStateError(f"phase_expansion_targets.{phase} must be a non-empty list")
        targets = [_positive_int(item, f"phase_expansion_targets.{phase}") for item in values]
        if targets != sorted(set(targets)):
            raise QuotaStateError(
                f"phase_expansion_targets.{phase} must be strictly increasing"
            )
        if targets[-1] > 120:
            raise QuotaStateError(f"phase_expansion_targets.{phase} cannot exceed 120")
        normalised[phase] = targets
    return normalised


def _candidate_lineage(
    payload: dict[str, Any],
    *,
    eligible: list[str],
    pool_fingerprints: dict[str, str],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    raw = payload.get("candidate_lineage")
    if not isinstance(raw, list):
        raise QuotaStateError("candidate_lineage must be a list")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    phase_counts = {phase: 0 for phase in SUPPLY_PHASES}
    for item in raw:
        if not isinstance(item, dict):
            raise QuotaStateError("candidate_lineage entries must be objects")
        article_key = item.get("article_key")
        phase = item.get("supply_phase")
        trend_class = item.get("trend_class")
        fingerprint = item.get("pool_fingerprint")
        if not isinstance(article_key, str) or not article_key.strip():
            raise QuotaStateError("candidate_lineage.article_key must be a non-empty string")
        article_key = article_key.strip()
        if article_key in seen:
            raise QuotaStateError(f"duplicate candidate lineage article key: {article_key}")
        if phase not in SUPPLY_PHASES:
            raise QuotaStateError(f"invalid candidate lineage supply phase: {phase}")
        if phase == "HOT_PRIMARY" and trend_class not in {"REALTIME_HOT", "RISING_SEARCH"}:
            raise QuotaStateError("HOT_PRIMARY lineage requires REALTIME_HOT or RISING_SEARCH")
        if phase == "EVERGREEN_FALLBACK" and trend_class != "EVERGREEN_SEARCH":
            raise QuotaStateError("EVERGREEN_FALLBACK lineage requires EVERGREEN_SEARCH")
        normalised_fingerprint = _sha256(
            fingerprint, f"candidate_lineage.{article_key}.pool_fingerprint"
        )
        if pool_fingerprints.get(phase) != normalised_fingerprint:
            raise QuotaStateError(
                f"candidate lineage fingerprint mismatch for {article_key}"
            )
        seen.add(article_key)
        phase_counts[phase] += 1
        rows.append(
            {
                "article_key": article_key,
                "supply_phase": phase,
                "trend_class": trend_class,
                "pool_fingerprint": normalised_fingerprint,
            }
        )
    if seen != set(eligible):
        raise QuotaStateError("candidate_lineage must cover exactly the eligible article keys")
    return rows, phase_counts


def _evaluate_v2(payload: dict[str, Any]) -> dict[str, Any]:
    common = _normalise_common(payload)
    phase = payload.get("supply_phase")
    if phase not in SUPPLY_PHASES:
        raise QuotaStateError("supply_phase must be HOT_PRIMARY or EVERGREEN_FALLBACK")
    targets_by_phase = _phase_targets(payload)
    current_target = _positive_int(payload.get("current_phase_target"), "current_phase_target")
    targets = targets_by_phase[phase]
    if current_target not in targets:
        raise QuotaStateError("current_phase_target must be an expansion target for supply_phase")

    raw_fingerprints = payload.get("candidate_pool_fingerprints")
    if not isinstance(raw_fingerprints, dict):
        raise QuotaStateError("candidate_pool_fingerprints must be an object")
    required_phases = {"HOT_PRIMARY"} if phase == "HOT_PRIMARY" else set(SUPPLY_PHASES)
    if set(raw_fingerprints) != required_phases:
        raise QuotaStateError(
            "candidate_pool_fingerprints must contain exactly the phases already started"
        )
    pool_fingerprints = {
        key: _sha256(value, f"candidate_pool_fingerprints.{key}")
        for key, value in raw_fingerprints.items()
    }
    lineage, phase_eligible_counts = _candidate_lineage(
        payload, eligible=common["eligible"], pool_fingerprints=pool_fingerprints
    )

    current_index = targets.index(current_target)
    next_target = targets[current_index + 1] if current_index + 1 < len(targets) else None
    phase_expansion_available = next_target is not None
    replacement_pool_count = len(
        common["eligible_set"] - common["selected_set"] - set(common["blocked_keys"])
    )

    if len(common["live"]) >= common["required"]:
        state = "COMPLETE"
        next_action = "TERMINALISE_SUCCESS"
    elif replacement_pool_count > 0 and (
        common["normalized_blockers"] or len(common["selected"]) < common["required"]
    ):
        state = "REPLACEMENT_REQUIRED"
        next_action = "SELECT_REPLACEMENT"
    elif len(common["selected"]) >= common["required"]:
        state = "PRODUCTION_IN_PROGRESS"
        next_action = "CONTINUE_DOWNSTREAM_GATES"
    elif phase_expansion_available:
        state = "EXPAND_REQUIRED"
        next_action = "EXPAND_HOT_PRIMARY" if phase == "HOT_PRIMARY" else "EXPAND_EVERGREEN_FALLBACK"
    elif phase == "HOT_PRIMARY":
        state = "SWITCH_TO_EVERGREEN"
        next_action = "START_EVERGREEN_FALLBACK"
    else:
        state = "DAILY_QUOTA_BLOCKED"
        next_action = "TERMINALISE_BLOCKER"

    total_candidate_limit = sum(targets_by_phase[item][-1] for item in SUPPLY_PHASES)
    return {
        "contract_version": CONTRACT_VERSION,
        "execution_id": common["execution_id"],
        "state": state,
        "next_action": next_action,
        "supply_phase": phase,
        "phase_expansion_targets": targets_by_phase,
        "current_phase_target": current_target,
        "next_phase_target": next_target,
        "phase_candidate_limit": targets[-1],
        "total_candidate_limit": total_candidate_limit,
        "candidate_pool_fingerprints": pool_fingerprints,
        "candidate_lineage": lineage,
        "phase_eligible_counts": phase_eligible_counts,
        "required_publish_count": common["required"],
        "max_articles": common["max_articles"],
        "eligible_count": len(common["eligible"]),
        "selected_count": len(common["selected"]),
        "live_verified_count": len(common["live"]),
        "blocked_count": len(common["normalized_blockers"]),
        "replacement_pool_count": replacement_pool_count,
        "gates_preserved": True,
        "blocked_articles": common["normalized_blockers"],
    }


def _validate_shared_author_block(evidence: dict[str, Any]) -> None:
    """A single failed candidate or assertion cannot substitute for shared evidence."""
    if (evidence.get("all_six_desks_and_article_template_affected") is not True
            or evidence.get("expected_institutional_type") != "Organization"
            or evidence.get("article_qa_performed") is not False
            or type(evidence.get("sanity_mutations")) is not int
            or evidence["sanity_mutations"] != 0
            or evidence.get("manual_apple_exception_applies") is not False):
        raise QuotaStateError("AUTHOR_BLOCKED requires an unwaived shared pre-discovery failure")
    checks = evidence.get("checks")
    if not isinstance(checks, list) or len(checks) < 7:
        raise QuotaStateError("AUTHOR_BLOCKED requires all six profiles and an article observation")
    profiles: set[str] = set()
    articles: set[str] = set()
    for check in checks:
        if (not isinstance(check, dict) or check.get("http_status") != 200
                or check.get("source_state") != "AVAILABLE"
                or not isinstance(check.get("url"), str)
                or check.get("final_url") != check["url"]):
            raise QuotaStateError("AUTHOR_BLOCKED observations must be available and unredirected")
        _sha256(check.get("html_sha256"), "AUTHOR_BLOCKED.html_sha256")
        url = check["url"]
        nodes = check.get("author_nodes")
        if (not isinstance(nodes, list) or len(nodes) != 1
                or not isinstance(nodes[0], dict) or nodes[0].get("type") != "Person"
                or not isinstance(nodes[0].get("url"), str)
                or nodes[0].get("url") not in INSTITUTIONAL_AUTHOR_URLS):
            raise QuotaStateError("AUTHOR_BLOCKED requires observed institutional Person mismatch")
        if url in INSTITUTIONAL_AUTHOR_URLS:
            if url in profiles or nodes[0]["url"] != url:
                raise QuotaStateError("AUTHOR_BLOCKED profile identity missing or duplicated")
            profiles.add(url)
        else:
            parsed = urlparse(url)
            segments = parsed.path.strip("/").split("/")
            if (parsed.scheme != "https" or parsed.netloc != "vertu.com"
                    or parsed.query or parsed.fragment or len(segments) != 2
                    or segments[0] not in {"guides", "lifestyle", "innovation", "ai-tools",
                                           "craftsmanship", "concierge", "luxury-life-guides"}
                    or not segments[1] or url in articles):
                raise QuotaStateError("AUTHOR_BLOCKED requires a distinct non-News article URL")
            articles.add(url)
    if profiles != INSTITUTIONAL_AUTHOR_URLS or not articles:
        raise QuotaStateError("AUTHOR_BLOCKED does not demonstrate a shared six-desk template failure")


def _pre_discovery_block(payload: dict[str, Any], evidence_root: Path | None) -> dict[str, Any]:
    common = _normalise_common(payload)
    _phase_targets(payload)
    if (payload.get("actual_candidate_count") != 0
            or isinstance(payload.get("actual_candidate_count"), bool)
            or payload.get("candidate_pool_fingerprints") != {}
            or payload.get("candidate_lineage") != []
            or common["eligible"] or common["selected"] or common["live"]
            or common["normalized_blockers"]):
        raise QuotaStateError("PRE_DISCOVERY requires zero candidates and empty pools/lineage/article states")
    blocker = payload.get("hard_blocker")
    if not isinstance(blocker, dict) or blocker.get("code") not in PRE_DISCOVERY_BLOCKERS:
        raise QuotaStateError("PRE_DISCOVERY requires a recognised hard blocker")
    if evidence_root is None:
        raise QuotaStateError("hard-block evidence root is required")
    relative = blocker.get("evidence_path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise QuotaStateError("hard-block evidence_path must be relative to the input run directory")
    root = evidence_root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise QuotaStateError("hard-block evidence must exist inside the input run directory")
    raw = path.read_bytes()
    fingerprint = _sha256(blocker.get("evidence_sha256"), "hard_blocker.evidence_sha256")
    if hashlib.sha256(raw).hexdigest() != fingerprint:
        raise QuotaStateError("hard-block evidence fingerprint mismatch")
    evidence = json.loads(raw)
    if not isinstance(evidence, dict) or evidence.get("execution_id") != common["execution_id"]:
        raise QuotaStateError("hard-block evidence execution_id mismatch")
    if evidence.get("blocker") != blocker["code"]:
        raise QuotaStateError("hard-block evidence code mismatch")
    if evidence.get("verdict") not in {"BLOCK", "SOURCE_BLOCKED", "FAILED"}:
        raise QuotaStateError("hard-block evidence must record an observed failure")
    if evidence.get("authorises_release") is True or evidence.get("startup_compatible") is True:
        raise QuotaStateError("hard-block evidence contradicts failure")
    if blocker["code"] == "AUTHOR_BLOCKED":
        _validate_shared_author_block(evidence)
    return {
        "contract_version": CONTRACT_VERSION, "execution_id": common["execution_id"],
        "state": "DAILY_QUOTA_BLOCKED", "next_action": "REPAIR_HARD_BLOCKER",
        "supply_phase": "PRE_DISCOVERY", "candidate_pool_fingerprints": {},
        "candidate_lineage": [], "actual_candidate_count": 0, "eligible_count": 0,
        "selected_count": 0, "live_verified_count": 0, "blocked_count": 1,
        "required_publish_count": common["required"], "max_articles": common["max_articles"],
        "shortfall": common["required"], "supply_exhausted": False,
        "gates_preserved": True, "hard_blocker": dict(blocker), "authorises_release": False,
    }


def evaluate_quota_state(payload: dict[str, Any], *, evidence_root: Path | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise QuotaStateError("input must be a JSON object")
    version = payload.get("contract_version")
    if version == LEGACY_CONTRACT_VERSION:
        return _evaluate_v1(payload)
    if version == CONTRACT_VERSION:
        if payload.get("supply_phase") == "PRE_DISCOVERY":
            return _pre_discovery_block(payload, evidence_root)
        if "hard_blocker" in payload:
            raise QuotaStateError("hard_blocker is valid only before discovery; preserve downstream replacement")
        return _evaluate_v2(payload)
    raise QuotaStateError(
        f"contract_version must equal {CONTRACT_VERSION} or {LEGACY_CONTRACT_VERSION}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Quota-state JSON input")
    parser.add_argument("--output", required=True, help="Decision JSON output")
    args = parser.parse_args()

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = evaluate_quota_state(payload, evidence_root=Path(args.input).resolve().parent)
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

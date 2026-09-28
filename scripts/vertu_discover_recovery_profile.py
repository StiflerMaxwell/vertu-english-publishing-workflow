#!/usr/bin/env python3
"""Build a bounded, candidate-generation-only Discover recovery profile."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


CONTRACT = "discover-recovery-editorial-strategy-v1"


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fingerprint(payload: Dict[str, Any]) -> str:
    clean = dict(payload)
    clean.pop("fingerprint", None)
    encoded = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_profile(
    pulse: Dict[str, Any], approval_reference: str, approved_at: str, expires_at: str
) -> Dict[str, Any]:
    if pulse.get("contract_version") != "discover-pulse-v1":
        raise ValueError("discover pulse contract must be discover-pulse-v1")
    approved = parse_time(approved_at)
    expires = parse_time(expires_at)
    lifetime = (expires - approved).total_seconds()
    if lifetime <= 0 or lifetime > 7 * 24 * 3600:
        raise ValueError("expiry must be after approval and no more than seven days later")

    seven = pulse.get("comparisons", {}).get("7d", {})
    changes = seven.get("change_pct", {})
    click_drop = changes.get("clicks")
    impression_drop = changes.get("impressions")
    if not isinstance(click_drop, (int, float)) or not isinstance(impression_drop, (int, float)):
        raise ValueError("finalised seven-day click and impression changes are required")
    active = click_drop <= -40 and impression_drop <= -40

    categories: List[Dict[str, Any]] = pulse.get("category_14d_vs_previous", [])
    resilient = [
        row["category"]
        for row in categories
        if row.get("current_clicks", 0) >= 500 and row.get("click_change_pct", -100) > -65
    ]
    cooldown = [
        row["category"]
        for row in categories
        if isinstance(row.get("click_change_pct"), (int, float)) and row["click_change_pct"] <= -80
    ]

    pulse_fp = fingerprint(pulse)
    profile: Dict[str, Any] = {
        "contract_version": CONTRACT,
        "state": "ACTIVE" if active else "INACTIVE",
        "authority_basis": "USER_APPROVED_EDITORIAL_STRATEGY",
        "approval_reference": approval_reference,
        "approved_at": approved.isoformat().replace("+00:00", "Z"),
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "auto_extend": False,
        "source": {
            "contract_version": pulse["contract_version"],
            "publication_run_id": pulse.get("publication_run_id"),
            "latest_finalised_metric_date": pulse.get("latest_finalised_metric_date"),
            "fingerprint": pulse_fp,
            "seven_day_change_pct": {
                "clicks": click_drop,
                "impressions": impression_drop,
                "ctr": changes.get("ctr"),
            },
        },
        "authority": {
            "candidate_generation": active,
            "portfolio_framing": active,
            "search_demand": False,
            "raw_score": False,
            "trend_class": False,
            "eligibility": False,
            "veto_relief": False,
            "qa": False,
            "publication": False,
            "learned_prior": False,
        },
        "candidate_pool_contract": {
            "preferred_core_min_share": 0.70,
            "current_event_share_range": [0.10, 0.20],
            "exploration_max_share": 0.10,
            "targets_are_soft_candidate_generation_guidance": True,
            "targets_may_force_selection_or_publication": False,
            "focus_lanes": [
                "VERTU_RELEVANT_DECISION_COMPARISON",
                "EXECUTIVE_AI_PRIVACY_SECURITY_MOBILE",
            ],
            "resilient_observed_categories": sorted(resilient),
            "default_exclusions": [
                "GENERIC_HOUSEHOLD",
                "GENERIC_KITCHEN",
                "MATTRESS",
                "WEAKLY_RELATED_WELLBEING",
            ],
            "cooldown_observed_categories": sorted(cooldown),
            "cooldown_override": "MATERIAL_NEW_EVIDENCE_PLUS_UNCHANGED_NORMAL_GATES",
        },
        "measurement": {
            "checkpoints": ["T+72h", "D+7", "D+28"],
            "early_observation_may_promote_rule": False,
            "renewal_requires_separate_governed_decision": True,
            "rollback_on_guardrail_breach": True,
        },
    }
    profile["fingerprint"] = fingerprint(profile)
    return profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discover-pulse", required=True)
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument("--approved-at", required=True)
    parser.add_argument("--expires-at", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    pulse = json.loads(Path(args.discover_pulse).read_text())
    profile = build_profile(pulse, args.approval_reference, args.approved_at, args.expires_at)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"state": profile["state"], "fingerprint": profile["fingerprint"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

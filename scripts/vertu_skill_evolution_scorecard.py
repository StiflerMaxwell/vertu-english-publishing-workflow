#!/usr/bin/env python3
"""Deterministic release scorecard for governed VERTU Skill evolution.

The scorecard deliberately keeps structural diagnostics, paired comparison and
production outcomes separate. It never mutates a Skill, Sanity or Feishu Base.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any


INPUT_CONTRACT = "skill-evolution-scorecard-input-v2"
OUTPUT_CONTRACT = "skill-evolution-scorecard-v2"
FACTOR_EVALUATION_CONTRACT = "skill-evolution-factor-evaluation-v1"
FACTOR_DECISIONS = {
    "REVERT_REQUIRED",
    "SOURCE_BLOCKED",
    "CONTINUE_OBSERVING",
    "NO_EFFECT",
    "EXPERIMENT_REQUIRED",
    "PROMOTION_CANDIDATE",
}

DIAGNOSTIC_WEIGHTS = {
    "workflow_executability": 15,
    "failure_and_rollback": 15,
    "evidence_and_lineage": 15,
    "permissions_and_manual_approval": 10,
    "test_coverage": 15,
    "historical_replay": 20,
    "docs_runtime_maintenance": 10,
}

OUTCOME_WEIGHTS = {
    "directional_consistency": 25,
    "search_discover_lift": 20,
    "ga4_qualified_journeys": 15,
    "cross_run_stability": 15,
    "winner_coverage": 10,
    "diversity_and_cannibalisation": 5,
    "qa_publish_base_reliability": 10,
}

CHANGE_CLASSES = {
    "GOVERNANCE_INFRASTRUCTURE",
    "STRUCTURAL_RULE",
    "NON_STRUCTURAL_PROCESS",
}

PAIRED_STATUSES = {"COMPLETED", "NOT_RUN", "NOT_REQUIRED"}
PAIR_VERDICTS = {"AFTER_BETTER", "BEFORE_BETTER", "TIE"}
PRODUCTION_LEVELS = {
    "NOT_MATURE",
    "OBSERVATION_72H",
    "CANDIDATE_7D",
    "DURABLE_28D",
    "VERIFIED_EXPERIMENT",
}
DURABLE_LEVELS = {"DURABLE_28D", "VERIFIED_EXPERIMENT"}


class ScorecardError(ValueError):
    """Raised when an input cannot support an auditable scorecard."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any, omit: str | None = None) -> str:
    material = value
    if omit and isinstance(value, dict):
        material = {key: item for key, item in value.items() if key != omit}
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScorecardError(f"{label} must be a non-empty string")
    return value.strip()


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ScorecardError(f"{label} must be a boolean")
    return value


def _require_non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ScorecardError(f"{label} must be a non-negative integer")
    return value


def _require_evidence(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ScorecardError(f"{label} must contain at least one evidence reference")
    refs = [_require_text(item, f"{label} item") for item in value]
    if len(refs) != len(set(refs)):
        raise ScorecardError(f"{label} contains duplicate evidence references")
    return refs


def _weighted_score(
    dimensions: Any,
    weights: dict[str, int],
    label: str,
) -> tuple[float, dict[str, dict[str, Any]]]:
    if not isinstance(dimensions, dict):
        raise ScorecardError(f"{label} must be an object")
    unknown = sorted(set(dimensions) - set(weights))
    missing = sorted(set(weights) - set(dimensions))
    if unknown or missing:
        raise ScorecardError(
            f"{label} dimensions mismatch; missing={missing}, unknown={unknown}"
        )

    normalised: dict[str, dict[str, Any]] = {}
    weighted_total = 0.0
    for dimension, weight in weights.items():
        row = dimensions[dimension]
        if not isinstance(row, dict):
            raise ScorecardError(f"{label}.{dimension} must be an object")
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ScorecardError(f"{label}.{dimension}.score must be numeric")
        if score < 0 or score > 100:
            raise ScorecardError(f"{label}.{dimension}.score must be between 0 and 100")
        evidence = _require_evidence(
            row.get("evidence"), f"{label}.{dimension}.evidence"
        )
        score = round(float(score), 2)
        contribution = round(score * weight / 100, 4)
        weighted_total += contribution
        normalised[dimension] = {
            "score": score,
            "weight": weight,
            "weighted_contribution": contribution,
            "evidence": evidence,
        }

    return round(weighted_total, 2), normalised


def _paired_result(
    paired_review: Any,
    change_class: str,
    affects_traffic_decisions: bool,
    approval_reference: str | None,
) -> dict[str, Any]:
    if not isinstance(paired_review, dict):
        raise ScorecardError("paired_review must be an object")
    status = paired_review.get("status")
    if status not in PAIRED_STATUSES:
        raise ScorecardError(f"paired_review.status must be one of {sorted(PAIRED_STATUSES)}")

    if status == "NOT_RUN":
        return {
            "status": status,
            "verdict": "NOT_RUN",
            "judge_count": 0,
            "votes": {"AFTER_BETTER": 0, "BEFORE_BETTER": 0, "TIE": 0},
            "rubric_fingerprint": paired_review.get("rubric_fingerprint"),
        }

    if status == "NOT_REQUIRED":
        if change_class != "GOVERNANCE_INFRASTRUCTURE":
            raise ScorecardError(
                "paired_review NOT_REQUIRED is limited to governance infrastructure"
            )
        if affects_traffic_decisions:
            raise ScorecardError(
                "traffic-affecting governance changes still require paired review"
            )
        if not approval_reference:
            raise ScorecardError(
                "governance bootstrap requires an explicit approval reference"
            )
        return {
            "status": status,
            "verdict": "NOT_REQUIRED",
            "judge_count": 0,
            "votes": {"AFTER_BETTER": 0, "BEFORE_BETTER": 0, "TIE": 0},
            "rubric_fingerprint": paired_review.get("rubric_fingerprint"),
        }

    rubric_fingerprint = _require_text(
        paired_review.get("rubric_fingerprint"),
        "paired_review.rubric_fingerprint",
    )
    judges = paired_review.get("judges")
    if not isinstance(judges, list):
        raise ScorecardError("paired_review.judges must be a list")
    if len(judges) < 3 or len(judges) % 2 == 0:
        raise ScorecardError(
            "completed paired review requires an odd number of at least three judges"
        )

    judge_ids: list[str] = []
    votes = {"AFTER_BETTER": 0, "BEFORE_BETTER": 0, "TIE": 0}
    normalised_judges: list[dict[str, Any]] = []
    for index, judge in enumerate(judges):
        if not isinstance(judge, dict):
            raise ScorecardError(f"paired_review.judges[{index}] must be an object")
        judge_id = _require_text(
            judge.get("judge_id"), f"paired_review.judges[{index}].judge_id"
        )
        verdict = judge.get("verdict")
        if verdict not in PAIR_VERDICTS:
            raise ScorecardError(
                f"paired_review.judges[{index}].verdict must be one of {sorted(PAIR_VERDICTS)}"
            )
        evidence = _require_evidence(
            judge.get("evidence"), f"paired_review.judges[{index}].evidence"
        )
        judge_ids.append(judge_id)
        votes[verdict] += 1
        normalised_judges.append(
            {"judge_id": judge_id, "verdict": verdict, "evidence": evidence}
        )

    if len(judge_ids) != len(set(judge_ids)):
        raise ScorecardError("completed paired review requires unique judge IDs")

    strict_majority = len(judges) // 2 + 1
    if votes["AFTER_BETTER"] >= strict_majority:
        verdict = "AFTER_BETTER"
    elif votes["BEFORE_BETTER"] >= strict_majority:
        verdict = "BEFORE_BETTER"
    else:
        verdict = "INCONCLUSIVE"

    return {
        "status": status,
        "verdict": verdict,
        "judge_count": len(judges),
        "strict_majority": strict_majority,
        "votes": votes,
        "rubric_fingerprint": rubric_fingerprint,
        "judges": normalised_judges,
    }


def _replay_result(replay: Any) -> dict[str, Any]:
    if not isinstance(replay, dict):
        raise ScorecardError("replay must be an object")
    status = replay.get("status")
    if status not in {"PASS", "FAIL", "NOT_RUN"}:
        raise ScorecardError("replay.status must be PASS, FAIL or NOT_RUN")
    regressions = replay.get("gate_regressions", [])
    if not isinstance(regressions, list) or any(
        not isinstance(item, str) or not item.strip() for item in regressions
    ):
        raise ScorecardError("replay.gate_regressions must be a list of strings")
    result = {
        "status": status,
        "gate_regressions": [item.strip() for item in regressions],
        "candidate_count": _require_non_negative_int(
            replay.get("candidate_count", 0), "replay.candidate_count"
        ),
        "holdout_count": _require_non_negative_int(
            replay.get("holdout_count", 0), "replay.holdout_count"
        ),
        "dataset_fingerprint": replay.get("dataset_fingerprint"),
        "evidence": replay.get("evidence", []),
    }
    if status != "NOT_RUN":
        result["dataset_fingerprint"] = _require_text(
            replay.get("dataset_fingerprint"), "replay.dataset_fingerprint"
        )
        result["evidence"] = _require_evidence(
            replay.get("evidence"), "replay.evidence"
        )
    return result


def _production_result(
    production: Any,
    required: bool,
) -> dict[str, Any]:
    if not isinstance(production, dict):
        raise ScorecardError("production_evidence must be an object")
    level = production.get("level")
    if level not in PRODUCTION_LEVELS:
        raise ScorecardError(
            f"production_evidence.level must be one of {sorted(PRODUCTION_LEVELS)}"
        )
    result: dict[str, Any] = {
        "required": required,
        "level": level,
        "mature_for_promotion": level in DURABLE_LEVELS,
        "article_count": _require_non_negative_int(
            production.get("article_count", 0), "production_evidence.article_count"
        ),
        "publication_run_count": _require_non_negative_int(
            production.get("publication_run_count", 0),
            "production_evidence.publication_run_count",
        ),
        "outcome_score": None,
        "dimensions": None,
        "evidence": production.get("evidence", []),
    }

    if level not in DURABLE_LEVELS:
        return result

    result["evidence"] = _require_evidence(
        production.get("evidence"), "production_evidence.evidence"
    )
    if level == "DURABLE_28D":
        if result["article_count"] < 3 or result["publication_run_count"] < 2:
            raise ScorecardError(
                "DURABLE_28D requires at least three articles across two publication runs"
            )
    else:
        result["verified_experiment_id"] = _require_text(
            production.get("verified_experiment_id"),
            "production_evidence.verified_experiment_id",
        )

    score, dimensions = _weighted_score(
        production.get("dimensions"), OUTCOME_WEIGHTS, "production_evidence.dimensions"
    )
    result["outcome_score"] = score
    result["dimensions"] = dimensions
    return result


def _factor_evaluation_result(
    specification: Any,
    *,
    change_id: str,
    execution_id: str,
    before_version: str,
    after_version: str,
    affects_traffic_decisions: bool,
) -> dict[str, Any]:
    if not isinstance(specification, dict):
        raise ScorecardError("factor_evaluation must be an object")
    path = pathlib.Path(
        _require_text(specification.get("path"), "factor_evaluation.path")
    )
    expected_fingerprint = _require_text(
        specification.get("evaluation_fingerprint"),
        "factor_evaluation.evaluation_fingerprint",
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScorecardError(f"factor evaluation cannot be read: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ScorecardError("factor evaluation is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ScorecardError("factor evaluation root must be an object")
    if payload.get("contract_version") != FACTOR_EVALUATION_CONTRACT:
        raise ScorecardError(
            f"factor evaluation contract must be {FACTOR_EVALUATION_CONTRACT}"
        )
    actual_fingerprint = _require_text(
        payload.get("evaluation_fingerprint"),
        "factor evaluation artifact fingerprint",
    )
    if actual_fingerprint != _fingerprint(payload, omit="evaluation_fingerprint"):
        raise ScorecardError("factor evaluation artifact fingerprint mismatch")
    if expected_fingerprint != actual_fingerprint:
        raise ScorecardError("factor evaluation input fingerprint mismatch")
    identity = {
        "change_id": change_id,
        "execution_id": execution_id,
        "before_version": before_version,
        "after_version": after_version,
    }
    for field, expected in identity.items():
        if payload.get(field) != expected:
            raise ScorecardError(f"factor evaluation identity mismatch for {field}")
    if payload.get("affects_traffic_decisions") is not affects_traffic_decisions:
        raise ScorecardError(
            "factor evaluation traffic-decision boundary does not match scorecard"
        )
    decision = payload.get("decision")
    if decision not in FACTOR_DECISIONS:
        raise ScorecardError("factor evaluation decision is unsupported")
    hard_boundaries = payload.get("hard_boundaries")
    if not isinstance(hard_boundaries, dict) or any(
        hard_boundaries.get(key) is not False
        for key in (
            "may_activate_skill",
            "may_approve_experiment",
            "may_change_topic_score",
            "may_create_demand",
            "may_waive_veto",
            "may_mutate_sanity",
        )
    ):
        raise ScorecardError("factor evaluation hard boundaries are invalid")
    activation_state = _require_text(
        payload.get("activation_state"),
        "factor evaluation activation_state",
    )
    if activation_state not in {"PROPOSED", "ACTIVE_SHADOW", "ACTIVE_PRODUCTION"}:
        raise ScorecardError("factor evaluation activation_state is unsupported")
    if payload.get("activation_authority") != "MANUAL_APPROVAL_REQUIRED":
        raise ScorecardError("factor evaluation activation authority is invalid")
    if payload.get("mutations_performed") is not False:
        raise ScorecardError("factor evaluation must not perform mutations")
    if not isinstance(payload.get("summary"), dict):
        raise ScorecardError("factor evaluation summary must be an object")
    return {
        "path": str(path.resolve()),
        "evaluation_fingerprint": actual_fingerprint,
        "vector_fingerprint": _require_text(
            payload.get("vector_fingerprint"),
            "factor evaluation vector_fingerprint",
        ),
        "decision": decision,
        "reasons": payload.get("reasons") or [],
        "activation_state": activation_state,
        "evaluation_window": _require_text(
            payload.get("evaluation_window"),
            "factor evaluation evaluation_window",
        ),
        "production_level": _require_text(
            payload.get("production_level"),
            "factor evaluation production_level",
        ),
        "selected_factor_count": _require_non_negative_int(
            payload.get("selected_factor_count"),
            "factor evaluation selected_factor_count",
        ),
        "summary": payload.get("summary"),
        "activation_authority": payload.get("activation_authority"),
        "mutations_performed": payload.get("mutations_performed"),
    }


def _release_decision(
    *,
    change_class: str,
    diagnostic_score: float,
    paired: dict[str, Any],
    replay: dict[str, Any],
    production: dict[str, Any],
    factor_evaluation: dict[str, Any],
    approval_reference: str | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    factor_decision = factor_evaluation["decision"]
    if factor_decision == "REVERT_REQUIRED":
        reasons.append("FACTOR_GUARDRAIL_REQUIRES_REVERT")
        return "REVERT_REQUIRED", reasons
    if replay["gate_regressions"]:
        reasons.append("REPLAY_GATE_REGRESSION")
        return "REVERT_REQUIRED", reasons
    if factor_decision in {"SOURCE_BLOCKED", "CONTINUE_OBSERVING"}:
        reasons.append(
            "FACTOR_SOURCE_BLOCKED"
            if factor_decision == "SOURCE_BLOCKED"
            else "FACTOR_EVIDENCE_NOT_MATURE"
        )
        return "PENDING_MATURITY", reasons
    if factor_decision == "EXPERIMENT_REQUIRED":
        reasons.append("FACTOR_EXPERIMENT_REQUIRED")
        return "MANUAL_REVIEW", reasons
    if factor_decision == "NO_EFFECT":
        if factor_evaluation["activation_state"] == "ACTIVE_PRODUCTION":
            reasons.append("ACTIVE_PRODUCTION_FACTOR_NO_EFFECT")
            return "REVERT_REQUIRED", reasons
        reasons.append("FACTOR_TARGETS_SHOW_NO_EFFECT")
        return "REJECTED", reasons
    if factor_decision != "PROMOTION_CANDIDATE":
        raise ScorecardError("factor evaluation cannot continue to release gates")
    if diagnostic_score < 70:
        reasons.append("DIAGNOSTIC_SCORE_BELOW_70")
        return "REJECTED", reasons
    if paired["verdict"] == "BEFORE_BETTER":
        reasons.append("PAIRED_REVIEW_PREFERS_BEFORE")
        return "REVERT_REQUIRED", reasons
    if replay["status"] == "FAIL":
        reasons.append("REPLAY_FAILED")
        return "REVERT_REQUIRED", reasons

    if (
        change_class == "GOVERNANCE_INFRASTRUCTURE"
        and paired["verdict"] == "NOT_REQUIRED"
        and replay["status"] == "PASS"
        and approval_reference
        and not production["required"]
    ):
        reasons.append("EXPLICITLY_APPROVED_GOVERNANCE_BOOTSTRAP")
        return "IMPLEMENTED_BY_APPROVAL", reasons

    if paired["verdict"] in {"NOT_RUN", "INCONCLUSIVE", "NOT_REQUIRED"}:
        reasons.append("PAIRED_REVIEW_INCOMPLETE")
        return "MANUAL_REVIEW", reasons
    if replay["status"] != "PASS":
        reasons.append("REPLAY_NOT_COMPLETE")
        return "MANUAL_REVIEW", reasons
    if not production["required"]:
        reasons.append("NON_TRAFFIC_CHANGE_PASSED_COMPARISON_AND_REPLAY")
        return "PROMOTION_ELIGIBLE", reasons
    if not production["mature_for_promotion"]:
        reasons.append("PRODUCTION_EVIDENCE_NOT_DURABLE")
        return "PENDING_MATURITY", reasons

    outcome_score = production["outcome_score"]
    assert isinstance(outcome_score, float)
    if outcome_score < 60:
        reasons.append("PRODUCTION_OUTCOME_SCORE_BELOW_60")
        return "REVERT_REQUIRED", reasons
    if outcome_score < 75:
        reasons.append("PRODUCTION_OUTCOME_REQUIRES_REVIEW")
        return "MANUAL_REVIEW", reasons
    reasons.append("ALL_PROMOTION_GATES_PASS")
    return "PROMOTION_ELIGIBLE", reasons


def build_scorecard(data: dict[str, Any], observed_at: str | None = None) -> dict[str, Any]:
    if data.get("contract_version") != INPUT_CONTRACT:
        raise ScorecardError(f"contract_version must be {INPUT_CONTRACT}")
    change_id = _require_text(data.get("change_id"), "change_id")
    execution_id = _require_text(data.get("execution_id"), "execution_id")
    change_class = data.get("change_class")
    if change_class not in CHANGE_CLASSES:
        raise ScorecardError(f"change_class must be one of {sorted(CHANGE_CLASSES)}")
    affects_traffic_decisions = _require_bool(
        data.get("affects_traffic_decisions"), "affects_traffic_decisions"
    )
    if change_class == "STRUCTURAL_RULE" and not affects_traffic_decisions:
        raise ScorecardError("STRUCTURAL_RULE must set affects_traffic_decisions=true")

    skill = data.get("skill")
    if not isinstance(skill, dict):
        raise ScorecardError("skill must be an object")
    before_version = _require_text(skill.get("before_version"), "skill.before_version")
    after_version = _require_text(skill.get("after_version"), "skill.after_version")
    if before_version == after_version:
        raise ScorecardError("before and after Skill versions must differ")
    before_path = _require_text(skill.get("before_path"), "skill.before_path")
    after_path = _require_text(skill.get("after_path"), "skill.after_path")

    approval_reference_value = data.get("approval_reference")
    approval_reference = None
    if approval_reference_value is not None:
        approval_reference = _require_text(
            approval_reference_value, "approval_reference"
        )

    factor_evaluation = _factor_evaluation_result(
        data.get("factor_evaluation"),
        change_id=change_id,
        execution_id=execution_id,
        before_version=before_version,
        after_version=after_version,
        affects_traffic_decisions=affects_traffic_decisions,
    )
    diagnostic_score, diagnostic_dimensions = _weighted_score(
        data.get("diagnostic"), DIAGNOSTIC_WEIGHTS, "diagnostic"
    )
    paired = _paired_result(
        data.get("paired_review"),
        change_class,
        affects_traffic_decisions,
        approval_reference,
    )
    replay = _replay_result(data.get("replay"))
    production = _production_result(
        data.get("production_evidence"), affects_traffic_decisions
    )
    decision, reasons = _release_decision(
        change_class=change_class,
        diagnostic_score=diagnostic_score,
        paired=paired,
        replay=replay,
        production=production,
        factor_evaluation=factor_evaluation,
        approval_reference=approval_reference,
    )

    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        observed_at = _require_text(observed_at, "observed_at")

    result: dict[str, Any] = {
        "contract_version": OUTPUT_CONTRACT,
        "change_id": change_id,
        "execution_id": execution_id,
        "observed_at": observed_at,
        "change_class": change_class,
        "affects_traffic_decisions": affects_traffic_decisions,
        "skill": {
            "before_version": before_version,
            "after_version": after_version,
            "before_path": before_path,
            "after_path": after_path,
        },
        "approval_reference": approval_reference,
        "structural_diagnostic": {
            "score": diagnostic_score,
            "triage_only": True,
            "threshold": 70,
            "dimensions": diagnostic_dimensions,
        },
        "paired_review": paired,
        "replay": replay,
        "factor_evaluation": factor_evaluation,
        "production_outcome": production,
        "release": {
            "decision": decision,
            "reasons": reasons,
            "activation_authority": (
                "MANUAL_APPROVAL_REQUIRED"
                if change_class in {"GOVERNANCE_INFRASTRUCTURE", "STRUCTURAL_RULE"}
                else "EXISTING_GOVERNED_POLICY"
            ),
            "mutations_performed": False,
        },
        "hard_boundaries": [
            "ABSOLUTE_SCORE_IS_TRIAGE_ONLY",
            "SCORE_CANNOT_CREATE_DEMAND_OR_TREND_LABELS",
            "SCORE_CANNOT_WAIVE_VETO_OR_PUBLICATION_GATES",
            "FACTOR_EVALUATION_IS_REQUIRED_FOR_NEW_SCORECARDS",
            "FACTOR_EVALUATION_CANNOT_ACTIVATE_SKILL_OR_EXPERIMENT",
            "STRUCTURAL_ACTIVATION_REQUIRES_MANUAL_APPROVAL",
            "LOW_RISK_EXPERIMENTS_REMAIN_MANUAL_APPROVAL",
        ],
    }
    result["input_fingerprint"] = _fingerprint(data)
    result["scorecard_fingerprint"] = _fingerprint(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a deterministic VERTU Skill evolution scorecard"
    )
    parser.add_argument("--input", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--observed-at")
    args = parser.parse_args(argv)

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ScorecardError("input root must be an object")
        scorecard = build_scorecard(data, observed_at=args.observed_at)
    except (OSError, json.JSONDecodeError, ScorecardError) as exc:
        print(
            json.dumps(
                {"status": "INVALID_INPUT", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "OK",
                "decision": scorecard["release"]["decision"],
                "scorecard_fingerprint": scorecard["scorecard_fingerprint"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

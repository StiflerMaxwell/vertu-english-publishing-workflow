#!/usr/bin/env python3
"""Build the governed 60-factor VERTU Skill-evolution observation vector.

This is a read-only/shadow calculator. It does not score topic candidates,
mutate the canonical Skill, write Feishu Base, change priors, or touch Sanity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo


INPUT_CONTRACT = "skill-evolution-factor-input-v1"
OUTPUT_CONTRACT = "skill-evolution-factor-vector-v1"
EVALUATION_INPUT_CONTRACT = "skill-evolution-factor-evaluation-input-v1"
EVALUATION_OUTPUT_CONTRACT = "skill-evolution-factor-evaluation-v1"
STATUSES = {
    "AVAILABLE",
    "SOURCE_UNAVAILABLE",
    "INSUFFICIENT_SAMPLE",
    "NOT_APPLICABLE",
}
DIRECTIONS = {"HIGHER_BETTER", "LOWER_BETTER", "CONTEXTUAL"}
WINDOWS = {"runtime", "24h", "72h", "7d", "28d", "90d"}
WINDOW_RANK = {
    "runtime": 0,
    "24h": 1,
    "72h": 2,
    "7d": 3,
    "28d": 4,
    "90d": 5,
}
ACTIVATION_STATES = {"PROPOSED", "ACTIVE_SHADOW", "ACTIVE_PRODUCTION"}
EVALUATION_PRODUCTION_LEVELS = {
    "NOT_REQUIRED",
    "NOT_MATURE",
    "OBSERVATION_72H",
    "CANDIDATE_7D",
    "DURABLE_28D",
    "VERIFIED_EXPERIMENT",
}
FACTOR_DECISIONS = {
    "REVERT_REQUIRED",
    "SOURCE_BLOCKED",
    "CONTINUE_OBSERVING",
    "NO_EFFECT",
    "EXPERIMENT_REQUIRED",
    "PROMOTION_CANDIDATE",
}


class Factor(NamedTuple):
    factor_id: str
    name: str
    family: str
    direction: str
    unit: str
    maturity_window: str
    description: str


def _f(
    factor_id: str,
    name: str,
    family: str,
    direction: str,
    unit: str,
    maturity_window: str,
    description: str,
) -> Factor:
    return Factor(
        factor_id,
        name,
        family,
        direction,
        unit,
        maturity_window,
        description,
    )


FACTORS = (
    _f("F01", "Search click lift", "traffic", "HIGHER_BETTER", "ratio", "28d", "Change in finalised Search clicks versus the declared comparable baseline."),
    _f("F02", "Search impression lift", "traffic", "HIGHER_BETTER", "ratio", "28d", "Change in finalised Search impressions versus baseline."),
    _f("F03", "Search CTR lift", "traffic", "HIGHER_BETTER", "percentage_points", "28d", "Change in Search click-through rate versus baseline."),
    _f("F04", "Search position improvement", "traffic", "HIGHER_BETTER", "positions", "28d", "Baseline average position minus treatment average position."),
    _f("F05", "Discover click lift", "traffic", "HIGHER_BETTER", "ratio", "28d", "Change in finalised Discover clicks versus baseline."),
    _f("F06", "Discover impression lift", "traffic", "HIGHER_BETTER", "ratio", "28d", "Change in finalised Discover impressions versus baseline."),
    _f("F07", "Discover CTR lift", "traffic", "HIGHER_BETTER", "percentage_points", "28d", "Change in Discover click-through rate versus baseline."),
    _f("F08", "Search hit rate", "traffic", "HIGHER_BETTER", "ratio", "28d", "Share of published cohort passing the predeclared Search success gate."),
    _f("F09", "Discover hit rate", "traffic", "HIGHER_BETTER", "ratio", "28d", "Share of published cohort passing the predeclared Discover success gate."),
    _f("F10", "GA4 sessions lift", "engagement", "HIGHER_BETTER", "ratio", "7d", "Change in article landing sessions versus comparable baseline."),
    _f("F11", "Engaged sessions lift", "engagement", "HIGHER_BETTER", "ratio", "7d", "Change in GA4 engaged sessions versus baseline."),
    _f("F12", "Engagement rate lift", "engagement", "HIGHER_BETTER", "percentage_points", "7d", "Change in GA4 engagement rate versus baseline."),
    _f("F13", "Average engagement time lift", "engagement", "HIGHER_BETTER", "ratio", "7d", "Change in average engagement time versus baseline."),
    _f("F14", "Returning-user rate lift", "engagement", "HIGHER_BETTER", "percentage_points", "28d", "Change in returning-user rate versus baseline."),
    _f("F15", "Qualified journey lift", "commerce", "HIGHER_BETTER", "ratio", "28d", "Change in verified qualified product/service journeys."),
    _f("F16", "Commerce-assisted conversion lift", "commerce", "HIGHER_BETTER", "ratio", "28d", "Change in verified content-assisted commerce conversions."),
    _f("F17", "72h to 7d persistence", "persistence", "HIGHER_BETTER", "ratio", "7d", "Share of positive 72-hour directions remaining positive at seven days."),
    _f("F18", "7d to 28d persistence", "persistence", "HIGHER_BETTER", "ratio", "28d", "Share of positive seven-day directions remaining positive at 28 days."),
    _f("F19", "Cross-run directional agreement", "generalisation", "HIGHER_BETTER", "ratio", "28d", "Directional agreement across distinct publication runs."),
    _f("F20", "Cross-cluster agreement", "generalisation", "HIGHER_BETTER", "ratio", "28d", "Directional agreement across distinct content clusters."),
    _f("F21", "Cross-intent agreement", "generalisation", "HIGHER_BETTER", "ratio", "28d", "Directional agreement across distinct search or decision intents."),
    _f("F22", "Cross-title-pattern agreement", "generalisation", "HIGHER_BETTER", "ratio", "28d", "Directional agreement across title-pattern groups."),
    _f("F23", "Cross-trend-class agreement", "generalisation", "HIGHER_BETTER", "ratio", "28d", "Directional agreement across hot, rising and evergreen classes."),
    _f("F24", "Cross-market agreement", "generalisation", "HIGHER_BETTER", "ratio", "28d", "Directional agreement across declared markets."),
    _f("F25", "Holdout lift", "causality", "HIGHER_BETTER", "ratio", "28d", "Treatment improvement relative to an untouched holdout cohort."),
    _f("F26", "Unseen-entity generalisation", "generalisation", "HIGHER_BETTER", "ratio", "28d", "Performance retained on entities absent from rule-development evidence."),
    _f("F27", "Winner capture recall", "decision_quality", "HIGHER_BETTER", "ratio", "28d", "Share of eventual winners selected or prioritised by the changed Skill."),
    _f("F28", "Loser avoidance precision", "decision_quality", "HIGHER_BETTER", "ratio", "28d", "Share of deprioritised candidates that become mature underperformers."),
    _f("F29", "Outcome variance reduction", "stability", "HIGHER_BETTER", "ratio", "28d", "Relative reduction in outcome variance versus baseline."),
    _f("F30", "Cannibalisation delta", "portfolio", "LOWER_BETTER", "ratio", "28d", "Change in verified query or page cannibalisation incidents."),
    _f("F31", "Selection churn", "stability", "LOWER_BETTER", "ratio", "runtime", "Share of portfolio selections changing under immaterial input changes."),
    _f("F32", "Rule coverage", "evidence_quality", "HIGHER_BETTER", "ratio", "runtime", "Share of material changes with predeclared targets, guardrails and maturity."),
    _f("F33", "Sample adequacy", "evidence_quality", "HIGHER_BETTER", "ratio", "28d", "Share of evaluated cohorts satisfying their declared sample gate."),
    _f("F34", "Source-complete ratio", "evidence_quality", "HIGHER_BETTER", "ratio", "runtime", "Accepted source-complete checkpoints divided by actionable checkpoint inputs."),
    _f("F35", "Context-lineage completeness", "evidence_quality", "HIGHER_BETTER", "ratio", "runtime", "Accepted checkpoints with complete publication, cluster, intent, lane and trend context."),
    _f("F36", "Evidence freshness", "evidence_quality", "LOWER_BETTER", "hours", "runtime", "Age of the newest accepted evidence at observation time."),
    _f("F37", "Missing-data ratio", "evidence_quality", "LOWER_BETTER", "ratio", "runtime", "Source-blocked or immature actionable inputs divided by actionable inputs."),
    _f("F38", "Usable evidence yield", "evidence_quality", "HIGHER_BETTER", "ratio", "runtime", "Accepted checkpoints divided by all inspected checkpoint inputs."),
    _f("F39", "Candidate-pool identity integrity", "lineage", "HIGHER_BETTER", "ratio", "runtime", "Accepted checkpoints carrying an exact publication-run identity."),
    _f("F40", "Baseline comparability", "causality", "HIGHER_BETTER", "ratio", "28d", "Share of treatment observations with a valid same-age comparable baseline."),
    _f("F41", "Effect confidence", "causality", "HIGHER_BETTER", "ratio", "28d", "Predeclared confidence measure for the observed effect."),
    _f("F42", "Confounder penalty", "causality", "LOWER_BETTER", "ratio", "28d", "Share or severity of identified uncontrolled confounders."),
    _f("F43", "Replay determinism", "reliability", "HIGHER_BETTER", "ratio", "runtime", "Share of identical-input replays producing identical outputs."),
    _f("F44", "Provider agreement", "evidence_quality", "HIGHER_BETTER", "ratio", "28d", "Directional agreement among independent acquisition-system families."),
    _f("F45", "Hypothesis direction match", "causality", "HIGHER_BETTER", "ratio", "28d", "Share of target factors moving in the predeclared direction."),
    _f("F46", "Causal attribution strength", "causality", "HIGHER_BETTER", "ratio", "28d", "Strength of attribution after holdout, baseline and confounder checks."),
    _f("F47", "QA pass-rate delta", "quality", "HIGHER_BETTER", "percentage_points", "7d", "Change in independent first-pass QA pass rate."),
    _f("F48", "QA blocker or defect-rate delta", "quality", "LOWER_BETTER", "percentage_points", "7d", "Change in blocker or material defect rate."),
    _f("F49", "Live-verification pass rate", "delivery", "HIGHER_BETTER", "ratio", "runtime", "Share of attempted current-run publications passing all live checks."),
    _f("F50", "Base handoff completion rate", "delivery", "HIGHER_BETTER", "ratio", "runtime", "Share of domain decisions with complete exact-record Base lineage."),
    _f("F51", "Automation execution success rate", "operations", "HIGHER_BETTER", "ratio", "7d", "Share of governed executions ending in a truthful successful state."),
    _f("F52", "Retry convergence", "operations", "HIGHER_BETTER", "ratio", "7d", "Share of retryable failures resolved within the bounded attempt limit."),
    _f("F53", "Scope collision or stale-lock rate", "operations", "LOWER_BETTER", "ratio", "7d", "Share of executions blocked by collisions or stale ownership."),
    _f("F54", "Rollback or reversal rate", "operations", "LOWER_BETTER", "ratio", "90d", "Share of promoted changes later rolled back or directionally reversed."),
    _f("F55", "Notification precision", "operations", "HIGHER_BETTER", "ratio", "7d", "Share of notifications representing distinct actionable or terminal events."),
    _f("F56", "Time to mature evidence", "learning_velocity", "LOWER_BETTER", "hours", "28d", "Elapsed time from change activation to its first mature decision-grade evidence."),
    _f("F57", "Learning cost efficiency", "learning_velocity", "HIGHER_BETTER", "outcome_per_cost", "28d", "Verified decision-grade learning produced per measured compute or labour cost."),
    _f("F58", "Human intervention rate", "operations", "LOWER_BETTER", "ratio", "7d", "Share of low-risk governed executions requiring manual intervention."),
    _f("F59", "Skill version drift incidence", "reliability", "LOWER_BETTER", "ratio", "runtime", "Share of producer, QA or automation executions with an incompatible Skill version."),
    _f("F60", "Promotion survival at D28 and D90", "persistence", "HIGHER_BETTER", "ratio", "90d", "Share of promoted changes still valid at both D+28 and D+90 review."),
)

FACTOR_BY_ID = {factor.factor_id: factor for factor in FACTORS}


class FactorVectorError(ValueError):
    """Raised when evidence cannot form an auditable factor vector."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any, omit: str | None = None) -> str:
    material = value
    if omit and isinstance(value, dict):
        material = {key: item for key, item in value.items() if key != omit}
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FactorVectorError(f"{label} must be a non-empty string")
    return value.strip()


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise FactorVectorError(f"{label} must be a boolean")
    return value


def parse_time(value: Any, label: str) -> datetime:
    text = require_text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FactorVectorError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise FactorVectorError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def load_json(path: pathlib.Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_snapshot(path: pathlib.Path) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict) or payload.get("contract_version") != "performance-learning-v1":
        raise FactorVectorError("learning snapshot must use performance-learning-v1")
    expected = require_text(payload.get("snapshot_fingerprint"), "learning snapshot fingerprint")
    actual = fingerprint(payload, omit="snapshot_fingerprint")
    if expected != actual:
        raise FactorVectorError("learning snapshot fingerprint mismatch")
    return payload


def validate_hypothesis(change: dict[str, Any]) -> dict[str, Any]:
    hypothesis = change.get("hypothesis")
    if not isinstance(hypothesis, dict):
        raise FactorVectorError("change.hypothesis must be an object")
    windows = hypothesis.get("maturity_windows")
    if not isinstance(windows, list) or not windows:
        raise FactorVectorError("hypothesis.maturity_windows must be a non-empty list")
    normal_windows = [require_text(item, "maturity window") for item in windows]
    if len(normal_windows) != len(set(normal_windows)) or set(normal_windows) - WINDOWS:
        raise FactorVectorError("hypothesis maturity windows are duplicate or unsupported")

    seen: set[str] = set()
    result: dict[str, Any] = {"maturity_windows": normal_windows}
    for role, key in (("TARGET", "target_factors"), ("GUARDRAIL", "guardrail_factors")):
        rows = hypothesis.get(key)
        if not isinstance(rows, list) or not rows:
            raise FactorVectorError(f"hypothesis.{key} must be a non-empty list")
        normal_rows = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise FactorVectorError(f"hypothesis.{key}[{index}] must be an object")
            factor_id = require_text(row.get("factor_id"), f"hypothesis.{key}[{index}].factor_id")
            if factor_id not in FACTOR_BY_ID:
                raise FactorVectorError(f"unknown factor in hypothesis: {factor_id}")
            if factor_id in seen:
                raise FactorVectorError(f"duplicate target/guardrail factor: {factor_id}")
            seen.add(factor_id)
            expected_direction = require_text(row.get("expected_direction"), f"hypothesis.{key}[{index}].expected_direction")
            if expected_direction not in {"INCREASE", "DECREASE", "NO_HARM"}:
                raise FactorVectorError(f"unsupported expected direction for {factor_id}")
            factor = FACTOR_BY_ID[factor_id]
            if role == "TARGET":
                required_direction = {
                    "HIGHER_BETTER": "INCREASE",
                    "LOWER_BETTER": "DECREASE",
                }.get(factor.direction)
                if required_direction is None:
                    raise FactorVectorError(
                        f"contextual target {factor_id} requires an explicit contract"
                    )
                if expected_direction != required_direction:
                    raise FactorVectorError(
                        f"target {factor_id} must use expected_direction={required_direction}"
                    )
            elif expected_direction != "NO_HARM":
                raise FactorVectorError(
                    f"guardrail {factor_id} must use expected_direction=NO_HARM"
                )
            threshold = row.get("threshold")
            if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
                raise FactorVectorError(f"hypothesis.{key}[{index}].threshold must be numeric")
            normal_rows.append(
                {
                    "factor_id": factor_id,
                    "role": role,
                    "expected_direction": expected_direction,
                    "threshold": float(threshold),
                }
            )
        result[key] = normal_rows
    return result


def derived_measurements(
    snapshot: dict[str, Any], snapshot_path: pathlib.Path, observed_at: datetime
) -> dict[str, dict[str, Any]]:
    accepted = int(snapshot.get("accepted_checkpoint_count") or 0)
    rejected = int(snapshot.get("rejected_checkpoint_count") or 0)
    reasons = snapshot.get("rejected_by_reason") or {}
    if not isinstance(reasons, dict):
        reasons = {}
    actionable_rejected = sum(
        int(count or 0)
        for reason, count in reasons.items()
        if reason not in {"SUPERSEDED_RETRY", "UNSUPPORTED_CHECKPOINT"}
    )
    actionable_total = accepted + actionable_rejected
    inspected_total = accepted + rejected
    context = snapshot.get("learning_context_completeness") or {}
    source_ref = str(snapshot_path.resolve())
    window = {
        "label": "current-learning-snapshot",
        "start": None,
        "end": snapshot.get("generated_at"),
    }
    result: dict[str, dict[str, Any]] = {}

    def put(factor_id: str, value: float, reason: str) -> None:
        result[factor_id] = {
            "status": "AVAILABLE",
            "value": round(float(value), 6),
            "unit": FACTOR_BY_ID[factor_id].unit,
            "source_refs": [source_ref],
            "observed_window": window,
            "status_reason": reason,
        }

    if actionable_total > 0:
        put("F34", accepted / actionable_total, "Accepted source-complete checkpoints divided by actionable inputs; unsupported and superseded inputs excluded.")
        missing = int(reasons.get("SOURCE_BLOCKED") or 0) + int(reasons.get("DATA_NOT_MATURE") or 0)
        put("F37", missing / actionable_total, "Source-blocked plus immature inputs divided by actionable inputs.")
    if accepted > 0:
        put("F35", int(context.get("complete") or 0) / accepted, "Complete learning-context rows divided by accepted checkpoints.")
        put("F39", int(context.get("with_publication_run_id") or 0) / accepted, "Accepted checkpoints with publication-run identity divided by accepted checkpoints.")
    if inspected_total > 0:
        put("F38", accepted / inspected_total, "Accepted checkpoints divided by all inspected checkpoint inputs.")

    latest: datetime | None = None
    for row in snapshot.get("checkpoints") or []:
        if not isinstance(row, dict) or not row.get("executed_at"):
            continue
        try:
            when = parse_time(row.get("executed_at"), "checkpoint executed_at")
        except FactorVectorError:
            continue
        latest = when if latest is None or when > latest else latest
    if latest is not None and observed_at >= latest:
        put("F36", (observed_at - latest).total_seconds() / 3600, "Age of newest accepted checkpoint at vector observation time.")
    return result


def normalise_measurement(
    factor: Factor,
    raw: Any,
    default_source: str,
    cohort_fingerprint: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise FactorVectorError(f"measurement {factor.factor_id} must be an object")
    status = require_text(raw.get("status"), f"{factor.factor_id}.status")
    if status not in STATUSES:
        raise FactorVectorError(f"unsupported status for {factor.factor_id}: {status}")
    value = raw.get("value")
    if status == "AVAILABLE":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise FactorVectorError(f"AVAILABLE {factor.factor_id} requires numeric value")
        value = round(float(value), 6)
    elif value is not None:
        raise FactorVectorError(f"non-AVAILABLE {factor.factor_id} must use value=null")
    unit = require_text(raw.get("unit") or factor.unit, f"{factor.factor_id}.unit")
    if unit != factor.unit:
        raise FactorVectorError(f"unit mismatch for {factor.factor_id}: expected {factor.unit}")
    refs = raw.get("source_refs") or [default_source]
    if not isinstance(refs, list) or not refs:
        raise FactorVectorError(f"{factor.factor_id}.source_refs must be non-empty")
    refs = [require_text(ref, f"{factor.factor_id}.source_ref") for ref in refs]
    if len(refs) != len(set(refs)):
        raise FactorVectorError(f"duplicate source refs for {factor.factor_id}")
    observed_window = raw.get("observed_window") or {
        "label": factor.maturity_window,
        "start": None,
        "end": None,
    }
    if not isinstance(observed_window, dict):
        raise FactorVectorError(f"{factor.factor_id}.observed_window must be an object")
    return {
        "factor_id": factor.factor_id,
        "factor_name": factor.name,
        "family": factor.family,
        "direction": factor.direction,
        "status": status,
        "value": value,
        "unit": factor.unit,
        "maturity_window": factor.maturity_window,
        "observed_window": observed_window,
        "cohort_fingerprint": require_text(
            raw.get("cohort_fingerprint") or cohort_fingerprint,
            f"{factor.factor_id}.cohort_fingerprint",
        ),
        "source_refs": refs,
        "status_reason": require_text(
            raw.get("status_reason") or "No verified comparable measurement supplied for this vector.",
            f"{factor.factor_id}.status_reason",
        ),
        "description": factor.description,
    }


def build_vector(payload: dict[str, Any], observed_at_override: str | None = None) -> dict[str, Any]:
    if payload.get("contract_version") != INPUT_CONTRACT:
        raise FactorVectorError(f"input contract must be {INPUT_CONTRACT}")
    execution_id = require_text(payload.get("execution_id"), "execution_id")
    change = payload.get("change")
    if not isinstance(change, dict):
        raise FactorVectorError("change must be an object")
    change_id = require_text(change.get("change_id"), "change.change_id")
    before_version = require_text(change.get("before_version"), "change.before_version")
    after_version = require_text(change.get("after_version"), "change.after_version")
    hypothesis = validate_hypothesis(change)
    observed_at_text = observed_at_override or payload.get("observed_at")
    observed_at = parse_time(observed_at_text, "observed_at")

    snapshot_path = pathlib.Path(require_text(payload.get("learning_snapshot_path"), "learning_snapshot_path"))
    snapshot = validate_snapshot(snapshot_path)
    cohort_fingerprint = require_text(
        payload.get("cohort_fingerprint") or snapshot.get("snapshot_fingerprint"),
        "cohort_fingerprint",
    )
    supplied = payload.get("measurements") or {}
    if not isinstance(supplied, dict):
        raise FactorVectorError("measurements must be an object")
    unknown = sorted(set(supplied) - set(FACTOR_BY_ID))
    if unknown:
        raise FactorVectorError(f"unknown measurement factors: {unknown}")
    defaults = payload.get("default_statuses") or {}
    if not isinstance(defaults, dict):
        raise FactorVectorError("default_statuses must be an object")
    for factor_id, status in defaults.items():
        if factor_id not in FACTOR_BY_ID or status not in STATUSES - {"AVAILABLE"}:
            raise FactorVectorError(f"invalid default status for {factor_id}")

    derived = derived_measurements(snapshot, snapshot_path, observed_at)
    default_source = str(snapshot_path.resolve())
    factors = []
    for factor in FACTORS:
        raw = supplied.get(factor.factor_id)
        if raw is None:
            raw = derived.get(factor.factor_id)
        if raw is None:
            status = defaults.get(factor.factor_id, "INSUFFICIENT_SAMPLE")
            raw = {
                "status": status,
                "value": None,
                "unit": factor.unit,
                "source_refs": [default_source],
                "status_reason": (
                    "Factor is outside this governance-only bootstrap change."
                    if status == "NOT_APPLICABLE"
                    else "Required source or instrumentation is not configured."
                    if status == "SOURCE_UNAVAILABLE"
                    else "No mature comparable treatment and baseline sample is available."
                ),
            }
        factors.append(normalise_measurement(factor, raw, default_source, cohort_fingerprint))

    if len(factors) != 60 or [row["factor_id"] for row in factors] != [factor.factor_id for factor in FACTORS]:
        raise FactorVectorError("factor registry completeness invariant failed")
    counts = {status: sum(row["status"] == status for row in factors) for status in sorted(STATUSES)}
    registry_payload = [factor._asdict() for factor in FACTORS]
    output: dict[str, Any] = {
        "contract_version": OUTPUT_CONTRACT,
        "execution_id": execution_id,
        "change_id": change_id,
        "before_version": before_version,
        "after_version": after_version,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "mode": "SHADOW_ONLY",
        "global_score_allowed": False,
        "production_effect": "NONE",
        "factor_count": len(factors),
        "status_counts": counts,
        "hypothesis": hypothesis,
        "learning_snapshot": {
            "path": str(snapshot_path.resolve()),
            "execution_id": snapshot.get("execution_id"),
            "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        },
        "cohort_fingerprint": cohort_fingerprint,
        "registry_fingerprint": fingerprint(registry_payload),
        "factors": factors,
        "hard_boundaries": {
            "may_change_topic_score": False,
            "may_create_demand": False,
            "may_waive_veto": False,
            "may_change_qa_or_discover": False,
            "may_mutate_sanity": False,
            "may_promote_skill": False,
        },
    }
    output["vector_fingerprint"] = fingerprint(output)
    return output


def validate_vector(vector: dict[str, Any]) -> dict[str, Any]:
    """Validate a complete immutable vector before evaluating its hypothesis."""
    if vector.get("contract_version") != OUTPUT_CONTRACT:
        raise FactorVectorError(f"vector contract must be {OUTPUT_CONTRACT}")
    expected_fingerprint = require_text(
        vector.get("vector_fingerprint"), "vector_fingerprint"
    )
    if expected_fingerprint != fingerprint(vector, omit="vector_fingerprint"):
        raise FactorVectorError("vector fingerprint mismatch")
    rows = vector.get("factors")
    if not isinstance(rows, list) or len(rows) != 60 or vector.get("factor_count") != 60:
        raise FactorVectorError("evaluation requires a complete 60-factor vector")
    if [row.get("factor_id") for row in rows if isinstance(row, dict)] != [
        factor.factor_id for factor in FACTORS
    ]:
        raise FactorVectorError("factor registry order mismatch")
    for factor, row in zip(FACTORS, rows):
        if not isinstance(row, dict):
            raise FactorVectorError(f"factor row {factor.factor_id} must be an object")
        expected = {
            "factor_name": factor.name,
            "family": factor.family,
            "direction": factor.direction,
            "unit": factor.unit,
            "maturity_window": factor.maturity_window,
        }
        for key, value in expected.items():
            if row.get(key) != value:
                raise FactorVectorError(
                    f"factor registry metadata mismatch for {factor.factor_id}.{key}"
                )
        status = row.get("status")
        if status not in STATUSES:
            raise FactorVectorError(f"unsupported factor status for {factor.factor_id}")
        value = row.get("value")
        if status == "AVAILABLE":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise FactorVectorError(
                    f"AVAILABLE {factor.factor_id} requires numeric value"
                )
        elif value is not None:
            raise FactorVectorError(
                f"non-AVAILABLE {factor.factor_id} must use value=null"
            )
    hypothesis = vector.get("hypothesis")
    if not isinstance(hypothesis, dict):
        raise FactorVectorError("vector hypothesis must be an object")
    validate_hypothesis({"hypothesis": hypothesis})
    return vector


def _factor_comparator(
    factor: Factor, role: str, expected_direction: str
) -> tuple[str, str]:
    if role == "TARGET":
        if expected_direction == "INCREASE":
            return ">=", "TARGET_INCREASE"
        if expected_direction == "DECREASE":
            return "<=", "TARGET_DECREASE"
        raise FactorVectorError(
            f"target {factor.factor_id} cannot use expected_direction=NO_HARM"
        )
    if expected_direction != "NO_HARM":
        raise FactorVectorError(
            f"guardrail {factor.factor_id} must use expected_direction=NO_HARM"
        )
    if factor.direction == "HIGHER_BETTER":
        return ">=", "GUARDRAIL_MINIMUM"
    if factor.direction == "LOWER_BETTER":
        return "<=", "GUARDRAIL_MAXIMUM"
    raise FactorVectorError(
        f"contextual guardrail {factor.factor_id} requires an explicit comparator"
    )


def _validate_evaluation_context(
    vector: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    if context.get("contract_version") != EVALUATION_INPUT_CONTRACT:
        raise FactorVectorError(
            f"evaluation input contract must be {EVALUATION_INPUT_CONTRACT}"
        )
    identity_fields = {
        "change_id": vector.get("change_id"),
        "execution_id": vector.get("execution_id"),
        "vector_fingerprint": vector.get("vector_fingerprint"),
        "before_version": vector.get("before_version"),
        "after_version": vector.get("after_version"),
    }
    for field, expected in identity_fields.items():
        actual = require_text(context.get(field), f"evaluation.{field}")
        if actual != expected:
            raise FactorVectorError(f"evaluation identity mismatch for {field}")
    evaluation_window = require_text(
        context.get("evaluation_window"), "evaluation.evaluation_window"
    )
    if evaluation_window not in WINDOWS:
        raise FactorVectorError("evaluation_window is unsupported")
    activation_state = require_text(
        context.get("activation_state"), "evaluation.activation_state"
    )
    if activation_state not in ACTIVATION_STATES:
        raise FactorVectorError("activation_state is unsupported")
    affects_traffic = require_bool(
        context.get("affects_traffic_decisions"),
        "evaluation.affects_traffic_decisions",
    )
    production_level = require_text(
        context.get("production_level"), "evaluation.production_level"
    )
    if production_level not in EVALUATION_PRODUCTION_LEVELS:
        raise FactorVectorError("production_level is unsupported")
    if affects_traffic and production_level == "NOT_REQUIRED":
        raise FactorVectorError(
            "traffic-affecting evaluation cannot use production_level=NOT_REQUIRED"
        )
    if not affects_traffic and production_level != "NOT_REQUIRED":
        raise FactorVectorError(
            "non-traffic evaluation must use production_level=NOT_REQUIRED"
        )
    minimum_windows = {
        "OBSERVATION_72H": "72h",
        "CANDIDATE_7D": "7d",
        "DURABLE_28D": "28d",
    }
    minimum_window = minimum_windows.get(production_level)
    if minimum_window and WINDOW_RANK[evaluation_window] < WINDOW_RANK[minimum_window]:
        raise FactorVectorError(
            f"production_level {production_level} is incompatible with evaluation_window"
        )
    verified_experiment_id = None
    if production_level == "VERIFIED_EXPERIMENT":
        verified_experiment_id = require_text(
            context.get("verified_experiment_id"),
            "evaluation.verified_experiment_id",
        )
    evidence_refs = context.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        raise FactorVectorError("evaluation.evidence_refs must be a non-empty list")
    evidence_refs = [
        require_text(ref, "evaluation.evidence_refs item") for ref in evidence_refs
    ]
    if len(evidence_refs) != len(set(evidence_refs)):
        raise FactorVectorError("evaluation.evidence_refs contains duplicates")
    return {
        **identity_fields,
        "evaluation_window": evaluation_window,
        "activation_state": activation_state,
        "affects_traffic_decisions": affects_traffic,
        "production_level": production_level,
        "verified_experiment_id": verified_experiment_id,
        "evidence_refs": evidence_refs,
    }


def evaluate_vector(
    vector: dict[str, Any],
    context: dict[str, Any],
    *,
    vector_path: str | None = None,
    observed_at_override: str | None = None,
) -> dict[str, Any]:
    """Evaluate predeclared target and guardrail factors without activation."""
    validate_vector(vector)
    normal_context = _validate_evaluation_context(vector, context)
    row_by_id = {row["factor_id"]: row for row in vector["factors"]}
    declared_windows = set(vector["hypothesis"]["maturity_windows"])
    selected = []
    for key in ("target_factors", "guardrail_factors"):
        for declaration in vector["hypothesis"][key]:
            factor = FACTOR_BY_ID[declaration["factor_id"]]
            if factor.maturity_window not in declared_windows:
                raise FactorVectorError(
                    f"selected factor {factor.factor_id} maturity window "
                    f"{factor.maturity_window} is not declared"
                )
            row = row_by_id[factor.factor_id]
            role = declaration["role"]
            comparator, comparator_reason = _factor_comparator(
                factor, role, declaration["expected_direction"]
            )
            maturity_reached = (
                normal_context["production_level"] == "VERIFIED_EXPERIMENT"
                or WINDOW_RANK[normal_context["evaluation_window"]]
                >= WINDOW_RANK[factor.maturity_window]
            )
            passed = None
            if maturity_reached and row["status"] == "AVAILABLE":
                if comparator == ">=":
                    passed = float(row["value"]) >= float(declaration["threshold"])
                else:
                    passed = float(row["value"]) <= float(declaration["threshold"])
            selected.append(
                {
                    "factor_id": factor.factor_id,
                    "factor_name": factor.name,
                    "role": role,
                    "status": row["status"],
                    "value": row["value"],
                    "unit": row["unit"],
                    "factor_direction": factor.direction,
                    "expected_direction": declaration["expected_direction"],
                    "threshold": declaration["threshold"],
                    "comparator": comparator,
                    "comparator_reason": comparator_reason,
                    "maturity_window": factor.maturity_window,
                    "evaluation_window": normal_context["evaluation_window"],
                    "maturity_reached": maturity_reached,
                    "passed": passed,
                    "source_refs": row["source_refs"],
                    "status_reason": row["status_reason"],
                }
            )

    invalid = [row for row in selected if row["status"] == "NOT_APPLICABLE"]
    blocked = [row for row in selected if row["status"] == "SOURCE_UNAVAILABLE"]
    immature = [
        row
        for row in selected
        if not row["maturity_reached"] or row["status"] == "INSUFFICIENT_SAMPLE"
    ]
    guardrail_breaches = [
        row
        for row in selected
        if row["role"] == "GUARDRAIL" and row["passed"] is False
    ]
    target_failures = [
        row
        for row in selected
        if row["role"] == "TARGET" and row["passed"] is False
    ]
    reasons: list[str] = []
    if invalid:
        raise FactorVectorError(
            "selected factors cannot be NOT_APPLICABLE: "
            + ",".join(row["factor_id"] for row in invalid)
        )
    if guardrail_breaches:
        decision = "REVERT_REQUIRED"
        reasons.append("MATURE_GUARDRAIL_BREACH")
    elif blocked:
        decision = "SOURCE_BLOCKED"
        reasons.append("SELECTED_FACTOR_SOURCE_UNAVAILABLE")
    elif immature:
        decision = "CONTINUE_OBSERVING"
        reasons.append("SELECTED_FACTOR_NOT_MATURE")
    elif target_failures:
        decision = "NO_EFFECT"
        reasons.append("MATURE_TARGET_THRESHOLD_NOT_MET")
    elif normal_context["affects_traffic_decisions"]:
        if normal_context["production_level"] in {
            "DURABLE_28D",
            "VERIFIED_EXPERIMENT",
        }:
            decision = "PROMOTION_CANDIDATE"
            reasons.append("ALL_FACTORS_PASS_WITH_DURABLE_EVIDENCE")
        elif WINDOW_RANK[normal_context["evaluation_window"]] >= WINDOW_RANK["7d"]:
            decision = "EXPERIMENT_REQUIRED"
            reasons.append("POSITIVE_FACTORS_REQUIRE_GOVERNED_EXPERIMENT_OR_D28")
        else:
            decision = "CONTINUE_OBSERVING"
            reasons.append("POSITIVE_TRAFFIC_FACTORS_BEFORE_7D")
    else:
        decision = "PROMOTION_CANDIDATE"
        reasons.append("NON_TRAFFIC_FACTORS_PASS")
    assert decision in FACTOR_DECISIONS

    observed_at = parse_time(
        observed_at_override or context.get("observed_at") or vector.get("observed_at"),
        "evaluation observed_at",
    ).isoformat().replace("+00:00", "Z")
    result: dict[str, Any] = {
        "contract_version": EVALUATION_OUTPUT_CONTRACT,
        "change_id": vector["change_id"],
        "execution_id": vector["execution_id"],
        "before_version": vector["before_version"],
        "after_version": vector["after_version"],
        "observed_at": observed_at,
        "vector_path": str(pathlib.Path(vector_path).resolve()) if vector_path else None,
        "vector_fingerprint": vector["vector_fingerprint"],
        "evaluation_window": normal_context["evaluation_window"],
        "activation_state": normal_context["activation_state"],
        "affects_traffic_decisions": normal_context["affects_traffic_decisions"],
        "production_level": normal_context["production_level"],
        "verified_experiment_id": normal_context["verified_experiment_id"],
        "evidence_refs": normal_context["evidence_refs"],
        "selected_factor_count": len(selected),
        "factor_results": selected,
        "summary": {
            "passed": sum(row["passed"] is True for row in selected),
            "failed": sum(row["passed"] is False for row in selected),
            "source_blocked": len(blocked),
            "immature_or_insufficient": len(immature),
            "guardrail_breaches": len(guardrail_breaches),
            "target_failures": len(target_failures),
        },
        "decision": decision,
        "reasons": reasons,
        "activation_authority": "MANUAL_APPROVAL_REQUIRED",
        "mutations_performed": False,
        "hard_boundaries": {
            "may_activate_skill": False,
            "may_approve_experiment": False,
            "may_change_topic_score": False,
            "may_create_demand": False,
            "may_waive_veto": False,
            "may_mutate_sanity": False,
        },
        "evaluation_input_fingerprint": fingerprint(context),
    }
    result["evaluation_fingerprint"] = fingerprint(result)
    return result


def build_base_payload(vector: dict[str, Any]) -> dict[str, Any]:
    """Project a validated vector into normalised Base record field maps."""
    if vector.get("contract_version") != OUTPUT_CONTRACT:
        raise FactorVectorError(f"vector contract must be {OUTPUT_CONTRACT}")
    if vector.get("factor_count") != 60 or len(vector.get("factors") or []) != 60:
        raise FactorVectorError("Base payload requires a complete 60-factor vector")
    target_ids = {
        row["factor_id"] for row in vector["hypothesis"].get("target_factors") or []
    }
    guardrail_ids = {
        row["factor_id"] for row in vector["hypothesis"].get("guardrail_factors") or []
    }
    observed = parse_time(vector.get("observed_at"), "vector observed_at").astimezone(
        ZoneInfo("Asia/Hong_Kong")
    )
    observed_cell = observed.strftime("%Y-%m-%d %H:%M:%S")
    records = []
    for row in vector["factors"]:
        factor_id = row["factor_id"]
        identity_material = {
            "change_id": vector["change_id"],
            "execution_id": vector["execution_id"],
            "factor_id": factor_id,
            "vector_fingerprint": vector["vector_fingerprint"],
        }
        role = (
            "TARGET"
            if factor_id in target_ids
            else "GUARDRAIL"
            if factor_id in guardrail_ids
            else "DIAGNOSTIC"
        )
        fields: dict[str, Any] = {
            "观测ID": f"skill-factor-observation-{fingerprint(identity_material)[:24]}",
            "Change ID": vector["change_id"],
            "执行ID": vector["execution_id"],
            "Skill 版本前": vector["before_version"],
            "Skill 版本后": vector["after_version"],
            "Factor ID": factor_id,
            "Factor Name": row["factor_name"],
            "Factor Family": row["family"],
            "Factor Status": row["status"],
            "Unit": row["unit"],
            "Direction": row["direction"],
            "Role": role,
            "Maturity Window": row["maturity_window"],
            "Cohort Fingerprint": row["cohort_fingerprint"],
            "Source Refs": "\n".join(row["source_refs"]),
            "Status Reason": row["status_reason"],
            "Vector Fingerprint": vector["vector_fingerprint"],
            "Observed At": observed_cell,
            "Evidence Validity": "ACTIVE",
        }
        if row["value"] is not None:
            fields["Factor Value"] = row["value"]
        records.append(fields)
    return {"create_records": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--observed-at")
    parser.add_argument("--base-payload-output")
    args = parser.parse_args()
    try:
        payload = load_json(pathlib.Path(args.input))
        if not isinstance(payload, dict):
            raise FactorVectorError("input must be a JSON object")
        output = build_vector(payload, args.observed_at)
        output_path = pathlib.Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if args.base_payload_output:
            base_path = pathlib.Path(args.base_payload_output)
            base_path.parent.mkdir(parents=True, exist_ok=True)
            base_path.write_text(
                json.dumps(build_base_payload(output), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (OSError, json.JSONDecodeError, FactorVectorError) as exc:
        print(f"skill evolution factor vector blocked: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

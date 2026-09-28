#!/usr/bin/env python3
"""Build provenance-bound raw evidence for the 32-factor topic shadow model."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from vertu_content_traffic_gate import (
    AVAILABLE,
    DIRECT_FACTOR_MODEL_CONTRACT_VERSION,
    DIRECT_FACTOR_REGISTRY,
    INSUFFICIENT_SAMPLE,
    NOT_APPLICABLE,
    SOURCE_UNAVAILABLE,
    _provider_family,
)


CONTRACT_VERSION = "content-factor-extractor-v1"


def _load(path: Optional[Path]) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalise(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _observed(payload: Any, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback
    for key in ("fetched_at", "observed_at", "generated_at", "verified_at"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return fallback


def _ref(path: Optional[Path], fragment: str = "") -> str:
    if path is None:
        return ""
    suffix = f"#{fragment}" if fragment else ""
    return f"{path.resolve()}{suffix}"


def _available(
    raw_value: float,
    observed_at: str,
    refs: Iterable[str],
    **extra: Any,
) -> dict[str, Any]:
    row = {
        "status": AVAILABLE,
        "raw_value": raw_value,
        "observed_at": observed_at,
        "evidence_refs": [str(ref) for ref in refs if str(ref).strip()],
    }
    row.update(extra)
    return row


def _state(
    status: str,
    reason: str,
    observed_at: str,
    refs: Iterable[str] = (),
    raw_value: Optional[float] = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "status": status,
        "reason": reason,
        "observed_at": observed_at,
    }
    evidence_refs = [str(ref) for ref in refs if str(ref).strip()]
    if evidence_refs:
        row["evidence_refs"] = evidence_refs
    if raw_value is not None:
        row["raw_value"] = raw_value
    return row


def _query(candidate: dict[str, Any]) -> str:
    boundary = _normalise(candidate.get("query_intent_boundary"))
    if boundary:
        return boundary
    for signal in candidate.get("demand_signals") or []:
        if not isinstance(signal, dict):
            continue
        metrics = signal.get("metrics") or {}
        value = _normalise(metrics.get("keyword") or metrics.get("trend_query"))
        if value:
            return value
    return _normalise(candidate.get("title"))


def _index_keyword_planner(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    rows = list(payload.get("seed_metrics") or []) + list(
        payload.get("related_ideas") or []
    )
    return {
        _normalise(row.get("keyword")): row
        for row in rows
        if isinstance(row, dict) and _normalise(row.get("keyword"))
    }


def _index_mapping(payload: Any, key: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), dict):
        return {}
    return {_normalise(name): row for name, row in payload[key].items()}


def _index_rows(payload: Any, key: str, id_key: str) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    return {
        str(row.get(id_key) or "").strip(): row
        for row in payload.get(key) or []
        if isinstance(row, dict) and str(row.get(id_key) or "").strip()
    }


def _growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous <= 0:
        return None
    return (current - previous) * 100.0 / previous


def _stability(values: list[float]) -> Optional[float]:
    if len(values) < 3:
        return None
    mean = sum(values) / len(values)
    if mean <= 0:
        return None
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    coefficient = math.sqrt(variance) / mean
    return max(0.0, 1.0 - min(coefficient, 1.0))


def _candidate_positive_families(candidate: dict[str, Any]) -> set[str]:
    families = set()
    for signal in candidate.get("demand_signals") or []:
        if not isinstance(signal, dict):
            continue
        if str(signal.get("status") or "").upper() != AVAILABLE:
            continue
        if signal.get("positive") is not True:
            continue
        family, role = _provider_family(str(signal.get("provider") or ""), signal)
        if role == "acquisition":
            families.add(family)
    return families


def _candidate_markets(candidate: dict[str, Any]) -> set[str]:
    markets = set()
    for signal in candidate.get("demand_signals") or []:
        if not isinstance(signal, dict) or signal.get("positive") is not True:
            continue
        metrics = signal.get("metrics") or {}
        values = metrics.get("markets") or [metrics.get("market") or metrics.get("geo")]
        for value in values:
            market = str(value or "").strip().upper()
            if market:
                markets.add(market)
    return markets


def _trend_signal(candidate: dict[str, Any]) -> Optional[dict[str, Any]]:
    for signal in candidate.get("demand_signals") or []:
        if not isinstance(signal, dict):
            continue
        family, _ = _provider_family(str(signal.get("provider") or ""), signal)
        if family == "google_trends" and signal.get("positive") is True:
            return signal
    return None


def _semantic_checks(
    candidate: dict[str, Any], visual_occurrences: dict[str, int]
) -> dict[str, tuple[int, list[dict[str, Any]]]]:
    candidate_id = str(candidate.get("candidate_id") or "").strip()
    forecast = candidate.get("predraft_discover_forecast") or {}
    visual = str(
        candidate.get("visual_subject") or forecast.get("concrete_visual") or ""
    ).strip()
    visual_key = _normalise(visual)
    forbidden = (
        "generic black and gold",
        "abstract glass panel",
        "generic technology background",
    )
    visual_checks = [
        {"check": "visual_subject_present", "passed": bool(visual)},
        {"check": "visual_has_eight_words", "passed": len(visual.split()) >= 8},
        {
            "check": "visual_unique_within_batch",
            "passed": bool(visual_key) and visual_occurrences.get(visual_key) == 1,
        },
        {
            "check": "visual_avoids_forbidden_generic_patterns",
            "passed": not any(value in visual.casefold() for value in forbidden),
        },
    ]
    decision_checks = [
        {"check": "decision_intent_present", "passed": bool(candidate.get("decision_intent"))},
        {"check": "query_boundary_present", "passed": bool(candidate.get("query_intent_boundary"))},
        {"check": "reader_consequence_present", "passed": bool(forecast.get("reader_consequence"))},
        {"check": "value_object_present", "passed": bool(candidate.get("value_object"))},
        {
            "check": "valid_outcome_lane",
            "passed": str(candidate.get("outcome_lane") or "").casefold()
            in {"search-first", "discover-first", "authority-first"},
        },
    ]
    original_block = (candidate.get("dimension_evidence") or {}).get("original_value") or {}
    exact_overlap = int(
        _number((candidate.get("inventory_overlap") or {}).get("exactish_count")) or 0
    )
    primary = str(candidate.get("primary_source") or "").strip()
    secondary = str(candidate.get("secondary_source") or "").strip()
    original_checks = [
        {"check": "value_object_present", "passed": bool(candidate.get("value_object"))},
        {
            "check": "two_distinct_sources",
            "passed": bool(primary and secondary and primary != secondary),
        },
        {
            "check": "original_value_evidence_present",
            "passed": bool(original_block.get("evidence_refs")),
        },
        {"check": "no_exact_inventory_overlap", "passed": exact_overlap == 0},
    ]
    historical_block = (candidate.get("dimension_evidence") or {}).get("historical_fit") or {}
    vetoes = {str(value) for value in candidate.get("vetoes") or []}
    right_checks = [
        {
            "check": "audience_fit_present",
            "passed": bool(candidate.get("audience_fit_lane") or candidate.get("audience_lane")),
        },
        {"check": "cluster_present", "passed": bool(candidate.get("cluster_id"))},
        {
            "check": "historical_fit_evidence_present",
            "passed": bool(historical_block.get("evidence_refs")),
        },
        {
            "check": "brand_insertion_not_forced",
            "passed": "forced_brand_insertion" not in vetoes,
        },
    ]
    return {
        "visual_specificity_checks_passed": (
            sum(row["passed"] for row in visual_checks),
            visual_checks,
        ),
        "reader_decision_checks_passed": (
            sum(row["passed"] for row in decision_checks),
            decision_checks,
        ),
        "original_value_checks_passed": (
            sum(row["passed"] for row in original_checks),
            original_checks,
        ),
        "vertu_right_to_win_checks_passed": (
            sum(row["passed"] for row in right_checks),
            right_checks,
        ),
    }


def extract_candidate(
    candidate: dict[str, Any],
    *,
    observed_at: str,
    paths: dict[str, Optional[Path]],
    keyword_rows: dict[str, dict[str, Any]],
    keyword_payload: Any,
    gsc_rows: dict[str, Any],
    gsc_payload: Any,
    realtime_payload: Any,
    velocity_rows: dict[str, dict[str, Any]],
    velocity_payload: Any,
    visual_occurrences: dict[str, int],
) -> dict[str, Any]:
    row = copy.deepcopy(candidate)
    factor: dict[str, dict[str, Any]] = {}
    query = _query(row)
    candidate_id = str(row.get("candidate_id") or "").strip()
    candidate_ref = f"candidate://{candidate_id or query}"

    keyword_observed = _observed(keyword_payload, observed_at)
    keyword_ref = _ref(paths.get("keyword_planner"), query)
    keyword = keyword_rows.get(query)
    if keyword:
        average = _number(keyword.get("average_monthly_searches"))
        monthly_rows = [
            value
            for value in keyword.get("monthly_search_volumes") or []
            if isinstance(value, dict)
        ]
        monthly_values = [
            value
            for value in (_number(item.get("monthly_searches")) for item in monthly_rows)
            if value is not None
        ]
        recent = monthly_values[-1] if monthly_values else None
        previous = monthly_values[-2] if len(monthly_values) >= 2 else None
        stability = _stability(monthly_values)
        values = {
            "keyword_planner_avg_monthly_searches": average,
            "keyword_planner_recent_searches": recent,
            "keyword_planner_growth_pct": _growth(recent, previous),
            "keyword_planner_stability": stability,
        }
        for name, value in values.items():
            if value is None:
                factor[name] = _state(
                    INSUFFICIENT_SAMPLE,
                    "Keyword Planner row lacks the required monthly series",
                    keyword_observed,
                    [keyword_ref],
                )
            else:
                factor[name] = _available(value, keyword_observed, [keyword_ref])
    else:
        state = SOURCE_UNAVAILABLE if keyword_payload is None else INSUFFICIENT_SAMPLE
        reason = (
            "Keyword Planner artifact unavailable"
            if keyword_payload is None
            else "Exact candidate query absent from Keyword Planner response"
        )
        for name in (
            "keyword_planner_avg_monthly_searches",
            "keyword_planner_recent_searches",
            "keyword_planner_growth_pct",
            "keyword_planner_stability",
        ):
            factor[name] = _state(state, reason, keyword_observed, [keyword_ref])

    gsc_observed = _observed(gsc_payload, observed_at)
    gsc_ref = _ref(paths.get("targeted_gsc"), query)
    gsc = gsc_rows.get(query)
    recent = (gsc or {}).get("recent_28d") or {}
    annual = (gsc or {}).get("trailing_365d") or {}
    selected = recent if int(recent.get("row_count") or 0) > 0 else annual
    if selected and int(selected.get("row_count") or 0) > 0:
        clicks = _number(selected.get("clicks")) or 0.0
        impressions = _number(selected.get("impressions")) or 0.0
        factor["gsc_candidate_clicks"] = _available(clicks, gsc_observed, [gsc_ref])
        factor["gsc_candidate_impressions"] = _available(
            impressions, gsc_observed, [gsc_ref]
        )
        if impressions > 0:
            factor["gsc_candidate_ctr"] = _available(
                clicks / impressions, gsc_observed, [gsc_ref]
            )
        else:
            factor["gsc_candidate_ctr"] = _state(
                INSUFFICIENT_SAMPLE,
                "Finalised GSC candidate sample has no impressions",
                gsc_observed,
                [gsc_ref],
            )
        previous = (gsc or {}).get("previous_28d") or {}
        growth = _growth(_number(recent.get("clicks")), _number(previous.get("clicks")))
        factor["gsc_candidate_growth_pct"] = (
            _available(growth, gsc_observed, [gsc_ref])
            if growth is not None
            else _state(
                INSUFFICIENT_SAMPLE,
                "Candidate-level comparable previous GSC window unavailable",
                gsc_observed,
                [gsc_ref],
            )
        )
    else:
        state = SOURCE_UNAVAILABLE if gsc_payload is None else INSUFFICIENT_SAMPLE
        reason = (
            "Targeted GSC artifact unavailable"
            if gsc_payload is None
            else "Newest finalised candidate query windows returned no rows"
        )
        for name in (
            "gsc_candidate_clicks",
            "gsc_candidate_impressions",
            "gsc_candidate_ctr",
            "gsc_candidate_growth_pct",
        ):
            factor[name] = _state(state, reason, gsc_observed, [gsc_ref])

    families = _candidate_positive_families(row)
    factor["demand_provider_family_count"] = _available(
        float(len(families)), observed_at, [f"{candidate_ref}#demand_signals"]
    )
    markets = _candidate_markets(row)
    factor["demand_market_count"] = (
        _available(float(len(markets)), observed_at, [f"{candidate_ref}#demand_signals"])
        if markets
        else _state(
            INSUFFICIENT_SAMPLE,
            "Candidate evidence does not expose market-level positive demand",
            observed_at,
            [f"{candidate_ref}#demand_signals"],
        )
    )

    trend = _trend_signal(row)
    trend_metrics = (trend or {}).get("metrics") or {}
    trend_observed = str((trend or {}).get("observed_at") or "").strip() or _observed(
        realtime_payload, observed_at
    )
    trend_ref = str((trend or {}).get("evidence_ref") or "").strip() or _ref(
        paths.get("realtime_trends"), query
    )
    topic = None
    if isinstance(realtime_payload, dict):
        topic = next(
            (
                item
                for item in realtime_payload.get("topics") or []
                if isinstance(item, dict) and _normalise(item.get("query")) == query
            ),
            None,
        )
    if trend is None and topic is None:
        for name in (
            "official_trends_interest",
            "official_trends_growth_pct",
            "official_trends_market_count",
            "official_trends_freshness_hours",
            "trend_persistence_periods",
        ):
            factor[name] = _state(
                NOT_APPLICABLE,
                "Candidate has no exact official Google Trends evidence",
                trend_observed,
                [trend_ref],
            )
    else:
        interest = _number(trend_metrics.get("interest"))
        growth = _number(trend_metrics.get("growth_pct"))
        if growth is None:
            growth = _growth(
                _number(trend_metrics.get("current_period_value")),
                _number(trend_metrics.get("previous_period_value")),
            )
        trend_values = {
            "official_trends_interest": interest,
            "official_trends_growth_pct": growth,
            "official_trends_market_count": float(
                len((topic or {}).get("markets") or trend_metrics.get("markets") or [])
            ),
            "official_trends_freshness_hours": _number(
                (topic or {}).get("minimum_age_hours")
            )
            if topic
            else _number(trend_metrics.get("age_hours")),
            "trend_persistence_periods": _number(
                trend_metrics.get("persistence_periods")
            ),
        }
        for name, value in trend_values.items():
            if value is None:
                factor[name] = _state(
                    INSUFFICIENT_SAMPLE,
                    "Official Trends evidence lacks the required raw metric",
                    trend_observed,
                    [trend_ref],
                )
            else:
                factor[name] = _available(value, trend_observed, [trend_ref])

    velocity = velocity_rows.get(candidate_id)
    velocity_observed = _observed(velocity_payload, observed_at)
    velocity_ref = _ref(paths.get("source_velocity"), candidate_id)
    if velocity:
        coverage = _number(
            velocity.get("independent_coverage_count")
            or velocity.get("independent_coverage")
        )
        community = _number(
            velocity.get("community_velocity") or velocity.get("velocity_score")
        )
        for name, value in (
            ("editorial_independent_coverage_count", coverage),
            ("editorial_community_velocity", community),
        ):
            factor[name] = (
                _available(value, velocity_observed, [velocity_ref])
                if value is not None
                else _state(
                    INSUFFICIENT_SAMPLE,
                    "Editorial velocity row lacks the required raw metric",
                    velocity_observed,
                    [velocity_ref],
                )
            )
    else:
        for name in (
            "editorial_independent_coverage_count",
            "editorial_community_velocity",
        ):
            factor[name] = _state(
                NOT_APPLICABLE
                if str(row.get("editorial_signal") or "").upper() == "NONE"
                else SOURCE_UNAVAILABLE,
                "Candidate has no editorial breakout velocity row",
                velocity_observed,
                [velocity_ref],
            )

    published_at = str(row.get("primary_source_published_at") or "").strip()
    if published_at:
        try:
            published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            age_hours = max(0.0, (observed - published).total_seconds() / 3600.0)
            factor["primary_source_freshness_hours"] = _available(
                age_hours, observed_at, [f"{candidate_ref}#primary_source_published_at"]
            )
        except ValueError:
            factor["primary_source_freshness_hours"] = _state(
                SOURCE_UNAVAILABLE,
                "Primary source publication timestamp is invalid",
                observed_at,
                [f"{candidate_ref}#primary_source_published_at"],
            )
    else:
        factor["primary_source_freshness_hours"] = _state(
            SOURCE_UNAVAILABLE,
            "Primary source publication timestamp unavailable before scoring",
            observed_at,
            [f"{candidate_ref}#primary_source"],
        )

    historical = row.get("historical_cluster_metrics") or {}
    historical_ref = str(historical.get("evidence_ref") or "").strip() or f"{candidate_ref}#historical_cluster_metrics"
    historical_values = {
        "historical_discover_cluster_clicks": _number(historical.get("discover_clicks")),
        "historical_discover_cluster_ctr": _number(historical.get("discover_ctr")),
        "historical_search_cluster_clicks": _number(historical.get("search_clicks")),
        "historical_search_cluster_ctr": _number(historical.get("search_ctr")),
        "historical_ga4_engagement_rate": _number(historical.get("ga4_engagement_rate")),
        "historical_cluster_growth_pct": _number(historical.get("growth_pct")),
    }
    for name, value in historical_values.items():
        factor[name] = (
            _available(value, observed_at, [historical_ref])
            if value is not None
            else _state(
                SOURCE_UNAVAILABLE,
                "Candidate lacks raw same-cluster historical outcome metrics",
                observed_at,
                [historical_ref],
            )
        )

    serp = row.get("serp_metrics") or {}
    serp_ref = str(serp.get("evidence_ref") or "").strip() or f"{candidate_ref}#serp_metrics"
    for name, value in (
        ("serp_weak_result_count", _number(serp.get("weak_result_count"))),
        ("serp_freshness_gap_days", _number(serp.get("freshness_gap_days"))),
    ):
        factor[name] = (
            _available(value, observed_at, [serp_ref])
            if value is not None
            else _state(
                SOURCE_UNAVAILABLE,
                "Candidate lacks reproducible SERP raw metrics",
                observed_at,
                [serp_ref],
            )
        )

    overlap = int(
        _number((row.get("inventory_overlap") or {}).get("exactish_count")) or 0
    )
    inventory_ref = _ref(paths.get("sanity_inventory"), candidate_id) or f"{candidate_ref}#inventory_overlap"
    factor["sanity_exact_intent_overlap_count"] = _available(
        float(overlap), observed_at, [inventory_ref]
    )
    boundary = str(row.get("query_intent_boundary") or "").strip()
    safety = max(0.0, 1.0 - min(overlap, 3) / 3.0) if boundary else 0.0
    factor["cannibalisation_safety"] = _available(
        safety,
        observed_at,
        [inventory_ref, f"{candidate_ref}#query_intent_boundary"],
        calculation="max(0, 1 - min(exact_overlap, 3) / 3) when query boundary exists",
    )

    for name, (count, checks) in _semantic_checks(row, visual_occurrences).items():
        factor[name] = _available(
            float(count),
            observed_at,
            [f"{candidate_ref}#{name}"],
            checks=checks,
        )

    missing = set(DIRECT_FACTOR_REGISTRY) - set(factor)
    if missing:
        raise RuntimeError(f"extractor failed to emit factors: {sorted(missing)}")
    row["direct_factor_evidence"] = factor
    return row


def extract(
    payload: Any,
    *,
    observed_at: str,
    paths: dict[str, Optional[Path]],
) -> tuple[Any, dict[str, Any]]:
    candidates = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(candidates, list) or not all(
        isinstance(row, dict) for row in candidates
    ):
        raise ValueError("input must be a candidate list or contain candidates")

    keyword_payload = _load(paths.get("keyword_planner"))
    gsc_payload = _load(paths.get("targeted_gsc"))
    realtime_payload = _load(paths.get("realtime_trends"))
    velocity_payload = _load(paths.get("source_velocity"))
    keyword_rows = _index_keyword_planner(keyword_payload)
    gsc_rows = _index_mapping(gsc_payload, "candidates")
    velocity_rows = _index_rows(velocity_payload, "candidates", "candidate_id")
    visual_occurrences: dict[str, int] = {}
    for candidate in candidates:
        forecast = candidate.get("predraft_discover_forecast") or {}
        key = _normalise(
            candidate.get("visual_subject") or forecast.get("concrete_visual")
        )
        if key:
            visual_occurrences[key] = visual_occurrences.get(key, 0) + 1

    enriched = [
        extract_candidate(
            candidate,
            observed_at=observed_at,
            paths=paths,
            keyword_rows=keyword_rows,
            keyword_payload=keyword_payload,
            gsc_rows=gsc_rows,
            gsc_payload=gsc_payload,
            realtime_payload=realtime_payload,
            velocity_rows=velocity_rows,
            velocity_payload=velocity_payload,
            visual_occurrences=visual_occurrences,
        )
        for candidate in candidates
    ]
    output = copy.deepcopy(payload)
    if isinstance(output, dict):
        output["candidates"] = enriched
    else:
        output = enriched

    status_counts = {
        name: {status: 0 for status in (AVAILABLE, SOURCE_UNAVAILABLE, NOT_APPLICABLE, INSUFFICIENT_SAMPLE)}
        for name in DIRECT_FACTOR_REGISTRY
    }
    for candidate in enriched:
        for name, block in candidate["direct_factor_evidence"].items():
            status = str(block.get("status") or "")
            status_counts[name].setdefault(status, 0)
            status_counts[name][status] += 1
    summary = {
        "contract_version": CONTRACT_VERSION,
        "factor_contract_version": DIRECT_FACTOR_MODEL_CONTRACT_VERSION,
        "observed_at": observed_at,
        "candidate_count": len(enriched),
        "factor_count": len(DIRECT_FACTOR_REGISTRY),
        "candidate_factor_row_count": len(enriched) * len(DIRECT_FACTOR_REGISTRY),
        "factor_status_counts": status_counts,
        "source_paths": {
            name: str(path.resolve()) if path is not None else None
            for name, path in paths.items()
        },
        "credentials_included": False,
    }
    summary["snapshot_fingerprint"] = _fingerprint(summary)
    return output, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--keyword-planner", type=Path)
    parser.add_argument("--targeted-gsc", type=Path)
    parser.add_argument("--realtime-trends", type=Path)
    parser.add_argument("--source-velocity", type=Path)
    parser.add_argument("--sanity-inventory", type=Path)
    parser.add_argument("--observed-at")
    args = parser.parse_args()
    observed_at = args.observed_at or datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    paths = {
        "keyword_planner": args.keyword_planner,
        "targeted_gsc": args.targeted_gsc,
        "realtime_trends": args.realtime_trends,
        "source_velocity": args.source_velocity,
        "sanity_inventory": args.sanity_inventory,
    }
    output, summary = extract(
        _load(args.input), observed_at=observed_at, paths=paths
    )
    _write(args.output, output)
    _write(args.summary, summary)
    print(
        json.dumps(
            {
                "status": "OK",
                "candidate_count": summary["candidate_count"],
                "factor_count": summary["factor_count"],
                "snapshot_fingerprint": summary["snapshot_fingerprint"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

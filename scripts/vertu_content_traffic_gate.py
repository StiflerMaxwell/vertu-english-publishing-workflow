#!/usr/bin/env python3
"""Deterministic demand scoring, learning-prior ordering and traffic diagnosis."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import math
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse


SCORE_WEIGHTS = {
    "market_demand": 25,
    "historical_fit": 20,
    "trend_velocity": 15,
    "serp_gap": 15,
    "discover_story": 10,
    "original_value": 10,
    "right_to_win": 5,
}

DIMENSION_KEYS = tuple(key for key in SCORE_WEIGHTS if key != "market_demand")
PASSING_SCORE = 80.0
AVAILABLE = "AVAILABLE"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
TREND_CLASSES = {"REALTIME_HOT", "RISING_SEARCH", "EVERGREEN_SEARCH"}
EDITORIAL_SIGNALS = {"EDITORIAL_BREAKOUT", "CURRENT_CONFIRMED", "NONE"}
TREND_VELOCITY_CAPS = {
    "REALTIME_HOT": 100.0,
    "RISING_SEARCH": 75.0,
    "EVERGREEN_SEARCH": 45.0,
}
REALTIME_TRENDS_PROVIDERS = {
    "google_trends_realtime",
    "google_trends_trending_now",
}
REALTIME_SOURCE_METHODS = {
    "api_alpha",
    "official_api_alpha",
    "official_trending_now_rss",
    "official_trending_now_csv",
    "official_trending_now_ui_export",
}
PRIMARY_SOURCE_RELATIONS = {
    "official_announcement",
    "release_note",
    "regulator_notice",
    "event_source",
}
LEARNING_SCOPE_FIELDS = {
    "cluster_id",
    "trend_class",
    "section",
    "outcome_lane",
    "intent_key",
    "portfolio_bucket",
}
MAX_LEARNING_ADJUSTMENT = 3.0
D2TR_MAX_ADJUSTMENT = 2.0
D2TR_MAX_CONTEXT_AGE_HOURS = 8.0
TRAFFIC_GATE_CONTRACT_VERSION = "traffic-acquisition-v3.12.0"
TRAFFIC_GATE_RUNTIME_VERSION = "3.12.0"
SCORE_SOURCE = "computed_v3_12_0"
HYBRID_TRAFFIC_GATE_CONTRACT_VERSION = "traffic-acquisition-v3.16.0-trial"
HYBRID_SCORE_SOURCE = "computed_hybrid_v3_16_0_trial"
FACTOR_SCORE_MODES = {"legacy", "hybrid_trial"}
BRAND_MINDSET_GATE_CONTRACT_VERSION = "brand-mindset-fit-v1"
BRAND_MINDSET_CLASSES = {"CORE_MINDSPACE", "QUALIFIED_ADJACENT"}
BRAND_MINDSET_PROFILES = {"stable", "recovery"}
BRAND_CONFLICT_VETO_MAP = {
    "COMMODITY_LIFESTYLE_MISMATCH": "commodity_lifestyle_mismatch",
    "FORCED_BRAND_ASSOCIATION": "forced_brand_association",
    "PRICE_ONLY_LUXURY_LABEL": "price_only_luxury_label",
    "OUTSIDE_BRAND_MINDSPACE": "outside_brand_mindspace",
}
HYBRID_LEGACY_WEIGHT = 0.80
HYBRID_FACTOR_WEIGHT = 0.20
HYBRID_MIN_FACTOR_COVERAGE = 30.0
HYBRID_MAX_COVERAGE_PENALTY = 15.0
HYBRID_COVERAGE_PENALTY_PER_POINT = 0.20
HYBRID_CORE_FACTORS = (
    "demand_provider_family_count",
    "sanity_exact_intent_overlap_count",
    "cannibalisation_safety",
    "visual_specificity_checks_passed",
    "reader_decision_checks_passed",
    "original_value_checks_passed",
    "vertu_right_to_win_checks_passed",
)
HYBRID_DEMAND_MAGNITUDE_FACTORS = (
    "keyword_planner_avg_monthly_searches",
    "keyword_planner_recent_searches",
    "gsc_candidate_clicks",
    "gsc_candidate_impressions",
    "official_trends_interest",
)
GSC_MIN_CLICKS = 3
GSC_MIN_IMPRESSIONS = 100
SEARCH_DEMAND_PROVIDER_FAMILIES = {
    "gsc",
    "google_trends",
    "google_ads_keyword_planner",
}

DIRECT_FACTOR_MODEL_CONTRACT_VERSION = "content-factor-model-v1"
DIRECT_FACTOR_SCORE_SOURCE = "computed_factor_v1_shadow"
DIRECT_FACTOR_MIN_DIAGNOSTIC_COVERAGE = 70.0
DIRECT_FACTOR_REGISTRY: Dict[str, Dict[str, Any]] = {
    "keyword_planner_avg_monthly_searches": {
        "weight": 6.0,
        "transform": "log",
        "minimum": 10.0,
        "maximum": 100_000.0,
    },
    "keyword_planner_recent_searches": {
        "weight": 4.0,
        "transform": "log",
        "minimum": 10.0,
        "maximum": 100_000.0,
    },
    "keyword_planner_growth_pct": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": -50.0,
        "maximum": 100.0,
    },
    "keyword_planner_stability": {
        "weight": 2.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 1.0,
    },
    "gsc_candidate_clicks": {
        "weight": 4.0,
        "transform": "log",
        "minimum": 1.0,
        "maximum": 1_000.0,
    },
    "gsc_candidate_impressions": {
        "weight": 4.0,
        "transform": "log",
        "minimum": 100.0,
        "maximum": 100_000.0,
    },
    "gsc_candidate_ctr": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 0.10,
    },
    "gsc_candidate_growth_pct": {
        "weight": 2.0,
        "transform": "linear",
        "minimum": -50.0,
        "maximum": 100.0,
    },
    "demand_provider_family_count": {
        "weight": 4.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 3.0,
    },
    "demand_market_count": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 9.0,
    },
    "official_trends_interest": {
        "weight": 4.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 100.0,
    },
    "official_trends_growth_pct": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": -50.0,
        "maximum": 200.0,
    },
    "official_trends_market_count": {
        "weight": 2.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 9.0,
    },
    "official_trends_freshness_hours": {
        "weight": 2.0,
        "transform": "inverse_linear",
        "minimum": 0.0,
        "maximum": 24.0,
    },
    "trend_persistence_periods": {
        "weight": 2.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 6.0,
    },
    "editorial_independent_coverage_count": {
        "weight": 2.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 5.0,
    },
    "editorial_community_velocity": {
        "weight": 1.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 100.0,
    },
    "primary_source_freshness_hours": {
        "weight": 2.0,
        "transform": "inverse_linear",
        "minimum": 0.0,
        "maximum": 72.0,
    },
    "historical_discover_cluster_clicks": {
        "weight": 5.0,
        "transform": "log",
        "minimum": 1.0,
        "maximum": 100_000.0,
    },
    "historical_discover_cluster_ctr": {
        "weight": 4.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 0.10,
    },
    "historical_search_cluster_clicks": {
        "weight": 4.0,
        "transform": "log",
        "minimum": 1.0,
        "maximum": 100_000.0,
    },
    "historical_search_cluster_ctr": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 0.10,
    },
    "historical_ga4_engagement_rate": {
        "weight": 2.0,
        "transform": "linear",
        "minimum": 0.20,
        "maximum": 0.80,
    },
    "historical_cluster_growth_pct": {
        "weight": 2.0,
        "transform": "linear",
        "minimum": -50.0,
        "maximum": 100.0,
    },
    "serp_weak_result_count": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 5.0,
    },
    "serp_freshness_gap_days": {
        "weight": 2.0,
        "transform": "log",
        "minimum": 1.0,
        "maximum": 1_095.0,
    },
    "sanity_exact_intent_overlap_count": {
        "weight": 5.0,
        "transform": "inverse_linear",
        "minimum": 0.0,
        "maximum": 3.0,
    },
    "cannibalisation_safety": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 1.0,
    },
    "visual_specificity_checks_passed": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 4.0,
    },
    "reader_decision_checks_passed": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 5.0,
    },
    "original_value_checks_passed": {
        "weight": 5.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 4.0,
    },
    "vertu_right_to_win_checks_passed": {
        "weight": 3.0,
        "transform": "linear",
        "minimum": 0.0,
        "maximum": 4.0,
    },
}

if len(DIRECT_FACTOR_REGISTRY) != 32:
    raise RuntimeError("direct factor registry must contain exactly 32 factors")
if not math.isclose(
    sum(float(spec["weight"]) for spec in DIRECT_FACTOR_REGISTRY.values()),
    100.0,
    abs_tol=1e-9,
):
    raise RuntimeError("direct factor registry weights must total 100")


def _provider_family(
    provider: str, signal: Optional[Dict[str, Any]] = None
) -> Tuple[str, str]:
    """Return the acquisition-system family and the signal's demand role."""

    provider = str(provider or "").strip().casefold()
    if provider == "gsc" or provider.startswith("gsc_"):
        return "gsc", "acquisition"
    if (
        provider in REALTIME_TRENDS_PROVIDERS
        or provider == "official_google_trends"
        or provider.startswith("google_trends")
    ):
        return "google_trends", "acquisition"
    if (
        provider in {"keyword_planner", "google_ads_keyword_planner"}
        or provider.startswith("keyword_planner_")
        or provider.startswith("google_ads_keyword_planner_")
    ):
        return "google_ads_keyword_planner", "acquisition"

    signal = signal or {}
    evidence_ref = str(signal.get("evidence_ref") or "").casefold()
    metrics = signal.get("metrics") or {}
    if provider == "current_interest" and (
        "keyword-planner" in evidence_ref
        or "keyword_planner" in evidence_ref
        or any(
            key in metrics
            for key in (
                "average_monthly_searches",
                "recent_month_searches",
                "monthly_searches",
            )
        )
    ):
        return "google_ads_keyword_planner", "supporting_current"
    if provider in {"current_event", "current_interest", "news_cycle"}:
        return "supporting_current", "supporting_current"
    if provider in {
        "editorial_breakout",
        "hacker_news",
        "reddit",
        "techmeme",
        "multi_publisher_cluster",
    }:
        return "supporting_editorial", "supporting_editorial"
    return "supporting_other", "supporting_other"


def _gsc_sample_metrics(metrics: Dict[str, Any]) -> Tuple[float, float, str]:
    """Read candidate GSC sample metrics in finalised-window priority order."""

    metric_windows = (
        ("recent_clicks", "recent_impressions", "recent_finalised"),
        ("annual_clicks", "annual_impressions", "annual_finalised"),
        ("clicks", "impressions", "generic"),
    )
    for clicks_key, impressions_key, window in metric_windows:
        if clicks_key in metrics or impressions_key in metrics:
            return (
                _number(metrics.get(clicks_key)) or 0.0,
                _number(metrics.get(impressions_key)) or 0.0,
                window,
            )
    return 0.0, 0.0, "missing"


def _bounded_score(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or value > 100:
        return None
    return float(value)


def _normalised_slug(value: Any) -> str:
    return str(value or "").strip().lower().strip("/")


def _normalised_values(values: Iterable[Any]) -> List[str]:
    return [str(value).strip().casefold() for value in values if str(value).strip()]


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _official_trends_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname in {
        "trends.google.com",
        "trends.googleapis.com",
    }


def _public_https_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.hostname)


def verify_live_sources(
    candidates: Sequence[Dict[str, Any]],
    *,
    timeout: float = 12.0,
    max_workers: int = 8,
) -> Dict[str, Any]:
    trend_requests: Dict[str, Set[str]] = {}
    primary_requests: Dict[str, Set[str]] = {}
    for candidate in candidates:
        for signal in candidate.get("demand_signals") or []:
            if not isinstance(signal, dict) or signal.get("positive") is not True:
                continue
            if str(signal.get("provider") or "").strip().casefold() not in REALTIME_TRENDS_PROVIDERS:
                continue
            metrics = signal.get("metrics") or {}
            query = _trend_topic_key(metrics.get("trend_query") or metrics.get("query"))
            urls = metrics.get("source_urls")
            if not isinstance(urls, list):
                url = metrics.get("source_url") or signal.get("evidence_ref")
                urls = [url] if url else []
            for raw_url in urls:
                url = str(raw_url or "").strip()
                if query and _official_trends_url(url):
                    trend_requests.setdefault(url, set()).add(query)
            primary_url = str(metrics.get("primary_source_url") or "").strip()
            terms = {
                str(value).strip().casefold()
                for value in metrics.get("primary_source_relevance_terms") or []
                if len(str(value).strip()) >= 3
            }
            if _public_https_url(primary_url) and terms:
                primary_requests.setdefault(primary_url, set()).update(terms)

    trend_verified: Set[str] = set()
    primary_verified: Dict[str, Dict[str, Any]] = {}
    receipts: List[Dict[str, Any]] = []

    def fetch(url: str) -> Tuple[str, int, str, bytes, Optional[str]]:
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        f"VERTU-Content-Traffic-Gate/{TRAFFIC_GATE_RUNTIME_VERSION}"
                    ),
                    "Range": "bytes=0-524287",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return (
                    url,
                    int(getattr(response, "status", 200)),
                    response.geturl(),
                    response.read(524_288),
                    None,
                )
        except Exception as error:
            return url, 0, url, b"", f"{type(error).__name__}: {error}"

    urls = sorted(set(trend_requests) | set(primary_requests))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        responses = list(executor.map(fetch, urls))

    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for url, status, final_url, body, error in responses:
        if url in trend_requests and status == 200:
            try:
                root = ET.fromstring(body)
                titles = {
                    _trend_topic_key(node.text)
                    for node in root.findall("./channel/item/title")
                    if _trend_topic_key(node.text)
                }
                for query in trend_requests[url].intersection(titles):
                    trend_verified.add(f"{query}|{url}")
            except ET.ParseError as parse_error:
                error = f"ParseError: {parse_error}"
        if url in primary_requests:
            text = (final_url + " " + body.decode("utf-8", errors="ignore")).casefold()
            matched_terms = sorted(
                term for term in primary_requests[url] if term in text
            )
            # The verifier deliberately requests a byte range. Standards-compliant
            # origin servers may therefore return 206 Partial Content, which is a
            # successful response for this exact request and must not invalidate an
            # otherwise relevant primary source.
            primary_verified[url] = {
                "verified": status in {200, 206} and bool(matched_terms),
                "http_status": status,
                "final_url": final_url,
                "matched_relevance_terms": matched_terms,
                "checked_at": checked_at,
                "error": error,
            }
        receipts.append(
            {
                "url": url,
                "http_status": status,
                "final_url": final_url,
                "checked_at": checked_at,
                "error": error,
            }
        )
    return {
        "trend_verified": trend_verified,
        "primary_verified": primary_verified,
        "receipts": receipts,
    }


def _iso_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _trend_topic_key(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _snapshot_fingerprint(snapshot: Dict[str, Any]) -> str:
    material = {
        key: value
        for key, value in snapshot.items()
        if key != "snapshot_fingerprint"
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _brand_mindset_fingerprint(payload: Dict[str, Any]) -> str:
    material = {
        key: value
        for key, value in payload.items()
        if key not in {"fingerprint", "snapshot_fingerprint"}
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _enforce_brand_mindset_gate(
    row: Dict[str, Any], errors: List[str], vetoes: List[str], required: bool
) -> bool:
    if not required:
        return False
    gate = row.get("brand_mindset_gate")
    if not isinstance(gate, dict):
        vetoes.append("brand_mindset_gate_invalid")
        return True
    fingerprint = str(gate.get("fingerprint") or "")
    valid = (
        gate.get("contract_version") == BRAND_MINDSET_GATE_CONTRACT_VERSION
        and len(fingerprint) == 64
        and fingerprint == _brand_mindset_fingerprint(gate)
        and gate.get("verdict") in {"PASS", "HOLD", "REJECT"}
        and gate.get("brand_mindset_class")
        in BRAND_MINDSET_CLASSES.union({"UNQUALIFIED"})
        and all(
            gate.get(key) is False
            for key in (
                "traffic_score_authority",
                "demand_authority",
                "trend_label_authority",
                "qa_authority",
                "publication_authority",
            )
        )
    )
    if not valid:
        vetoes.append("brand_mindset_gate_invalid")
        return True

    verdict = gate.get("verdict")
    classification = gate.get("brand_mindset_class")
    if verdict == "HOLD":
        vetoes.append("brand_mindset_evidence_incomplete")
    elif verdict == "REJECT":
        vetoes.append("brand_mindset_unqualified")
        for conflict in gate.get("brand_conflict_veto") or []:
            mapped = BRAND_CONFLICT_VETO_MAP.get(str(conflict).strip().upper())
            if mapped:
                vetoes.append(mapped)
    elif classification not in BRAND_MINDSET_CLASSES:
        vetoes.append("brand_mindset_gate_invalid")

    audience_fit_lane = str(row.get("audience_fit_lane") or "").strip().upper()
    if audience_fit_lane in {"EXPLORATION", "EXPLORATION_CANDIDATE"}:
        vetoes.append("automatic_exploration_disabled")
    return True


def _validated_learning_priors(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, dict):
        raise ValueError("learning-priors artifact must be an object")
    if payload.get("contract_version") != "performance-learning-v1":
        raise ValueError("learning-priors contract_version must be performance-learning-v1")
    expected_fingerprint = _snapshot_fingerprint(payload)
    if payload.get("snapshot_fingerprint") != expected_fingerprint:
        raise ValueError("learning-priors snapshot fingerprint mismatch")
    if payload.get("status") not in {"ACTIVE", "NO_DURABLE_LESSON"}:
        raise ValueError("learning-priors status must be ACTIVE or NO_DURABLE_LESSON")
    priors = payload.get("priors") or []
    if not isinstance(priors, list):
        raise ValueError("learning-priors priors must be a list")

    validated: List[Dict[str, Any]] = []
    for prior in priors:
        if not isinstance(prior, dict) or prior.get("state") != "ACTIVE":
            continue
        if prior.get("learning_level") != "DURABLE_PRIOR":
            raise ValueError("active learning prior must be DURABLE_PRIOR")
        scope_type = str(prior.get("scope_type") or "").strip()
        scope_value = str(prior.get("scope_value") or "").strip()
        adjustment = _number(prior.get("selection_adjustment"))
        evidence = prior.get("evidence") or {}
        if scope_type not in LEARNING_SCOPE_FIELDS or not scope_value:
            raise ValueError("active learning prior has invalid scope")
        if adjustment is None or abs(adjustment) > MAX_LEARNING_ADJUSTMENT:
            raise ValueError("learning prior adjustment must be within -3..3")
        enough_cohort = (
            int(evidence.get("d28_article_count") or 0) >= 3
            and int(evidence.get("publication_run_count") or 0) >= 2
        )
        verified_experiment = int(evidence.get("verified_experiment_count") or 0) >= 1
        if not (enough_cohort or verified_experiment):
            raise ValueError("active learning prior lacks durable evidence")
        validated.append(copy.deepcopy(prior))
    return validated


def _validated_provisional_learning_priors(
    payload: Any,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, dict):
        raise ValueError("provisional-learning-priors artifact must be an object")
    if payload.get("contract_version") != "performance-learning-provisional-v1":
        raise ValueError(
            "provisional-learning-priors contract_version must be "
            "performance-learning-provisional-v1"
        )
    expected_fingerprint = _snapshot_fingerprint(payload)
    if payload.get("snapshot_fingerprint") != expected_fingerprint:
        raise ValueError("provisional-learning-priors snapshot fingerprint mismatch")
    if payload.get("status") not in {"ACTIVE", "NO_PROVISIONAL_LESSON"}:
        raise ValueError(
            "provisional-learning-priors status must be ACTIVE or "
            "NO_PROVISIONAL_LESSON"
        )
    priors = payload.get("priors") or []
    if not isinstance(priors, list):
        raise ValueError("provisional-learning-priors priors must be a list")

    current_time = now or datetime.now(timezone.utc)
    validated: List[Dict[str, Any]] = []
    for prior in priors:
        if not isinstance(prior, dict) or prior.get("state") != "ACTIVE":
            continue
        if prior.get("learning_level") != "CANDIDATE_PRIOR":
            raise ValueError("active provisional prior must be CANDIDATE_PRIOR")
        scope_type = str(prior.get("scope_type") or "").strip()
        scope_value = str(prior.get("scope_value") or "").strip()
        adjustment = _number(prior.get("selection_adjustment"))
        activated_at = _iso_datetime(prior.get("activated_at"))
        expires_at = _iso_datetime(prior.get("expires_at"))
        evidence = prior.get("evidence") or {}
        source_checkpoint = str(evidence.get("source_checkpoint") or "").lower()
        article_count = int(evidence.get("article_count") or 0)
        publication_run_count = int(evidence.get("publication_run_count") or 0)
        if scope_type not in LEARNING_SCOPE_FIELDS or not scope_value:
            raise ValueError("active provisional prior has invalid scope")
        if adjustment is None or abs(adjustment) > 2:
            raise ValueError("provisional prior adjustment must be within -2..2")
        if activated_at is None or expires_at is None or expires_at <= activated_at:
            raise ValueError("active provisional prior has invalid activation window")
        if expires_at <= current_time:
            continue
        if source_checkpoint == "72h":
            enough_evidence = article_count >= 3 and publication_run_count >= 2
            if abs(adjustment) > 1:
                raise ValueError("72h provisional prior adjustment must be within -1..1")
        elif source_checkpoint == "7d":
            enough_evidence = article_count >= 2 and publication_run_count >= 2
        else:
            raise ValueError("provisional prior source checkpoint must be 72h or 7d")
        if not enough_evidence:
            raise ValueError("active provisional prior lacks repeated evidence")
        validated.append(copy.deepcopy(prior))
    return validated


def _validated_d2tr_market_context(
    payload: Any,
    now: Optional[datetime] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Validate optional independent Discover-market context.

    D2TR is not an official Google demand provider.  Invalid supplied
    artifacts fail closed; unavailable, blocked or stale artifacts simply
    produce no ordering adjustment.
    """

    if payload is None:
        return None, "NOT_PROVIDED"
    if not isinstance(payload, dict):
        raise ValueError("d2tr-market-context artifact must be an object")
    if payload.get("contract_version") != "d2tr-discover-context-v1":
        raise ValueError(
            "d2tr-market-context contract_version must be d2tr-discover-context-v1"
        )
    if payload.get("snapshot_fingerprint") != _snapshot_fingerprint(payload):
        raise ValueError("d2tr-market-context snapshot fingerprint mismatch")
    if payload.get("provider") != "d2tr_public_discover":
        raise ValueError("d2tr-market-context provider mismatch")
    if payload.get("official_google_source") is not False:
        raise ValueError("d2tr-market-context must not claim official Google provenance")
    if payload.get("may_create_google_demand") is not False:
        raise ValueError("d2tr-market-context may not create Google demand")
    if payload.get("may_create_realtime_hot") is not False:
        raise ValueError("d2tr-market-context may not create REALTIME_HOT")
    if payload.get("credentials_included") is not False:
        raise ValueError("d2tr-market-context must not include credentials")
    if not isinstance(payload.get("markets"), dict):
        raise ValueError("d2tr-market-context markets must be an object")
    source_fingerprint = str(payload.get("source_snapshot_fingerprint") or "")
    if not source_fingerprint:
        raise ValueError("d2tr-market-context source snapshot fingerprint is missing")
    status = str(payload.get("status") or "").upper()
    if status not in {"AVAILABLE", "PARTIAL", "SOURCE_BLOCKED"}:
        raise ValueError("d2tr-market-context status is invalid")
    if status == "SOURCE_BLOCKED":
        return None, "SOURCE_BLOCKED"
    observed_at = _iso_datetime(payload.get("observed_at"))
    current_time = now or datetime.now(timezone.utc)
    if observed_at is None or observed_at > current_time:
        raise ValueError("d2tr-market-context observed_at is invalid")
    if (current_time - observed_at).total_seconds() > D2TR_MAX_CONTEXT_AGE_HOURS * 3600:
        return None, "STALE"
    return copy.deepcopy(payload), status


def _normalised_signal_lookup(mapping: Any, expected: Any) -> Optional[Dict[str, Any]]:
    expected_key = _trend_topic_key(expected)
    if not expected_key or not isinstance(mapping, dict):
        return None
    for key, value in mapping.items():
        if _trend_topic_key(key) == expected_key and isinstance(value, dict):
            return value
    return None


def _fresh_d2tr_signal(signal: Any, now: datetime) -> Optional[Dict[str, Any]]:
    if not isinstance(signal, dict) or signal.get("status") != "AVAILABLE":
        return None
    generated_at = _iso_datetime(signal.get("source_generated_at"))
    if generated_at is None or generated_at > now:
        return None
    if (now - generated_at).total_seconds() > D2TR_MAX_CONTEXT_AGE_HOURS * 3600:
        return None
    return signal


def _d2tr_signal_strength(signal: Dict[str, Any], dimension: str) -> str:
    current = _number(signal.get("current_value"))
    change = _number(signal.get("change_value"))
    trend = str(signal.get("trend") or "").upper()
    state = str(signal.get("state") or "").upper()
    if dimension in {"topic_category", "format_group"}:
        if (current is not None and current >= 7) or state == "SUSTAINED":
            return "STRONG"
        if trend == "RISING" and current is not None and current >= 5:
            return "STRONG"
        if (current is not None and current >= 5) or trend == "RISING" or state == "ACTIVE":
            return "MODERATE"
    elif dimension == "format_type":
        if trend == "RISING" and change is not None and change >= 1:
            return "STRONG"
        if trend == "RISING" or (change is not None and change >= 0.5):
            return "MODERATE"
    elif dimension == "content_category":
        if change is not None and change >= 15:
            return "STRONG"
        if change is not None and change >= 5:
            return "MODERATE"
    return "NONE"


def _d2tr_context_adjustment(
    candidate: Dict[str, Any],
    context: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    result = {
        "raw_adjustment": 0.0,
        "market": None,
        "matched_dimensions": [],
        "strong_match_count": 0,
        "moderate_match_count": 0,
        "market_anomaly": False,
        "reason": "NO_CONTEXT",
    }
    if context is None:
        return result
    declaration = candidate.get("d2tr_context")
    if not isinstance(declaration, dict):
        result["reason"] = "CANDIDATE_CONTEXT_NOT_DECLARED"
        return result
    market = str(declaration.get("market") or "").strip().upper()
    result["market"] = market or None
    market_payload = (context.get("markets") or {}).get(market)
    if not market or not isinstance(market_payload, dict):
        result["reason"] = "MARKET_UNAVAILABLE"
        return result
    current_time = now or datetime.now(timezone.utc)
    volatility = _fresh_d2tr_signal(market_payload.get("volatility"), current_time)
    if volatility is not None:
        volatility_index = _number(volatility.get("current_value"))
        result["market_anomaly"] = bool(
            (volatility_index is not None and volatility_index >= 7)
            or str(volatility.get("state") or "").upper() == "SUSTAINED"
        )
    dimension_maps = {
        "topic_category": "topics",
        "format_group": "format_groups",
        "format_type": "formats",
        "content_category": "categories",
    }
    matches = []
    for dimension, market_field in dimension_maps.items():
        expected = declaration.get(dimension)
        signal = _normalised_signal_lookup(market_payload.get(market_field), expected)
        signal = _fresh_d2tr_signal(signal, current_time)
        if signal is None:
            continue
        strength = _d2tr_signal_strength(signal, dimension)
        if strength == "NONE":
            continue
        matches.append(
            {
                "dimension": dimension,
                "value": expected,
                "strength": strength,
                "current_value": signal.get("current_value"),
                "change_value": signal.get("change_value"),
                "trend": signal.get("trend"),
                "state": signal.get("state"),
                "source_generated_at": signal.get("source_generated_at"),
            }
        )
    strong_count = sum(row["strength"] == "STRONG" for row in matches)
    moderate_count = sum(row["strength"] == "MODERATE" for row in matches)
    if strong_count >= 2 or (result["market_anomaly"] and len(matches) >= 2):
        adjustment = 2.0
        reason = "MULTI_DIMENSION_BREAKOUT"
    elif strong_count >= 1 or moderate_count >= 2:
        adjustment = 1.0
        reason = "SUPPORTED_MARKET_CONTEXT"
    else:
        adjustment = 0.0
        reason = "NO_ACTIONABLE_MATCH"
    result.update(
        {
            "raw_adjustment": adjustment,
            "matched_dimensions": matches,
            "strong_match_count": strong_count,
            "moderate_match_count": moderate_count,
            "reason": reason,
        }
    )
    return result


def _apply_learning_priority(
    candidate: Dict[str, Any],
    priors: Sequence[Dict[str, Any]],
    d2tr_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row = copy.deepcopy(candidate)
    if not row.get("eligible"):
        row["durable_learning_adjustment"] = 0.0
        row["provisional_learning_adjustment"] = 0.0
        row["learning_adjustment"] = 0.0
        row["d2tr_market_context_adjustment_raw"] = 0.0
        row["d2tr_market_context_adjustment_applied"] = 0.0
        row["total_priority_adjustment"] = 0.0
        row["d2tr_market_context_evidence"] = {
            "reason": "INELIGIBLE_CANDIDATE",
            "matched_dimensions": [],
        }
        row["selection_priority_score"] = round(float(row.get("score") or 0), 2)
        row["matched_learning_priors"] = []
        row["matched_durable_priors"] = []
        row["matched_provisional_priors"] = []
        row["learning_can_change_eligibility"] = False
        return row
    matched: List[str] = []
    matched_durable: List[str] = []
    matched_provisional: List[str] = []
    durable_adjustment = 0.0
    provisional_adjustment = 0.0
    for prior in priors:
        scope_type = str(prior.get("scope_type") or "").strip()
        expected = str(prior.get("scope_value") or "").strip().casefold()
        observed = str(row.get(scope_type) or "").strip().casefold()
        if expected and observed == expected:
            prior_adjustment = float(prior.get("selection_adjustment") or 0)
            prior_id = str(prior.get("prior_id") or "")
            matched.append(prior_id)
            if prior.get("learning_level") == "DURABLE_PRIOR":
                durable_adjustment += prior_adjustment
                matched_durable.append(prior_id)
            elif prior.get("learning_level") == "CANDIDATE_PRIOR":
                provisional_adjustment += prior_adjustment
                matched_provisional.append(prior_id)
    durable_adjustment = max(
        -MAX_LEARNING_ADJUSTMENT,
        min(MAX_LEARNING_ADJUSTMENT, durable_adjustment),
    )
    provisional_adjustment = max(-2.0, min(2.0, provisional_adjustment))
    adjustment = durable_adjustment + provisional_adjustment
    adjustment = max(-MAX_LEARNING_ADJUSTMENT, min(MAX_LEARNING_ADJUSTMENT, adjustment))
    d2tr_evidence = _d2tr_context_adjustment(row, d2tr_context)
    d2tr_raw = max(
        0.0,
        min(D2TR_MAX_ADJUSTMENT, float(d2tr_evidence.get("raw_adjustment") or 0)),
    )
    total_adjustment = max(
        -MAX_LEARNING_ADJUSTMENT,
        min(MAX_LEARNING_ADJUSTMENT, adjustment + d2tr_raw),
    )
    d2tr_applied = total_adjustment - adjustment
    row["durable_learning_adjustment"] = round(durable_adjustment, 2)
    row["provisional_learning_adjustment"] = round(provisional_adjustment, 2)
    row["learning_adjustment"] = round(adjustment, 2)
    row["d2tr_market_context_adjustment_raw"] = round(d2tr_raw, 2)
    row["d2tr_market_context_adjustment_applied"] = round(d2tr_applied, 2)
    row["total_priority_adjustment"] = round(total_adjustment, 2)
    row["d2tr_market_context_evidence"] = d2tr_evidence
    row["selection_priority_score"] = round(
        float(row.get("score") or 0) + total_adjustment, 2
    )
    row["matched_learning_priors"] = sorted(value for value in matched if value)
    row["matched_durable_priors"] = sorted(
        value for value in matched_durable if value
    )
    row["matched_provisional_priors"] = sorted(
        value for value in matched_provisional if value
    )
    row["learning_can_change_eligibility"] = False
    return row


def _realtime_topic_registry(snapshot: Any) -> Dict[str, List[Dict[str, Any]]]:
    registry: Dict[str, List[Dict[str, Any]]] = {}
    run_id = str(snapshot.get("run_id") or "").strip() if isinstance(snapshot, dict) else ""
    fingerprint = (
        str(snapshot.get("snapshot_fingerprint") or "").strip()
        if isinstance(snapshot, dict)
        else ""
    )
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("contract_version") != "realtime-trends-v1"
        or not run_id
        or not fingerprint
        or fingerprint != _snapshot_fingerprint(snapshot)
        or snapshot.get("provider") not in REALTIME_TRENDS_PROVIDERS
        or snapshot.get("source_method") not in REALTIME_SOURCE_METHODS
        or snapshot.get("official_google_source") is not True
        or snapshot.get("credentials_included") is not False
        or snapshot.get("status") not in {"AVAILABLE", "PARTIAL"}
    ):
        return registry
    now = datetime.now(timezone.utc)
    for topic in snapshot.get("topics") or []:
        if not isinstance(topic, dict) or topic.get("realtime_candidate") is not True:
            continue
        published_at = _iso_datetime(topic.get("newest_published_at"))
        if (
            published_at is None
            or published_at > now
            or (now - published_at).total_seconds() > 24 * 3600
            or (_number(topic.get("max_approx_traffic")) or 0) <= 0
            or (_number(topic.get("news_confirmation_count")) or 0) < 1
        ):
            continue
        key = _trend_topic_key(topic.get("query"))
        if key:
            trusted_topic = copy.deepcopy(topic)
            trusted_topic["_snapshot_run_id"] = run_id
            trusted_topic["_snapshot_fingerprint"] = fingerprint
            trusted_topic["_snapshot_source_method"] = snapshot.get("source_method")
            registry.setdefault(key, []).append(trusted_topic)
    return registry


def _verified_realtime_signal(
    signal: Dict[str, Any],
    realtime_topics: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    candidate_run_id: str = "",
    live_trend_verifications: Optional[Set[str]] = None,
    live_primary_verifications: Optional[Dict[str, Dict[str, Any]]] = None,
) -> bool:
    if signal.get("provider") not in REALTIME_TRENDS_PROVIDERS:
        return False
    metrics = signal.get("metrics") or {}
    markets = metrics.get("markets")
    if not isinstance(markets, list):
        market = str(metrics.get("market") or metrics.get("geo") or "").strip()
        markets = [market] if market else []
    age_hours = _number(metrics.get("age_hours"))
    approx_traffic = _number(metrics.get("approx_traffic"))
    news_count = _number(metrics.get("news_confirmation_count"))
    source_method = str(metrics.get("source_method") or "").strip().casefold()
    official = metrics.get("official_google_source") is True
    normalised_markets = set(_normalised_values(markets))
    source_url = metrics.get("source_url") or signal.get("evidence_ref")
    source_urls = metrics.get("source_urls")
    if not isinstance(source_urls, list):
        source_urls = [source_url] if source_url else []
    normalised_source_urls = {
        str(value).strip() for value in source_urls if str(value or "").strip()
    }
    trend_query = _trend_topic_key(metrics.get("trend_query") or metrics.get("query"))
    primary_source_url = metrics.get("primary_source_url")
    primary_source_observed_at = _iso_datetime(metrics.get("primary_source_observed_at"))
    primary_source_published_at = _iso_datetime(metrics.get("primary_source_published_at"))
    primary_source_status = _number(metrics.get("primary_source_http_status"))
    primary_source_relation = str(metrics.get("primary_source_relation") or "").strip().casefold()
    primary_source_relevance_terms = metrics.get("primary_source_relevance_terms")
    signal_observed_at = _iso_datetime(signal.get("observed_at"))
    now = datetime.now(timezone.utc)
    observed_in_window = (
        signal_observed_at is not None
        and now - timedelta(hours=24) <= signal_observed_at <= now + timedelta(minutes=5)
    )
    primary_source_observed_in_window = (
        primary_source_observed_at is not None
        and now - timedelta(hours=24)
        <= primary_source_observed_at
        <= now + timedelta(minutes=5)
    )
    primary_source_published_in_window = (
        primary_source_published_at is not None
        and now - timedelta(hours=72)
        <= primary_source_published_at
        <= now + timedelta(minutes=5)
    )
    base_verified = (
        bool(normalised_markets)
        and bool(trend_query)
        and age_hours is not None
        and 0 <= age_hours <= 24
        and approx_traffic is not None
        and approx_traffic > 0
        and news_count is not None
        and news_count >= 1
        and official
        and source_method in REALTIME_SOURCE_METHODS
        and bool(normalised_source_urls)
        and all(_official_trends_url(value) for value in normalised_source_urls)
        and live_trend_verifications is not None
        and all(
            f"{trend_query}|{value}" in live_trend_verifications
            for value in normalised_source_urls
        )
        and _public_https_url(primary_source_url)
        and live_primary_verifications is not None
        and bool(
            (live_primary_verifications.get(str(primary_source_url)) or {}).get(
                "verified"
            )
        )
        and observed_in_window
        and primary_source_observed_in_window
        and primary_source_published_in_window
        and primary_source_status in {200, 206}
        and primary_source_relation in PRIMARY_SOURCE_RELATIONS
        and isinstance(primary_source_relevance_terms, list)
        and any(str(value).strip() for value in primary_source_relevance_terms)
    )
    if not base_verified or not realtime_topics:
        return False

    matching_topics = realtime_topics.get(trend_query) or []
    candidate_run_id = str(candidate_run_id or "").strip()
    candidate_fingerprint = str(metrics.get("snapshot_fingerprint") or "").strip()
    for topic in matching_topics:
        topic_markets = set(_normalised_values(topic.get("markets") or []))
        evidence = topic.get("evidence") or []
        evidence_by_market = {
            str(row.get("geo") or "").strip().casefold(): row
            for row in evidence
            if isinstance(row, dict)
        }
        snapshot_age = _number(topic.get("minimum_age_hours"))
        snapshot_traffic = _number(topic.get("max_approx_traffic"))
        snapshot_news = _number(topic.get("news_confirmation_count"))
        if (
            not normalised_markets.issubset(topic_markets)
            or candidate_run_id != topic.get("_snapshot_run_id")
            or candidate_fingerprint != topic.get("_snapshot_fingerprint")
            or source_method != topic.get("_snapshot_source_method")
            or snapshot_age is None
            or abs(age_hours - snapshot_age) > 0.25
            or approx_traffic != snapshot_traffic
            or news_count != snapshot_news
        ):
            continue
        expected_source_urls = {
            str(evidence_by_market[market].get("source_url") or "").strip()
            for market in normalised_markets
            if market in evidence_by_market
        }
        if (
            len(expected_source_urls) == len(normalised_markets)
            and normalised_source_urls == expected_source_urls
        ):
            return True
    return False


def _verified_rising_signal(signal: Dict[str, Any]) -> bool:
    metrics = signal.get("metrics") or {}
    growth_pct = _number(metrics.get("growth_pct"))
    if growth_pct is not None and growth_pct > 0:
        return True
    pairs = (
        ("current_period_value", "previous_period_value"),
        ("recent_month_searches", "average_monthly_searches"),
        ("current_interest", "baseline_interest"),
    )
    for current_key, baseline_key in pairs:
        current = _number(metrics.get(current_key))
        baseline = _number(metrics.get(baseline_key))
        if current is not None and baseline is not None and current > baseline:
            return True
    return False


def _validate_evidence_block(
    key: str, block: Any, errors: List[str]
) -> Optional[float]:
    if not isinstance(block, dict):
        errors.append(f"missing_dimension_evidence:{key}")
        return None
    score = _bounded_score(block.get("score_100"))
    refs = block.get("evidence_refs")
    observed_at = block.get("observed_at")
    if score is None:
        errors.append(f"invalid_dimension_score:{key}")
    if not isinstance(refs, list) or not any(str(ref).strip() for ref in refs):
        errors.append(f"missing_dimension_evidence:{key}")
    if not str(observed_at or "").strip():
        errors.append(f"missing_dimension_observed_at:{key}")
    return score


def _normalise_direct_factor(raw_value: float, spec: Dict[str, Any]) -> float:
    minimum = float(spec["minimum"])
    maximum = float(spec["maximum"])
    if maximum <= minimum:
        raise ValueError("direct factor maximum must be greater than minimum")
    transform = str(spec.get("transform") or "").strip()
    bounded = max(minimum, min(maximum, raw_value))
    if transform == "linear":
        ratio = (bounded - minimum) / (maximum - minimum)
    elif transform == "inverse_linear":
        ratio = 1.0 - ((bounded - minimum) / (maximum - minimum))
    elif transform == "log":
        if minimum <= 0 or maximum <= 0:
            raise ValueError("log direct factor bounds must be positive")
        ratio = (math.log(bounded) - math.log(minimum)) / (
            math.log(maximum) - math.log(minimum)
        )
    else:
        raise ValueError(f"unsupported direct factor transform:{transform}")
    return round(max(0.0, min(1.0, ratio)) * 100.0, 2)


def _evaluate_direct_factor_model(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate a provenance-bound shadow score without changing production gates."""

    evidence = candidate.get("direct_factor_evidence")
    if evidence is None:
        return {
            "contract_version": DIRECT_FACTOR_MODEL_CONTRACT_VERSION,
            "score_source": DIRECT_FACTOR_SCORE_SOURCE,
            "mode": "SHADOW",
            "status": "NOT_PROVIDED",
            "factor_count_total": len(DIRECT_FACTOR_REGISTRY),
            "factor_count_available": 0,
            "factor_count_unavailable": 0,
            "factor_count_not_applicable": 0,
            "factor_count_insufficient_sample": 0,
            "factor_count_missing": len(DIRECT_FACTOR_REGISTRY),
            "factor_count_invalid": 0,
            "applicable_weight_total": 100.0,
            "coverage_weight_pct": 0.0,
            "observed_weighted_score": 0.0,
            "coverage_normalized_score": None,
            "diagnostic_usable": False,
            "minimum_diagnostic_coverage_pct": DIRECT_FACTOR_MIN_DIAGNOSTIC_COVERAGE,
            "can_change_production_decision": False,
            "validation_errors": [],
            "factors": {},
        }
    if not isinstance(evidence, dict):
        return {
            "contract_version": DIRECT_FACTOR_MODEL_CONTRACT_VERSION,
            "score_source": DIRECT_FACTOR_SCORE_SOURCE,
            "mode": "SHADOW",
            "status": "INVALID",
            "factor_count_total": len(DIRECT_FACTOR_REGISTRY),
            "factor_count_available": 0,
            "factor_count_unavailable": 0,
            "factor_count_not_applicable": 0,
            "factor_count_insufficient_sample": 0,
            "factor_count_missing": len(DIRECT_FACTOR_REGISTRY),
            "factor_count_invalid": 1,
            "applicable_weight_total": 100.0,
            "coverage_weight_pct": 0.0,
            "observed_weighted_score": 0.0,
            "coverage_normalized_score": None,
            "diagnostic_usable": False,
            "minimum_diagnostic_coverage_pct": DIRECT_FACTOR_MIN_DIAGNOSTIC_COVERAGE,
            "can_change_production_decision": False,
            "validation_errors": ["direct_factor_evidence_must_be_object"],
            "factors": {},
        }

    errors: List[str] = []
    factors: Dict[str, Dict[str, Any]] = {}
    available_count = 0
    unavailable_count = 0
    not_applicable_count = 0
    insufficient_sample_count = 0
    missing_count = 0
    invalid_count = 0
    applicable_weight = sum(
        float(spec["weight"]) for spec in DIRECT_FACTOR_REGISTRY.values()
    )
    available_weight = 0.0
    observed_weighted_score = 0.0

    unknown_keys = sorted(set(evidence) - set(DIRECT_FACTOR_REGISTRY))
    errors.extend(f"unknown_direct_factor:{key}" for key in unknown_keys)

    for key, spec in DIRECT_FACTOR_REGISTRY.items():
        weight = float(spec["weight"])
        block = evidence.get(key)
        factor_row: Dict[str, Any] = {
            "weight": weight,
            "transform": spec["transform"],
            "minimum": spec["minimum"],
            "maximum": spec["maximum"],
        }
        if block is None:
            missing_count += 1
            factor_row["status"] = "MISSING"
            factors[key] = factor_row
            continue
        if not isinstance(block, dict):
            invalid_count += 1
            error = f"invalid_direct_factor_block:{key}"
            errors.append(error)
            factor_row.update({"status": "INVALID", "errors": [error]})
            factors[key] = factor_row
            continue

        status = str(block.get("status") or "").strip().upper()
        observed_at = str(block.get("observed_at") or "").strip()
        if status in {SOURCE_UNAVAILABLE, NOT_APPLICABLE, INSUFFICIENT_SAMPLE}:
            factor_errors = []
            reason = str(block.get("reason") or "").strip()
            if not reason:
                factor_errors.append(f"missing_direct_factor_status_reason:{key}")
            if not observed_at:
                factor_errors.append(f"missing_direct_factor_observed_at:{key}")
            if factor_errors:
                invalid_count += 1
                errors.extend(factor_errors)
                factor_row.update({"status": "INVALID", "errors": factor_errors})
            elif status == SOURCE_UNAVAILABLE:
                unavailable_count += 1
                factor_row.update(
                    {
                        "status": SOURCE_UNAVAILABLE,
                        "reason": reason,
                        "observed_at": observed_at,
                    }
                )
            elif status == NOT_APPLICABLE:
                not_applicable_count += 1
                applicable_weight -= weight
                factor_row.update(
                    {
                        "status": NOT_APPLICABLE,
                        "reason": reason,
                        "observed_at": observed_at,
                    }
                )
            else:
                insufficient_sample_count += 1
                factor_row.update(
                    {
                        "status": INSUFFICIENT_SAMPLE,
                        "reason": reason,
                        "observed_at": observed_at,
                    }
                )
                raw_value = _number(block.get("raw_value"))
                if raw_value is not None:
                    factor_row["raw_value"] = raw_value
                refs = block.get("evidence_refs")
                if isinstance(refs, list) and any(str(ref).strip() for ref in refs):
                    factor_row["evidence_refs"] = copy.deepcopy(refs)
            factors[key] = factor_row
            continue

        factor_errors: List[str] = []
        if status != AVAILABLE:
            factor_errors.append(f"invalid_direct_factor_status:{key}")
        if "score_100" in block:
            factor_errors.append(f"hand_authored_factor_score:{key}")
        raw_value = _number(block.get("raw_value"))
        if raw_value is None:
            factor_errors.append(f"invalid_direct_factor_raw_value:{key}")
        refs = block.get("evidence_refs")
        if not isinstance(refs, list) or not any(str(ref).strip() for ref in refs):
            factor_errors.append(f"missing_direct_factor_evidence:{key}")
        if not observed_at:
            factor_errors.append(f"missing_direct_factor_observed_at:{key}")
        if factor_errors:
            invalid_count += 1
            errors.extend(factor_errors)
            factor_row.update({"status": "INVALID", "errors": factor_errors})
            factors[key] = factor_row
            continue

        assert raw_value is not None
        normalised_score = _normalise_direct_factor(raw_value, spec)
        weighted_score = round(normalised_score * weight / 100.0, 4)
        available_count += 1
        available_weight += weight
        observed_weighted_score += weighted_score
        factor_row.update(
            {
                "status": AVAILABLE,
                "raw_value": raw_value,
                "score_100": normalised_score,
                "weighted_score": weighted_score,
                "observed_at": observed_at,
                "evidence_refs": copy.deepcopy(refs),
            }
        )
        factors[key] = factor_row

    coverage = (
        round(available_weight * 100.0 / applicable_weight, 2)
        if applicable_weight > 0
        else 0.0
    )
    observed_score = round(observed_weighted_score, 2)
    normalised_score = (
        round(observed_weighted_score * 100.0 / available_weight, 2)
        if available_weight > 0
        else None
    )
    diagnostic_usable = (
        invalid_count == 0 and coverage >= DIRECT_FACTOR_MIN_DIAGNOSTIC_COVERAGE
    )
    if invalid_count:
        status = "INVALID"
    elif coverage >= 100.0:
        status = "VALID_COMPLETE"
    elif diagnostic_usable:
        status = "VALID_PARTIAL"
    else:
        status = "INSUFFICIENT_FACTOR_COVERAGE"
    return {
        "contract_version": DIRECT_FACTOR_MODEL_CONTRACT_VERSION,
        "score_source": DIRECT_FACTOR_SCORE_SOURCE,
        "mode": "SHADOW",
        "status": status,
        "factor_count_total": len(DIRECT_FACTOR_REGISTRY),
        "factor_count_available": available_count,
        "factor_count_unavailable": unavailable_count,
        "factor_count_not_applicable": not_applicable_count,
        "factor_count_insufficient_sample": insufficient_sample_count,
        "factor_count_missing": missing_count,
        "factor_count_invalid": invalid_count,
        "applicable_weight_total": round(applicable_weight, 2),
        "available_weight_total": round(available_weight, 2),
        "coverage_weight_pct": coverage,
        "observed_weighted_score": observed_score,
        "coverage_normalized_score": normalised_score,
        "diagnostic_usable": diagnostic_usable,
        "minimum_diagnostic_coverage_pct": DIRECT_FACTOR_MIN_DIAGNOSTIC_COVERAGE,
        "can_change_production_decision": False,
        "validation_errors": sorted(set(errors)),
        "factors": factors,
    }


def _hybrid_factor_component(
    direct_factor_model: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate the factor evidence used by the opt-in hybrid score."""

    blockers: List[str] = []
    factors = direct_factor_model.get("factors")
    if not isinstance(factors, dict):
        factors = {}
    coverage = _number(direct_factor_model.get("coverage_weight_pct")) or 0.0
    normalised_score = _number(
        direct_factor_model.get("coverage_normalized_score")
    )
    invalid_count = int(direct_factor_model.get("factor_count_invalid") or 0)

    if invalid_count > 0:
        blockers.append("invalid_direct_factor_evidence")
    if coverage < HYBRID_MIN_FACTOR_COVERAGE:
        blockers.append("insufficient_direct_factor_coverage")
    for factor_key in HYBRID_CORE_FACTORS:
        if str((factors.get(factor_key) or {}).get("status") or "") != AVAILABLE:
            blockers.append(f"missing_core_direct_factor:{factor_key}")
    if not any(
        str((factors.get(factor_key) or {}).get("status") or "") == AVAILABLE
        for factor_key in HYBRID_DEMAND_MAGNITUDE_FACTORS
    ):
        blockers.append("missing_direct_demand_magnitude_factor")
    if normalised_score is None:
        blockers.append("missing_direct_factor_normalized_score")

    missing_applicable_pct = round(max(0.0, 100.0 - coverage), 2)
    coverage_penalty = round(
        min(
            HYBRID_MAX_COVERAGE_PENALTY,
            missing_applicable_pct * HYBRID_COVERAGE_PENALTY_PER_POINT,
        ),
        2,
    )
    effective_factor_score = (
        round(max(0.0, normalised_score - coverage_penalty), 2)
        if normalised_score is not None
        else None
    )
    blockers = sorted(set(blockers))
    return {
        "status": "READY" if not blockers else "BLOCKED",
        "ready": not blockers,
        "minimum_coverage_pct": HYBRID_MIN_FACTOR_COVERAGE,
        "coverage_weight_pct": round(coverage, 2),
        "missing_applicable_pct": missing_applicable_pct,
        "coverage_penalty": coverage_penalty,
        "coverage_normalized_score": normalised_score,
        "effective_factor_score": effective_factor_score,
        "core_factors_required": list(HYBRID_CORE_FACTORS),
        "demand_magnitude_factors": list(HYBRID_DEMAND_MAGNITUDE_FACTORS),
        "blockers": blockers,
    }


def _signal_statuses(
    signals: Any, errors: List[str]
) -> Tuple[
    Dict[str, Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    if not isinstance(signals, list):
        errors.append("missing_demand_signals")
        return {}, [], []

    statuses: Dict[str, Dict[str, Any]] = {}
    positive: List[Dict[str, Any]] = []
    qualifications: List[Dict[str, Any]] = []
    for index, raw_signal in enumerate(signals):
        if not isinstance(raw_signal, dict):
            errors.append(f"invalid_demand_signal:{index}")
            continue
        signal = copy.deepcopy(raw_signal)
        provider = str(signal.get("provider") or "").strip().casefold()
        status = str(signal.get("status") or "").strip().upper()
        if not provider:
            errors.append(f"missing_demand_provider:{index}")
            continue
        if status not in {AVAILABLE, SOURCE_UNAVAILABLE}:
            errors.append(f"invalid_demand_status:{provider}")
            continue
        if not str(signal.get("observed_at") or "").strip():
            errors.append(f"missing_demand_observed_at:{provider}")

        provider_family, demand_role = _provider_family(provider, signal)

        if status == SOURCE_UNAVAILABLE:
            unavailable = {
                "status": SOURCE_UNAVAILABLE,
                "reason": str(signal.get("reason") or "").strip(),
                "observed_at": signal.get("observed_at"),
                "provider_family": provider_family,
                "demand_role": demand_role,
                "qualification_status": SOURCE_UNAVAILABLE,
                "qualification_reason": str(signal.get("reason") or "").strip(),
                "counts_for_search_demand": False,
            }
            if not unavailable["reason"]:
                errors.append(f"missing_unavailable_reason:{provider}")
            statuses[provider] = unavailable
            qualifications.append(
                {
                    "signal_index": index,
                    "provider": provider,
                    **copy.deepcopy(unavailable),
                }
            )
            continue

        score = _bounded_score(signal.get("score_100"))
        evidence_ref = str(signal.get("evidence_ref") or "").strip()
        metrics = copy.deepcopy(signal.get("metrics") or {})
        if score is None:
            errors.append(f"invalid_demand_score:{provider}")
        if not evidence_ref:
            errors.append(f"missing_demand_evidence:{provider}")
        raw_positive = bool(signal.get("positive"))
        qualification_status = "NOT_POSITIVE"
        qualification_reason = "upstream_positive_false"
        qualification_metrics: Dict[str, Any] = {}
        effectively_positive = False
        if raw_positive:
            if score is None or not evidence_ref:
                qualification_status = "INVALID_EVIDENCE"
                qualification_reason = "positive_signal_requires_score_and_evidence"
            elif provider_family == "gsc":
                clicks, impressions, metric_window = _gsc_sample_metrics(metrics)
                qualification_metrics = {
                    "clicks": clicks,
                    "impressions": impressions,
                    "metric_window": metric_window,
                }
                if clicks < GSC_MIN_CLICKS and impressions < GSC_MIN_IMPRESSIONS:
                    qualification_status = "INSUFFICIENT_SAMPLE"
                    qualification_reason = (
                        "gsc_requires_clicks_gte_3_or_impressions_gte_100"
                    )
                else:
                    qualification_status = "QUALIFIED"
                    qualification_reason = "gsc_sample_floor_passed"
                    effectively_positive = True
            elif demand_role == "acquisition":
                qualification_status = "QUALIFIED"
                qualification_reason = "positive_acquisition_evidence"
                effectively_positive = True
            else:
                qualification_status = "QUALIFIED_SUPPORTING"
                qualification_reason = (
                    "supporting_signal_not_independent_search_demand"
                )
                effectively_positive = True

        counts_for_search_demand = (
            effectively_positive
            and demand_role == "acquisition"
            and provider_family in SEARCH_DEMAND_PROVIDER_FAMILIES
        )
        available = {
            "status": AVAILABLE,
            "positive": raw_positive,
            "score_100": score,
            "evidence_ref": evidence_ref,
            "observed_at": signal.get("observed_at"),
            "metrics": metrics,
            "provider_family": provider_family,
            "demand_role": demand_role,
            "qualification_status": qualification_status,
            "qualification_reason": qualification_reason,
            "qualification_metrics": qualification_metrics,
            "effectively_positive": effectively_positive,
            "counts_for_search_demand": counts_for_search_demand,
        }
        statuses[provider] = available
        qualification = {
            "signal_index": index,
            "provider": provider,
            **copy.deepcopy(available),
        }
        qualifications.append(qualification)
        if effectively_positive:
            positive.append(qualification)
    return statuses, positive, qualifications


def _market_demand_by_provider_family(
    positive_signals: Sequence[Dict[str, Any]],
    qualifications: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Select one strongest qualified score for each independent family."""

    independent_families = {
        str(signal.get("provider_family") or "")
        for signal in positive_signals
        if signal.get("counts_for_search_demand") is True
    }
    family_scores: Dict[str, Dict[str, Any]] = {}
    for family in sorted(independent_families):
        family_signals = [
            signal
            for signal in positive_signals
            if signal.get("provider_family") == family
        ]
        if not family_signals:
            continue
        strongest = sorted(
            family_signals,
            key=lambda signal: (
                -float(signal.get("score_100") or 0.0),
                str(signal.get("provider") or ""),
                int(signal.get("signal_index") or 0),
            ),
        )[0]
        family_scores[family] = {
            "score_100": float(strongest["score_100"]),
            "selected_provider": strongest["provider"],
            "selected_signal_index": strongest["signal_index"],
            "qualified_providers": sorted(
                {
                    str(signal.get("provider") or "")
                    for signal in family_signals
                    if str(signal.get("provider") or "")
                }
            ),
        }

    selected = {
        (family, row["selected_signal_index"])
        for family, row in family_scores.items()
    }
    for qualification in qualifications:
        qualification["selected_for_market_demand"] = (
            qualification.get("provider_family"),
            qualification.get("signal_index"),
        ) in selected
    return family_scores


def _validate_cluster_support(candidate: Dict[str, Any], errors: List[str]) -> None:
    support = candidate.get("cluster_support")
    if not isinstance(support, dict):
        errors.append("missing_cluster_support")
        return
    for key in ("cluster_role", "query_boundary"):
        if not str(support.get(key) or "").strip():
            errors.append(f"missing_cluster_support:{key}")
    outbound = support.get("outbound_destinations")
    inbound = support.get("inbound_candidates")
    if not isinstance(outbound, list) or not outbound:
        errors.append("missing_cluster_support:outbound_destinations")
    if not isinstance(inbound, list):
        errors.append("missing_cluster_support:inbound_candidates")


def _strong_community_signal(rows: Any) -> bool:
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "").strip().casefold()
        points = _number(row.get("points") or row.get("net_votes")) or 0
        comments = _number(row.get("comments")) or 0
        if provider == "hacker_news" and (points >= 300 or comments >= 150):
            return True
        if provider == "reddit" and points >= 500 and comments > 0:
            return True
        if provider in {"techmeme", "multi_publisher_cluster"} and (
            _number(row.get("publisher_count")) or 0
        ) >= 2:
            return True
    return False


def _validate_editorial_signal(
    candidate: Dict[str, Any],
    errors: List[str],
    vetoes: List[str],
    source_velocity: Optional[Dict[str, Dict[str, Any]]] = None,
) -> bool:
    signal = str(candidate.get("editorial_signal") or "").strip().upper()
    if signal not in EDITORIAL_SIGNALS:
        errors.append("invalid_or_missing_editorial_signal")
        return False
    if signal != "EDITORIAL_BREAKOUT":
        return False

    candidate_id = str(candidate.get("candidate_id") or "").strip()
    row = (source_velocity or {}).get(candidate_id)
    if not isinstance(row, dict):
        vetoes.append("unverified_editorial_breakout")
        return False
    primary = row.get("primary_source") or {}
    coverage = row.get("independent_coverage") or []
    community = row.get("community_signals") or []
    coverage_count = sum(
        isinstance(item, dict)
        and item.get("status", AVAILABLE) == AVAILABLE
        and _public_https_url(item.get("url"))
        for item in coverage
    )
    verified = (
        row.get("verdict") == "PASS"
        and row.get("editorial_signal") == "EDITORIAL_BREAKOUT"
        and _public_https_url(primary.get("url"))
        and primary.get("status") == AVAILABLE
        and bool(str(primary.get("verified_at") or "").strip())
        and (coverage_count >= 2 or (coverage_count >= 1 and _strong_community_signal(community)))
        and bool(str(row.get("broad_reader_consequence") or "").strip())
        and bool(str(row.get("visual_subject") or "").strip())
        and str(row.get("inventory_overlap") or "").strip().casefold()
        not in {"duplicate", "same_intent_satisfied"}
    )
    if not verified:
        vetoes.append("unverified_editorial_breakout")
    return verified


def evaluate_candidate(
    candidate: Dict[str, Any],
    realtime_topics: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    live_trend_verifications: Optional[Set[str]] = None,
    live_primary_verifications: Optional[Dict[str, Dict[str, Any]]] = None,
    source_velocity: Optional[Dict[str, Dict[str, Any]]] = None,
    factor_score_mode: str = "legacy",
    require_brand_mindset_gate: bool = False,
) -> Dict[str, Any]:
    """Validate one candidate and calculate its active-contract raw score."""

    if factor_score_mode not in FACTOR_SCORE_MODES:
        raise ValueError("factor_score_mode must be legacy or hybrid_trial")

    row = copy.deepcopy(candidate)
    errors: List[str] = []
    vetoes = [str(value) for value in row.get("vetoes", []) if str(value).strip()]
    section = str(row.get("section") or "").strip().casefold()
    slug = _normalised_slug(row.get("slug"))
    if section == "news" or slug == "news" or slug.startswith("news/"):
        vetoes.append("automatic_news_route")
    brand_mindset_gate_enforced = _enforce_brand_mindset_gate(
        row, errors, vetoes, require_brand_mindset_gate
    )

    source_statuses, positive_signals, signal_qualifications = _signal_statuses(
        row.get("demand_signals"), errors
    )
    positive_acquisition_signals = [
        signal
        for signal in positive_signals
        if signal.get("counts_for_search_demand") is True
    ]
    positive_providers = {
        signal["provider"] for signal in positive_acquisition_signals
    }
    positive_provider_families = {
        signal["provider_family"] for signal in positive_acquisition_signals
    }
    qualified_supporting_providers = {
        signal["provider"]
        for signal in positive_signals
        if signal.get("demand_role") != "acquisition"
    }
    provider_family_scores = _market_demand_by_provider_family(
        positive_signals, signal_qualifications
    )
    trend_class = str(row.get("trend_class") or "").strip().upper()
    if trend_class not in TREND_CLASSES:
        errors.append("invalid_or_missing_trend_class")
    verified_realtime = [
        signal
        for signal in positive_signals
        if _verified_realtime_signal(
            signal,
            realtime_topics,
            str(row.get("publication_run_id") or ""),
            live_trend_verifications,
            live_primary_verifications,
        )
    ]
    if trend_class == "REALTIME_HOT" and not verified_realtime:
        vetoes.append("unverified_realtime_hot_label")
    if trend_class == "RISING_SEARCH" and not any(
        _verified_rising_signal(signal) for signal in positive_signals
    ):
        vetoes.append("unverified_rising_search_label")
    editorial_breakout_verified = _validate_editorial_signal(
        row, errors, vetoes, source_velocity
    )

    dimension_scores: Dict[str, Optional[float]] = {}
    dimension_evidence = row.get("dimension_evidence")
    if not isinstance(dimension_evidence, dict):
        dimension_evidence = {}
    for key in DIMENSION_KEYS:
        dimension_scores[key] = _validate_evidence_block(
            key, dimension_evidence.get(key), errors
        )
    raw_trend_velocity = dimension_scores.get("trend_velocity")
    trend_cap = TREND_VELOCITY_CAPS.get(trend_class)
    if raw_trend_velocity is not None and trend_cap is not None:
        dimension_scores["trend_velocity"] = min(raw_trend_velocity, trend_cap)
    _validate_cluster_support(row, errors)

    market_demand_100 = (
        sum(float(row["score_100"]) for row in provider_family_scores.values())
        / len(provider_family_scores)
        if provider_family_scores
        else 0.0
    )
    score_breakdown: Dict[str, Dict[str, Any]] = {
        "market_demand": {
            "score_100": round(market_demand_100, 2),
            "weight": SCORE_WEIGHTS["market_demand"],
            "weighted_score": round(
                market_demand_100 * SCORE_WEIGHTS["market_demand"] / 100, 2
            ),
            "providers": sorted(positive_providers),
            "provider_families": sorted(positive_provider_families),
            "provider_family_scores": copy.deepcopy(provider_family_scores),
        }
    }
    for key in DIMENSION_KEYS:
        score_100 = dimension_scores[key] or 0.0
        score_breakdown[key] = {
            "score_100": score_100,
            "weight": SCORE_WEIGHTS[key],
            "weighted_score": round(score_100 * SCORE_WEIGHTS[key] / 100, 2),
            "evidence_refs": copy.deepcopy(
                (dimension_evidence.get(key) or {}).get("evidence_refs") or []
            ),
        }
        if key == "trend_velocity":
            score_breakdown[key]["raw_score_100"] = raw_trend_velocity
            score_breakdown[key]["classification_cap"] = trend_cap
    legacy_score = round(
        sum(value["weighted_score"] for value in score_breakdown.values()), 2
    )
    direct_factor_model = _evaluate_direct_factor_model(row)
    hybrid_factor_component = _hybrid_factor_component(direct_factor_model)
    hybrid_score: Optional[float] = None
    active_score = legacy_score
    active_score_source = SCORE_SOURCE
    active_contract_version = TRAFFIC_GATE_CONTRACT_VERSION
    score_status = "ACTIVE"
    factor_vetoes: List[str] = []
    if factor_score_mode == "hybrid_trial":
        active_score_source = HYBRID_SCORE_SOURCE
        active_contract_version = HYBRID_TRAFFIC_GATE_CONTRACT_VERSION
        if hybrid_factor_component["ready"]:
            hybrid_score = round(
                legacy_score * HYBRID_LEGACY_WEIGHT
                + float(hybrid_factor_component["effective_factor_score"])
                * HYBRID_FACTOR_WEIGHT,
                2,
            )
            active_score = hybrid_score
        else:
            score_status = "FACTOR_EVIDENCE_BLOCKED"
            factor_vetoes.append("insufficient_direct_factor_evidence")
            factor_vetoes.extend(hybrid_factor_component["blockers"])

    lane = str(row.get("outcome_lane") or "").strip().casefold()
    sufficient_demand = False
    if lane == "search-first":
        sufficient_demand = len(positive_provider_families) >= 2
    elif lane == "discover-first":
        current_provider = (
            editorial_breakout_verified
            or bool(verified_realtime)
            or any(
                signal.get("provider_family") == "google_trends"
                or signal.get("demand_role") == "supporting_current"
                for signal in positive_signals
            )
        )
        historical = (dimension_scores.get("historical_fit") or 0) > 0
        visual = (dimension_scores.get("discover_story") or 0) > 0
        sufficient_demand = current_provider and historical and visual
    elif lane == "authority-first":
        sufficient_demand = len(positive_provider_families) >= 1
    else:
        errors.append("invalid_outcome_lane")

    legacy_demand_verdict = "REJECT"
    if not sufficient_demand:
        vetoes.append("insufficient_independent_demand_signals")
    elif legacy_score >= PASSING_SCORE:
        legacy_demand_verdict = "TEST" if lane == "authority-first" else "STRONG"
    elif legacy_score >= 70:
        legacy_demand_verdict = "HOLD"
    legacy_vetoes = sorted(set(vetoes))
    legacy_eligible = (
        legacy_score >= PASSING_SCORE
        and legacy_demand_verdict in {"STRONG", "TEST"}
        and not legacy_vetoes
        and not errors
    )

    vetoes.extend(factor_vetoes)
    demand_verdict = "REJECT"
    if not sufficient_demand:
        demand_verdict = "REJECT"
    elif score_status == "FACTOR_EVIDENCE_BLOCKED":
        demand_verdict = "REJECT"
    elif active_score >= PASSING_SCORE:
        demand_verdict = "TEST" if lane == "authority-first" else "STRONG"
    elif active_score >= 70:
        demand_verdict = "HOLD"

    vetoes = sorted(set(vetoes))
    eligible = (
        active_score >= PASSING_SCORE
        and demand_verdict in {"STRONG", "TEST"}
        and not vetoes
        and not errors
    )

    row.update(
        {
            "score": active_score,
            "raw_score": active_score,
            "score_source": active_score_source,
            "score_contract_version": active_contract_version,
            "score_status": score_status,
            "factor_score_mode": factor_score_mode,
            "legacy_score": legacy_score,
            "legacy_score_source": SCORE_SOURCE,
            "legacy_demand_verdict": legacy_demand_verdict,
            "legacy_eligible": legacy_eligible,
            "hybrid_score": hybrid_score,
            "hybrid_score_weights": {
                "legacy": HYBRID_LEGACY_WEIGHT,
                "direct_factor": HYBRID_FACTOR_WEIGHT,
            },
            "score_breakdown": score_breakdown,
            "trend_class": trend_class,
            "editorial_signal": str(row.get("editorial_signal") or "").strip().upper(),
            "editorial_breakout_verified": editorial_breakout_verified,
            "hot_label_eligible": eligible
            and trend_class == "REALTIME_HOT"
            and bool(verified_realtime),
            "hot_markets": sorted(
                {
                    market
                    for signal in verified_realtime
                    for market in (
                        signal.get("metrics", {}).get("markets")
                        or [
                            signal.get("metrics", {}).get("market")
                            or signal.get("metrics", {}).get("geo")
                        ]
                    )
                    if str(market or "").strip()
                }
            ),
            "demand_verdict": demand_verdict,
            "positive_demand_providers": sorted(positive_providers),
            "positive_demand_provider_families": sorted(
                positive_provider_families
            ),
            "qualified_supporting_providers": sorted(
                qualified_supporting_providers
            ),
            "demand_signal_qualifications": signal_qualifications,
            "source_statuses": source_statuses,
            "validation_errors": sorted(set(errors)),
            "vetoes": vetoes,
            "eligible": eligible,
            "brand_mindset_gate_enforced": brand_mindset_gate_enforced,
            "direct_factor_model": direct_factor_model,
            "direct_factor_shadow_score": direct_factor_model.get(
                "coverage_normalized_score"
            ),
            "hybrid_factor_component": hybrid_factor_component,
            "direct_factor_can_change_eligibility": factor_score_mode
            == "hybrid_trial",
        }
    )
    return row


def _can_add_candidate(
    candidate: Dict[str, Any], selected: Sequence[Dict[str, Any]]
) -> Tuple[bool, Optional[str]]:
    intent = str(candidate.get("intent_key") or "").strip().casefold()
    if intent and any(
        intent == str(row.get("intent_key") or "").strip().casefold()
        for row in selected
    ):
        return False, "duplicate_intent_in_portfolio"

    entities = set(_normalised_values(candidate.get("entities") or []))
    for entity in entities:
        count = sum(
            entity in set(_normalised_values(row.get("entities") or []))
            for row in selected
        )
        if count >= 3:
            return False, f"entity_cap:{entity}"
    return True, None


def select_portfolio(
    candidates: Sequence[Dict[str, Any]],
    max_articles: int = 10,
    trend_mode: str = "balanced",
    realtime_trends_snapshot: Any = None,
    live_source_verifications: Optional[Dict[str, Any]] = None,
    source_velocity: Optional[Dict[str, Dict[str, Any]]] = None,
    learning_priors: Optional[Dict[str, Any]] = None,
    provisional_learning_priors: Optional[Dict[str, Any]] = None,
    d2tr_market_context: Optional[Dict[str, Any]] = None,
    factor_score_mode: str = "legacy",
    require_brand_mindset_gate: bool = False,
    brand_mindset_profile: str = "stable",
) -> Dict[str, Any]:
    """Evaluate candidates and select a traffic-weighted, capped portfolio."""

    if max_articles < 0:
        raise ValueError("max_articles must be non-negative")
    if trend_mode not in {"balanced", "realtime_hot", "evergreen"}:
        raise ValueError("trend_mode must be balanced, realtime_hot, or evergreen")
    if factor_score_mode not in FACTOR_SCORE_MODES:
        raise ValueError("factor_score_mode must be legacy or hybrid_trial")
    if brand_mindset_profile not in BRAND_MINDSET_PROFILES:
        raise ValueError("brand_mindset_profile must be stable or recovery")
    realtime_topics = (
        _realtime_topic_registry(realtime_trends_snapshot)
        if realtime_trends_snapshot is not None
        else {}
    )
    live_source_verifications = live_source_verifications or {}
    evaluated = [
        evaluate_candidate(
            candidate,
            realtime_topics,
            live_source_verifications.get("trend_verified"),
            live_source_verifications.get("primary_verified"),
            source_velocity,
            factor_score_mode,
            require_brand_mindset_gate,
        )
        for candidate in candidates
    ]
    validated_durable_priors = _validated_learning_priors(learning_priors)
    validated_provisional_priors = _validated_provisional_learning_priors(
        provisional_learning_priors
    )
    validated_priors = validated_durable_priors + validated_provisional_priors
    validated_d2tr_context, d2tr_context_status = _validated_d2tr_market_context(
        d2tr_market_context
    )
    evaluated = [
        _apply_learning_priority(row, validated_priors, validated_d2tr_context)
        for row in evaluated
    ]
    eligible = sorted(
        (row for row in evaluated if row["eligible"]),
        key=lambda row: (
            -float(row["selection_priority_score"]),
            -float(row["score"]),
            str(row.get("candidate_id") or ""),
        ),
    )
    rejected = [row for row in evaluated if not row["eligible"]]
    selected: List[Dict[str, Any]] = []

    bucket_targets = {
        "proven_demand": int(math.ceil(max_articles * 0.5)),
        "rising_interest": int(math.ceil(max_articles * 0.3)),
        "exploration_authority": int(math.floor(max_articles * 0.2)),
    }
    considered: Set[str] = set()

    def try_add(row: Dict[str, Any]) -> None:
        candidate_key = str(row.get("candidate_id") or row.get("slug") or "")
        if candidate_key in considered or len(selected) >= max_articles:
            return
        considered.add(candidate_key)
        allowed, reason = _can_add_candidate(row, selected)
        if allowed:
            selected.append(row)
        else:
            rejected_row = copy.deepcopy(row)
            rejected_row["eligible"] = False
            rejected_row["portfolio_rejection"] = reason
            rejected.append(rejected_row)

    if require_brand_mindset_gate:
        core_target_share = 0.80 if brand_mindset_profile == "recovery" else 0.60
        core_target = int(math.ceil(max_articles * core_target_share))
        for row in eligible:
            if (
                (row.get("brand_mindset_gate") or {}).get("brand_mindset_class")
                == "CORE_MINDSPACE"
            ):
                try_add(row)
            if len(selected) >= core_target:
                break

    if trend_mode == "realtime_hot":
        for row in eligible:
            if row.get("trend_class") == "REALTIME_HOT":
                try_add(row)
            if len(selected) >= int(math.ceil(max_articles * 0.4)):
                break
        for row in eligible:
            if row.get("trend_class") == "RISING_SEARCH":
                try_add(row)
            if len(selected) >= int(math.ceil(max_articles * 0.6)):
                break
    elif trend_mode == "evergreen":
        for row in eligible:
            if row.get("trend_class") == "EVERGREEN_SEARCH":
                try_add(row)

    for bucket, target in bucket_targets.items():
        bucket_rows = [row for row in eligible if row.get("portfolio_bucket") == bucket]
        before = len(selected)
        for row in bucket_rows:
            if len(selected) - before >= target:
                break
            try_add(row)

    for row in eligible:
        try_add(row)

    active_contract_version = (
        HYBRID_TRAFFIC_GATE_CONTRACT_VERSION
        if factor_score_mode == "hybrid_trial"
        else TRAFFIC_GATE_CONTRACT_VERSION
    )
    active_score_source = (
        HYBRID_SCORE_SOURCE if factor_score_mode == "hybrid_trial" else SCORE_SOURCE
    )
    return {
        "rubric_version": active_contract_version,
        "score_source": active_score_source,
        "factor_score_mode": factor_score_mode,
        "candidate_pool_fingerprint": _snapshot_fingerprint(
            {"candidates": list(candidates)}
        ),
        "trend_mode": trend_mode,
        "candidate_count": len(candidates),
        "max_articles": max_articles,
        "selected": selected,
        "rejected": rejected,
        "no_topic_slots": max(0, max_articles - len(selected)),
        "portfolio_mix": {
            bucket: sum(row.get("portfolio_bucket") == bucket for row in selected)
            for bucket in bucket_targets
        },
        "trend_mix": {
            trend_class: sum(
                row.get("trend_class") == trend_class for row in selected
            )
            for trend_class in sorted(TREND_CLASSES)
        },
        "editorial_mix": {
            signal: sum(row.get("editorial_signal") == signal for row in selected)
            for signal in sorted(EDITORIAL_SIGNALS)
        },
        "brand_mindset_mix": {
            "contract_version": BRAND_MINDSET_GATE_CONTRACT_VERSION,
            "enforced": require_brand_mindset_gate,
            "profile": brand_mindset_profile,
            "core": sum(
                (row.get("brand_mindset_gate") or {}).get("brand_mindset_class")
                == "CORE_MINDSPACE"
                for row in selected
            ),
            "qualified_adjacent": sum(
                (row.get("brand_mindset_gate") or {}).get("brand_mindset_class")
                == "QUALIFIED_ADJACENT"
                for row in selected
            ),
            "automatic_exploration_allowed": False
            if require_brand_mindset_gate
            else None,
        },
        "direct_factor_model_summary": {
            "contract_version": DIRECT_FACTOR_MODEL_CONTRACT_VERSION,
            "score_source": DIRECT_FACTOR_SCORE_SOURCE,
            "mode": (
                "HYBRID_TRIAL" if factor_score_mode == "hybrid_trial" else "SHADOW"
            ),
            "factor_count": len(DIRECT_FACTOR_REGISTRY),
            "factor_weight_total": round(
                sum(
                    float(spec["weight"])
                    for spec in DIRECT_FACTOR_REGISTRY.values()
                ),
                2,
            ),
            "candidates_with_factor_evidence": sum(
                (row.get("direct_factor_model") or {}).get("status")
                != "NOT_PROVIDED"
                for row in evaluated
            ),
            "diagnostic_usable_candidates": sum(
                bool((row.get("direct_factor_model") or {}).get("diagnostic_usable"))
                for row in evaluated
            ),
            "hybrid_ready_candidates": sum(
                bool((row.get("hybrid_factor_component") or {}).get("ready"))
                for row in evaluated
            ),
            "hybrid_blocked_candidates": sum(
                not bool((row.get("hybrid_factor_component") or {}).get("ready"))
                for row in evaluated
            ),
            "production_decisions_affected": 0,
            "trial_decisions_affected": (
                sum(
                    bool(row.get("eligible")) != bool(row.get("legacy_eligible"))
                    for row in evaluated
                )
                if factor_score_mode == "hybrid_trial"
                else 0
            ),
        },
        "live_source_verification": {
            "trend_evidence_count": len(
                live_source_verifications.get("trend_verified") or []
            ),
            "primary_source_count": sum(
                bool(row.get("verified"))
                for row in (
                    live_source_verifications.get("primary_verified") or {}
                ).values()
            ),
            "receipts": live_source_verifications.get("receipts") or [],
        },
        "hard_boundaries": {
            "minimum_score": PASSING_SCORE,
            "max_same_entity": 3,
            "automatic_news_allowed": False,
            "brand_mindset_gate_required": require_brand_mindset_gate,
            "brand_mindset_gate_can_change_raw_score": False,
            "brand_mindset_gate_can_create_demand": False,
            "automatic_exploration_allowed": False
            if require_brand_mindset_gate
            else None,
            "realtime_hot_requires_verified_official_google_trends": True,
            "realtime_hot_reconciled_to_snapshot": bool(realtime_topics),
            "learning_priors_apply_after_eligibility": True,
            "learning_priors_can_bypass_veto": False,
            "maximum_learning_adjustment": MAX_LEARNING_ADJUSTMENT,
            "d2tr_applies_after_eligibility": True,
            "d2tr_can_create_demand": False,
            "d2tr_can_create_realtime_hot": False,
            "maximum_d2tr_raw_adjustment": D2TR_MAX_ADJUSTMENT,
            "maximum_combined_priority_adjustment": MAX_LEARNING_ADJUSTMENT,
        },
        "learning_prior_summary": {
            "status": (
                learning_priors.get("status")
                if isinstance(learning_priors, dict)
                else "NOT_PROVIDED"
            ),
            "active_prior_count": len(validated_durable_priors),
            "snapshot_fingerprint": (
                learning_priors.get("snapshot_fingerprint")
                if isinstance(learning_priors, dict)
                else None
            ),
        },
        "provisional_learning_prior_summary": {
            "status": (
                provisional_learning_priors.get("status")
                if isinstance(provisional_learning_priors, dict)
                else "NOT_PROVIDED"
            ),
            "active_prior_count": len(validated_provisional_priors),
            "snapshot_fingerprint": (
                provisional_learning_priors.get("snapshot_fingerprint")
                if isinstance(provisional_learning_priors, dict)
                else None
            ),
            "expired_priors_ignored": max(
                0,
                len(
                    provisional_learning_priors.get("priors") or []
                    if isinstance(provisional_learning_priors, dict)
                    else []
                )
                - len(validated_provisional_priors),
            ),
        },
        "d2tr_market_context_summary": {
            "status": d2tr_context_status,
            "snapshot_fingerprint": (
                d2tr_market_context.get("snapshot_fingerprint")
                if isinstance(d2tr_market_context, dict)
                else None
            ),
            "source_snapshot_fingerprint": (
                d2tr_market_context.get("source_snapshot_fingerprint")
                if isinstance(d2tr_market_context, dict)
                else None
            ),
            "observed_at": (
                d2tr_market_context.get("observed_at")
                if isinstance(d2tr_market_context, dict)
                else None
            ),
            "eligible_candidates_with_adjustment": sum(
                float(row.get("d2tr_market_context_adjustment_raw") or 0) > 0
                for row in evaluated
            ),
            "matched_markets": sorted(
                {
                    str(
                        (row.get("d2tr_market_context_evidence") or {}).get("market")
                        or ""
                    )
                    for row in evaluated
                    if float(row.get("d2tr_market_context_adjustment_raw") or 0) > 0
                }
                - {""}
            ),
        },
    }


def _metric_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def classify_72h(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a 72-hour checkpoint without leaving gate-passing data generic."""

    if str(checkpoint.get("data_maturity") or "").upper() != "MATURE":
        return {
            "classification": "DATA_NOT_MATURE",
            "confidence": "LOW",
            "recommended_variable": None,
            "reason": "The GSC metric date does not cover the full checkpoint window.",
            "sample_gate": {"passed": False},
        }

    gsc = checkpoint.get("gsc") or {}
    search = gsc.get("search") or {}
    discover = gsc.get("discover") or {}
    search_impressions = _metric_number(search.get("impressions")) or 0.0
    discover_impressions = _metric_number(discover.get("impressions")) or 0.0
    search_clicks = _metric_number(search.get("clicks")) or 0.0
    discover_clicks = _metric_number(discover.get("clicks")) or 0.0
    search_ctr = _metric_number(search.get("ctr"))
    discover_ctr = _metric_number(discover.get("ctr"))
    search_position = _metric_number(search.get("average_position"))
    benchmarks = checkpoint.get("benchmarks") or {}
    search_benchmark = _metric_number(benchmarks.get("search_ctr"))
    discover_benchmark = _metric_number(benchmarks.get("discover_ctr"))
    provided_benchmarks = sum(
        value is not None for value in (search_benchmark, discover_benchmark)
    )
    benchmark_source = (
        "provided"
        if provided_benchmarks == 2
        else "mixed"
        if provided_benchmarks == 1
        else "configured_default"
    )
    if search_benchmark is None:
        search_benchmark = 0.04
    if discover_benchmark is None:
        discover_benchmark = 0.05

    search_gate = search_impressions >= 100
    discover_gate = discover_impressions >= 300
    gate = {
        "passed": search_gate or discover_gate,
        "search_impressions_gate": search_gate,
        "discover_impressions_gate": discover_gate,
        "thresholds": {"search_impressions": 100, "discover_impressions": 300},
    }
    if not gate["passed"]:
        return {
            "classification": "NO_MATURE_SIGNAL",
            "confidence": "LOW",
            "recommended_variable": None,
            "reason": "Mature data is below both configured sample gates.",
            "sample_gate": gate,
        }

    if (
        search_gate
        and search_position is not None
        and 4 <= search_position <= 10
        and search_ctr is not None
        and search_ctr < search_benchmark
    ):
        classification = "SEARCH_CTR_OPPORTUNITY"
        recommended_variable = "title"
        reason = "Page-one Search visibility is meaningful but CTR is below benchmark."
    elif (
        discover_gate
        and discover_ctr is not None
        and discover_ctr < discover_benchmark
    ):
        classification = "DISCOVER_PACKAGING_OPPORTUNITY"
        recommended_variable = "hero_or_title"
        reason = "Discover visibility passes the sample gate but CTR is below benchmark."
    elif (
        search_gate
        and search_position is not None
        and 8 <= search_position <= 20
    ):
        classification = "CONTENT_COVERAGE_OPPORTUNITY"
        recommended_variable = "content_coverage"
        reason = "Search demand is visible near page one and supports a coverage review."
    elif discover_clicks >= 50 or search_clicks >= 50:
        classification = "WINNER_WATCH"
        recommended_variable = None
        reason = "The page has a strong mature click signal and should be watched before change."
    elif discover_clicks > 0 or search_clicks > 0:
        classification = "PROMISING"
        recommended_variable = None
        reason = "The page passes a sample gate and has a positive click signal."
    elif search_gate:
        classification = "SEARCH_INTENT_OPPORTUNITY"
        recommended_variable = "intent_alignment"
        reason = "Search impressions pass the gate without clicks; inspect query-intent alignment."
    else:
        classification = "DISCOVER_PACKAGING_OPPORTUNITY"
        recommended_variable = "hero_or_title"
        reason = "Discover impressions pass the gate without clicks; inspect feed packaging."

    return {
        "classification": classification,
        "confidence": "MEDIUM",
        "recommended_variable": recommended_variable,
        "reason": reason,
        "sample_gate": gate,
        "benchmarks": {
            "search_ctr": search_benchmark,
            "discover_ctr": discover_benchmark,
        },
        "benchmark_source": benchmark_source,
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_snapshot_derivative(
    derivative: Any,
    snapshot: Dict[str, Any],
    *,
    expected_contract: str,
) -> None:
    if not isinstance(derivative, dict):
        raise ValueError(f"{expected_contract} artifact must be an object")
    if derivative.get("contract_version") != expected_contract:
        raise ValueError(f"invalid {expected_contract} contract version")
    if derivative.get("run_id") != snapshot.get("run_id"):
        raise ValueError(f"{expected_contract} run_id mismatch")
    if derivative.get("snapshot_fingerprint") != snapshot.get("snapshot_fingerprint"):
        raise ValueError(f"{expected_contract} snapshot fingerprint mismatch")
    if expected_contract == "realtime-trends-v1":
        expected = {
            "contract_version": snapshot.get("contract_version"),
            "run_id": snapshot.get("run_id"),
            "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
            "observed_at": snapshot.get("observed_at"),
            "status": snapshot.get("status"),
            "markets": [
                {
                    "geo": row.get("geo"),
                    "market_tier": row.get("market_tier"),
                    "status": row.get("status"),
                    "item_count": row.get("item_count"),
                    "source_url": row.get("source_url"),
                    "reason": row.get("reason"),
                }
                for row in snapshot.get("markets") or []
            ],
        }
    else:
        expected = {
            "contract_version": "hotness-gate-v1",
            "run_id": snapshot.get("run_id"),
            "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
            "observed_at": snapshot.get("observed_at"),
            "source_status": snapshot.get("status"),
            "realtime_candidate_count": sum(
                row.get("realtime_candidate") is True
                for row in snapshot.get("topics") or []
            ),
            "topics": [
                {
                    "trend_query": row.get("query"),
                    "markets": row.get("markets"),
                    "newest_published_at": row.get("newest_published_at"),
                    "max_approx_traffic": row.get("max_approx_traffic"),
                    "news_confirmation_count": row.get("news_confirmation_count"),
                }
                for row in snapshot.get("topics") or []
                if row.get("realtime_candidate") is True
            ],
            "credentials_included": False,
        }
    if derivative != expected:
        raise ValueError(f"{expected_contract} contents do not match snapshot")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--input", required=True, type=Path)
    score_parser.add_argument("--output", required=True, type=Path)
    score_parser.add_argument("--max-articles", type=int, default=10)
    score_parser.add_argument(
        "--trend-mode",
        choices=("balanced", "realtime_hot", "evergreen"),
        default="balanced",
    )
    score_parser.add_argument(
        "--require-brand-mindset-gate",
        action="store_true",
        help=(
            "Fail closed unless every candidate carries a valid brand-mindset-fit-v1 "
            "pre-score gate result"
        ),
    )
    score_parser.add_argument(
        "--brand-mindset-profile",
        choices=tuple(sorted(BRAND_MINDSET_PROFILES)),
        default="stable",
        help="Soft core-mindspace portfolio preference after normal eligibility",
    )
    score_parser.add_argument(
        "--factor-score-mode",
        choices=tuple(sorted(FACTOR_SCORE_MODES)),
        default="legacy",
        help=(
            "Opt-in hybrid_trial uses 80% legacy and 20% evidence-gated "
            "direct-factor score; legacy remains the production default"
        ),
    )
    score_parser.add_argument(
        "--realtime-trends",
        type=Path,
        help="Official realtime-trends snapshot; required for realtime_hot mode",
    )
    score_parser.add_argument("--trend-market-map", type=Path)
    score_parser.add_argument("--hotness-gate", type=Path)
    score_parser.add_argument("--editorial-intelligence", type=Path)
    score_parser.add_argument("--source-velocity", type=Path)
    score_parser.add_argument(
        "--learning-priors",
        type=Path,
        help="Governed performance-learning-v1 priors; only reorder eligible candidates",
    )
    score_parser.add_argument(
        "--provisional-learning-priors",
        type=Path,
        help=(
            "Expiring performance-learning-provisional-v1 priors; only reorder "
            "eligible candidates"
        ),
    )
    score_parser.add_argument(
        "--d2tr-market-context",
        type=Path,
        help=(
            "Independent d2tr-discover-context-v1 snapshot; may only reorder "
            "already eligible candidates"
        ),
    )

    classify_parser = subparsers.add_parser("classify-72h")
    classify_parser.add_argument("--input", required=True, type=Path)
    classify_parser.add_argument("--output", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "score":
        payload = _load_json(args.input)
        candidates = payload.get("candidates") if isinstance(payload, dict) else payload
        if not isinstance(candidates, list):
            raise ValueError("score input must be a list or contain a candidates list")
        contains_realtime_hot = any(
            str(row.get("trend_class") or "").strip().upper() == "REALTIME_HOT"
            for row in candidates
            if isinstance(row, dict)
        )
        if (
            any(
                value is None
                for value in (
                    args.realtime_trends,
                    args.trend_market_map,
                    args.hotness_gate,
                )
            )
            and (args.trend_mode == "realtime_hot" or contains_realtime_hot)
        ):
            raise ValueError(
                "--realtime-trends, --trend-market-map and --hotness-gate are required "
                "for realtime_hot mode or candidates"
            )
        realtime_snapshot = (
            _load_json(args.realtime_trends) if args.realtime_trends is not None else None
        )
        if realtime_snapshot is not None:
            _validate_snapshot_derivative(
                _load_json(args.trend_market_map),
                realtime_snapshot,
                expected_contract="realtime-trends-v1",
            )
            _validate_snapshot_derivative(
                _load_json(args.hotness_gate),
                realtime_snapshot,
                expected_contract="hotness-gate-v1",
            )
        live_source_verifications = verify_live_sources(candidates)
        contains_editorial_breakout = any(
            str(row.get("editorial_signal") or "").strip().upper()
            == "EDITORIAL_BREAKOUT"
            for row in candidates
            if isinstance(row, dict)
        )
        if contains_editorial_breakout and (
            args.editorial_intelligence is None or args.source_velocity is None
        ):
            raise ValueError(
                "--editorial-intelligence and --source-velocity are required "
                "for EDITORIAL_BREAKOUT candidates"
            )
        if args.editorial_intelligence is not None:
            editorial_intelligence = _load_json(args.editorial_intelligence)
            if not isinstance(editorial_intelligence, dict):
                raise ValueError("editorial-intelligence artifact must be an object")
        velocity_payload = (
            _load_json(args.source_velocity) if args.source_velocity is not None else []
        )
        if isinstance(velocity_payload, dict):
            velocity_rows = velocity_payload.get("candidates") or []
        else:
            velocity_rows = velocity_payload
        if not isinstance(velocity_rows, list):
            raise ValueError("source-velocity artifact must be a list or contain candidates")
        source_velocity = {
            str(row.get("candidate_id") or "").strip(): row
            for row in velocity_rows
            if isinstance(row, dict) and str(row.get("candidate_id") or "").strip()
        }
        learning_priors = (
            _load_json(args.learning_priors) if args.learning_priors is not None else None
        )
        provisional_learning_priors = (
            _load_json(args.provisional_learning_priors)
            if args.provisional_learning_priors is not None
            else None
        )
        d2tr_market_context = (
            _load_json(args.d2tr_market_context)
            if args.d2tr_market_context is not None
            else None
        )
        _write_json(
            args.output,
            select_portfolio(
                candidates,
                args.max_articles,
                args.trend_mode,
                realtime_snapshot,
                live_source_verifications,
                source_velocity,
                learning_priors,
                provisional_learning_priors,
                d2tr_market_context,
                args.factor_score_mode,
                args.require_brand_mindset_gate,
                args.brand_mindset_profile,
            ),
        )
    else:
        _write_json(args.output, classify_72h(_load_json(args.input)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

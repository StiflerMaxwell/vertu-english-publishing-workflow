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
                    "User-Agent": "VERTU-Content-Traffic-Gate/3.5.0",
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
            primary_verified[url] = {
                "verified": status == 200 and bool(matched_terms),
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


def _apply_learning_priority(
    candidate: Dict[str, Any], priors: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    row = copy.deepcopy(candidate)
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
    row["durable_learning_adjustment"] = round(durable_adjustment, 2)
    row["provisional_learning_adjustment"] = round(provisional_adjustment, 2)
    row["learning_adjustment"] = round(adjustment, 2)
    row["selection_priority_score"] = round(float(row.get("score") or 0) + adjustment, 2)
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
        and primary_source_status == 200
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


def _signal_statuses(
    signals: Any, errors: List[str]
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    if not isinstance(signals, list):
        errors.append("missing_demand_signals")
        return {}, []

    statuses: Dict[str, Dict[str, Any]] = {}
    positive: List[Dict[str, Any]] = []
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

        if status == SOURCE_UNAVAILABLE:
            unavailable = {
                "status": SOURCE_UNAVAILABLE,
                "reason": str(signal.get("reason") or "").strip(),
                "observed_at": signal.get("observed_at"),
            }
            if not unavailable["reason"]:
                errors.append(f"missing_unavailable_reason:{provider}")
            statuses[provider] = unavailable
            continue

        score = _bounded_score(signal.get("score_100"))
        evidence_ref = str(signal.get("evidence_ref") or "").strip()
        if score is None:
            errors.append(f"invalid_demand_score:{provider}")
        if not evidence_ref:
            errors.append(f"missing_demand_evidence:{provider}")
        available = {
            "status": AVAILABLE,
            "positive": bool(signal.get("positive")),
            "score_100": score,
            "evidence_ref": evidence_ref,
            "observed_at": signal.get("observed_at"),
            "metrics": copy.deepcopy(signal.get("metrics") or {}),
        }
        statuses[provider] = available
        if available["positive"] and score is not None and evidence_ref:
            positive.append({"provider": provider, **available})
    return statuses, positive


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
) -> Dict[str, Any]:
    """Validate one candidate and calculate its final v3.5.0 score."""

    row = copy.deepcopy(candidate)
    errors: List[str] = []
    vetoes = [str(value) for value in row.get("vetoes", []) if str(value).strip()]
    section = str(row.get("section") or "").strip().casefold()
    slug = _normalised_slug(row.get("slug"))
    if section == "news" or slug == "news" or slug.startswith("news/"):
        vetoes.append("automatic_news_route")

    source_statuses, positive_signals = _signal_statuses(
        row.get("demand_signals"), errors
    )
    positive_providers = {signal["provider"] for signal in positive_signals}
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
        sum(float(signal["score_100"]) for signal in positive_signals)
        / len(positive_signals)
        if positive_signals
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
    final_score = round(
        sum(value["weighted_score"] for value in score_breakdown.values()), 2
    )

    lane = str(row.get("outcome_lane") or "").strip().casefold()
    sufficient_demand = False
    demand_verdict = "REJECT"
    if lane == "search-first":
        sufficient_demand = len(positive_providers) >= 2
    elif lane == "discover-first":
        current_provider = editorial_breakout_verified or bool(verified_realtime) or bool(
            positive_providers
            & {"google_trends", "current_event", "current_interest", "news_cycle"}
        )
        historical = (dimension_scores.get("historical_fit") or 0) > 0
        visual = (dimension_scores.get("discover_story") or 0) > 0
        sufficient_demand = current_provider and historical and visual
    elif lane == "authority-first":
        sufficient_demand = len(positive_providers) >= 1
    else:
        errors.append("invalid_outcome_lane")

    if not sufficient_demand:
        vetoes.append("insufficient_independent_demand_signals")
    elif final_score >= PASSING_SCORE:
        demand_verdict = "TEST" if lane == "authority-first" else "STRONG"
    elif final_score >= 70:
        demand_verdict = "HOLD"

    vetoes = sorted(set(vetoes))
    eligible = (
        final_score >= PASSING_SCORE
        and demand_verdict in {"STRONG", "TEST"}
        and not vetoes
        and not errors
    )

    row.update(
        {
            "score": final_score,
            "score_source": "computed_v3_5_0",
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
            "source_statuses": source_statuses,
            "validation_errors": sorted(set(errors)),
            "vetoes": vetoes,
            "eligible": eligible,
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
) -> Dict[str, Any]:
    """Evaluate candidates and select a traffic-weighted, capped portfolio."""

    if max_articles < 0:
        raise ValueError("max_articles must be non-negative")
    if trend_mode not in {"balanced", "realtime_hot", "evergreen"}:
        raise ValueError("trend_mode must be balanced, realtime_hot, or evergreen")
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
        )
        for candidate in candidates
    ]
    validated_durable_priors = _validated_learning_priors(learning_priors)
    validated_provisional_priors = _validated_provisional_learning_priors(
        provisional_learning_priors
    )
    validated_priors = validated_durable_priors + validated_provisional_priors
    evaluated = [_apply_learning_priority(row, validated_priors) for row in evaluated]
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

    return {
        "rubric_version": "traffic-acquisition-v3.5.0",
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
            "realtime_hot_requires_verified_official_google_trends": True,
            "realtime_hot_reconciled_to_snapshot": bool(realtime_topics),
            "learning_priors_apply_after_eligibility": True,
            "learning_priors_can_bypass_veto": False,
            "maximum_learning_adjustment": MAX_LEARNING_ADJUSTMENT,
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
            ),
        )
    else:
        _write_json(args.output, classify_72h(_load_json(args.input)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

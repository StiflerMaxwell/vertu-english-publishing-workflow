#!/usr/bin/env python3
"""Build governed VERTU content-learning snapshots from real checkpoint evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


CHECKPOINT_LEVEL = {
    "72h": "OBSERVATION",
    "7d": "CANDIDATE_PRIOR",
    "28d": "DURABLE_INPUT",
}
POSITIVE_CLASSES = {"WINNER", "WINNER_WATCH", "EARLY_WINNER", "PROMISING", "SEARCH_BUILDER"}
NEGATIVE_CLASSES = {
    "UNDERPERFORMER",
    "NO_DEMAND",
    "CTR_PACKAGING",
    "DISCOVER_PACKAGING_OPPORTUNITY",
    "SEARCH_CTR_OPPORTUNITY",
    "CONTENT_COVERAGE_OPPORTUNITY",
    "SEARCH_INTENT_OPPORTUNITY",
    "RANKING_OPPORTUNITY",
    "ENGAGEMENT_GAP",
    "TECHNICAL_FAILURE",
}
CONTEXT_SPECIFIC_SCOPE_FIELDS = (
    "cluster_id",
    "intent_key",
    "outcome_lane",
)
CONTEXT_COMPLETE_FIELDS = (
    "publication_run_id",
    "cluster_id",
    "intent_key",
    "outcome_lane",
    "trend_class",
)
PROMOTION_MIN_ARTICLES = 3
PROMOTION_MIN_RUNS = 2
PROVISIONAL_EVIDENCE_MAX_AGE_DAYS = 14
PROVISIONAL_TTL_DAYS = 8
PROVISIONAL_RULES = {
    "72h": {
        "minimum_articles": 3,
        "minimum_runs": 2,
        "minimum_directional_agreement": 0.67,
        "maximum_absolute_adjustment": 1,
    },
    "7d": {
        "minimum_articles": 2,
        "minimum_runs": 2,
        "minimum_directional_agreement": 0.75,
        "maximum_absolute_adjustment": 2,
    },
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def fingerprint(payload: Dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "snapshot_fingerprint"}
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def iso_datetime(value: Any) -> Optional[datetime]:
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


def article_key(row: Dict[str, Any], path: Path) -> str:
    publication = row.get("publication") or {}
    return str(
        row.get("article_key")
        or publication.get("slug")
        or row.get("slug")
        or path.parent.name
    ).strip()


def checkpoint_rejection(row: Dict[str, Any]) -> Optional[str]:
    checkpoint = str(row.get("checkpoint") or "").strip().lower()
    if checkpoint not in CHECKPOINT_LEVEL:
        return "UNSUPPORTED_CHECKPOINT"
    if iso_datetime(row.get("executed_at_utc") or row.get("executed_at")) is None:
        return "PLANNED_PLACEHOLDER"
    if str(row.get("checkpoint_status") or "").strip().upper() != "COMPLETED":
        return str(row.get("checkpoint_status") or "NOT_COMPLETED").strip().upper()
    if str(row.get("data_maturity") or "").strip().upper() != "MATURE":
        return str(row.get("data_maturity") or "DATA_NOT_MATURE").strip().upper()
    gsc = row.get("gsc")
    if not isinstance(gsc, dict) or str(gsc.get("status") or "").upper() != "MATURE":
        return "GSC_NOT_MATURE"
    ga4 = row.get("ga4")
    ga4_status = (
        str(ga4.get("status") or "").strip().upper()
        if isinstance(ga4, dict)
        else ""
    )
    if ga4_status == "SOURCE_BLOCKED":
        return "SOURCE_BLOCKED"
    if ga4_status in {"", "DATA_NOT_MATURE", "PRELIMINARY"}:
        return "GA4_NOT_MATURE"
    return None


def checkpoint_paths(root: Path) -> Iterable[Path]:
    yield from root.glob("**/performance/*/*.json")


def metadata_index(root: Path) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    field_priority: Dict[str, Dict[str, int]] = defaultdict(dict)

    def merge(slug: str, values: Dict[str, Any], priority: int, source: str) -> None:
        if not slug:
            return
        current = index.setdefault(slug, {})
        for key, value in values.items():
            if (
                value not in (None, "", [], {})
                and priority >= field_priority[slug].get(key, -1)
            ):
                current[key] = value
                field_priority[slug][key] = priority
        sources = current.setdefault("metadata_sources", [])
        if source not in sources:
            sources.append(source)

    def run_id(payload: Dict[str, Any], path: Path) -> str:
        return str(
            payload.get("publication_run_id")
            or payload.get("run_id")
            or payload.get("execution_id")
            or path.parent.name
        ).strip()

    def candidate_cluster_map(run_path: Path) -> Dict[str, str]:
        path = run_path / "cluster-support.json"
        if not path.exists():
            return {}
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            return {}
        rows = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return {}
        return {
            str(row.get("candidate_id") or "").strip(): str(
                row.get("cluster") or ""
            ).strip()
            for row in rows
            if isinstance(row, dict)
            and str(row.get("candidate_id") or "").strip()
            and str(row.get("cluster") or "").strip()
        }

    # Candidate demand rows are useful enrichment, but include unselected rows and
    # therefore have the lowest authority.
    for path in sorted(root.glob("**/traffic-demand.json")):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        rows = None
        if isinstance(payload, dict):
            rows = payload.get("selected") or payload.get("candidates")
        if not isinstance(rows, list):
            continue
        clusters = candidate_cluster_map(path.parent)
        for row in rows:
            if not isinstance(row, dict):
                continue
            slug = str(row.get("slug") or "").strip()
            gsc_cluster = None
            for signal in row.get("demand_signals") or []:
                if (
                    isinstance(signal, dict)
                    and signal.get("provider") == "google_search_console_cluster"
                ):
                    metrics = signal.get("metrics") or {}
                    gsc_cluster = metrics.get("cluster")
                    if gsc_cluster:
                        break
            merge(
                slug,
                {
                    "publication_run_id": row.get("publication_run_id")
                    or run_id(payload, path),
                    "candidate_id": row.get("candidate_id"),
                    "cluster_id": row.get("cluster_id")
                    or clusters.get(str(row.get("candidate_id") or ""))
                    or row.get("audience_fit_lane")
                    or gsc_cluster,
                    "trend_class": row.get("trend_class"),
                    "section": row.get("section"),
                    "outcome_lane": row.get("outcome_lane"),
                    "intent_key": row.get("intent_key")
                    or row.get("decision_intent")
                    or row.get("query_intent_boundary"),
                    "portfolio_bucket": row.get("portfolio_bucket"),
                },
                priority=10,
                source="traffic-demand",
            )

    # Preserve compatibility with first-generation publication packages.
    for path in sorted(root.glob("**/completion-report.json")):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        rows = payload.get("articles") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            continue
        publication_run_id = run_id(payload, path)
        for row in rows:
            if not isinstance(row, dict):
                continue
            slug = str(row.get("slug") or "").strip()
            if slug:
                merge(
                    slug,
                    {
                        "publication_run_id": publication_run_id,
                        "candidate_id": row.get("candidate_id"),
                        "cluster_id": row.get("cluster_id"),
                        "trend_class": row.get("trend_class"),
                        "section": row.get("section"),
                        "outcome_lane": row.get("traffic_mode")
                        or row.get("outcome_lane"),
                        "intent_key": row.get("intent_key"),
                        "portfolio_bucket": row.get("portfolio_bucket"),
                    },
                    priority=20,
                    source="completion-report",
                )

    # Current delivery truth: only articles present here reached the run result.
    for path in sorted(root.glob("**/run-summary.json")):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        rows = payload.get("articles") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            slug = str(row.get("slug") or "").strip()
            merge(
                slug,
                {
                    "publication_run_id": row.get("publication_run_id")
                    or run_id(payload, path),
                    "candidate_id": row.get("candidate_id"),
                    "cluster_id": row.get("cluster_id"),
                    "trend_class": row.get("trend_class"),
                    "section": row.get("section"),
                    "outcome_lane": row.get("outcome_lane"),
                    "intent_key": row.get("intent_key"),
                    "portfolio_bucket": row.get("portfolio_bucket"),
                },
                priority=30,
                source="run-summary",
            )

    # Current selection truth has the richest governed topic context.
    for path in sorted(root.glob("**/candidate-scores.json")):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        rows = payload.get("selected") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            continue
        clusters = candidate_cluster_map(path.parent)
        for row in rows:
            if not isinstance(row, dict):
                continue
            slug = str(row.get("slug") or "").strip()
            candidate_id = str(row.get("candidate_id") or "").strip()
            forecast = row.get("predraft_discover_forecast") or {}
            merge(
                slug,
                {
                    "publication_run_id": row.get("publication_run_id")
                    or run_id(payload, path),
                    "candidate_id": candidate_id,
                    "cluster_id": row.get("cluster_id")
                    or clusters.get(candidate_id)
                    or row.get("audience_fit_lane")
                    or forecast.get("historical_cluster"),
                    "trend_class": row.get("trend_class"),
                    "section": row.get("section"),
                    "outcome_lane": row.get("outcome_lane"),
                    "intent_key": row.get("intent_key")
                    or row.get("decision_intent")
                    or row.get("query_intent_boundary"),
                    "portfolio_bucket": row.get("portfolio_bucket"),
                },
                priority=40,
                source="candidate-scores:selected",
            )

    for values in index.values():
        values["learning_context_version"] = "learning-context-v1"
        values["learning_context_status"] = (
            "COMPLETE"
            if all(str(values.get(field) or "").strip() for field in CONTEXT_COMPLETE_FIELDS)
            else "PARTIAL"
        )
    return index


def _classification(row: Dict[str, Any]) -> str:
    diagnosis = row.get("diagnosis") or {}
    return str(
        diagnosis.get("classification")
        or row.get("classification")
        or "NO_CLASSIFICATION"
    ).strip().upper()


def _direction(classification: str) -> int:
    if classification in POSITIVE_CLASSES:
        return 1
    if classification in NEGATIVE_CLASSES:
        return -1
    return 0


def collect_checkpoints(root: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    metadata = metadata_index(root)
    latest_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    rejected: List[Dict[str, Any]] = []
    for path in checkpoint_paths(root):
        try:
            row = load_json(path)
        except (OSError, json.JSONDecodeError) as error:
            rejected.append({"path": str(path), "reason": f"INVALID_JSON:{error}"})
            continue
        if not isinstance(row, dict):
            rejected.append({"path": str(path), "reason": "INVALID_SHAPE"})
            continue
        key = article_key(row, path)
        checkpoint = str(row.get("checkpoint") or "").strip().lower()
        if checkpoint not in CHECKPOINT_LEVEL:
            rejected.append(
                {
                    "article_key": key,
                    "checkpoint": checkpoint or None,
                    "path": str(path),
                    "reason": "UNSUPPORTED_CHECKPOINT",
                }
            )
            continue
        executed = iso_datetime(row.get("executed_at_utc") or row.get("executed_at"))
        if executed is None:
            rejected.append(
                {
                    "article_key": key,
                    "checkpoint": checkpoint,
                    "path": str(path),
                    "reason": "PLANNED_PLACEHOLDER",
                }
            )
            continue
        envelope = {
            "article_key": key,
            "checkpoint": checkpoint,
            "executed": executed,
            "path": str(path),
            "row": row,
        }
        previous = latest_by_key.get((key, checkpoint))
        if previous is None or (executed, str(path)) > (
            previous["executed"],
            previous["path"],
        ):
            if previous is not None:
                rejected.append(
                    {
                        "article_key": key,
                        "checkpoint": checkpoint,
                        "path": previous["path"],
                        "reason": "SUPERSEDED_RETRY",
                    }
                )
            latest_by_key[(key, checkpoint)] = envelope
        else:
            rejected.append(
                {
                    "article_key": key,
                    "checkpoint": checkpoint,
                    "path": str(path),
                    "reason": "SUPERSEDED_RETRY",
                }
            )

    accepted: List[Dict[str, Any]] = []
    for key, checkpoint in sorted(latest_by_key):
        envelope = latest_by_key[(key, checkpoint)]
        row = envelope["row"]
        path = Path(envelope["path"])
        reason = checkpoint_rejection(row)
        if reason is not None:
            rejected.append(
                {
                    "article_key": key,
                    "checkpoint": checkpoint,
                    "path": str(path),
                    "reason": reason,
                }
            )
            continue
        executed = envelope["executed"]
        publication = row.get("publication") or {}
        candidate = {
            "article_key": key,
            "checkpoint": checkpoint,
            "learning_level": CHECKPOINT_LEVEL[checkpoint],
            "executed_at": executed.isoformat().replace("+00:00", "Z"),
            "classification": _classification(row),
            "raw_classification": _classification(row),
            "direction": _direction(_classification(row)),
            "learning_direction": _direction(_classification(row)),
            "path": str(path),
            "gsc": row.get("gsc"),
            "ga4_status": (row.get("ga4") or {}).get("status"),
            "publication_run_id": (
                row.get("publication_run_id")
                or publication.get("publication_run_id")
                or publication.get("run_id")
            ),
            "cluster_id": row.get("cluster_id"),
            "trend_class": row.get("trend_class"),
            "section": row.get("section") or publication.get("section"),
            "outcome_lane": row.get("outcome_lane"),
            "intent_key": row.get("intent_key"),
            "portfolio_bucket": row.get("portfolio_bucket"),
            **metadata.get(key, {}),
        }
        accepted.append(candidate)
    return sorted(accepted, key=lambda row: (row["checkpoint"], row["article_key"])), rejected


def _scope_pairs(row: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    if not str(row.get("publication_run_id") or "").strip():
        return
    fields = list(CONTEXT_SPECIFIC_SCOPE_FIELDS)
    if row.get("learning_context_status") == "COMPLETE":
        fields.extend(("trend_class", "section", "portfolio_bucket"))
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value:
            yield field, value


def build_priors(checkpoints: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in checkpoints:
        if row.get("checkpoint") != "28d":
            continue
        for scope in _scope_pairs(row):
            groups[scope].append(row)

    priors: List[Dict[str, Any]] = []
    for (scope_type, scope_value), rows in sorted(groups.items()):
        articles = {row["article_key"] for row in rows}
        runs = {
            str(row.get("publication_run_id") or "").strip()
            for row in rows
            if str(row.get("publication_run_id") or "").strip()
        }
        directional = [int(row.get("direction") or 0) for row in rows]
        if len(articles) < PROMOTION_MIN_ARTICLES or len(runs) < PROMOTION_MIN_RUNS:
            continue
        total_direction = sum(directional)
        if total_direction == 0:
            continue
        agreement = abs(total_direction) / len(directional)
        if agreement < 0.67:
            continue
        adjustment = 1 if agreement < 0.8 else 2
        if len(articles) >= 6 and agreement >= 0.8:
            adjustment = 3
        if total_direction < 0:
            adjustment *= -1
        evidence_paths = sorted({row["path"] for row in rows})
        prior_id = hashlib.sha256(
            f"{scope_type}|{scope_value}|{'|'.join(evidence_paths)}".encode("utf-8")
        ).hexdigest()[:16]
        priors.append(
            {
                "prior_id": f"prior-{prior_id}",
                "state": "ACTIVE",
                "learning_level": "DURABLE_PRIOR",
                "scope_type": scope_type,
                "scope_value": scope_value,
                "selection_adjustment": adjustment,
                "confidence": "HIGH" if len(articles) >= 6 else "MEDIUM",
                "evidence": {
                    "d28_article_count": len(articles),
                    "publication_run_count": len(runs),
                    "verified_experiment_count": 0,
                    "positive_count": sum(value > 0 for value in directional),
                    "negative_count": sum(value < 0 for value in directional),
                    "neutral_count": sum(value == 0 for value in directional),
                    "paths": evidence_paths,
                },
                "rollback_condition": "Disable if the next two mature cohorts reverse the directional result or replay reduces gate compliance or diversity.",
            }
        )
    return priors


def build_provisional_priors(
    checkpoints: Sequence[Dict[str, Any]],
    generated_at: datetime,
) -> List[Dict[str, Any]]:
    """Build expiring candidate priors from recent repeated 72h/7d evidence."""

    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    oldest_allowed = generated_at - timedelta(days=PROVISIONAL_EVIDENCE_MAX_AGE_DAYS)
    for row in checkpoints:
        checkpoint = str(row.get("checkpoint") or "").strip().lower()
        if checkpoint not in PROVISIONAL_RULES:
            continue
        executed = iso_datetime(row.get("executed_at"))
        if executed is None or executed < oldest_allowed or executed > generated_at:
            continue
        for scope_type, scope_value in _scope_pairs(row):
            groups[(checkpoint, scope_type, scope_value)].append(row)

    selected_by_scope: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for checkpoint in ("7d", "72h"):
        rule = PROVISIONAL_RULES[checkpoint]
        matching_groups = sorted(
            (
                (scope_type, scope_value, rows)
                for (row_checkpoint, scope_type, scope_value), rows in groups.items()
                if row_checkpoint == checkpoint
            ),
            key=lambda item: (item[0], item[1]),
        )
        for scope_type, scope_value, rows in matching_groups:
            scope_key = (scope_type, scope_value)
            if scope_key in selected_by_scope:
                continue
            articles = {row["article_key"] for row in rows}
            runs = {
                str(row.get("publication_run_id") or "").strip()
                for row in rows
                if str(row.get("publication_run_id") or "").strip()
            }
            directional = [int(row.get("direction") or 0) for row in rows]
            if (
                len(articles) < int(rule["minimum_articles"])
                or len(runs) < int(rule["minimum_runs"])
                or not directional
            ):
                continue
            total_direction = sum(directional)
            if total_direction == 0:
                continue
            agreement = abs(total_direction) / len(directional)
            if agreement < float(rule["minimum_directional_agreement"]):
                continue

            adjustment = 1
            if (
                checkpoint == "7d"
                and len(articles) >= 3
                and agreement >= 0.8
            ):
                adjustment = 2
            adjustment = min(
                adjustment,
                int(rule["maximum_absolute_adjustment"]),
            )
            if total_direction < 0:
                adjustment *= -1

            evidence_paths = sorted({row["path"] for row in rows})
            prior_id = hashlib.sha256(
                (
                    f"{checkpoint}|{scope_type}|{scope_value}|"
                    f"{'|'.join(evidence_paths)}"
                ).encode("utf-8")
            ).hexdigest()[:16]
            expires_at = generated_at + timedelta(days=PROVISIONAL_TTL_DAYS)
            selected_by_scope[scope_key] = {
                "prior_id": f"candidate-prior-{prior_id}",
                "state": "ACTIVE",
                "learning_level": "CANDIDATE_PRIOR",
                "scope_type": scope_type,
                "scope_value": scope_value,
                "selection_adjustment": adjustment,
                "confidence": "MEDIUM" if checkpoint == "7d" else "LOW",
                "activated_at": generated_at.isoformat().replace("+00:00", "Z"),
                "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
                "evidence": {
                    "source_checkpoint": checkpoint,
                    "article_count": len(articles),
                    "publication_run_count": len(runs),
                    "positive_count": sum(value > 0 for value in directional),
                    "negative_count": sum(value < 0 for value in directional),
                    "neutral_count": sum(value == 0 for value in directional),
                    "directional_agreement": round(agreement, 4),
                    "maximum_evidence_age_days": PROVISIONAL_EVIDENCE_MAX_AGE_DAYS,
                    "paths": evidence_paths,
                },
                "rollback_condition": (
                    "Expire automatically after eight days; replace or disable sooner "
                    "if the next 48-hour check reverses the directional result."
                ),
            }
    return [
        selected_by_scope[key]
        for key in sorted(selected_by_scope)
    ]


def build_snapshot(root: Path, execution_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    checkpoints, rejected = collect_checkpoints(root)
    priors = build_priors(checkpoints)
    generated_at = datetime.now(timezone.utc)
    provisional_priors = build_provisional_priors(checkpoints, generated_at)
    now = generated_at.isoformat().replace("+00:00", "Z")
    snapshot: Dict[str, Any] = {
        "contract_version": "performance-learning-v1",
        "execution_id": execution_id,
        "generated_at": now,
        "source_root": str(root.resolve()),
        "status": "ACTIVE_PRIORS_READY" if priors else "NO_DURABLE_LESSON",
        "promotion_status": (
            "DURABLE_AND_PROVISIONAL_READY"
            if priors and provisional_priors
            else "DURABLE_PRIORS_READY"
            if priors
            else "PROVISIONAL_PRIORS_READY"
            if provisional_priors
            else "NO_PROMOTION"
        ),
        "accepted_checkpoint_count": len(checkpoints),
        "learning_context_version": "learning-context-v1",
        "learning_context_completeness": {
            "complete": sum(
                row.get("learning_context_status") == "COMPLETE"
                for row in checkpoints
            ),
            "partial": sum(
                row.get("learning_context_status") != "COMPLETE"
                for row in checkpoints
            ),
            "with_publication_run_id": sum(
                bool(str(row.get("publication_run_id") or "").strip())
                for row in checkpoints
            ),
            "with_cluster_id": sum(
                bool(str(row.get("cluster_id") or "").strip())
                for row in checkpoints
            ),
            "with_intent_key": sum(
                bool(str(row.get("intent_key") or "").strip())
                for row in checkpoints
            ),
            "with_trend_class": sum(
                bool(str(row.get("trend_class") or "").strip())
                for row in checkpoints
            ),
            "with_outcome_lane": sum(
                bool(str(row.get("outcome_lane") or "").strip())
                for row in checkpoints
            ),
        },
        "accepted_by_level": {
            level: sum(row["learning_level"] == level for row in checkpoints)
            for level in sorted(set(CHECKPOINT_LEVEL.values()))
        },
        "rejected_checkpoint_count": len(rejected),
        "rejected_by_reason": {
            reason: sum(row["reason"] == reason for row in rejected)
            for reason in sorted({row["reason"] for row in rejected})
        },
        "checkpoints": checkpoints,
        "rejected_inputs": rejected,
        "proposed_provisional_priors": provisional_priors,
        "proposed_priors": priors,
        "provisional_policy": {
            "promotion_check_cadence_hours": 48,
            "maximum_evidence_age_days": PROVISIONAL_EVIDENCE_MAX_AGE_DAYS,
            "ttl_days": PROVISIONAL_TTL_DAYS,
            "rules": PROVISIONAL_RULES,
            "combined_selection_adjustment_bounds": [-3, 3],
            "eligibility_override_allowed": False,
        },
        "promotion_policy": {
            "minimum_d28_articles": PROMOTION_MIN_ARTICLES,
            "minimum_publication_runs": PROMOTION_MIN_RUNS,
            "minimum_directional_agreement": 0.67,
            "selection_adjustment_bounds": [-3, 3],
            "eligibility_override_allowed": False,
            "realtime_hot_override_allowed": False,
        },
    }
    snapshot["snapshot_fingerprint"] = fingerprint(snapshot)

    active: Dict[str, Any] = {
        "contract_version": "performance-learning-v1",
        "generated_at": now,
        "source_execution_id": execution_id,
        "source_snapshot_fingerprint": snapshot["snapshot_fingerprint"],
        "status": "ACTIVE" if priors else "NO_DURABLE_LESSON",
        "priors": priors,
        "hard_boundaries": {
            "applies_after_eligibility": True,
            "maximum_absolute_adjustment": 3,
            "may_change_raw_score": False,
            "may_bypass_veto": False,
            "may_create_realtime_hot": False,
        },
    }
    active["snapshot_fingerprint"] = fingerprint(active)
    return snapshot, active


def build_provisional_artifact(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    priors = list(snapshot.get("proposed_provisional_priors") or [])
    artifact: Dict[str, Any] = {
        "contract_version": "performance-learning-provisional-v1",
        "generated_at": snapshot.get("generated_at"),
        "source_execution_id": snapshot.get("execution_id"),
        "source_snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "status": "ACTIVE" if priors else "NO_PROVISIONAL_LESSON",
        "priors": priors,
        "hard_boundaries": {
            "applies_after_eligibility": True,
            "maximum_absolute_adjustment": 2,
            "combined_with_durable_maximum_absolute_adjustment": 3,
            "may_change_raw_score": False,
            "may_bypass_veto": False,
            "may_create_realtime_hot": False,
        },
    }
    artifact["snapshot_fingerprint"] = fingerprint(artifact)
    return artifact


def valid_active_pointer(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    claimed_fingerprint = str(payload.get("snapshot_fingerprint") or "").strip()
    if not claimed_fingerprint or claimed_fingerprint != fingerprint(payload):
        return False
    if payload.get("contract_version") != "performance-learning-v1":
        return False
    priors = payload.get("priors")
    if not isinstance(priors, list):
        return False
    status = payload.get("status")
    if status == "ACTIVE":
        return len(priors) > 0
    if status == "NO_DURABLE_LESSON":
        return len(priors) == 0
    return False


def preserve_previous_active(
    snapshot: Dict[str, Any],
    proposed_active: Dict[str, Any],
    previous_active: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if proposed_active.get("priors") or not valid_active_pointer(previous_active):
        snapshot["active_pointer_action"] = (
            "REPLACED_WITH_NEW_DURABLE_PRIORS"
            if proposed_active.get("priors")
            else "WROTE_EMPTY_INITIAL_STATE"
        )
        snapshot["snapshot_fingerprint"] = fingerprint(snapshot)
        proposed_active["source_snapshot_fingerprint"] = snapshot["snapshot_fingerprint"]
        proposed_active["snapshot_fingerprint"] = fingerprint(proposed_active)
        return snapshot, proposed_active

    snapshot["active_pointer_action"] = "PRESERVED_PREVIOUS_ACTIVE"
    snapshot["preserved_active_fingerprint"] = previous_active["snapshot_fingerprint"]
    snapshot["snapshot_fingerprint"] = fingerprint(snapshot)
    return snapshot, previous_active


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--active-output", required=True, type=Path)
    parser.add_argument("--provisional-output", type=Path)
    args = parser.parse_args(argv)
    snapshot, active = build_snapshot(args.root, args.execution_id)
    previous_active: Any = None
    if args.active_output.exists():
        try:
            previous_active = load_json(args.active_output)
        except (OSError, json.JSONDecodeError):
            previous_active = None
    snapshot, active = preserve_previous_active(snapshot, active, previous_active)
    provisional = build_provisional_artifact(snapshot)
    write_json(args.output, snapshot)
    write_json(args.active_output, active)
    if args.provisional_output is not None:
        write_json(args.provisional_output, provisional)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Dynamic, idempotent VERTU content checkpoint runtime.

The module is intentionally split into pure discovery/planning functions and a
read-only Google metrics provider.  Production writes are limited to immutable
local evidence; Feishu reconciliation is handled by the separate audited
``vertu_content_monitor_base_handoff.py`` boundary.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from vertu_content_traffic_gate import classify_72h
except ModuleNotFoundError:  # imported as scripts.vertu_content_monitor_runtime in tests
    from scripts.vertu_content_traffic_gate import classify_72h


UTC = dt.timezone.utc
HKT = dt.timezone(dt.timedelta(hours=8))
CHECKPOINT_OFFSETS = {
    "24h": dt.timedelta(hours=24),
    "72h": dt.timedelta(hours=72),
    "7d": dt.timedelta(days=7),
    "28d": dt.timedelta(days=28),
}
REQUIRED_RUN_ARTIFACTS = (
    "handoff.json",
    "publish-result.json",
    "live-verification.json",
    "performance-plan.json",
)
LEGACY_CUTOFF = dt.date(2026, 7, 11)


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_datetime(value: Any, default_tz: dt.tzinfo = UTC) -> Optional[dt.datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed.astimezone(UTC)


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def url_path(url: str) -> str:
    return urllib.parse.urlparse(url).path.rstrip("/") or "/"


def slug_from_url(url: str) -> str:
    return url_path(url).split("/")[-1]


def date_from_run_dir(path: Path) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(path.parent.name)
    except ValueError:
        return None


@dataclass(frozen=True)
class Article:
    publication_run_id: str
    article_key: str
    candidate_id: Optional[str]
    slug: str
    title: Optional[str]
    canonical_url: str
    section: str
    document_id: Optional[str]
    source_rev: Optional[str]
    published_at_utc: str
    run_dir: str
    cluster_id: Optional[str]
    intent_key: Optional[str]
    outcome_lane: Optional[str]
    trend_class: Optional[str]
    portfolio_bucket: Optional[str]
    live_verdict: str


def _candidate_context(run_dir: Path) -> Dict[str, Dict[str, Any]]:
    cluster_payload = load_json(run_dir / "cluster-support.json", {}) or {}
    clusters = {
        str(row.get("candidate_id") or ""): row.get("cluster")
        for row in cluster_payload.get("candidates") or []
        if isinstance(row, dict)
    }
    scores = load_json(run_dir / "candidate-scores.json", {}) or {}
    run_summary = load_json(run_dir / "run-summary.json", {}) or {}
    published_slugs = {
        str(row.get("slug") or "").strip()
        for row in run_summary.get("articles") or []
        if isinstance(row, dict) and str(row.get("slug") or "").strip()
    }
    selected_rows = scores.get("selected") or []
    if not selected_rows and published_slugs:
        demand = load_json(run_dir / "traffic-demand.json", {}) or {}
        selected_rows = [
            row
            for row in demand.get("candidates") or demand.get("selected") or []
            if isinstance(row, dict)
            and str(row.get("slug") or "").strip() in published_slugs
        ]
    context: Dict[str, Dict[str, Any]] = {}
    for row in selected_rows:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "").strip()
        if not slug:
            continue
        candidate_id = str(row.get("candidate_id") or "").strip()
        forecast = row.get("predraft_discover_forecast") or {}
        context[slug] = {
            "candidate_id": candidate_id or None,
            "cluster_id": row.get("cluster_id")
            or clusters.get(candidate_id)
            or row.get("audience_fit_lane")
            or forecast.get("historical_cluster"),
            "intent_key": row.get("intent_key")
            or row.get("decision_intent")
            or row.get("query_intent_boundary"),
            "outcome_lane": row.get("outcome_lane"),
            "trend_class": row.get("trend_class"),
            "portfolio_bucket": row.get("portfolio_bucket"),
        }
    return context


def _live_by_slug(run_dir: Path) -> Dict[str, Dict[str, Any]]:
    payload = load_json(run_dir / "live-verification.json", {}) or {}
    result: Dict[str, Dict[str, Any]] = {}
    for row in payload.get("results") or []:
        if not isinstance(row, dict) or not row.get("url"):
            continue
        result[slug_from_url(str(row["url"]))] = row
    return result


def _live_pass(row: Dict[str, Any]) -> bool:
    required = (
        "canonical_pass",
        "og_image_pass",
        "visible_author_pass",
        "blogposting_author_pass",
        "max_image_preview_large_pass",
        "non_news_pass",
        "rendered_link_reconciliation_pass",
    )
    return row.get("status") == 200 and all(row.get(field) is not False for field in required)


def discover_articles(
    root: Path,
    now: dt.datetime,
    window_days: int = 35,
    legacy_cutoff: dt.date = LEGACY_CUTOFF,
) -> Dict[str, Any]:
    """Discover live-verified articles from current local publication packages."""

    start_date = now.astimezone(HKT).date() - dt.timedelta(days=window_days)
    articles: List[Article] = []
    legacy_exceptions: List[Dict[str, Any]] = []
    blocked_runs: List[Dict[str, Any]] = []
    reconciled_publication_runs: List[Dict[str, Any]] = []
    scanned_runs = 0

    for run_dir in sorted(root.glob("20??-??-??/*")):
        if not run_dir.is_dir():
            continue
        run_date = date_from_run_dir(run_dir)
        if run_date is None or run_date < start_date:
            continue
        handoff = load_json(run_dir / "handoff.json", {}) or {}
        publish = load_json(run_dir / "publish-result.json", {}) or {}
        run_summary = load_json(run_dir / "run-summary.json", {}) or {}
        live_payload = load_json(run_dir / "live-verification.json", {}) or {}
        legacy_run = load_json(run_dir / "run.json", {}) or {}
        legacy_publication = load_json(run_dir / "publication.json", {}) or {}
        handoff_state = str(handoff.get("state") or "").upper()
        live_rows = live_payload.get("results") or []
        reconciled_published = bool(
            (publish.get("articles") or publish.get("canonical_urls"))
            and (
                publish.get("published_at")
                or publish.get("published_at_utc")
                or any(
                    isinstance(row, dict)
                    and (row.get("publishedAt") or row.get("published_at"))
                    for row in publish.get("articles") or []
                )
            )
            and str(run_summary.get("status") or "").upper() == "SUCCESS"
            and live_rows
            and all(isinstance(row, dict) and _live_pass(row) for row in live_rows)
        )
        if handoff_state != "PUBLISHED" and not reconciled_published:
            legacy_published_marker = bool(
                run_date <= legacy_cutoff
                and (
                    str(legacy_run.get("state") or legacy_run.get("status") or "").upper()
                    == "PUBLISHED"
                    or str(
                        legacy_publication.get("state")
                        or legacy_publication.get("status")
                        or ""
                    ).upper()
                    == "PUBLISHED"
                )
            )
            if legacy_published_marker:
                scanned_runs += 1
                legacy_exceptions.append(
                    {
                        "run": str(run_dir.relative_to(root)),
                        "missing": [
                            name for name in REQUIRED_RUN_ARTIFACTS if not (run_dir / name).exists()
                        ],
                        "status": "LEGACY_EVIDENCE_EXCEPTION",
                        "legacy_publication_marker": True,
                        "policy": "exclude_from_checkpoint_and_learning",
                    }
                )
            continue
        scanned_runs += 1
        missing = [name for name in REQUIRED_RUN_ARTIFACTS if not (run_dir / name).exists()]
        if reconciled_published and "handoff.json" in missing:
            missing.remove("handoff.json")
        if reconciled_published and handoff_state != "PUBLISHED":
            reconciled_publication_runs.append(
                {
                    "run": str(run_dir.relative_to(root)),
                    "status": "PUBLISHED_RECONCILED",
                    "handoff_state": handoff_state or "MISSING",
                    "evidence": [
                        "publish-result.json:published_at+articles",
                        "run-summary.json:SUCCESS",
                        "live-verification.json:all_results_PASS",
                    ],
                    "repair_required": "reconcile handoff state without changing article content",
                }
            )
        if missing:
            record = {
                "run": str(run_dir.relative_to(root)),
                "missing": missing,
                "policy": "exclude_from_checkpoint_and_learning",
            }
            if run_date <= legacy_cutoff:
                record["status"] = "LEGACY_EVIDENCE_EXCEPTION"
                legacy_exceptions.append(record)
            else:
                record["status"] = "SOURCE_BLOCKED"
                blocked_runs.append(record)
            continue

        run_id = str(
            handoff.get("run_id")
            or handoff.get("execution_id")
            or publish.get("run_id")
            or run_summary.get("run_id")
            or run_summary.get("execution_id")
            or run_dir.name
        ).strip()
        default_published = parse_datetime(
            handoff.get("published_at")
            or handoff.get("published_at_utc")
            or publish.get("published_at")
            or publish.get("published_at_utc")
        )
        context = _candidate_context(run_dir)
        live = _live_by_slug(run_dir)
        by_slug: Dict[str, Dict[str, Any]] = {}

        for row in publish.get("articles") or []:
            if not isinstance(row, dict):
                continue
            slug = str(row.get("slug") or "").strip()
            if slug:
                by_slug[slug] = dict(row)
        for row in handoff.get("articles") or []:
            if not isinstance(row, dict):
                continue
            slug = str(row.get("slug") or "").strip()
            if slug:
                by_slug.setdefault(slug, {}).update(
                    {key: value for key, value in row.items() if value not in (None, "")}
                )

        # Early canonical runs stored verified URLs and aggregate publish evidence
        # without expanding an `articles` array. Accept that shape only when the
        # normal run-level artifact and exact per-URL live gates above have already
        # passed. This restores monitoring eligibility without inventing document
        # IDs, revisions, timestamps or live verdicts.
        if not by_slug:
            for canonical in publish.get("urls") or []:
                if not isinstance(canonical, str) or not canonical.strip():
                    continue
                slug = slug_from_url(canonical)
                if not slug:
                    continue
                path_parts = url_path(canonical).split("/")
                section = path_parts[1] if len(path_parts) > 1 else "guides"
                by_slug[slug] = {
                    "slug": slug,
                    "canonical_url": canonical,
                    "section": section,
                    "publishedAt": publish.get("published_at")
                    or publish.get("published_at_utc"),
                }

        for slug, row in sorted(by_slug.items()):
            canonical = str(
                row.get("canonical_url")
                or row.get("url")
                or f"https://vertu.com/{row.get('section') or 'guides'}/{slug}"
            ).strip()
            section = str(row.get("section") or url_path(canonical).split("/")[1]).strip()
            if section.lower() == "news" or url_path(canonical).startswith("/news/"):
                continue
            published = parse_datetime(
                row.get("publishedAt")
                or row.get("published_at")
                or row.get("published_at_utc")
            ) or default_published
            live_row = live.get(slug, {})
            if published is None or not live_row or not _live_pass(live_row):
                blocked_runs.append(
                    {
                        "run": str(run_dir.relative_to(root)),
                        "article_key": slug,
                        "status": "SOURCE_BLOCKED",
                        "reason": "Missing publication timestamp or exact live-verification PASS",
                    }
                )
                continue
            selected = context.get(slug, {})
            articles.append(
                Article(
                    publication_run_id=run_id,
                    article_key=slug,
                    candidate_id=selected.get("candidate_id"),
                    slug=slug,
                    title=row.get("title"),
                    canonical_url=canonical,
                    section=section,
                    document_id=row.get("document_id") or row.get("_id"),
                    source_rev=row.get("source_rev") or row.get("_rev"),
                    published_at_utc=iso_utc(published),
                    run_dir=str(run_dir),
                    cluster_id=selected.get("cluster_id"),
                    intent_key=selected.get("intent_key"),
                    outcome_lane=selected.get("outcome_lane"),
                    trend_class=selected.get("trend_class"),
                    portfolio_bucket=selected.get("portfolio_bucket"),
                    live_verdict="PASS",
                )
            )

    deduplicated: Dict[Tuple[str, str], Article] = {}
    for article in articles:
        deduplicated[(article.publication_run_id, article.article_key)] = article
    return {
        "contract_version": "vertu-monitor-runtime-v1",
        "generated_at": iso_utc(now),
        "window_days": window_days,
        "window_start_date": start_date.isoformat(),
        "published_runs_scanned": scanned_runs,
        "articles": [asdict(row) for row in deduplicated.values()],
        "legacy_exceptions": legacy_exceptions,
        "blocked_runs": blocked_runs,
        "reconciled_publication_runs": reconciled_publication_runs,
    }


def checkpoint_attempts(article: Dict[str, Any], checkpoint: str) -> List[Dict[str, Any]]:
    performance_dir = Path(article["run_dir"]) / "performance" / article["slug"]
    result = []
    for path in performance_dir.glob("*.json") if performance_dir.exists() else []:
        if path.name != f"{checkpoint}.json" and not path.name.startswith(
            f"metrics-supplement-{checkpoint}-"
        ):
            continue
        payload = load_json(path, {}) or {}
        if payload.get("checkpoint") != checkpoint and path.name != f"{checkpoint}.json":
            continue
        executed = parse_datetime(payload.get("executed_at_utc") or payload.get("executed_at"))
        result.append(
            {
                "path": str(path),
                "executed_at": iso_utc(executed) if executed else None,
                "checkpoint_status": payload.get("checkpoint_status") or payload.get("status"),
                "data_maturity": payload.get("data_maturity"),
                "payload": payload,
            }
        )
    return sorted(result, key=lambda row: (row["executed_at"] or "", row["path"]))


def completed_attempt(attempts: Iterable[Dict[str, Any]], checkpoint: str) -> bool:
    for row in attempts:
        status = str(row.get("checkpoint_status") or "").upper()
        maturity = str(row.get("data_maturity") or "").upper()
        if status != "COMPLETED":
            continue
        if checkpoint == "24h" or maturity == "MATURE":
            return True
    return False


def build_due_plan(
    inventory: Dict[str, Any],
    now: dt.datetime,
    retry_after_hours: int = 12,
    max_jobs: int = 40,
) -> Dict[str, Any]:
    due: List[Dict[str, Any]] = []
    future: List[dt.datetime] = []
    for article in inventory.get("articles") or []:
        published = parse_datetime(article.get("published_at_utc"))
        if published is None:
            continue
        for checkpoint, offset in CHECKPOINT_OFFSETS.items():
            due_at = published + offset
            attempts = checkpoint_attempts(article, checkpoint)
            if completed_attempt(attempts, checkpoint):
                continue
            if due_at > now:
                future.append(due_at)
                continue
            latest = attempts[-1] if attempts else None
            latest_executed = parse_datetime(latest.get("executed_at")) if latest else None
            if latest_executed and latest_executed + dt.timedelta(hours=retry_after_hours) > now:
                future.append(latest_executed + dt.timedelta(hours=retry_after_hours))
                continue
            due.append(
                {
                    "deterministic_id": (
                        f"{article['publication_run_id']}:{article['article_key']}:{checkpoint}"
                    ),
                    "checkpoint": checkpoint,
                    "due_at": iso_utc(due_at),
                    "attempt_count": len(attempts),
                    "retry_of": latest.get("path") if latest else None,
                    "article": article,
                }
            )
    priority = {"24h": 0, "72h": 1, "7d": 2, "28d": 3}
    due = sorted(
        due,
        key=lambda row: (
            priority[row["checkpoint"]],
            -parse_datetime(row["due_at"]).timestamp(),
            row["deterministic_id"],
        ),
    )
    available_checkpoints = [
        checkpoint
        for checkpoint in ("24h", "72h", "7d", "28d")
        if any(row["checkpoint"] == checkpoint for row in due)
    ]
    execution_queue: List[Dict[str, Any]] = []
    if max_jobs > 0 and available_checkpoints:
        base_quota = max_jobs // len(available_checkpoints)
        remainder = max_jobs % len(available_checkpoints)
        for index, checkpoint in enumerate(available_checkpoints):
            quota = base_quota + (1 if index < remainder else 0)
            lane_rows = [row for row in due if row["checkpoint"] == checkpoint]
            execution_queue.extend(lane_rows[:quota])
        selected_ids = {row["deterministic_id"] for row in execution_queue}
        if len(execution_queue) < max_jobs:
            execution_queue.extend(
                row
                for row in due
                if row["deterministic_id"] not in selected_ids
            )
            execution_queue = execution_queue[:max_jobs]
    return {
        "contract_version": "vertu-monitor-due-plan-v1",
        "generated_at": iso_utc(now),
        "due_count": len(due),
        "due": due,
        "execution_queue_count": len(execution_queue),
        "execution_queue": execution_queue,
        "max_jobs_per_execution": max_jobs,
        "next_due_at": iso_utc(min(future)) if future else None,
        "legacy_exception_count": len(inventory.get("legacy_exceptions") or []),
        "blocked_run_count": len(inventory.get("blocked_runs") or []),
        "reconciled_publication_run_count": len(
            inventory.get("reconciled_publication_runs") or []
        ),
    }


def load_env(project: Path) -> None:
    env_path = project / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


class GoogleMetricProvider:
    """Read-only GSC/GA4 provider with per-article observation windows."""

    def __init__(self, project: Path, observed_at: dt.datetime):
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        load_env(project)
        service_path = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON_PATH"]
        if not os.path.isabs(service_path):
            service_path = str(project / service_path)
        credentials = service_account.Credentials.from_service_account_file(
            service_path,
            scopes=[
                "https://www.googleapis.com/auth/webmasters.readonly",
                "https://www.googleapis.com/auth/analytics.readonly",
            ],
        )
        self.gsc = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
        # The local automation runs behind an HTTPS proxy.  The default gRPC
        # transport does not honour that route reliably and previously turned
        # reachable GA4 endpoints into false SOURCE_BLOCKED results.  REST is
        # an official transport and follows the same authenticated read-only
        # Data API contract through the configured HTTPS path.
        ga4_transport = os.environ.get("VERTU_GA4_TRANSPORT", "rest").strip().lower()
        if ga4_transport not in {"rest", "grpc", "grpc_asyncio"}:
            raise ValueError("VERTU_GA4_TRANSPORT must be rest, grpc or grpc_asyncio")
        self.ga4 = BetaAnalyticsDataClient(
            credentials=credentials,
            transport=ga4_transport,
        )
        self.site_url = os.environ["GSC_SITE_URL"]
        self.property_id = os.environ["GA4_PROPERTY_ID"]
        self.observed_at = observed_at
        self._latest_gsc_date: Optional[str] = None

    def _gsc_query(self, body: Dict[str, Any]) -> List[Dict[str, Any]]:
        return (
            self.gsc.searchanalytics()
            .query(siteUrl=self.site_url, body=body)
            .execute()
            .get("rows", [])
        )

    def latest_gsc_date(self) -> Optional[str]:
        if self._latest_gsc_date is None:
            rows = self._gsc_query(
                {
                    "startDate": (self.observed_at - dt.timedelta(days=30)).date().isoformat(),
                    "endDate": self.observed_at.date().isoformat(),
                    "dimensions": ["date"],
                    "rowLimit": 25000,
                }
            )
            self._latest_gsc_date = max(
                (row["keys"][0] for row in rows if row.get("keys")), default=None
            )
        return self._latest_gsc_date

    def gsc_metrics(self, article: Dict[str, Any], checkpoint: str) -> Dict[str, Any]:
        published = parse_datetime(article["published_at_utc"])
        assert published is not None
        end = published + CHECKPOINT_OFFSETS[checkpoint]
        latest = self.latest_gsc_date()
        required = end.date().isoformat()
        if not latest or latest < required:
            return {
                "status": "DATA_NOT_MATURE",
                "latest_metric_date": latest,
                "required_observation_through": required,
                "discover": {"clicks": None, "impressions": None, "ctr": None},
                "search": {
                    "clicks": None,
                    "impressions": None,
                    "ctr": None,
                    "average_position": None,
                    "queries": [],
                },
                "missing_values_policy": "null_not_zero",
            }
        start_date = published.date().isoformat()
        end_date = end.date().isoformat()
        page_filter = {
            "groupType": "and",
            "filters": [
                {
                    "dimension": "page",
                    "operator": "equals",
                    "expression": article["canonical_url"],
                }
            ],
        }
        common = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensionFilterGroups": [page_filter],
            "rowLimit": 25000,
        }
        search_rows = self._gsc_query({**common, "dimensions": ["page"]})
        query_rows = self._gsc_query({**common, "dimensions": ["query"]})
        discover_rows = self._gsc_query(
            {**common, "dimensions": ["page"], "type": "discover"}
        )
        search = search_rows[0] if search_rows else {}
        discover = discover_rows[0] if discover_rows else {}
        return {
            "status": "MATURE",
            "latest_metric_date": latest,
            "required_observation_through": required,
            "query_window": {"start": start_date, "end": end_date},
            "discover": {
                "clicks": discover.get("clicks"),
                "impressions": discover.get("impressions"),
                "ctr": discover.get("ctr"),
            },
            "search": {
                "clicks": search.get("clicks"),
                "impressions": search.get("impressions"),
                "ctr": search.get("ctr"),
                "average_position": search.get("position"),
                "queries": [
                    {
                        "query": row.get("keys", [None])[0],
                        "clicks": row.get("clicks"),
                        "impressions": row.get("impressions"),
                        "ctr": row.get("ctr"),
                        "average_position": row.get("position"),
                    }
                    for row in query_rows
                ],
            },
            "missing_values_policy": "null_not_zero",
        }

    def ga4_metrics(self, article: Dict[str, Any], checkpoint: str) -> Dict[str, Any]:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            Metric,
            RunReportRequest,
        )

        published = parse_datetime(article["published_at_utc"])
        assert published is not None
        end = published + CHECKPOINT_OFFSETS[checkpoint]
        start_local = published.astimezone(HKT)
        end_local = end.astimezone(HKT)
        path = url_path(article["canonical_url"])

        def report(dimension: str, metrics: Sequence[str]):
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name=dimension), Dimension(name="dateHourMinute")],
                metrics=[Metric(name=name) for name in metrics],
                date_ranges=[
                    DateRange(
                        start_date=start_local.date().isoformat(),
                        end_date=end_local.date().isoformat(),
                    )
                ],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name=dimension,
                        string_filter=Filter.StringFilter(
                            value=path,
                            match_type=Filter.StringFilter.MatchType.EXACT,
                        ),
                    )
                ),
                limit=250000,
            )
            return self.ga4.run_report(request).rows

        def in_window(row: Any) -> bool:
            minute = parse_datetime(
                dt.datetime.strptime(
                    row.dimension_values[1].value, "%Y%m%d%H%M"
                ).replace(tzinfo=HKT)
            )
            return minute is not None and published <= minute < end

        view_rows = [
            row for row in report("pagePath", ["screenPageViews"]) if in_window(row)
        ]
        metric_names = (
            "sessions",
            "engagedSessions",
            "userEngagementDuration",
            "activeUsers",
            "totalUsers",
            "newUsers",
        )
        entry_rows = [row for row in report("landingPage", metric_names) if in_window(row)]
        totals = [0.0] * len(metric_names)
        for row in entry_rows:
            for index, metric in enumerate(row.metric_values):
                totals[index] += float(metric.value or 0)
        sessions, engaged, duration, active, total, new = totals
        return {
            "status": "AVAILABLE_EXACT_WINDOW",
            "observed_at": iso_utc(self.observed_at),
            "property_timezone": "Asia/Hong_Kong",
            "window_utc": {"inclusive": iso_utc(published), "exclusive": iso_utc(end)},
            "dimensions": {"views": "pagePath", "entries": "landingPage"},
            "metrics": {
                "page_views": sum(int(float(row.metric_values[0].value or 0)) for row in view_rows),
                "sessions": int(sessions),
                "engaged_sessions": int(engaged),
                "engagement_rate": engaged / sessions if sessions else None,
                "user_engagement_duration_seconds": int(duration),
                "active_users": int(active),
                "total_users": int(total),
                "new_users": int(new),
                "average_engagement_time_seconds": duration / active if active else None,
                "returning_users": None,
                "returning_users_status": "NOT_DIRECTLY_AVAILABLE",
                "qualified_journeys": None,
                "qualified_journeys_status": "UNVERIFIED_EVENT_MAPPING",
            },
            "missing_values_policy": "null_not_zero",
        }


def diagnosis_for(checkpoint: str, maturity: str, gsc: Dict[str, Any], ga4: Dict[str, Any]) -> Dict[str, Any]:
    if maturity == "SOURCE_BLOCKED":
        return {
            "classification": "SOURCE_BLOCKED",
            "confidence": "LOW",
            "recommended_variable": None,
            "reason": "A mandatory GSC or GA4 source query failed; missing values remain null and the checkpoint is retryable.",
            "sample_gate": {"passed": False},
        }
    if checkpoint == "24h":
        return {
            "classification": "DELIVERY_OK",
            "confidence": "HIGH",
            "recommended_variable": None,
            "reason": "Live delivery passed; GA4 remains preliminary and GSC is not judged at 24 hours.",
        }
    if maturity != "MATURE":
        return {
            "classification": "DATA_NOT_MATURE",
            "confidence": "LOW",
            "recommended_variable": None,
            "reason": "The finalised GSC metric date does not cover the full checkpoint window.",
            "sample_gate": {"passed": False},
        }
    if checkpoint in {"72h", "7d"}:
        return classify_72h({"data_maturity": maturity, "gsc": gsc})

    search = gsc.get("search") or {}
    discover = gsc.get("discover") or {}
    search_impressions = float(search.get("impressions") or 0)
    discover_impressions = float(discover.get("impressions") or 0)
    search_clicks = float(search.get("clicks") or 0)
    discover_clicks = float(discover.get("clicks") or 0)
    engagement = (ga4.get("metrics") or {}).get("engagement_rate")
    total_clicks = search_clicks + discover_clicks
    if total_clicks >= 50 and (engagement is None or engagement >= 0.5):
        classification = "WINNER"
    elif search_clicks > 0 and discover_clicks == 0:
        classification = "SEARCH_BUILDER"
    elif total_clicks > 0:
        classification = "PROMISING"
    elif search_impressions >= 100 or discover_impressions >= 300:
        classification = "UNDERPERFORMER"
    else:
        classification = "INSUFFICIENT_DATA"
    return {
        "classification": classification,
        "confidence": "MEDIUM" if classification != "INSUFFICIENT_DATA" else "LOW",
        "recommended_variable": None,
        "reason": "D+28 deterministic portfolio classification from mature Search, Discover and available GA4 evidence.",
        "sample_gate": {
            "passed": search_impressions >= 100 or discover_impressions >= 300,
            "search_impressions": search_impressions,
            "discover_impressions": discover_impressions,
        },
    }


def execute_due_plan(
    plan: Dict[str, Any],
    provider: GoogleMetricProvider,
    execution_id: str,
    now: dt.datetime,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    jobs = plan.get("execution_queue") or plan.get("due") or []
    for job in jobs:
        article = job["article"]
        checkpoint = job["checkpoint"]
        try:
            ga4 = provider.ga4_metrics(article, checkpoint)
        except Exception as error:  # source failure must stay explicit
            ga4 = {"status": "SOURCE_BLOCKED", "error": str(error)[:500], "metrics": {}}
        if checkpoint == "24h":
            gsc = {
                "status": "NOT_DUE_AT_24H",
                "latest_metric_date": provider.latest_gsc_date(),
                "discover": {"clicks": None, "impressions": None, "ctr": None},
                "search": {
                    "clicks": None,
                    "impressions": None,
                    "ctr": None,
                    "average_position": None,
                    "queries": [],
                },
            }
            if ga4.get("status") == "SOURCE_BLOCKED":
                maturity = "SOURCE_BLOCKED"
                status = "SOURCE_BLOCKED"
            else:
                maturity = "PRELIMINARY"
                status = "COMPLETED"
        else:
            try:
                gsc = provider.gsc_metrics(article, checkpoint)
            except Exception as error:
                gsc = {
                    "status": "SOURCE_BLOCKED",
                    "error": str(error)[:500],
                    "discover": {"clicks": None, "impressions": None, "ctr": None},
                    "search": {
                        "clicks": None,
                        "impressions": None,
                        "ctr": None,
                        "average_position": None,
                        "queries": [],
                    },
                }
            if gsc.get("status") == "SOURCE_BLOCKED" or ga4.get("status") == "SOURCE_BLOCKED":
                maturity = "SOURCE_BLOCKED"
                status = "SOURCE_BLOCKED"
            else:
                maturity = "MATURE" if gsc.get("status") == "MATURE" else "DATA_NOT_MATURE"
                status = "COMPLETED" if maturity == "MATURE" else "DATA_NOT_MATURE"
        diagnosis = diagnosis_for(checkpoint, maturity, gsc, ga4)
        artifact = {
            "contract_version": "vertu-content-performance-checkpoint-v1",
            "deterministic_id": job["deterministic_id"],
            "run_id": execution_id,
            "publication_run_id": article["publication_run_id"],
            "article_key": article["article_key"],
            "checkpoint": checkpoint,
            "checkpoint_status": status,
            "executed_at_utc": iso_utc(now),
            "due_at": job["due_at"],
            "data_maturity": maturity,
            "publication": {
                "article_key": article["article_key"],
                "slug": article["slug"],
                "title": article.get("title"),
                "canonical_url": article["canonical_url"],
                "section": article["section"],
                "published_at_utc": article["published_at_utc"],
                "document_id": article.get("document_id"),
                "source_rev": article.get("source_rev"),
            },
            "cluster_id": article.get("cluster_id"),
            "intent_key": article.get("intent_key"),
            "outcome_lane": article.get("outcome_lane"),
            "trend_class": article.get("trend_class"),
            "portfolio_bucket": article.get("portfolio_bucket"),
            "ga4": ga4,
            "gsc": gsc,
            "diagnosis": diagnosis,
            "sanity_mutation_executed": False,
            "experiment_approval_status": "NOT_REQUESTED",
            "retry_of": job.get("retry_of"),
        }
        target_dir = Path(article["run_dir"]) / "performance" / article["slug"]
        if job.get("attempt_count", 0) == 0:
            target = target_dir / f"{checkpoint}.json"
        else:
            stamp = now.strftime("%Y%m%dT%H%M%SZ")
            target = target_dir / f"metrics-supplement-{checkpoint}-{stamp}.json"
        if target.exists():
            existing = load_json(target, {}) or {}
            if existing.get("deterministic_id") != artifact["deterministic_id"]:
                results.append(
                    {
                        "deterministic_id": job["deterministic_id"],
                        "status": "CONFLICTING_IMMUTABLE_ARTIFACT",
                        "path": str(target),
                    }
                )
                continue
        else:
            write_json(target, artifact)
        write_json(
            target_dir / "diagnosis.json",
            {
                "updated_at_utc": iso_utc(now),
                "latest_checkpoint_path": str(target),
                "latest_checkpoint": artifact,
                "sanity_mutation_executed": False,
                "experiment_approval_status": "MANUAL_REQUIRED",
            },
        )
        results.append(
            {
                "deterministic_id": job["deterministic_id"],
                "status": status,
                "classification": diagnosis.get("classification"),
                "path": str(target),
            }
        )
    return {
        "contract_version": "vertu-monitor-execution-v1",
        "execution_id": execution_id,
        "executed_at": iso_utc(now),
        "job_count": len(jobs),
        "result_count": len(results),
        "results": results,
        "sanity_mutations": 0,
        "experiments_auto_approved": 0,
        "base_handoff_state": "PENDING_SEPARATE_AUDITED_HANDOFF",
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--root", type=Path)
    parser.add_argument("--now")
    parser.add_argument("--window-days", type=int, default=35)
    parser.add_argument("--legacy-cutoff", default=LEGACY_CUTOFF.isoformat())
    parser.add_argument("--max-jobs", type=int, default=40)
    parser.add_argument("--execution-id")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    now = parse_datetime(args.now) if args.now else dt.datetime.now(UTC)
    if now is None:
        parser.error("--now must be an ISO-8601 datetime")
    root = args.root or args.project / "output/vertu-signals"
    inventory = discover_articles(
        root=root,
        now=now,
        window_days=args.window_days,
        legacy_cutoff=dt.date.fromisoformat(args.legacy_cutoff),
    )
    plan = build_due_plan(inventory, now, max_jobs=args.max_jobs)
    payload: Dict[str, Any] = {"inventory": inventory, "plan": plan}
    if args.execute:
        execution_id = args.execution_id or f"vertu-{now.strftime('%Y%m%dT%H%M%SZ')}"
        provider = GoogleMetricProvider(args.project, now)
        payload["execution"] = execute_due_plan(plan, provider, execution_id, now)
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "published_runs": inventory["published_runs_scanned"],
                "articles": len(inventory["articles"]),
                "legacy_exceptions": len(inventory["legacy_exceptions"]),
                "blocked_runs": len(inventory["blocked_runs"]),
                "reconciled_publication_runs": len(
                    inventory["reconciled_publication_runs"]
                ),
                "due": plan["due_count"],
                "executed": len((payload.get("execution") or {}).get("results") or []),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

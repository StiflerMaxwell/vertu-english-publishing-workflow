#!/usr/bin/env python3
"""Audited, idempotent Feishu Base handoff for content-monitor checkpoints.

The monitor runtime remains responsible for read-only metrics collection and
immutable local evidence.  This module turns one runtime execution into a
deterministic Base manifest, then optionally applies it after a canonical
automation-ledger start receipt has been established.

No Sanity mutation or experiment approval is performed here.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from vertu_content_monitor_runtime import CHECKPOINT_OFFSETS, HKT, UTC, load_json, parse_datetime, write_json
except ModuleNotFoundError:  # imported as scripts.* in tests
    from scripts.vertu_content_monitor_runtime import (
        CHECKPOINT_OFFSETS,
        HKT,
        UTC,
        load_json,
        parse_datetime,
        write_json,
    )


DEFAULT_SCHEMA_MAP = Path("output/vertu-signals/performance-monitor-base.json")
CHECKPOINT_LABELS = {"24h": "T+24h", "72h": "T+72h", "7d": "D+7", "28d": "D+28"}
DIAGNOSIS_MAP = {
    "SOURCE_BLOCKED": "TECHNICAL_BLOCKER",
    "NO_DEMAND": "UNDERPERFORMER",
    "CTR_PACKAGING": "PACKAGING_OPPORTUNITY",
    "RANKING_OPPORTUNITY": "SEARCH_INTENT_OPPORTUNITY",
    "ENGAGEMENT_GAP": "CONTENT_OPPORTUNITY",
    "EARLY_WINNER": "WINNER_WATCH",
    "SEARCH_BUILDER": "PROMISING",
}
ARTICLE_DIAGNOSIS_MAP = {
    "WINNER_WATCH": "PROMISING",
    "CONTENT_COVERAGE_OPPORTUNITY": "CONTENT_OPPORTUNITY",
}
ACTIONABLE = {
    "PACKAGING_OPPORTUNITY",
    "SEARCH_INTENT_OPPORTUNITY",
    "CONTENT_OPPORTUNITY",
    "DISCOVER_PACKAGING_OPPORTUNITY",
    "SEARCH_CTR_OPPORTUNITY",
    "CONTENT_COVERAGE_OPPORTUNITY",
    "UNDERPERFORMER",
}

PROJECTION_LIFECYCLE_FIELD = "证据有效性"
PROJECTION_REPLACED_BY_FIELD = "取代复盘ID"
PROJECTION_CURRENT = "CURRENT"
PROJECTION_SUPERSEDED = "SUPERSEDED"
PROJECTION_HISTORICAL = "HISTORICAL"
LARK_CLI_TIMEOUT_SECONDS = 45
PROJECTION_REQUIRED_FIELDS = {
    "复盘ID",
    "Article Key",
    "检查节点",
    "执行时间",
    "数据成熟度",
    "源状态",
    PROJECTION_LIFECYCLE_FIELD,
    PROJECTION_REPLACED_BY_FIELD,
}


class BaseHandoffError(RuntimeError):
    pass


def _first(mapping: Dict[str, Any], paths: Iterable[Sequence[str]]) -> Any:
    for path in paths:
        value: Any = mapping
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value not in (None, ""):
            return value
    return None


def _hkt_text(value: Any) -> Optional[str]:
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    return parsed.astimezone(HKT).strftime("%Y-%m-%d %H:%M:%S")


def _date_text(value: Any) -> Optional[str]:
    if not value:
        return None
    text = str(value)
    parsed = parse_datetime(text)
    if parsed is not None:
        return parsed.astimezone(HKT).strftime("%Y-%m-%d")
    try:
        return dt.date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _omit_none(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in fields.items() if value is not None}


def _cell_scalar(value: Any) -> Any:
    """Normalise lark-cli single-select readback without touching links."""
    if isinstance(value, list) and len(value) == 1 and not isinstance(value[0], dict):
        return value[0]
    return value


def validate_audit_receipt(path: Path) -> Dict[str, Any]:
    payload = load_json(path, {}) or {}
    record_id = _first(
        payload,
        (
            ("record_id",),
            ("recordId",),
            ("base_audit", "record_id"),
            ("ledger", "record_id"),
        ),
    )
    state = str(
        _first(
            payload,
            (
                ("status",),
                ("state",),
                ("base_audit", "status"),
                ("ledger", "status"),
            ),
        )
        or ""
    ).upper()
    execution_id = _first(
        payload,
        (
            ("execution_id",),
            ("执行ID",),
            ("base_audit", "execution_id"),
            ("ledger", "execution_id"),
        ),
    )
    if not record_id or not execution_id or state not in {"运行中", "RUNNING"}:
        raise BaseHandoffError(
            "Canonical Base start-ledger receipt is missing execution identity or is not RUNNING/运行中"
        )
    return {
        "record_id": str(record_id),
        "execution_id": str(execution_id),
        "status": state,
        "path": str(path),
    }


def checkpoint_source_complete(artifact: Dict[str, Any]) -> bool:
    checkpoint = str(artifact.get("checkpoint") or "")
    status = str(artifact.get("checkpoint_status") or "").upper()
    maturity = str(artifact.get("data_maturity") or "").upper()
    if status != "COMPLETED":
        return False
    if str((artifact.get("ga4") or {}).get("status") or "").upper() == "SOURCE_BLOCKED":
        return False
    if checkpoint == "24h":
        return maturity == "PRELIMINARY"
    return maturity == "MATURE" and str(
        (artifact.get("gsc") or {}).get("status") or ""
    ).upper() == "MATURE"


def checkpoint_learning_eligible(artifact: Dict[str, Any]) -> bool:
    return (
        checkpoint_source_complete(artifact)
        and str(artifact.get("checkpoint") or "") in {"72h", "7d", "28d"}
        and str(artifact.get("data_maturity") or "").upper() == "MATURE"
    )


def checkpoint_review_id(artifact: Dict[str, Any]) -> str:
    base = str(artifact.get("deterministic_id") or "").strip()
    if not base:
        raise BaseHandoffError("Checkpoint artifact has no deterministic_id")
    if not artifact.get("retry_of"):
        return base
    executed = parse_datetime(artifact.get("executed_at_utc") or artifact.get("executed_at"))
    if executed is None:
        raise BaseHandoffError("Retry checkpoint has no executed_at timestamp")
    return f"{base}:retry:{executed.strftime('%Y%m%dT%H%M%SZ')}"


def _diagnosis(artifact: Dict[str, Any]) -> str:
    raw = str((artifact.get("diagnosis") or {}).get("classification") or "NO_MATURE_SIGNAL")
    return DIAGNOSIS_MAP.get(raw, raw)


def _checkpoint_cutoff(artifact: Dict[str, Any]) -> Optional[str]:
    latest = _first(
        artifact,
        (
            ("gsc", "latest_metric_date"),
            ("ga4", "observed_at"),
            ("executed_at_utc",),
        ),
    )
    return _date_text(latest)


def checkpoint_fields(
    artifact: Dict[str, Any],
    evidence_path: Path,
    article_record_id: str,
    source_rev_field: Optional[str] = None,
) -> Dict[str, Any]:
    checkpoint = str(artifact["checkpoint"])
    publication = artifact.get("publication") or {}
    gsc = artifact.get("gsc") or {}
    search = gsc.get("search") or {}
    discover = gsc.get("discover") or {}
    ga4 = (artifact.get("ga4") or {}).get("metrics") or {}
    diagnosis = artifact.get("diagnosis") or {}
    raw_classification = str(diagnosis.get("classification") or "NO_MATURE_SIGNAL")
    reason = str(diagnosis.get("reason") or "").strip()
    # A retry is still the same logical checkpoint.  Its exact retry identity
    # is carried by 复盘ID; changing the node label would prevent deterministic
    # CURRENT/SUPERSEDED projection for the original checkpoint.
    label = CHECKPOINT_LABELS[checkpoint]
    suggested_action = "保持不变"
    mapped_diagnosis = _diagnosis(artifact)
    if str(artifact.get("data_maturity") or "").upper() in {
        "DATA_NOT_MATURE",
        "SOURCE_BLOCKED",
    }:
        suggested_action = "等待数据"
    elif mapped_diagnosis in {"PACKAGING_OPPORTUNITY", "SEARCH_CTR_OPPORTUNITY"}:
        suggested_action = "标题调整"
    elif mapped_diagnosis == "DISCOVER_PACKAGING_OPPORTUNITY":
        suggested_action = "首图调整"
    elif mapped_diagnosis in {
        "SEARCH_INTENT_OPPORTUNITY",
        "CONTENT_OPPORTUNITY",
        "CONTENT_COVERAGE_OPPORTUNITY",
    }:
        suggested_action = "正文扩充"
    fields = {
        "复盘ID": checkpoint_review_id(artifact),
        "Article Key": artifact.get("article_key"),
        "关联文章": [{"id": article_record_id}],
        "文章URL": publication.get("canonical_url"),
        "检查节点": label,
        "执行时间": _hkt_text(artifact.get("executed_at_utc")),
        "数据截止日期": _checkpoint_cutoff(artifact),
        "数据成熟度": artifact.get("data_maturity"),
        "源状态": (
            f"GA4={(artifact.get('ga4') or {}).get('status')};"
            f"GSC={(artifact.get('gsc') or {}).get('status')}"
        ),
        "Search Clicks": search.get("clicks"),
        "Search Impressions": search.get("impressions"),
        "Search CTR": search.get("ctr"),
        "Search Position": search.get("average_position"),
        "Discover Clicks": discover.get("clicks"),
        "Discover Impressions": discover.get("impressions"),
        "Discover CTR": discover.get("ctr"),
        "GA4 Views": ga4.get("page_views"),
        "GA4 Sessions": ga4.get("sessions"),
        "GA4 Engaged Sessions": ga4.get("engaged_sessions"),
        "GA4 Engagement Rate": ga4.get("engagement_rate"),
        "GA4 Avg Engagement Sec": ga4.get("average_engagement_time_seconds"),
        "Qualified Journeys": ga4.get("qualified_journeys"),
        "达到样本门槛": bool((diagnosis.get("sample_gate") or {}).get("passed", False)),
        "诊断": mapped_diagnosis,
        "置信度": diagnosis.get("confidence") or "LOW",
        "结论": f"{raw_classification}: {reason}".strip(),
        "建议动作": suggested_action,
        "证据路径": str(evidence_path),
    }
    if source_rev_field:
        fields[source_rev_field] = publication.get("source_rev")
    return _omit_none(fields)


def _content_review_action(artifact: Dict[str, Any]) -> str:
    diagnosis = _diagnosis(artifact)
    maturity = str(artifact.get("data_maturity") or "").upper()
    if maturity == "SOURCE_BLOCKED":
        return "技术修复"
    if maturity == "DATA_NOT_MATURE":
        return "等待数据"
    if diagnosis in {"PACKAGING_OPPORTUNITY", "SEARCH_CTR_OPPORTUNITY"}:
        return "标题/Meta"
    if diagnosis == "DISCOVER_PACKAGING_OPPORTUNITY":
        return "首图"
    if diagnosis in {
        "SEARCH_INTENT_OPPORTUNITY",
        "CONTENT_OPPORTUNITY",
        "CONTENT_COVERAGE_OPPORTUNITY",
    }:
        return "正文扩充"
    return "保持不变"


def content_review_fields(
    artifact: Dict[str, Any],
    evidence_path: Path,
    article_record_id: str,
    checkpoint_record_id: str,
    qa_record: Optional[Dict[str, Any]],
    base_token: str,
    checkpoint_table_id: str,
) -> Dict[str, Any]:
    publication = artifact.get("publication") or {}
    gsc = artifact.get("gsc") or {}
    search = gsc.get("search") or {}
    discover = gsc.get("discover") or {}
    ga4_payload = artifact.get("ga4") or {}
    ga4 = ga4_payload.get("metrics") or {}
    diagnosis = artifact.get("diagnosis") or {}
    raw_classification = str(diagnosis.get("classification") or "NO_MATURE_SIGNAL")
    checkpoint = str(artifact.get("checkpoint") or "")
    published = parse_datetime(publication.get("published_at_utc"))
    next_checkpoint = None
    if published is not None:
        next_checkpoint = {
            "24h": published + CHECKPOINT_OFFSETS["72h"],
            "72h": published + CHECKPOINT_OFFSETS["7d"],
            "7d": published + CHECKPOINT_OFFSETS["28d"],
        }.get(checkpoint)
    maturity = str(artifact.get("data_maturity") or "").upper()
    state = "待观察"
    if maturity in {"DATA_NOT_MATURE", "SOURCE_BLOCKED"}:
        state = "数据未成熟"
    elif _diagnosis(artifact) in ACTIONABLE:
        state = "待优化"
    elif checkpoint == "28d":
        state = "完成"
    elif _diagnosis(artifact) in {"WINNER", "WINNER_WATCH", "DELIVERY_OK"}:
        state = "保持"
    qa_fields = (qa_record or {}).get("fields") or {}
    qa_run_id = qa_fields.get("QA Run ID")
    conclusion = f"{raw_classification}: {str(diagnosis.get('reason') or '').strip()}".strip()
    if qa_record is None:
        conclusion += " | QA_LINK_UNAVAILABLE for exact Sanity Doc ID + Source Rev"
    query_rows = search.get("queries") or []
    fields = {
        "复盘ID": checkpoint_review_id(artifact),
        "Article Key": artifact.get("article_key"),
        "关联文章": [{"id": article_record_id}],
        "QA Run ID": qa_run_id,
        "关联 QA Run": [{"id": qa_record["record_id"]}] if qa_record else None,
        "文章 URL": publication.get("canonical_url"),
        "文章标题": publication.get("title"),
        "记录来源": "性能监控",
        "监控运行ID": artifact.get("run_id"),
        "表现监控记录ID": checkpoint_record_id,
        "源 Base": base_token,
        "源 Table ID": checkpoint_table_id,
        "源 Record ID": checkpoint_record_id,
        "复盘节点": CHECKPOINT_LABELS.get(checkpoint),
        "发布日期": _hkt_text(publication.get("published_at_utc")),
        "观察日期": _hkt_text(artifact.get("executed_at_utc")),
        "GSC最新日期": _date_text(gsc.get("latest_metric_date")),
        "GA4最新日期": _date_text(ga4_payload.get("observed_at")),
        "数据成熟度": artifact.get("data_maturity"),
        "GSC Search Clicks": search.get("clicks"),
        "GSC Search Impressions": search.get("impressions"),
        "GSC Search CTR": search.get("ctr"),
        "GSC Search Position": search.get("average_position"),
        "GSC Discover Clicks": discover.get("clicks"),
        "GSC Discover Impressions": discover.get("impressions"),
        "GSC Discover CTR": discover.get("ctr"),
        "Search Queries": json.dumps(query_rows, ensure_ascii=False, separators=(",", ":"))[:5000]
        if query_rows
        else None,
        "GA4 Page Views": ga4.get("page_views"),
        "GA4 Sessions": ga4.get("sessions"),
        "GA4 Engaged Sessions": ga4.get("engaged_sessions"),
        "GA4 Engagement Rate": ga4.get("engagement_rate"),
        "GA4 Avg Engagement Sec": ga4.get("average_engagement_time_seconds"),
        "GA4 Returning Users": ga4.get("returning_users"),
        "Qualified Journeys": ga4.get("qualified_journeys"),
        "诊断": _diagnosis(artifact),
        "置信度": diagnosis.get("confidence") or "LOW",
        "复盘结论": conclusion,
        "建议动作": _content_review_action(artifact),
        "状态": state,
        "下一检查时间": _hkt_text(next_checkpoint) if next_checkpoint else None,
        "证据路径": str(evidence_path),
    }
    return _omit_none(fields)


def article_fields(artifact: Dict[str, Any], evidence_path: Path) -> Dict[str, Any]:
    publication = artifact.get("publication") or {}
    published = parse_datetime(publication.get("published_at_utc"))
    if published is None:
        raise BaseHandoffError("Checkpoint publication timestamp is missing")
    checkpoint = str(artifact["checkpoint"])
    diagnosis = _diagnosis(artifact)
    article_diagnosis = ARTICLE_DIAGNOSIS_MAP.get(diagnosis, diagnosis)
    canonical_url = str(publication.get("canonical_url") or "")
    section = str(publication.get("section") or "")
    if section.lower() == "news" or "/news/" in canonical_url:
        raise BaseHandoffError("Permanent non-News boundary rejected the checkpoint handoff")
    current_state = "等待T+72h" if checkpoint == "24h" else "等待D+7"
    if checkpoint == "7d":
        current_state = "等待D+28"
    elif checkpoint == "28d":
        current_state = "已完成复盘"
    if str(artifact.get("data_maturity") or "").upper() == "SOURCE_BLOCKED":
        current_state = "技术阻塞"
    elif str(artifact.get("data_maturity") or "").upper() == "DATA_NOT_MATURE":
        current_state = "数据不足"
    if diagnosis in ACTIONABLE:
        current_state = "需调整"
    elif diagnosis in {"WINNER", "WINNER_WATCH"}:
        current_state = "优胜内容"
    fields = {
        "Article Key": artifact.get("article_key"),
        "文章标题": publication.get("title"),
        "文章URL": canonical_url,
        "栏目": section,
        "非News通过": True,
        "Run ID": artifact.get("publication_run_id"),
        "Sanity Doc ID": publication.get("document_id"),
        "Source Rev": publication.get("source_rev"),
        "发布时间": _hkt_text(publication.get("published_at_utc")),
        "T+24h": _hkt_text(published + CHECKPOINT_OFFSETS["24h"]),
        "T+72h": _hkt_text(published + CHECKPOINT_OFFSETS["72h"]),
        "D+7": _hkt_text(published + CHECKPOINT_OFFSETS["7d"]),
        "D+28": _hkt_text(published + CHECKPOINT_OFFSETS["28d"]),
        "最新数据日期": _checkpoint_cutoff(artifact),
        "最新诊断": article_diagnosis,
        "置信度": (artifact.get("diagnosis") or {}).get("confidence") or "LOW",
        "当前状态": current_state,
        "本地证据路径": str(evidence_path),
    }
    next_checkpoint = {
        "24h": published + CHECKPOINT_OFFSETS["72h"],
        "72h": published + CHECKPOINT_OFFSETS["7d"],
        "7d": published + CHECKPOINT_OFFSETS["28d"],
    }.get(checkpoint)
    if next_checkpoint is not None:
        fields["下次检查时间"] = _hkt_text(next_checkpoint)
    return _omit_none(fields)


def load_execution_artifacts(runtime_output: Path) -> List[Dict[str, Any]]:
    payload = load_json(runtime_output, {}) or {}
    artifacts: List[Dict[str, Any]] = []
    for result in ((payload.get("execution") or {}).get("results") or []):
        path = Path(str(result.get("path") or ""))
        artifact = load_json(path, {}) or {}
        artifacts.append({"path": path, "artifact": artifact})
    return artifacts


def build_manifest(runtime_output: Path, schema_map: Path) -> Dict[str, Any]:
    runtime = load_json(runtime_output, {}) or {}
    schema = load_json(schema_map, {}) or {}
    execution = runtime.get("execution") or {}
    if not execution.get("execution_id"):
        raise BaseHandoffError("Runtime output has no execution_id")
    records = load_execution_artifacts(runtime_output)
    eligible = [row for row in records if checkpoint_source_complete(row["artifact"])]
    learning_eligible = [
        row for row in records if checkpoint_learning_eligible(row["artifact"])
    ]
    blocked = [
        {
            "path": str(row["path"]),
            "status": row["artifact"].get("checkpoint_status"),
            "data_maturity": row["artifact"].get("data_maturity"),
        }
        for row in records
        if not checkpoint_source_complete(row["artifact"])
    ]
    return {
        "contract_version": "vertu-monitor-base-handoff-v1",
        "execution_id": execution["execution_id"],
        "runtime_output": str(runtime_output),
        "base_token": schema.get("base_token"),
        "tables": {
            key: (schema.get("tables") or {}).get(key, {}).get("table_id")
            for key in ("monitor_runs", "articles", "checkpoints", "content_review", "qa_runs")
        },
        "checkpoint_count": len(records),
        "eligible_checkpoint_count": len(eligible),
        "source_complete_checkpoint_count": len(eligible),
        "ineligible_checkpoint_count": len(blocked),
        "observation_checkpoint_count": len(records),
        "learning_eligible_checkpoint_count": len(learning_eligible),
        "ineligible_checkpoints": blocked,
        "eligible_checkpoints": [
            {
                "review_id": checkpoint_review_id(row["artifact"]),
                "article_key": row["artifact"].get("article_key"),
                "path": str(row["path"]),
            }
            for row in eligible
        ],
        "sanity_mutations": 0,
        "experiments_auto_approved": 0,
        "apply_state": "NOT_APPLIED",
    }


class LarkCliBaseClient:
    def __init__(self, base_token: str, config_dir: Optional[Path] = None):
        self.base_token = base_token
        self.env = dict(os.environ)
        if "LARK_CONFIG_DIR" not in self.env:
            self.env["LARK_CONFIG_DIR"] = str(config_dir or Path.home() / ".lark-cli")

    def _run(self, args: Sequence[str]) -> Dict[str, Any]:
        command = ["lark-cli", *args, "--format", "json"]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=self.env,
                timeout=LARK_CLI_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            raise BaseHandoffError(
                "SOURCE_BLOCKED: lark-cli exceeded the 45-second command timeout"
            ) from error

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as error:
            raise BaseHandoffError(f"lark-cli returned invalid JSON: {error}") from error
        if result.returncode != 0 or not payload.get("ok"):
            message = (payload.get("error") or {}).get("message") or result.stderr or "unknown error"
            raise BaseHandoffError(f"lark-cli failed: {message}")
        return payload

    def exact_records(
        self, table_id: str, key_field: str, key_value: str, fields: Sequence[str]
    ) -> List[Dict[str, Any]]:
        filter_json = json.dumps(
            {"logic": "and", "conditions": [[key_field, "==", key_value]]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        args = [
            "base",
            "+record-list",
            "--base-token",
            self.base_token,
            "--table-id",
            table_id,
            "--filter-json",
            filter_json,
            "--limit",
            "200",
        ]
        for field in fields:
            args.extend(("--field-id", field))
        payload = self._run(args).get("data") or {}
        names = payload.get("fields") or []
        rows = payload.get("data") or []
        ids = payload.get("record_id_list") or []
        return [
            {"record_id": record_id, "fields": dict(zip(names, row))}
            for record_id, row in zip(ids, rows)
        ]

    def field_names(self, table_id: str) -> List[str]:
        """Read the live table schema before lifecycle projection.

        Lifecycle metadata must never be guessed.  The projection layer uses
        this read to decide whether it can run and whether exact revision is
        part of the logical key.
        """

        payload = self._run(
            (
                "base",
                "+field-list",
                "--base-token",
                self.base_token,
                "--table-id",
                table_id,
                "--limit",
                "200",
            )
        )
        data = payload.get("data") or {}
        candidates = data.get("items") or data.get("fields") or data.get("data") or []
        names: List[str] = []
        for item in candidates:
            if isinstance(item, str):
                names.append(item)
                continue
            if not isinstance(item, dict):
                continue
            name = item.get("field_name") or item.get("name") or item.get("fieldName")
            if name:
                names.append(str(name))
        if not names:
            raise BaseHandoffError(
                f"SOURCE_BLOCKED: field-list returned no readable schema for {table_id}"
            )
        return names

    def upsert(self, table_id: str, fields: Dict[str, Any], record_id: Optional[str] = None) -> str:
        args = [
            "base",
            "+record-upsert",
            "--base-token",
            self.base_token,
            "--table-id",
            table_id,
            "--json",
            json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
        ]
        if record_id:
            args.extend(("--record-id", record_id))
        payload = self._run(args)
        data = payload.get("data") or {}
        record = data.get("record") or {}
        created_id = (
            data.get("record_id")
            or data.get("recordId")
            or record.get("record_id")
            or record.get("recordId")
            or (record.get("record_id_list") or [None])[0]
            or (data.get("record_id_list") or [None])[0]
            or record_id
        )
        # Create responses vary across lark-cli versions.  The authoritative
        # identity is always the required exact-key readback performed by the
        # caller, never this response hint.
        return str(created_id or "")


def _require_unique(rows: List[Dict[str, Any]], label: str) -> Optional[Dict[str, Any]]:
    if len(rows) > 1:
        raise BaseHandoffError(f"{label}: duplicate exact business key ({len(rows)} matches)")
    return rows[0] if rows else None


def _readback_created(
    client: Any,
    table_id: str,
    key_field: str,
    key_value: str,
    fields: Sequence[str],
    label: str,
) -> Dict[str, Any]:
    """Resolve a just-created row by its immutable business key.

    Feishu Base writes can become visible to filtered reads shortly after the
    create response.  The create response is only a hint, so use bounded
    readback retries and never issue a second create from this helper.
    """

    delays = (0.0, 0.25, 0.75, 1.5)
    for delay in delays:
        if delay:
            time.sleep(delay)
        row = _require_unique(
            client.exact_records(table_id, key_field, key_value, fields),
            label,
        )
        if row is not None:
            return row
    raise BaseHandoffError(f"{label}: create did not survive bounded exact readback")


def _verify_readback(
    client: Any,
    table_id: str,
    key_field: str,
    key_value: str,
    expected_fields: Dict[str, Any],
) -> Dict[str, Any]:
    rows = client.exact_records(table_id, key_field, key_value, tuple(expected_fields))
    row = _require_unique(rows, key_value)
    if row is None:
        raise BaseHandoffError(f"{key_value}: Base readback returned zero records")
    actual = row.get("fields") or {}
    for field in (key_field, "Article Key"):
        if field in expected_fields and str(_cell_scalar(actual.get(field))) != str(
            expected_fields[field]
        ):
            raise BaseHandoffError(f"{key_value}: immutable field {field} readback mismatch")
    return row


def _resolve_qa_record(client: Any, table_id: str, artifact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    publication = artifact.get("publication") or {}
    document_id = str(publication.get("document_id") or "").strip()
    source_rev = str(publication.get("source_rev") or "").strip()
    if not document_id or not source_rev:
        return None
    handoff = artifact.get("qa_handoff") or publication.get("qa_handoff") or {}
    qa_run_id = str(
        handoff.get("qa_run_id") or publication.get("qa_run_id") or ""
    ).strip()
    qa_fields = (
        "QA Run ID",
        "Sanity Doc ID",
        "Source Rev",
        "最终决策",
        "审核时间",
        "QA Handoff Contract Version",
        "Producer Skill ID",
        "Producer Skill Version",
        "QA Policy ID",
        "QA Policy Version",
        "QA Policy Hash",
        "Evaluation Profile",
        "Draft Bundle SHA256",
        "Release Gate Role",
        "Compatibility Status",
        "QA Result Fingerprint",
    )
    if qa_run_id:
        row = _require_unique(
            client.exact_records(table_id, "QA Run ID", qa_run_id, qa_fields),
            f"qa-run:{qa_run_id}",
        )
        if row is None:
            return None
        fields = row.get("fields") or {}
        expected = {
            "Sanity Doc ID": document_id,
            "Source Rev": source_rev,
            "最终决策": "PASS",
        }
        for field, value in expected.items():
            if str(_cell_scalar(fields.get(field)) or "") != value:
                return None
        handoff_field_map = {
            "contract_version": "QA Handoff Contract Version",
            "producer_skill_id": "Producer Skill ID",
            "producer_skill_version": "Producer Skill Version",
            "qa_policy_id": "QA Policy ID",
            "qa_policy_version": "QA Policy Version",
            "qa_policy_hash": "QA Policy Hash",
            "evaluation_profile": "Evaluation Profile",
            "draft_bundle_sha256": "Draft Bundle SHA256",
            "release_gate_role": "Release Gate Role",
            "compatibility_status": "Compatibility Status",
            "qa_result_fingerprint": "QA Result Fingerprint",
        }
        for handoff_key, base_field in handoff_field_map.items():
            expected_value = handoff.get(handoff_key)
            if expected_value not in (None, "") and str(
                _cell_scalar(fields.get(base_field)) or ""
            ) != str(expected_value):
                return None
        if handoff.get("contract_version") == "qa-handoff-v1" and str(
            _cell_scalar(fields.get("Compatibility Status")) or ""
        ) != "COMPATIBLE":
            return None
        row["_qa_binding_status"] = "COMPATIBLE"
        return row

    # Historical observation only: accept one unique exact-revision PASS, but
    # never choose the latest among multiple rows and never treat it as current
    # release authority.
    rows = client.exact_records(table_id, "Sanity Doc ID", document_id, qa_fields)
    matches = [
        row
        for row in rows
        if str(_cell_scalar((row.get("fields") or {}).get("Source Rev")) or "") == source_rev
        and str(_cell_scalar((row.get("fields") or {}).get("最终决策")) or "") == "PASS"
    ]
    if len(matches) != 1:
        return None
    matches[0]["_qa_binding_status"] = "LEGACY_UNVERIFIED"
    return matches[0]


def monitor_run_status(artifacts: Sequence[Dict[str, Any]]) -> str:
    checkpoint_statuses = {
        str(artifact.get("checkpoint_status") or "").upper() for artifact in artifacts
    }
    if "SOURCE_BLOCKED" in checkpoint_statuses:
        return "SOURCE_BLOCKED"
    if "DATA_NOT_MATURE" in checkpoint_statuses:
        return "DATA_NOT_MATURE"
    diagnoses = [_diagnosis(artifact) for artifact in artifacts]
    return "ACTION_PROPOSED" if any(row in ACTIONABLE for row in diagnoses) else "NO_ACTIONABLE_CHANGE"


def _projection_schema(client: Any, table_id: str) -> Dict[str, Any]:
    """Resolve lifecycle fields from the actual table schema.

    The handoff can continue writing immutable observations when the lifecycle
    projection is schema-blocked, but it must report that state and must not
    attempt a guessed field write.
    """

    if not hasattr(client, "field_names"):
        return {
            "status": "SCHEMA_BLOCKED",
            "reason": "Client does not expose field_names for lifecycle preflight",
            "missing_fields": sorted(PROJECTION_REQUIRED_FIELDS),
            "source_rev_field": None,
        }
    try:
        field_names = {str(name) for name in client.field_names(table_id)}
    except Exception as error:
        return {
            "status": "SOURCE_BLOCKED",
            "reason": str(error)[:500],
            "missing_fields": [],
            "source_rev_field": None,
        }
    missing = sorted(PROJECTION_REQUIRED_FIELDS - field_names)
    if missing:
        return {
            "status": "SCHEMA_BLOCKED",
            "reason": "Lifecycle projection fields are absent from the checkpoint table",
            "missing_fields": missing,
            "source_rev_field": None,
        }
    return {
        "status": "READY",
        "reason": None,
        "missing_fields": [],
        "source_rev_field": "Source Rev" if "Source Rev" in field_names else None,
    }


def _effective_projection_node(fields: Dict[str, Any]) -> str:
    node = str(_cell_scalar(fields.get("检查节点")) or "")
    if node in CHECKPOINT_LABELS.values():
        return node
    # Legacy retry rows used the display label 重试.  Keep the immutable cell
    # untouched and derive its original node from the deterministic 复盘ID.
    review_id_parts = str(_cell_scalar(fields.get("复盘ID")) or "").split(":")
    for checkpoint, label in CHECKPOINT_LABELS.items():
        if checkpoint in review_id_parts:
            return label
    return node


def _projection_row_eligible(fields: Dict[str, Any]) -> bool:
    node = _effective_projection_node(fields)
    maturity = str(_cell_scalar(fields.get("数据成熟度")) or "").upper()
    source_state = str(_cell_scalar(fields.get("源状态")) or "").upper()
    if "SOURCE_BLOCKED" in source_state:
        return False
    if node == CHECKPOINT_LABELS["24h"]:
        return maturity == "PRELIMINARY"
    return maturity == "MATURE" and "GSC=MATURE" in source_state


def _projection_sort_key(row: Dict[str, Any]) -> tuple:
    fields = row.get("fields") or {}
    raw_executed = _cell_scalar(fields.get("执行时间"))
    executed = parse_datetime(raw_executed)
    if executed is None and isinstance(raw_executed, (int, float)):
        epoch_seconds = float(raw_executed)
        if epoch_seconds > 10_000_000_000:
            epoch_seconds /= 1000.0
        executed = dt.datetime.fromtimestamp(epoch_seconds, tz=UTC)
    timestamp = executed.timestamp() if executed is not None else float("-inf")
    return (
        timestamp,
        str(_cell_scalar(fields.get("复盘ID")) or ""),
        str(row.get("record_id") or ""),
    )


def _write_lifecycle_with_requery(
    client: Any,
    table_id: str,
    review_id: str,
    desired: str,
    replaced_by_review_id: Optional[str],
) -> Dict[str, Any]:
    """Write one lifecycle cell with bounded, non-blind retries.

    Every attempt starts with an exact business-key query.  This makes an
    ambiguous response safe: if the prior PATCH succeeded, the next attempt
    observes the desired value and does not repeat the mutation.
    """

    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        rows = client.exact_records(
            table_id,
            "复盘ID",
            review_id,
            (
                "复盘ID",
                PROJECTION_LIFECYCLE_FIELD,
                PROJECTION_REPLACED_BY_FIELD,
            ),
        )
        row = _require_unique(rows, f"projection:{review_id}")
        if row is None:
            raise BaseHandoffError(
                f"projection:{review_id}: exact row disappeared before lifecycle write"
            )
        actual = str(
            _cell_scalar((row.get("fields") or {}).get(PROJECTION_LIFECYCLE_FIELD)) or ""
        )
        actual_replaced_by = str(
            _cell_scalar((row.get("fields") or {}).get(PROJECTION_REPLACED_BY_FIELD)) or ""
        )
        expected_replaced_by = str(replaced_by_review_id or "")
        if actual == desired and actual_replaced_by == expected_replaced_by:
            return {
                "record_id": row["record_id"],
                "status": "NOOP" if attempt == 1 else "RECONCILED_AFTER_RETRY",
                "attempts": attempt,
                "retries": attempt - 1,
            }
        try:
            client.upsert(
                table_id,
                {
                    PROJECTION_LIFECYCLE_FIELD: desired,
                    PROJECTION_REPLACED_BY_FIELD: replaced_by_review_id,
                },
                record_id=row["record_id"],
            )
        except Exception as error:
            last_error = error
            if attempt == 3:
                raise BaseHandoffError(
                    f"projection:{review_id}: lifecycle write failed after re-query retries: {error}"
                ) from error
            continue
        readback = _require_unique(
            client.exact_records(
                table_id,
                "复盘ID",
                review_id,
                (
                    "复盘ID",
                    PROJECTION_LIFECYCLE_FIELD,
                    PROJECTION_REPLACED_BY_FIELD,
                ),
            ),
            f"projection-readback:{review_id}",
        )
        if readback is not None and str(
            _cell_scalar(
                (readback.get("fields") or {}).get(PROJECTION_LIFECYCLE_FIELD)
            )
            or ""
        ) == desired and str(
            _cell_scalar(
                (readback.get("fields") or {}).get(PROJECTION_REPLACED_BY_FIELD)
            )
            or ""
        ) == expected_replaced_by:
            return {
                "record_id": readback["record_id"],
                "status": "UPDATED",
                "attempts": attempt,
                "retries": attempt - 1,
            }
        last_error = BaseHandoffError(
            f"projection:{review_id}: lifecycle readback mismatch"
        )
    raise BaseHandoffError(str(last_error or "lifecycle projection failed"))


def _apply_checkpoint_projection(
    client: Any,
    table_id: str,
    requests: Sequence[Dict[str, Any]],
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "status": schema.get("status") or "SCHEMA_BLOCKED",
        "reason": schema.get("reason"),
        "missing_fields": list(schema.get("missing_fields") or []),
        "source_rev_field": schema.get("source_rev_field"),
        "logical_key_count": 0,
        "current_count": 0,
        "superseded_count": 0,
        "historical_count": 0,
        "lifecycle_update_count": 0,
        "lifecycle_noop_count": 0,
        "retry_count": 0,
        "current_record_ids": [],
        "superseded_record_ids": [],
        "historical_record_ids": [],
        "updated_record_ids": [],
        "logical_keys": [],
    }
    if schema.get("status") != "READY":
        return result

    source_rev_field = schema.get("source_rev_field")
    by_key: Dict[tuple, Dict[str, Any]] = {}
    for request in requests:
        key = (
            str(request.get("article_key") or ""),
            str(request.get("checkpoint_node") or ""),
            str(request.get("source_rev") or "") if source_rev_field else "",
        )
        by_key[key] = request

    for logical_key in sorted(by_key):
        article_key, checkpoint_node, source_rev = logical_key
        fields = [
            "复盘ID",
            "Article Key",
            "检查节点",
            "执行时间",
            "数据成熟度",
            "源状态",
            PROJECTION_LIFECYCLE_FIELD,
            PROJECTION_REPLACED_BY_FIELD,
        ]
        if source_rev_field:
            fields.append(source_rev_field)
        rows = client.exact_records(
            table_id,
            "Article Key",
            article_key,
            tuple(fields),
        )
        logical_rows = []
        for row in rows:
            row_fields = row.get("fields") or {}
            if _effective_projection_node(row_fields) != checkpoint_node:
                continue
            if source_rev_field and str(
                _cell_scalar(row_fields.get(source_rev_field)) or ""
            ) != source_rev:
                continue
            logical_rows.append(row)

        duplicate_ids: Dict[str, List[str]] = {}
        for row in logical_rows:
            review_id = str(_cell_scalar((row.get("fields") or {}).get("复盘ID")) or "")
            duplicate_ids.setdefault(review_id, []).append(str(row.get("record_id") or ""))
        duplicate_ids = {
            review_id: record_ids
            for review_id, record_ids in duplicate_ids.items()
            if review_id and len(record_ids) > 1
        }
        if duplicate_ids:
            raise BaseHandoffError(
                "projection duplicate exact 复盘ID: "
                + json.dumps(duplicate_ids, ensure_ascii=False, sort_keys=True)
            )

        eligible_rows = [row for row in logical_rows if _projection_row_eligible(row.get("fields") or {})]
        current_row = max(eligible_rows, key=_projection_sort_key) if eligible_rows else None
        current_record_id = str((current_row or {}).get("record_id") or "")
        current_review_id = str(
            _cell_scalar(((current_row or {}).get("fields") or {}).get("复盘ID")) or ""
        )
        logical_result = {
            "article_key": article_key,
            "checkpoint_node": checkpoint_node,
            "source_rev": source_rev if source_rev_field else None,
            "record_count": len(logical_rows),
            "eligible_record_count": len(eligible_rows),
            "current_record_id": current_record_id or None,
            "superseded_record_ids": [],
            "historical_record_ids": [],
        }
        for row in sorted(logical_rows, key=_projection_sort_key):
            record_id = str(row.get("record_id") or "")
            review_id = str(_cell_scalar((row.get("fields") or {}).get("复盘ID")) or "")
            if current_record_id and record_id == current_record_id:
                desired = PROJECTION_CURRENT
                replaced_by_review_id = None
            elif row in eligible_rows and current_record_id:
                desired = PROJECTION_SUPERSEDED
                replaced_by_review_id = current_review_id
            else:
                desired = PROJECTION_HISTORICAL
                replaced_by_review_id = None
            write_result = _write_lifecycle_with_requery(
                client,
                table_id,
                review_id,
                desired,
                replaced_by_review_id,
            )
            result["retry_count"] += int(write_result.get("retries") or 0)
            if write_result["status"] == "NOOP":
                result["lifecycle_noop_count"] += 1
            else:
                result["lifecycle_update_count"] += 1
                result["updated_record_ids"].append(record_id)
            if desired == PROJECTION_CURRENT:
                result["current_record_ids"].append(record_id)
            elif desired == PROJECTION_SUPERSEDED:
                result["superseded_record_ids"].append(record_id)
                logical_result["superseded_record_ids"].append(record_id)
            else:
                result["historical_record_ids"].append(record_id)
                logical_result["historical_record_ids"].append(record_id)
        result["logical_keys"].append(logical_result)

    result["status"] = "SUCCESS"
    result["logical_key_count"] = len(result["logical_keys"])
    result["current_record_ids"] = sorted(set(result["current_record_ids"]))
    result["superseded_record_ids"] = sorted(set(result["superseded_record_ids"]))
    result["historical_record_ids"] = sorted(set(result["historical_record_ids"]))
    result["updated_record_ids"] = sorted(set(result["updated_record_ids"]))
    result["current_count"] = len(result["current_record_ids"])
    result["superseded_count"] = len(result["superseded_record_ids"])
    result["historical_count"] = len(result["historical_record_ids"])
    return result


def apply_manifest(
    manifest: Dict[str, Any], runtime_output: Path, client: Any
) -> Dict[str, Any]:
    tables = manifest["tables"]
    if not all(tables.values()) or not manifest.get("base_token"):
        raise BaseHandoffError("Canonical Base schema map is incomplete")
    runtime = load_json(runtime_output, {}) or {}
    execution = runtime.get("execution") or {}
    execution_id = str(execution["execution_id"])
    projection_schema = _projection_schema(client, tables["checkpoints"])

    existing_run = _require_unique(
        client.exact_records(
            tables["monitor_runs"], "执行ID", execution_id, ("执行ID", "运行状态", "飞书写入状态")
        ),
        execution_id,
    )
    if existing_run is None:
        client.upsert(
            tables["monitor_runs"],
            {
                "执行ID": execution_id,
                "Automation ID": "vertu",
                "执行时间": _hkt_text(execution.get("executed_at")),
                "扫描发布批次": (runtime.get("inventory") or {}).get("published_runs_scanned", 0),
                "扫描文章数": len((runtime.get("inventory") or {}).get("articles") or []),
                "到期节点数": execution.get("job_count", 0),
                "运行状态": "NO_ACTIONABLE_CHANGE",
                "飞书写入状态": "RETRYING",
                "本地证据路径": str(runtime_output),
                "执行摘要": "Canonical checkpoint handoff started; no Sanity mutation.",
            },
        )
        created_run = _readback_created(
            client,
            tables["monitor_runs"],
            "执行ID",
            execution_id,
            ("执行ID", "运行状态", "飞书写入状态"),
            execution_id,
        )
        monitor_record_id = created_run["record_id"]
    else:
        monitor_record_id = existing_run["record_id"]

    written: List[Dict[str, Any]] = []
    projection_requests: List[Dict[str, Any]] = []
    qa_link_warnings: List[Dict[str, Any]] = []
    legacy_qa_links: List[Dict[str, Any]] = []
    try:
        for item in load_execution_artifacts(runtime_output):
            artifact = item["artifact"]
            key = str(artifact["article_key"])
            article_rows = client.exact_records(
                tables["articles"],
                "Article Key",
                key,
                ("Article Key", "文章URL", "最新数据日期", "最新诊断", "当前状态"),
            )
            article_row = _require_unique(article_rows, key)
            a_fields = article_fields(artifact, item["path"])
            if article_row is None:
                client.upsert(tables["articles"], a_fields)
                article_row = _readback_created(
                    client,
                    tables["articles"],
                    "Article Key",
                    key,
                    ("Article Key", "文章URL"),
                    key,
                )
                article_record_id = article_row["record_id"]
            else:
                article_record_id = article_row["record_id"]
                client.upsert(tables["articles"], a_fields, record_id=article_record_id)
            _verify_readback(
                client, tables["articles"], "Article Key", key, {"Article Key": key}
            )

            source_rev_field = (
                projection_schema.get("source_rev_field")
                if projection_schema.get("status") == "READY"
                else None
            )
            fields = checkpoint_fields(
                artifact,
                item["path"],
                article_record_id,
                source_rev_field=source_rev_field,
            )
            review_id = str(fields["复盘ID"])
            checkpoint_rows = client.exact_records(
                tables["checkpoints"],
                "复盘ID",
                review_id,
                ("复盘ID", "Article Key", "数据成熟度", "检查节点", "关联文章"),
            )
            checkpoint_row = _require_unique(checkpoint_rows, review_id)
            if checkpoint_row is None:
                client.upsert(tables["checkpoints"], fields)
                checkpoint_row = _readback_created(
                    client,
                    tables["checkpoints"],
                    "复盘ID",
                    review_id,
                    ("复盘ID", "Article Key", "数据成熟度", "检查节点", "关联文章"),
                    review_id,
                )
                checkpoint_record_id = checkpoint_row["record_id"]
            else:
                checkpoint_record_id = checkpoint_row["record_id"]
                actual = checkpoint_row.get("fields") or {}
                immutable_names = ["Article Key", "数据成熟度", "检查节点"]
                if source_rev_field:
                    immutable_names.append(source_rev_field)
                for name in immutable_names:
                    if str(_cell_scalar(actual.get(name))) != str(fields.get(name)):
                        raise BaseHandoffError(
                            f"{review_id}: existing immutable field {name} does not match"
                        )
                if not actual.get("关联文章"):
                    client.upsert(
                        tables["checkpoints"],
                        {"关联文章": [{"id": article_record_id}]},
                        record_id=checkpoint_record_id,
                    )
            _verify_readback(
                client,
                tables["checkpoints"],
                "复盘ID",
                review_id,
                {"复盘ID": review_id, "Article Key": key},
            )
            projection_requests.append(
                {
                    "article_key": key,
                    "checkpoint_node": CHECKPOINT_LABELS[str(artifact["checkpoint"])],
                    "source_rev": (artifact.get("publication") or {}).get("source_rev"),
                    "review_id": review_id,
                }
            )
            qa_record = _resolve_qa_record(client, tables["qa_runs"], artifact)
            if qa_record is None:
                qa_link_warnings.append(
                    {
                        "review_id": review_id,
                        "article_key": key,
                        "document_id": (artifact.get("publication") or {}).get("document_id"),
                        "source_rev": (artifact.get("publication") or {}).get("source_rev"),
                        "status": "QA_LINK_UNAVAILABLE",
                    }
                )
            elif qa_record.get("_qa_binding_status") == "LEGACY_UNVERIFIED":
                legacy_qa_links.append(
                    {
                        "review_id": review_id,
                        "article_key": key,
                        "qa_run_id": (qa_record.get("fields") or {}).get("QA Run ID"),
                        "status": "LEGACY_UNVERIFIED",
                    }
                )
            review_fields = content_review_fields(
                artifact,
                item["path"],
                article_record_id,
                checkpoint_record_id,
                qa_record,
                str(manifest["base_token"]),
                tables["checkpoints"],
            )
            review_rows = client.exact_records(
                tables["content_review"],
                "复盘ID",
                review_id,
                ("复盘ID", "Article Key", "表现监控记录ID", "关联文章", "关联 QA Run"),
            )
            review_row = _require_unique(review_rows, f"content-review:{review_id}")
            if review_row is None:
                client.upsert(tables["content_review"], review_fields)
                review_row = _readback_created(
                    client,
                    tables["content_review"],
                    "复盘ID",
                    review_id,
                    ("复盘ID", "Article Key", "表现监控记录ID", "关联文章", "关联 QA Run"),
                    f"content-review:{review_id}",
                )
                content_review_record_id = review_row["record_id"]
            else:
                content_review_record_id = review_row["record_id"]
                actual_review = review_row.get("fields") or {}
                for name in ("Article Key", "表现监控记录ID"):
                    if str(_cell_scalar(actual_review.get(name))) != str(review_fields.get(name)):
                        raise BaseHandoffError(
                            f"content-review:{review_id}: immutable field {name} does not match"
                        )
                links: Dict[str, Any] = {}
                if not actual_review.get("关联文章"):
                    links["关联文章"] = [{"id": article_record_id}]
                if qa_record and not actual_review.get("关联 QA Run"):
                    links["QA Run ID"] = (qa_record.get("fields") or {}).get("QA Run ID")
                    links["关联 QA Run"] = [{"id": qa_record["record_id"]}]
                if links:
                    client.upsert(tables["content_review"], links, record_id=content_review_record_id)
            _verify_readback(
                client,
                tables["content_review"],
                "复盘ID",
                review_id,
                {"复盘ID": review_id, "Article Key": key},
            )
            written.append(
                {
                    "review_id": review_id,
                    "article_record_id": article_record_id,
                    "checkpoint_record_id": checkpoint_record_id,
                    "content_review_record_id": content_review_record_id,
                    "qa_run_record_id": qa_record["record_id"] if qa_record else None,
                    "evidence_path": str(item["path"]),
                }
            )

        projection = _apply_checkpoint_projection(
            client,
            tables["checkpoints"],
            projection_requests,
            projection_schema,
        )
        execution_artifacts = load_execution_artifacts(runtime_output)
        run_status = monitor_run_status([item["artifact"] for item in execution_artifacts])
        if run_status == "SOURCE_BLOCKED":
            next_action = "来源阻塞项按12小时窗口重试；不把缺失值写成0。"
        elif run_status == "DATA_NOT_MATURE":
            next_action = "等待GSC最终数据覆盖观察窗口后按确定性复盘ID重试。"
        elif run_status == "ACTION_PROPOSED":
            next_action = "低风险实验保持人工审批；批准后由独立执行链处理。"
        else:
            next_action = "保持观察，按下一到期节点继续监控。"
        projection_complete = projection.get("status") == "SUCCESS"
        client.upsert(
            tables["monitor_runs"],
            {
                "运行状态": run_status,
                "飞书写入状态": "SUCCESS" if projection_complete else "FAILED",
                "执行摘要": (
                    f"{len(written)} checkpoint and content-review observations written/read back; "
                    f"projection={projection.get('status')} "
                    f"current={projection.get('current_count', 0)} "
                    f"superseded={projection.get('superseded_count', 0)} "
                    f"historical={projection.get('historical_count', 0)}; "
                    f"{len(qa_link_warnings)} exact-revision QA links unavailable; "
                    f"{len(legacy_qa_links)} historical QA links are LEGACY_UNVERIFIED; "
                    "no Sanity mutation; experiments remain manual."
                ),
                "数据源状态": ",".join(
                    sorted(
                        {
                            str(item["artifact"].get("checkpoint_status") or "UNKNOWN")
                            for item in execution_artifacts
                        }
                    )
                ),
                "下一动作": next_action,
            },
            record_id=monitor_record_id,
        )
        _verify_readback(
            client,
            tables["monitor_runs"],
            "执行ID",
            execution_id,
            {"执行ID": execution_id},
        )
    except Exception as error:
        try:
            client.upsert(
                tables["monitor_runs"],
                {"飞书写入状态": "FAILED", "错误信息": str(error)[:500]},
                record_id=monitor_record_id,
            )
        except Exception:
            pass
        raise

    return {
        "status": (
            "HANDOFF_INCOMPLETE"
            if qa_link_warnings or projection.get("status") != "SUCCESS"
            else "SUCCESS"
        ),
        "monitor_run_record_id": monitor_record_id,
        "checkpoint_records": written,
        "checkpoint_count": len(written),
        "qa_link_warnings": qa_link_warnings,
        "legacy_qa_links": legacy_qa_links,
        "checkpoint_projection": projection,
        "sanity_mutations": 0,
        "experiments_auto_approved": 0,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-output", required=True, type=Path)
    parser.add_argument("--schema-map", type=Path, default=DEFAULT_SCHEMA_MAP)
    parser.add_argument("--audit-receipt", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    manifest = build_manifest(args.runtime_output, args.schema_map)
    if args.apply:
        if args.audit_receipt is None:
            parser.error("--apply requires --audit-receipt")
        manifest["audit_receipt"] = validate_audit_receipt(args.audit_receipt)
        if manifest["audit_receipt"]["execution_id"] != manifest["execution_id"]:
            raise BaseHandoffError(
                "Start-ledger execution_id does not match the monitor runtime execution_id"
            )
        client = LarkCliBaseClient(str(manifest["base_token"]))
        try:
            manifest["apply_result"] = apply_manifest(manifest, args.runtime_output, client)
            manifest["apply_state"] = manifest["apply_result"]["status"]
        except Exception as error:
            manifest["apply_state"] = "FEISHU_BASE_WRITE_FAILED"
            manifest["error"] = str(error)[:500]
            write_json(args.output, manifest)
            raise
    write_json(args.output, manifest)
    print(
        json.dumps(
            {
                "execution_id": manifest["execution_id"],
                "eligible_checkpoints": manifest["eligible_checkpoint_count"],
                "ineligible_checkpoints": manifest["ineligible_checkpoint_count"],
                "apply_state": manifest["apply_state"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

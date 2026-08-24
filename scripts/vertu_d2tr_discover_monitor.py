#!/usr/bin/env python3
"""Collect, retain and hand off public D2TR Google Discover context.

D2TR is an independent market-observation source.  This module deliberately
keeps its signals separate from official Google Trends, GSC and Keyword
Planner demand evidence.  The resulting context may only reorder candidates
that already passed the normal traffic gate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


UTC = dt.timezone.utc
HKT = dt.timezone(dt.timedelta(hours=8))
CONTRACT_VERSION = "d2tr-discover-snapshot-v1"
CONTEXT_CONTRACT_VERSION = "d2tr-discover-context-v1"
DEFAULT_MARKETS = (
    "US", "GB", "AU", "CA", "AE", "SA", "SG", "HK", "IN",
    "PH", "ZA", "MY", "NZ", "PK", "ID",
)
ENDPOINTS = (
    "volatility",
    "category-volatility",
    "topic-volatility",
    "format-interest",
    "categories",
)
API_ROOT = "https://d2tr.com/api/public/discover"
USER_AGENT = "VERTU-Discover-Monitor/1.0 (+https://vertu.com/)"
RETENTION_DAYS = 30
MAX_CONTEXT_AGE_HOURS = 8
LARK_TIMEOUT_SECONDS = 60


class D2TRMonitorError(RuntimeError):
    pass


def _iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> Optional[dt.datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000.0
        try:
            return dt.datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_base_datetime(value: Any) -> Optional[dt.datetime]:
    """Parse Feishu datetime readback, whose plain text is Base-local HKT."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _parse_datetime(value)
    if value in (None, ""):
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=HKT)
    return parsed.astimezone(UTC)


def _fingerprint(payload: Dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "snapshot_fingerprint"}
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _payload_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def endpoint_url(endpoint: str, market: str) -> str:
    if endpoint not in ENDPOINTS:
        raise ValueError(f"unsupported D2TR endpoint: {endpoint}")
    params: Dict[str, Any] = {"country": market.lower()}
    if endpoint in {"volatility", "category-volatility"}:
        params["granularity"] = "day"
    if endpoint == "categories":
        params["limit"] = 50
    return f"{API_ROOT}/{endpoint}?{urllib.parse.urlencode(params)}"


def fetch_json(url: str, timeout_seconds: int = 30) -> Tuple[int, Any, Dict[str, str]]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return int(response.status), json.loads(body), dict(response.headers.items())
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            payload: Any = json.loads(body)
        except json.JSONDecodeError:
            payload = {"detail": body[:500]}
        return int(error.code), payload, dict(error.headers.items())


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _upper(value: Any, allowed: Iterable[str], default: str = "UNKNOWN") -> str:
    text = str(value or "").strip().upper()
    return text if text in set(allowed) else default


def _latest_series_metrics(series: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    latest = series[-1] if series else {}
    metrics = latest.get("metrics") or {}
    return {
        "confidence": _upper(
            latest.get("confidence"), {"HIGH", "MEDIUM", "LOW"}
        ),
        "estimated_impressions": _number(
            metrics.get("total_impressions") or latest.get("impressions")
        ),
        "publications": _number(
            metrics.get("total_articles") or latest.get("articles")
        ),
        "publishers": _number(metrics.get("unique_domains")),
        "note": latest.get("note"),
    }


def _normalise_volatility_object(
    name: str, summary: Dict[str, Any], series: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    latest = _latest_series_metrics(series)
    current = _number(summary.get("current_index"))
    status = "AVAILABLE"
    if current is None or latest.get("note") == "insufficient_baseline":
        status = "INSUFFICIENT_BASELINE"
    return {
        "name": name,
        "status": status,
        "current_value": current,
        "baseline_value": _number(summary.get("mean_index")),
        "change_value": (
            round(current - float(summary.get("mean_index")), 4)
            if current is not None and _number(summary.get("mean_index")) is not None
            else None
        ),
        "trend": _upper(summary.get("trend"), {"RISING", "STABLE", "FALLING"}),
        "state": _upper(
            summary.get("current_state"), {"CALM", "BLIP", "ACTIVE", "SUSTAINED"}
        ),
        **latest,
    }


def normalise_response(endpoint: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "status": "INVALID_RESPONSE",
            "generated_at": None,
            "signals": [],
        }
    generated_at = payload.get("generated_at")
    signals: List[Dict[str, Any]] = []
    if endpoint == "volatility":
        signals.append(
            _normalise_volatility_object(
                "ALL", payload.get("summary") or {}, payload.get("series") or []
            )
        )
    elif endpoint in {"category-volatility", "topic-volatility"}:
        for item in payload.get("categories") or []:
            if not isinstance(item, dict):
                continue
            signals.append(
                _normalise_volatility_object(
                    str(item.get("category") or ""),
                    item.get("summary") or {},
                    item.get("series") or [],
                )
            )
    elif endpoint == "format-interest":
        for item in payload.get("formats") or []:
            if not isinstance(item, dict):
                continue
            summary = item.get("summary") or {}
            series = item.get("series") or []
            latest = _latest_series_metrics(series)
            current = _number(summary.get("current_index"))
            signals.append(
                {
                    "name": str(item.get("format_type") or ""),
                    "status": "AVAILABLE" if current is not None else "INSUFFICIENT_BASELINE",
                    "current_value": current,
                    "baseline_value": _number(summary.get("mean_index")),
                    "change_value": _number(summary.get("shift_vs_mean")),
                    "trend": _upper(
                        summary.get("trend"), {"RISING", "STABLE", "FALLING"}
                    ),
                    "state": "UNKNOWN",
                    **latest,
                }
            )
    elif endpoint == "categories":
        for item in payload.get("categories") or []:
            if not isinstance(item, dict):
                continue
            impressions = _number(item.get("impressions"))
            signals.append(
                {
                    "name": str(item.get("category") or ""),
                    "status": "AVAILABLE" if impressions is not None else "INSUFFICIENT_BASELINE",
                    "current_value": impressions,
                    "baseline_value": None,
                    "change_value": _number(item.get("delta_pct")),
                    "trend": (
                        "RISING"
                        if (_number(item.get("delta_pct")) or 0) > 0
                        else "FALLING"
                        if (_number(item.get("delta_pct")) or 0) < 0
                        else "STABLE"
                    ),
                    "state": "UNKNOWN",
                    "confidence": "UNKNOWN",
                    "estimated_impressions": impressions,
                    "publications": _number(item.get("publications")),
                    "publishers": _number(item.get("publishers")),
                    "note": None,
                }
            )
    status = "AVAILABLE"
    if not signals:
        status = "INSUFFICIENT_BASELINE"
    elif all(row.get("status") != "AVAILABLE" for row in signals):
        status = "INSUFFICIENT_BASELINE"
    return {"status": status, "generated_at": generated_at, "signals": signals}


Transport = Callable[[str], Tuple[int, Any, Dict[str, str]]]


def collect_snapshot(
    execution_id: str,
    markets: Sequence[str] = DEFAULT_MARKETS,
    now: Optional[dt.datetime] = None,
    transport: Transport = fetch_json,
) -> Dict[str, Any]:
    observed_at = (now or dt.datetime.now(UTC)).astimezone(UTC)
    rows: List[Dict[str, Any]] = []
    for market in markets:
        market = market.strip().upper()
        if len(market) != 2:
            raise ValueError(f"invalid ISO alpha-2 market: {market}")
        for endpoint in ENDPOINTS:
            url = endpoint_url(endpoint, market)
            started = time.monotonic()
            attempts: List[Dict[str, Any]] = []
            http_status, payload, headers = 0, {"detail": "not attempted"}, {}
            for attempt in range(1, 4):
                try:
                    http_status, payload, headers = transport(url)
                except Exception as error:  # preserve source failure, never invent zero
                    http_status, payload, headers = 0, {"detail": str(error)[:500]}, {}
                attempts.append({"attempt": attempt, "http_status": http_status})
                if http_status == 200:
                    break
                if http_status not in {0, 429} and http_status < 500:
                    break
                if attempt < 3:
                    time.sleep(0.25 * (2 ** (attempt - 1)))
            normalised = (
                normalise_response(endpoint, payload)
                if http_status == 200
                else {"status": "SOURCE_BLOCKED", "generated_at": None, "signals": []}
            )
            rows.append(
                {
                    "market": market,
                    "endpoint": endpoint,
                    "source_url": url,
                    "http_status": http_status,
                    "source_status": normalised["status"],
                    "generated_at": normalised.get("generated_at"),
                    "observed_at": _iso(observed_at),
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                    "retry_count": max(0, len(attempts) - 1),
                    "attempts": attempts,
                    "retry_after": headers.get("Retry-After") or headers.get("retry-after"),
                    "raw_payload_hash": _payload_hash(payload),
                    "signals": normalised.get("signals") or [],
                    "raw_payload": payload,
                }
            )
    available = sum(row["source_status"] == "AVAILABLE" for row in rows)
    blocked = sum(row["source_status"] == "SOURCE_BLOCKED" for row in rows)
    invalid = sum(row["source_status"] == "INVALID_RESPONSE" for row in rows)
    # A null volatility value caused by an insufficient market baseline is a
    # valid source response, not a transport failure and not a zero signal.
    status = (
        "AVAILABLE"
        if blocked == 0 and invalid == 0
        else "PARTIAL"
        if available or any(row["source_status"] == "INSUFFICIENT_BASELINE" for row in rows)
        else "SOURCE_BLOCKED"
    )
    snapshot: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "execution_id": execution_id,
        "provider": "d2tr_public_discover",
        "official_google_source": False,
        "may_create_google_demand": False,
        "may_create_realtime_hot": False,
        "credentials_included": False,
        "observed_at": _iso(observed_at),
        "expires_at": _iso(observed_at + dt.timedelta(days=RETENTION_DAYS)),
        "retention_days": RETENTION_DAYS,
        "markets": list(dict.fromkeys(market.strip().upper() for market in markets)),
        "endpoints": list(ENDPOINTS),
        "status": status,
        "summary": {
            "request_count": len(rows),
            "available_count": available,
            "insufficient_baseline_count": sum(
                row["source_status"] == "INSUFFICIENT_BASELINE" for row in rows
            ),
            "source_blocked_count": blocked,
            "invalid_response_count": invalid,
        },
        "requests": rows,
    }
    snapshot["snapshot_fingerprint"] = _fingerprint(snapshot)
    return snapshot


def build_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    if snapshot.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("D2TR snapshot contract mismatch")
    if snapshot.get("snapshot_fingerprint") != _fingerprint(snapshot):
        raise ValueError("D2TR snapshot fingerprint mismatch")
    markets: Dict[str, Any] = {}
    for request in snapshot.get("requests") or []:
        market = str(request.get("market") or "").upper()
        endpoint = str(request.get("endpoint") or "")
        target = markets.setdefault(
            market,
            {
                "status": "SOURCE_BLOCKED",
                "volatility": None,
                "format_groups": {},
                "topics": {},
                "formats": {},
                "categories": {},
            },
        )
        signals = request.get("signals") or []
        signals = [
            {**row, "source_generated_at": request.get("generated_at")}
            for row in signals
            if isinstance(row, dict)
        ]
        if request.get("source_status") == "AVAILABLE":
            target["status"] = "AVAILABLE"
        if endpoint == "volatility":
            target["volatility"] = signals[0] if signals else None
        else:
            field = {
                "category-volatility": "format_groups",
                "topic-volatility": "topics",
                "format-interest": "formats",
                "categories": "categories",
            }.get(endpoint)
            if field:
                target[field] = {
                    str(row.get("name") or ""): row
                    for row in signals
                    if str(row.get("name") or "")
                }
    context: Dict[str, Any] = {
        "contract_version": CONTEXT_CONTRACT_VERSION,
        "provider": "d2tr_public_discover",
        "official_google_source": False,
        "may_create_google_demand": False,
        "may_create_realtime_hot": False,
        "credentials_included": False,
        "execution_id": snapshot.get("execution_id"),
        "observed_at": snapshot.get("observed_at"),
        "expires_at": snapshot.get("expires_at"),
        "status": snapshot.get("status"),
        "source_snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "markets": markets,
    }
    context["snapshot_fingerprint"] = _fingerprint(context)
    return context


def _top_signal(request: Dict[str, Any]) -> Dict[str, Any]:
    signals = list(request.get("signals") or [])
    if not signals:
        return {
            "name": "ALL" if request.get("endpoint") == "volatility" else "NO_SIGNAL",
            "status": request.get("source_status"),
        }
    return max(
        signals,
        key=lambda row: (
            row.get("status") == "AVAILABLE",
            float(row.get("current_value") or float("-inf")),
            str(row.get("name") or ""),
        ),
    )


def base_rows(snapshot: Dict[str, Any], evidence_path: Path) -> List[Dict[str, Any]]:
    if snapshot.get("snapshot_fingerprint") != _fingerprint(snapshot):
        raise ValueError("D2TR snapshot fingerprint mismatch")
    observed = _parse_datetime(snapshot.get("observed_at"))
    expires = _parse_datetime(snapshot.get("expires_at"))
    if observed is None or expires is None:
        raise ValueError("D2TR snapshot timestamps are invalid")
    rows = []
    for request in snapshot.get("requests") or []:
        signal = _top_signal(request)
        generated = _parse_datetime(request.get("generated_at"))
        key = ":".join(
            (
                "d2tr",
                str(snapshot.get("execution_id") or ""),
                str(request.get("market") or ""),
                str(request.get("endpoint") or ""),
            )
        )
        fields: Dict[str, Any] = {
            "快照ID": key,
            "数据源": "D2TR Public",
            "市场": request.get("market"),
            "接口": request.get("endpoint"),
            "信号对象": signal.get("name"),
            "观测时间": observed.astimezone(HKT).strftime("%Y-%m-%d %H:%M:%S"),
            "过期时间": expires.astimezone(HKT).strftime("%Y-%m-%d %H:%M:%S"),
            "数据状态": request.get("source_status"),
            "趋势": signal.get("trend") or "UNKNOWN",
            "运行状态": signal.get("state") or "UNKNOWN",
            "置信度": signal.get("confidence") or "UNKNOWN",
            "Snapshot Fingerprint": snapshot.get("snapshot_fingerprint"),
            "Source URL": request.get("source_url"),
            "本地证据路径": str(evidence_path),
            "执行ID": snapshot.get("execution_id"),
            "Raw Payload Hash": request.get("raw_payload_hash"),
        }
        optional = {
            "源生成时间": generated.astimezone(HKT).strftime("%Y-%m-%d %H:%M:%S")
            if generated
            else None,
            "当前值": signal.get("current_value"),
            "基线值": signal.get("baseline_value"),
            "变化率": signal.get("change_value"),
            "估算曝光": signal.get("estimated_impressions"),
            "发布数": signal.get("publications"),
            "发布者数": signal.get("publishers"),
        }
        fields.update({key: value for key, value in optional.items() if value is not None})
        rows.append(fields)
    return rows


class LarkClient:
    def __init__(self, base_token: str):
        self.base_token = base_token
        self.env = dict(os.environ)
        self.env.setdefault("LARK_CONFIG_DIR", str(Path.home() / ".lark-cli"))

    def run(self, args: Sequence[str]) -> Dict[str, Any]:
        command = ["lark-cli", *args, "--format", "json", "--as", "user"]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=self.env,
                timeout=LARK_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            raise D2TRMonitorError("SOURCE_BLOCKED: lark-cli timeout") from error
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as error:
            raise D2TRMonitorError("SOURCE_BLOCKED: invalid lark-cli response") from error
        if result.returncode != 0 or not payload.get("ok"):
            message = (payload.get("error") or {}).get("message") or result.stderr
            raise D2TRMonitorError(f"SOURCE_BLOCKED: lark-cli failed: {message}")
        return payload

    def list_by_execution(self, table_id: str, execution_id: str) -> List[Dict[str, Any]]:
        return self.exact_records(
            table_id, "执行ID", execution_id, ("快照ID", "执行ID")
        )

    def exact_records(
        self,
        table_id: str,
        key_field: str,
        key_value: str,
        fields: Sequence[str],
    ) -> List[Dict[str, Any]]:
        filter_json = json.dumps(
            {"logic": "and", "conditions": [[key_field, "==", key_value]]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        args: List[str] = [
            "base", "+record-list", "--base-token", self.base_token,
            "--table-id", table_id, "--filter-json", filter_json, "--limit", "200",
        ]
        for field in fields:
            args.extend(("--field-id", field))
        payload = self.run(tuple(args)).get("data") or {}
        names = payload.get("fields") or []
        return [
            {"record_id": record_id, "fields": dict(zip(names, values))}
            for record_id, values in zip(
                payload.get("record_id_list") or [], payload.get("data") or []
            )
        ]

    def upsert_one(
        self, table_id: str, fields: Dict[str, Any], record_id: Optional[str] = None
    ) -> str:
        args: List[str] = [
            "base", "+record-upsert", "--base-token", self.base_token,
            "--table-id", table_id, "--json",
            json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
        ]
        if record_id:
            args.extend(("--record-id", record_id))
        payload = self.run(tuple(args)).get("data") or {}
        record = payload.get("record") or {}
        return str(
            payload.get("record_id")
            or payload.get("recordId")
            or record.get("record_id")
            or record.get("recordId")
            or record_id
            or ""
        )

    def batch_create(self, table_id: str, rows: Sequence[Dict[str, Any]]) -> List[str]:
        if not rows:
            return []
        payload = self.run(
            (
                "base", "+record-batch-create", "--base-token", self.base_token,
                "--table-id", table_id, "--json",
                json.dumps({"create_records": list(rows)}, ensure_ascii=False, separators=(",", ":")),
            )
        ).get("data") or {}
        records = payload.get("records") or payload.get("record_list") or []
        ids = payload.get("record_id_list") or []
        if ids:
            return [str(value) for value in ids]
        return [
            str(row.get("record_id") or row.get("recordId") or "")
            for row in records if isinstance(row, dict)
        ]

    def _filtered_rows(
        self, table_id: str, filter_json: Dict[str, Any], fields: Sequence[str]
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        offset = 0
        while True:
            args: List[str] = [
                "base", "+record-list", "--base-token", self.base_token,
                "--table-id", table_id, "--filter-json",
                json.dumps(filter_json, ensure_ascii=False, separators=(",", ":")),
                "--limit", "200", "--offset", str(offset),
            ]
            for field in fields:
                args.extend(("--field-id", field))
            payload = self.run(tuple(args)).get("data") or {}
            names = payload.get("fields") or []
            page_ids = [str(value) for value in payload.get("record_id_list") or []]
            page_values = payload.get("data") or []
            rows.extend(
                {
                    "record_id": record_id,
                    "fields": dict(zip(names, values)),
                }
                for record_id, values in zip(page_ids, page_values)
            )
            if len(page_ids) < 200:
                break
            offset += len(page_ids)
        return rows

    def list_expired(self, table_id: str, now: dt.datetime) -> List[str]:
        now_utc = now.astimezone(UTC)
        local_date = now_utc.astimezone(HKT).date().isoformat()
        definitely_old = self._filtered_rows(
            table_id,
            {
                "logic": "and",
                "conditions": [["过期时间", "<", f"ExactDate({local_date})"]],
            },
            ("快照ID", "过期时间"),
        )
        boundary = self._filtered_rows(
            table_id,
            {
                "logic": "and",
                "conditions": [["过期时间", "==", f"ExactDate({local_date})"]],
            },
            ("快照ID", "过期时间"),
        )
        expired = [str(row["record_id"]) for row in definitely_old]
        for row in boundary:
            expires_at = _parse_base_datetime(
                _scalar((row.get("fields") or {}).get("过期时间"))
            )
            if expires_at is not None and expires_at < now_utc:
                expired.append(str(row["record_id"]))
        return sorted(set(expired))

    def delete(self, table_id: str, record_ids: Sequence[str]) -> None:
        for start in range(0, len(record_ids), 500):
            chunk = list(record_ids[start:start + 500])
            if not chunk:
                continue
            self.run(
                (
                    "base", "+record-delete", "--base-token", self.base_token,
                    "--table-id", table_id, "--json",
                    json.dumps({"record_id_list": chunk}, separators=(",", ":")), "--yes",
                )
            )


def handoff_rows(
    client: LarkClient,
    table_id: str,
    snapshot: Dict[str, Any],
    evidence_path: Path,
) -> Dict[str, Any]:
    expected = base_rows(snapshot, evidence_path)
    existing = client.list_by_execution(table_id, str(snapshot.get("execution_id") or ""))
    existing_by_key: Dict[str, Dict[str, Any]] = {}
    for row in existing:
        key = str((row.get("fields") or {}).get("快照ID") or "")
        if key in existing_by_key:
            raise D2TRMonitorError(f"HANDOFF_INCOMPLETE: duplicate 快照ID {key}")
        existing_by_key[key] = row
    expected_keys = {str(row["快照ID"]) for row in expected}
    unexpected = sorted(set(existing_by_key) - expected_keys)
    if unexpected:
        raise D2TRMonitorError(
            "HANDOFF_INCOMPLETE: existing execution contains unexpected snapshot keys"
        )
    missing = [row for row in expected if str(row["快照ID"]) not in existing_by_key]
    created_ids = client.batch_create(table_id, missing)
    delays = (0.0, 0.25, 0.75, 1.5)
    readback: List[Dict[str, Any]] = []
    for delay in delays:
        if delay:
            time.sleep(delay)
        readback = client.list_by_execution(
            table_id, str(snapshot.get("execution_id") or "")
        )
        if {str((row.get("fields") or {}).get("快照ID") or "") for row in readback} == expected_keys:
            break
    else:
        raise D2TRMonitorError("HANDOFF_INCOMPLETE: snapshot readback mismatch")
    return {
        "status": "SUCCESS",
        "execution_id": snapshot.get("execution_id"),
        "table_id": table_id,
        "expected_count": len(expected),
        "existing_count": len(existing),
        "created_count": len(missing),
        "created_record_ids": created_ids,
        "readback_count": len(readback),
        "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
    }


def _scalar(value: Any) -> Any:
    if isinstance(value, list) and len(value) == 1 and not isinstance(value[0], dict):
        return value[0]
    return value


def handoff_monitor_run(
    client: LarkClient,
    table_id: str,
    snapshot: Dict[str, Any],
    evidence_path: Path,
) -> Dict[str, Any]:
    execution_id = str(snapshot.get("execution_id") or "")
    fields = (
        "执行ID", "运行状态", "执行摘要", "数据源状态", "飞书写入状态", "本地证据路径"
    )
    existing = client.exact_records(table_id, "执行ID", execution_id, fields)
    if len(existing) > 1:
        raise D2TRMonitorError(
            f"HANDOFF_INCOMPLETE: duplicate monitor execution {execution_id}"
        )
    summary = snapshot.get("summary") or {}
    d2tr_summary = (
        f"D2TR 8h pulse: requests={summary.get('request_count', 0)}, "
        f"available={summary.get('available_count', 0)}, "
        f"insufficient_baseline={summary.get('insufficient_baseline_count', 0)}, "
        f"blocked={summary.get('source_blocked_count', 0)}, "
        f"fingerprint={snapshot.get('snapshot_fingerprint')}"
    )
    d2tr_source_state = (
        f"D2TR={snapshot.get('status')}; markets={','.join(snapshot.get('markets') or [])}; "
        "official_google_source=false; demand_authority=false"
    )
    record_id: Optional[str] = None
    if existing:
        record_id = str(existing[0].get("record_id") or "")
        current = existing[0].get("fields") or {}
        current_summary = str(_scalar(current.get("执行摘要")) or "")
        current_sources = str(_scalar(current.get("数据源状态")) or "")
        patch = {
            "执行摘要": (
                current_summary + " | " + d2tr_summary
                if d2tr_summary not in current_summary
                else current_summary
            )[:5000],
            "数据源状态": (
                current_sources + " | " + d2tr_source_state
                if d2tr_source_state not in current_sources
                else current_sources
            )[:5000],
            "飞书写入状态": "SUCCESS",
            "本地证据路径": str(evidence_path),
        }
    else:
        observed = _parse_datetime(snapshot.get("observed_at")) or dt.datetime.now(UTC)
        patch = {
            "执行ID": execution_id,
            "Automation ID": "vertu",
            "执行时间": observed.astimezone(HKT).strftime("%Y-%m-%d %H:%M:%S"),
            "运行状态": (
                "SOURCE_BLOCKED"
                if snapshot.get("status") == "SOURCE_BLOCKED"
                else "NO_ACTIONABLE_CHANGE"
            ),
            "扫描发布批次": 0,
            "扫描文章数": 0,
            "到期节点数": 0,
            "执行摘要": d2tr_summary,
            "数据源状态": d2tr_source_state,
            "下一动作": "下一次 8 小时趋势脉冲；D2TR 仅作合格候选排序上下文",
            "飞书写入状态": "SUCCESS",
            "本地证据路径": str(evidence_path),
        }
    client.upsert_one(table_id, patch, record_id=record_id)
    for delay in (0.0, 0.25, 0.75, 1.5):
        if delay:
            time.sleep(delay)
        readback = client.exact_records(table_id, "执行ID", execution_id, fields)
        if len(readback) == 1:
            readback_fields = readback[0].get("fields") or {}
            if "D2TR 8h pulse" in str(_scalar(readback_fields.get("执行摘要")) or ""):
                return {
                    "status": "SUCCESS",
                    "record_id": readback[0]["record_id"],
                    "created": not bool(existing),
                }
    raise D2TRMonitorError("HANDOFF_INCOMPLETE: monitor-run readback mismatch")


def prune_local(root: Path, cutoff: dt.datetime) -> List[str]:
    removed: List[str] = []
    if not root.exists():
        return removed
    cutoff_utc = cutoff.astimezone(UTC)
    cutoff_date = cutoff_utc.astimezone(HKT).date()
    for date_dir in sorted(root.iterdir()):
        if not date_dir.is_dir():
            continue
        try:
            directory_date = dt.date.fromisoformat(date_dir.name)
        except ValueError:
            continue
        if directory_date < cutoff_date:
            shutil.rmtree(date_dir)
            removed.append(str(date_dir))
            continue
        if directory_date != cutoff_date:
            continue
        # Date directories are coarse; on the boundary day, inspect each
        # immutable run timestamp so retention remains a true rolling 30 days.
        for run_dir in sorted(path for path in date_dir.iterdir() if path.is_dir()):
            snapshot_path = run_dir / "d2tr-snapshot.json"
            if not snapshot_path.exists():
                continue
            try:
                observed_at = _parse_datetime(_load_json(snapshot_path).get("observed_at"))
            except (OSError, json.JSONDecodeError, AttributeError):
                observed_at = None
            if observed_at is not None and observed_at < cutoff_utc:
                shutil.rmtree(run_dir)
                removed.append(str(run_dir))
        if date_dir.exists() and not any(date_dir.iterdir()):
            date_dir.rmdir()
    return removed


def load_schema(path: Path) -> Tuple[str, str, str]:
    payload = _load_json(path)
    base_token = str(payload.get("base_token") or "")
    table_id = str(
        ((payload.get("tables") or {}).get("discover_trend_snapshots") or {}).get("table_id")
        or ""
    )
    monitor_table_id = str(
        ((payload.get("tables") or {}).get("monitor_runs") or {}).get("table_id") or ""
    )
    if not base_token or not table_id or not monitor_table_id:
        raise D2TRMonitorError("schema map is missing D2TR Base coordinates")
    return base_token, table_id, monitor_table_id


def finish_audit(
    client: LarkClient,
    automation_table_id: str,
    start_receipt: Dict[str, Any],
    snapshot: Dict[str, Any],
    handoff: Dict[str, Any],
    cleanup: Dict[str, Any],
    ended_at: dt.datetime,
) -> Dict[str, Any]:
    execution_id = str(start_receipt.get("execution_id") or "")
    record_id = str(start_receipt.get("record_id") or "")
    if (
        not execution_id
        or not record_id
        or start_receipt.get("status") != "运行中"
        or snapshot.get("execution_id") != execution_id
    ):
        raise D2TRMonitorError("invalid canonical start-audit receipt")
    rows = client.exact_records(
        automation_table_id,
        "执行ID",
        execution_id,
        ("执行ID", "执行状态", "下游交接状态"),
    )
    if len(rows) != 1 or rows[0].get("record_id") != record_id:
        raise D2TRMonitorError("canonical audit row identity mismatch")
    current_state = str(_scalar((rows[0].get("fields") or {}).get("执行状态")) or "")
    if current_state != "运行中":
        raise D2TRMonitorError(f"canonical audit row is already terminal: {current_state}")
    handoff_ok = handoff.get("status") == "SUCCESS" and cleanup.get("status") == "SUCCESS"
    source_status = str(snapshot.get("status") or "SOURCE_BLOCKED")
    if not handoff_ok:
        terminal = "部分成功"
        downstream = "HANDOFF_INCOMPLETE"
    elif source_status == "SOURCE_BLOCKED":
        terminal = "来源阻塞"
        downstream = "已交接"
    elif source_status == "PARTIAL":
        terminal = "部分成功"
        downstream = "已交接"
    else:
        terminal = "成功"
        downstream = "已交接"
    summary = snapshot.get("summary") or {}
    fields = {
        "执行状态": terminal,
        "结束时间": ended_at.astimezone(HKT).strftime("%Y-%m-%d %H:%M:%S"),
        "扫描数量": summary.get("request_count") or 0,
        "处理数量": summary.get("request_count") or 0,
        "成功数量": (summary.get("available_count") or 0)
        + (summary.get("insufficient_baseline_count") or 0),
        "阻塞数量": (summary.get("source_blocked_count") or 0)
        + (summary.get("invalid_response_count") or 0),
        "输出摘要": (
            f"D2TR 8h pulse {source_status}; requests={summary.get('request_count', 0)}; "
            f"Base snapshots={handoff.get('readback_count', 0)}; "
            f"expired Base rows deleted={cleanup.get('base_deleted_count', 0)}; "
            f"local directories removed={len(cleanup.get('local_removed') or [])}; "
            "no Google demand/hot label created; no Sanity mutation."
        ),
        "下游交接状态": downstream,
        "外部事务ID": json.dumps(
            {
                "d2tr_snapshot_table_id": handoff.get("table_id"),
                "d2tr_snapshot_created_count": handoff.get("created_count"),
                "monitor_run_record_id": (handoff.get("monitor_run") or {}).get("record_id"),
                "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )[:5000],
        "回销状态": "已记录",
        "重试次数": 0,
        "错误或阻塞原因": (
            None
            if terminal == "成功"
            else f"D2TR source={source_status}; handoff={handoff.get('status')}; cleanup={cleanup.get('status')}"
        ),
        "操作明细": (
            "D2TR public endpoints queried with explicit market scope; null baselines preserved; "
            "snapshot and monitor rows reconciled by deterministic keys; 30-day dedicated trend "
            "retention applied; audit rows preserved."
        ),
    }
    client.upsert_one(
        automation_table_id,
        {key: value for key, value in fields.items() if value is not None},
        record_id=record_id,
    )
    readback = client.exact_records(
        automation_table_id,
        "执行ID",
        execution_id,
        ("执行ID", "执行状态", "下游交接状态", "成功数量", "阻塞数量"),
    )
    if len(readback) != 1 or str(
        _scalar((readback[0].get("fields") or {}).get("执行状态")) or ""
    ) != terminal:
        raise D2TRMonitorError("canonical terminal-audit readback mismatch")
    return {
        "status": terminal,
        "execution_id": execution_id,
        "record_id": record_id,
        "downstream_handoff": downstream,
        "readback": readback[0],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--execution-id", required=True)
    collect.add_argument("--output", required=True, type=Path)
    collect.add_argument("--context-output", required=True, type=Path)
    collect.add_argument("--latest-context-output", type=Path)
    collect.add_argument("--market", action="append", dest="markets")

    activate = subparsers.add_parser("activate-context")
    activate.add_argument("--context", required=True, type=Path)
    activate.add_argument("--output", required=True, type=Path)

    handoff = subparsers.add_parser("handoff")
    handoff.add_argument("--snapshot", required=True, type=Path)
    handoff.add_argument("--schema-map", required=True, type=Path)
    handoff.add_argument("--receipt", required=True, type=Path)

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--root", required=True, type=Path)
    cleanup.add_argument("--schema-map", required=True, type=Path)
    cleanup.add_argument("--receipt", required=True, type=Path)
    cleanup.add_argument("--retention-days", type=int, default=RETENTION_DAYS)

    audit_finish = subparsers.add_parser("audit-finish")
    audit_finish.add_argument("--start-receipt", required=True, type=Path)
    audit_finish.add_argument("--snapshot", required=True, type=Path)
    audit_finish.add_argument("--handoff", required=True, type=Path)
    audit_finish.add_argument("--cleanup", required=True, type=Path)
    audit_finish.add_argument("--schema-map", required=True, type=Path)
    audit_finish.add_argument("--receipt", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "collect":
        snapshot = collect_snapshot(args.execution_id, args.markets or DEFAULT_MARKETS)
        context = build_context(snapshot)
        _write_json(args.output, snapshot)
        _write_json(args.context_output, context)
        if args.latest_context_output is not None:
            _write_json(args.latest_context_output, context)
        return 0
    if args.command == "activate-context":
        context = _load_json(args.context)
        if context.get("contract_version") != CONTEXT_CONTRACT_VERSION:
            raise D2TRMonitorError("context activation contract mismatch")
        if context.get("snapshot_fingerprint") != _fingerprint(context):
            raise D2TRMonitorError("context activation fingerprint mismatch")
        if context.get("status") not in {"AVAILABLE", "PARTIAL"}:
            raise D2TRMonitorError("context activation source is unavailable")
        _write_json(args.output, context)
        return 0
    if args.command == "handoff":
        snapshot = _load_json(args.snapshot)
        base_token, table_id, monitor_table_id = load_schema(args.schema_map)
        client = LarkClient(base_token)
        receipt = handoff_rows(client, table_id, snapshot, args.snapshot)
        receipt["monitor_run"] = handoff_monitor_run(
            client, monitor_table_id, snapshot, args.snapshot
        )
        _write_json(args.receipt, receipt)
        return 0

    if args.command == "audit-finish":
        schema = _load_json(args.schema_map)
        base_token = str(schema.get("base_token") or "")
        automation_table_id = str(
            ((schema.get("tables") or {}).get("automation_runs") or {}).get("table_id")
            or ""
        )
        if not base_token or not automation_table_id:
            raise D2TRMonitorError("schema map is missing automation audit coordinates")
        receipt = finish_audit(
            LarkClient(base_token),
            automation_table_id,
            _load_json(args.start_receipt),
            _load_json(args.snapshot),
            _load_json(args.handoff),
            _load_json(args.cleanup),
            dt.datetime.now(UTC),
        )
        _write_json(args.receipt, receipt)
        return 0

    cleanup_now = dt.datetime.now(UTC)
    cutoff = cleanup_now - dt.timedelta(days=args.retention_days)
    base_token, table_id, _monitor_table_id = load_schema(args.schema_map)
    client = LarkClient(base_token)
    expired_ids = client.list_expired(table_id, cleanup_now)
    client.delete(table_id, expired_ids)
    receipt = {
        "status": "SUCCESS",
        "executed_at": _iso(dt.datetime.now(UTC)),
        "retention_days": args.retention_days,
        "cutoff": _iso(cutoff),
        "local_removed": prune_local(args.root, cutoff),
        "base_deleted_count": len(expired_ids),
        "base_deleted_record_ids": expired_ids,
        "audit_rows_deleted": 0,
    }
    _write_json(args.receipt, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

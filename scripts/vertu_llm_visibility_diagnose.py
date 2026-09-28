#!/usr/bin/env python3
"""Create a read-only post-publication LLM visibility diagnosis.

The input is a normalised observation panel produced by a dedicated agent or
connector.  Raw private model responses are intentionally unnecessary.  A
missing citation is an observation, never proof that the page is not indexed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlsplit, urlunsplit


UTC = dt.timezone.utc
CONTRACT_VERSION = "llm-visibility-diagnosis-v1"
AVAILABLE_STATES = {"AVAILABLE", "OK", "SUCCESS"}


class LLMVisibilityError(RuntimeError):
    pass


def _iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _normalise_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parts = urlsplit(text)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fingerprint(payload: Dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "diagnosis_fingerprint"}
    return _hash_payload(material)


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 6) if denominator else None


def _base_datetime(value: Any) -> Optional[str]:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _normalise_observations(payload: Dict[str, Any], canonical_url: str) -> List[Dict[str, Any]]:
    raw_rows = payload.get("observations")
    if not isinstance(raw_rows, list):
        raise LLMVisibilityError("input must contain observations[]")
    canonical = _normalise_url(canonical_url)
    domain = urlsplit(canonical).netloc
    rows: List[Dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        citations = sorted(
            {
                _normalise_url(value)
                for value in raw.get("citations") or []
                if _normalise_url(value)
            }
        )
        state = str(raw.get("source_status") or "SOURCE_UNAVAILABLE").upper()
        rows.append(
            {
                "provider": str(raw.get("provider") or "").strip(),
                "model": str(raw.get("model") or "").strip(),
                "model_version": str(raw.get("model_version") or "unknown").strip(),
                "prompt_id": str(raw.get("prompt_id") or "").strip(),
                "market": str(raw.get("market") or "").strip().upper(),
                "observed_at": raw.get("observed_at"),
                "source_status": state,
                "citations": citations,
                "citation_observed": bool(citations),
                "canonical_citation_observed": canonical in citations,
                "vertu_domain_citation_observed": any(
                    urlsplit(value).netloc == domain for value in citations
                ),
                "brand_mention_observed": bool(raw.get("brand_mention_observed")),
            }
        )
    return rows


def _crawl_access(payload: Dict[str, Any], canonical_url: str) -> Dict[str, Any]:
    raw = payload.get("crawl_access") or {}
    if not isinstance(raw, dict):
        raw = {}
    try:
        status_code = int(raw.get("http_status"))
    except (TypeError, ValueError):
        status_code = None
    robots_allowed = raw.get("robots_allowed")
    noindex = raw.get("noindex")
    canonical_match = _normalise_url(raw.get("canonical_url")) == _normalise_url(canonical_url)
    proxy_pass = (
        status_code == 200
        and robots_allowed is True
        and noindex is False
        and canonical_match
    )
    blocked = (
        status_code in {401, 403, 429, 451, 500, 502, 503, 504}
        or robots_allowed is False
        or noindex is True
    )
    return {
        "canonical_url": canonical_url,
        "observed_at": raw.get("observed_at"),
        "http_status": status_code,
        "robots_allowed": robots_allowed,
        "noindex": noindex,
        "canonical_match": canonical_match,
        "indexability_proxy_pass": proxy_pass,
        "crawl_blocked": blocked,
        "proof_of_llm_indexation": False,
    }


def _prompt_variance(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[int]] = defaultdict(list)
    for row in rows:
        if row["source_status"] in AVAILABLE_STATES and row["prompt_id"]:
            grouped[row["prompt_id"]].append(int(row["vertu_domain_citation_observed"]))
    rates = {
        prompt_id: round(sum(values) / len(values), 6)
        for prompt_id, values in sorted(grouped.items())
        if values
    }
    spread = round(max(rates.values()) - min(rates.values()), 6) if len(rates) >= 2 else None
    return {
        "prompt_citation_rates": rates,
        "rate_spread": spread,
        "high": spread is not None and spread >= 0.5,
    }


def build_diagnosis(
    payload: Dict[str, Any], now: Optional[dt.datetime] = None
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise LLMVisibilityError("input must be an object")
    canonical_url = _normalise_url(payload.get("canonical_url"))
    if not canonical_url:
        raise LLMVisibilityError("canonical_url is required")
    observations = _normalise_observations(payload, canonical_url)
    crawl = _crawl_access(payload, canonical_url)
    available = [row for row in observations if row["source_status"] in AVAILABLE_STATES]
    citation_count = sum(row["vertu_domain_citation_observed"] for row in available)
    canonical_count = sum(row["canonical_citation_observed"] for row in available)
    brand_count = sum(row["brand_mention_observed"] for row in available)
    model_keys = {
        (row["provider"], row["model"], row["model_version"])
        for row in available
        if row["provider"] and row["model"]
    }
    variance = _prompt_variance(available)
    states: List[str] = []
    if crawl["crawl_blocked"]:
        states.append("CRAWL_BLOCKED")
    elif crawl["indexability_proxy_pass"]:
        states.append("INDEXABILITY_PROXY_PASS")
    if not available:
        states.append("SOURCE_UNAVAILABLE")
    elif citation_count:
        states.append("CITATION_OBSERVED")
    else:
        states.append("NO_CITATION_OBSERVED")
    if variance["high"]:
        states.append("PROMPT_VARIANCE_HIGH")

    summary = {
        "observation_count": len(observations),
        "available_observation_count": len(available),
        "model_coverage_count": len(model_keys),
        "prompt_coverage_count": len({row["prompt_id"] for row in available if row["prompt_id"]}),
        "market_coverage": sorted({row["market"] for row in available if row["market"]}),
        "vertu_citation_count": citation_count,
        "canonical_citation_count": canonical_count,
        "brand_mention_count": brand_count,
        "citation_rate": _rate(citation_count, len(available)),
        "canonical_citation_rate": _rate(canonical_count, len(available)),
        "brand_mention_rate": _rate(brand_count, len(available)),
        "prompt_variance": variance,
    }
    diagnosis: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "article_key": payload.get("article_key"),
        "publication_run_id": payload.get("publication_run_id"),
        "canonical_url": canonical_url,
        "observed_at": _iso(now or dt.datetime.now(tz=UTC)),
        "states": states,
        "summary": summary,
        "crawl_access_fingerprint": _hash_payload(crawl),
        "observations_fingerprint": _hash_payload(observations),
        "read_only": True,
        "may_mutate_sanity": False,
        "may_create_topic_demand": False,
        "may_change_learning_prior": False,
        "single_negative_proves_not_indexed": False,
        "recommended_action": (
            "INVESTIGATE_CRAWL_ACCESS"
            if crawl["crawl_blocked"]
            else "COLLECT_MORE_OBSERVATIONS"
            if not available or not citation_count or variance["high"]
            else "OBSERVE_UNTIL_GOVERNED_REVIEW"
        ),
    }
    diagnosis["diagnosis_fingerprint"] = _fingerprint(diagnosis)
    observations_output = {
        "contract_version": CONTRACT_VERSION,
        "canonical_url": canonical_url,
        "diagnosis_fingerprint": diagnosis["diagnosis_fingerprint"],
        "observations": observations,
    }
    return diagnosis, crawl, observations_output


def build_base_handoff_row(
    payload: Dict[str, Any],
    diagnosis: Dict[str, Any],
    evidence_path: str,
    *,
    integration_config: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build the deterministic canonical Base 内容复盘 payload.

    This function deliberately produces a write request instead of performing
    the write.  The scheduled diagnostic agent remains responsible for the
    start-ledger gate, linked article resolution, Base mutation and exact
    readback.
    """
    article_key = str(diagnosis.get("article_key") or "").strip()
    if not article_key:
        raise LLMVisibilityError("article_key is required for Base handoff")
    states = list(diagnosis.get("states") or [])
    summary = diagnosis.get("summary") or {}
    available_count = int(summary.get("available_observation_count") or 0)
    source_states = {
        str(row.get("source_status") or "SOURCE_UNAVAILABLE").upper()
        for row in payload.get("observations") or []
        if isinstance(row, dict)
    }
    if available_count:
        source_status = "AVAILABLE"
    elif "SOURCE_BLOCKED" in source_states:
        source_status = "SOURCE_BLOCKED"
    else:
        source_status = "SOURCE_UNAVAILABLE"

    panel_id = str(payload.get("prompt_panel_id") or "").strip()
    if not panel_id:
        panel_id = "llm-panel-" + diagnosis["diagnosis_fingerprint"][:16]
    checkpoint = str(payload.get("checkpoint") or "T+72h").strip()
    if checkpoint not in {"T+72h", "D+7", "D+28"}:
        raise LLMVisibilityError("checkpoint must be T+72h, D+7 or D+28")
    primary_diagnosis = next(
        (
            state
            for state in (
                "CRAWL_BLOCKED",
                "SOURCE_UNAVAILABLE",
                "PROMPT_VARIANCE_HIGH",
                "CITATION_OBSERVED",
                "NO_CITATION_OBSERVED",
                "INDEXABILITY_PROXY_PASS",
            )
            if state in states
        ),
        "SOURCE_UNAVAILABLE",
    )
    action = (
        "技术修复"
        if "CRAWL_BLOCKED" in states
        else "保持不变"
        if "CITATION_OBSERVED" in states and "PROMPT_VARIANCE_HIGH" not in states
        else "等待数据"
    )
    review_id = f"llm-visibility:{article_key}:{checkpoint}:{panel_id}"
    config = integration_config or {}
    required_config = ("base_token", "checkpoint_table_id", "article_table_id")
    missing_config = [key for key in required_config
                      if not str(config.get(key) or "").strip()
                      or str(config[key]).startswith(("${", "CONFIGURE_"))]
    return {
        "contract_version": "llm-visibility-base-handoff-v1",
        "configuration_status": "MISSING_CONFIGURATION" if missing_config else "CONFIGURED",
        "missing_configuration": missing_config,
        "authorises_write": False,
        "base_token": None if missing_config else config["base_token"],
        "table_id": None if missing_config else config["checkpoint_table_id"],
        "business_key": {"field": "复盘ID", "value": review_id},
        "requires_link_resolution": {
            "table_id": None if missing_config else config["article_table_id"],
            "field": "Article Key",
            "value": article_key,
            "target_field": "关联文章",
        },
        "source_observed_at": diagnosis.get("observed_at"),
        "fields": {
            "复盘ID": review_id,
            "Article Key": article_key,
            "文章 URL": diagnosis.get("canonical_url"),
            "观察日期": _base_datetime(diagnosis.get("observed_at")),
            "复盘节点": checkpoint,
            "记录来源": "LLM诊断",
            "诊断类型": "LLM Visibility",
            "Prompt Panel ID": panel_id,
            "模型覆盖数": int(summary.get("model_coverage_count") or 0),
            "引用数": int(summary.get("vertu_citation_count") or 0),
            "品牌提及数": int(summary.get("brand_mention_count") or 0),
            "观察指纹": diagnosis.get("diagnosis_fingerprint"),
            "来源状态": source_status,
            "诊断": primary_diagnosis,
            "建议动作": action,
            "状态": "待观察" if action == "等待数据" else "待优化" if action == "技术修复" else "保持",
            "数据成熟度": "PRELIMINARY",
            "证据路径": evidence_path,
            "复盘结论": ", ".join(states),
        },
        "requires_exact_readback": True,
        "may_mutate_sanity": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-handoff-output", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    payload = _load_json(args.input)
    diagnosis, crawl, observations = build_diagnosis(payload)
    _write_json(args.output_dir / "crawl-access.json", crawl)
    _write_json(args.output_dir / "llm-citation-observations.json", observations)
    diagnosis_path = args.output_dir / "llm-visibility-diagnosis.json"
    _write_json(diagnosis_path, diagnosis)
    if args.base_handoff_output:
        _write_json(
            args.base_handoff_output,
            build_base_handoff_row(payload, diagnosis, str(diagnosis_path)),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

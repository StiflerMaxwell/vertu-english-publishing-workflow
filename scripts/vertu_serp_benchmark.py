#!/usr/bin/env python3
"""Validate post-selection SERP evidence and build a differentiation brief.

This tool consumes a normalised export from an authorised SERP provider or a
reproducible browser research run.  It does not scrape Google and does not copy
ranking-page prose.  Its only production role is a post-selection,
pre-writing gate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse


UTC = dt.timezone.utc
CONTRACT_VERSION = "serp-benchmark-v1"
MIN_RESULT_SUMMARIES = 5
MIN_BODY_EXTRACTS = 3
GENERIC_VALUE_DELTAS = {
    "better article",
    "more comprehensive",
    "more detail",
    "higher quality",
    "unique insights",
    "vertu perspective",
}


class SerpBenchmarkError(RuntimeError):
    pass


def _iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fingerprint(payload: Dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "benchmark_fingerprint"}
    return _hash_payload(material)


def _normalise_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _heading_key(value: Any) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", _normalise_text(value))
    return " ".join(text.split())


def _is_accessible_body(result: Dict[str, Any]) -> bool:
    status = result.get("status_code")
    try:
        status_ok = int(status) == 200
    except (TypeError, ValueError):
        status_ok = False
    headings = result.get("headings")
    word_count = result.get("word_count")
    try:
        has_words = int(word_count or 0) >= 300
    except (TypeError, ValueError):
        has_words = False
    return status_ok and isinstance(headings, list) and bool(headings) and has_words


def _value_delta_is_concrete(value: str) -> bool:
    normalised = _normalise_text(value)
    if len(normalised) < 40 or normalised in GENERIC_VALUE_DELTAS:
        return False
    concrete_terms = (
        "table",
        "matrix",
        "timeline",
        "checklist",
        "dataset",
        "calculation",
        "scenario",
        "framework",
        "comparison",
        "primary source",
        "decision",
        "verified",
        "country",
        "market",
        "cost",
        "risk",
    )
    return any(term in normalised for term in concrete_terms)


def _required_value_object_types(value: str) -> List[str]:
    normalised = _normalise_text(value)
    mappings = {
        "table": ("table", "matrix", "comparison"),
        "timeline": ("timeline",),
        "checklist": ("checklist", "decision tree", "framework"),
        "calculation": ("calculation", "cost", "scenario"),
        "market_comparison": ("country", "market"),
        "risk_analysis": ("risk",),
        "primary_evidence_synthesis": ("primary source", "dataset", "verified"),
    }
    return [
        name
        for name, terms in mappings.items()
        if any(term in normalised for term in terms)
    ]


def _normalise_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise SerpBenchmarkError("input must contain results[]")
    results: List[Dict[str, Any]] = []
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not url or not title:
            continue
        results.append(
            {
                "rank": raw.get("rank"),
                "title": title,
                "url": url,
                "domain": urlparse(url).netloc.lower(),
                "snippet": str(raw.get("snippet") or "").strip(),
                "status_code": raw.get("status_code"),
                "published_at": raw.get("published_at"),
                "headings": [str(item).strip() for item in raw.get("headings") or [] if str(item).strip()],
                "word_count": raw.get("word_count"),
                "format_type": str(raw.get("format_type") or "unknown").strip(),
                "value_objects": [
                    str(item).strip()
                    for item in raw.get("value_objects") or []
                    if str(item).strip()
                ],
                "source_type": str(raw.get("source_type") or "publisher").strip(),
            }
        )
    return results


def _anatomy(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(results)
    accessible = [row for row in rows if _is_accessible_body(row)]
    format_counts = Counter(row["format_type"] for row in rows)
    value_counts = Counter(value for row in accessible for value in row["value_objects"])
    heading_counts = Counter(
        key
        for row in accessible
        for key in (_heading_key(heading) for heading in row["headings"])
        if key
    )
    repeated_headings = [
        {"heading_pattern": key, "page_count": count}
        for key, count in heading_counts.most_common()
        if count >= 2
    ]
    return {
        "result_count": len(rows),
        "accessible_body_count": len(accessible),
        "independent_domain_count": len({row["domain"] for row in rows if row["domain"]}),
        "format_distribution": dict(sorted(format_counts.items())),
        "value_object_distribution": dict(sorted(value_counts.items())),
        "repeated_heading_patterns": repeated_headings,
        "median_accessible_word_count": _median_int(
            [row.get("word_count") for row in accessible]
        ),
    }


def _median_int(values: Iterable[Any]) -> Optional[int]:
    parsed: List[int] = []
    for value in values:
        try:
            parsed.append(int(value))
        except (TypeError, ValueError):
            continue
    if not parsed:
        return None
    ordered = sorted(parsed)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return round((ordered[middle - 1] + ordered[middle]) / 2)


def build_benchmark(
    payload: Dict[str, Any],
    selected_query: str,
    selected_intent: str,
    proposed_query: str,
    proposed_intent: str,
    original_value_delta: str,
    now: Optional[dt.datetime] = None,
    min_results: int = MIN_RESULT_SUMMARIES,
    min_bodies: int = MIN_BODY_EXTRACTS,
) -> tuple[Dict[str, Any], Dict[str, Any], str]:
    if not isinstance(payload, dict):
        raise SerpBenchmarkError("input must be an object")
    results = _normalise_results(payload)
    anatomy = _anatomy(results)
    exact_context = {
        "query": str(payload.get("query") or "").strip(),
        "market": str(payload.get("market") or "").strip().upper(),
        "language": str(payload.get("language") or "").strip(),
        "device": str(payload.get("device") or "").strip().lower(),
        "source_type": str(payload.get("source_type") or "normalised_export").strip(),
        "observed_at": payload.get("observed_at"),
    }
    context_valid = bool(
        exact_context["query"]
        and exact_context["market"]
        and exact_context["language"]
        and exact_context["device"] in {"mobile", "desktop"}
    )
    query_matches_export = _normalise_text(exact_context["query"]) == _normalise_text(selected_query)
    reframe = (
        _normalise_text(proposed_query) != _normalise_text(selected_query)
        or _normalise_text(proposed_intent) != _normalise_text(selected_intent)
    )
    source_sufficient = (
        context_valid
        and query_matches_export
        and anatomy["result_count"] >= min_results
        and anatomy["accessible_body_count"] >= min_bodies
        and anatomy["independent_domain_count"] >= min_bodies
    )
    if not source_sufficient:
        verdict = "SERP_BENCHMARK_SOURCE_BLOCKED"
    elif reframe:
        verdict = "BENCHMARK_REFRAME"
    elif not _value_delta_is_concrete(original_value_delta):
        verdict = "BENCHMARK_REPLACE"
    else:
        verdict = "BENCHMARK_PASS"

    benchmark: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "verdict": verdict,
        "observed_at": _iso(now or dt.datetime.now(tz=UTC)),
        "selected_query": selected_query,
        "selected_intent": selected_intent,
        "proposed_query": proposed_query,
        "proposed_intent": proposed_intent,
        "exact_context": exact_context,
        "source_sufficient": source_sufficient,
        "query_matches_export": query_matches_export,
        "original_value_delta": original_value_delta,
        "original_value_delta_concrete": _value_delta_is_concrete(original_value_delta),
        "required_value_object_types": _required_value_object_types(original_value_delta),
        "minimum_result_summaries": min_results,
        "minimum_body_extracts": min_bodies,
        "result_set_fingerprint": _hash_payload(results),
        "anatomy_fingerprint": _hash_payload(anatomy),
        "anatomy": anatomy,
        "copying_permitted": False,
        "next_stage": {
            "BENCHMARK_PASS": "EVIDENCE_PACK",
            "BENCHMARK_REFRAME": "RETURN_TO_SCORING",
            "BENCHMARK_REPLACE": "SELECT_REPLACEMENT",
            "SERP_BENCHMARK_SOURCE_BLOCKED": "STOP_DRAFTING",
        }[verdict],
    }
    benchmark["benchmark_fingerprint"] = _fingerprint(benchmark)
    anatomy_output = {
        "contract_version": CONTRACT_VERSION,
        "benchmark_fingerprint": benchmark["benchmark_fingerprint"],
        "query": exact_context["query"],
        "market": exact_context["market"],
        **anatomy,
    }
    brief = render_brief(benchmark, anatomy_output)
    return benchmark, anatomy_output, brief


def render_brief(benchmark: Dict[str, Any], anatomy: Dict[str, Any]) -> str:
    format_lines = [
        f"- {name}: {count} result(s)"
        for name, count in anatomy.get("format_distribution", {}).items()
    ] or ["- No reliable format distribution available."]
    heading_lines = [
        f"- {row['heading_pattern']} ({row['page_count']} pages)"
        for row in anatomy.get("repeated_heading_patterns", [])[:10]
    ] or ["- No repeated heading pattern met the evidence threshold."]
    return "\n".join(
        [
            "# Content differentiation brief",
            "",
            f"- Contract: `{CONTRACT_VERSION}`",
            f"- Verdict: `{benchmark['verdict']}`",
            f"- Benchmark fingerprint: `{benchmark['benchmark_fingerprint']}`",
            f"- Query: {benchmark['selected_query']}",
            f"- Intent: {benchmark['selected_intent']}",
            f"- Market: {benchmark['exact_context']['market']}",
            "",
            "## Ranking-page anatomy",
            "",
            *format_lines,
            "",
            "## Repeated coverage patterns",
            "",
            *heading_lines,
            "",
            "## Required original value",
            "",
            benchmark["original_value_delta"] or "No acceptable original-value delta supplied.",
            "",
            "## Writing boundary",
            "",
            "Use the observed structure to understand reader expectations. Do not copy wording, paragraph order, proprietary data or unsupported claims. The final article must visibly deliver the required original value and cite its own primary evidence.",
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--selected-query", required=True)
    parser.add_argument("--selected-intent", required=True)
    parser.add_argument("--proposed-query", required=True)
    parser.add_argument("--proposed-intent", required=True)
    parser.add_argument("--original-value-delta", required=True)
    parser.add_argument("--benchmark-output", type=Path, required=True)
    parser.add_argument("--anatomy-output", type=Path, required=True)
    parser.add_argument("--brief-output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    benchmark, anatomy, brief = build_benchmark(
        _load_json(args.input),
        args.selected_query,
        args.selected_intent,
        args.proposed_query,
        args.proposed_intent,
        args.original_value_delta,
    )
    _write_json(args.benchmark_output, benchmark)
    _write_json(args.anatomy_output, anatomy)
    _write_text(args.brief_output, brief)
    return 0 if benchmark["verdict"] == "BENCHMARK_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

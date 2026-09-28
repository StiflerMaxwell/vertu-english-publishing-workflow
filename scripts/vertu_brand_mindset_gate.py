#!/usr/bin/env python3
"""Deterministic pre-score VERTU brand-mindset eligibility gate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


CONTRACT_VERSION = "brand-mindset-fit-v1"
DIMENSIONS = (
    "audience_overlap",
    "mindset_overlap",
    "editorial_right_to_win",
)
DIMENSION_STATUSES = {
    "PASS",
    "FAIL",
    "SOURCE_UNAVAILABLE",
    "INSUFFICIENT_SAMPLE",
    "NOT_APPLICABLE",
}
HARD_CONFLICTS = {
    "COMMODITY_LIFESTYLE_MISMATCH",
    "FORCED_BRAND_ASSOCIATION",
    "PRICE_ONLY_LUXURY_LABEL",
    "OUTSIDE_BRAND_MINDSPACE",
}
AUTHORITY_STORY_MODE = "LUXURY_AUTHORITY_STORY"
AUTHORITY_EVIDENCE_TYPES = {
    "VERIFIED_PRICE_OR_TRANSACTION",
    "MATERIAL_OR_CRAFT",
    "SCARCITY_OR_OWNERSHIP",
}


def _fingerprint(payload: Any) -> str:
    if isinstance(payload, dict):
        clean = copy.deepcopy(payload)
        clean.pop("fingerprint", None)
        clean.pop("snapshot_fingerprint", None)
    else:
        clean = payload
    encoded = json.dumps(
        clean,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean_refs(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _dimension_result(
    name: str, block: Any, errors: List[str]
) -> Tuple[Dict[str, Any], bool]:
    if not isinstance(block, dict):
        errors.append("missing_dimension:%s" % name)
        return {
            "status": "SOURCE_UNAVAILABLE",
            "rationale": "",
            "evidence_refs": [],
            "passes": False,
        }, False

    status = str(block.get("status") or "").strip().upper()
    rationale = str(block.get("rationale") or "").strip()
    refs = _clean_refs(block.get("evidence_refs"))
    if status not in DIMENSION_STATUSES:
        errors.append("invalid_dimension_status:%s" % name)
        status = "SOURCE_UNAVAILABLE"
    passes = status == "PASS" and bool(rationale) and bool(refs)
    if status == "PASS" and not rationale:
        errors.append("missing_dimension_rationale:%s" % name)
    if status == "PASS" and not refs:
        errors.append("missing_dimension_evidence_refs:%s" % name)
    return {
        "status": status,
        "rationale": rationale,
        "evidence_refs": refs,
        "passes": passes,
    }, passes


def _authority_story_result(
    candidate: Dict[str, Any], errors: List[str], conflicts: List[str]
) -> Dict[str, Any]:
    required = (
        str(candidate.get("content_mode") or "").strip().upper()
        == AUTHORITY_STORY_MODE
    )
    rows = candidate.get("authority_story_evidence")
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        errors.append("invalid_authority_story_evidence")
        rows = []

    verified_types = set()
    evidence_refs: List[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append("invalid_authority_story_evidence_row:%d" % index)
            continue
        evidence_type = str(row.get("type") or "").strip().upper()
        status = str(row.get("status") or "").strip().upper()
        refs = _clean_refs(row.get("evidence_refs"))
        if evidence_type not in AUTHORITY_EVIDENCE_TYPES:
            errors.append("invalid_authority_story_evidence_type:%d" % index)
            continue
        if status == "AVAILABLE" and refs:
            verified_types.add(evidence_type)
            evidence_refs.extend(refs)

    if required and verified_types == {"VERIFIED_PRICE_OR_TRANSACTION"}:
        conflicts.append("PRICE_ONLY_LUXURY_LABEL")
    if required and len(verified_types) < 2 and not conflicts:
        errors.append("insufficient_authority_story_evidence")

    return {
        "required": required,
        "passes": not required or len(verified_types) >= 2,
        "verified_types": sorted(verified_types),
        "verified_type_count": len(verified_types),
        "evidence_refs": sorted(set(evidence_refs)),
    }


def evaluate_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one predeclared candidate without calculating traffic score."""

    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")

    errors: List[str] = []
    candidate_id = str(
        candidate.get("candidate_id") or candidate.get("slug") or ""
    ).strip()
    if not candidate_id:
        errors.append("missing_candidate_id")
    if candidate.get("brand_mindset_predeclared") is not True:
        errors.append("brand_mindset_not_predeclared")

    evidence = candidate.get("brand_mindset_evidence")
    if not isinstance(evidence, dict):
        evidence = {}
        errors.append("missing_brand_mindset_evidence")

    dimension_results: Dict[str, Dict[str, Any]] = {}
    matched_dimensions: List[str] = []
    for name in DIMENSIONS:
        result, passes = _dimension_result(name, evidence.get(name), errors)
        dimension_results[name] = result
        if passes:
            matched_dimensions.append(name)

    raw_conflicts = candidate.get("brand_conflicts")
    if raw_conflicts is None:
        raw_conflicts = []
    if not isinstance(raw_conflicts, list):
        errors.append("invalid_brand_conflicts")
        raw_conflicts = []
    conflicts = sorted(
        {
            str(item).strip().upper()
            for item in raw_conflicts
            if str(item).strip()
        }
    )
    for conflict in conflicts:
        if conflict not in HARD_CONFLICTS:
            errors.append("unknown_brand_conflict:%s" % conflict)

    authority_story = _authority_story_result(candidate, errors, conflicts)
    conflicts = sorted(set(conflicts))

    if conflicts:
        verdict = "REJECT"
        classification = "UNQUALIFIED"
    elif errors or len(matched_dimensions) < 2 or not authority_story["passes"]:
        verdict = "HOLD"
        classification = "UNQUALIFIED"
    else:
        verdict = "PASS"
        classification = (
            "CORE_MINDSPACE"
            if len(matched_dimensions) == 3
            or (
                authority_story["required"]
                and authority_story["passes"]
            )
            else "QUALIFIED_ADJACENT"
        )

    rationale = [
        dimension_results[name]["rationale"]
        for name in matched_dimensions
        if dimension_results[name]["rationale"]
    ]
    result: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "candidate_id": candidate_id,
        "verdict": verdict,
        "brand_mindset_class": classification,
        "recommended_audience_fit_lane": (
            "PREMIUM_DECISION_CORE"
            if classification == "CORE_MINDSPACE"
            else "ADJACENT"
            if classification == "QUALIFIED_ADJACENT"
            else None
        ),
        "matched_mindset_dimensions": matched_dimensions,
        "brand_fit_rationale": rationale,
        "brand_conflict_veto": conflicts,
        "dimension_results": dimension_results,
        "authority_story_evidence": authority_story,
        "content_mode": str(candidate.get("content_mode") or "").strip().upper(),
        "pre_score_declared": candidate.get("brand_mindset_predeclared") is True,
        "validation_errors": sorted(set(errors)),
        "traffic_score_authority": False,
        "demand_authority": False,
        "trend_label_authority": False,
        "qa_authority": False,
        "publication_authority": False,
    }
    result["fingerprint"] = _fingerprint(result)
    return result


def validate_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("contract_version") != CONTRACT_VERSION:
        return False
    fingerprint = str(result.get("fingerprint") or "")
    if len(fingerprint) != 64 or fingerprint != _fingerprint(result):
        return False
    if result.get("verdict") not in {"PASS", "HOLD", "REJECT"}:
        return False
    if result.get("brand_mindset_class") not in {
        "CORE_MINDSPACE",
        "QUALIFIED_ADJACENT",
        "UNQUALIFIED",
    }:
        return False
    return all(
        result.get(key) is False
        for key in (
            "traffic_score_authority",
            "demand_authority",
            "trend_label_authority",
            "qa_authority",
            "publication_authority",
        )
    )


def process_payload(payload: Any) -> Tuple[Any, Dict[str, Any]]:
    if isinstance(payload, dict):
        candidates = payload.get("candidates")
    else:
        candidates = payload
    if not isinstance(candidates, list):
        raise ValueError("input must be a candidate list or contain candidates")

    output_rows: List[Dict[str, Any]] = []
    for row in candidates:
        if not isinstance(row, dict):
            raise ValueError("every candidate must be an object")
        output_row = copy.deepcopy(row)
        output_row["brand_mindset_gate"] = evaluate_candidate(row)
        output_rows.append(output_row)

    output_payload: Any
    if isinstance(payload, dict):
        output_payload = copy.deepcopy(payload)
        output_payload["candidates"] = output_rows
    else:
        output_payload = output_rows

    verdict_counts = Counter(
        row["brand_mindset_gate"]["verdict"] for row in output_rows
    )
    class_counts = Counter(
        row["brand_mindset_gate"]["brand_mindset_class"] for row in output_rows
    )
    summary: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "candidate_count": len(output_rows),
        "verdict_counts": {
            key: verdict_counts.get(key, 0) for key in ("PASS", "HOLD", "REJECT")
        },
        "class_counts": {
            key: class_counts.get(key, 0)
            for key in (
                "CORE_MINDSPACE",
                "QUALIFIED_ADJACENT",
                "UNQUALIFIED",
            )
        },
        "candidate_gate_fingerprints": [
            row["brand_mindset_gate"]["fingerprint"] for row in output_rows
        ],
        "global_score_allowed": False,
        "production_authority": False,
    }
    summary["snapshot_fingerprint"] = _fingerprint(summary)
    return output_payload, summary


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args(argv)
    output_payload, summary = process_payload(_load(args.input))
    _write(args.output, output_payload)
    _write(args.summary, summary)
    print(
        json.dumps(
            {
                "contract_version": CONTRACT_VERSION,
                "candidate_count": summary["candidate_count"],
                "verdict_counts": summary["verdict_counts"],
                "snapshot_fingerprint": summary["snapshot_fingerprint"],
                "output": str(args.output),
                "summary": str(args.summary),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

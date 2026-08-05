#!/usr/bin/env python3
"""Deterministic QA policy identity and restricted-claim context routing.

The module is intentionally read-only. It produces stable identities and
semantic routing evidence; it never writes Sanity, publishes content or edits
historical QA decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from typing import Any, Iterable


POLICY_ID = "vertu-seo-publish-gate"
POLICY_VERSION = "0.7.0"
DEFAULT_EVALUATION_PROFILE = "official_site_standard"

EVALUATION_PROFILES = {
    "official_site_relaxed",
    "official_site_standard",
    "official_site_strict",
}

HARD_RED_TERMS = {
    "diagnose",
    "diagnosis",
    "diagnostic",
    "treat",
    "treatment",
    "cure",
    "prevent disease",
    "disease detection",
    "early warning of disease",
    "medical-grade",
    "clinical-grade",
    "hospital-grade",
    "FDA approved",
    "FDA cleared",
    "doctor approved",
    "doctor recommended",
    "100% accurate",
    "guaranteed results",
    "personal doctor on your finger",
}

NON_MEDICAL_CONTEXT_TERMS = {
    "booking",
    "cabin",
    "deal",
    "fare",
    "flight",
    "itinerary",
    "offer",
    "payment",
    "ticket",
    "transaction",
    "travel",
    "upgrade",
}

MEDICAL_CONTEXT_TERMS = {
    "blood pressure",
    "cancer",
    "clinical",
    "condition",
    "disease",
    "doctor",
    "fda",
    "health",
    "hypertension",
    "illness",
    "infection",
    "medical",
    "patient",
    "symptom",
}

NEGATION_SCOPE_PATTERN = re.compile(
    r"\b(?:does\s+not|do\s+not|did\s+not|cannot|can't|never|not|no)\b"
    r"(?:\W+\w+){0,5}\W*$",
    re.IGNORECASE,
)
CLAUSE_BOUNDARY_PATTERN = re.compile(
    r"(?:[.!?;:\n]+|,\s*(?:but|however|yet)\b|\b(?:but|however|yet)\b)",
    re.IGNORECASE,
)


class QAPolicyError(ValueError):
    """Raised when an identity or classifier input is not auditable."""


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QAPolicyError(f"{label} must be a non-empty string")
    return value.strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalise_policy_version(value: str) -> str:
    """Normalise legacy free-text Skill versions without rewriting history."""

    value = _require_text(value, "skill_version")
    prefix = f"{POLICY_ID}-"
    return value[len(prefix) :] if value.startswith(prefix) else value


def _stable_source_label(path: pathlib.Path) -> str:
    labels = {
        "SKILL.md": "SKILL.md",
        "qa-tracking-contract.md": "references/qa-tracking-contract.md",
        "vertu_qa_policy.py": "scripts/vertu_qa_policy.py",
        "vertu_editorial_safeguards.py": "scripts/vertu_editorial_safeguards.py",
        "VERTU-QA-Handoff-Contract.md": "contracts/VERTU-QA-Handoff-Contract.md",
    }
    return labels.get(path.name, path.name)


def canonical_policy_hash(*paths: str | pathlib.Path) -> str:
    """Hash ordered policy sources without depending on an absolute workspace path."""

    if not paths:
        raise QAPolicyError("at least one policy source path is required")
    digest = hashlib.sha256()
    for index, raw_path in enumerate(paths):
        path = pathlib.Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise QAPolicyError(f"policy source does not exist: {path}")
        digest.update(str(index).encode("ascii"))
        digest.update(b"\0")
        digest.update(_stable_source_label(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_qa_identity(
    *,
    sanity_doc_id: str,
    source_rev: str,
    policy_hash: str,
    evaluation_profile: str,
) -> dict[str, str]:
    """Build the deterministic identity used for current-revision QA runs."""

    sanity_doc_id = _require_text(sanity_doc_id, "sanity_doc_id")
    source_rev = _require_text(source_rev, "source_rev")
    policy_hash = _require_text(policy_hash, "policy_hash")
    evaluation_profile = _require_text(evaluation_profile, "evaluation_profile")
    if evaluation_profile not in EVALUATION_PROFILES:
        raise QAPolicyError(
            f"evaluation_profile must be one of {sorted(EVALUATION_PROFILES)}"
        )
    payload = {
        "sanity_doc_id": sanity_doc_id,
        "source_rev": source_rev,
        "qa_policy_hash": policy_hash,
        "evaluation_profile": evaluation_profile,
    }
    return {
        **payload,
        "qa_identity": hashlib.sha256(
            _canonical_json(payload).encode("utf-8")
        ).hexdigest(),
    }


def duplicate_qa_run_ids(rows: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    """Return duplicate QA Run IDs and their source record IDs."""

    grouped: dict[str, list[str]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise QAPolicyError(f"rows[{index}] must be an object")
        qa_run_id = _require_text(row.get("qa_run_id"), f"rows[{index}].qa_run_id")
        record_id = _require_text(row.get("record_id"), f"rows[{index}].record_id")
        grouped.setdefault(qa_run_id, []).append(record_id)
    return {
        qa_run_id: record_ids
        for qa_run_id, record_ids in sorted(grouped.items())
        if len(record_ids) > 1
    }


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _local_clause(text: str, start: int, end: int) -> str:
    clause_start = 0
    for boundary in CLAUSE_BOUNDARY_PATTERN.finditer(text, 0, start):
        clause_start = boundary.end()
    next_boundary = CLAUSE_BOUNDARY_PATTERN.search(text, end)
    clause_end = next_boundary.start() if next_boundary else len(text)
    return text[clause_start:clause_end].strip()


def classify_restricted_context(text: str, term: str) -> dict[str, Any]:
    """Classify a literal hard-red match without treating recall as verdict."""

    text = _require_text(text, "text")
    term = _require_text(term, "term")
    lowered_text = text.casefold()
    lowered_term = term.casefold()
    if lowered_term not in {item.casefold() for item in HARD_RED_TERMS}:
        raise QAPolicyError(f"unsupported hard-red term: {term}")
    term_pattern = re.compile(
        rf"(?<!\w){re.escape(lowered_term)}(?!\w)", re.IGNORECASE
    )
    matches = list(term_pattern.finditer(lowered_text))
    if not matches:
        return {
            "rule_id": "RESTRICTED_TERM_NOT_FOUND",
            "term": term,
            "classification": "NO_MATCH",
            "auto_block": False,
            "semantic_review_required": False,
            "evidence_label": "Measured",
            "matched_excerpt": None,
        }

    classifications: list[str] = []
    clauses: list[str] = []
    for match in matches:
        clause = _local_clause(lowered_text, match.start(), match.end())
        clauses.append(clause)
        term_offset = clause.find(lowered_term)
        prefix = clause[:term_offset] if term_offset >= 0 else clause
        if NEGATION_SCOPE_PATTERN.search(prefix):
            classifications.append("NEGATION_OR_DISCLAIMER")
        elif _contains_any(clause, MEDICAL_CONTEXT_TERMS):
            classifications.append("AFFIRMATIVE_MEDICAL_CLAIM")
        elif lowered_term in {"treat", "treatment"} and _contains_any(
            clause, NON_MEDICAL_CONTEXT_TERMS
        ):
            classifications.append("NON_MEDICAL_CONTEXT")
        else:
            classifications.append("AMBIGUOUS_CONTEXT")

    if "AFFIRMATIVE_MEDICAL_CLAIM" in classifications:
        classification = "AFFIRMATIVE_MEDICAL_CLAIM"
        rule_id = "RESTRICTED_AFFIRMATIVE_MEDICAL_BLOCK"
        auto_block = True
        semantic_review = True
    elif "AMBIGUOUS_CONTEXT" in classifications:
        classification = "AMBIGUOUS_CONTEXT"
        rule_id = "RESTRICTED_CONTEXT_REVIEW_REQUIRED"
        auto_block = False
        semantic_review = True
    elif "NEGATION_OR_DISCLAIMER" in classifications:
        classification = "NEGATION_OR_DISCLAIMER"
        rule_id = "RESTRICTED_NEGATION_REVIEW"
        auto_block = False
        semantic_review = True
    else:
        classification = "NON_MEDICAL_CONTEXT"
        rule_id = "RESTRICTED_NON_MEDICAL_FALSE_POSITIVE"
        auto_block = False
        semantic_review = False

    return {
        "rule_id": rule_id,
        "term": term,
        "classification": classification,
        "auto_block": auto_block,
        "semantic_review_required": semantic_review,
        "evidence_label": "Measured",
        "matched_excerpt": text,
        "matched_clauses": clauses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    identity = subparsers.add_parser("identity")
    identity.add_argument("--sanity-doc-id", required=True)
    identity.add_argument("--source-rev", required=True)
    identity.add_argument("--policy-hash", required=True)
    identity.add_argument(
        "--evaluation-profile", default=DEFAULT_EVALUATION_PROFILE
    )

    restricted = subparsers.add_parser("restricted-context")
    restricted.add_argument("--text", required=True)
    restricted.add_argument("--term", required=True)

    policy_hash = subparsers.add_parser("policy-hash")
    policy_hash.add_argument("--source", action="append", required=True)

    args = parser.parse_args()
    if args.command == "identity":
        result = build_qa_identity(
            sanity_doc_id=args.sanity_doc_id,
            source_rev=args.source_rev,
            policy_hash=args.policy_hash,
            evaluation_profile=args.evaluation_profile,
        )
    elif args.command == "restricted-context":
        result = classify_restricted_context(args.text, args.term)
    else:
        result = {
            "qa_policy_id": POLICY_ID,
            "qa_policy_version": POLICY_VERSION,
            "qa_policy_hash": canonical_policy_hash(*args.source),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

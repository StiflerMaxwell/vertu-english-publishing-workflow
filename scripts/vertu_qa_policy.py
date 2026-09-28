#!/usr/bin/env python3
"""Deterministic QA policy identity and restricted-claim context routing.

The module is intentionally read-only. It produces stable identities and
semantic routing evidence; it never writes Sanity, publishes content or edits
historical QA decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
from typing import Any, Iterable


POLICY_ID = "vertu-seo-publish-gate"
POLICY_VERSION = "0.8.0"
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
    "activity",
    "background",
    "benchmark",
    "booking",
    "bonus",
    "browser",
    "card",
    "cabin",
    "checkout",
    "compatibility",
    "contract",
    "credit",
    "deal",
    "display",
    "evidence",
    "fare",
    "flight",
    "insurance",
    "itinerary",
    "journey",
    "lounge",
    "mileage",
    "model",
    "offer",
    "payment",
    "price",
    "pricing",
    "refund",
    "reporting",
    "research",
    "retailer",
    "room",
    "royalty",
    "safety",
    "screen",
    "screenshot",
    "seat",
    "service",
    "subscription",
    "ticket",
    "transaction",
    "travel",
    "traveller",
    "upgrade",
    "visual",
    "weather",
    "wealth",
}

DIAGNOSTIC_NON_MEDICAL_CONTEXT_TERMS = {
    "battery",
    "error",
    "failure",
    "fault",
    "hardware",
    "maintenance",
    "network",
    "performance",
    "problem",
    "quote",
    "repair",
    "security",
    "service",
    "software",
    "system",
    "technical",
    "workflow",
}

MEDICAL_CONTEXT_TERMS = {
    "blood pressure",
    "cancer",
    "clinical",
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
        "VERTU-QA-Handoff-Contract.md": "docs/03-运行/VERTU-QA-Handoff-Contract.md",
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


def canonical_policy_sources() -> tuple[pathlib.Path, ...]:
    root = pathlib.Path(__file__).resolve().parents[1]
    # The public handoff package must validate its own exact policy sources,
    # not silently read another installation from the recipient's home folder.
    for package_root in (root, *root.parents):
        if (package_root / ".public-workflow-package").is_file():
            skill = package_root / "skills/vertu-seo-publish-gate"
            return (
                skill / "SKILL.md", skill / "references/qa-tracking-contract.md",
                package_root / "scripts/vertu_qa_policy.py",
                skill / "scripts/vertu_editorial_safeguards.py",
                package_root / "contracts/VERTU-QA-Handoff-Contract.md",
            )
    skill = pathlib.Path.home() / ".openclaw/workspace/skills/vertu-seo-publish-gate"
    return (
        skill / "SKILL.md", skill / "references/qa-tracking-contract.md",
        pathlib.Path(__file__).resolve(), skill / "scripts/vertu_editorial_safeguards.py",
        root / "docs/03-运行/VERTU-QA-Handoff-Contract.md",
    )


def current_policy_identity() -> dict[str, str]:
    sources = canonical_policy_sources()
    declared = re.search(r'Current policy version: `([^`]+)`', sources[0].read_text())
    if not declared or declared.group(1) != POLICY_VERSION:
        raise QAPolicyError("QA_POLICY_VERSION_MISMATCH")
    return {"qa_policy_id": POLICY_ID, "qa_policy_version": POLICY_VERSION,
            "qa_policy_hash": canonical_policy_hash(*sources)}


def check_runtime() -> dict[str, Any]:
    """Execute real safeguard probes; this is NOT article QA or release approval."""
    identity = current_policy_identity()
    path = canonical_policy_sources()[3]
    spec = importlib.util.spec_from_file_location("_vertu_current_safeguards", path)
    if spec is None or spec.loader is None:
        raise QAPolicyError("QA_RUNTIME_CHECK_FAILED: safeguard loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        benchmark = {"contract_version": "serp-benchmark-v1", "verdict": "BENCHMARK_PASS",
                     "original_value_delta": "Compare cabin upgrade refund restrictions",
                     "required_value_object_types": ["comparison_table"]}
        benchmark["benchmark_fingerprint"] = module._benchmark_fingerprint(benchmark)
        body = "# Cabin upgrade\n\nCabin upgrade refund restrictions differ.\n\n| Cabin | Refund |\n| --- | --- |\n| Business | Fare dependent |\n"
        good = module.evaluate_article(article_key="probe", content=body, content_type="guide",
                                       serp_benchmark=benchmark, require_serp_benchmark=True)
        missing = module.evaluate_article(article_key="probe", content=body, content_type="guide",
                                          require_serp_benchmark=True)
        changed = dict(benchmark, original_value_delta="Unrelated camera comparison")
        tampered = module.serp_differentiation_evaluation(body, benchmark=changed, required=True)
        duplicate = module.duplicate_integration_evaluation(
            "## How VERTU helps\nA.\n## VERTU Concierge for travellers\nB.")
        repeated = "# Comparison\n" + "\n".join(
            "## " + heading + "\nSpecific evidence."
            for heading in ("Cabin upgrade eligibility", "Refund restrictions compared",
                            "Seat booking conditions", "Baggage purchase decisions",
                            "Change fee calculation", "Airport lounge admission"))
        batch = module.evaluate_batch([
            {"article_key": key, "content": repeated, "content_type": "guide"}
            for key in ("probe-a", "probe-b")])
        visual = module.evaluate_article(article_key="probe", content=body + " evidence" * 1550,
                                         content_type="buying_guide", title="Best cabin comparison")
        checks = {
            "serp_positive": good["preflight_pass"],
            "serp_missing_blocks": "SERP_DIFFERENTIATION_MISMATCH" in missing["blocking_codes"],
            "serp_tampered_blocks": tampered["blocking"],
            "duplicate_integration_blocks": bool(duplicate.get("finding")),
            "batch_template_blocks": batch["template_dependent_pair_count"] == 1,
            "body_visual_warning_only": "BODY_VISUAL_MISSING" in visual["warning_codes"] and visual["preflight_pass"],
            "medical_affirmation_blocks": classify_restricted_context("This device can treat hypertension.", "treat")["auto_block"],
            "nonmedical_idiom_preserved": not classify_restricted_context("Treat the offer as a new transaction.", "treat")["auto_block"],
        }
    finally:
        sys.modules.pop(spec.name, None)
    passed = all(checks.values())
    return {**identity, "contract_version": "qa-runtime-compatibility-v1",
            "verdict": "PASS" if passed else "BLOCK", "checks": checks,
            "blocker": None if passed else "QA_RUNTIME_CHECK_FAILED",
            "startup_compatible": passed, "authorises_release": False}


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
    for term in terms:
        escaped = re.escape(term).replace(r"\ ", r"\s+")
        if re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE):
            return True
    return False


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
        elif lowered_term in {"treat", "treatment"} and (
            _contains_any(clause, NON_MEDICAL_CONTEXT_TERMS)
            or re.search(r"\btreat\b.{0,160}\bas\b", clause, re.IGNORECASE)
        ):
            classifications.append("NON_MEDICAL_CONTEXT")
        elif lowered_term in {"diagnose", "diagnosis", "diagnostic"} and _contains_any(
            clause, DIAGNOSTIC_NON_MEDICAL_CONTEXT_TERMS
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

    runtime = subparsers.add_parser("runtime-check")
    runtime.add_argument("--execution-id", required=True)
    runtime.add_argument("--output")

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
    elif args.command == "runtime-check":
        try:
            result = check_runtime()
        except (OSError, QAPolicyError, ValueError, AttributeError, KeyError) as exc:
            result = {"verdict": "BLOCK", "startup_compatible": False,
                      "authorises_release": False, "blocker": "QA_RUNTIME_CHECK_FAILED",
                      "reason": str(exc)}
        result["execution_id"] = args.execution_id
        if args.output:
            pathlib.Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["startup_compatible"] else 2
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

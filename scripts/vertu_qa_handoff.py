#!/usr/bin/env python3
"""Deterministic producer-to-QA handoff identity and compatibility gate.

This module is read-only. It fingerprints artifacts and validates release
evidence; it never mutates Sanity or changes historical QA decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from typing import Any, Mapping


CONTRACT_VERSION = "qa-handoff-v1"
PRODUCER_SKILL_ID = "vertu-english-blog-pipeline"
QA_POLICY_ID = "vertu-seo-publish-gate"
COMPATIBLE_PRODUCER_MIN = (3, 10, 0)
COMPATIBLE_PRODUCER_MAX_EXCLUSIVE = (4, 0, 0)
COMPATIBLE_QA_MIN = (0, 6, 0)
COMPATIBLE_QA_MAX_EXCLUSIVE = (1, 0, 0)

SOURCE_ROLE_MATRIX = {
    "preflight": "artifact_bundle",
    "prepublish": "sanity_draft_revision",
    "postpublish_audit": "published_revision",
}
EVALUATION_PROFILES = {
    "official_site_relaxed",
    "official_site_standard",
    "official_site_strict",
}
COMPATIBILITY_STATES = {
    "COMPATIBLE",
    "LEGACY_UNVERIFIED",
    "VERSION_MISMATCH",
    "ARTIFACT_MISMATCH",
    "REVISION_MISMATCH",
    "TRACKING_INCOMPLETE",
}
SEMVER_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


class QAHandoffError(ValueError):
    """Raised when a handoff cannot be evaluated deterministically."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QAHandoffError(f"{label} must be a non-empty string")
    return value.strip()


def parse_semver(value: Any, label: str) -> tuple[int, int, int]:
    text = require_text(value, label)
    match = SEMVER_PATTERN.fullmatch(text)
    if not match:
        raise QAHandoffError(f"{label} must be semantic version x.y.z")
    return tuple(int(part) for part in match.groups())


def in_range(value: Any, label: str, minimum: tuple[int, int, int], maximum: tuple[int, int, int]) -> bool:
    parsed = parse_semver(value, label)
    return minimum <= parsed < maximum


def artifact_bundle_fingerprint(entries: Mapping[str, Any]) -> str:
    """Hash ordered artifact labels plus bytes or explicit absent status."""

    if not isinstance(entries, Mapping) or not entries:
        raise QAHandoffError("artifact entries must be a non-empty object")
    digest = hashlib.sha256()
    for label in sorted(entries):
        require_text(label, "artifact label")
        value = entries[label]
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        if isinstance(value, str):
            path = pathlib.Path(value).expanduser().resolve()
            if not path.is_file():
                raise QAHandoffError(f"artifact does not exist: {path}")
            digest.update(b"FILE\0")
            digest.update(path.read_bytes())
        elif isinstance(value, Mapping) and value.get("status") in {"NOT_APPLICABLE", "SOURCE_UNAVAILABLE"}:
            digest.update(b"STATUS\0")
            digest.update(canonical_json(dict(value)).encode("utf-8"))
        else:
            raise QAHandoffError(
                f"artifact {label} must be a file path or explicit NOT_APPLICABLE/SOURCE_UNAVAILABLE status"
            )
        digest.update(b"\0")
    return digest.hexdigest()


def qa_result_fingerprint(payload: Mapping[str, Any]) -> str:
    source = payload.get("source_identity") or {}
    qa = payload.get("qa") or {}
    identity = {
        "contract_version": payload.get("contract_version"),
        "publication_run_id": payload.get("publication_run_id"),
        "article_key": payload.get("article_key"),
        "producer_skill": payload.get("producer_skill"),
        "source_identity": source,
        "release_gate_role": payload.get("release_gate_role"),
        "qa": {
            "run_id": qa.get("run_id"),
            "record_id": qa.get("record_id"),
            "policy_id": qa.get("policy_id"),
            "policy_version": qa.get("policy_version"),
            "policy_hash": qa.get("policy_hash"),
            "evaluation_profile": qa.get("evaluation_profile"),
            "verdict": qa.get("verdict"),
            "score": qa.get("score"),
            "patch_action": qa.get("patch_action"),
            "critical_veto": qa.get("critical_veto"),
            "unresolved_critical": qa.get("unresolved_critical"),
            "unresolved_required": qa.get("unresolved_required"),
        },
    }
    return hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()


def validate_handoff(
    payload: Mapping[str, Any],
    *,
    expected_bundle_sha256: str | None = None,
    expected_sanity_doc_id: str | None = None,
    expected_source_rev: str | None = None,
    require_authorising_pass: bool = True,
) -> dict[str, Any]:
    """Return a deterministic compatibility verdict without mutating input."""

    errors: list[str] = []
    if not isinstance(payload, Mapping):
        raise QAHandoffError("handoff payload must be an object")

    required_text = (
        "contract_version",
        "publication_run_id",
        "article_key",
        "canonical_url",
        "section",
        "language",
        "release_gate_role",
    )
    for key in required_text:
        try:
            require_text(payload.get(key), key)
        except QAHandoffError as exc:
            errors.append(str(exc))

    producer = payload.get("producer_skill") or {}
    source = payload.get("source_identity") or {}
    qa = payload.get("qa") or {}
    for key, label in (
        (producer.get("id"), "producer_skill.id"),
        (producer.get("version"), "producer_skill.version"),
        (source.get("type"), "source_identity.type"),
        (source.get("draft_bundle_sha256"), "source_identity.draft_bundle_sha256"),
        (qa.get("run_id"), "qa.run_id"),
        (qa.get("record_id"), "qa.record_id"),
        (qa.get("policy_id"), "qa.policy_id"),
        (qa.get("policy_version"), "qa.policy_version"),
        (qa.get("policy_hash"), "qa.policy_hash"),
        (qa.get("evaluation_profile"), "qa.evaluation_profile"),
        (qa.get("verdict"), "qa.verdict"),
        (qa.get("patch_action"), "qa.patch_action"),
    ):
        try:
            require_text(key, label)
        except QAHandoffError as exc:
            errors.append(str(exc))

    status = "COMPATIBLE"
    version_errors = False
    if payload.get("contract_version") != CONTRACT_VERSION:
        errors.append("contract_version is not qa-handoff-v1")
        version_errors = True
    if producer.get("id") != PRODUCER_SKILL_ID:
        errors.append("producer_skill.id mismatch")
        version_errors = True
    try:
        if not in_range(producer.get("version"), "producer_skill.version", COMPATIBLE_PRODUCER_MIN, COMPATIBLE_PRODUCER_MAX_EXCLUSIVE):
            errors.append("producer_skill.version outside compatible range")
            version_errors = True
    except QAHandoffError as exc:
        errors.append(str(exc))
        version_errors = True
    if qa.get("policy_id") != QA_POLICY_ID:
        errors.append("qa.policy_id mismatch")
        version_errors = True
    try:
        if not in_range(qa.get("policy_version"), "qa.policy_version", COMPATIBLE_QA_MIN, COMPATIBLE_QA_MAX_EXCLUSIVE):
            errors.append("qa.policy_version outside compatible range")
            version_errors = True
    except QAHandoffError as exc:
        errors.append(str(exc))
        version_errors = True
    if qa.get("evaluation_profile") not in EVALUATION_PROFILES:
        errors.append("qa.evaluation_profile is unsupported")
        version_errors = True
    if version_errors:
        status = "VERSION_MISMATCH"

    role = payload.get("release_gate_role")
    source_type = source.get("type")
    if role not in SOURCE_ROLE_MATRIX or SOURCE_ROLE_MATRIX.get(role) != source_type:
        errors.append("release_gate_role and source_identity.type mismatch")
        if status == "COMPATIBLE":
            status = "TRACKING_INCOMPLETE"
    bundle_hash = source.get("draft_bundle_sha256")
    if not isinstance(bundle_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", bundle_hash):
        errors.append("source_identity.draft_bundle_sha256 must be 64 lowercase hex characters")
        if status == "COMPATIBLE":
            status = "TRACKING_INCOMPLETE"
    if expected_bundle_sha256 and bundle_hash != expected_bundle_sha256:
        errors.append("draft bundle fingerprint mismatch")
        status = "ARTIFACT_MISMATCH"

    if source_type in {"sanity_draft_revision", "published_revision"}:
        if not source.get("sanity_doc_id") or not source.get("source_rev"):
            errors.append("Sanity document ID and source revision are required for revision-bound QA")
            if status == "COMPATIBLE":
                status = "TRACKING_INCOMPLETE"
    if expected_sanity_doc_id and source.get("sanity_doc_id") != expected_sanity_doc_id:
        errors.append("Sanity document ID mismatch")
        status = "REVISION_MISMATCH"
    if expected_source_rev and source.get("source_rev") != expected_source_rev:
        errors.append("Sanity source revision mismatch")
        status = "REVISION_MISMATCH"

    for field in ("unresolved_critical", "unresolved_required"):
        value = qa.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"qa.{field} must be a non-negative integer")
            if status == "COMPATIBLE":
                status = "TRACKING_INCOMPLETE"
    if require_authorising_pass:
        if qa.get("verdict") != "PASS":
            errors.append("authorising QA verdict must be PASS")
        if qa.get("patch_action") != "no_patch_needed":
            errors.append("authorising QA patch_action must be no_patch_needed")
        if qa.get("critical_veto") not in (None, False, "", "NONE"):
            errors.append("authorising QA has a critical veto")
        if qa.get("unresolved_critical") != 0 or qa.get("unresolved_required") != 0:
            errors.append("authorising QA has unresolved critical or required findings")
        if errors and status == "COMPATIBLE":
            status = "TRACKING_INCOMPLETE"

    fingerprint = qa_result_fingerprint(payload)
    declared_fingerprint = payload.get("qa_result_fingerprint")
    if declared_fingerprint and declared_fingerprint != fingerprint:
        errors.append("qa_result_fingerprint mismatch")
        if status == "COMPATIBLE":
            status = "ARTIFACT_MISMATCH"
    declared_status = payload.get("compatibility_status")
    if declared_status and declared_status not in COMPATIBILITY_STATES:
        errors.append("declared compatibility_status is unsupported")
        if status == "COMPATIBLE":
            status = "TRACKING_INCOMPLETE"
    elif declared_status and declared_status != status:
        errors.append("declared compatibility_status does not match computed status")
        if status == "COMPATIBLE":
            status = "TRACKING_INCOMPLETE"

    return {
        "contract_version": CONTRACT_VERSION,
        "compatibility_status": status,
        "valid_evidence": status == "COMPATIBLE" and not errors,
        "authorises_release": require_authorising_pass
        and status == "COMPATIBLE"
        and not errors,
        "qa_result_fingerprint": fingerprint,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle = subparsers.add_parser("bundle-fingerprint")
    bundle.add_argument("--manifest", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--handoff", required=True)
    validate.add_argument("--expected-bundle-sha256")
    validate.add_argument("--expected-sanity-doc-id")
    validate.add_argument("--expected-source-rev")
    validate.add_argument("--observation-only", action="store_true")

    args = parser.parse_args()
    if args.command == "bundle-fingerprint":
        entries = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
        result = {"draft_bundle_sha256": artifact_bundle_fingerprint(entries)}
    else:
        payload = json.loads(pathlib.Path(args.handoff).read_text(encoding="utf-8"))
        result = validate_handoff(
            payload,
            expected_bundle_sha256=args.expected_bundle_sha256,
            expected_sanity_doc_id=args.expected_sanity_doc_id,
            expected_source_rev=args.expected_source_rev,
            require_authorising_pass=not args.observation_only,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    success_key = "valid_evidence" if args.command == "validate" and args.observation_only else "authorises_release"
    return 0 if result.get(success_key, True) else 2


if __name__ == "__main__":
    raise SystemExit(main())

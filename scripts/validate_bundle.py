#!/usr/bin/env python3
"""Validate the portable VERTU publishing-workflow package."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    ".public-workflow-package",
    "docs/CONTENT-CREATOR-HANDOFF.zh-CN.md",
    "docs/CURRENT-OPERATING-PROFILE.md",
    "templates/creator-submission.md",
    "scripts/vertu_brand_mindset_gate.py",
    "scripts/vertu_serp_benchmark.py",
    "scripts/vertu_youtube_topic_signals.py",
    "scripts/vertu_llm_visibility_diagnose.py",
    "README.md",
    "LICENSE",
    "NOTICE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    ".env.example",
    "automation/vertu-10.template.toml",
    "config/performance-monitor-base.example.json",
    "contracts/VERTU-Content-Automation-Chain-Contract.md",
    "contracts/VERTU-Content-Performance-Monitoring-Contract.md",
    "contracts/VERTU-QA-Handoff-Contract.md",
    "contracts/VERTU-vvv-Group-Receipt-Template.md",
    "docs/PUBLIC-RELEASE-CHECKLIST.md",
    "docs/LOOP-ENGINEERING-REVIEW.md",
    "skills/vertu-english-blog-pipeline/SKILL.md",
    "skills/vertu-english-blog-pipeline/references/README.md",
    "skills/vertu-seo-publish-gate/SKILL.md",
    "skills/vertu-seo-publish-gate/scripts/vertu_qa_policy.py",
    "skills/vertu-seo-publish-gate/scripts/vertu_editorial_safeguards.py",
    "scripts/vertu_content_traffic_gate.py",
    "scripts/vertu_content_monitor_runtime.py",
    "scripts/vertu_content_monitor_base_handoff.py",
    "scripts/vertu_qa_policy.py",
    "scripts/vertu_qa_handoff.py",
    "scripts/vertu_editorial_safeguards.py",
    "scripts/vertu_skill_evolution_scorecard.py",
    "scripts/vertu_google_trends_realtime.py",
    "scripts/vertu_content_learning_flywheel.py",
    "scripts/vertu_content_loop_runtime.py",
    "scripts/vertu_daily_publishing_quota.py",
    "scripts/vertu_d2tr_discover_monitor.py",
    "scripts/vertu-vvv-notify.ts",
}

ACTIVE_REFERENCES = {
    "brand-mindset-gate.md",
    "evergreen-quota-fallback.md",
    "direct-factor-model.md",
    "hybrid-factor-trial.md",
    "youtube-topic-signals.md",
    "discover-recovery-profile.md",
    "serp-benchmark.md",
    "llm-visibility-diagnosis.md",
    "skill-evolution-factor-vector.md",
    "topic-selection.md",
    "traffic-demand-gate.md",
    "realtime-trends.md",
    "editorial-intelligence.md",
    "performance-learning.md",
    "skill-evolution-scorecard.md",
    "product-knowledge.md",
    "writing-contract.md",
    "author-policy.md",
    "automation-contract.md",
    "loop-runtime-governance.md",
}

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".ts",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
    ".example",
    ".gitignore",
}

FORBIDDEN_PATTERNS = {
    "quoted opaque resource identifier": re.compile(r"[`\"'](?!(?:averageSessionDuration|additionalProperties|dimensionFilterGroups|userEngagementDuration)[`\"'])(?=[A-Za-z0-9]{20,40}[`\"'])(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*[a-z])[A-Za-z0-9]+[`\"']"),
    "private deployment hostname": re.compile(r"https?://[^/\s]+\.(?:feishu\.cn|vertu\.cn)(?:/|\b)"),
    "opaque mixed-case resource identifier": re.compile(r"(?<![A-Za-z0-9+/])\b(?=[A-Za-z0-9]{20,40}\b)(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]+\b(?![A-Za-z0-9+/=])"),
    "deployed author reference": re.compile(r"\bauthor-vertu-[a-z-]+-desk\b"),
    "OpenAI secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "credential-bearing URL": re.compile(r"https?://[^/\s:@]+:[^/\s@]+@"),
    "machine-specific home path": re.compile("/" + "Users" + r"/[^/\s]+/"),
    "vvv secret value": re.compile(r"\bvbs_[A-Za-z0-9_-]{16,}\b"),
    "GitHub classic token": re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "private key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    "production Feishu table/view/field identifier": re.compile(
        r"\b(?:tbl|vew|fld)[A-Za-z0-9]{8,}\b"
    ),
    "production Feishu object URL": re.compile(
        r"https://[^\s/]+\.feishu\.cn/(?:base|wiki|docx)/[A-Za-z0-9]+"
    ),
    "production bot application identifier": re.compile(
        r"\bvbot_[A-Za-z0-9_-]{8,}\b"
    ),
    "production channel UUID": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
}

FORBIDDEN_TEMPLATE_FIELDS = {
    "target_thread_id",
    "created_at",
    "updated_at",
}


def iter_text_files() -> list[Path]:
    # Scan every release file, not just extensions; ignored runtime files are
    # never part of a release. Include untracked candidates before staging.
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, check=True, capture_output=True,
    )
    files = {ROOT / name.decode("utf-8") for name in result.stdout.split(b"\0") if name}
    return sorted(path for path in files if path.is_file())


def main() -> int:
    failures: list[str] = []

    for private_path in (".private-release-only", "config/private-release-scope.json", "config/hermes-runtime-manifest.sha256"):
        if (ROOT / private_path).exists():
            failures.append(f"private deployment artifact: {private_path}")
    package = json.loads((ROOT / "package.json").read_text())
    if package.get("version") != "3.20.0" or package.get("name") != "vertu-english-publishing-workflow":
        failures.append("public package identity/version mismatch")
    if package.get("private") is not True:
        failures.append("npm publication must remain disabled")

    for relative in sorted(REQUIRED_FILES):
        if not (ROOT / relative).is_file():
            failures.append(f"missing required file: {relative}")

    reference_root = ROOT / "skills/vertu-english-blog-pipeline/references"
    for name in sorted(ACTIVE_REFERENCES):
        if not (reference_root / name).is_file():
            failures.append(f"missing active reference: {name}")

    for path in iter_text_files():
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            failures.append(f"non-local release file: {path.relative_to(ROOT)}")
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            failures.append(f"populated environment file tracked: {path.relative_to(ROOT)}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append(f"non-UTF-8 text file: {path.relative_to(ROOT)}")
            continue
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{label}: {path.relative_to(ROOT)}")

    automation = ROOT / "automation/vertu-10.template.toml"
    if automation.is_file():
        text = automation.read_text(encoding="utf-8")
        for field in FORBIDDEN_TEMPLATE_FIELDS:
            if re.search(rf"(?m)^{re.escape(field)}\s*=", text):
                failures.append(f"instance field in automation template: {field}")

    for line in (ROOT / ".env.example").read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if re.search(r"(?:TOKEN|SECRET|PASSWORD|API_KEY|_ID|_WIKI_TOKEN)$", key) and value.strip():
            failures.append(f"populated sensitive example setting: {key}")

    excluded_roots = {"output", "artifacts", "run-output"}
    for name in sorted(excluded_roots):
        if (ROOT / name).exists():
            failures.append(f"excluded runtime directory present: {name}")

    mirrored_sources = (
        (
            ROOT / "scripts/vertu_qa_policy.py",
            ROOT / "skills/vertu-seo-publish-gate/scripts/vertu_qa_policy.py",
        ),
        (
            ROOT / "scripts/vertu_editorial_safeguards.py",
            ROOT / "skills/vertu-seo-publish-gate/scripts/vertu_editorial_safeguards.py",
        ),
    )
    for reusable, bundled in mirrored_sources:
        if reusable.is_file() and bundled.is_file() and reusable.read_bytes() != bundled.read_bytes():
            failures.append(
                "mirrored QA source drift: "
                f"{reusable.relative_to(ROOT)} != {bundled.relative_to(ROOT)}"
            )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    digest = hashlib.sha256()
    for path in iter_text_files():
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    print(f"PASS bundle validation ({len(iter_text_files())} text files)")
    print(f"bundle_fingerprint={digest.hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

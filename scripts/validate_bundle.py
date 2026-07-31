#!/usr/bin/env python3
"""Validate the portable VERTU publishing-workflow package."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
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
    "contracts/VERTU-vvv-Group-Receipt-Template.md",
    "docs/PUBLIC-RELEASE-CHECKLIST.md",
    "skills/vertu-english-blog-pipeline/SKILL.md",
    "skills/vertu-english-blog-pipeline/references/README.md",
    "skills/vertu-seo-publish-gate/SKILL.md",
    "scripts/vertu_content_traffic_gate.py",
    "scripts/vertu_google_trends_realtime.py",
    "scripts/vertu_content_learning_flywheel.py",
    "scripts/vertu-vvv-notify.ts",
}

ACTIVE_REFERENCES = {
    "topic-selection.md",
    "traffic-demand-gate.md",
    "realtime-trends.md",
    "editorial-intelligence.md",
    "performance-learning.md",
    "product-knowledge.md",
    "writing-contract.md",
    "author-policy.md",
    "automation-contract.md",
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
    "machine-specific home path": re.compile("/" + "Users" + r"/[^/\s]+/"),
    "vvv secret value": re.compile(r"\bvbs_[A-Za-z0-9_-]{16,}\b"),
    "GitHub classic token": re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "private key": re.compile(r"BEGIN (?:RSA |OPENSSH )?PRIVATE KEY"),
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
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "node_modules" in path.parts:
            continue
        if path.name in {".gitignore", ".env.example", "LICENSE", "NOTICE"} or path.suffix in TEXT_SUFFIXES:
            files.append(path)
    return sorted(files)


def main() -> int:
    failures: list[str] = []

    for relative in sorted(REQUIRED_FILES):
        if not (ROOT / relative).is_file():
            failures.append(f"missing required file: {relative}")

    reference_root = ROOT / "skills/vertu-english-blog-pipeline/references"
    for name in sorted(ACTIVE_REFERENCES):
        if not (reference_root / name).is_file():
            failures.append(f"missing active reference: {name}")

    for path in iter_text_files():
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

    excluded_roots = {"output", "artifacts", "run-output"}
    for name in sorted(excluded_roots):
        if (ROOT / name).exists():
            failures.append(f"excluded runtime directory present: {name}")

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

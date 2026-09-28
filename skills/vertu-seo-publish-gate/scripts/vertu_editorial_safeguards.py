#!/usr/bin/env python3
"""Deterministic editorial safeguards for independent VERTU QA.

This module evaluates final Markdown/HTML article bodies.  It is deliberately
read-only: it does not patch drafts, mutate Sanity, publish content, or write QA
tracking records.  Its output is compatible with ``qa-handoff-v1`` because
blocking defects are represented as unresolved required findings while the
phase-one body-visual check remains a recommended, non-blocking warning.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import pathlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable, Sequence


QA_HANDOFF_CONTRACT_VERSION = "qa-handoff-v1"
SAFEGUARD_SCHEMA_VERSION = "editorial-safeguards-v2"
DEFAULT_TEMPLATE_SIMILARITY_THRESHOLD = 0.78
DEFAULT_MIN_COMPARABLE_HEADINGS = 5
DEFAULT_MIN_SHARED_HEADINGS = 5
DEFAULT_LONG_FORM_WORD_THRESHOLD = 1500


class EditorialSafeguardError(ValueError):
    """Raised when an editorial-safeguard input is not auditable."""


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    line: int


COMMON_HEADING_PATTERNS = (
    re.compile(r"^(?:sources?|references?)(?: and (?:verification|notes|methodology))?$"),
    re.compile(
        r"^(?:further|related)(?: vertu)? (?:reading|guides|guides and reading)$"
    ),
    re.compile(r"^(?:conclusion|final verdict|the bottom line)$"),
    re.compile(r"^(?:faqs?|frequently asked questions)$"),
    re.compile(r"^(?:methodology|how we researched)$"),
    re.compile(r"^(?:disclaimer|editorial note)$"),
)

INTEGRATION_CUES = {
    "advantage",
    "angle",
    "assist",
    "assists",
    "connection",
    "difference",
    "fit",
    "fits",
    "help",
    "helps",
    "how",
    "perspective",
    "relevance",
    "role",
    "service",
    "support",
    "supports",
    "where",
    "why",
}

BUYER_CONTENT_TYPES = {
    "buyer",
    "buyer-guide",
    "buyer_guide",
    "buying-guide",
    "buying_guide",
    "comparison",
    "comparison-guide",
    "comparison_guide",
    "product-comparison",
    "product_comparison",
}

GENERIC_IMAGE_ALTS = {
    "article image",
    "blog image",
    "decorative image",
    "hero",
    "hero image",
    "image",
    "luxury background",
    "placeholder",
}

SERP_BENCHMARK_CONTRACT_VERSION = "serp-benchmark-v1"
VALUE_OBJECT_PATTERNS = {
    "table": (
        re.compile(r"(?m)^\s*\|.+\|\s*$"),
        re.compile(r"<table\b", re.IGNORECASE),
        re.compile(r"\b(?:decision|comparison) matrix\b", re.IGNORECASE),
    ),
    "timeline": (re.compile(r"\btimeline\b", re.IGNORECASE),),
    "checklist": (
        re.compile(r"\bchecklist\b", re.IGNORECASE),
        re.compile(r"(?m)^\s*[-*]\s+\[[ xX]\]"),
        re.compile(r"\bdecision tree\b", re.IGNORECASE),
    ),
    "calculation": (
        re.compile(r"\b(?:cost|scenario) calculation\b", re.IGNORECASE),
        re.compile(r"\btotal cost\b", re.IGNORECASE),
        re.compile(r"\bworked scenario\b", re.IGNORECASE),
    ),
    "market_comparison": (
        re.compile(r"\bmarket[- ]by[- ]market\b", re.IGNORECASE),
        re.compile(r"\bcountry[- ]by[- ]country\b", re.IGNORECASE),
        re.compile(r"\bmarket comparison\b", re.IGNORECASE),
    ),
    "risk_analysis": (
        re.compile(r"\brisk(?:s| analysis| matrix)?\b", re.IGNORECASE),
        re.compile(r"\btrade[- ]offs?\b", re.IGNORECASE),
    ),
    "primary_evidence_synthesis": (
        re.compile(r"\bprimary (?:source|evidence)\b", re.IGNORECASE),
        re.compile(r"\bverified (?:evidence|data|sources?)\b", re.IGNORECASE),
        re.compile(r"\bmethodology\b", re.IGNORECASE),
    ),
}

DELTA_STOPWORDS = {
    "about", "after", "again", "against", "article", "between", "comparing",
    "comparison", "could", "decision", "from", "have", "into", "market",
    "matrix", "more", "other", "reader", "their", "these", "this", "those",
    "through", "using", "verified", "which", "with",
}


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EditorialSafeguardError(f"{label} must be a non-empty string")
    return value.strip()


def _strip_inline_markup(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[`*_~]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_headings(content: str) -> list[Heading]:
    """Extract final H2-H6 headings while ignoring fenced code examples."""

    content = _require_text(content, "content")
    headings: list[Heading] = []
    in_fence = False
    fence_marker: str | None = None
    markdown_pattern = re.compile(r"^(#{2,6})\s+(.+?)\s*#*\s*$")
    html_pattern = re.compile(
        r"<h([2-6])(?:\s+[^>]*)?>(.*?)</h\1>", re.IGNORECASE
    )

    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.lstrip()
        fence = re.match(r"^(```+|~~~+)", stripped)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = None
            continue
        if in_fence:
            continue

        markdown_match = markdown_pattern.match(line.strip())
        if markdown_match:
            text = _strip_inline_markup(markdown_match.group(2))
            if text:
                headings.append(
                    Heading(
                        level=len(markdown_match.group(1)),
                        text=text,
                        line=line_number,
                    )
                )
            continue

        for html_match in html_pattern.finditer(line):
            text = _strip_inline_markup(html_match.group(2))
            if text:
                headings.append(
                    Heading(
                        level=int(html_match.group(1)),
                        text=text,
                        line=line_number,
                    )
                )
    return headings


def normalise_heading(text: str, entity_terms: Sequence[str] = ()) -> str:
    """Normalise punctuation, year/number tokens and supplied entity aliases."""

    text = _require_text(text, "heading")
    normalised = unicodedata.normalize("NFKC", _strip_inline_markup(text)).casefold()
    normalised = normalised.replace("&", " and ")
    normalised = re.sub(r"\bvs\.?\b", " versus ", normalised)
    normalised = re.sub(
        r"^[^:]{2,100}:\s+(?=(?:best|ideal|strongest|designed)\b)",
        " {entity}: ",
        normalised,
    )

    aliases = sorted(
        {
            unicodedata.normalize("NFKC", alias).casefold().strip()
            for alias in entity_terms
            if isinstance(alias, str) and alias.strip()
        },
        key=len,
        reverse=True,
    )
    for alias in aliases:
        normalised = re.sub(
            rf"(?<!\w){re.escape(alias)}(?!\w)", " {entity} ", normalised
        )

    normalised = re.sub(r"\b(?:19|20)\d{2}\b", " {year} ", normalised)
    normalised = re.sub(r"\b\d+(?:[.,]\d+)?\b", " {number} ", normalised)
    normalised = re.sub(r"[^\w{}]+", " ", normalised, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalised).strip()


def infer_entity_terms(content: str, title: str | None = None) -> list[str]:
    """Infer conservative comparison aliases from the final H1/title.

    Only comparison titles are inferred.  Broad list-category titles are left
    untouched; list-item prefixes such as ``Brand: best for ...`` are handled
    structurally by :func:`normalise_heading`.
    """

    candidate_title = title.strip() if isinstance(title, str) and title.strip() else ""
    if not candidate_title:
        h1 = re.search(r"^#\s+(.+?)\s*#*\s*$", content, re.MULTILINE)
        candidate_title = _strip_inline_markup(h1.group(1)) if h1 else ""
    if not candidate_title or not re.search(
        r"\b(?:vs\.?|versus)\b", candidate_title, re.IGNORECASE
    ):
        return []

    cleaned = re.sub(r"\b(?:19|20)\d{2}\b", " ", candidate_title)
    sides = re.split(r"\b(?:vs\.?|versus)\b", cleaned, flags=re.IGNORECASE)
    aliases: list[str] = []
    generic_suffix = re.compile(
        r"\b(?:premium economy|business class|first class|economy class|"
        r"size guide|comparison guide|comparison|travel guide|buyer(?:'s)? guide|"
        r"buying guide|guide|review)\b.*$",
        re.IGNORECASE,
    )
    for side in sides:
        side = re.sub(r"^[\s:—–-]+|[\s:—–-]+$", "", side)
        side = re.sub(r"^(?:best|top)\s+", "", side, flags=re.IGNORECASE)
        if len(side) >= 3:
            aliases.append(side)
        brand_prefix = generic_suffix.sub("", side).strip(" :—–-")
        if len(brand_prefix) >= 3 and brand_prefix.casefold() != side.casefold():
            aliases.append(brand_prefix)
    return list(dict.fromkeys(aliases))


def _is_common_heading(normalised: str) -> bool:
    comparable = re.sub(r"\{(?:year|number)\}", " ", normalised)
    comparable = re.sub(r"\s+", " ", comparable).strip()
    return any(pattern.fullmatch(comparable) for pattern in COMMON_HEADING_PATTERNS)


def is_vertu_integration_heading(text: str) -> bool:
    """Return whether a heading represents a VERTU/Concierge integration block."""

    normalised = normalise_heading(text)
    tokens = set(re.findall(r"[a-z]+", normalised))
    if "vertu" in tokens and "concierge" in tokens:
        return True
    if "vertu" in tokens and bool(tokens & INTEGRATION_CUES):
        return True
    if "concierge" in tokens:
        concierge_integration_cues = INTEGRATION_CUES - {"how", "service"}
        if tokens & concierge_integration_cues:
            return True
        plain_concierge_patterns = (
            r"\bwhere\b.*\bconcierge\b.*\bfit(?:s)?\b",
            r"\bhow\b.*\bconcierge\b.*\b(?:help|support|assist|add|fit)(?:s)?\b",
            r"\bconcierge\b.*\b(?:may|can|could)\b.*\b(?:help|support|assist|add|fit)\b",
            r"\bconcierge\b.*\b(?:role|advantage|perspective|relevance|connection)\b",
        )
        if any(re.search(pattern, normalised) for pattern in plain_concierge_patterns):
            return True
    return False


def duplicate_integration_evaluation(content: str) -> dict[str, Any]:
    """Evaluate duplicate brand-integration headings in one final article."""

    matches = [
        heading
        for heading in extract_headings(content)
        if is_vertu_integration_heading(heading.text)
    ]
    blocking = len(matches) > 1
    finding = None
    if blocking:
        finding = {
            "code": "DUPLICATE_VERTU_CONCIERGE_INTEGRATION",
            "severity": "required",
            "blocking": True,
            "decision_impact": "FIX",
            "evidence_label": "Measured",
            "location": [
                {"line": heading.line, "heading": heading.text} for heading in matches
            ],
            "message": (
                "Final article contains more than one VERTU/Concierge integration "
                "section; consolidate them into one article-specific section."
            ),
        }
    return {
        "code": "DUPLICATE_VERTU_CONCIERGE_INTEGRATION",
        "integration_heading_count": len(matches),
        "integration_headings": [
            {"line": heading.line, "level": heading.level, "text": heading.text}
            for heading in matches
        ],
        "blocking": blocking,
        "finding": finding,
    }


def heading_fingerprint(
    content: str,
    *,
    entity_terms: Sequence[str] = (),
) -> dict[str, Any]:
    """Create an auditable structural fingerprint from meaningful H2-H4 headings."""

    entries: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    for heading in extract_headings(content):
        if heading.level > 4:
            continue
        normalised = normalise_heading(heading.text, entity_terms)
        item = {
            "level": heading.level,
            "line": heading.line,
            "text": heading.text,
            "normalised": normalised,
        }
        if _is_common_heading(normalised):
            ignored.append(item)
        else:
            entries.append(item)

    sequence = [f"h{item['level']}:{item['normalised']}" for item in entries]
    digest = hashlib.sha256("\n".join(sequence).encode("utf-8")).hexdigest()
    return {
        "fingerprint_sha256": digest,
        "meaningful_heading_count": len(entries),
        "headings": entries,
        "ignored_common_headings": ignored,
        "sequence": sequence,
        "entity_terms": list(entity_terms),
    }


def _heading_match_score(left: dict[str, Any], right: dict[str, Any]) -> float:
    if left["level"] != right["level"]:
        return 0.0
    left_text = left["normalised"]
    right_text = right["normalised"]
    if left_text == right_text:
        return 1.0
    left_tokens = set(left_text.split())
    right_tokens = set(right_text.split())
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left_text, right_text).ratio()
    return (0.55 * jaccard) + (0.45 * sequence)


def _heading_lcs(
    left: Sequence[dict[str, Any]],
    right: Sequence[dict[str, Any]],
    *,
    heading_match_threshold: float = 0.82,
) -> tuple[int, list[dict[str, Any]]]:
    rows = len(left) + 1
    columns = len(right) + 1
    lengths = [[0] * columns for _ in range(rows)]
    for left_index in range(1, rows):
        for right_index in range(1, columns):
            if (
                _heading_match_score(
                    left[left_index - 1], right[right_index - 1]
                )
                >= heading_match_threshold
            ):
                lengths[left_index][right_index] = (
                    lengths[left_index - 1][right_index - 1] + 1
                )
            else:
                lengths[left_index][right_index] = max(
                    lengths[left_index - 1][right_index],
                    lengths[left_index][right_index - 1],
                )

    matches: list[dict[str, Any]] = []
    left_index = len(left)
    right_index = len(right)
    while left_index and right_index:
        score = _heading_match_score(left[left_index - 1], right[right_index - 1])
        if score >= heading_match_threshold:
            matches.append(
                {
                    "left": left[left_index - 1]["text"],
                    "right": right[right_index - 1]["text"],
                    "normalised_left": left[left_index - 1]["normalised"],
                    "normalised_right": right[right_index - 1]["normalised"],
                    "match_score": round(score, 6),
                }
            )
            left_index -= 1
            right_index -= 1
        elif lengths[left_index - 1][right_index] >= lengths[left_index][right_index - 1]:
            left_index -= 1
        else:
            right_index -= 1
    matches.reverse()
    return lengths[-1][-1], matches


def compare_heading_fingerprints(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    threshold: float = DEFAULT_TEMPLATE_SIMILARITY_THRESHOLD,
    min_comparable_headings: int = DEFAULT_MIN_COMPARABLE_HEADINGS,
    min_shared_headings: int = DEFAULT_MIN_SHARED_HEADINGS,
) -> dict[str, Any]:
    """Compare two fingerprints without letting generic headings trigger a flag."""

    left_headings = left["headings"]
    right_headings = right["headings"]
    smaller = min(len(left_headings), len(right_headings))
    larger = max(len(left_headings), len(right_headings))
    if smaller < min_comparable_headings:
        return {
            "similarity": 0.0,
            "shared_heading_count": 0,
            "comparable": False,
            "template_dependent": False,
            "matches": [],
        }

    shared_count, matches = _heading_lcs(left_headings, right_headings)
    containment = shared_count / smaller if smaller else 0.0
    coverage = shared_count / larger if larger else 0.0
    similarity = (0.7 * containment) + (0.3 * coverage)
    template_dependent = (
        shared_count >= min_shared_headings and similarity >= threshold
    )
    return {
        "similarity": round(similarity, 6),
        "shared_heading_count": shared_count,
        "comparable": True,
        "template_dependent": template_dependent,
        "matches": matches,
    }


def _substantive_word_count(content: str) -> int:
    without_frontmatter = re.sub(
        r"\A---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL
    )
    without_code = re.sub(
        r"```.*?```|~~~.*?~~~", " ", without_frontmatter, flags=re.DOTALL
    )
    without_urls = re.sub(r"https?://\S+", " ", without_code)
    plain = _strip_inline_markup(without_urls)
    return len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", plain, re.UNICODE))


def _is_buyer_or_comparison(content_type: str, title: str | None) -> bool:
    normalised_type = content_type.strip().casefold().replace(" ", "-")
    if normalised_type in BUYER_CONTENT_TYPES:
        return True
    if title:
        normalised_title = f" {normalise_heading(title)} "
        return any(
            marker in normalised_title
            for marker in (
                " versus ",
                " best ",
                " top ",
                " buyer ",
                " buying ",
                " compare ",
                " comparison ",
            )
        )
    return False


def _descriptive_alt(alt: str) -> bool:
    if not isinstance(alt, str) or not alt.strip():
        return False
    normalised = normalise_heading(alt)
    if normalised in GENERIC_IMAGE_ALTS:
        return False
    if {"hero", "featured", "decorative", "placeholder"} & set(normalised.split()):
        return False
    return len(re.findall(r"[a-z0-9]+", normalised)) >= 3


def _in_body_visuals(content: str) -> list[dict[str, Any]]:
    body_heading = re.search(r"^##\s+", content, re.MULTILINE)
    if not body_heading:
        body_heading = re.search(r"<h2(?:\s+[^>]*)?>", content, re.IGNORECASE)
    if not body_heading:
        return []
    body_start = body_heading.start()
    visuals: list[dict[str, Any]] = []

    markdown_image = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    for match in markdown_image.finditer(content):
        if match.start() <= body_start or not _descriptive_alt(match.group(1)):
            continue
        visuals.append(
            {
                "type": "markdown_image",
                "alt": match.group(1).strip(),
                "line": content.count("\n", 0, match.start()) + 1,
            }
        )

    html_image = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
    alt_pattern = re.compile(r"\balt\s*=\s*['\"]([^'\"]*)['\"]", re.IGNORECASE)
    for match in html_image.finditer(content):
        if match.start() <= body_start:
            continue
        alt_match = alt_pattern.search(match.group(0))
        if not alt_match or not _descriptive_alt(alt_match.group(1)):
            continue
        visuals.append(
            {
                "type": "html_image",
                "alt": alt_match.group(1).strip(),
                "line": content.count("\n", 0, match.start()) + 1,
            }
        )

    for visual_type, pattern in (
        ("svg", re.compile(r"<svg\b", re.IGNORECASE)),
        ("mermaid", re.compile(r"```mermaid\b", re.IGNORECASE)),
    ):
        for match in pattern.finditer(content):
            if match.start() > body_start:
                visuals.append(
                    {
                        "type": visual_type,
                        "alt": None,
                        "line": content.count("\n", 0, match.start()) + 1,
                    }
                )
    return visuals


def body_visual_evaluation(
    content: str,
    *,
    content_type: str,
    title: str | None = None,
    visual_exception: str | None = None,
    word_threshold: int = DEFAULT_LONG_FORM_WORD_THRESHOLD,
) -> dict[str, Any]:
    """Measure in-body evidence visuals without introducing a phase-one gate."""

    content = _require_text(content, "content")
    content_type = _require_text(content_type, "content_type")
    word_count = _substantive_word_count(content)
    applicable = _is_buyer_or_comparison(content_type, title) and word_count >= word_threshold
    exception = visual_exception.strip() if isinstance(visual_exception, str) else ""
    visuals = _in_body_visuals(content) if applicable else []

    if not applicable:
        status = "NOT_APPLICABLE"
    elif exception:
        status = "EXCEPTION"
    elif visuals:
        status = "PRESENT"
    else:
        status = "MISSING"

    warning = None
    if status == "MISSING":
        warning = {
            "code": "BODY_VISUAL_MISSING",
            "severity": "recommended",
            "blocking": False,
            "decision_impact": "NONE",
            "evidence_label": "Measured",
            "location": "article body",
            "message": (
                "Long buyer/comparison draft has no descriptive in-body evidence "
                "visual or explicit editorial exception; the hero image does not count."
            ),
            "experiment_candidate": True,
        }
    return {
        "code": "BODY_VISUAL_MISSING",
        "applicable": applicable,
        "status": status,
        "word_count": word_count,
        "word_threshold": word_threshold,
        "visual_exception": exception or None,
        "in_body_visual_count": len(visuals),
        "in_body_visuals": visuals,
        "blocking": False,
        "warning": warning,
    }


def _benchmark_fingerprint(payload: dict[str, Any]) -> str:
    material = {
        key: value for key, value in payload.items() if key != "benchmark_fingerprint"
    }
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def serp_differentiation_evaluation(
    content: str,
    *,
    benchmark: dict[str, Any] | None,
    required: bool,
) -> dict[str, Any]:
    """Verify the producer benchmark identity and visible value implementation."""

    if not required and benchmark is None:
        return {
            "code": "SERP_DIFFERENTIATION_MISMATCH",
            "applicable": False,
            "status": "NOT_APPLICABLE",
            "blocking": False,
            "finding": None,
        }

    issues: list[str] = []
    if not isinstance(benchmark, dict):
        issues.append("serp-benchmark.json is missing or invalid")
        benchmark = {}
    if benchmark.get("contract_version") != SERP_BENCHMARK_CONTRACT_VERSION:
        issues.append("SERP benchmark contract is not serp-benchmark-v1")
    if benchmark.get("verdict") != "BENCHMARK_PASS":
        issues.append("SERP benchmark verdict is not BENCHMARK_PASS")
    declared_fingerprint = benchmark.get("benchmark_fingerprint")
    computed_fingerprint = _benchmark_fingerprint(benchmark) if benchmark else None
    if not declared_fingerprint or declared_fingerprint != computed_fingerprint:
        issues.append("SERP benchmark fingerprint mismatch")

    delta = str(benchmark.get("original_value_delta") or "").strip()
    if not delta:
        issues.append("original-value delta is missing")
    required_types = [
        value
        for value in benchmark.get("required_value_object_types") or []
        if value in VALUE_OBJECT_PATTERNS
    ]
    matched_types = [
        value
        for value in required_types
        if any(pattern.search(content) for pattern in VALUE_OBJECT_PATTERNS[value])
    ]
    if required_types and not matched_types:
        issues.append("no declared article-specific value object is visible in the final body")

    delta_terms = {
        token
        for token in re.findall(r"[a-z][a-z0-9-]{4,}", delta.casefold())
        if token not in DELTA_STOPWORDS
    }
    content_terms = set(re.findall(r"[a-z][a-z0-9-]{4,}", content.casefold()))
    matched_terms = sorted(delta_terms & content_terms)
    minimum_term_matches = min(2, len(delta_terms)) if delta_terms else 0
    if minimum_term_matches and len(matched_terms) < minimum_term_matches:
        issues.append("final body does not substantively reflect the declared original-value delta")

    finding = None
    if issues:
        finding = {
            "code": "SERP_DIFFERENTIATION_MISMATCH",
            "severity": "required",
            "blocking": True,
            "decision_impact": "FIX",
            "evidence_label": "Measured",
            "location": "SERP benchmark bundle and final article body",
            "message": "; ".join(issues),
            "benchmark_fingerprint": declared_fingerprint,
        }
    return {
        "code": "SERP_DIFFERENTIATION_MISMATCH",
        "applicable": True,
        "status": "MISMATCH" if issues else "PASS",
        "blocking": bool(issues),
        "benchmark_fingerprint": declared_fingerprint,
        "computed_benchmark_fingerprint": computed_fingerprint,
        "required_value_object_types": required_types,
        "matched_value_object_types": matched_types,
        "matched_delta_terms": matched_terms,
        "finding": finding,
    }


def _summarise_article(
    *,
    article_key: str,
    duplicate: dict[str, Any],
    visual: dict[str, Any],
    fingerprint: dict[str, Any],
    serp_differentiation: dict[str, Any] | None = None,
    additional_findings: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    findings = [finding for finding in (duplicate.get("finding"),) if finding]
    findings.extend(additional_findings)
    if serp_differentiation and serp_differentiation.get("finding"):
        findings.append(serp_differentiation["finding"])
    warnings = [warning for warning in (visual.get("warning"),) if warning]
    required_count = sum(
        1
        for finding in findings
        if finding.get("blocking") and finding.get("severity") == "required"
    )
    critical_count = sum(
        1
        for finding in findings
        if finding.get("blocking") and finding.get("severity") == "critical"
    )
    return {
        "schema_version": SAFEGUARD_SCHEMA_VERSION,
        "qa_handoff_contract_version": QA_HANDOFF_CONTRACT_VERSION,
        "article_key": article_key,
        "preflight_pass": required_count == 0 and critical_count == 0,
        "minimum_qa_status": "FIX" if required_count or critical_count else "PASS",
        "qa_handoff_counts": {
            "unresolved_critical": critical_count,
            "unresolved_required": required_count,
            "unresolved_recommended": len(warnings),
        },
        "blocking_codes": [
            finding["code"] for finding in findings if finding.get("blocking")
        ],
        "warning_codes": [warning["code"] for warning in warnings],
        "findings": findings,
        "warnings": warnings,
        "duplicate_integration": duplicate,
        "body_visual": visual,
        "heading_fingerprint": fingerprint,
        "serp_differentiation": serp_differentiation,
    }


def evaluate_article(
    *,
    article_key: str,
    content: str,
    content_type: str,
    title: str | None = None,
    entity_terms: Sequence[str] = (),
    visual_exception: str | None = None,
    word_threshold: int = DEFAULT_LONG_FORM_WORD_THRESHOLD,
    serp_benchmark: dict[str, Any] | None = None,
    require_serp_benchmark: bool = False,
) -> dict[str, Any]:
    article_key = _require_text(article_key, "article_key")
    effective_entity_terms = list(
        dict.fromkeys(
            [
                *(
                    term.strip()
                    for term in entity_terms
                    if isinstance(term, str) and term.strip()
                ),
                *infer_entity_terms(content, title),
            ]
        )
    )
    duplicate = duplicate_integration_evaluation(content)
    visual = body_visual_evaluation(
        content,
        content_type=content_type,
        title=title,
        visual_exception=visual_exception,
        word_threshold=word_threshold,
    )
    fingerprint = heading_fingerprint(content, entity_terms=effective_entity_terms)
    serp_differentiation = serp_differentiation_evaluation(
        content,
        benchmark=serp_benchmark,
        required=require_serp_benchmark,
    )
    return _summarise_article(
        article_key=article_key,
        duplicate=duplicate,
        visual=visual,
        fingerprint=fingerprint,
        serp_differentiation=serp_differentiation,
    )


def evaluate_batch(
    articles: Sequence[dict[str, Any]],
    *,
    similarity_threshold: float = DEFAULT_TEMPLATE_SIMILARITY_THRESHOLD,
    min_comparable_headings: int = DEFAULT_MIN_COMPARABLE_HEADINGS,
    min_shared_headings: int = DEFAULT_MIN_SHARED_HEADINGS,
    word_threshold: int = DEFAULT_LONG_FORM_WORD_THRESHOLD,
) -> dict[str, Any]:
    """Evaluate article safeguards plus pairwise final-heading similarity."""

    if len(articles) < 1:
        raise EditorialSafeguardError("articles must contain at least one article")
    if not 0 <= similarity_threshold <= 1:
        raise EditorialSafeguardError("similarity_threshold must be between 0 and 1")

    base_results: dict[str, dict[str, Any]] = {}
    fingerprints: dict[str, dict[str, Any]] = {}
    for index, article in enumerate(articles):
        if not isinstance(article, dict):
            raise EditorialSafeguardError(f"articles[{index}] must be an object")
        article_key = _require_text(article.get("article_key"), f"articles[{index}].article_key")
        if article_key in base_results:
            raise EditorialSafeguardError(f"duplicate article_key: {article_key}")
        result = evaluate_article(
            article_key=article_key,
            content=_require_text(article.get("content"), f"articles[{index}].content"),
            content_type=_require_text(
                article.get("content_type"), f"articles[{index}].content_type"
            ),
            title=article.get("title"),
            entity_terms=article.get("entity_terms") or (),
            visual_exception=article.get("visual_exception"),
            word_threshold=word_threshold,
            serp_benchmark=article.get("serp_benchmark"),
            require_serp_benchmark=bool(article.get("require_serp_benchmark")),
        )
        base_results[article_key] = result
        fingerprints[article_key] = result["heading_fingerprint"]

    keys = list(base_results)
    pairs: list[dict[str, Any]] = []
    affected: dict[str, list[dict[str, Any]]] = {key: [] for key in keys}
    for left_index, left_key in enumerate(keys):
        for right_key in keys[left_index + 1 :]:
            comparison = compare_heading_fingerprints(
                fingerprints[left_key],
                fingerprints[right_key],
                threshold=similarity_threshold,
                min_comparable_headings=min_comparable_headings,
                min_shared_headings=min_shared_headings,
            )
            pair = {
                "left_article_key": left_key,
                "right_article_key": right_key,
                **comparison,
            }
            pairs.append(pair)
            if comparison["template_dependent"]:
                affected[left_key].append(pair)
                affected[right_key].append(pair)

    final_results: list[dict[str, Any]] = []
    for article_key in keys:
        base = base_results[article_key]
        template_findings: list[dict[str, Any]] = []
        if affected[article_key]:
            template_findings.append(
                {
                    "code": "TEMPLATE_DEPENDENT_DRAFT",
                    "severity": "required",
                    "blocking": True,
                    "decision_impact": "FIX",
                    "evidence_label": "Measured",
                    "location": "final article heading structure",
                    "message": (
                        "Final heading fingerprint materially repeats another draft "
                        "in the current batch."
                    ),
                    "similar_pairs": [
                        {
                            "other_article_key": (
                                pair["right_article_key"]
                                if pair["left_article_key"] == article_key
                                else pair["left_article_key"]
                            ),
                            "similarity": pair["similarity"],
                            "shared_heading_count": pair["shared_heading_count"],
                        }
                        for pair in affected[article_key]
                    ],
                }
            )
        final_results.append(
            _summarise_article(
                article_key=article_key,
                duplicate=base["duplicate_integration"],
                visual=base["body_visual"],
                fingerprint=base["heading_fingerprint"],
                serp_differentiation=base.get("serp_differentiation"),
                additional_findings=template_findings,
            )
        )

    return {
        "schema_version": SAFEGUARD_SCHEMA_VERSION,
        "qa_handoff_contract_version": QA_HANDOFF_CONTRACT_VERSION,
        "similarity_threshold": similarity_threshold,
        "min_comparable_headings": min_comparable_headings,
        "min_shared_headings": min_shared_headings,
        "template_dependent_pair_count": sum(
            1 for pair in pairs if pair["template_dependent"]
        ),
        "template_dependent_article_keys": sorted(
            key for key, value in affected.items() if value
        ),
        "preflight_pass": all(result["preflight_pass"] for result in final_results),
        "pairs": pairs,
        "articles": final_results,
    }


def _load_manifest_articles(manifest_path: pathlib.Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EditorialSafeguardError("batch manifest must be a JSON object")
    contract = payload.get("qa_handoff_contract_version")
    if contract not in (None, QA_HANDOFF_CONTRACT_VERSION):
        raise EditorialSafeguardError(
            f"unsupported qa_handoff_contract_version: {contract}"
        )
    raw_articles = payload.get("articles")
    if not isinstance(raw_articles, list) or not raw_articles:
        raise EditorialSafeguardError("batch manifest articles must be a non-empty list")
    articles: list[dict[str, Any]] = []
    for index, raw_article in enumerate(raw_articles):
        if not isinstance(raw_article, dict):
            raise EditorialSafeguardError(f"articles[{index}] must be an object")
        content = raw_article.get("content")
        raw_path = raw_article.get("path")
        if bool(content) == bool(raw_path):
            raise EditorialSafeguardError(
                f"articles[{index}] must provide exactly one of content or path"
            )
        if raw_path:
            article_path = pathlib.Path(raw_path).expanduser()
            if not article_path.is_absolute():
                article_path = manifest_path.parent / article_path
            content = article_path.read_text(encoding="utf-8")
        articles.append(
            {
                "article_key": raw_article.get("article_key"),
                "content": content,
                "content_type": raw_article.get("content_type"),
                "title": raw_article.get("title"),
                "entity_terms": raw_article.get("entity_terms") or (),
                "visual_exception": raw_article.get("visual_exception"),
                "serp_benchmark": (
                    json.loads(
                        (
                            manifest_path.parent / raw_article["serp_benchmark_path"]
                            if not pathlib.Path(raw_article["serp_benchmark_path"]).is_absolute()
                            else pathlib.Path(raw_article["serp_benchmark_path"])
                        ).read_text(encoding="utf-8")
                    )
                    if raw_article.get("serp_benchmark_path")
                    else raw_article.get("serp_benchmark")
                ),
                "require_serp_benchmark": bool(raw_article.get("require_serp_benchmark")),
            }
        )
    return payload, articles


def _emit_result(result: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if output:
        pathlib.Path(output).expanduser().write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    article_parser = subparsers.add_parser("article")
    article_parser.add_argument("--input", required=True)
    article_parser.add_argument("--article-key", required=True)
    article_parser.add_argument("--content-type", required=True)
    article_parser.add_argument("--title")
    article_parser.add_argument("--entity", action="append", default=[])
    article_parser.add_argument("--visual-exception")
    article_parser.add_argument("--serp-benchmark")
    article_parser.add_argument("--require-serp-benchmark", action="store_true")
    article_parser.add_argument(
        "--word-threshold", type=int, default=DEFAULT_LONG_FORM_WORD_THRESHOLD
    )
    article_parser.add_argument("--output")

    batch_parser = subparsers.add_parser("batch")
    batch_parser.add_argument("--manifest", required=True)
    batch_parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=DEFAULT_TEMPLATE_SIMILARITY_THRESHOLD,
    )
    batch_parser.add_argument(
        "--min-comparable-headings",
        type=int,
        default=DEFAULT_MIN_COMPARABLE_HEADINGS,
    )
    batch_parser.add_argument(
        "--min-shared-headings",
        type=int,
        default=DEFAULT_MIN_SHARED_HEADINGS,
    )
    batch_parser.add_argument(
        "--word-threshold", type=int, default=DEFAULT_LONG_FORM_WORD_THRESHOLD
    )
    batch_parser.add_argument("--output")

    args = parser.parse_args(argv)
    if args.command == "article":
        content = pathlib.Path(args.input).expanduser().read_text(encoding="utf-8")
        result = evaluate_article(
            article_key=args.article_key,
            content=content,
            content_type=args.content_type,
            title=args.title,
            entity_terms=args.entity,
            visual_exception=args.visual_exception,
            word_threshold=args.word_threshold,
            serp_benchmark=(
                json.loads(pathlib.Path(args.serp_benchmark).expanduser().read_text(encoding="utf-8"))
                if args.serp_benchmark
                else None
            ),
            require_serp_benchmark=args.require_serp_benchmark,
        )
        output = args.output
    else:
        manifest_path = pathlib.Path(args.manifest).expanduser().resolve()
        _, articles = _load_manifest_articles(manifest_path)
        result = evaluate_batch(
            articles,
            similarity_threshold=args.similarity_threshold,
            min_comparable_headings=args.min_comparable_headings,
            min_shared_headings=args.min_shared_headings,
            word_threshold=args.word_threshold,
        )
        output = args.output
    _emit_result(result, output)
    return 0 if result["preflight_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

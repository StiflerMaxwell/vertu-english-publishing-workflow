#!/usr/bin/env python3
"""Audit legacy VERTU inventories against the brand-mindset boundary.

Historical rows predate explicit semantic evidence, so this conservative
replay identifies only obvious conflicts, clear core topics, and qualified
adjacent topics. Unclear rows remain HOLD. The result is audit-only and has no
score, selection, QA, repair, or publication authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


CONTRACT_VERSION = "brand-mindset-replay-v1"

COMMODITY_PATTERNS = (
    r"\brefrigerator\b", r"\bwasher\b", r"\bdryer\b", r"\bwater heater\b",
    r"\bheat pump\b", r"\bfurnace\b", r"\bcooktop\b", r"\boven\b",
    r"\bcookware\b", r"\bblender\b", r"\bfood processor\b",
    r"\bpressure cooker\b", r"\bslow cooker\b", r"\bwater softener\b",
    r"\bwater filter\b", r"\bhumidifier\b", r"\bdehumidifier\b",
    r"\bair conditioner\b", r"\bair quality monitor\b", r"\bsofa\b",
    r"\bmattress\b", r"\bduvet\b", r"\bbath towel", r"\bpillow(case)?\b",
    r"\bweighted blanket\b", r"\btreadmill\b", r"\bcutting board\b",
    r"\bgas range\b", r"\bskillet\b", r"\bice maker\b", r"\bpizza oven\b",
    r"\bcordless vacuum\b", r"\bsurge protector\b",
)

CORE_PATTERNS = (
    r"\bvertu\b", r"\bluxury phone\b", r"\bmost expensive (phone|watch)",
    r"\bfoldable phone\b", r"\bflip phone\b", r"\bsmart ring\b",
    r"\bfitness ring\b", r"\bsleep-tracking ring\b", r"\bwatch\b",
    r"\bdiamond\b", r"\bgemstone\b", r"\bruby\b", r"\bsapphire\b",
    r"\bemerald\b", r"\bpearl", r"\bjewellery\b", r"\bplatinum ring\b",
    r"\bgold(-plated|-filled)?\b", r"\bprivacy\b", r"\bsecure email\b",
    r"\bencryption\b", r"\bpassword manager\b",
)

ADJACENT_PATTERNS = (
    r"\b(first|business) class\b", r"\bairport lounge\b", r"\bhotel\b",
    r"\bresort\b", r"\btravel insurance\b", r"\bchampagne\b",
    r"\bprosecco\b", r"\bcava\b", r"\bwhisk(e)?y\b", r"\bscotch\b",
    r"\bcognac\b", r"\bbrandy\b", r"\btequila\b", r"\bmezcal\b",
    r"\bsedan\b", r"\bsuv\b", r"\bcoupe\b", r"\bdrivetrain\b",
    r"\btyres\b", r"\bceramic coating\b", r"\bturbo\b",
    r"\bsupercharger\b", r"\bshirt\b", r"\bcoat\b", r"\bblazer\b",
    r"\bsuit jacket\b", r"\boxford shoes\b", r"\bdenim\b", r"\bnubuck\b",
    r"\bsuede\b", r"\bsilk\b", r"\bcamera\b", r"\bphotograph",
    r"\blens\b", r"\bhi-fi\b", r"\bamplifier\b", r"\bopen-ear earbuds\b",
    r"\bai translation earbuds\b", r"\bai data cent", r"\bchip manufacturing\b",
    r"\bai model pricing\b", r"\bchatgpt ads\b",
)


def _matches(text: str, patterns: Iterable[str]) -> List[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, re.I)]


def classify_legacy_article(row: Dict[str, Any]) -> Dict[str, Any]:
    title = str(row.get("title") or row.get("headline") or row.get("name") or "")
    cluster = str(row.get("cluster_id") or row.get("audience_fit_lane") or "")
    text = f"{title} {cluster}".casefold()
    commodity = _matches(text, COMMODITY_PATTERNS)
    core = _matches(text, CORE_PATTERNS)
    adjacent = _matches(text, ADJACENT_PATTERNS)

    if commodity:
        verdict, classification = "REJECT", "UNQUALIFIED"
        reason = "OBVIOUS_COMMODITY_LIFESTYLE_CONFLICT"
    elif core:
        verdict, classification = "PASS", "CORE_MINDSPACE"
        reason = "LEGACY_METADATA_MATCHED_CLEAR_CORE"
    elif adjacent:
        verdict, classification = "PASS", "QUALIFIED_ADJACENT"
        reason = "LEGACY_METADATA_MATCHED_QUALIFIED_ADJACENT"
    else:
        verdict, classification = "HOLD", "UNQUALIFIED"
        reason = "EXPLICIT_SEMANTIC_EVIDENCE_NOT_RECORDED"

    return {
        "title": title,
        "url": row.get("url") or row.get("canonical_url"),
        "candidate_id": row.get("candidate_id"),
        "cluster_id": row.get("cluster_id"),
        "verdict": verdict,
        "brand_mindset_class": classification,
        "reason": reason,
        "matched_core_rules": core,
        "matched_adjacent_rules": adjacent,
        "matched_conflict_rules": commodity,
        "evidence_quality": "LEGACY_INFERRED",
        "production_authority": False,
        "repair_authority": False,
    }


def _load_rows(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("articles"), list):
        return [row for row in payload["articles"] if isinstance(row, dict)]
    return [
        row
        for key in ("selected", "rejected")
        for row in payload.get(key) or []
        if isinstance(row, dict)
    ]


def _fingerprint(payload: Dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "fingerprint"}
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def replay(paths: Sequence[Path]) -> Dict[str, Any]:
    results = [
        classify_legacy_article(row)
        for path in paths
        for row in _load_rows(path)
    ]
    clear_core = [row for row in results if row["matched_core_rules"]]
    false_rejections = [row for row in clear_core if row["verdict"] == "REJECT"]
    report = {
        "contract_version": CONTRACT_VERSION,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "LEGACY_AUDIT_ONLY",
        "source_paths": [str(path.resolve()) for path in paths],
        "counts": {
            "total": len(results),
            "core": sum(row["brand_mindset_class"] == "CORE_MINDSPACE" for row in results),
            "qualified_adjacent": sum(row["brand_mindset_class"] == "QUALIFIED_ADJACENT" for row in results),
            "hold": sum(row["verdict"] == "HOLD" for row in results),
            "reject": sum(row["verdict"] == "REJECT" for row in results),
        },
        "clear_core_audit": {
            "audited_count": len(clear_core),
            "false_rejection_count": len(false_rejections),
            "false_rejection_rate": round(len(false_rejections) / len(clear_core), 4) if clear_core else None,
            "rollback_threshold": 0.20,
            "threshold_breached": bool(clear_core and len(false_rejections) / len(clear_core) > 0.20),
        },
        "authority": {"score": False, "selection": False, "qa": False, "repair": False, "publication": False},
        "limitations": [
            "Historical rows predate explicit brand-mindset semantic evidence.",
            "HOLD means editorial evidence is missing, not that the topic is necessarily poor.",
            "This replay may identify obvious conflicts but cannot activate or relax the production gate.",
        ],
        "results": results,
    }
    report["fingerprint"] = _fingerprint(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fetch auditable Google Trends Trending Now evidence for VERTU topic discovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence


RSS_URL = "https://trends.google.com/trending/rss?geo={geo}"
HT_NAMESPACE = "https://trends.google.com/trending/rss"
DEFAULT_MARKETS = ("US", "GB", "AU", "CA", "AE", "SA", "SG", "HK", "IN")
MARKET_TIERS = {
    "core_english": ("US", "GB", "AU", "CA"),
    "premium_global_mobility": ("AE", "SA", "SG", "HK"),
    "scale_reach": ("IN",),
}


def parse_approx_traffic(value: Any) -> Optional[int]:
    text = str(value or "").strip().upper().replace(",", "")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\+?", text)
    if not match:
        return None
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    return int(float(match.group(1)) * multiplier[match.group(2)])


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(parent: ET.Element, tag: str) -> str:
    node = parent.find(tag)
    return (node.text or "").strip() if node is not None else ""


def parse_feed(
    xml_text: str,
    geo: str,
    *,
    observed_at: Optional[datetime] = None,
    max_items: int = 50,
) -> List[Dict[str, Any]]:
    now = observed_at or datetime.now(timezone.utc)
    root = ET.fromstring(xml_text)
    items: List[Dict[str, Any]] = []
    for item in root.findall("./channel/item")[:max_items]:
        title = _text(item, "title")
        published_raw = _text(item, "pubDate")
        try:
            published = parsedate_to_datetime(published_raw)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        published = published.astimezone(timezone.utc)
        if not title or published > now + timedelta(minutes=5):
            continue
        age_hours = max(0.0, (now - published.astimezone(timezone.utc)).total_seconds() / 3600)
        if age_hours <= 4:
            freshness = "LAST_4H"
        elif age_hours <= 24:
            freshness = "LAST_24H"
        elif age_hours <= 48:
            freshness = "LAST_48H"
        else:
            freshness = "LAST_7D"
        news_items = []
        for news in item.findall(f"{{{HT_NAMESPACE}}}news_item"):
            news_title = _text(news, f"{{{HT_NAMESPACE}}}news_item_title")
            news_url = _text(news, f"{{{HT_NAMESPACE}}}news_item_url")
            news_source = _text(news, f"{{{HT_NAMESPACE}}}news_item_source")
            if news_title and news_url.startswith("https://") and news_source:
                news_items.append(
                    {
                        "title": news_title,
                        "url": news_url,
                        "source": news_source,
                    }
                )
        raw_traffic = _text(item, f"{{{HT_NAMESPACE}}}approx_traffic")
        items.append(
            {
                "query": title,
                "geo": geo,
                "published_at": _utc_iso(published),
                "age_hours": round(age_hours, 2),
                "freshness_bucket": freshness,
                "approx_traffic_label": raw_traffic,
                "approx_traffic": parse_approx_traffic(raw_traffic),
                "news_confirmation_count": len(news_items),
                "news_items": news_items,
                "source_url": RSS_URL.format(geo=geo),
                "source_method": "official_trending_now_rss",
                "official_google_source": True,
            }
        )
    return items


def _default_fetch(url: str, timeout: float) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "VERTU-Content-Trends/3.3.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _market_tier(geo: str) -> str:
    for tier, markets in MARKET_TIERS.items():
        if geo in markets:
            return tier
    return "other"


def build_snapshot(
    markets: Iterable[str],
    *,
    run_id: str,
    timeout: float = 20.0,
    max_items: int = 50,
    observed_at: Optional[datetime] = None,
    fetcher: Callable[[str, float], str] = _default_fetch,
) -> Dict[str, Any]:
    run_id = str(run_id or "").strip()
    if not run_id:
        raise ValueError("run_id is required")
    now = observed_at or datetime.now(timezone.utc)
    market_rows = []
    aggregate: Dict[str, Dict[str, Any]] = {}
    for raw_geo in markets:
        geo = str(raw_geo).strip().upper()
        if not geo:
            continue
        url = RSS_URL.format(geo=geo)
        try:
            items = parse_feed(
                fetcher(url, timeout),
                geo,
                observed_at=now,
                max_items=max_items,
            )
            market_rows.append(
                {
                    "geo": geo,
                    "market_tier": _market_tier(geo),
                    "status": "AVAILABLE",
                    "source_url": url,
                    "item_count": len(items),
                    "items": items,
                }
            )
            for item in items:
                key = item["query"].casefold()
                row = aggregate.setdefault(
                    key,
                    {
                        "query": item["query"],
                        "markets": [],
                        "market_tiers": [],
                        "newest_published_at": item["published_at"],
                        "minimum_age_hours": item["age_hours"],
                        "max_approx_traffic": item["approx_traffic"],
                        "news_confirmation_count": 0,
                        "evidence": [],
                    },
                )
                row["markets"].append(geo)
                row["market_tiers"].append(_market_tier(geo))
                row["minimum_age_hours"] = min(row["minimum_age_hours"], item["age_hours"])
                row["newest_published_at"] = max(row["newest_published_at"], item["published_at"])
                traffic = item["approx_traffic"]
                if traffic is not None:
                    row["max_approx_traffic"] = max(row["max_approx_traffic"] or 0, traffic)
                row["news_confirmation_count"] += item["news_confirmation_count"]
                row["evidence"].append(
                    {
                        "geo": geo,
                        "published_at": item["published_at"],
                        "approx_traffic": item["approx_traffic"],
                        "news_confirmation_count": item["news_confirmation_count"],
                        "source_url": item["source_url"],
                    }
                )
        except Exception as error:  # preserve per-market source failure without hiding other markets
            market_rows.append(
                {
                    "geo": geo,
                    "market_tier": _market_tier(geo),
                    "status": "SOURCE_UNAVAILABLE",
                    "source_url": url,
                    "reason": f"{type(error).__name__}: {error}",
                    "item_count": 0,
                    "items": [],
                }
            )
    topics = []
    for row in aggregate.values():
        row["markets"] = sorted(set(row["markets"]))
        row["market_tiers"] = sorted(set(row["market_tiers"]))
        row["realtime_candidate"] = (
            row["minimum_age_hours"] <= 24
            and (row["max_approx_traffic"] or 0) > 0
            and row["news_confirmation_count"] > 0
        )
        topics.append(row)
    topics.sort(
        key=lambda row: (
            not row["realtime_candidate"],
            -(row["max_approx_traffic"] or 0),
            row["minimum_age_hours"],
            row["query"].casefold(),
        )
    )
    available_count = sum(row["status"] == "AVAILABLE" for row in market_rows)
    status = (
        "AVAILABLE"
        if available_count == len(market_rows)
        else "PARTIAL"
        if available_count
        else "SOURCE_UNAVAILABLE"
    )
    snapshot = {
        "contract_version": "realtime-trends-v1",
        "run_id": run_id,
        "provider": "google_trends_trending_now",
        "source_method": "official_trending_now_rss",
        "official_google_source": True,
        "status": status,
        "observed_at": _utc_iso(now),
        "markets_requested": [row["geo"] for row in market_rows],
        "market_tiers": {key: list(value) for key, value in MARKET_TIERS.items()},
        "markets": market_rows,
        "topics": topics,
        "credentials_included": False,
    }
    snapshot["snapshot_fingerprint"] = snapshot_fingerprint(snapshot)
    return snapshot


def snapshot_fingerprint(snapshot: Dict[str, Any]) -> str:
    material = {
        key: value
        for key, value in snapshot.items()
        if key != "snapshot_fingerprint"
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_market_map(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contract_version": snapshot.get("contract_version"),
        "run_id": snapshot.get("run_id"),
        "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "observed_at": snapshot.get("observed_at"),
        "status": snapshot.get("status"),
        "markets": [
            {
                "geo": row.get("geo"),
                "market_tier": row.get("market_tier"),
                "status": row.get("status"),
                "item_count": row.get("item_count"),
                "source_url": row.get("source_url"),
                "reason": row.get("reason"),
            }
            for row in snapshot.get("markets") or []
        ],
    }


def build_hotness_gate(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    topics = [
        {
            "trend_query": row.get("query"),
            "markets": row.get("markets"),
            "newest_published_at": row.get("newest_published_at"),
            "max_approx_traffic": row.get("max_approx_traffic"),
            "news_confirmation_count": row.get("news_confirmation_count"),
        }
        for row in snapshot.get("topics") or []
        if row.get("realtime_candidate") is True
    ]
    return {
        "contract_version": "hotness-gate-v1",
        "run_id": snapshot.get("run_id"),
        "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "observed_at": snapshot.get("observed_at"),
        "source_status": snapshot.get("status"),
        "realtime_candidate_count": len(topics),
        "topics": topics,
        "credentials_included": False,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--markets", nargs="+", default=list(DEFAULT_MARKETS))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-items", type=int, default=50)
    parser.add_argument("--market-map-output", required=True, type=Path)
    parser.add_argument("--hotness-gate-output", required=True, type=Path)
    args = parser.parse_args(argv)
    snapshot = build_snapshot(
        args.markets,
        run_id=args.run_id,
        timeout=args.timeout,
        max_items=args.max_items,
    )
    _write_json(args.output, snapshot)
    if args.market_map_output is not None:
        _write_json(args.market_map_output, build_market_map(snapshot))
    if args.hotness_gate_output is not None:
        _write_json(args.hotness_gate_output, build_hotness_gate(snapshot))
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "markets": len(snapshot["markets"]),
                "available_markets": sum(
                    row["status"] == "AVAILABLE" for row in snapshot["markets"]
                ),
                "topics": len(snapshot["topics"]),
                "realtime_candidates": sum(
                    row["realtime_candidate"] for row in snapshot["topics"]
                ),
                "output": str(args.output),
            }
        )
    )
    return 0 if snapshot["status"] != "SOURCE_UNAVAILABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())

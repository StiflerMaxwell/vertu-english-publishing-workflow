#!/usr/bin/env python3
"""Build shadow-only YouTube topic signals for VERTU candidate discovery.

The contract deliberately grants YouTube no Search-demand, Google-trend,
eligibility, veto or score authority.  Inputs may be a reproducible normalised
export or the official YouTube Data API when an API key is available only in
the environment.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import statistics
import subprocess
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


UTC = dt.timezone.utc
CONTRACT_VERSION = "youtube-topic-signals-v1"
API_ROOT = "https://www.googleapis.com/youtube/v3"
DEFAULT_WINDOW_HOURS = 72
USER_AGENT = "VERTU-YouTube-Signal/1.0 (+https://vertu.com/)"
DEFAULT_KEYCHAIN_SERVICE = "vertu-youtube-data-api"


class YouTubeSignalError(RuntimeError):
    pass


def _iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fingerprint(payload: Dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "snapshot_fingerprint"}
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def resolve_api_key(
    environment_name: str,
    keychain_service: str = DEFAULT_KEYCHAIN_SERVICE,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve the credential without logging or persisting its value."""
    environment_value = os.environ.get(environment_name)
    if environment_value:
        return environment_value.strip(), "environment"
    if not keychain_service:
        return None, None
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                keychain_service,
                "-w",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    value = result.stdout.strip() if result.returncode == 0 else ""
    return (value, "macos_keychain") if value else (None, None)


def _normalise_rows(payload: Any) -> List[Dict[str, Any]]:
    rows = payload.get("videos") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise YouTubeSignalError("input must be a list or an object containing videos[]")
    normalised: List[Dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        query = str(raw.get("query") or "").strip()
        market = str(raw.get("market") or "").strip().upper()
        video_id = str(raw.get("video_id") or "").strip()
        channel_id = str(raw.get("channel_id") or "").strip()
        published_at = _parse_time(raw.get("published_at"))
        if not all((query, market, video_id, channel_id, published_at)):
            continue
        normalised.append(
            {
                "query": query,
                "market": market,
                "video_id": video_id,
                "channel_id": channel_id,
                "published_at": _iso(published_at),
                "views": _number(raw.get("views")),
                "likes": _number(raw.get("likes")),
                "comments": _number(raw.get("comments")),
                "subscriber_count": _number(raw.get("subscriber_count")),
                "source_url": raw.get("source_url") or f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return normalised


def _official_get(resource: str, params: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    request = urllib.request.Request(
        f"{API_ROOT}/{resource}?{urllib.parse.urlencode(params)}",
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "x-goog-api-key": api_key,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise YouTubeSignalError(f"official YouTube API request failed: {type(error).__name__}") from error


def fetch_official_rows(
    queries: Sequence[str],
    markets: Sequence[str],
    api_key: str,
    now: dt.datetime,
    window_hours: int,
) -> List[Dict[str, Any]]:
    published_after = _iso(now - dt.timedelta(hours=window_hours))
    rows: List[Dict[str, Any]] = []
    for market in markets:
        for query in queries:
            search = _official_get(
                "search",
                {
                    "part": "snippet",
                    "type": "video",
                    "q": query,
                    "regionCode": market,
                    "publishedAfter": published_after,
                    "order": "date",
                    "maxResults": 25,
                },
                api_key,
            )
            ids = [
                str(item.get("id", {}).get("videoId") or "")
                for item in search.get("items") or []
            ]
            ids = [value for value in ids if value]
            if not ids:
                continue
            details = _official_get(
                "videos",
                {"part": "snippet,statistics", "id": ",".join(ids)},
                api_key,
            )
            channel_ids = sorted(
                {
                    str(item.get("snippet", {}).get("channelId") or "")
                    for item in details.get("items") or []
                    if item.get("snippet", {}).get("channelId")
                }
            )
            subscribers: Dict[str, Optional[float]] = {}
            if channel_ids:
                channel_payload = _official_get(
                    "channels",
                    {"part": "statistics", "id": ",".join(channel_ids)},
                    api_key,
                )
                for item in channel_payload.get("items") or []:
                    channel_id = str(item.get("id") or "")
                    subscribers[channel_id] = _number(
                        item.get("statistics", {}).get("subscriberCount")
                    )
            for item in details.get("items") or []:
                snippet = item.get("snippet") or {}
                stats = item.get("statistics") or {}
                video_id = str(item.get("id") or "")
                channel_id = str(snippet.get("channelId") or "")
                rows.append(
                    {
                        "query": query,
                        "market": market.upper(),
                        "video_id": video_id,
                        "channel_id": channel_id,
                        "published_at": snippet.get("publishedAt"),
                        "views": stats.get("viewCount"),
                        "likes": stats.get("likeCount"),
                        "comments": stats.get("commentCount"),
                        "subscriber_count": subscribers.get(channel_id),
                        "source_url": f"https://www.youtube.com/watch?v={video_id}",
                    }
                )
    return _normalise_rows(rows)


def _percentile(values: Sequence[float], fraction: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return round(ordered[index], 4)


def _classify(video_count: int, channel_count: int, total_views: float, median_vph: float) -> str:
    if video_count >= 5 and channel_count >= 3 and total_views >= 25_000 and median_vph >= 150:
        return "YOUTUBE_BREAKOUT"
    if video_count >= 3 and channel_count >= 2 and total_views >= 5_000 and median_vph >= 50:
        return "YOUTUBE_RISING"
    return "NONE"


def build_snapshot(
    run_id: str,
    rows: Iterable[Dict[str, Any]],
    now: Optional[dt.datetime] = None,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    source_type: str = "normalised_export",
) -> Dict[str, Any]:
    now = (now or dt.datetime.now(tz=UTC)).astimezone(UTC)
    cutoff = now - dt.timedelta(hours=window_hours)
    grouped: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    rejected = 0
    for row in rows:
        published_at = _parse_time(row.get("published_at"))
        if published_at is None or published_at < cutoff or published_at > now + dt.timedelta(minutes=5):
            rejected += 1
            continue
        grouped[(str(row["query"]), str(row["market"]))].append(row)

    signals: List[Dict[str, Any]] = []
    for (query, market), videos in sorted(grouped.items()):
        velocities: List[float] = []
        engagements: List[float] = []
        total_views = 0.0
        for video in videos:
            views = _number(video.get("views")) or 0.0
            age_hours = max(
                (now - _parse_time(video.get("published_at"))).total_seconds() / 3600.0,
                1.0,
            )
            velocities.append(views / age_hours)
            total_views += views
            likes = _number(video.get("likes")) or 0.0
            comments = _number(video.get("comments")) or 0.0
            if views > 0:
                engagements.append((likes + comments) / views)
        median_vph = statistics.median(velocities) if velocities else 0.0
        channel_count = len({str(video.get("channel_id")) for video in videos})
        signal = _classify(len(videos), channel_count, total_views, median_vph)
        signals.append(
            {
                "query": query,
                "market": market,
                "signal": signal,
                "video_count": len(videos),
                "independent_channel_count": channel_count,
                "total_views": int(total_views),
                "median_views_per_hour": round(median_vph, 4),
                "p75_views_per_hour": _percentile(velocities, 0.75),
                "median_engagement_ratio": (
                    round(statistics.median(engagements), 6) if engagements else None
                ),
                "newest_published_at": max(video["published_at"] for video in videos),
                "source_urls": sorted({str(video["source_url"]) for video in videos}),
            }
        )

    snapshot: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "publication_run_id": run_id,
        "status": "AVAILABLE" if signals else "SOURCE_UNAVAILABLE",
        "source_type": source_type,
        "observed_at": _iso(now),
        "source_window_hours": window_hours,
        "signals": signals,
        "summary": {
            "signal_count": len(signals),
            "youtube_breakout_count": sum(row["signal"] == "YOUTUBE_BREAKOUT" for row in signals),
            "youtube_rising_count": sum(row["signal"] == "YOUTUBE_RISING" for row in signals),
            "rejected_out_of_window_or_invalid": rejected,
        },
        "production_authority": "SHADOW_ONLY",
        "may_create_search_demand": False,
        "may_create_realtime_hot": False,
        "may_create_rising_search": False,
        "may_change_raw_score": False,
        "may_change_eligibility": False,
        "may_waive_veto": False,
    }
    snapshot["snapshot_fingerprint"] = _fingerprint(snapshot)
    return snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--market", action="append", default=[])
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--api-key-env", default="YOUTUBE_DATA_API_KEY")
    parser.add_argument("--keychain-service", default=DEFAULT_KEYCHAIN_SERVICE)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.window_hours <= 0:
        raise YouTubeSignalError("window-hours must be positive")
    if args.input:
        rows = _normalise_rows(_load_json(args.input))
        source_type = "normalised_export"
    else:
        api_key, _credential_source = resolve_api_key(
            args.api_key_env, args.keychain_service
        )
        if not api_key:
            raise YouTubeSignalError(
                "YouTube API credential is unavailable in the configured environment or macOS Keychain"
            )
        if not args.query or not args.market:
            raise YouTubeSignalError("official API mode requires --query and --market")
        rows = fetch_official_rows(
            args.query,
            [market.upper() for market in args.market],
            api_key,
            dt.datetime.now(tz=UTC),
            args.window_hours,
        )
        source_type = "youtube_data_api_v3"
    snapshot = build_snapshot(
        args.run_id,
        rows,
        window_hours=args.window_hours,
        source_type=source_type,
    )
    _write_json(args.output, snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

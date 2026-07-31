import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_google_trends_realtime.py"
SPEC = importlib.util.spec_from_file_location("vertu_google_trends_realtime", MODULE_PATH)
trends = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(trends)


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item>
      <title>Example launch</title>
      <ht:approx_traffic>20K+</ht:approx_traffic>
      <pubDate>Wed, 22 Jul 2026 01:00:00 +0000</pubDate>
      <ht:news_item>
        <ht:news_item_title>Official example launch</ht:news_item_title>
        <ht:news_item_url>https://example.com/launch</ht:news_item_url>
        <ht:news_item_source>Example</ht:news_item_source>
      </ht:news_item>
    </item>
  </channel>
</rss>
"""


class ParseTrafficTests(unittest.TestCase):
    def test_parses_google_traffic_buckets(self):
        self.assertEqual(trends.parse_approx_traffic("500+"), 500)
        self.assertEqual(trends.parse_approx_traffic("20K+"), 20_000)
        self.assertEqual(trends.parse_approx_traffic("1.5M+"), 1_500_000)
        self.assertIsNone(trends.parse_approx_traffic(""))


class FeedTests(unittest.TestCase):
    def test_feed_produces_auditable_realtime_item(self):
        observed = datetime(2026, 7, 22, 3, 0, tzinfo=timezone.utc)
        rows = trends.parse_feed(RSS, "US", observed_at=observed)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["geo"], "US")
        self.assertEqual(rows[0]["approx_traffic"], 20_000)
        self.assertEqual(rows[0]["freshness_bucket"], "LAST_4H")
        self.assertEqual(rows[0]["news_confirmation_count"], 1)
        self.assertTrue(rows[0]["official_google_source"])

    def test_invalid_date_and_empty_news_are_not_treated_as_realtime_evidence(self):
        observed = datetime(2026, 7, 22, 3, 0, tzinfo=timezone.utc)
        invalid_date = RSS.replace(
            "Wed, 22 Jul 2026 01:00:00 +0000",
            "not-a-date",
        )
        self.assertEqual(trends.parse_feed(invalid_date, "US", observed_at=observed), [])

        empty_news = RSS.replace(
            "<ht:news_item_title>Official example launch</ht:news_item_title>",
            "<ht:news_item_title></ht:news_item_title>",
        )
        rows = trends.parse_feed(empty_news, "US", observed_at=observed)
        self.assertEqual(rows[0]["news_confirmation_count"], 0)

    def test_snapshot_preserves_market_failure_and_success(self):
        observed = datetime(2026, 7, 22, 3, 0, tzinfo=timezone.utc)

        def fetcher(url, _timeout):
            if "geo=GB" in url:
                raise TimeoutError("simulated timeout")
            return RSS

        snapshot = trends.build_snapshot(
            ["US", "GB"],
            run_id="run-test",
            observed_at=observed,
            fetcher=fetcher,
        )

        self.assertEqual(snapshot["status"], "PARTIAL")
        self.assertEqual(snapshot["topics"][0]["markets"], ["US"])
        self.assertTrue(snapshot["topics"][0]["realtime_candidate"])
        self.assertEqual(snapshot["markets"][1]["status"], "SOURCE_UNAVAILABLE")

    def test_builds_market_map_and_hotness_gate_artifacts(self):
        observed = datetime(2026, 7, 22, 3, 0, tzinfo=timezone.utc)
        snapshot = trends.build_snapshot(
            ["US"],
            run_id="run-test",
            observed_at=observed,
            fetcher=lambda _url, _timeout: RSS,
        )

        market_map = trends.build_market_map(snapshot)
        hotness_gate = trends.build_hotness_gate(snapshot)

        self.assertEqual(market_map["markets"][0]["geo"], "US")
        self.assertEqual(market_map["run_id"], "run-test")
        self.assertEqual(
            market_map["snapshot_fingerprint"], snapshot["snapshot_fingerprint"]
        )
        self.assertEqual(hotness_gate["realtime_candidate_count"], 1)
        self.assertEqual(hotness_gate["topics"][0]["trend_query"], "Example launch")


if __name__ == "__main__":
    unittest.main()

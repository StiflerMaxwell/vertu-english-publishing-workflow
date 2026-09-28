import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_youtube_topic_signals.py"
SPEC = importlib.util.spec_from_file_location("vertu_youtube_topic_signals", MODULE_PATH)
signals = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(signals)


NOW = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)


def video(index, views=20_000, hours=10, channel=None):
    published = datetime(2026, 8, 27, 14, 0, tzinfo=timezone.utc)
    return {
        "query": "private AI phone",
        "market": "US",
        "video_id": f"v{index}",
        "channel_id": channel or f"c{index}",
        "published_at": published.isoformat().replace("+00:00", "Z"),
        "views": views,
        "likes": views * 0.03,
        "comments": views * 0.002,
        "source_url": f"https://www.youtube.com/watch?v=v{index}",
    }


class YouTubeTopicSignalTests(unittest.TestCase):
    def test_environment_credential_wins(self):
        with mock.patch.dict("os.environ", {"YOUTUBE_DATA_API_KEY": "fake-secret"}):
            value, source = signals.resolve_api_key("YOUTUBE_DATA_API_KEY")

        self.assertEqual(value, "fake-secret")
        self.assertEqual(source, "environment")

    @mock.patch.object(signals.subprocess, "run")
    def test_keychain_fallback_is_supported_without_secret_in_arguments(self, run):
        run.return_value = mock.Mock(returncode=0, stdout="fake-keychain-secret\n")

        with mock.patch.dict("os.environ", {}, clear=True):
            value, source = signals.resolve_api_key(
                "YOUTUBE_DATA_API_KEY", "vertu-youtube-data-api"
            )

        self.assertEqual(value, "fake-keychain-secret")
        self.assertEqual(source, "macos_keychain")
        self.assertNotIn("fake-keychain-secret", str(run.call_args))

    @mock.patch.object(signals.urllib.request, "urlopen")
    def test_official_request_uses_header_not_url_for_key(self, urlopen):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"items":[]}'
        urlopen.return_value = response

        result = signals._official_get(
            "search", {"part": "snippet", "q": "privacy phone"}, "fake-secret"
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(result, {"items": []})
        self.assertNotIn("fake-secret", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "fake-secret")

    def test_breakout_is_shadow_only(self):
        snapshot = signals.build_snapshot(
            "run-1", [video(index) for index in range(5)], now=NOW
        )

        self.assertEqual(snapshot["signals"][0]["signal"], "YOUTUBE_BREAKOUT")
        self.assertEqual(snapshot["production_authority"], "SHADOW_ONLY")
        self.assertFalse(snapshot["may_create_search_demand"])
        self.assertFalse(snapshot["may_create_realtime_hot"])
        self.assertFalse(snapshot["may_change_raw_score"])
        self.assertEqual(snapshot["snapshot_fingerprint"], signals._fingerprint(snapshot))

    def test_channel_breadth_prevents_single_channel_breakout(self):
        snapshot = signals.build_snapshot(
            "run-2", [video(index, channel="same") for index in range(6)], now=NOW
        )

        self.assertEqual(snapshot["signals"][0]["signal"], "NONE")
        self.assertEqual(snapshot["signals"][0]["independent_channel_count"], 1)

    def test_out_of_window_is_rejected_not_zero_filled(self):
        row = video(1)
        row["published_at"] = "2026-08-20T00:00:00Z"
        snapshot = signals.build_snapshot("run-3", [row], now=NOW)

        self.assertEqual(snapshot["status"], "SOURCE_UNAVAILABLE")
        self.assertEqual(snapshot["signals"], [])
        self.assertEqual(snapshot["summary"]["rejected_out_of_window_or_invalid"], 1)

    def test_rising_requires_multiple_independent_channels(self):
        rows = [video(index, views=2_000) for index in range(3)]
        snapshot = signals.build_snapshot("run-4", rows, now=NOW)

        self.assertEqual(snapshot["signals"][0]["signal"], "YOUTUBE_RISING")


if __name__ == "__main__":
    unittest.main()

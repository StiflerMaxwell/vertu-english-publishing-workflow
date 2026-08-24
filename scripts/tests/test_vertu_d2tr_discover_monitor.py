import importlib.util
import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_d2tr_discover_monitor.py"
SPEC = importlib.util.spec_from_file_location("vertu_d2tr_discover_monitor", MODULE_PATH)
monitor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(monitor)


NOW = datetime(2026, 8, 6, 0, 0, tzinfo=timezone.utc)


def payload_for(endpoint):
    base = {"country": "us", "generated_at": "2026-08-06T00:00:00Z"}
    if endpoint == "volatility":
        base.update(
            {
                "summary": {
                    "current_index": 7.4,
                    "mean_index": 3.2,
                    "trend": "rising",
                    "current_state": "active",
                },
                "series": [
                    {
                        "date": "2026-08-05",
                        "volatility_index": 7.4,
                        "confidence": "high",
                        "metrics": {
                            "total_impressions": 10000,
                            "total_articles": 100,
                            "unique_domains": 20,
                        },
                    }
                ],
            }
        )
    elif endpoint in {"category-volatility", "topic-volatility"}:
        name = "Service" if endpoint == "category-volatility" else "Travel"
        base["categories"] = [
            {
                "category": name,
                "summary": {
                    "current_index": 6.2,
                    "mean_index": 3.1,
                    "trend": "rising",
                    "current_state": "active",
                },
                "series": [
                    {
                        "date": "2026-08-05",
                        "volatility_index": 6.2,
                        "confidence": "high",
                    }
                ],
            }
        ]
    elif endpoint == "format-interest":
        base["formats"] = [
            {
                "format_type": "T03_listicle",
                "summary": {
                    "current_index": 12.4,
                    "mean_index": 10.0,
                    "shift_vs_mean": 2.4,
                    "trend": "rising",
                },
                "series": [
                    {
                        "date": "2026-08-05",
                        "interest_index": 12.4,
                        "impressions": 5000,
                        "articles": 50,
                    }
                ],
            }
        ]
    else:
        base["categories"] = [
            {
                "category": "/Travel/Air Travel",
                "impressions": 20000,
                "delta_pct": 22.0,
                "publications": 80,
                "publishers": 15,
            }
        ]
    return base


def fake_transport(url):
    endpoint = url.split("/discover/", 1)[1].split("?", 1)[0]
    return 200, payload_for(endpoint), {}


class D2TRMonitorTests(unittest.TestCase):
    def test_collects_five_endpoints_without_claiming_google_demand(self):
        snapshot = monitor.collect_snapshot(
            "d2tr-test", markets=["US"], now=NOW, transport=fake_transport
        )

        self.assertEqual(snapshot["status"], "AVAILABLE")
        self.assertEqual(snapshot["summary"]["request_count"], 5)
        self.assertFalse(snapshot["official_google_source"])
        self.assertFalse(snapshot["may_create_google_demand"])
        self.assertFalse(snapshot["may_create_realtime_hot"])
        self.assertEqual(snapshot["retention_days"], 30)
        self.assertEqual(
            snapshot["snapshot_fingerprint"], monitor._fingerprint(snapshot)
        )

    def test_null_volatility_is_insufficient_baseline_not_zero(self):
        payload = payload_for("volatility")
        payload["summary"]["current_index"] = None
        payload["series"][-1]["note"] = "insufficient_baseline"

        normalised = monitor.normalise_response("volatility", payload)

        self.assertEqual(normalised["status"], "INSUFFICIENT_BASELINE")
        self.assertIsNone(normalised["signals"][0]["current_value"])

    def test_transient_get_failure_is_retried_with_bounded_attempts(self):
        calls = {}

        def flaky_transport(url):
            endpoint = url.split("/discover/", 1)[1].split("?", 1)[0]
            calls[endpoint] = calls.get(endpoint, 0) + 1
            if endpoint == "categories" and calls[endpoint] == 1:
                raise TimeoutError("temporary timeout")
            return 200, payload_for(endpoint), {}

        snapshot = monitor.collect_snapshot(
            "d2tr-test", markets=["US"], now=NOW, transport=flaky_transport
        )
        category_request = next(
            row for row in snapshot["requests"] if row["endpoint"] == "categories"
        )

        self.assertEqual(category_request["source_status"], "AVAILABLE")
        self.assertEqual(category_request["retry_count"], 1)
        self.assertEqual(calls["categories"], 2)

    def test_all_http_success_with_thin_baselines_is_source_available(self):
        def thin_transport(url):
            endpoint = url.split("/discover/", 1)[1].split("?", 1)[0]
            payload = {"country": "us", "generated_at": "2026-08-06T00:00:00Z"}
            if endpoint == "volatility":
                payload.update(
                    {
                        "summary": {"current_index": None},
                        "series": [{"note": "insufficient_baseline"}],
                    }
                )
            return 200, payload, {}

        snapshot = monitor.collect_snapshot(
            "d2tr-test", markets=["US"], now=NOW, transport=thin_transport
        )

        self.assertEqual(snapshot["status"], "AVAILABLE")
        self.assertEqual(snapshot["summary"]["insufficient_baseline_count"], 5)
        self.assertEqual(snapshot["summary"]["source_blocked_count"], 0)

    def test_context_preserves_exact_topic_format_and_category_names(self):
        snapshot = monitor.collect_snapshot(
            "d2tr-test", markets=["US"], now=NOW, transport=fake_transport
        )
        context = monitor.build_context(snapshot)

        market = context["markets"]["US"]
        self.assertIn("Travel", market["topics"])
        self.assertIn("Service", market["format_groups"])
        self.assertIn("T03_listicle", market["formats"])
        self.assertIn("/Travel/Air Travel", market["categories"])
        self.assertFalse(context["may_create_google_demand"])
        self.assertEqual(
            context["snapshot_fingerprint"], monitor._fingerprint(context)
        )

    def test_activate_context_writes_validated_mutable_pointer(self):
        snapshot = monitor.collect_snapshot(
            "d2tr-test", markets=["US"], now=NOW, transport=fake_transport
        )
        context = monitor.build_context(snapshot)
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "context.json"
            target = pathlib.Path(directory) / "latest.json"
            monitor._write_json(source, context)

            result = monitor.main(
                ["activate-context", "--context", str(source), "--output", str(target)]
            )

            self.assertEqual(result, 0)
            self.assertEqual(monitor._load_json(target), context)

    def test_base_rows_write_one_summary_per_market_endpoint(self):
        snapshot = monitor.collect_snapshot(
            "d2tr-test", markets=["US"], now=NOW, transport=fake_transport
        )
        rows = monitor.base_rows(snapshot, pathlib.Path("snapshot.json"))

        self.assertEqual(len(rows), 5)
        self.assertEqual(len({row["快照ID"] for row in rows}), 5)
        self.assertTrue(all(row["执行ID"] == "d2tr-test" for row in rows))
        self.assertTrue(all(row["过期时间"] == "2026-09-05 08:00:00" for row in rows))

    def test_local_retention_removes_only_expired_date_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            expired = root / "2026-07-01"
            current = root / "2026-08-01"
            unrelated = root / "learning"
            for path in (expired, current, unrelated):
                path.mkdir()

            removed = monitor.prune_local(root, NOW - timedelta(days=30))

            self.assertEqual(removed, [str(expired)])
            self.assertFalse(expired.exists())
            self.assertTrue(current.exists())
            self.assertTrue(unrelated.exists())

    def test_local_retention_uses_exact_timestamp_on_boundary_day(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            boundary = root / "2026-07-07"
            old_run = boundary / "old"
            fresh_run = boundary / "fresh"
            old_run.mkdir(parents=True)
            fresh_run.mkdir(parents=True)
            monitor._write_json(
                old_run / "d2tr-snapshot.json",
                {"observed_at": "2026-07-07T08:00:00Z"},
            )
            monitor._write_json(
                fresh_run / "d2tr-snapshot.json",
                {"observed_at": "2026-07-07T10:00:00Z"},
            )

            removed = monitor.prune_local(root, datetime(2026, 7, 7, 9, 0, tzinfo=timezone.utc))

            self.assertEqual(removed, [str(old_run)])
            self.assertFalse(old_run.exists())
            self.assertTrue(fresh_run.exists())


class FakeLarkClient:
    def __init__(self):
        self.rows = []
        self.created = []

    def list_by_execution(self, table_id, execution_id):
        return [
            row for row in self.rows if row["fields"].get("执行ID") == execution_id
        ]

    def batch_create(self, table_id, rows):
        ids = []
        for fields in rows:
            record_id = f"rec-{len(self.rows) + 1}"
            self.rows.append({"record_id": record_id, "fields": dict(fields)})
            ids.append(record_id)
        self.created.extend(ids)
        return ids


class BaseHandoffTests(unittest.TestCase):
    def test_handoff_is_idempotent_by_execution_and_snapshot_key(self):
        snapshot = monitor.collect_snapshot(
            "d2tr-test", markets=["US"], now=NOW, transport=fake_transport
        )
        client = FakeLarkClient()

        first = monitor.handoff_rows(
            client, "table", snapshot, pathlib.Path("snapshot.json")
        )
        second = monitor.handoff_rows(
            client, "table", snapshot, pathlib.Path("snapshot.json")
        )

        self.assertEqual(first["created_count"], 5)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(len(client.rows), 5)

    def test_base_retention_compares_expiry_to_now_not_observation_cutoff(self):
        class ExpiryClient(monitor.LarkClient):
            def __init__(self):
                pass

            def _filtered_rows(self, table_id, filter_json, fields):
                operator = filter_json["conditions"][0][1]
                if operator == "<":
                    return [
                        {
                            "record_id": "rec-old-day",
                            "fields": {"过期时间": "2026-08-05 23:00:00"},
                        }
                    ]
                return [
                    {
                        "record_id": "rec-old-hour",
                        "fields": {"过期时间": "2026-08-06 16:00:00"},
                    },
                    {
                        "record_id": "rec-future-hour",
                        "fields": {"过期时间": "2026-08-06 18:00:00"},
                    },
                ]

        expired = ExpiryClient().list_expired(
            "table", datetime(2026, 8, 6, 9, 0, tzinfo=timezone.utc)
        )

        self.assertEqual(expired, ["rec-old-day", "rec-old-hour"])


if __name__ == "__main__":
    unittest.main()

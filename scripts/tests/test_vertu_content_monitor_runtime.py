import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_content_monitor_runtime.py"
SPEC = importlib.util.spec_from_file_location("vertu_content_monitor_runtime", MODULE_PATH)
monitor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_run(root, date, name, published_at, slug="article-one", complete=True):
    run = root / date / name
    write_json(
        run / "handoff.json",
        {
            "state": "PUBLISHED",
            "run_id": f"run-{date}-{name}",
            "published_at": published_at,
            "articles": [
                {
                    "slug": slug,
                    "canonical_url": f"https://vertu.com/guides/{slug}",
                    "document_id": f"doc-{slug}",
                    "source_rev": "rev-1",
                }
            ],
        },
    )
    if complete:
        write_json(
            run / "publish-result.json",
            {
                "run_id": f"run-{date}-{name}",
                "published_at": published_at,
                "articles": [
                    {
                        "slug": slug,
                        "section": "guides",
                        "title": "Article One",
                        "publishedAt": published_at,
                        "_id": f"doc-{slug}",
                        "_rev": "rev-1",
                    }
                ],
            },
        )
        write_json(
            run / "live-verification.json",
            {
                "results": [
                    {
                        "url": f"https://vertu.com/guides/{slug}",
                        "status": 200,
                        "canonical_pass": True,
                        "og_image_pass": True,
                        "visible_author_pass": True,
                        "blogposting_author_pass": True,
                        "max_image_preview_large_pass": True,
                        "non_news_pass": True,
                        "rendered_link_reconciliation_pass": True,
                    }
                ]
            },
        )
        write_json(run / "performance-plan.json", {"status": "SCHEDULED"})
        write_json(
            run / "candidate-scores.json",
            {
                "selected": [
                    {
                        "publication_run_id": f"run-{date}-{name}",
                        "candidate_id": "C01",
                        "slug": slug,
                        "section": "guides",
                        "audience_fit_lane": "premium_cabin_decisions",
                        "intent_key": "upgrade-decision",
                        "outcome_lane": "search-first",
                        "trend_class": "EVERGREEN_SEARCH",
                        "portfolio_bucket": "proven_demand",
                    }
                ]
            },
        )
    return run


class MonitorRuntimeTests(unittest.TestCase):
    def test_mandatory_source_failure_keeps_checkpoint_retryable(self):
        gsc = {
            "status": "DATA_NOT_MATURE",
            "discover": {"clicks": None, "impressions": None, "ctr": None},
            "search": {"clicks": None, "impressions": None, "ctr": None},
        }
        ga4 = {"status": "SOURCE_BLOCKED", "metrics": {}}

        diagnosis = monitor.diagnosis_for("72h", "SOURCE_BLOCKED", gsc, ga4)

        self.assertEqual(diagnosis["classification"], "SOURCE_BLOCKED")

    def test_stale_handoff_is_reconciled_only_with_exact_publish_live_and_summary_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            run = make_run(root, "2026-08-03", "daily-10", "2026-08-03T03:00:00Z")
            handoff = json.loads((run / "handoff.json").read_text())
            handoff["state"] = "READY_TO_PUBLISH"
            write_json(run / "handoff.json", handoff)
            write_json(run / "run-summary.json", {"run_id": "run-current", "status": "SUCCESS"})

            inventory = monitor.discover_articles(
                root, dt.datetime(2026, 8, 4, tzinfo=dt.timezone.utc)
            )

            self.assertEqual(len(inventory["articles"]), 1)
            self.assertEqual(len(inventory["reconciled_publication_runs"]), 1)
            self.assertEqual(
                inventory["reconciled_publication_runs"][0]["status"],
                "PUBLISHED_RECONCILED",
            )

    def test_dynamic_inventory_includes_current_run_and_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            make_run(root, "2026-08-03", "daily-10", "2026-08-03T03:00:00Z")
            now = dt.datetime(2026, 8, 4, 4, tzinfo=dt.timezone.utc)

            inventory = monitor.discover_articles(root, now)
            plan = monitor.build_due_plan(inventory, now)

            self.assertEqual(len(inventory["articles"]), 1)
            article = inventory["articles"][0]
            self.assertEqual(article["cluster_id"], "premium_cabin_decisions")
            self.assertEqual(article["intent_key"], "upgrade-decision")
            self.assertEqual(plan["due_count"], 1)
            self.assertEqual(plan["due"][0]["checkpoint"], "24h")

    def test_legacy_incomplete_run_is_isolated_not_globally_blocking(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            make_run(root, "2026-07-10", "first-batch", "2026-07-10T03:00:00Z", complete=False)
            make_run(root, "2026-08-03", "daily-10", "2026-08-03T03:00:00Z")
            now = dt.datetime(2026, 8, 4, 4, tzinfo=dt.timezone.utc)

            inventory = monitor.discover_articles(root, now, window_days=40)

            self.assertEqual(len(inventory["legacy_exceptions"]), 1)
            self.assertEqual(inventory["legacy_exceptions"][0]["status"], "LEGACY_EVIDENCE_EXCEPTION")
            self.assertEqual(len(inventory["blocked_runs"]), 0)
            self.assertEqual(len(inventory["articles"]), 1)

    def test_legacy_run_json_published_marker_is_audited_when_handoff_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            run = root / "2026-07-11" / "daily-10"
            write_json(run / "run.json", {"state": "PUBLISHED"})

            inventory = monitor.discover_articles(
                root,
                dt.datetime(2026, 8, 3, tzinfo=dt.timezone.utc),
                window_days=40,
            )

            self.assertEqual(len(inventory["legacy_exceptions"]), 1)
            self.assertTrue(inventory["legacy_exceptions"][0]["legacy_publication_marker"])

    def test_early_published_urls_shape_requires_exact_live_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            run = root / "2026-07-12" / "daily-new-10-v1"
            published_at = "2026-07-12T14:06:33Z"
            url = "https://vertu.com/guides/legacy-verified-article"
            write_json(
                run / "handoff.json",
                {"state": "PUBLISHED", "run_id": "legacy-run", "published_at": published_at},
            )
            write_json(
                run / "publish-result.json",
                {"run_id": "legacy-run", "published_at": published_at, "urls": [url]},
            )
            write_json(
                run / "live-verification.json",
                {
                    "results": [
                        {
                            "url": url,
                            "status": 200,
                            "canonical_pass": True,
                            "non_news_pass": True,
                        }
                    ]
                },
            )
            write_json(run / "performance-plan.json", {"status": "SCHEDULED"})

            inventory = monitor.discover_articles(
                root,
                dt.datetime(2026, 8, 4, tzinfo=dt.timezone.utc),
                window_days=40,
            )

            self.assertEqual(len(inventory["articles"]), 1)
            self.assertEqual(inventory["articles"][0]["article_key"], "legacy-verified-article")
            self.assertEqual(inventory["blocked_runs"], [])

    def test_completed_checkpoint_is_not_scheduled_again(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            run = make_run(root, "2026-08-01", "daily-10", "2026-08-01T03:00:00Z")
            write_json(
                run / "performance" / "article-one" / "24h.json",
                {
                    "article_key": "article-one",
                    "checkpoint": "24h",
                    "checkpoint_status": "COMPLETED",
                    "executed_at_utc": "2026-08-02T04:00:00Z",
                    "data_maturity": "PRELIMINARY",
                },
            )
            now = dt.datetime(2026, 8, 2, 5, tzinfo=dt.timezone.utc)

            plan = monitor.build_due_plan(monitor.discover_articles(root, now), now)

            self.assertEqual(plan["due_count"], 0)

    def test_news_is_never_discovered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            run = make_run(root, "2026-08-03", "daily-10", "2026-08-03T03:00:00Z")
            handoff = json.loads((run / "handoff.json").read_text())
            handoff["articles"][0]["canonical_url"] = "https://vertu.com/news/article-one"
            write_json(run / "handoff.json", handoff)
            publish = json.loads((run / "publish-result.json").read_text())
            publish["articles"][0]["section"] = "news"
            write_json(run / "publish-result.json", publish)
            live = json.loads((run / "live-verification.json").read_text())
            live["results"][0]["url"] = "https://vertu.com/news/article-one"
            write_json(run / "live-verification.json", live)

            inventory = monitor.discover_articles(
                root, dt.datetime(2026, 8, 4, tzinfo=dt.timezone.utc)
            )

            self.assertEqual(inventory["articles"], [])


if __name__ == "__main__":
    unittest.main()

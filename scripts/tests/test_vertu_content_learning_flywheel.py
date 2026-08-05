import importlib.util
import json
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_content_learning_flywheel.py"
SPEC = importlib.util.spec_from_file_location("vertu_content_learning_flywheel", MODULE_PATH)
learning = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(learning)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def checkpoint(slug, checkpoint_name="28d", classification="WINNER", executed=True):
    return {
        "article_key": slug,
        "checkpoint": checkpoint_name,
        "checkpoint_status": "COMPLETED" if executed else None,
        "executed_at_utc": "2026-07-24T10:00:00Z" if executed else None,
        "data_maturity": "MATURE" if executed else None,
        "gsc": {
            "status": "MATURE" if executed else None,
            "search": {"impressions": 500, "clicks": 20, "ctr": 0.04},
            "discover": {"impressions": 1000, "clicks": 50, "ctr": 0.05},
        },
        "ga4": {
            "status": "AVAILABLE_EXACT_WINDOW" if executed else None,
        },
        "diagnosis": {"classification": classification},
    }


class LearningFlywheelTests(unittest.TestCase):
    def test_current_production_artifacts_supply_complete_learning_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            run = root / "2026-08-03" / "daily-10"
            slug = "production-shape-article"
            write_json(
                run / "performance" / slug / "72h-result.json",
                checkpoint(
                    slug,
                    checkpoint_name="72h",
                    classification="SEARCH_CTR_OPPORTUNITY",
                ),
            )
            write_json(
                run / "cluster-support.json",
                {
                    "publication_run_id": "run-production",
                    "candidates": [
                        {"candidate_id": "C01", "cluster": "premium_cabin_decisions"}
                    ],
                },
            )
            write_json(
                run / "candidate-scores.json",
                {
                    "selected": [
                        {
                            "publication_run_id": "run-production",
                            "candidate_id": "C01",
                            "slug": slug,
                            "section": "guides",
                            "outcome_lane": "search-first",
                            "portfolio_bucket": "proven_demand",
                            "trend_class": "EVERGREEN_SEARCH",
                            "intent_key": "premium-cabin-upgrade-decision",
                        }
                    ]
                },
            )
            write_json(
                run / "run-summary.json",
                {
                    "run_id": "run-production",
                    "status": "SUCCESS",
                    "articles": [
                        {
                            "candidate_id": "C01",
                            "slug": slug,
                            "section": "guides",
                            "trend_class": "EVERGREEN_SEARCH",
                            "live_verdict": "PASS",
                        }
                    ],
                },
            )

            snapshot, _ = learning.build_snapshot(root, "production-shape-test")
            row = snapshot["checkpoints"][0]

            self.assertEqual(row["publication_run_id"], "run-production")
            self.assertEqual(row["cluster_id"], "premium_cabin_decisions")
            self.assertEqual(row["intent_key"], "premium-cabin-upgrade-decision")
            self.assertEqual(row["learning_context_status"], "COMPLETE")
            self.assertEqual(row["raw_classification"], "SEARCH_CTR_OPPORTUNITY")
            self.assertEqual(row["learning_direction"], -1)
            self.assertEqual(snapshot["learning_context_completeness"]["complete"], 1)

    def test_partial_context_cannot_create_broad_section_prior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for index, run_id in enumerate(("run-a", "run-a", "run-b"), start=1):
                slug = f"partial-{index}"
                write_json(
                    root / run_id / "performance" / slug / "28d-result.json",
                    checkpoint(slug),
                )
                write_json(
                    root / run_id / "run-summary.json",
                    {
                        "run_id": run_id,
                        "articles": [{"slug": slug, "section": "guides"}],
                    },
                )

            _, active = learning.build_snapshot(root, "partial-context-test")

            self.assertEqual(active["priors"], [])

    def test_placeholder_and_immature_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_json(
                root / "run" / "performance" / "placeholder" / "28d.json",
                checkpoint("placeholder", executed=False),
            )
            immature = checkpoint("immature")
            immature["checkpoint_status"] = "DATA_NOT_MATURE"
            immature["data_maturity"] = "DATA_NOT_MATURE"
            write_json(
                root / "run" / "performance" / "immature" / "28d.json",
                immature,
            )

            snapshot, active = learning.build_snapshot(root, "weekly-test")

            self.assertEqual(snapshot["accepted_checkpoint_count"], 0)
            self.assertEqual(snapshot["status"], "NO_DURABLE_LESSON")
            self.assertEqual(active["priors"], [])
            self.assertEqual(snapshot["rejected_by_reason"]["PLANNED_PLACEHOLDER"], 1)
            self.assertEqual(snapshot["rejected_by_reason"]["DATA_NOT_MATURE"], 1)

    def test_source_blocked_ga4_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            blocked = checkpoint("source-blocked", checkpoint_name="72h")
            blocked["ga4"]["status"] = "SOURCE_BLOCKED"
            write_json(
                root / "run" / "performance" / "source-blocked" / "72h.json",
                blocked,
            )

            snapshot, active = learning.build_snapshot(root, "weekly-test")

            self.assertEqual(snapshot["accepted_checkpoint_count"], 0)
            self.assertEqual(snapshot["status"], "NO_DURABLE_LESSON")
            self.assertEqual(active["priors"], [])
            self.assertEqual(snapshot["rejected_by_reason"]["SOURCE_BLOCKED"], 1)

    def test_latest_blocked_retry_supersedes_older_mature_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            older = checkpoint("retry-order", checkpoint_name="72h")
            older["executed_at_utc"] = "2026-07-24T09:00:00Z"
            newer = checkpoint("retry-order", checkpoint_name="72h")
            newer["executed_at_utc"] = "2026-07-24T10:00:00Z"
            newer["ga4"]["status"] = "SOURCE_BLOCKED"
            write_json(
                root / "run" / "performance" / "retry-order" / "72h.json",
                older,
            )
            write_json(
                root
                / "run"
                / "performance"
                / "retry-order"
                / "metrics-supplement-72h.json",
                newer,
            )

            snapshot, active = learning.build_snapshot(root, "weekly-test")

            self.assertEqual(snapshot["accepted_checkpoint_count"], 0)
            self.assertEqual(active["priors"], [])
            self.assertEqual(snapshot["rejected_by_reason"]["SOURCE_BLOCKED"], 1)
            self.assertEqual(snapshot["rejected_by_reason"]["SUPERSEDED_RETRY"], 1)

    def test_three_d28_articles_across_two_runs_promote_bounded_prior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            reports = {"run-a": [], "run-b": []}
            for index, run_id in enumerate(("run-a", "run-a", "run-b"), start=1):
                slug = f"article-{index}"
                write_json(
                    root / run_id / "performance" / slug / "28d-result.json",
                    checkpoint(slug),
                )
                reports[run_id].append(
                    {
                        "slug": slug,
                        "cluster_id": "travel-decision",
                        "section": "guides",
                        "trend_class": "EVERGREEN_SEARCH",
                    }
                )
            for run_id, articles in reports.items():
                write_json(
                    root / run_id / "completion-report.json",
                    {
                        "publication_run_id": run_id,
                        "articles": articles,
                    },
                )

            snapshot, active = learning.build_snapshot(root, "weekly-test")
            cluster_prior = next(
                row
                for row in active["priors"]
                if row["scope_type"] == "cluster_id"
                and row["scope_value"] == "travel-decision"
            )

            self.assertEqual(snapshot["status"], "ACTIVE_PRIORS_READY")
            self.assertEqual(cluster_prior["learning_level"], "DURABLE_PRIOR")
            self.assertLessEqual(abs(cluster_prior["selection_adjustment"]), 3)
            self.assertEqual(cluster_prior["evidence"]["d28_article_count"], 3)
            self.assertEqual(cluster_prior["evidence"]["publication_run_count"], 2)

    def test_repeated_recent_72h_evidence_creates_expiring_provisional_prior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            reports = {"run-a": [], "run-b": []}
            for index, run_id in enumerate(("run-a", "run-a", "run-b"), start=1):
                slug = f"article-{index}"
                row = checkpoint(slug, checkpoint_name="72h")
                row["executed_at_utc"] = "2026-07-29T00:00:00Z"
                write_json(
                    root / run_id / "performance" / slug / "72h-result.json",
                    row,
                )
                reports[run_id].append(
                    {
                        "slug": slug,
                        "cluster_id": "premium-travel-decision",
                        "section": "guides",
                    }
                )
            for run_id, articles in reports.items():
                write_json(
                    root / run_id / "completion-report.json",
                    {
                        "publication_run_id": run_id,
                        "articles": articles,
                    },
                )

            snapshot, _ = learning.build_snapshot(root, "48h-test")
            provisional = learning.build_provisional_artifact(snapshot)
            cluster_prior = next(
                row
                for row in provisional["priors"]
                if row["scope_type"] == "cluster_id"
                and row["scope_value"] == "premium-travel-decision"
            )

            self.assertEqual(provisional["status"], "ACTIVE")
            self.assertEqual(cluster_prior["learning_level"], "CANDIDATE_PRIOR")
            self.assertEqual(cluster_prior["selection_adjustment"], 1)
            self.assertEqual(cluster_prior["evidence"]["source_checkpoint"], "72h")
            self.assertEqual(cluster_prior["evidence"]["article_count"], 3)
            self.assertEqual(cluster_prior["evidence"]["publication_run_count"], 2)
            self.assertGreater(
                learning.iso_datetime(cluster_prior["expires_at"]),
                learning.iso_datetime(cluster_prior["activated_at"]),
            )

    def test_two_recent_7d_articles_across_two_runs_create_provisional_prior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for index, run_id in enumerate(("run-a", "run-b"), start=1):
                slug = f"article-{index}"
                row = checkpoint(slug, checkpoint_name="7d")
                row["executed_at_utc"] = "2026-07-29T00:00:00Z"
                write_json(
                    root / run_id / "performance" / slug / "7d-result.json",
                    row,
                )
                write_json(
                    root / run_id / "completion-report.json",
                    {
                        "publication_run_id": run_id,
                        "articles": [
                            {
                                "slug": slug,
                                "cluster_id": "executive-technology",
                            }
                        ],
                    },
                )

            snapshot, _ = learning.build_snapshot(root, "48h-test")
            provisional = learning.build_provisional_artifact(snapshot)
            cluster_prior = next(
                row
                for row in provisional["priors"]
                if row["scope_type"] == "cluster_id"
                and row["scope_value"] == "executive-technology"
            )

            self.assertEqual(cluster_prior["evidence"]["source_checkpoint"], "7d")
            self.assertEqual(cluster_prior["evidence"]["article_count"], 2)
            self.assertLessEqual(abs(cluster_prior["selection_adjustment"]), 2)

    def test_empty_week_preserves_previous_valid_active_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            previous = {
                "contract_version": "performance-learning-v1",
                "generated_at": "2026-07-17T13:30:00Z",
                "source_execution_id": "previous-week",
                "source_snapshot_fingerprint": "previous-source",
                "status": "ACTIVE",
                "priors": [
                    {
                        "prior_id": "prior-existing",
                        "state": "ACTIVE",
                        "learning_level": "DURABLE_PRIOR",
                        "scope_type": "cluster_id",
                        "scope_value": "travel-decision",
                        "selection_adjustment": 2,
                        "evidence": {
                            "d28_article_count": 4,
                            "publication_run_count": 2,
                        },
                    }
                ],
                "hard_boundaries": {
                    "applies_after_eligibility": True,
                    "maximum_absolute_adjustment": 3,
                    "may_change_raw_score": False,
                    "may_bypass_veto": False,
                    "may_create_realtime_hot": False,
                },
            }
            previous["snapshot_fingerprint"] = learning.fingerprint(previous)
            snapshot, proposed = learning.build_snapshot(root, "empty-week")

            snapshot, active = learning.preserve_previous_active(
                snapshot, proposed, previous
            )

            self.assertEqual(
                snapshot["active_pointer_action"], "PRESERVED_PREVIOUS_ACTIVE"
            )
            self.assertEqual(
                snapshot["preserved_active_fingerprint"],
                previous["snapshot_fingerprint"],
            )
            self.assertEqual(active, previous)

    def test_empty_week_preserves_previous_no_durable_lesson_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            previous = {
                "contract_version": "performance-learning-v1",
                "generated_at": "2026-07-26T09:46:37Z",
                "source_execution_id": "previous-no-durable-week",
                "source_snapshot_fingerprint": "previous-source",
                "status": "NO_DURABLE_LESSON",
                "priors": [],
                "hard_boundaries": {
                    "applies_after_eligibility": True,
                    "maximum_absolute_adjustment": 3,
                    "may_change_raw_score": False,
                    "may_bypass_veto": False,
                    "may_create_realtime_hot": False,
                },
            }
            previous["snapshot_fingerprint"] = learning.fingerprint(previous)
            snapshot, proposed = learning.build_snapshot(root, "empty-week")

            snapshot, active = learning.preserve_previous_active(
                snapshot, proposed, previous
            )

            self.assertEqual(
                snapshot["active_pointer_action"], "PRESERVED_PREVIOUS_ACTIVE"
            )
            self.assertEqual(
                snapshot["preserved_active_fingerprint"],
                previous["snapshot_fingerprint"],
            )
            self.assertEqual(active, previous)


if __name__ == "__main__":
    unittest.main()

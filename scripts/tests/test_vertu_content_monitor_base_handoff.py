import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.vertu_content_monitor_base_handoff import (
    BaseHandoffError,
    LarkCliBaseClient,
    apply_manifest,
    build_manifest,
    checkpoint_fields,
    checkpoint_learning_eligible,
    checkpoint_review_id,
    checkpoint_source_complete,
    monitor_run_status,
    _resolve_qa_record,
    validate_audit_receipt,
)


class LarkCliClientTests(unittest.TestCase):
    def test_command_timeout_is_reported_as_source_blocked(self):
        client = LarkCliBaseClient("base")
        with mock.patch(
            "scripts.vertu_content_monitor_base_handoff.subprocess.run",
            side_effect=__import__("subprocess").TimeoutExpired("lark-cli", 45),
        ):
            with self.assertRaisesRegex(
                BaseHandoffError,
                "SOURCE_BLOCKED: lark-cli exceeded the 45-second command timeout",
            ):
                client._run(("base", "+field-list"))


def complete_artifact(retry=False):
    return {
        "deterministic_id": "run-1:article-1:72h",
        "publication_run_id": "run-1",
        "article_key": "article-1",
        "checkpoint": "72h",
        "checkpoint_status": "COMPLETED",
        "executed_at_utc": "2026-08-03T06:00:00Z",
        "due_at": "2026-08-03T05:00:00Z",
        "data_maturity": "MATURE",
        "retry_of": "old.json" if retry else None,
        "publication": {
            "article_key": "article-1",
            "title": "Article One",
            "canonical_url": "https://vertu.com/guides/article-1",
            "section": "guides",
            "published_at_utc": "2026-07-31T05:00:00Z",
            "document_id": "doc-1",
            "source_rev": "rev-1",
            "qa_run_id": "qa-run-1",
            "qa_handoff": {
                "qa_run_id": "qa-run-1",
                "contract_version": "qa-handoff-v1",
                "producer_skill_id": "vertu-english-blog-pipeline",
                "producer_skill_version": "3.10.0",
                "qa_policy_id": "vertu-seo-publish-gate",
                "qa_policy_version": "0.6.0",
                "qa_policy_hash": "b" * 64,
                "evaluation_profile": "official_site_standard",
                "draft_bundle_sha256": "a" * 64,
                "release_gate_role": "postpublish_audit",
                "compatibility_status": "COMPATIBLE",
                "qa_result_fingerprint": "c" * 64,
            },
        },
        "ga4": {
            "status": "AVAILABLE_EXACT_WINDOW",
            "observed_at": "2026-08-03T06:00:00Z",
            "metrics": {
                "page_views": 100,
                "sessions": 60,
                "engaged_sessions": 45,
                "engagement_rate": 0.75,
                "average_engagement_time_seconds": 80,
                "qualified_journeys": None,
            },
        },
        "gsc": {
            "status": "MATURE",
            "latest_metric_date": "2026-08-03",
            "search": {"clicks": 20, "impressions": 500, "ctr": 0.04, "average_position": 8},
            "discover": {"clicks": 10, "impressions": 1000, "ctr": 0.01},
        },
        "diagnosis": {
            "classification": "EARLY_WINNER",
            "confidence": "MEDIUM",
            "reason": "qualified early signal",
            "sample_gate": {"passed": True},
        },
    }


def handoff_manifest():
    return {
        "base_token": "base",
        "tables": {
            "monitor_runs": "runs",
            "articles": "articles",
            "checkpoints": "checkpoints",
            "content_review": "reviews",
            "qa_runs": "qa",
        },
    }


def write_runtime(root, artifacts, execution_id="exec-projection"):
    results = []
    for index, artifact in enumerate(artifacts):
        artifact_path = root / f"checkpoint-{index}.json"
        artifact_path.write_text(json.dumps(artifact))
        results.append({"path": str(artifact_path)})
    runtime_path = root / "runtime.json"
    runtime_path.write_text(
        json.dumps(
            {
                "inventory": {"published_runs_scanned": 1, "articles": [{}]},
                "execution": {
                    "execution_id": execution_id,
                    "executed_at": "2026-08-03T06:00:00Z",
                    "job_count": len(artifacts),
                    "results": results,
                },
            }
        )
    )
    return runtime_path


def seed_exact_qa(client):
    client.tables["qa"] = {
        "qa-1": {
            "QA Run ID": "qa-run-1",
            "Sanity Doc ID": "doc-1",
            "Source Rev": "rev-1",
            "最终决策": ["PASS"],
            "审核时间": "2026-08-03 12:00:00",
            "QA Handoff Contract Version": "qa-handoff-v1",
            "Producer Skill ID": "vertu-english-blog-pipeline",
            "Producer Skill Version": "3.10.0",
            "QA Policy ID": "vertu-seo-publish-gate",
            "QA Policy Version": "0.6.0",
            "QA Policy Hash": "b" * 64,
            "Evaluation Profile": "official_site_standard",
            "Draft Bundle SHA256": "a" * 64,
            "Release Gate Role": "postpublish_audit",
            "Compatibility Status": "COMPATIBLE",
            "QA Result Fingerprint": "c" * 64,
        }
    }


class FakeClient:
    CHECKPOINT_FIELDS = {
        "复盘ID",
        "Article Key",
        "检查节点",
        "执行时间",
        "数据成熟度",
        "源状态",
        "证据有效性",
        "取代复盘ID",
    }

    def __init__(self, checkpoint_fields=None):
        self.tables = {}
        self.next_id = 1
        self.schemas = {
            "checkpoints": set(
                self.CHECKPOINT_FIELDS
                if checkpoint_fields is None
                else checkpoint_fields
            )
        }

    def exact_records(self, table, key_field, key_value, fields):
        return [
            {"record_id": rid, "fields": {k: v for k, v in row.items() if k in fields}}
            for rid, row in self.tables.get(table, {}).items()
            if str(row.get(key_field)) == str(key_value)
        ]

    def upsert(self, table, fields, record_id=None):
        if record_id is None:
            record_id = f"rec-{self.next_id}"
            self.next_id += 1
        self.tables.setdefault(table, {}).setdefault(record_id, {}).update(fields)
        return record_id

    def field_names(self, table):
        return sorted(self.schemas.get(table, set()))


class AmbiguousLifecycleClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.ambiguous_lifecycle_write_seen = False

    def upsert(self, table, fields, record_id=None):
        result = super().upsert(table, fields, record_id=record_id)
        if (
            table == "checkpoints"
            and set(fields) == {"证据有效性", "取代复盘ID"}
            and not self.ambiguous_lifecycle_write_seen
        ):
            self.ambiguous_lifecycle_write_seen = True
            raise RuntimeError("ambiguous response after applied lifecycle patch")
        return result


class BaseHandoffTests(unittest.TestCase):
    def test_monitor_run_status_preserves_data_not_mature(self):
        artifact = complete_artifact()
        artifact["checkpoint_status"] = "DATA_NOT_MATURE"
        artifact["diagnosis"]["classification"] = "DATA_NOT_MATURE"
        self.assertEqual(monitor_run_status([artifact]), "DATA_NOT_MATURE")

    def test_source_complete_gate_and_retry_identity(self):
        artifact = complete_artifact(retry=True)
        self.assertTrue(checkpoint_source_complete(artifact))
        self.assertEqual(
            checkpoint_review_id(artifact),
            "run-1:article-1:72h:retry:20260803T060000Z",
        )
        artifact["ga4"]["status"] = "SOURCE_BLOCKED"
        self.assertFalse(checkpoint_source_complete(artifact))

    def test_24h_is_source_complete_but_not_learning_eligible(self):
        artifact = complete_artifact()
        artifact["checkpoint"] = "24h"
        artifact["deterministic_id"] = "run-1:article-1:24h"
        artifact["data_maturity"] = "PRELIMINARY"
        artifact["gsc"]["status"] = "NOT_DUE_AT_24H"
        self.assertTrue(checkpoint_source_complete(artifact))
        self.assertFalse(checkpoint_learning_eligible(artifact))

    def test_checkpoint_fields_map_raw_outcome_without_auto_approval(self):
        artifact = complete_artifact()
        fields = checkpoint_fields(artifact, Path("evidence.json"), "article-rec")
        self.assertEqual(fields["诊断"], "WINNER_WATCH")
        self.assertEqual(fields["复盘ID"], "run-1:article-1:72h")
        self.assertNotIn("Qualified Journeys", fields)

    def test_audit_receipt_is_required_and_must_be_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            path.write_text(
                json.dumps({"record_id": "rec-a", "execution_id": "exec-1", "status": "运行中"})
            )
            self.assertEqual(validate_audit_receipt(path)["record_id"], "rec-a")
            path.write_text(
                json.dumps({"record_id": "rec-a", "execution_id": "exec-1", "status": "成功"})
            )
            with self.assertRaises(BaseHandoffError):
                validate_audit_receipt(path)

    def test_manifest_excludes_source_blocked_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good_path = root / "good.json"
            bad_path = root / "bad.json"
            good_path.write_text(json.dumps(complete_artifact()))
            bad = complete_artifact()
            bad["deterministic_id"] = "run-1:article-2:24h"
            bad["article_key"] = "article-2"
            bad["checkpoint"] = "24h"
            bad["checkpoint_status"] = "SOURCE_BLOCKED"
            bad["data_maturity"] = "SOURCE_BLOCKED"
            bad_path.write_text(json.dumps(bad))
            runtime = root / "runtime.json"
            runtime.write_text(
                json.dumps(
                    {
                        "execution": {
                            "execution_id": "exec-1",
                            "results": [{"path": str(good_path)}, {"path": str(bad_path)}],
                        }
                    }
                )
            )
            schema = root / "schema.json"
            schema.write_text(
                json.dumps(
                    {
                        "base_token": "base",
                        "tables": {
                            "monitor_runs": {"table_id": "runs"},
                            "articles": {"table_id": "articles"},
                            "checkpoints": {"table_id": "checkpoints"},
                        },
                    }
                )
            )
            manifest = build_manifest(runtime, schema)
            self.assertEqual(manifest["eligible_checkpoint_count"], 1)
            self.assertEqual(manifest["ineligible_checkpoint_count"], 1)
            self.assertEqual(manifest["observation_checkpoint_count"], 2)

    def test_apply_is_idempotent_and_reads_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "checkpoint.json"
            artifact_path.write_text(json.dumps(complete_artifact()))
            runtime_path = root / "runtime.json"
            runtime_path.write_text(
                json.dumps(
                    {
                        "inventory": {"published_runs_scanned": 1, "articles": [{}]},
                        "execution": {
                            "execution_id": "exec-1",
                            "executed_at": "2026-08-03T06:00:00Z",
                            "job_count": 1,
                            "results": [{"path": str(artifact_path)}],
                        },
                    }
                )
            )
            manifest = {
                "base_token": "base",
                "tables": {
                    "monitor_runs": "runs",
                    "articles": "articles",
                    "checkpoints": "checkpoints",
                    "content_review": "reviews",
                    "qa_runs": "qa",
                },
            }
            client = FakeClient()
            client.tables["qa"] = {
                "qa-1": {
                    "QA Run ID": "qa-run-1",
                    "Sanity Doc ID": "doc-1",
                    "Source Rev": "rev-1",
                    "最终决策": ["PASS"],
                    "审核时间": "2026-08-03 12:00:00",
                    "QA Handoff Contract Version": "qa-handoff-v1",
                    "Producer Skill ID": "vertu-english-blog-pipeline",
                    "Producer Skill Version": "3.10.0",
                    "QA Policy ID": "vertu-seo-publish-gate",
                    "QA Policy Version": "0.6.0",
                    "QA Policy Hash": "b" * 64,
                    "Evaluation Profile": "official_site_standard",
                    "Draft Bundle SHA256": "a" * 64,
                    "Release Gate Role": "postpublish_audit",
                    "Compatibility Status": "COMPATIBLE",
                    "QA Result Fingerprint": "c" * 64,
                }
            }
            first = apply_manifest(manifest, runtime_path, client)
            second = apply_manifest(manifest, runtime_path, client)
            self.assertEqual(first["status"], "SUCCESS")
            self.assertEqual(first["checkpoint_count"], 1)
            self.assertEqual(second["checkpoint_count"], 1)
            self.assertEqual(len(client.tables["runs"]), 1)
            self.assertEqual(len(client.tables["articles"]), 1)
            self.assertEqual(len(client.tables["checkpoints"]), 1)
            self.assertEqual(len(client.tables["reviews"]), 1)

    def test_explicit_qa_run_binding_never_selects_newer_pass(self):
        artifact = complete_artifact()
        client = FakeClient()
        current_fields = {
            "Sanity Doc ID": "doc-1",
            "Source Rev": "rev-1",
            "最终决策": ["PASS"],
            "QA Handoff Contract Version": "qa-handoff-v1",
            "Producer Skill ID": "vertu-english-blog-pipeline",
            "Producer Skill Version": "3.10.0",
            "QA Policy ID": "vertu-seo-publish-gate",
            "QA Policy Version": "0.6.0",
            "QA Policy Hash": "b" * 64,
            "Evaluation Profile": "official_site_standard",
            "Draft Bundle SHA256": "a" * 64,
            "Release Gate Role": "postpublish_audit",
            "Compatibility Status": "COMPATIBLE",
            "QA Result Fingerprint": "c" * 64,
        }
        client.tables["qa"] = {
            "qa-1": {"QA Run ID": "qa-run-1", "审核时间": "2026-08-03 12:00:00", **current_fields},
            "qa-2": {"QA Run ID": "qa-run-2", "审核时间": "2026-08-04 12:00:00", **current_fields},
        }
        resolved = _resolve_qa_record(client, "qa", artifact)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["record_id"], "qa-1")

    def test_legacy_multiple_passes_are_not_guessed(self):
        artifact = complete_artifact()
        artifact["publication"].pop("qa_run_id")
        artifact["publication"].pop("qa_handoff")
        client = FakeClient()
        client.tables["qa"] = {
            "qa-1": {"QA Run ID": "qa-run-1", "Sanity Doc ID": "doc-1", "Source Rev": "rev-1", "最终决策": ["PASS"]},
            "qa-2": {"QA Run ID": "qa-run-2", "Sanity Doc ID": "doc-1", "Source Rev": "rev-1", "最终决策": ["PASS"]},
        }
        self.assertIsNone(_resolve_qa_record(client, "qa", artifact))

    def test_missing_exact_revision_qa_marks_handoff_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "checkpoint.json"
            artifact_path.write_text(json.dumps(complete_artifact()))
            runtime_path = root / "runtime.json"
            runtime_path.write_text(
                json.dumps(
                    {
                        "inventory": {"published_runs_scanned": 1, "articles": [{}]},
                        "execution": {
                            "execution_id": "exec-2",
                            "executed_at": "2026-08-03T06:00:00Z",
                            "job_count": 1,
                            "results": [{"path": str(artifact_path)}],
                        },
                    }
                )
            )
            client = FakeClient()
            result = apply_manifest(
                {
                    "base_token": "base",
                    "tables": {
                        "monitor_runs": "runs",
                        "articles": "articles",
                        "checkpoints": "checkpoints",
                        "content_review": "reviews",
                        "qa_runs": "qa",
                    },
                },
                runtime_path,
                client,
            )
            self.assertEqual(result["status"], "HANDOFF_INCOMPLETE")
            self.assertEqual(result["qa_link_warnings"][0]["status"], "QA_LINK_UNAVAILABLE")

    def test_newer_retry_becomes_current_and_preserves_older_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = complete_artifact(retry=True)
            runtime_path = write_runtime(root, [artifact])
            client = FakeClient()
            seed_exact_qa(client)
            client.tables["checkpoints"] = {
                "old-checkpoint": {
                    "复盘ID": "run-1:article-1:72h:retry:20260803T050000Z",
                    "Article Key": "article-1",
                    "检查节点": "重试",
                    "执行时间": "2026-08-03 13:00:00",
                    "数据成熟度": "MATURE",
                    "源状态": "GA4=AVAILABLE_EXACT_WINDOW;GSC=MATURE",
                    "Search Clicks": 7,
                    "Discover Clicks": 4,
                    "证据有效性": "CURRENT",
                    "取代复盘ID": None,
                }
            }

            result = apply_manifest(handoff_manifest(), runtime_path, client)

            self.assertEqual(result["status"], "SUCCESS")
            projection = result["checkpoint_projection"]
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertEqual(projection["logical_key_count"], 1)
            self.assertEqual(projection["current_count"], 1)
            self.assertEqual(projection["superseded_count"], 1)
            self.assertEqual(
                client.tables["checkpoints"]["old-checkpoint"]["证据有效性"],
                "SUPERSEDED",
            )
            self.assertEqual(
                client.tables["checkpoints"]["old-checkpoint"]["取代复盘ID"],
                checkpoint_review_id(artifact),
            )
            self.assertEqual(client.tables["checkpoints"]["old-checkpoint"]["Search Clicks"], 7)
            self.assertEqual(client.tables["checkpoints"]["old-checkpoint"]["Discover Clicks"], 4)
            retry_id = checkpoint_review_id(artifact)
            retry_rows = client.exact_records(
                "checkpoints", "复盘ID", retry_id, ("复盘ID", "证据有效性")
            )
            self.assertEqual(len(retry_rows), 1)
            self.assertEqual(retry_rows[0]["fields"]["证据有效性"], "CURRENT")
            retry_record = client.tables["checkpoints"][retry_rows[0]["record_id"]]
            self.assertIsNone(retry_record["取代复盘ID"])

    def test_projection_is_idempotent_on_second_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_path = write_runtime(root, [complete_artifact()])
            client = FakeClient()
            seed_exact_qa(client)

            first = apply_manifest(handoff_manifest(), runtime_path, client)
            second = apply_manifest(handoff_manifest(), runtime_path, client)

            self.assertEqual(first["checkpoint_projection"]["current_count"], 1)
            self.assertEqual(second["checkpoint_projection"]["current_count"], 1)
            self.assertEqual(second["checkpoint_projection"]["lifecycle_update_count"], 0)
            self.assertEqual(second["checkpoint_projection"]["lifecycle_noop_count"], 1)
            self.assertEqual(len(client.tables["checkpoints"]), 1)

    def test_duplicate_exact_review_id_blocks_before_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = complete_artifact()
            runtime_path = write_runtime(root, [artifact])
            client = FakeClient()
            duplicate = {
                "复盘ID": checkpoint_review_id(artifact),
                "Article Key": "article-1",
                "检查节点": "T+72h",
                "执行时间": "2026-08-03 14:00:00",
                "数据成熟度": "MATURE",
                "源状态": "GA4=AVAILABLE_EXACT_WINDOW;GSC=MATURE",
            }
            client.tables["checkpoints"] = {
                "duplicate-a": dict(duplicate),
                "duplicate-b": dict(duplicate),
            }

            with self.assertRaisesRegex(BaseHandoffError, "duplicate exact business key"):
                apply_manifest(handoff_manifest(), runtime_path, client)

    def test_ambiguous_lifecycle_write_requeries_and_reads_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_path = write_runtime(root, [complete_artifact()])
            client = AmbiguousLifecycleClient()
            seed_exact_qa(client)

            result = apply_manifest(handoff_manifest(), runtime_path, client)

            projection = result["checkpoint_projection"]
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(projection["current_count"], 1)
            self.assertEqual(projection["retry_count"], 1)
            self.assertTrue(client.ambiguous_lifecycle_write_seen)
            current_id = projection["current_record_ids"][0]
            self.assertEqual(client.tables["checkpoints"][current_id]["证据有效性"], "CURRENT")

    def test_missing_lifecycle_field_is_schema_blocked_without_guessing(self):
        for missing_field in ("证据有效性", "取代复盘ID"):
            with self.subTest(missing_field=missing_field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                runtime_path = write_runtime(root, [complete_artifact()])
                checkpoint_fields = FakeClient.CHECKPOINT_FIELDS - {missing_field}
                client = FakeClient(checkpoint_fields=checkpoint_fields)
                seed_exact_qa(client)

                result = apply_manifest(handoff_manifest(), runtime_path, client)

                self.assertEqual(result["status"], "HANDOFF_INCOMPLETE")
                self.assertEqual(
                    result["checkpoint_projection"]["status"], "SCHEMA_BLOCKED"
                )
                self.assertIn(
                    missing_field, result["checkpoint_projection"]["missing_fields"]
                )
                checkpoint = next(iter(client.tables["checkpoints"].values()))
                self.assertNotIn("证据有效性", checkpoint)
                self.assertNotIn("取代复盘ID", checkpoint)
                self.assertEqual(checkpoint["Search Clicks"], 20)

    def test_ineligible_observation_is_historical_without_replacement_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = complete_artifact()
            artifact["checkpoint_status"] = "DATA_NOT_MATURE"
            artifact["data_maturity"] = "DATA_NOT_MATURE"
            runtime_path = write_runtime(root, [artifact])
            client = FakeClient()
            seed_exact_qa(client)

            result = apply_manifest(handoff_manifest(), runtime_path, client)

            projection = result["checkpoint_projection"]
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertEqual(projection["current_count"], 0)
            self.assertEqual(projection["historical_count"], 1)
            historical_id = projection["historical_record_ids"][0]
            row = client.tables["checkpoints"][historical_id]
            self.assertEqual(row["证据有效性"], "HISTORICAL")
            self.assertIsNone(row["取代复盘ID"])

    def test_ineligible_observation_stays_historical_when_current_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = complete_artifact(retry=True)
            runtime_path = write_runtime(root, [artifact])
            client = FakeClient()
            seed_exact_qa(client)
            client.tables["checkpoints"] = {
                "immature-checkpoint": {
                    "复盘ID": "run-1:article-1:72h:retry:20260803T040000Z",
                    "Article Key": "article-1",
                    "检查节点": "重试",
                    "执行时间": "2026-08-03 12:00:00",
                    "数据成熟度": "DATA_NOT_MATURE",
                    "源状态": "GA4=AVAILABLE_EXACT_WINDOW;GSC=DATA_NOT_MATURE",
                    "证据有效性": "CURRENT",
                    "取代复盘ID": None,
                }
            }

            result = apply_manifest(handoff_manifest(), runtime_path, client)

            projection = result["checkpoint_projection"]
            self.assertEqual(projection["current_count"], 1)
            self.assertEqual(projection["historical_count"], 1)
            self.assertEqual(projection["superseded_count"], 0)
            row = client.tables["checkpoints"]["immature-checkpoint"]
            self.assertEqual(row["证据有效性"], "HISTORICAL")
            self.assertIsNone(row["取代复盘ID"])

    def test_source_revision_is_part_of_key_only_when_schema_exposes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_path = write_runtime(root, [complete_artifact()])
            client = FakeClient(
                checkpoint_fields=FakeClient.CHECKPOINT_FIELDS | {"Source Rev"}
            )
            seed_exact_qa(client)
            client.tables["checkpoints"] = {
                "old-revision": {
                    "复盘ID": "old-run:article-1:72h",
                    "Article Key": "article-1",
                    "检查节点": "T+72h",
                    "执行时间": "2026-08-03 15:00:00",
                    "数据成熟度": "MATURE",
                    "源状态": "GA4=AVAILABLE_EXACT_WINDOW;GSC=MATURE",
                    "Source Rev": "rev-old",
                    "证据有效性": "CURRENT",
                }
            }

            result = apply_manifest(handoff_manifest(), runtime_path, client)

            projection = result["checkpoint_projection"]
            self.assertEqual(projection["source_rev_field"], "Source Rev")
            self.assertEqual(projection["logical_keys"][0]["source_rev"], "rev-1")
            self.assertEqual(
                client.tables["checkpoints"]["old-revision"]["证据有效性"],
                "CURRENT",
            )
            current_id = projection["current_record_ids"][0]
            self.assertEqual(client.tables["checkpoints"][current_id]["Source Rev"], "rev-1")


if __name__ == "__main__":
    unittest.main()

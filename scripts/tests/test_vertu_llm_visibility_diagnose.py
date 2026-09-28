import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_llm_visibility_diagnose.py"
SPEC = importlib.util.spec_from_file_location("vertu_llm_visibility_diagnose", MODULE_PATH)
diagnose = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(diagnose)


NOW = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)
CANONICAL = "https://vertu.com/lifestyle/example/"


def payload(observations):
    return {
        "article_key": "example",
        "publication_run_id": "run-1",
        "prompt_panel_id": "panel-v1",
        "checkpoint": "T+72h",
        "canonical_url": CANONICAL,
        "crawl_access": {
            "observed_at": "2026-08-28T00:00:00Z",
            "http_status": 200,
            "robots_allowed": True,
            "noindex": False,
            "canonical_url": "https://vertu.com/lifestyle/example",
        },
        "observations": observations,
    }


def observation(prompt, citations=None, status="AVAILABLE", brand=True):
    return {
        "provider": "provider-a",
        "model": "model-a",
        "model_version": "2026-08",
        "prompt_id": prompt,
        "market": "US",
        "observed_at": "2026-08-28T00:00:00Z",
        "source_status": status,
        "citations": citations or [],
        "brand_mention_observed": brand,
    }


class LLMVisibilityDiagnosisTests(unittest.TestCase):
    def test_canonical_citation_is_observed_read_only(self):
        result, crawl, rows = diagnose.build_diagnosis(
            payload([observation("p1", [CANONICAL])]), now=NOW
        )

        self.assertIn("CITATION_OBSERVED", result["states"])
        self.assertIn("INDEXABILITY_PROXY_PASS", result["states"])
        self.assertEqual(result["summary"]["canonical_citation_rate"], 1.0)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["may_mutate_sanity"])
        self.assertFalse(crawl["proof_of_llm_indexation"])
        self.assertEqual(rows["diagnosis_fingerprint"], result["diagnosis_fingerprint"])

    def test_no_citation_does_not_claim_non_indexation(self):
        result, _, _ = diagnose.build_diagnosis(payload([observation("p1")]), now=NOW)

        self.assertIn("NO_CITATION_OBSERVED", result["states"])
        self.assertFalse(result["single_negative_proves_not_indexed"])
        self.assertFalse(result["may_change_learning_prior"])

    def test_no_available_panel_is_source_unavailable(self):
        result, _, _ = diagnose.build_diagnosis(
            payload([observation("p1", status="SOURCE_BLOCKED")]), now=NOW
        )

        self.assertIn("SOURCE_UNAVAILABLE", result["states"])
        self.assertIsNone(result["summary"]["citation_rate"])

    def test_prompt_variance_is_visible(self):
        observations = [
            observation("p1", ["https://vertu.com/another"]),
            observation("p2", []),
        ]
        result, _, _ = diagnose.build_diagnosis(payload(observations), now=NOW)

        self.assertIn("PROMPT_VARIANCE_HIGH", result["states"])
        self.assertEqual(result["summary"]["prompt_variance"]["rate_spread"], 1.0)

    def test_crawl_block_is_separate_from_model_observation(self):
        data = payload([observation("p1")])
        data["crawl_access"]["http_status"] = 403
        data["crawl_access"]["robots_allowed"] = False
        result, _, _ = diagnose.build_diagnosis(data, now=NOW)

        self.assertIn("CRAWL_BLOCKED", result["states"])
        self.assertIn("NO_CITATION_OBSERVED", result["states"])

    def test_base_handoff_is_deterministic_and_read_only(self):
        data = payload([observation("p1", [CANONICAL])])
        result, _, _ = diagnose.build_diagnosis(data, now=NOW)
        row = diagnose.build_base_handoff_row(
            data, result, "/evidence/llm-visibility-diagnosis.json"
        )

        self.assertIsNone(row["table_id"])
        self.assertEqual(row["configuration_status"], "MISSING_CONFIGURATION")
        self.assertFalse(row["authorises_write"])
        self.assertEqual(
            row["business_key"]["value"],
            "llm-visibility:example:T+72h:panel-v1",
        )
        self.assertEqual(row["fields"]["记录来源"], "LLM诊断")
        self.assertEqual(row["fields"]["诊断类型"], "LLM Visibility")
        self.assertEqual(row["fields"]["引用数"], 1)
        self.assertEqual(row["fields"]["观察日期"], "2026-08-28 00:00:00")
        self.assertTrue(row["requires_exact_readback"])
        self.assertFalse(row["may_mutate_sanity"])

    def test_explicit_configuration_does_not_grant_write_authority(self):
        data = payload([observation("p1", [CANONICAL])])
        result, _, _ = diagnose.build_diagnosis(data, now=NOW)
        row = diagnose.build_base_handoff_row(data, result, "/evidence/diagnosis.json",
            integration_config={"base_token": "test-base", "checkpoint_table_id": "test-checkpoints", "article_table_id": "test-articles"})
        self.assertEqual(row["configuration_status"], "CONFIGURED")
        self.assertEqual(row["table_id"], "test-checkpoints")
        self.assertFalse(row["authorises_write"])

    def test_literal_placeholder_is_not_configuration(self):
        data = payload([observation("p1", [CANONICAL])])
        result, _, _ = diagnose.build_diagnosis(data, now=NOW)
        row = diagnose.build_base_handoff_row(data, result, "/evidence/diagnosis.json",
            integration_config={"base_token": "${FEISHU_BASE_TOKEN}", "checkpoint_table_id": "test-checkpoints", "article_table_id": "test-articles"})
        self.assertEqual(row["configuration_status"], "MISSING_CONFIGURATION")
        self.assertIsNone(row["base_token"])


if __name__ == "__main__":
    unittest.main()

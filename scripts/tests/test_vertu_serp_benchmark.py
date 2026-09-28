import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_serp_benchmark.py"
SPEC = importlib.util.spec_from_file_location("vertu_serp_benchmark", MODULE_PATH)
benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(benchmark)


NOW = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)


def payload(result_count=5, body_count=3):
    results = []
    for index in range(result_count):
        accessible = index < body_count
        results.append(
            {
                "rank": index + 1,
                "title": f"Result {index}",
                "url": f"https://example{index}.com/article",
                "snippet": "A result summary",
                "status_code": 200 if accessible else 403,
                "published_at": "2026-08-27T00:00:00Z",
                "headings": ["How it works", "Decision checklist"] if accessible else [],
                "word_count": 1200 if accessible else None,
                "format_type": "buyer_guide",
                "value_objects": ["comparison table"] if accessible else [],
            }
        )
    return {
        "query": "secure AI phone comparison",
        "market": "US",
        "language": "en-US",
        "device": "mobile",
        "source_type": "authorised_serp_export",
        "observed_at": "2026-08-28T00:00:00Z",
        "results": results,
    }


DELTA = "A verified decision matrix comparing privacy controls, update policy, ownership cost and market-specific risks."


class SerpBenchmarkTests(unittest.TestCase):
    def build(self, data=None, **overrides):
        values = {
            "selected_query": "secure AI phone comparison",
            "selected_intent": "buyer comparison",
            "proposed_query": "secure AI phone comparison",
            "proposed_intent": "buyer comparison",
            "original_value_delta": DELTA,
            "now": NOW,
        }
        values.update(overrides)
        return benchmark.build_benchmark(data or payload(), **values)

    def test_pass_requires_sufficient_exact_serp_and_value_delta(self):
        result, anatomy, brief = self.build()

        self.assertEqual(result["verdict"], "BENCHMARK_PASS")
        self.assertEqual(result["next_stage"], "EVIDENCE_PACK")
        self.assertEqual(anatomy["accessible_body_count"], 3)
        self.assertIn("table", result["required_value_object_types"])
        self.assertIn("risk_analysis", result["required_value_object_types"])
        self.assertIn(result["benchmark_fingerprint"], brief)
        self.assertFalse(result["copying_permitted"])

    def test_thin_body_evidence_blocks_drafting(self):
        result, _, _ = self.build(payload(5, 2))

        self.assertEqual(result["verdict"], "SERP_BENCHMARK_SOURCE_BLOCKED")
        self.assertEqual(result["next_stage"], "STOP_DRAFTING")

    def test_query_or_intent_change_returns_to_scoring(self):
        result, _, _ = self.build(proposed_intent="definition explainer")

        self.assertEqual(result["verdict"], "BENCHMARK_REFRAME")
        self.assertEqual(result["next_stage"], "RETURN_TO_SCORING")

    def test_generic_value_delta_requires_replacement(self):
        result, _, _ = self.build(original_value_delta="More comprehensive")

        self.assertEqual(result["verdict"], "BENCHMARK_REPLACE")

    def test_export_query_mismatch_is_source_blocked(self):
        data = payload()
        data["query"] = "different query"
        result, _, _ = self.build(data)

        self.assertEqual(result["verdict"], "SERP_BENCHMARK_SOURCE_BLOCKED")


if __name__ == "__main__":
    unittest.main()

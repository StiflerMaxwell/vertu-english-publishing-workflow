import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "vertu_brand_mindset_gate.py"
SPEC = importlib.util.spec_from_file_location("brand_gate", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)

REPLAY_PATH = Path(__file__).parents[1] / "vertu_brand_mindset_replay.py"
REPLAY_SPEC = importlib.util.spec_from_file_location("brand_gate_replay", REPLAY_PATH)
REPLAY = importlib.util.module_from_spec(REPLAY_SPEC)
assert REPLAY_SPEC.loader
REPLAY_SPEC.loader.exec_module(REPLAY)


def dimension(status="PASS", rationale="Relevant verified relationship", ref="artifact://brand-evidence"):
    return {
        "status": status,
        "rationale": rationale,
        "evidence_refs": [ref] if ref else [],
    }


def candidate(**overrides):
    row = {
        "candidate_id": "most-expensive-phones",
        "title": "The Most Expensive Phones in the World",
        "content_mode": "LUXURY_AUTHORITY_STORY",
        "brand_mindset_predeclared": True,
        "brand_mindset_evidence": {
            "audience_overlap": dimension(ref="artifact://audience/high-net-worth-mobile"),
            "mindset_overlap": dimension(ref="artifact://mindset/rarity-craft"),
            "editorial_right_to_win": dimension(ref="artifact://vertu/luxury-mobile-authority"),
        },
        "brand_conflicts": [],
        "authority_story_evidence": [
            {
                "type": "VERIFIED_PRICE_OR_TRANSACTION",
                "status": "AVAILABLE",
                "evidence_refs": ["https://example.com/verified-price"],
            },
            {
                "type": "MATERIAL_OR_CRAFT",
                "status": "AVAILABLE",
                "evidence_refs": ["https://example.com/craft"],
            },
        ],
    }
    row.update(overrides)
    return row


class BrandMindsetGateTests(unittest.TestCase):
    def test_expensive_phone_authority_story_is_core(self):
        result = MODULE.evaluate_candidate(candidate())
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["brand_mindset_class"], "CORE_MINDSPACE")
        self.assertEqual(result["authority_story_evidence"]["verified_type_count"], 2)
        self.assertFalse(result["traffic_score_authority"])
        self.assertTrue(MODULE.validate_result(result))

    def test_two_dimensions_are_qualified_adjacent(self):
        row = candidate(content_mode="DECISION_GUIDE", authority_story_evidence=[])
        row["brand_mindset_evidence"]["editorial_right_to_win"] = dimension(
            status="FAIL", rationale="No direct editorial authority", ref=None
        )
        result = MODULE.evaluate_candidate(row)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["brand_mindset_class"], "QUALIFIED_ADJACENT")
        self.assertEqual(result["recommended_audience_fit_lane"], "ADJACENT")

    def test_generic_refrigerator_is_rejected_even_with_three_claimed_dimensions(self):
        row = candidate(
            candidate_id="best-smart-refrigerator",
            title="Best Smart Refrigerators",
            content_mode="DECISION_GUIDE",
            authority_story_evidence=[],
            brand_conflicts=["COMMODITY_LIFESTYLE_MISMATCH"],
        )
        result = MODULE.evaluate_candidate(row)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertEqual(result["brand_mindset_class"], "UNQUALIFIED")
        self.assertEqual(result["brand_conflict_veto"], ["COMMODITY_LIFESTYLE_MISMATCH"])

    def test_missing_dimension_evidence_holds_instead_of_guessing(self):
        row = candidate(content_mode="DECISION_GUIDE", authority_story_evidence=[])
        row["brand_mindset_evidence"] = {
            "audience_overlap": dimension(),
            "mindset_overlap": dimension(
                status="SOURCE_UNAVAILABLE", rationale="Source blocked", ref=None
            ),
        }
        result = MODULE.evaluate_candidate(row)
        self.assertEqual(result["verdict"], "HOLD")
        self.assertIn("missing_dimension:editorial_right_to_win", result["validation_errors"])

    def test_price_only_authority_story_is_rejected(self):
        row = candidate(
            authority_story_evidence=[
                {
                    "type": "VERIFIED_PRICE_OR_TRANSACTION",
                    "status": "AVAILABLE",
                    "evidence_refs": ["https://example.com/price"],
                }
            ]
        )
        result = MODULE.evaluate_candidate(row)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertIn("PRICE_ONLY_LUXURY_LABEL", result["brand_conflict_veto"])

    def test_result_fingerprint_detects_tampering(self):
        result = MODULE.evaluate_candidate(candidate())
        result["brand_mindset_class"] = "QUALIFIED_ADJACENT"
        self.assertFalse(MODULE.validate_result(result))

    def test_process_payload_preserves_candidates_and_emits_summary(self):
        result, summary = MODULE.process_payload({"candidates": [candidate()]})
        self.assertEqual(result["candidates"][0]["brand_mindset_gate"]["verdict"], "PASS")
        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["verdict_counts"]["PASS"], 1)
        self.assertEqual(len(summary["snapshot_fingerprint"]), 64)

    def test_legacy_replay_rejects_obvious_refrigerator_topic(self):
        result = REPLAY.classify_legacy_article(
            {"title": "French-Door vs Side-by-Side Refrigerator"}
        )
        self.assertEqual(result["verdict"], "REJECT")
        self.assertEqual(result["reason"], "OBVIOUS_COMMODITY_LIFESTYLE_CONFLICT")

    def test_legacy_replay_preserves_clear_watch_topic(self):
        result = REPLAY.classify_legacy_article(
            {"title": "Automatic vs Manual-Wind Watch"}
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["brand_mindset_class"], "CORE_MINDSPACE")


if __name__ == "__main__":
    unittest.main()

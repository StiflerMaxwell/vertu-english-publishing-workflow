import importlib.util
import pathlib
import sys
import unittest


SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "vertu_content_factor_extractor.py"
SPEC = importlib.util.spec_from_file_location("vertu_content_factor_extractor", MODULE_PATH)
extractor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(extractor)


OBSERVED = "2026-08-25T02:00:00Z"


def candidate():
    return {
        "candidate_id": "T01",
        "title": "Turbo vs Supercharger",
        "query_intent_boundary": "turbo vs supercharger",
        "section": "guides",
        "outcome_lane": "discover-first",
        "trend_class": "RISING_SEARCH",
        "editorial_signal": "NONE",
        "decision_intent": "choose power delivery",
        "cluster_id": "premium_automotive_decisions",
        "audience_fit_lane": "premium_automotive_decisions",
        "value_object": "power delivery decision matrix",
        "visual_subject": "two unbranded cutaway engines showing different forced induction layouts",
        "predraft_discover_forecast": {
            "verdict": "PASS",
            "reader_consequence": "choose response, efficiency and ownership trade-offs",
        },
        "primary_source": "https://example.com/primary",
        "secondary_source": "https://example.com/secondary",
        "demand_signals": [
            {
                "provider": "google_ads_keyword_planner",
                "status": "AVAILABLE",
                "positive": True,
                "metrics": {"keyword": "turbo vs supercharger"},
            }
        ],
        "dimension_evidence": {
            "historical_fit": {"evidence_refs": ["artifact://history"]},
            "original_value": {"evidence_refs": ["artifact://value"]},
        },
        "inventory_overlap": {"exactish_count": 0},
        "historical_cluster_metrics": {
            "discover_clicks": 120,
            "discover_ctr": 0.04,
            "search_clicks": 80,
            "search_ctr": 0.03,
            "ga4_engagement_rate": 0.55,
            "growth_pct": 18,
            "evidence_ref": "artifact://cluster",
        },
        "serp_metrics": {
            "weak_result_count": 3,
            "freshness_gap_days": 240,
            "evidence_ref": "artifact://serp",
        },
        "vetoes": [],
    }


class ExtractorTests(unittest.TestCase):
    def paths(self):
        return {
            "keyword_planner": pathlib.Path("keyword.json"),
            "targeted_gsc": pathlib.Path("gsc.json"),
            "realtime_trends": pathlib.Path("trends.json"),
            "source_velocity": pathlib.Path("velocity.json"),
            "sanity_inventory": pathlib.Path("inventory.json"),
        }

    def test_extractor_emits_all_32_factors_from_raw_artifacts(self):
        keyword = {
            "fetched_at": OBSERVED,
            "seed_metrics": [
                {
                    "keyword": "turbo vs supercharger",
                    "average_monthly_searches": 8100,
                    "monthly_search_volumes": [
                        {"monthly_searches": 6000},
                        {"monthly_searches": 7000},
                        {"monthly_searches": 8100},
                    ],
                }
            ],
        }
        gsc = {
            "fetched_at": OBSERVED,
            "candidates": {
                "turbo vs supercharger": {
                    "recent_28d": {
                        "row_count": 2,
                        "clicks": 12,
                        "impressions": 300,
                    },
                    "previous_28d": {
                        "row_count": 1,
                        "clicks": 8,
                        "impressions": 220,
                    },
                    "trailing_365d": {
                        "row_count": 3,
                        "clicks": 40,
                        "impressions": 900,
                    },
                }
            },
        }
        row = candidate()
        result = extractor.extract_candidate(
            row,
            observed_at=OBSERVED,
            paths=self.paths(),
            keyword_rows=extractor._index_keyword_planner(keyword),
            keyword_payload=keyword,
            gsc_rows=extractor._index_mapping(gsc, "candidates"),
            gsc_payload=gsc,
            realtime_payload={"observed_at": OBSERVED, "topics": []},
            velocity_rows={},
            velocity_payload={"generated_at": OBSERVED, "candidates": []},
            visual_occurrences={extractor._normalise(row["visual_subject"]): 1},
        )
        factors = result["direct_factor_evidence"]

        self.assertEqual(len(factors), 32)
        self.assertEqual(
            factors["keyword_planner_avg_monthly_searches"]["raw_value"], 8100
        )
        self.assertAlmostEqual(
            factors["keyword_planner_growth_pct"]["raw_value"],
            15.714285714285714,
        )
        self.assertEqual(factors["gsc_candidate_clicks"]["raw_value"], 12)
        self.assertEqual(factors["gsc_candidate_ctr"]["raw_value"], 0.04)
        self.assertEqual(
            factors["official_trends_interest"]["status"], "NOT_APPLICABLE"
        )
        self.assertEqual(
            factors["visual_specificity_checks_passed"]["raw_value"], 4
        )
        self.assertEqual(
            factors["reader_decision_checks_passed"]["raw_value"], 5
        )

    def test_zero_gsc_rows_are_insufficient_sample_not_zero_score(self):
        row = candidate()
        result = extractor.extract_candidate(
            row,
            observed_at=OBSERVED,
            paths=self.paths(),
            keyword_rows={},
            keyword_payload=None,
            gsc_rows={
                "turbo vs supercharger": {
                    "recent_28d": {"row_count": 0, "clicks": 0, "impressions": 0},
                    "trailing_365d": {"row_count": 0, "clicks": 0, "impressions": 0},
                }
            },
            gsc_payload={"fetched_at": OBSERVED},
            realtime_payload=None,
            velocity_rows={},
            velocity_payload=None,
            visual_occurrences={extractor._normalise(row["visual_subject"]): 1},
        )
        factor = result["direct_factor_evidence"]["gsc_candidate_clicks"]

        self.assertEqual(factor["status"], "INSUFFICIENT_SAMPLE")
        self.assertNotIn("score_100", factor)


if __name__ == "__main__":
    unittest.main()

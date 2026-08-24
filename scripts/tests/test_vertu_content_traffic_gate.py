import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_content_traffic_gate.py"
SPEC = importlib.util.spec_from_file_location("vertu_content_traffic_gate", MODULE_PATH)
traffic_gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(traffic_gate)
NOW_ISO = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def evidence(score=85, ref="artifact://evidence"):
    return {
        "score_100": score,
        "evidence_refs": [ref],
        "observed_at": "2026-07-21T08:00:00Z",
    }


def valid_candidate(**overrides):
    candidate = {
        "candidate_id": "travel-watch-movement-2026",
        "title": "Mechanical vs Quartz vs Solar for Travel",
        "slug": "mechanical-quartz-solar-travel-watch",
        "section": "guides",
        "outcome_lane": "Search-first",
        "portfolio_bucket": "proven_demand",
        "trend_class": "REALTIME_HOT",
        "editorial_signal": "NONE",
        "publication_run_id": "run-test",
        "intent_key": "best-travel-watch-movement",
        "entities": ["travel watch"],
        "demand_signals": [
            {
                "provider": "gsc",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 90,
                "evidence_ref": "artifact://gsc-query-page",
                "observed_at": NOW_ISO,
                "metrics": {"impressions": 2308, "clicks": 66},
            },
            {
                "provider": "google_trends_realtime",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 80,
                "evidence_ref": "https://trends.google.com/example",
                "observed_at": NOW_ISO,
                "metrics": {
                    "markets": ["US"],
                    "trend_query": "best travel watch movement",
                    "age_hours": 2,
                    "approx_traffic": 20_000,
                    "news_confirmation_count": 2,
                    "source_method": "official_trending_now_rss",
                    "official_google_source": True,
                    "source_url": "https://trends.google.com/trending/rss?geo=US",
                    "primary_source_url": "https://example.com/official-launch",
                    "primary_source_observed_at": NOW_ISO,
                    "primary_source_published_at": NOW_ISO,
                    "primary_source_http_status": 200,
                    "primary_source_relation": "official_announcement",
                    "primary_source_relevance_terms": ["travel", "watch"],
                },
            },
            {
                "provider": "keyword_planner",
                "status": "SOURCE_UNAVAILABLE",
                "reason": "Google Ads customer access not configured",
                "observed_at": "2026-07-21T08:06:00Z",
            },
        ],
        "dimension_evidence": {
            "historical_fit": evidence(90, "artifact://gsc-cluster"),
            "trend_velocity": evidence(85, "https://trends.google.com/example"),
            "serp_gap": evidence(80, "artifact://serp-snapshot"),
            "discover_story": evidence(80, "artifact://visual-story"),
            "original_value": evidence(90, "artifact://value-object"),
            "right_to_win": evidence(90, "artifact://vertu-audience-fit"),
        },
        "cluster_support": {
            "cluster_role": "opportunity_page",
            "query_boundary": "travel watch movement comparison",
            "outbound_destinations": ["https://vertu.com/lifestyle/example"],
            "inbound_candidates": [
                "https://vertu.com/lifestyle/a",
                "https://vertu.com/lifestyle/b",
                "https://vertu.com/guides/c",
            ],
        },
        "vetoes": [],
    }
    candidate.update(overrides)
    return candidate


def realtime_snapshot(query="best travel watch movement", market="US"):
    snapshot = {
        "contract_version": "realtime-trends-v1",
        "run_id": "run-test",
        "provider": "google_trends_trending_now",
        "source_method": "official_trending_now_rss",
        "official_google_source": True,
        "credentials_included": False,
        "status": "AVAILABLE",
        "observed_at": NOW_ISO,
        "topics": [
            {
                "query": query,
                "markets": [market],
                "realtime_candidate": True,
                "newest_published_at": NOW_ISO,
                "minimum_age_hours": 2,
                "max_approx_traffic": 20_000,
                "news_confirmation_count": 2,
                "evidence": [
                    {
                        "geo": market,
                        "published_at": NOW_ISO,
                        "approx_traffic": 20_000,
                        "news_confirmation_count": 2,
                        "source_url": f"https://trends.google.com/trending/rss?geo={market}",
                    }
                ],
            }
        ],
    }
    snapshot["snapshot_fingerprint"] = traffic_gate._snapshot_fingerprint(snapshot)
    return snapshot


def evaluate_with_snapshot(candidate, snapshot=None):
    snapshot = snapshot or realtime_snapshot()
    candidate["publication_run_id"] = snapshot["run_id"]
    candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
        "snapshot_fingerprint"
    ]
    trend_verified = {
        f"{traffic_gate._trend_topic_key(topic['query'])}|{row['source_url']}"
        for topic in snapshot["topics"]
        for row in topic["evidence"]
    }
    primary_verified = {
        "https://example.com/official-launch": {
            "verified": True,
            "http_status": 200,
            "matched_relevance_terms": ["travel", "watch"],
        }
    }
    return traffic_gate.evaluate_candidate(
        candidate,
        traffic_gate._realtime_topic_registry(snapshot),
        trend_verified,
        primary_verified,
    )


def live_verifications(snapshot):
    return {
        "trend_verified": {
            f"{traffic_gate._trend_topic_key(topic['query'])}|{row['source_url']}"
            for topic in snapshot["topics"]
            for row in topic["evidence"]
        },
        "primary_verified": {
            "https://example.com/official-launch": {"verified": True}
        },
        "receipts": [],
    }


def d2tr_context(observed_at=NOW_ISO):
    payload = {
        "contract_version": "d2tr-discover-context-v1",
        "provider": "d2tr_public_discover",
        "official_google_source": False,
        "may_create_google_demand": False,
        "may_create_realtime_hot": False,
        "credentials_included": False,
        "execution_id": "d2tr-test",
        "observed_at": observed_at,
        "expires_at": "2099-09-05T00:00:00Z",
        "status": "AVAILABLE",
        "source_snapshot_fingerprint": "source-fingerprint",
        "markets": {
            "US": {
                "status": "AVAILABLE",
                "volatility": {
                    "name": "ALL",
                    "status": "AVAILABLE",
                    "current_value": 7.4,
                    "trend": "RISING",
                    "state": "ACTIVE",
                    "source_generated_at": observed_at,
                },
                "format_groups": {
                    "Service": {
                        "name": "Service",
                        "status": "AVAILABLE",
                        "current_value": 6.4,
                        "trend": "RISING",
                        "state": "ACTIVE",
                        "source_generated_at": observed_at,
                    }
                },
                "topics": {
                    "Travel": {
                        "name": "Travel",
                        "status": "AVAILABLE",
                        "current_value": 7.1,
                        "trend": "RISING",
                        "state": "ACTIVE",
                        "source_generated_at": observed_at,
                    }
                },
                "formats": {},
                "categories": {},
            }
        },
    }
    payload["snapshot_fingerprint"] = traffic_gate._snapshot_fingerprint(payload)
    return payload


class CandidateEvaluationTests(unittest.TestCase):
    def test_valid_search_candidate_gets_computed_score_and_passes(self):
        result = evaluate_with_snapshot(valid_candidate())

        self.assertTrue(result["eligible"])
        self.assertEqual(result["demand_verdict"], "STRONG")
        self.assertGreaterEqual(result["score"], 80)
        self.assertEqual(result["score_source"], traffic_gate.SCORE_SOURCE)
        self.assertEqual(
            result["score_contract_version"],
            traffic_gate.TRAFFIC_GATE_CONTRACT_VERSION,
        )
        self.assertEqual(result["raw_score"], result["score"])
        self.assertTrue(result["hot_label_eligible"])
        self.assertIn("market_demand", result["score_breakdown"])

    def test_missing_dimension_evidence_is_rejected(self):
        candidate = valid_candidate()
        candidate["dimension_evidence"]["serp_gap"]["evidence_refs"] = []

        result = evaluate_with_snapshot(candidate)

        self.assertFalse(result["eligible"])
        self.assertIn("missing_dimension_evidence:serp_gap", result["validation_errors"])

    def test_search_candidate_requires_two_independent_positive_signals(self):
        candidate = valid_candidate()
        candidate["demand_signals"][1]["positive"] = False

        result = evaluate_with_snapshot(candidate)

        self.assertFalse(result["eligible"])
        self.assertEqual(result["demand_verdict"], "REJECT")
        self.assertIn("insufficient_independent_demand_signals", result["vetoes"])

    def test_unavailable_source_is_preserved_not_converted_to_zero(self):
        result = evaluate_with_snapshot(valid_candidate())

        unavailable = result["source_statuses"]["keyword_planner"]
        self.assertEqual(unavailable["status"], "SOURCE_UNAVAILABLE")
        self.assertNotIn("score_100", unavailable)

    def test_same_family_alias_and_supporting_signal_count_once(self):
        candidate = valid_candidate(trend_class="EVERGREEN_SEARCH")
        candidate["demand_signals"] = [
            {
                "provider": "google_ads_keyword_planner",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 70,
                "evidence_ref": "artifact://keyword-planner",
                "observed_at": NOW_ISO,
                "metrics": {"average_monthly_searches": 1000},
            },
            {
                "provider": "current_interest",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 95,
                "evidence_ref": "artifact://keyword-planner#recent",
                "observed_at": NOW_ISO,
                "metrics": {
                    "average_monthly_searches": 1000,
                    "recent_month_searches": 1400,
                },
            },
        ]

        result = traffic_gate.evaluate_candidate(candidate)

        self.assertEqual(
            result["positive_demand_provider_families"],
            ["google_ads_keyword_planner"],
        )
        self.assertEqual(
            result["score_breakdown"]["market_demand"]["score_100"], 95
        )
        family = result["score_breakdown"]["market_demand"][
            "provider_family_scores"
        ]["google_ads_keyword_planner"]
        self.assertEqual(family["selected_provider"], "current_interest")
        current_interest = next(
            row
            for row in result["demand_signal_qualifications"]
            if row["provider"] == "current_interest"
        )
        self.assertEqual(
            current_interest["provider_family"], "google_ads_keyword_planner"
        )
        self.assertEqual(current_interest["demand_role"], "supporting_current")
        self.assertFalse(current_interest["counts_for_search_demand"])
        self.assertFalse(result["eligible"])
        self.assertIn("insufficient_independent_demand_signals", result["vetoes"])

    def test_supporting_current_signal_is_not_an_independent_search_provider(self):
        candidate = valid_candidate(trend_class="EVERGREEN_SEARCH")
        candidate["demand_signals"] = [
            {
                "provider": "gsc_candidate_query_page",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://gsc",
                "observed_at": NOW_ISO,
                "metrics": {"clicks": 3, "impressions": 100},
            },
            {
                "provider": "current_event",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://editorial-current",
                "observed_at": NOW_ISO,
                "metrics": {"publisher_count": 5},
            },
        ]

        result = traffic_gate.evaluate_candidate(candidate)

        self.assertEqual(result["positive_demand_provider_families"], ["gsc"])
        self.assertEqual(result["qualified_supporting_providers"], ["current_event"])
        self.assertFalse(result["eligible"])
        self.assertIn("insufficient_independent_demand_signals", result["vetoes"])

    def test_tiny_gsc_sample_stays_available_but_does_not_count(self):
        candidate = valid_candidate(trend_class="EVERGREEN_SEARCH")
        candidate["demand_signals"] = [
            {
                "provider": "gsc_candidate_query_page",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://gsc-tiny",
                "observed_at": NOW_ISO,
                "metrics": {
                    "recent_clicks": 0,
                    "recent_impressions": 3,
                    "annual_clicks": 44,
                    "annual_impressions": 649,
                },
            },
            {
                "provider": "google_ads_keyword_planner",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://keyword-planner",
                "observed_at": NOW_ISO,
                "metrics": {"average_monthly_searches": 1000},
            },
        ]

        result = traffic_gate.evaluate_candidate(candidate)

        gsc = result["source_statuses"]["gsc_candidate_query_page"]
        self.assertEqual(gsc["status"], "AVAILABLE")
        self.assertTrue(gsc["positive"])
        self.assertEqual(
            gsc["metrics"],
            {
                "recent_clicks": 0,
                "recent_impressions": 3,
                "annual_clicks": 44,
                "annual_impressions": 649,
            },
        )
        self.assertEqual(gsc["qualification_status"], "INSUFFICIENT_SAMPLE")
        self.assertEqual(
            gsc["qualification_metrics"],
            {
                "clicks": 0.0,
                "impressions": 3.0,
                "metric_window": "recent_finalised",
            },
        )
        self.assertFalse(gsc["effectively_positive"])
        self.assertFalse(gsc["counts_for_search_demand"])
        self.assertEqual(
            result["positive_demand_provider_families"],
            ["google_ads_keyword_planner"],
        )
        self.assertNotIn(
            "gsc", result["score_breakdown"]["market_demand"]["provider_families"]
        )
        self.assertFalse(result["eligible"])

    def test_valid_gsc_and_keyword_planner_are_independent_families(self):
        candidate = valid_candidate(trend_class="EVERGREEN_SEARCH")
        candidate["demand_signals"] = [
            {
                "provider": "gsc_candidate_query_page",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://gsc",
                "observed_at": NOW_ISO,
                "metrics": {"recent_clicks": 44, "recent_impressions": 649},
            },
            {
                "provider": "keyword_planner",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://keyword-planner",
                "observed_at": NOW_ISO,
                "metrics": {"average_monthly_searches": 1000},
            },
        ]

        result = traffic_gate.evaluate_candidate(candidate)

        self.assertEqual(
            result["positive_demand_provider_families"],
            ["google_ads_keyword_planner", "gsc"],
        )
        self.assertEqual(result["demand_verdict"], "STRONG")
        self.assertTrue(result["eligible"])

    def test_annual_gsc_metrics_are_used_when_recent_window_is_absent(self):
        candidate = valid_candidate(trend_class="EVERGREEN_SEARCH")
        candidate["demand_signals"] = [
            {
                "provider": "gsc_candidate_query_page",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://gsc",
                "observed_at": NOW_ISO,
                "metrics": {"annual_clicks": 44, "annual_impressions": 649},
            },
            {
                "provider": "google_ads_keyword_planner",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://keyword-planner",
                "observed_at": NOW_ISO,
                "metrics": {"average_monthly_searches": 1000},
            },
        ]

        result = traffic_gate.evaluate_candidate(candidate)

        gsc = result["source_statuses"]["gsc_candidate_query_page"]
        self.assertEqual(gsc["qualification_status"], "QUALIFIED")
        self.assertEqual(
            gsc["qualification_metrics"]["metric_window"], "annual_finalised"
        )
        self.assertTrue(result["eligible"])

    def test_keyword_planner_current_interest_retains_rising_role(self):
        candidate = valid_candidate(trend_class="RISING_SEARCH")
        candidate["demand_signals"] = [
            {
                "provider": "gsc_candidate_query_page",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 100,
                "evidence_ref": "artifact://gsc",
                "observed_at": NOW_ISO,
                "metrics": {"recent_clicks": 44, "recent_impressions": 649},
            },
            {
                "provider": "google_ads_keyword_planner",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 90,
                "evidence_ref": "artifact://keyword-planner",
                "observed_at": NOW_ISO,
                "metrics": {"average_monthly_searches": 1000},
            },
            {
                "provider": "current_interest",
                "status": "AVAILABLE",
                "positive": True,
                "score_100": 95,
                "evidence_ref": "artifact://keyword-planner.json#recent-vs-average",
                "observed_at": NOW_ISO,
                "metrics": {
                    "recent_month_searches": 1400,
                    "average_monthly_searches": 1000,
                },
            },
        ]

        result = traffic_gate.evaluate_candidate(candidate)

        self.assertNotIn("unverified_rising_search_label", result["vetoes"])
        self.assertEqual(
            result["positive_demand_provider_families"],
            ["google_ads_keyword_planner", "gsc"],
        )
        self.assertEqual(
            result["score_breakdown"]["market_demand"][
                "provider_family_scores"
            ]["google_ads_keyword_planner"]["selected_provider"],
            "current_interest",
        )
        self.assertTrue(result["eligible"])

    def test_realtime_hot_label_requires_verified_official_trends(self):
        candidate = valid_candidate()
        candidate["demand_signals"][1]["metrics"]["official_google_source"] = False

        result = evaluate_with_snapshot(candidate)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["hot_label_eligible"])
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_realtime_hot_label_rejects_forged_official_flag_without_google_url(self):
        candidate = valid_candidate()
        candidate["demand_signals"][1]["metrics"]["source_url"] = (
            "https://example.com/not-google-trends"
        )

        result = evaluate_with_snapshot(candidate)

        self.assertFalse(result["eligible"])
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_realtime_hot_label_must_reconcile_to_collected_snapshot(self):
        candidate = valid_candidate()
        snapshot = realtime_snapshot(query="a different trend")
        result = evaluate_with_snapshot(candidate, snapshot)

        self.assertFalse(result["eligible"])
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_direct_evaluator_cannot_bypass_snapshot_reconciliation(self):
        result = traffic_gate.evaluate_candidate(valid_candidate())

        self.assertFalse(result["eligible"])
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_snapshot_fingerprint_and_all_declared_markets_must_match(self):
        candidate = valid_candidate()
        candidate["demand_signals"][1]["metrics"]["markets"] = ["US", "GB"]
        result = evaluate_with_snapshot(candidate)
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

        snapshot = realtime_snapshot()
        snapshot["topics"][0]["max_approx_traffic"] = 99_999
        candidate = valid_candidate()
        result = evaluate_with_snapshot(candidate, snapshot)
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_candidate_metrics_cannot_diverge_from_snapshot(self):
        candidate = valid_candidate()
        candidate["demand_signals"][1]["metrics"]["approx_traffic"] = 999_999

        result = evaluate_with_snapshot(candidate)

        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_extra_fabricated_google_source_url_is_rejected(self):
        candidate = valid_candidate()
        candidate["demand_signals"][1]["metrics"]["source_urls"] = [
            "https://trends.google.com/trending/rss?geo=US",
            "https://trends.google.com/fabricated-evidence",
        ]

        result = evaluate_with_snapshot(candidate)

        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_primary_source_requires_live_verification(self):
        candidate = valid_candidate()
        snapshot = realtime_snapshot()
        candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
            "snapshot_fingerprint"
        ]
        verification = live_verifications(snapshot)
        verification["primary_verified"]["https://example.com/official-launch"] = {
            "verified": False
        }

        result = traffic_gate.evaluate_candidate(
            candidate,
            traffic_gate._realtime_topic_registry(snapshot),
            verification["trend_verified"],
            verification["primary_verified"],
        )

        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_primary_source_partial_content_is_valid_for_range_verification(self):
        candidate = valid_candidate()
        snapshot = realtime_snapshot()
        candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
            "snapshot_fingerprint"
        ]
        candidate["demand_signals"][1]["metrics"]["primary_source_http_status"] = 206
        verification = live_verifications(snapshot)
        verification["primary_verified"]["https://example.com/official-launch"] = {
            "verified": True,
            "http_status": 206,
            "matched_relevance_terms": ["travel", "watch"],
        }

        result = traffic_gate.evaluate_candidate(
            candidate,
            traffic_gate._realtime_topic_registry(snapshot),
            verification["trend_verified"],
            verification["primary_verified"],
        )

        self.assertNotIn("unverified_realtime_hot_label", result["vetoes"])

    def test_blank_market_and_missing_primary_source_are_rejected(self):
        candidate = valid_candidate()
        candidate["demand_signals"][1]["metrics"]["markets"] = [""]
        result = evaluate_with_snapshot(candidate)
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

        candidate = valid_candidate()
        candidate["demand_signals"][1]["metrics"]["primary_source_http_status"] = 404
        result = evaluate_with_snapshot(candidate)
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

        candidate = valid_candidate()
        candidate["demand_signals"][1]["metrics"].pop("primary_source_url")
        result = evaluate_with_snapshot(candidate)
        self.assertIn("unverified_realtime_hot_label", result["vetoes"])

    def test_evergreen_candidate_cannot_inflate_trend_velocity(self):
        candidate = valid_candidate(trend_class="EVERGREEN_SEARCH")
        candidate["demand_signals"][1]["provider"] = "keyword_planner_recent"
        candidate["dimension_evidence"]["trend_velocity"]["score_100"] = 95

        result = traffic_gate.evaluate_candidate(candidate)

        trend = result["score_breakdown"]["trend_velocity"]
        self.assertEqual(trend["raw_score_100"], 95)
        self.assertEqual(trend["score_100"], 45)
        self.assertFalse(result["hot_label_eligible"])

    def test_missing_trend_class_is_rejected(self):
        candidate = valid_candidate()
        candidate.pop("trend_class")

        result = traffic_gate.evaluate_candidate(candidate)

        self.assertFalse(result["eligible"])
        self.assertIn(
            "invalid_or_missing_trend_class",
            result["validation_errors"],
        )

    def test_editorial_breakout_can_support_discover_without_google_hot_label(self):
        candidate = valid_candidate(
            outcome_lane="Discover-first",
            trend_class="EVERGREEN_SEARCH",
            editorial_signal="EDITORIAL_BREAKOUT",
        )
        candidate["demand_signals"][1]["provider"] = "gsc_recent_cluster"
        candidate["demand_signals"][1]["metrics"] = {"impressions": 1200}
        candidate["dimension_evidence"]["discover_story"]["score_100"] = 90
        velocity = {
            candidate["candidate_id"]: {
                "candidate_id": candidate["candidate_id"],
                "editorial_signal": "EDITORIAL_BREAKOUT",
                "primary_source": {
                    "url": "https://example.com/official-launch",
                    "verified_at": NOW_ISO,
                    "status": "AVAILABLE",
                },
                "independent_coverage": [
                    {"url": "https://example.org/a", "status": "AVAILABLE"},
                    {"url": "https://example.net/b", "status": "AVAILABLE"},
                ],
                "community_signals": [],
                "broad_reader_consequence": "Changes the price and speed of AI tools.",
                "visual_subject": "A concrete model comparison on two workstations.",
                "inventory_overlap": "gap",
                "verdict": "PASS",
            }
        }

        result = traffic_gate.evaluate_candidate(
            candidate, source_velocity=velocity
        )

        self.assertTrue(result["editorial_breakout_verified"])
        self.assertTrue(result["eligible"])
        self.assertFalse(result["hot_label_eligible"])

    def test_unverified_editorial_breakout_is_vetoed(self):
        candidate = valid_candidate(
            outcome_lane="Discover-first",
            trend_class="EVERGREEN_SEARCH",
            editorial_signal="EDITORIAL_BREAKOUT",
        )
        candidate["demand_signals"][1]["provider"] = "current_event"

        result = traffic_gate.evaluate_candidate(candidate)

        self.assertFalse(result["eligible"])
        self.assertIn("unverified_editorial_breakout", result["vetoes"])

    def test_rising_search_requires_compared_period_evidence(self):
        candidate = valid_candidate(trend_class="RISING_SEARCH")

        result = traffic_gate.evaluate_candidate(candidate)

        self.assertFalse(result["eligible"])
        self.assertIn("unverified_rising_search_label", result["vetoes"])

        candidate["demand_signals"][1]["metrics"]["growth_pct"] = 42
        result = traffic_gate.evaluate_candidate(candidate)
        self.assertNotIn("unverified_rising_search_label", result["vetoes"])
        self.assertEqual(
            result["score_breakdown"]["trend_velocity"]["classification_cap"],
            75,
        )

    def test_news_route_is_a_hard_veto(self):
        result = evaluate_with_snapshot(
            valid_candidate(section="news", slug="/news/forbidden")
        )

        self.assertFalse(result["eligible"])
        self.assertFalse(result["hot_label_eligible"])
        self.assertIn("automatic_news_route", result["vetoes"])


class PortfolioSelectionTests(unittest.TestCase):
    def provisional_priors(
        self,
        *,
        activated_at="2026-07-29T00:00:00Z",
        expires_at="2099-08-06T10:00:00Z",
    ):
        priors = {
            "contract_version": "performance-learning-provisional-v1",
            "generated_at": NOW_ISO,
            "source_execution_id": "48h-test",
            "source_snapshot_fingerprint": "source",
            "status": "ACTIVE",
            "priors": [
                {
                    "prior_id": "candidate-prior-preferred",
                    "state": "ACTIVE",
                    "learning_level": "CANDIDATE_PRIOR",
                    "scope_type": "cluster_id",
                    "scope_value": "preferred-cluster",
                    "selection_adjustment": 1,
                    "activated_at": activated_at,
                    "expires_at": expires_at,
                    "evidence": {
                        "source_checkpoint": "72h",
                        "article_count": 3,
                        "publication_run_count": 2,
                    },
                }
            ],
        }
        priors["snapshot_fingerprint"] = traffic_gate._snapshot_fingerprint(priors)
        return priors

    def test_durable_prior_reorders_only_already_eligible_candidates(self):
        snapshot = realtime_snapshot()
        first = valid_candidate(
            candidate_id="first",
            slug="first",
            intent_key="first-intent",
            cluster_id="neutral-cluster",
        )
        second = valid_candidate(
            candidate_id="second",
            slug="second",
            intent_key="second-intent",
            cluster_id="preferred-cluster",
        )
        for candidate in (first, second):
            candidate["publication_run_id"] = snapshot["run_id"]
            candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
                "snapshot_fingerprint"
            ]
        priors = {
            "contract_version": "performance-learning-v1",
            "generated_at": NOW_ISO,
            "source_execution_id": "weekly-test",
            "source_snapshot_fingerprint": "source",
            "status": "ACTIVE",
            "priors": [
                {
                    "prior_id": "prior-preferred",
                    "state": "ACTIVE",
                    "learning_level": "DURABLE_PRIOR",
                    "scope_type": "cluster_id",
                    "scope_value": "preferred-cluster",
                    "selection_adjustment": 3,
                    "evidence": {
                        "d28_article_count": 3,
                        "publication_run_count": 2,
                        "verified_experiment_count": 0,
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
        priors["snapshot_fingerprint"] = traffic_gate._snapshot_fingerprint(priors)

        portfolio = traffic_gate.select_portfolio(
            [first, second],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            learning_priors=priors,
        )

        self.assertEqual(portfolio["selected"][0]["candidate_id"], "second")
        self.assertEqual(portfolio["selected"][0]["learning_adjustment"], 3)
        self.assertTrue(portfolio["selected"][0]["eligible"])
        self.assertFalse(portfolio["selected"][0]["learning_can_change_eligibility"])

    def test_durable_prior_cannot_make_vetoed_candidate_eligible(self):
        snapshot = realtime_snapshot()
        candidate = valid_candidate(
            cluster_id="preferred-cluster",
            vetoes=["forced_brand_insertion"],
        )
        candidate["publication_run_id"] = snapshot["run_id"]
        candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
            "snapshot_fingerprint"
        ]
        priors = {
            "contract_version": "performance-learning-v1",
            "status": "ACTIVE",
            "priors": [
                {
                    "prior_id": "prior-preferred",
                    "state": "ACTIVE",
                    "learning_level": "DURABLE_PRIOR",
                    "scope_type": "cluster_id",
                    "scope_value": "preferred-cluster",
                    "selection_adjustment": 3,
                    "evidence": {
                        "d28_article_count": 3,
                        "publication_run_count": 2,
                        "verified_experiment_count": 0,
                    },
                }
            ],
        }
        priors["snapshot_fingerprint"] = traffic_gate._snapshot_fingerprint(priors)

        portfolio = traffic_gate.select_portfolio(
            [candidate],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            learning_priors=priors,
        )

        self.assertEqual(portfolio["selected"], [])
        rejected = portfolio["rejected"][0]
        self.assertIn("forced_brand_insertion", rejected["vetoes"])
        self.assertEqual(rejected["learning_adjustment"], 0)
        self.assertEqual(rejected["selection_priority_score"], rejected["score"])
        self.assertEqual(rejected["matched_learning_priors"], [])

    def test_provisional_prior_is_not_applied_to_ineligible_candidate(self):
        snapshot = realtime_snapshot()
        candidate = valid_candidate(
            cluster_id="preferred-cluster",
            vetoes=["forced_brand_insertion"],
        )
        candidate["publication_run_id"] = snapshot["run_id"]
        candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
            "snapshot_fingerprint"
        ]

        portfolio = traffic_gate.select_portfolio(
            [candidate],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            provisional_learning_priors=self.provisional_priors(),
        )

        rejected = portfolio["rejected"][0]
        self.assertEqual(rejected["learning_adjustment"], 0)
        self.assertEqual(rejected["selection_priority_score"], rejected["score"])
        self.assertEqual(rejected["matched_provisional_priors"], [])

    def test_provisional_prior_reorders_only_already_eligible_candidates(self):
        snapshot = realtime_snapshot()
        first = valid_candidate(
            candidate_id="first",
            slug="first",
            intent_key="first-intent",
            cluster_id="neutral-cluster",
        )
        second = valid_candidate(
            candidate_id="second",
            slug="second",
            intent_key="second-intent",
            cluster_id="preferred-cluster",
        )
        for candidate in (first, second):
            candidate["publication_run_id"] = snapshot["run_id"]
            candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
                "snapshot_fingerprint"
            ]

        portfolio = traffic_gate.select_portfolio(
            [first, second],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            provisional_learning_priors=self.provisional_priors(),
        )

        selected = portfolio["selected"][0]
        self.assertEqual(selected["candidate_id"], "second")
        self.assertEqual(selected["learning_adjustment"], 1)
        self.assertEqual(
            selected["matched_provisional_priors"],
            ["candidate-prior-preferred"],
        )
        self.assertTrue(selected["eligible"])
        self.assertFalse(selected["learning_can_change_eligibility"])

    def test_expired_provisional_prior_is_ignored(self):
        snapshot = realtime_snapshot()
        candidate = valid_candidate(cluster_id="preferred-cluster")
        candidate["publication_run_id"] = snapshot["run_id"]
        candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
            "snapshot_fingerprint"
        ]

        portfolio = traffic_gate.select_portfolio(
            [candidate],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            provisional_learning_priors=self.provisional_priors(
                activated_at="2026-07-20T10:00:00Z",
                expires_at="2026-07-28T10:00:00Z"
            ),
        )

        selected = portfolio["selected"][0]
        self.assertEqual(selected["learning_adjustment"], 0)
        self.assertEqual(selected["matched_provisional_priors"], [])
        self.assertEqual(
            portfolio["provisional_learning_prior_summary"][
                "expired_priors_ignored"
            ],
            1,
        )

    def test_provisional_layer_is_capped_to_two_points(self):
        snapshot = realtime_snapshot()
        candidate = valid_candidate(
            cluster_id="preferred-cluster",
            section="guides",
        )
        candidate["publication_run_id"] = snapshot["run_id"]
        candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
            "snapshot_fingerprint"
        ]
        priors = self.provisional_priors()
        for prior in priors["priors"]:
            prior["selection_adjustment"] = 2
            prior["evidence"]["source_checkpoint"] = "7d"
            prior["evidence"]["article_count"] = 2
        section_prior = dict(priors["priors"][0])
        section_prior["prior_id"] = "candidate-prior-guides"
        section_prior["scope_type"] = "section"
        section_prior["scope_value"] = "guides"
        section_prior["evidence"] = dict(section_prior["evidence"])
        priors["priors"].append(section_prior)
        priors["snapshot_fingerprint"] = traffic_gate._snapshot_fingerprint(priors)

        portfolio = traffic_gate.select_portfolio(
            [candidate],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            provisional_learning_priors=priors,
        )

        selected = portfolio["selected"][0]
        self.assertEqual(selected["provisional_learning_adjustment"], 2)
        self.assertEqual(selected["learning_adjustment"], 2)
        self.assertEqual(len(selected["matched_provisional_priors"]), 2)

    def test_d2tr_context_reorders_only_already_eligible_candidates(self):
        snapshot = realtime_snapshot()
        first = valid_candidate(
            candidate_id="first",
            slug="first",
            intent_key="first-intent",
        )
        second = valid_candidate(
            candidate_id="second",
            slug="second",
            intent_key="second-intent",
            d2tr_context={
                "market": "US",
                "topic_category": "Travel",
                "format_group": "Service",
            },
        )
        for candidate in (first, second):
            candidate["publication_run_id"] = snapshot["run_id"]
            candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
                "snapshot_fingerprint"
            ]

        portfolio = traffic_gate.select_portfolio(
            [first, second],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            d2tr_market_context=d2tr_context(),
        )

        selected = portfolio["selected"][0]
        self.assertEqual(selected["candidate_id"], "second")
        self.assertEqual(selected["d2tr_market_context_adjustment_raw"], 2)
        self.assertEqual(selected["d2tr_market_context_adjustment_applied"], 2)
        self.assertEqual(selected["total_priority_adjustment"], 2)
        self.assertEqual(selected["score"], selected["raw_score"])
        self.assertTrue(selected["eligible"])
        self.assertFalse(portfolio["hard_boundaries"]["d2tr_can_create_demand"])

    def test_d2tr_context_cannot_rescue_vetoed_candidate(self):
        snapshot = realtime_snapshot()
        candidate = valid_candidate(
            vetoes=["forced_brand_insertion"],
            d2tr_context={
                "market": "US",
                "topic_category": "Travel",
                "format_group": "Service",
            },
        )
        candidate["publication_run_id"] = snapshot["run_id"]
        candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
            "snapshot_fingerprint"
        ]

        portfolio = traffic_gate.select_portfolio(
            [candidate],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            d2tr_market_context=d2tr_context(),
        )

        rejected = portfolio["rejected"][0]
        self.assertFalse(rejected["eligible"])
        self.assertEqual(rejected["d2tr_market_context_adjustment_raw"], 0)
        self.assertEqual(rejected["selection_priority_score"], rejected["score"])

    def test_learning_and_d2tr_share_one_three_point_cap(self):
        snapshot = realtime_snapshot()
        candidate = valid_candidate(
            cluster_id="preferred-cluster",
            d2tr_context={
                "market": "US",
                "topic_category": "Travel",
                "format_group": "Service",
            },
        )
        candidate["publication_run_id"] = snapshot["run_id"]
        candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
            "snapshot_fingerprint"
        ]
        priors = {
            "contract_version": "performance-learning-v1",
            "status": "ACTIVE",
            "priors": [
                {
                    "prior_id": "prior-preferred",
                    "state": "ACTIVE",
                    "learning_level": "DURABLE_PRIOR",
                    "scope_type": "cluster_id",
                    "scope_value": "preferred-cluster",
                    "selection_adjustment": 3,
                    "evidence": {
                        "d28_article_count": 3,
                        "publication_run_count": 2,
                        "verified_experiment_count": 0,
                    },
                }
            ],
        }
        priors["snapshot_fingerprint"] = traffic_gate._snapshot_fingerprint(priors)

        portfolio = traffic_gate.select_portfolio(
            [candidate],
            max_articles=1,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
            learning_priors=priors,
            d2tr_market_context=d2tr_context(),
        )

        selected = portfolio["selected"][0]
        self.assertEqual(selected["learning_adjustment"], 3)
        self.assertEqual(selected["d2tr_market_context_adjustment_raw"], 2)
        self.assertEqual(selected["d2tr_market_context_adjustment_applied"], 0)
        self.assertEqual(selected["total_priority_adjustment"], 3)

    def test_portfolio_respects_ceiling_entity_cap_and_no_topic_slots(self):
        candidates = []
        for index in range(6):
            candidate = valid_candidate(
                candidate_id=f"candidate-{index}",
                slug=f"candidate-{index}",
                intent_key=f"intent-{index}",
                entities=["same entity"] if index < 4 else [f"entity-{index}"],
            )
            candidate["dimension_evidence"]["historical_fit"]["score_100"] = 95 - index
            candidates.append(candidate)

        snapshot = realtime_snapshot()
        for candidate in candidates:
            candidate["demand_signals"][1]["metrics"]["snapshot_fingerprint"] = snapshot[
                "snapshot_fingerprint"
            ]
        portfolio = traffic_gate.select_portfolio(
            candidates,
            max_articles=5,
            realtime_trends_snapshot=snapshot,
            live_source_verifications=live_verifications(snapshot),
        )

        self.assertLessEqual(len(portfolio["selected"]), 5)
        self.assertLessEqual(
            sum("same entity" in row["entities"] for row in portfolio["selected"]), 3
        )
        self.assertEqual(
            portfolio["no_topic_slots"], 5 - len(portfolio["selected"])
        )

    def test_portfolio_rejects_hot_candidate_without_snapshot(self):
        portfolio = traffic_gate.select_portfolio([valid_candidate()], max_articles=1)

        self.assertEqual(portfolio["selected"], [])
        self.assertIn(
            "unverified_realtime_hot_label",
            portfolio["rejected"][0]["vetoes"],
        )
        self.assertFalse(
            portfolio["hard_boundaries"]["realtime_hot_reconciled_to_snapshot"]
        )

    def test_derivative_artifact_contents_must_match_snapshot(self):
        snapshot = realtime_snapshot()
        market_map = {
            "contract_version": "realtime-trends-v1",
            "run_id": snapshot["run_id"],
            "snapshot_fingerprint": snapshot["snapshot_fingerprint"],
            "observed_at": snapshot["observed_at"],
            "status": snapshot["status"],
            "markets": [],
        }
        traffic_gate._validate_snapshot_derivative(
            market_map,
            snapshot,
            expected_contract="realtime-trends-v1",
        )
        market_map["markets"].append({"geo": "FORGED"})
        with self.assertRaisesRegex(ValueError, "contents do not match"):
            traffic_gate._validate_snapshot_derivative(
                market_map,
                snapshot,
                expected_contract="realtime-trends-v1",
            )


class CheckpointClassificationTests(unittest.TestCase):
    def test_page_one_low_ctr_becomes_search_ctr_opportunity(self):
        checkpoint = {
            "data_maturity": "MATURE",
            "gsc": {
                "search": {
                    "impressions": 1057,
                    "clicks": 21,
                    "ctr": 0.0199,
                    "average_position": 8.74,
                },
                "discover": {"impressions": None, "clicks": None, "ctr": None},
            },
            "benchmarks": {"search_ctr": 0.04, "discover_ctr": 0.03},
        }

        result = traffic_gate.classify_72h(checkpoint)

        self.assertEqual(result["classification"], "SEARCH_CTR_OPPORTUNITY")
        self.assertEqual(result["recommended_variable"], "title")
        self.assertEqual(result["benchmark_source"], "provided")

    def test_discover_low_ctr_becomes_packaging_opportunity(self):
        checkpoint = {
            "data_maturity": "MATURE",
            "gsc": {
                "search": {"impressions": 0, "clicks": 0, "ctr": None},
                "discover": {"impressions": 1000, "clicks": 10, "ctr": 0.01},
            },
            "benchmarks": {"discover_ctr": 0.03},
        }

        result = traffic_gate.classify_72h(checkpoint)

        self.assertEqual(result["classification"], "DISCOVER_PACKAGING_OPPORTUNITY")
        self.assertEqual(result["recommended_variable"], "hero_or_title")

    def test_below_gate_mature_page_has_no_mature_signal(self):
        checkpoint = {
            "data_maturity": "MATURE",
            "gsc": {
                "search": {"impressions": 50, "clicks": 1, "ctr": 0.02},
                "discover": {"impressions": 100, "clicks": 2, "ctr": 0.02},
            },
            "benchmarks": {"search_ctr": 0.04, "discover_ctr": 0.03},
        }

        result = traffic_gate.classify_72h(checkpoint)

        self.assertEqual(result["classification"], "NO_MATURE_SIGNAL")
        self.assertIsNone(result["recommended_variable"])

    def test_default_benchmark_source_is_explicit(self):
        checkpoint = {
            "data_maturity": "MATURE",
            "gsc": {
                "search": {
                    "impressions": 200,
                    "clicks": 1,
                    "ctr": 0.005,
                    "average_position": 7,
                },
                "discover": {},
            },
        }

        result = traffic_gate.classify_72h(checkpoint)

        self.assertEqual(result["benchmark_source"], "configured_default")


if __name__ == "__main__":
    unittest.main()

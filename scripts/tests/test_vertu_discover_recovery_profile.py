import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "vertu_discover_recovery_profile.py"
SPEC = importlib.util.spec_from_file_location("recovery", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def pulse(clicks=-71.19, impressions=-68.84):
    return {
        "contract_version": "discover-pulse-v1",
        "publication_run_id": "run-1",
        "latest_finalised_metric_date": "2026-08-28",
        "comparisons": {"7d": {"change_pct": {"clicks": clicks, "impressions": impressions, "ctr": -7.54}}},
        "category_14d_vs_previous": [
            {"category": "comparison_other", "current_clicks": 16000, "click_change_pct": -20},
            {"category": "phones_ai_and_security", "current_clicks": 1300, "click_change_pct": -55},
            {"category": "commercial_aviation_and_airport", "current_clicks": 1400, "click_change_pct": -93},
        ],
    }


def test_active_profile_has_zero_gate_authority():
    result = MODULE.build_profile(
        pulse(), "user-message-2026-08-31", "2026-08-31T02:00:00Z", "2026-09-07T02:00:00Z"
    )
    assert result["state"] == "ACTIVE"
    assert result["authority"]["candidate_generation"] is True
    for key in ("search_demand", "raw_score", "trend_class", "eligibility", "veto_relief", "qa", "publication", "learned_prior"):
        assert result["authority"][key] is False
    assert result["candidate_pool_contract"]["resilient_observed_categories"] == [
        "comparison_other",
        "phones_ai_and_security",
    ]
    assert result["candidate_pool_contract"]["cooldown_observed_categories"] == [
        "commercial_aviation_and_airport"
    ]
    assert len(result["fingerprint"]) == 64


def test_profile_is_inactive_without_material_drop():
    result = MODULE.build_profile(
        pulse(-20, -25), "user-message-2026-08-31", "2026-08-31T02:00:00Z", "2026-09-07T02:00:00Z"
    )
    assert result["state"] == "INACTIVE"
    assert result["authority"]["candidate_generation"] is False


def test_expiry_cannot_exceed_seven_days():
    with pytest.raises(ValueError, match="seven days"):
        MODULE.build_profile(
            pulse(), "user-message-2026-08-31", "2026-08-31T02:00:00Z", "2026-09-08T02:00:01Z"
        )


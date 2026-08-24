import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_daily_publishing_quota.py"
SPEC = importlib.util.spec_from_file_location("vertu_daily_publishing_quota", MODULE_PATH)
quota = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(quota)


def state(**overrides):
    payload = {
        "contract_version": "daily-publishing-quota-v1",
        "execution_id": "vertu-10-2026-08-10T01:01:55.664Z",
        "required_publish_count": 10,
        "max_articles": 10,
        "expansion_targets": [30, 60, 90, 120],
        "current_candidate_target": 30,
        "eligible_article_keys": [f"article-{i}" for i in range(10)],
        "selected_article_keys": [f"article-{i}" for i in range(10)],
        "live_verified_article_keys": [],
        "blocked_articles": [],
        "gates_preserved": True,
    }
    payload.update(overrides)
    return payload


class DailyPublishingQuotaTests(unittest.TestCase):
    def test_complete_requires_ten_live_verified_articles(self):
        result = quota.evaluate_quota_state(
            state(live_verified_article_keys=[f"article-{i}" for i in range(10)])
        )
        self.assertEqual(result["state"], "COMPLETE")
        self.assertEqual(result["next_action"], "TERMINALISE_SUCCESS")

    def test_initial_shortfall_requires_expansion(self):
        keys = [f"article-{i}" for i in range(7)]
        result = quota.evaluate_quota_state(
            state(eligible_article_keys=keys, selected_article_keys=keys)
        )
        self.assertEqual(result["state"], "EXPAND_REQUIRED")
        self.assertEqual(result["next_candidate_target"], 60)

    def test_downstream_blocker_requires_replacement(self):
        result = quota.evaluate_quota_state(
            state(
                live_verified_article_keys=[f"article-{i}" for i in range(9)],
                blocked_articles=[
                    {"article_key": "article-9", "stage": "QA", "reason": "BLOCK"}
                ],
            )
        )
        self.assertEqual(result["state"], "REPLACEMENT_REQUIRED")
        self.assertEqual(result["live_verified_count"], 9)

    def test_exhausted_pool_returns_daily_quota_blocker(self):
        keys = [f"article-{i}" for i in range(9)]
        result = quota.evaluate_quota_state(
            state(
                current_candidate_target=120,
                eligible_article_keys=keys,
                selected_article_keys=keys,
            )
        )
        self.assertEqual(result["state"], "DAILY_QUOTA_BLOCKED")
        self.assertEqual(result["next_candidate_target"], None)

    def test_selected_articles_must_remain_eligible(self):
        with self.assertRaises(quota.QuotaStateError):
            quota.evaluate_quota_state(
                state(
                    eligible_article_keys=["article-0"],
                    selected_article_keys=["article-0", "article-1"],
                )
            )

    def test_gate_waiver_is_invalid(self):
        with self.assertRaises(quota.QuotaStateError):
            quota.evaluate_quota_state(state(gates_preserved=False))

    def test_ten_selected_are_not_success(self):
        result = quota.evaluate_quota_state(state())
        self.assertEqual(result["state"], "PRODUCTION_IN_PROGRESS")


if __name__ == "__main__":
    unittest.main()

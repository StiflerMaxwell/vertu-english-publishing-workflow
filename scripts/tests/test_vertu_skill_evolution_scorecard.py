import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_skill_evolution_scorecard.py"
SPEC = importlib.util.spec_from_file_location("vertu_skill_evolution_scorecard", MODULE_PATH)
scorecard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(scorecard)


def dimensions(weights, score=80):
    return {
        key: {"score": score, "evidence": [f"evidence/{key}.json"]}
        for key in weights
    }


def completed_pair(verdicts):
    return {
        "status": "COMPLETED",
        "rubric_fingerprint": "rubric-sha256-test",
        "judges": [
            {
                "judge_id": f"judge-{index}",
                "verdict": verdict,
                "evidence": [f"paired/judge-{index}.json"],
            }
            for index, verdict in enumerate(verdicts, start=1)
        ],
    }


def replay(status="PASS", regressions=None):
    return {
        "status": status,
        "dataset_fingerprint": "replay-sha256-test",
        "candidate_count": 30,
        "holdout_count": 10,
        "gate_regressions": regressions or [],
        "evidence": ["replay/summary.json"],
    }


def production(level="NOT_MATURE", score=80):
    row = {
        "level": level,
        "article_count": 0,
        "publication_run_count": 0,
    }
    if level == "DURABLE_28D":
        row.update(
            {
                "article_count": 3,
                "publication_run_count": 2,
                "evidence": ["performance/d28-cohort.json"],
                "dimensions": dimensions(scorecard.OUTCOME_WEIGHTS, score),
            }
        )
    elif level == "VERIFIED_EXPERIMENT":
        row.update(
            {
                "article_count": 1,
                "publication_run_count": 1,
                "verified_experiment_id": "experiment-001",
                "evidence": ["experiments/experiment-001.json"],
                "dimensions": dimensions(scorecard.OUTCOME_WEIGHTS, score),
            }
        )
    return row


def payload():
    return {
        "contract_version": scorecard.INPUT_CONTRACT,
        "change_id": "change-test-001",
        "execution_id": "execution-test-001",
        "change_class": "STRUCTURAL_RULE",
        "affects_traffic_decisions": True,
        "skill": {
            "before_version": "3.8.1",
            "after_version": "3.9.0",
            "before_path": "skill-before/SKILL.md",
            "after_path": "skill-after/SKILL.md",
        },
        "diagnostic": dimensions(scorecard.DIAGNOSTIC_WEIGHTS, 80),
        "paired_review": completed_pair(
            ["AFTER_BETTER", "AFTER_BETTER", "BEFORE_BETTER"]
        ),
        "replay": replay(),
        "production_evidence": production("DURABLE_28D", 80),
    }


class SkillEvolutionScorecardTests(unittest.TestCase):
    def build(self, value):
        return scorecard.build_scorecard(value, observed_at="2026-08-03T08:00:00Z")

    def test_weighted_diagnostic_score_is_separate_and_triage_only(self):
        value = payload()
        value["diagnostic"] = dimensions(scorecard.DIAGNOSTIC_WEIGHTS, 80)

        result = self.build(value)

        self.assertEqual(result["structural_diagnostic"]["score"], 80.0)
        self.assertTrue(result["structural_diagnostic"]["triage_only"])
        self.assertEqual(result["release"]["decision"], "PROMOTION_ELIGIBLE")

    def test_absolute_score_cannot_replace_paired_comparison(self):
        value = payload()
        value["diagnostic"] = dimensions(scorecard.DIAGNOSTIC_WEIGHTS, 100)
        value["paired_review"] = {"status": "NOT_RUN"}

        result = self.build(value)

        self.assertEqual(result["structural_diagnostic"]["score"], 100.0)
        self.assertEqual(result["release"]["decision"], "MANUAL_REVIEW")

    def test_before_version_majority_requires_revert(self):
        value = payload()
        value["paired_review"] = completed_pair(
            ["BEFORE_BETTER", "BEFORE_BETTER", "AFTER_BETTER"]
        )

        result = self.build(value)

        self.assertEqual(result["paired_review"]["verdict"], "BEFORE_BETTER")
        self.assertEqual(result["release"]["decision"], "REVERT_REQUIRED")

    def test_positive_72h_signal_remains_pending_maturity(self):
        value = payload()
        value["production_evidence"] = production("NOT_MATURE")
        value["production_evidence"]["level"] = "OBSERVATION_72H"

        result = self.build(value)

        self.assertIsNone(result["production_outcome"]["outcome_score"])
        self.assertEqual(result["release"]["decision"], "PENDING_MATURITY")

    def test_durable_outcome_below_promotion_threshold_requires_review(self):
        value = payload()
        value["production_evidence"] = production("DURABLE_28D", 70)

        result = self.build(value)

        self.assertEqual(result["production_outcome"]["outcome_score"], 70.0)
        self.assertEqual(result["release"]["decision"], "MANUAL_REVIEW")

    def test_replay_gate_regression_overrides_high_scores(self):
        value = payload()
        value["diagnostic"] = dimensions(scorecard.DIAGNOSTIC_WEIGHTS, 100)
        value["production_evidence"] = production("DURABLE_28D", 100)
        value["replay"] = replay(regressions=["NON_NEWS_ROUTING_REGRESSION"])

        result = self.build(value)

        self.assertEqual(result["release"]["decision"], "REVERT_REQUIRED")
        self.assertIn("REPLAY_GATE_REGRESSION", result["release"]["reasons"])

    def test_even_judge_count_is_rejected(self):
        value = payload()
        value["paired_review"] = completed_pair(
            ["AFTER_BETTER", "AFTER_BETTER", "BEFORE_BETTER", "TIE"]
        )

        with self.assertRaisesRegex(scorecard.ScorecardError, "odd number"):
            self.build(value)

    def test_duplicate_judge_ids_are_rejected(self):
        value = payload()
        value["paired_review"] = completed_pair(
            ["AFTER_BETTER", "AFTER_BETTER", "BEFORE_BETTER"]
        )
        value["paired_review"]["judges"][2]["judge_id"] = "judge-1"

        with self.assertRaisesRegex(scorecard.ScorecardError, "unique judge IDs"):
            self.build(value)

    def test_approved_governance_bootstrap_can_implement_without_traffic_claim(self):
        value = payload()
        value.update(
            {
                "change_class": "GOVERNANCE_INFRASTRUCTURE",
                "affects_traffic_decisions": False,
                "approval_reference": "user-approval-2026-08-03",
                "paired_review": {"status": "NOT_REQUIRED"},
                "production_evidence": production("NOT_MATURE"),
            }
        )

        result = self.build(value)

        self.assertEqual(result["release"]["decision"], "IMPLEMENTED_BY_APPROVAL")
        self.assertFalse(result["production_outcome"]["required"])
        self.assertEqual(
            result["release"]["activation_authority"], "MANUAL_APPROVAL_REQUIRED"
        )

    def test_durable_28d_requires_three_articles_across_two_runs(self):
        value = payload()
        value["production_evidence"] = production("DURABLE_28D", 80)
        value["production_evidence"]["publication_run_count"] = 1

        with self.assertRaisesRegex(scorecard.ScorecardError, "three articles"):
            self.build(value)


if __name__ == "__main__":
    unittest.main()

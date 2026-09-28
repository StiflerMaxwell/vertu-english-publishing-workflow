import importlib.util
import json
import pathlib
import tempfile
import unittest
from argparse import Namespace


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_factor_score_paired_trial.py"
SPEC = importlib.util.spec_from_file_location("vertu_factor_score_paired_trial", MODULE_PATH)
trial = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(trial)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def score_output(mode="legacy", fingerprint="pool-1", selected_ids=("A", "B")):
    source = (
        trial.CONTROL_SCORE_SOURCE
        if mode == trial.CONTROL_MODE
        else trial.CHALLENGER_SCORE_SOURCE
    )
    selected = []
    for index, candidate_id in enumerate(selected_ids):
        score = 90 - index
        selected.append(
            {
                "candidate_id": candidate_id,
                "title": f"Title {candidate_id}",
                "eligible": True,
                "score": score,
                "legacy_score": score if mode == "legacy" else score + 1,
                "hybrid_score": None if mode == "legacy" else score,
                "hybrid_factor_component": {
                    "coverage_weight_pct": 50,
                    "effective_factor_score": 70,
                },
            }
        )
    return {
        "factor_score_mode": mode,
        "score_source": source,
        "candidate_pool_fingerprint": fingerprint,
        "candidate_count": 30,
        "trend_mode": "realtime_hot",
        "selected": selected,
        "no_topic_slots": 0,
        "direct_factor_model_summary": {"production_decisions_affected": 0},
    }


class PairedTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.config = self.root / "config.json"
        trial.initialise_config(
            Namespace(
                output=self.config,
                trial_id="factor-trial-test",
                observed_at="2026-08-25T08:00:00Z",
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    def register(self, run_id, selected_ids=("A", "B"), fingerprint="pool-1"):
        run = self.root / run_id
        legacy = run / "legacy.json"
        hybrid = run / "hybrid.json"
        output = run / "factor-score-paired-trial.json"
        write_json(legacy, score_output("legacy", fingerprint, selected_ids))
        write_json(
            hybrid,
            score_output("hybrid_trial", fingerprint, tuple(reversed(selected_ids))),
        )
        return trial.register_pair(
            Namespace(
                config=self.config,
                legacy=legacy,
                hybrid=hybrid,
                publication_run_id=run_id,
                observed_at="2026-08-25T08:05:00Z",
                registry_root=self.root,
                output=output,
            )
        )

    def test_registers_control_and_challenger_without_changing_authority(self):
        result = self.register("run-1")

        self.assertEqual(result["status"], "REGISTERED")
        self.assertEqual(result["slot"], 1)
        self.assertEqual(result["publication_authority"], "CONTROL_ONLY")
        self.assertFalse(result["challenger_can_publish"])
        self.assertFalse(result["comparison"]["selected_order_equal"])
        self.assertTrue(result["comparison"]["selected_set_equal"])

    def test_retry_reconciles_the_same_slot(self):
        first = self.register("run-1")
        second = self.register("run-1")

        self.assertEqual(first["slot"], 1)
        self.assertEqual(second["status"], "ALREADY_REGISTERED")
        self.assertEqual(second["slot"], 1)

    def test_third_unique_run_is_not_registered(self):
        self.register("run-1")
        self.register("run-2")
        third = self.register("run-3")

        self.assertEqual(third["status"], "TRIAL_CAP_REACHED")
        self.assertEqual(third["requested_production_mutations"], 0)

    def test_candidate_pool_mismatch_fails_closed(self):
        run = self.root / "run-bad"
        legacy = run / "legacy.json"
        hybrid = run / "hybrid.json"
        write_json(legacy, score_output("legacy", "pool-a"))
        write_json(hybrid, score_output("hybrid_trial", "pool-b"))

        with self.assertRaisesRegex(trial.TrialError, "candidate_pool_fingerprint mismatch"):
            trial.register_pair(
                Namespace(
                    config=self.config,
                    legacy=legacy,
                    hybrid=hybrid,
                    publication_run_id="run-bad",
                    observed_at="2026-08-25T08:05:00Z",
                    registry_root=self.root,
                    output=run / "factor-score-paired-trial.json",
                )
            )


if __name__ == "__main__":
    unittest.main()

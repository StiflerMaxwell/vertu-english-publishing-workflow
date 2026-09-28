from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "vertu_skill_evolution_factors.py"
SPEC = importlib.util.spec_from_file_location("vertu_skill_evolution_factors", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SkillEvolutionFactorVectorTests(unittest.TestCase):
    def snapshot(self, root: pathlib.Path) -> pathlib.Path:
        payload = {
            "contract_version": "performance-learning-v1",
            "execution_id": "learning-1",
            "generated_at": "2026-08-25T02:30:00Z",
            "accepted_checkpoint_count": 4,
            "rejected_checkpoint_count": 6,
            "rejected_by_reason": {
                "DATA_NOT_MATURE": 1,
                "SOURCE_BLOCKED": 1,
                "SUPERSEDED_RETRY": 2,
                "UNSUPPORTED_CHECKPOINT": 2,
            },
            "learning_context_completeness": {
                "complete": 3,
                "with_publication_run_id": 4,
            },
            "checkpoints": [
                {"executed_at": "2026-08-25T01:30:00Z"},
                {"executed_at": "2026-08-24T01:30:00Z"},
            ],
        }
        payload["snapshot_fingerprint"] = MODULE.fingerprint(payload)
        path = root / "learning-snapshot.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def input(self, snapshot: pathlib.Path) -> dict:
        return {
            "contract_version": MODULE.INPUT_CONTRACT,
            "execution_id": "skill-factor-1",
            "observed_at": "2026-08-25T02:30:00Z",
            "learning_snapshot_path": str(snapshot),
            "change": {
                "change_id": "change-1",
                "before_version": "3.15.1",
                "after_version": "3.16.0",
                "hypothesis": {
                    "maturity_windows": ["runtime", "28d"],
                    "target_factors": [
                        {"factor_id": "F32", "expected_direction": "INCREASE", "threshold": 0.0}
                    ],
                    "guardrail_factors": [
                        {"factor_id": "F59", "expected_direction": "NO_HARM", "threshold": 0.0}
                    ],
                },
            },
            "measurements": {
                "F32": {
                    "status": "AVAILABLE",
                    "value": 1,
                    "unit": "ratio",
                    "source_refs": ["spec://change-1"],
                    "status_reason": "All material changes declare a hypothesis.",
                }
            },
            "default_statuses": {
                "F15": "SOURCE_UNAVAILABLE",
                "F16": "SOURCE_UNAVAILABLE",
                "F25": "NOT_APPLICABLE",
            },
        }

    def evaluation_context(
        self,
        vector: dict,
        *,
        window: str = "runtime",
        affects_traffic: bool = False,
        production_level: str = "NOT_REQUIRED",
        activation_state: str = "PROPOSED",
    ) -> dict:
        return {
            "contract_version": MODULE.EVALUATION_INPUT_CONTRACT,
            "change_id": vector["change_id"],
            "execution_id": vector["execution_id"],
            "vector_fingerprint": vector["vector_fingerprint"],
            "before_version": vector["before_version"],
            "after_version": vector["after_version"],
            "observed_at": vector["observed_at"],
            "evaluation_window": window,
            "activation_state": activation_state,
            "affects_traffic_decisions": affects_traffic,
            "production_level": production_level,
            "evidence_refs": ["evidence://factor-evaluation"],
        }

    def configured_vector(
        self,
        root: pathlib.Path,
        *,
        target: str,
        target_value: float | None,
        target_status: str = "AVAILABLE",
        target_threshold: float = 0.0,
        guardrail: str,
        guardrail_value: float | None,
        guardrail_status: str = "AVAILABLE",
        guardrail_threshold: float = 0.0,
        windows: list[str],
    ) -> dict:
        payload = self.input(self.snapshot(root))
        payload["change"]["hypothesis"] = {
            "maturity_windows": windows,
            "target_factors": [
                {
                    "factor_id": target,
                    "expected_direction": "INCREASE",
                    "threshold": target_threshold,
                }
            ],
            "guardrail_factors": [
                {
                    "factor_id": guardrail,
                    "expected_direction": "NO_HARM",
                    "threshold": guardrail_threshold,
                }
            ],
        }
        payload["measurements"] = {
            target: {
                "status": target_status,
                "value": target_value,
                "unit": MODULE.FACTOR_BY_ID[target].unit,
                "source_refs": [f"evidence://{target}"],
                "status_reason": "Target test measurement.",
            },
            guardrail: {
                "status": guardrail_status,
                "value": guardrail_value,
                "unit": MODULE.FACTOR_BY_ID[guardrail].unit,
                "source_refs": [f"evidence://{guardrail}"],
                "status_reason": "Guardrail test measurement.",
            },
        }
        return MODULE.build_vector(payload)

    def test_registry_contains_exactly_sixty_unique_factors(self):
        self.assertEqual(len(MODULE.FACTORS), 60)
        self.assertEqual(len({factor.factor_id for factor in MODULE.FACTORS}), 60)
        self.assertEqual(MODULE.FACTORS[0].factor_id, "F01")
        self.assertEqual(MODULE.FACTORS[-1].factor_id, "F60")

    def test_builds_complete_vector_and_derives_snapshot_factors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            vector = MODULE.build_vector(self.input(self.snapshot(root)))
        rows = {row["factor_id"]: row for row in vector["factors"]}
        self.assertEqual(vector["factor_count"], 60)
        self.assertFalse(vector["global_score_allowed"])
        self.assertNotIn("total_score", vector)
        self.assertAlmostEqual(rows["F34"]["value"], 4 / 6, places=6)
        self.assertEqual(rows["F35"]["value"], 0.75)
        self.assertEqual(rows["F36"]["value"], 1.0)
        self.assertAlmostEqual(rows["F37"]["value"], 2 / 6, places=6)
        self.assertEqual(rows["F38"]["value"], 0.4)
        self.assertEqual(rows["F39"]["value"], 1.0)
        self.assertEqual(rows["F15"]["status"], "SOURCE_UNAVAILABLE")
        self.assertIsNone(rows["F15"]["value"])
        self.assertEqual(rows["F25"]["status"], "NOT_APPLICABLE")

    def test_identical_input_has_deterministic_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            payload = self.input(self.snapshot(root))
            first = MODULE.build_vector(payload)
            second = MODULE.build_vector(payload)
        self.assertEqual(first["vector_fingerprint"], second["vector_fingerprint"])

    def test_base_payload_has_one_normalised_row_per_factor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            vector = MODULE.build_vector(self.input(self.snapshot(root)))
            payload = MODULE.build_base_payload(vector)
        self.assertEqual(len(payload["create_records"]), 60)
        rows = {row["Factor ID"]: row for row in payload["create_records"]}
        self.assertEqual(rows["F32"]["Role"], "TARGET")
        self.assertEqual(rows["F59"]["Role"], "GUARDRAIL")
        self.assertEqual(rows["F34"]["Role"], "DIAGNOSTIC")
        self.assertNotIn("Factor Value", rows["F15"])
        self.assertEqual(len({row["观测ID"] for row in payload["create_records"]}), 60)

    def test_unknown_hypothesis_factor_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            payload = self.input(self.snapshot(root))
            payload["change"]["hypothesis"]["target_factors"][0]["factor_id"] = "F99"
            with self.assertRaisesRegex(MODULE.FactorVectorError, "unknown factor"):
                MODULE.build_vector(payload)

    def test_target_guardrail_overlap_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            payload = self.input(self.snapshot(root))
            payload["change"]["hypothesis"]["guardrail_factors"][0]["factor_id"] = "F32"
            with self.assertRaisesRegex(MODULE.FactorVectorError, "duplicate"):
                MODULE.build_vector(payload)

    def test_target_direction_must_match_factor_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            payload = self.input(self.snapshot(root))
            payload["change"]["hypothesis"]["target_factors"][0][
                "expected_direction"
            ] = "DECREASE"
            with self.assertRaisesRegex(MODULE.FactorVectorError, "must use"):
                MODULE.build_vector(payload)

    def test_non_available_numeric_value_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            payload = self.input(self.snapshot(root))
            payload["measurements"]["F15"] = {
                "status": "SOURCE_UNAVAILABLE",
                "value": 0,
                "unit": "ratio",
                "source_refs": ["source://missing"],
                "status_reason": "Not instrumented.",
            }
            with self.assertRaisesRegex(MODULE.FactorVectorError, "value=null"):
                MODULE.build_vector(payload)

    def test_snapshot_fingerprint_mismatch_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            snapshot = self.snapshot(root)
            data = json.loads(snapshot.read_text())
            data["accepted_checkpoint_count"] = 99
            snapshot.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.FactorVectorError, "fingerprint mismatch"):
                MODULE.build_vector(self.input(snapshot))

    def test_guardrail_breach_requires_revert(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F32",
                target_value=1.0,
                guardrail="F59",
                guardrail_value=0.1,
                windows=["runtime"],
            )
            result = MODULE.evaluate_vector(vector, self.evaluation_context(vector))
        self.assertEqual(result["decision"], "REVERT_REQUIRED")
        self.assertEqual(result["summary"]["guardrail_breaches"], 1)

    def test_selected_source_unavailable_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F32",
                target_value=None,
                target_status="SOURCE_UNAVAILABLE",
                guardrail="F59",
                guardrail_value=0.0,
                windows=["runtime"],
            )
            result = MODULE.evaluate_vector(vector, self.evaluation_context(vector))
        self.assertEqual(result["decision"], "SOURCE_BLOCKED")
        self.assertEqual(result["summary"]["source_blocked"], 1)

    def test_pre_maturity_factor_continues_observing(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F01",
                target_value=0.2,
                target_threshold=0.1,
                guardrail="F30",
                guardrail_value=0.0,
                windows=["28d"],
            )
            context = self.evaluation_context(
                vector,
                window="7d",
                affects_traffic=True,
                production_level="CANDIDATE_7D",
            )
            result = MODULE.evaluate_vector(vector, context)
        self.assertEqual(result["decision"], "CONTINUE_OBSERVING")
        self.assertEqual(result["summary"]["immature_or_insufficient"], 2)

    def test_positive_7d_traffic_factors_require_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F10",
                target_value=0.2,
                target_threshold=0.1,
                guardrail="F48",
                guardrail_value=0.0,
                windows=["7d"],
            )
            context = self.evaluation_context(
                vector,
                window="7d",
                affects_traffic=True,
                production_level="CANDIDATE_7D",
            )
            result = MODULE.evaluate_vector(vector, context)
        self.assertEqual(result["decision"], "EXPERIMENT_REQUIRED")

    def test_durable_positive_traffic_factors_become_promotion_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F01",
                target_value=0.2,
                target_threshold=0.1,
                guardrail="F30",
                guardrail_value=0.0,
                windows=["28d"],
            )
            context = self.evaluation_context(
                vector,
                window="28d",
                affects_traffic=True,
                production_level="DURABLE_28D",
            )
            result = MODULE.evaluate_vector(vector, context)
        self.assertEqual(result["decision"], "PROMOTION_CANDIDATE")
        self.assertEqual(result["summary"]["passed"], 2)

    def test_mature_target_failure_has_no_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F10",
                target_value=0.05,
                target_threshold=0.1,
                guardrail="F48",
                guardrail_value=0.0,
                windows=["7d"],
            )
            context = self.evaluation_context(
                vector,
                window="7d",
                affects_traffic=True,
                production_level="CANDIDATE_7D",
            )
            result = MODULE.evaluate_vector(vector, context)
        self.assertEqual(result["decision"], "NO_EFFECT")
        self.assertEqual(result["summary"]["target_failures"], 1)

    def test_evaluation_identity_mismatch_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F32",
                target_value=1.0,
                guardrail="F59",
                guardrail_value=0.0,
                windows=["runtime"],
            )
            context = self.evaluation_context(vector)
            context["vector_fingerprint"] = "wrong"
            with self.assertRaisesRegex(MODULE.FactorVectorError, "identity mismatch"):
                MODULE.evaluate_vector(vector, context)

    def test_selected_factor_requires_declared_maturity_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F10",
                target_value=0.2,
                guardrail="F48",
                guardrail_value=0.0,
                windows=["runtime"],
            )
            context = self.evaluation_context(
                vector,
                window="7d",
                affects_traffic=True,
                production_level="CANDIDATE_7D",
            )
            with self.assertRaisesRegex(MODULE.FactorVectorError, "is not declared"):
                MODULE.evaluate_vector(vector, context)

    def test_identical_evaluation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            vector = self.configured_vector(
                pathlib.Path(tmp),
                target="F32",
                target_value=1.0,
                guardrail="F59",
                guardrail_value=0.0,
                windows=["runtime"],
            )
            context = self.evaluation_context(vector)
            first = MODULE.evaluate_vector(vector, context)
            second = MODULE.evaluate_vector(vector, context)
        self.assertEqual(
            first["evaluation_fingerprint"], second["evaluation_fingerprint"]
        )


if __name__ == "__main__":
    unittest.main()

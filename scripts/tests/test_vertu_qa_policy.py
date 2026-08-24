import importlib.util
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_qa_policy.py"
SPEC = importlib.util.spec_from_file_location("vertu_qa_policy", MODULE_PATH)
policy = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(policy)


class QAPolicyTests(unittest.TestCase):
    def test_current_policy_version_includes_editorial_safeguards(self):
        self.assertEqual(policy.POLICY_VERSION, "0.7.1")
        self.assertEqual(
            policy._stable_source_label(
                pathlib.Path("/tmp/vertu_editorial_safeguards.py")
            ),
            "scripts/vertu_editorial_safeguards.py",
        )

    def test_normalises_prefixed_legacy_version(self):
        self.assertEqual(
            policy.normalise_policy_version("vertu-seo-publish-gate-0.4.0"),
            "0.4.0",
        )

    def test_identity_is_deterministic_and_profile_sensitive(self):
        first = policy.build_qa_identity(
            sanity_doc_id="article-1",
            source_rev="rev-1",
            policy_hash="hash-1",
            evaluation_profile="official_site_standard",
        )
        second = policy.build_qa_identity(
            sanity_doc_id="article-1",
            source_rev="rev-1",
            policy_hash="hash-1",
            evaluation_profile="official_site_standard",
        )
        strict = policy.build_qa_identity(
            sanity_doc_id="article-1",
            source_rev="rev-1",
            policy_hash="hash-1",
            evaluation_profile="official_site_strict",
        )
        self.assertEqual(first["qa_identity"], second["qa_identity"])
        self.assertNotEqual(first["qa_identity"], strict["qa_identity"])

    def test_policy_hash_is_ordered_and_content_sensitive(self):
        with tempfile.TemporaryDirectory() as directory:
            first = pathlib.Path(directory) / "first.md"
            second = pathlib.Path(directory) / "second.md"
            first.write_text("one", encoding="utf-8")
            second.write_text("two", encoding="utf-8")
            original = policy.canonical_policy_hash(first, second)
            self.assertNotEqual(original, policy.canonical_policy_hash(second, first))
            second.write_text("changed", encoding="utf-8")
            self.assertNotEqual(original, policy.canonical_policy_hash(first, second))

    def test_policy_hash_is_workspace_path_independent(self):
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first = pathlib.Path(first_directory) / "SKILL.md"
                second = pathlib.Path(second_directory) / "SKILL.md"
                first.write_text("same policy", encoding="utf-8")
                second.write_text("same policy", encoding="utf-8")
                self.assertEqual(
                    policy.canonical_policy_hash(first),
                    policy.canonical_policy_hash(second),
                )

    def test_duplicate_audit_preserves_all_record_ids(self):
        duplicates = policy.duplicate_qa_run_ids(
            [
                {"qa_run_id": "qa-1", "record_id": "rec-a"},
                {"qa_run_id": "qa-1", "record_id": "rec-b"},
                {"qa_run_id": "qa-2", "record_id": "rec-c"},
            ]
        )
        self.assertEqual(duplicates, {"qa-1": ["rec-a", "rec-b"]})

    def test_travel_transaction_treat_is_not_medical_block(self):
        result = policy.classify_restricted_context(
            "Treat the offer as a new transaction.", "treat"
        )
        self.assertEqual(result["classification"], "NON_MEDICAL_CONTEXT")
        self.assertFalse(result["auto_block"])
        self.assertFalse(result["semantic_review_required"])

    def test_fare_conditions_and_upgrade_treatment_are_not_medical(self):
        result = policy.classify_restricted_context(
            "Read the fare conditions, including changes, refunds, baggage, seat selection and upgrade treatment.",
            "treatment",
        )
        self.assertEqual(result["classification"], "NON_MEDICAL_CONTEXT")
        self.assertFalse(result["auto_block"])

    def test_idiomatic_treat_as_is_not_medical(self):
        result = policy.classify_restricted_context(
            "Treat the room as part of the display system.", "treat"
        )
        self.assertEqual(result["classification"], "NON_MEDICAL_CONTEXT")
        self.assertFalse(result["semantic_review_required"])

    def test_diagnose_a_failure_is_not_medical(self):
        result = policy.classify_restricted_context(
            "Diagnose a failure without authorising a fix.", "diagnose"
        )
        self.assertEqual(result["classification"], "NON_MEDICAL_CONTEXT")
        self.assertFalse(result["auto_block"])

    def test_insurance_policy_treatment_is_not_product_medical_claim(self):
        result = policy.classify_restricted_context(
            "Review the insurance wording, including pre-existing-condition treatment and journey limits.",
            "treatment",
        )
        self.assertEqual(result["classification"], "NON_MEDICAL_CONTEXT")
        self.assertFalse(result["auto_block"])

    def test_affirmative_medical_claim_blocks(self):
        result = policy.classify_restricted_context(
            "This device can treat hypertension.", "treat"
        )
        self.assertEqual(result["classification"], "AFFIRMATIVE_MEDICAL_CLAIM")
        self.assertTrue(result["auto_block"])

    def test_medical_context_wins_when_non_medical_words_are_also_present(self):
        result = policy.classify_restricted_context(
            "The offer claims it can treat hypertension.", "treat"
        )
        self.assertEqual(result["classification"], "AFFIRMATIVE_MEDICAL_CLAIM")
        self.assertTrue(result["auto_block"])

    def test_unrelated_negation_does_not_hide_later_affirmative_claim(self):
        result = policy.classify_restricted_context(
            "It does not diagnose, but it can treat hypertension.", "treat"
        )
        self.assertEqual(result["classification"], "AFFIRMATIVE_MEDICAL_CLAIM")
        self.assertTrue(result["auto_block"])

    def test_negation_routes_to_review_without_auto_block(self):
        result = policy.classify_restricted_context(
            "This service does not diagnose or treat disease.", "diagnose"
        )
        self.assertEqual(result["classification"], "NEGATION_OR_DISCLAIMER")
        self.assertFalse(result["auto_block"])
        self.assertTrue(result["semantic_review_required"])

    def test_ambiguous_context_does_not_auto_block(self):
        result = policy.classify_restricted_context(
            "Treat this matter seriously.", "treat"
        )
        self.assertEqual(result["classification"], "AMBIGUOUS_CONTEXT")
        self.assertFalse(result["auto_block"])


if __name__ == "__main__":
    unittest.main()

import importlib.util
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vertu_qa_handoff.py"
SPEC = importlib.util.spec_from_file_location("vertu_qa_handoff", MODULE_PATH)
handoff = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(handoff)


def compatible_payload():
    return {
        "contract_version": "qa-handoff-v1",
        "publication_run_id": "run-1",
        "article_key": "article-1",
        "canonical_url": "https://vertu.com/guides/article-1",
        "section": "guides",
        "language": "en-GB",
        "markets": ["US", "GB"],
        "producer_skill": {"id": "vertu-english-blog-pipeline", "version": "3.10.0"},
        "source_identity": {
            "type": "sanity_draft_revision",
            "draft_bundle_sha256": "a" * 64,
            "sanity_doc_id": "doc-1",
            "source_rev": "rev-1",
        },
        "release_gate_role": "prepublish",
        "qa": {
            "run_id": "qa-run-1",
            "record_id": "rec-qa-1",
            "policy_id": "vertu-seo-publish-gate",
            "policy_version": "0.6.0",
            "policy_hash": "b" * 64,
            "evaluation_profile": "official_site_standard",
            "verdict": "PASS",
            "score": 93,
            "patch_action": "no_patch_needed",
            "critical_veto": None,
            "unresolved_critical": 0,
            "unresolved_required": 0,
        },
    }


class QAHandoffTests(unittest.TestCase):
    def test_compatible_handoff_authorises_release(self):
        result = handoff.validate_handoff(compatible_payload())
        self.assertEqual(result["compatibility_status"], "COMPATIBLE")
        self.assertTrue(result["authorises_release"])

    def test_current_producer_and_qa_pair_authorises_release(self):
        payload = compatible_payload()
        payload["producer_skill"]["version"] = "3.11.0"
        payload["qa"]["policy_version"] = "0.7.0"
        result = handoff.validate_handoff(payload)
        self.assertEqual(result["compatibility_status"], "COMPATIBLE")
        self.assertTrue(result["authorises_release"])

    def test_producer_version_mismatch_fails_closed(self):
        payload = compatible_payload()
        payload["producer_skill"]["version"] = "3.9.0"
        result = handoff.validate_handoff(payload)
        self.assertEqual(result["compatibility_status"], "VERSION_MISMATCH")
        self.assertFalse(result["authorises_release"])

    def test_policy_version_mismatch_fails_closed(self):
        payload = compatible_payload()
        payload["qa"]["policy_version"] = "0.5.0"
        result = handoff.validate_handoff(payload)
        self.assertEqual(result["compatibility_status"], "VERSION_MISMATCH")

    def test_artifact_mismatch_fails_closed(self):
        result = handoff.validate_handoff(
            compatible_payload(), expected_bundle_sha256="c" * 64
        )
        self.assertEqual(result["compatibility_status"], "ARTIFACT_MISMATCH")

    def test_revision_mismatch_fails_closed(self):
        result = handoff.validate_handoff(
            compatible_payload(), expected_source_rev="rev-2"
        )
        self.assertEqual(result["compatibility_status"], "REVISION_MISMATCH")

    def test_unresolved_required_finding_does_not_authorise(self):
        payload = compatible_payload()
        payload["qa"]["unresolved_required"] = 1
        result = handoff.validate_handoff(payload)
        self.assertFalse(result["authorises_release"])
        self.assertEqual(result["compatibility_status"], "TRACKING_INCOMPLETE")

    def test_result_fingerprint_detects_tampering(self):
        payload = compatible_payload()
        payload["qa_result_fingerprint"] = "d" * 64
        result = handoff.validate_handoff(payload)
        self.assertEqual(result["compatibility_status"], "ARTIFACT_MISMATCH")

    def test_observation_only_is_valid_but_never_authorises_release(self):
        payload = compatible_payload()
        payload["qa"]["verdict"] = "FIX"
        payload["qa"]["patch_action"] = "manual_review_before_patch"
        result = handoff.validate_handoff(payload, require_authorising_pass=False)
        self.assertTrue(result["valid_evidence"])
        self.assertFalse(result["authorises_release"])

    def test_bundle_fingerprint_is_content_sensitive_and_path_independent(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = pathlib.Path(first_dir) / "article.md"
            second = pathlib.Path(second_dir) / "article.md"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            first_hash = handoff.artifact_bundle_fingerprint({"article.md": str(first)})
            second_hash = handoff.artifact_bundle_fingerprint({"article.md": str(second)})
            self.assertEqual(first_hash, second_hash)
            second.write_text("changed", encoding="utf-8")
            self.assertNotEqual(
                first_hash,
                handoff.artifact_bundle_fingerprint({"article.md": str(second)}),
            )


if __name__ == "__main__":
    unittest.main()

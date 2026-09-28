"""Offline portability and least-authority checks for the public handoff."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import vertu_qa_policy as policy


class CreatorHandoffPackageTests(unittest.TestCase):
    def test_qa_uses_bundled_sources_without_installed_home_skill(self):
        with tempfile.TemporaryDirectory() as home:
            with patch.object(Path, "home", return_value=Path(home)):
                sources = policy.canonical_policy_sources()
                self.assertEqual(len(sources), 5)
                self.assertTrue(all(p.is_file() and p.is_relative_to(ROOT) for p in sources))
                result = policy.check_runtime()
        self.assertEqual(result["verdict"], "PASS")
        self.assertFalse(result["authorises_release"])

    def test_mirrored_qa_is_identical(self):
        self.assertEqual((ROOT / "scripts/vertu_qa_policy.py").read_bytes(),
                         (ROOT / "skills/vertu-seo-publish-gate/scripts/vertu_qa_policy.py").read_bytes())

    def test_missing_contract_fails_closed(self):
        sources = policy.canonical_policy_sources()
        with patch.object(policy, "canonical_policy_sources", return_value=(*sources[:-1], ROOT / "missing-contract.md")):
            with self.assertRaises(policy.QAPolicyError):
                policy.current_policy_identity()

    def test_template_has_no_publication_authority(self):
        data = tomllib.loads((ROOT / "automation/vertu-10.template.toml").read_text())
        self.assertEqual(data["status"], "INACTIVE")
        for expected in ("target_article_count: 5", "required_publish_count: 0", "delivery: local_draft", "production_publish: false"):
            self.assertIn(expected, data["prompt"])
        self.assertNotIn("required_publish_count: 10", data["prompt"])

    def test_creator_entrypoints_exist(self):
        for name in ("docs/CONTENT-CREATOR-HANDOFF.zh-CN.md", "docs/CURRENT-OPERATING-PROFILE.md", "templates/creator-submission.md"):
            self.assertTrue((ROOT / name).is_file())


if __name__ == "__main__":
    unittest.main()

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("public_release_validator", ROOT / "scripts/validate_bundle.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class PublicReleaseSafetyTests(unittest.TestCase):
    def detected(self, text):
        return any(p.search(text) for p in validator.FORBIDDEN_PATTERNS.values())

    def test_flags_resource_ids_even_without_url(self):
        self.assertTrue(self.detected("AbC" + "dEf0123456789" + "GhIjKl"))
        self.assertTrue(self.detected('`' + 'AbCdEf' * 4 + '`'))

    def test_flags_known_secret_shapes(self):
        self.assertTrue(self.detected("ghp_" + "a" * 30))
        self.assertTrue(self.detected("sk-" + "b" * 30))

    def test_flags_private_host_and_author(self):
        self.assertTrue(self.detected("https://" + "workspace" + ".feishu.cn/wiki/example"))
        self.assertTrue(self.detected("author-" + "vertu-example-desk"))

    def test_does_not_redact_normal_code_words_or_placeholders(self):
        self.assertFalse(self.detected("recommended recovery_profile records receipt_fingerprint"))
        self.assertFalse(self.detected("${FEISHU_BASE_TOKEN} ${AUTHOR_BUYER_GUIDE_ID}"))


if __name__ == "__main__":
    unittest.main()

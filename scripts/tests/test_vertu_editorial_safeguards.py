import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "skills"
    / "vertu-seo-publish-gate"
    / "scripts"
    / "vertu_editorial_safeguards.py"
)
SPEC = importlib.util.spec_from_file_location("vertu_editorial_safeguards", MODULE_PATH)
safeguards = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = safeguards
SPEC.loader.exec_module(safeguards)


def long_body(*, image: str = "", headings: str = "## Decision guide") -> str:
    words = " ".join(["substantive"] * 1510)
    return f"# Title\n\n{image}\n\n{headings}\n\n{words}\n"


class DuplicateIntegrationTests(unittest.TestCase):
    def test_two_integration_headings_are_a_required_blocking_fix(self):
        content = """# Guide

## Where VERTU Concierge Fits

One article-specific paragraph.

## How VERTU Concierge Can Help

Another article-specific paragraph.
"""
        result = safeguards.evaluate_article(
            article_key="guide-1",
            content=content,
            content_type="guide",
        )
        self.assertFalse(result["preflight_pass"])
        self.assertEqual(result["minimum_qa_status"], "FIX")
        self.assertEqual(result["qa_handoff_contract_version"], "qa-handoff-v1")
        self.assertEqual(result["qa_handoff_counts"]["unresolved_required"], 1)
        self.assertIn(
            "DUPLICATE_VERTU_CONCIERGE_INTEGRATION", result["blocking_codes"]
        )
        finding = result["findings"][0]
        self.assertEqual(finding["severity"], "required")
        self.assertEqual([item["line"] for item in finding["location"]], [3, 7])

    def test_one_integration_heading_does_not_block(self):
        result = safeguards.evaluate_article(
            article_key="guide-2",
            content="# Guide\n\n## The VERTU Perspective\n\nSpecific advice.",
            content_type="guide",
        )
        self.assertTrue(result["preflight_pass"])
        self.assertEqual(result["qa_handoff_counts"]["unresolved_required"], 0)

    def test_generic_concierge_topic_heading_is_not_integration(self):
        result = safeguards.duplicate_integration_evaluation(
            "# Guide\n\n## What Is a Hotel Concierge?\n\nAnswer.\n\n"
            "## How Concierge Service Works\n\nDetails."
        )
        self.assertEqual(result["integration_heading_count"], 0)
        self.assertFalse(result["blocking"])

    def test_related_vertu_navigation_heading_is_not_integration(self):
        result = safeguards.duplicate_integration_evaluation(
            "# Guide\n\n## Related VERTU guides and reading\n\n- [Guide](/guides/example)"
        )
        self.assertEqual(result["integration_heading_count"], 0)
        self.assertFalse(result["blocking"])

    def test_concierge_support_heading_counts_as_an_integration(self):
        result = safeguards.duplicate_integration_evaluation(
            "# Guide\n\n"
            "## Concierge support is downstream of connectivity\n\nDetails.\n\n"
            "## Where VERTU Concierge may fit\n\nDetails."
        )
        self.assertEqual(result["integration_heading_count"], 2)
        self.assertTrue(result["blocking"])


class HeadingFingerprintTests(unittest.TestCase):
    def test_normalises_year_punctuation_and_explicit_entities(self):
        left = safeguards.normalise_heading(
            "Emirates: Premium Economy vs. Business Class (2026)",
            ["Emirates"],
        )
        right = safeguards.normalise_heading(
            "Qatar Airways — Premium Economy versus Business Class 2027",
            ["Qatar Airways"],
        )
        self.assertEqual(left, right)
        self.assertIn("{entity}", left)
        self.assertIn("{year}", left)

    def test_repeated_substituted_outline_is_template_dependent(self):
        left = """# Emirates Premium Economy versus Business Class 2026
## Emirates Premium Economy versus Business Class at a Glance
## What You Get in Emirates Premium Economy
## What You Get in Emirates Business Class
## Emirates Seat and Sleep Comparison
## Food and Lounge Access on Emirates
## Who Should Choose Emirates Business Class
## Sources
"""
        right = """# Qatar Airways Premium Economy versus Business Class 2027
## Qatar Airways Premium Economy versus Business Class at a Glance
## What You Get in Qatar Airways Premium Economy
## What You Get in Qatar Airways Business Class
## Qatar Airways Seat and Sleep Comparison
## Food and Lounge Access on Qatar Airways
## Who Should Choose Qatar Airways Business Class
## Sources
"""
        result = safeguards.evaluate_batch(
            [
                {
                    "article_key": "emirates",
                    "content": left,
                    "content_type": "comparison",
                },
                {
                    "article_key": "qatar",
                    "content": right,
                    "content_type": "comparison",
                },
            ]
        )
        self.assertFalse(result["preflight_pass"])
        self.assertEqual(result["template_dependent_pair_count"], 1)
        self.assertEqual(
            result["template_dependent_article_keys"], ["emirates", "qatar"]
        )
        for article in result["articles"]:
            self.assertIn("TEMPLATE_DEPENDENT_DRAFT", article["blocking_codes"])
            self.assertEqual(article["qa_handoff_counts"]["unresolved_required"], 1)
            self.assertTrue(article["heading_fingerprint"]["entity_terms"])

    def test_sources_alone_cannot_create_template_dependent_finding(self):
        first = """# First
## Cabin layout
## Seat dimensions
## Food service
## Booking rules
## Sources and verification
## Related VERTU reading
"""
        second = """# Second
## Watch movement
## Case material
## Bracelet fit
## Collector value
## Sources and verification
## Related VERTU guides and reading
"""
        result = safeguards.evaluate_batch(
            [
                {
                    "article_key": "first",
                    "content": first,
                    "content_type": "guide",
                },
                {
                    "article_key": "second",
                    "content": second,
                    "content_type": "guide",
                },
            ]
        )
        self.assertTrue(result["preflight_pass"])
        self.assertEqual(result["template_dependent_pair_count"], 0)
        ignored = result["articles"][0]["heading_fingerprint"][
            "ignored_common_headings"
        ]
        self.assertEqual(
            [item["normalised"] for item in ignored],
            ["sources and verification", "related vertu reading"],
        )


class BodyVisualTests(unittest.TestCase):
    def test_hero_alone_emits_non_blocking_body_visual_warning(self):
        content = long_body(
            image="![Luxury aircraft cabin hero](https://example.com/hero.jpg)"
        )
        result = safeguards.evaluate_article(
            article_key="long-comparison",
            content=content,
            content_type="comparison",
        )
        self.assertTrue(result["preflight_pass"])
        self.assertEqual(result["body_visual"]["status"], "MISSING")
        self.assertEqual(result["warning_codes"], ["BODY_VISUAL_MISSING"])
        self.assertEqual(result["qa_handoff_counts"]["unresolved_required"], 0)
        self.assertEqual(result["qa_handoff_counts"]["unresolved_recommended"], 1)
        self.assertFalse(result["warnings"][0]["blocking"])

    def test_image_labelled_hero_after_h2_still_does_not_count(self):
        content = long_body(
            headings=(
                "## Decision guide\n\n"
                "![Luxury aircraft cabin hero image]"
                "(https://example.com/hero.jpg)"
            )
        )
        result = safeguards.body_visual_evaluation(
            content,
            content_type="comparison",
        )
        self.assertEqual(result["status"], "MISSING")
        self.assertEqual(result["in_body_visual_count"], 0)

    def test_descriptive_in_body_image_satisfies_visual_measure(self):
        content = long_body(
            headings=(
                "## Decision guide\n\n"
                "![Business-class seat width comparison diagram]"
                "(https://example.com/seat-comparison.jpg)"
            )
        )
        result = safeguards.body_visual_evaluation(
            content,
            content_type="comparison",
        )
        self.assertEqual(result["status"], "PRESENT")
        self.assertEqual(result["in_body_visual_count"], 1)
        self.assertIsNone(result["warning"])

    def test_explicit_editorial_exception_suppresses_warning(self):
        result = safeguards.body_visual_evaluation(
            long_body(),
            content_type="buyer_guide",
            visual_exception="No licensed cabin-detail image is available for this route.",
        )
        self.assertEqual(result["status"], "EXCEPTION")
        self.assertIsNone(result["warning"])

    def test_non_buyer_article_is_not_applicable(self):
        result = safeguards.body_visual_evaluation(
            long_body(),
            content_type="newsroom",
        )
        self.assertEqual(result["status"], "NOT_APPLICABLE")
        self.assertIsNone(result["warning"])


class ManifestCompatibilityTests(unittest.TestCase):
    def test_batch_manifest_rejects_unknown_handoff_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = pathlib.Path(directory) / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "qa_handoff_contract_version": "qa-handoff-v2",
                        "articles": [
                            {
                                "article_key": "one",
                                "content": "# One\n\n## Detail\n\nBody",
                                "content_type": "guide",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(safeguards.EditorialSafeguardError):
                safeguards._load_manifest_articles(manifest)


if __name__ == "__main__":
    unittest.main()

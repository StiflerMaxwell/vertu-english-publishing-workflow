import importlib.util
import hashlib
import json
import pathlib
import tempfile
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


HOT_FINGERPRINT = "a" * 64
EVERGREEN_FINGERPRINT = "b" * 64


def state_v2(**overrides):
    eligible = [f"article-{i}" for i in range(10)]
    payload = {
        "contract_version": "daily-publishing-quota-v2",
        "execution_id": "vertu-10-2026-09-02T04:00:00Z",
        "required_publish_count": 10,
        "max_articles": 10,
        "supply_phase": "HOT_PRIMARY",
        "phase_expansion_targets": {
            "HOT_PRIMARY": [30, 60, 90, 120],
            "EVERGREEN_FALLBACK": [30, 60, 90, 120],
        },
        "current_phase_target": 30,
        "candidate_pool_fingerprints": {"HOT_PRIMARY": HOT_FINGERPRINT},
        "candidate_lineage": [
            {
                "article_key": key,
                "supply_phase": "HOT_PRIMARY",
                "trend_class": "RISING_SEARCH",
                "pool_fingerprint": HOT_FINGERPRINT,
            }
            for key in eligible
        ],
        "eligible_article_keys": eligible,
        "selected_article_keys": eligible,
        "live_verified_article_keys": [],
        "blocked_articles": [],
        "gates_preserved": True,
    }
    payload.update(overrides)
    return payload


class DailyPublishingQuotaTests(unittest.TestCase):
    def test_user_five_article_profile_completes_only_at_five(self):
        keys = [f"article-{i}" for i in range(5)]
        for live_count in (0, 4, 5):
            with self.subTest(live_count=live_count):
                payload = state_v2(required_publish_count=5, max_articles=5,
                                   selected_article_keys=keys,
                                   live_verified_article_keys=keys[:live_count])
                result = quota.evaluate_quota_state(payload)
                self.assertEqual(result["state"] == "COMPLETE", live_count == 5)
                self.assertEqual(result["required_publish_count"], 5)

    def test_user_five_article_profile_rejects_six_selected_or_gate_waiver(self):
        for change in ({"selected_article_keys": [f"article-{i}" for i in range(6)]},
                       {"gates_preserved": False}):
            payload = state_v2(required_publish_count=5, max_articles=5,
                               selected_article_keys=[f"article-{i}" for i in range(5)])
            payload.update(change)
            with self.assertRaises(quota.QuotaStateError):
                quota.evaluate_quota_state(payload)

    def pre_discovery_fixture(self, directory):
        root = pathlib.Path(directory)
        evidence = {"execution_id": "run-startup", "verdict": "BLOCK",
                    "blocker": "QA_POLICY_VERSION_MISMATCH"}
        path = root / "failure.json"
        path.write_text(json.dumps(evidence))
        payload = state_v2(execution_id="run-startup", supply_phase="PRE_DISCOVERY",
                           actual_candidate_count=0, candidate_pool_fingerprints={},
                           candidate_lineage=[], eligible_article_keys=[], selected_article_keys=[],
                           hard_blocker={"code": evidence["blocker"], "evidence_path": path.name,
                                         "evidence_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        return payload, root, path, evidence

    def test_pre_discovery_hard_block_needs_no_artificial_pool(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, root, _, _ = self.pre_discovery_fixture(directory)
            result = quota.evaluate_quota_state(payload, evidence_root=root)
            self.assertEqual(result["state"], "DAILY_QUOTA_BLOCKED")
            self.assertEqual(result["shortfall"], 10)
            self.assertEqual(result["candidate_pool_fingerprints"], {})
            self.assertFalse(result["supply_exhausted"])
            self.assertFalse(result["authorises_release"])

    def author_fixture(self, directory):
        payload, root, path, evidence = self.pre_discovery_fixture(directory)
        evidence.update(blocker="AUTHOR_BLOCKED", all_six_desks_and_article_template_affected=True,
                        expected_institutional_type="Organization", article_qa_performed=False,
                        sanity_mutations=0, manual_apple_exception_applies=False)
        slugs = [f"vertu-{desk}-desk" for desk in (
            "buyer-guide", "ai-innovation", "watch-craft", "privacy-security",
            "concierge-travel", "product-service")]
        evidence["checks"] = [
            {"url": f"https://vertu.com/authors/{slug}",
             "final_url": f"https://vertu.com/authors/{slug}",
             "http_status": 200, "source_state": "AVAILABLE", "html_sha256": "c" * 64,
             "author_nodes": [{"type": "Person", "url": f"https://vertu.com/authors/{slug}"}]}
            for slug in slugs]
        article = dict(evidence["checks"][0], url="https://vertu.com/guides/test",
                       final_url="https://vertu.com/guides/test")
        evidence["checks"].append(article)
        payload["hard_blocker"]["code"] = evidence["blocker"]
        self.save_evidence(payload, path, evidence)
        return payload, root, path, evidence

    def save_evidence(self, payload, path, evidence):
        path.write_text(json.dumps(evidence))
        payload["hard_blocker"]["evidence_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    def test_shared_author_block_is_not_supply_exhaustion_or_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, root, _, _ = self.author_fixture(directory)
            result = quota.evaluate_quota_state(payload, evidence_root=root)
            self.assertEqual(result["state"], "DAILY_QUOTA_BLOCKED")
            self.assertEqual(result["next_action"], "REPAIR_HARD_BLOCKER")
            self.assertEqual(result["live_verified_count"], 0)
            self.assertFalse(result["authorises_release"])
            self.assertFalse(result["supply_exhausted"])

    def test_shared_author_rejects_incomplete_or_contradictory_observations(self):
        mutations = {
            "only_assertion": lambda e: e.pop("checks"),
            "single_desk": lambda e: e.update(checks=e["checks"][:1]),
            "missing_article": lambda e: e.update(checks=e["checks"][:6]),
            "duplicate_desk": lambda e: e["checks"].__setitem__(1, e["checks"][0]),
            "passing_desk": lambda e: e["checks"][0]["author_nodes"][0].update(type="Organization"),
            "redirect": lambda e: e["checks"][0].update(final_url="https://integration.example.invalid/configure"),
            "http_failure": lambda e: e["checks"][0].update(http_status=503),
            "source_blocked": lambda e: e["checks"][0].update(source_state="SOURCE_BLOCKED"),
            "unknown_author": lambda e: e["checks"][-1].update(author_nodes=[{"type": "Person", "url": "https://vertu.com/authors/unknown"}]),
            "invalid_author_url_type": lambda e: e["checks"][0]["author_nodes"][0].update(url=[]),
            "invalid_hash": lambda e: e["checks"][0].update(html_sha256="bad"),
            "manual_exception": lambda e: e.update(manual_apple_exception_applies=True),
            "mutations": lambda e: e.update(sanity_mutations=1),
            "qa_already_run": lambda e: e.update(article_qa_performed=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                payload, root, path, evidence = self.author_fixture(directory)
                mutate(evidence)
                self.save_evidence(payload, path, evidence)
                with self.assertRaises(quota.QuotaStateError):
                    quota.evaluate_quota_state(payload, evidence_root=root)

    def test_shared_author_uses_existing_execution_and_fingerprint_guards(self):
        for mode in ("foreign_run", "passing", "release", "tampered", "path_escape"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                payload, root, path, evidence = self.author_fixture(directory)
                if mode == "foreign_run":
                    evidence["execution_id"] = "other-run"
                elif mode == "passing":
                    evidence["verdict"] = "PASS"
                elif mode == "release":
                    evidence["authorises_release"] = True
                self.save_evidence(payload, path, evidence)
                if mode == "tampered":
                    path.write_text("{}")
                elif mode == "path_escape":
                    payload["hard_blocker"]["evidence_path"] = "../failure.json"
                with self.assertRaises(quota.QuotaStateError):
                    quota.evaluate_quota_state(payload, evidence_root=root)

    def test_single_downstream_author_block_still_requires_replacement(self):
        result = quota.evaluate_quota_state(state_v2(selected_article_keys=[f"article-{i}" for i in range(9)], blocked_articles=[
            {"article_key": "article-0", "stage": "AUTHOR", "reason": "AUTHOR_BLOCKED"}]))
        self.assertEqual(result["state"], "REPLACEMENT_REQUIRED")

    def test_pre_discovery_rejects_absent_or_tampered_evidence(self):
        for operation in ("delete", "tamper"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                payload, root, path, _ = self.pre_discovery_fixture(directory)
                path.unlink() if operation == "delete" else path.write_text("{}")
                with self.assertRaises(quota.QuotaStateError):
                    quota.evaluate_quota_state(payload, evidence_root=root)

    def test_pre_discovery_rejects_foreign_or_passing_or_wrong_code_evidence(self):
        for field, value in (("execution_id", "other"), ("verdict", "PASS"),
                             ("blocker", "NO_TOPIC"), ("authorises_release", True)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                payload, root, path, evidence = self.pre_discovery_fixture(directory)
                evidence[field] = value
                path.write_text(json.dumps(evidence))
                payload["hard_blocker"]["evidence_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.assertRaises(quota.QuotaStateError):
                    quota.evaluate_quota_state(payload, evidence_root=root)

    def test_pre_discovery_rejects_nonzero_candidates_and_unknown_code(self):
        for field, value in (("actual_candidate_count", 1), ("actual_candidate_count", False),
                             ("candidate_pool_fingerprints", {"HOT_PRIMARY": HOT_FINGERPRINT}),
                             ("hard_blocker", {"code": "NO_TOPIC"})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                payload, root, _, _ = self.pre_discovery_fixture(directory)
                payload[field] = value
                with self.assertRaises(quota.QuotaStateError):
                    quota.evaluate_quota_state(payload, evidence_root=root)

    def test_pre_discovery_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, root, _, _ = self.pre_discovery_fixture(directory)
            payload["hard_blocker"]["evidence_path"] = "../failure.json"
            with self.assertRaises(quota.QuotaStateError):
                quota.evaluate_quota_state(payload, evidence_root=root)

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

    def test_v2_hot_pool_can_complete_without_fallback(self):
        keys = [f"article-{i}" for i in range(10)]
        result = quota.evaluate_quota_state(state_v2(live_verified_article_keys=keys))
        self.assertEqual(result["state"], "COMPLETE")
        self.assertEqual(result["supply_phase"], "HOT_PRIMARY")

    def test_v2_hot_exhaustion_switches_to_evergreen(self):
        keys = ["article-0"]
        result = quota.evaluate_quota_state(
            state_v2(
                current_phase_target=120,
                eligible_article_keys=keys,
                selected_article_keys=keys,
                candidate_lineage=[
                    {
                        "article_key": "article-0",
                        "supply_phase": "HOT_PRIMARY",
                        "trend_class": "RISING_SEARCH",
                        "pool_fingerprint": HOT_FINGERPRINT,
                    }
                ],
            )
        )
        self.assertEqual(result["state"], "SWITCH_TO_EVERGREEN")
        self.assertEqual(result["next_action"], "START_EVERGREEN_FALLBACK")
        self.assertEqual(result["total_candidate_limit"], 240)

    def test_v2_evergreen_phase_expands_before_blocking(self):
        hot_keys = ["hot-0"]
        evergreen_keys = ["evergreen-0", "evergreen-1"]
        eligible = hot_keys + evergreen_keys
        result = quota.evaluate_quota_state(
            state_v2(
                supply_phase="EVERGREEN_FALLBACK",
                current_phase_target=30,
                candidate_pool_fingerprints={
                    "HOT_PRIMARY": HOT_FINGERPRINT,
                    "EVERGREEN_FALLBACK": EVERGREEN_FINGERPRINT,
                },
                eligible_article_keys=eligible,
                selected_article_keys=eligible,
                candidate_lineage=[
                    {
                        "article_key": "hot-0",
                        "supply_phase": "HOT_PRIMARY",
                        "trend_class": "RISING_SEARCH",
                        "pool_fingerprint": HOT_FINGERPRINT,
                    },
                    *[
                        {
                            "article_key": key,
                            "supply_phase": "EVERGREEN_FALLBACK",
                            "trend_class": "EVERGREEN_SEARCH",
                            "pool_fingerprint": EVERGREEN_FINGERPRINT,
                        }
                        for key in evergreen_keys
                    ],
                ],
            )
        )
        self.assertEqual(result["state"], "EXPAND_REQUIRED")
        self.assertEqual(result["next_action"], "EXPAND_EVERGREEN_FALLBACK")

    def test_v2_fallback_exhaustion_returns_quota_blocker(self):
        keys = [f"evergreen-{i}" for i in range(9)]
        result = quota.evaluate_quota_state(
            state_v2(
                supply_phase="EVERGREEN_FALLBACK",
                current_phase_target=120,
                candidate_pool_fingerprints={
                    "HOT_PRIMARY": HOT_FINGERPRINT,
                    "EVERGREEN_FALLBACK": EVERGREEN_FINGERPRINT,
                },
                eligible_article_keys=keys,
                selected_article_keys=keys,
                candidate_lineage=[
                    {
                        "article_key": key,
                        "supply_phase": "EVERGREEN_FALLBACK",
                        "trend_class": "EVERGREEN_SEARCH",
                        "pool_fingerprint": EVERGREEN_FINGERPRINT,
                    }
                    for key in keys
                ],
            )
        )
        self.assertEqual(result["state"], "DAILY_QUOTA_BLOCKED")

    def test_v2_downstream_blocker_uses_cumulative_replacement(self):
        eligible = [f"article-{i}" for i in range(11)]
        selected = eligible[:10]
        result = quota.evaluate_quota_state(
            state_v2(
                eligible_article_keys=eligible,
                selected_article_keys=selected,
                candidate_lineage=[
                    {
                        "article_key": key,
                        "supply_phase": "HOT_PRIMARY",
                        "trend_class": "RISING_SEARCH",
                        "pool_fingerprint": HOT_FINGERPRINT,
                    }
                    for key in eligible
                ],
                blocked_articles=[
                    {"article_key": "article-9", "stage": "QA", "reason": "BLOCK"}
                ],
            )
        )
        self.assertEqual(result["state"], "REPLACEMENT_REQUIRED")
        self.assertEqual(result["replacement_pool_count"], 1)

    def test_v2_rejects_hot_candidate_relabelled_as_evergreen(self):
        with self.assertRaises(quota.QuotaStateError):
            quota.evaluate_quota_state(
                state_v2(
                    candidate_lineage=[
                        {
                            "article_key": f"article-{i}",
                            "supply_phase": "HOT_PRIMARY",
                            "trend_class": "EVERGREEN_SEARCH",
                            "pool_fingerprint": HOT_FINGERPRINT,
                        }
                        for i in range(10)
                    ]
                )
            )


if __name__ == "__main__":
    unittest.main()

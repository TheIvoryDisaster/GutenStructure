import copy
import json
import unittest
from pathlib import Path
from scripts.apply_release_policy import desired_ruleset, ensure_not_weaker, validate_plan


class ReleasePolicyTests(unittest.TestCase):
    def test_payload_requires_two_reviews_and_owner_without_bypasses(self):
        policy = desired_ruleset(["build / build"])
        review = next(rule for rule in policy["rules"] if rule["type"] == "pull_request")["parameters"]
        self.assertEqual(review["required_approving_review_count"], 2)
        self.assertTrue(review["require_code_owner_review"])
        self.assertTrue(review["dismiss_stale_reviews_on_push"])
        self.assertEqual(policy["bypass_actors"], [])
        self.assertEqual(policy["conditions"]["ref_name"]["include"], ["refs/heads/release"])

    def test_explicit_seven_repository_plan(self):
        plan = validate_plan(json.loads(Path("backlog/releases.json").read_text()))
        self.assertEqual(len(plan["repositories"]), 8)
        plan["repositories"][0]["repository"] = "other-owner/repository"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_never_discards_stronger_reviews_or_extra_checks(self):
        desired = desired_ruleset(["build / build"])
        ensure_not_weaker(desired, desired)
        stronger = copy.deepcopy(desired)
        next(rule for rule in stronger["rules"] if rule["type"] == "pull_request")["parameters"]["required_approving_review_count"] = 3
        with self.assertRaises(ValueError):
            ensure_not_weaker(stronger, desired)
        extra = copy.deepcopy(desired)
        next(rule for rule in extra["rules"] if rule["type"] == "required_status_checks")["parameters"]["required_status_checks"].append({"context": "other", "integration_id": 15368})
        with self.assertRaises(ValueError):
            ensure_not_weaker(extra, desired)

    def test_never_changes_other_branch_scope_or_unknown_controls(self):
        desired = desired_ruleset(["build / build"])
        changed = copy.deepcopy(desired)
        changed["conditions"]["ref_name"]["include"].append("refs/heads/development")
        with self.assertRaises(ValueError):
            ensure_not_weaker(changed, desired)
        changed = copy.deepcopy(desired)
        changed["rules"].append({"type": "required_signatures"})
        with self.assertRaises(ValueError):
            ensure_not_weaker(changed, desired)


if __name__ == "__main__":
    unittest.main()


class FuturePolicyTests(unittest.TestCase):
    def fake(self, existing=None, missing_future_branch=True):
        import base64
        from scripts.apply_release_policy import GitHubFailure
        mutations = []
        def api(path, method="GET", body=None):
            if method != "GET":
                mutations.append((path, method, body))
                return {"id": 1}
            if path == "orgs/Meitou-Modding-Ecosystem":
                return {"id": 357134506}
            if "/repos?" in path:
                return [{"full_name": "Meitou-Modding-Ecosystem/NewMod", "default_branch": "main",
                         "private": False, "owner": {"id": 357134506}}]
            if "/branches/" in path:
                if "NewMod" in path and missing_future_branch:
                    raise GitHubFailure(404)
                return {"commit": {"sha": "sha"}}
            if "/contents/" in path:
                return {"content": base64.b64encode(b"* @Meitou-Modding-Ecosystem/maintainers\n").decode()}
            if "/rulesets?" in path:
                return [{"id": 1, "name": "Release promotion"}] if existing else []
            if "/rulesets/1" in path:
                return existing
            raise AssertionError(path)
        return api, mutations

    def test_future_public_repository_gets_policy_and_incomplete_setup_report(self):
        from scripts.apply_release_policy import synchronize
        plan = {"branch": "release", "repositories": [], "reconcile_future_public_repositories": True}
        api, mutations = self.fake()
        report = synchronize(api, plan, "Meitou-Modding-Ecosystem", apply=True)
        self.assertEqual(len(mutations), 1)
        self.assertEqual(report[0]["repository"], "Meitou-Modding-Ecosystem/NewMod")
        self.assertIn("release branch", report[0]["setup_required"])
        self.assertIn("fallback CODEOWNERS entry", report[0]["setup_required"])
        self.assertEqual(mutations[0][2]["bypass_actors"], [])

    def test_unchanged_daily_reconciliation_makes_no_writes(self):
        from scripts.apply_release_policy import synchronize
        current = desired_ruleset(["Release readiness"])
        api, mutations = self.fake(existing=current, missing_future_branch=False)
        report = synchronize(api, {"branch": "release", "repositories": [], "reconcile_future_public_repositories": True},
                             "Meitou-Modding-Ecosystem", apply=True)
        self.assertEqual(report[0]["action"], "unchanged")
        self.assertEqual(mutations, [])

    def test_preview_and_wrong_org_never_mutate(self):
        from scripts.apply_release_policy import synchronize
        api, mutations = self.fake()
        plan = {"branch": "release", "repositories": [], "reconcile_future_public_repositories": True}
        synchronize(api, plan, "Meitou-Modding-Ecosystem", apply=False)
        self.assertEqual(mutations, [])
        def wrong(path, **kwargs):
            if path.startswith("orgs/"):
                return {"id": 999}
            return api(path, **kwargs)
        with self.assertRaises(ValueError):
            synchronize(wrong, plan, "Meitou-Modding-Ecosystem", apply=True)
        self.assertEqual(mutations, [])


class PersonalExceptionTests(unittest.TestCase):
    def test_personal_repository_requires_prs_without_reviews(self):
        policy = desired_ruleset(["terraform", "automation"], personal=True)
        review = next(rule for rule in policy["rules"] if rule["type"] == "pull_request")["parameters"]
        self.assertEqual(review["required_approving_review_count"], 0)
        self.assertFalse(review["require_code_owner_review"])
        self.assertFalse(review["require_last_push_approval"])
        self.assertEqual(policy["bypass_actors"], [])
        self.assertEqual(set(policy["conditions"]["ref_name"]["include"]),
                         {"refs/heads/main", "refs/heads/release", "refs/heads/beta"})
        organization = desired_ruleset(["build / build"])
        review = next(rule for rule in organization["rules"] if rule["type"] == "pull_request")["parameters"]
        self.assertEqual(review["required_approving_review_count"], 2)
        self.assertTrue(review["require_code_owner_review"])

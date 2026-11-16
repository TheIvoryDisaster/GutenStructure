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
        self.assertEqual(len(plan["repositories"]), 7)
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
        changed["conditions"]["ref_name"]["include"].append("refs/heads/main")
        with self.assertRaises(ValueError):
            ensure_not_weaker(changed, desired)
        changed = copy.deepcopy(desired)
        changed["rules"].append({"type": "required_signatures"})
        with self.assertRaises(ValueError):
            ensure_not_weaker(changed, desired)


if __name__ == "__main__":
    unittest.main()

import unittest
from scripts.release_gate import check, validate_rules


class ReleaseGateTests(unittest.TestCase):
    def rule(self, count=2, owner=True):
        return {"type": "pull_request", "ruleset_id": 1,
                "parameters": {"required_approving_review_count": count, "require_code_owner_review": owner}}

    def test_requires_two_approvals_including_owner(self):
        good = lambda _: {"enforcement": "active", "bypass_actors": []}
        validate_rules([self.rule()], good)
        for rules in [[], [self.rule(1)], [self.rule(owner=False)]]:
            with self.assertRaises(RuntimeError):
                validate_rules(rules, good)

    def test_disabled_rules_and_bypass_are_rejected(self):
        for detail in [{"enforcement": "evaluate", "bypass_actors": []},
                       {"enforcement": "active", "bypass_actors": [{"actor_type": "RepositoryRole"}]}]:
            with self.assertRaises(RuntimeError):
                validate_rules([self.rule()], lambda _: detail)

    def test_other_branches_and_old_release_commits_are_rejected(self):
        repository = "Meitou-Modding-Ecosystem/MeitouClient"
        def api(path):
            if path.endswith("MeitouClient"):
                return {"owner": {"id": 357134506}}
            return {"commit": {"sha": "approved"}}
        with self.assertRaises(RuntimeError):
            check(api, repository, "refs/heads/fork", "approved")
        with self.assertRaises(RuntimeError):
            check(api, repository, "refs/tags/v1", "old")

    def test_unrelated_repository_is_never_queried(self):
        def api(path):
            raise AssertionError("No request should be made")
        with self.assertRaises(RuntimeError):
            check(api, "other-owner/repository", "refs/heads/release", "sha")


if __name__ == "__main__":
    unittest.main()


class FutureRepositoryGateTests(unittest.TestCase):
    def test_new_org_repository_uses_immutable_owner_identity_and_native_codeowners(self):
        import base64
        repository = "Meitou-Modding-Ecosystem/NewMod"
        rule = {"type": "pull_request", "ruleset_id": 1,
                "parameters": {"required_approving_review_count": 2, "require_code_owner_review": True}}
        def api(path):
            if path == "repos/" + repository:
                return {"owner": {"id": 357134506}}
            if "/branches/" in path and "/rules/" not in path:
                return {"commit": {"sha": "approved"}}
            if "/contents/" in path:
                return {"content": base64.b64encode(b"* @Meitou-Modding-Ecosystem/maintainers\n").decode()}
            if "/codeowners/errors" in path:
                return {"errors": []}
            if "/rules/branches/" in path:
                return [rule]
            return {"enforcement": "active", "bypass_actors": []}
        check(api, repository, "refs/heads/release", "approved")
        def wrong_owner(path):
            if path == "repos/" + repository:
                return {"owner": {"id": 1}}
            return api(path)
        with self.assertRaises(RuntimeError):
            check(wrong_owner, repository, "refs/heads/release", "approved")

    def test_invalid_or_partial_codeowner_coverage_blocks_release(self):
        import base64
        for text, errors in [("/src/ @owner", []), ("* @unknown", [{"kind": "Invalid owner"}])]:
            def api(path):
                if path == "repos/Meitou-Modding-Ecosystem/NewMod":
                    return {"owner": {"id": 357134506}}
                if "/contents/" in path:
                    return {"content": base64.b64encode(text.encode()).decode()}
                if "/codeowners/errors" in path:
                    return {"errors": errors}
                return {"commit": {"sha": "approved"}}
            with self.assertRaises(RuntimeError):
                check(api, "Meitou-Modding-Ecosystem/NewMod", "refs/heads/release", "approved")

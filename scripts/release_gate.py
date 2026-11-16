"""Require production releases to come from a protected, reviewed release branch."""
import json
import os
import urllib.error
import urllib.request

ALLOWED = {"TheIvoryDisaster/GutenStructure", *("Meitou-Modding-Ecosystem/" + name for name in (
    "MeitouClient", "MeitouMods", "PZAKenshiMotionLab", "TheWastelandRemembers", "PZAMeitouUi", "PZAMeitouUiProbe"))}


def validate_rules(rules, details):
    """At least one enforced ruleset must impose both reviews without bypass actors."""
    for rule in rules:
        parameters = rule.get("parameters", {})
        if rule.get("type") != "pull_request" or parameters.get("required_approving_review_count", 0) < 2:
            continue
        if not parameters.get("require_code_owner_review"):
            continue
        ruleset = details(rule["ruleset_id"])
        if ruleset.get("enforcement") == "active" and ruleset.get("bypass_actors") == []:
            return
    raise RuntimeError("Release branch requires an enforced ruleset with two approvals, a code owner and no bypass actors")


def check(api, repository, ref, commit):
    if repository not in ALLOWED:
        raise RuntimeError("Repository is outside the release allowlist")
    if ref != "refs/heads/release" and not ref.startswith("refs/tags/"):
        raise RuntimeError("Production release must run on release or a tag at its current head")
    branch = api(f"repos/{repository}/branches/release")
    if branch["commit"]["sha"] != commit:
        raise RuntimeError("Release commit must exactly match the release branch head")
    rules = api(f"repos/{repository}/rules/branches/release")
    validate_rules(rules, lambda ruleset_id: api(f"repos/{repository}/rulesets/{ruleset_id}"))
    print("PASS: release branch head and two-reviewer/code-owner ruleset verified")


def main():
    token = os.environ["GH_TOKEN"]
    def api(path):
        request = urllib.request.Request("https://api.github.com/" + path,
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "GutenStructure-release-gate"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Cannot verify release protection (HTTP {error.code}); publishing is blocked") from None
    check(api, os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REF"], os.environ["GITHUB_SHA"])


if __name__ == "__main__":
    main()

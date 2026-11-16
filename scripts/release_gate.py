"""Require production releases to come from a protected, reviewed release branch."""
import json
import re
import base64
import os
import urllib.error
import urllib.request

ALLOWED = {"TheIvoryDisaster/GutenStructure", *("Meitou-Modding-Ecosystem/" + name for name in (
    "MeitouClient", "MeitouMods", "PZAKenshiMotionLab", "TheWastelandRemembers", "PZAMeitouUi", "PZAMeitouUiProbe"))}


class MissingResource(RuntimeError):
    pass


def allowed_repository(repository):
    return repository == "TheIvoryDisaster/GutenStructure" or bool(re.fullmatch(r"Meitou-Modding-Ecosystem/[A-Za-z0-9_.-]+", repository))


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
    if not allowed_repository(repository):
        raise RuntimeError("Repository is outside the release allowlist")
    if ref != "refs/heads/release" and not ref.startswith("refs/tags/"):
        raise RuntimeError("Production release must run on release or a tag at its current head")
    metadata = api(f"repos/{repository}")
    expected_owner = 17211998 if repository == "TheIvoryDisaster/GutenStructure" else 357134506
    if metadata.get("owner", {}).get("id") != expected_owner:
        raise RuntimeError("Repository owner identity does not match the approved organization/account")
    if repository == "TheIvoryDisaster/GutenStructure" and metadata.get("id") != 1460291356:
        raise RuntimeError("Central repository identity mismatch")
    branch = api(f"repos/{repository}/branches/release")
    if branch["commit"]["sha"] != commit:
        raise RuntimeError("Release commit must exactly match the release branch head")
    owner_text = None
    for path in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        try:
            owners = api(f"repos/{repository}/contents/{path}?ref=release")
            owner_text = base64.b64decode(owners["content"]).decode()
            break
        except MissingResource:
            pass
    if not owner_text or not any(
        len(parts := line.split("#", 1)[0].split()) >= 2 and parts[0] == "*" and any("@" in value for value in parts[1:])
        for line in owner_text.splitlines()
    ):
        raise RuntimeError("Release needs a valid fallback CODEOWNERS entry covering every path")
    if api(f"repos/{repository}/codeowners/errors?ref=release").get("errors"):
        raise RuntimeError("GitHub reports invalid CODEOWNERS entries; publishing is blocked")
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
            if error.code == 404:
                raise MissingResource("Required release resource is missing") from None
            raise RuntimeError(f"Cannot verify release protection (HTTP {error.code}); publishing is blocked") from None
    check(api, os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REF"], os.environ["GITHUB_SHA"])


if __name__ == "__main__":
    main()

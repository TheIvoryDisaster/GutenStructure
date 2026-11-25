"""Require production releases to come from a protected, reviewed release branch."""
import json
import re
import base64
import os
import urllib.error
import urllib.request

ALLOWED = {"TheIvoryDisaster/GutenStructure", *("Meitou-Modding-Ecosystem/" + name for name in (
    "MeitouClient", "MeitouClientSandbox", "RivalryCore", "KenshiOracle", "PZAKenshiMotionLab", "TheWastelandRemembers", "PZAMeitouUi", "PZAMeitouUiProbe"))}


# Policy revision 5 (docs/branch-policy.md): the owner's one-person team may merge main/release promotion PRs without an approval.
# Pinned by ID, so renaming or recreating a team can't move the bypass. Kept here because this script runs standalone; the branch
# reconciliation imports both.
RELEASE_TEAM = "release-debugger"
RELEASE_TEAM_ID = 20828147


class MissingResource(RuntimeError):
    pass


def allowed_repository(repository):
    return repository == "TheIvoryDisaster/GutenStructure" or bool(re.fullmatch(r"Meitou-Modding-Ecosystem/[A-Za-z0-9_.-]+", repository))


def not_bypassable(ruleset, allowed=()):
    """GitHub returns bypass_actors only to callers who can edit the ruleset, so the workflow token sees no field.

    A hidden list is accepted: the scheduled "Configure release branch protections" run resets it to the policy's list with an
    administration token. A visible list may hold only the actors in <allowed>, and the calling token itself must never be able to
    bypass.
    """
    if ruleset.get("current_user_can_bypass", "never") != "never":
        return False
    return all(actor in allowed for actor in ruleset.get("bypass_actors", []))


def release_bypass(team_id):
    """Policy revision 5: the release team's PR-only bypass of the main/release approval rule (docs/branch-policy.md)."""
    return {"actor_type": "Team", "actor_id": team_id, "bypass_mode": "pull_request"}


def validate_rules(rules, details, personal=False, repository=None, release_team=RELEASE_TEAM_ID):
    """At least one enforced ruleset must impose both reviews without bypass actors."""
    for rule in rules:
        parameters = rule.get("parameters", {})
        if rule.get("type") != "pull_request":
            continue
        ruleset = details(rule["ruleset_id"])
        interim = (repository is not None and repository.startswith('Meitou-Modding-Ecosystem/')
            and (ruleset.get('name') == 'Meitou main and release approval' or
                 repository != 'Meitou-Modding-Ecosystem/Husbandry' and ruleset.get('name') == 'Interim super-maintainer approval')
            and parameters.get('required_approving_review_count', 0) >= 1
            and parameters.get('required_reviewers') == [{'file_patterns':['**'], 'minimum_approvals':1,
                 'reviewer':{'id':20738063,'type':'Team'}}])
        if not personal and not interim and (parameters.get("required_approving_review_count", 0) < 2 or not parameters.get("require_code_owner_review")):
            continue
        stable = interim and ruleset.get("name") == "Meitou main and release approval"
        allowed = [release_bypass(release_team)] if stable else []
        if ruleset.get("enforcement") == "active" and not_bypassable(ruleset, allowed):
            return
    raise RuntimeError("Release branch lacks the required enforced PR/review policy without bypass actors")


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
    native_rules = api(f"repos/{repository}/rules/branches/release")
    if isinstance(native_rules, list) and any(
            r.get('type') == 'pull_request' and r.get('parameters', {}).get('required_reviewers')
            and api(f"repos/{repository}/rulesets/{r['ruleset_id']}").get('name') == 'Meitou main and release approval'
            for r in native_rules):
        validate_rules(native_rules, lambda rid: api(f"repos/{repository}/rulesets/{rid}"), repository=repository)
        print("PASS: current release head and permanent super-maintainer policy (release team PR bypass only) verified")
        return
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
    validate_rules(rules, lambda ruleset_id: api(f"repos/{repository}/rulesets/{ruleset_id}"), personal=repository == "TheIvoryDisaster/GutenStructure", repository=repository)
    print("PASS: release head, ownership and repository-specific PR/review rules verified")


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

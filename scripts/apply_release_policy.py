"""Preview/apply release rulesets for an exact, version-controlled repository list."""
import argparse
import base64
import json
import copy
import os
import urllib.error
import urllib.request
from pathlib import Path
from scripts.release_gate import ALLOWED, allowed_repository


from scripts.github_errors import GitHubFailure

def optional(api, path):
    try:
        return api(path)
    except GitHubFailure as error:
        if error.status == 404:
            return None
        raise


def discover_repositories(api, selected):
    if api("orgs/Meitou-Modding-Ecosystem").get("id") != 357134506:
        raise ValueError("Organization identity mismatch")
    known = {item["repository"] for item in selected}
    result = list(selected)
    page = 1
    while True:
        repositories = api(f"orgs/Meitou-Modding-Ecosystem/repos?type=public&per_page=100&page={page}")
        for repo in repositories:
            if repo.get("archived") or repo.get("disabled"):
                continue
            if repo.get("private") or repo.get("owner", {}).get("id") != 357134506 or not allowed_repository(repo["full_name"]):
                raise ValueError("Discovery returned an unexpected owner or private repository")
            if repo["full_name"] not in known:
                result.append({"repository": repo["full_name"], "source": repo["default_branch"],
                               "checks": ["Release readiness"], "discovered": True})
                known.add(repo["full_name"])
        if len(repositories) < 100:
            return result
        page += 1


def desired_ruleset(checks, personal=False):
    return {"name": "Stable branch protection", "target": "branch", "enforcement": "active", "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/main", "refs/heads/release", "refs/heads/beta"] if personal else ["refs/heads/release"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
          {"type": "pull_request", "parameters": {"required_approving_review_count": 0 if personal else 2,
            "dismiss_stale_reviews_on_push": True, "require_code_owner_review": not personal,
            "require_last_push_approval": not personal, "required_review_thread_resolution": True}},
          {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": True,
            "required_status_checks": [{"context": check, "integration_id": 15368} for check in checks]}}]}


def validate_plan(plan):
    if plan.get("branch") != "release" or not isinstance(plan.get("repositories"), list):
        raise ValueError("Expected an explicit release-branch plan")
    seen = set()
    for item in plan["repositories"]:
        repo = item["repository"]
        if repo not in ALLOWED or repo in seen or not item.get("checks"):
            raise ValueError("Repository must be allowlisted, unique, and have required CI checks")
        if any(not isinstance(check, str) or not check for check in item["checks"]):
            raise ValueError("Required checks must be named")
        seen.add(repo)
    return plan


def ensure_not_weaker(existing, desired, personal=False):
    previous = existing.get("conditions", {}).get("ref_name", {})
    wanted = desired["conditions"]["ref_name"]
    if previous.get("exclude") != wanted["exclude"] or not set(previous.get("include", [])).issubset(wanted["include"]):
        raise ValueError("Existing managed ruleset has a different branch scope; review manually")
    desired_by_type = {rule["type"]: rule for rule in desired["rules"]}
    for rule in existing.get("rules", []):
        kind, parameters = rule["type"], rule.get("parameters", {})
        if kind not in desired_by_type:
            raise ValueError("Existing release ruleset has additional controls; preserve them manually")
        if kind == "pull_request" and not personal and (parameters.get("required_approving_review_count", 0) > 2 or parameters.get("required_reviewers")):
            raise ValueError("Existing release review requirement is stronger; do not weaken it")
        if kind == "required_status_checks":
            expected = {(check["context"], check.get("integration_id")) for check in desired_by_type[kind]["parameters"]["required_status_checks"]}
            actual = {(check["context"], check.get("integration_id")) for check in parameters.get("required_status_checks", [])}
            if not actual.issubset(expected):
                raise ValueError("Existing release ruleset requires additional checks; preserve them manually")


def synchronize(api, plan, target, apply=False):
    validate_plan(plan)
    selected = [item for item in plan["repositories"] if item["repository"].split("/")[0] == target]
    if target == "Meitou-Modding-Ecosystem" and plan.get("reconcile_future_public_repositories", False):
        selected = discover_repositories(api, selected)
    report = []
    # Inspect every selected repository before mutating any.
    prepared = []
    for item in selected:
        repo = item["repository"]
        setup_required = []
        branch = optional(api, f"repos/{repo}/branches/release")
        if not branch:
            setup_required.append("release branch")
        owners = None
        if branch:
            for path in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
                owners = optional(api, f"repos/{repo}/contents/{path}?ref=release")
                if owners:
                    break
        text = base64.b64decode(owners["content"]).decode() if owners else ""
        if not any(len(parts := line.split("#", 1)[0].split()) >= 2 and parts[0] == "*" and any("@" in value for value in parts[1:]) for line in text.splitlines()):
            setup_required.append("fallback CODEOWNERS entry")
        if item.get("discovered"):
            setup_required.append("required Release readiness CI check")
        # Install the rule even before a future release branch exists. The central
        # publishing gate separately refuses missing/invalid ownership and CI.
        rulesets = api(f"repos/{repo}/rulesets?includes_parents=false&per_page=100")
        if len(rulesets) >= 100:
            raise ValueError("Refusing an incomplete ruleset inventory")
        matching = [rule for rule in rulesets if rule["name"] in ("Stable branch protection", "Release promotion")]
        if len(matching) > 1:
            raise ValueError("Duplicate Release promotion rulesets; review manually")
        existing = api(f"repos/{repo}/rulesets/{matching[0]['id']}") if matching else None
        personal = repo == "TheIvoryDisaster/GutenStructure"
        desired = desired_ruleset(item["checks"], personal=personal)
        if existing:
            ensure_not_weaker(existing, desired, personal=personal)
            # Preserve supported additional review parameters rather than reset them.
            old_by_type = {rule["type"]: rule for rule in existing["rules"]}
            for rule in desired["rules"]:
                if "parameters" in rule and rule["type"] in old_by_type:
                    rule["parameters"] = {**old_by_type[rule["type"]].get("parameters", {}), **rule["parameters"]}
        prepared.append((repo, existing, desired, setup_required))
    for repo, existing, desired, setup_required in prepared:
        comparable = None if not existing else {key: existing.get(key) for key in desired}
        unchanged = comparable is not None and {**comparable, "rules": sorted(comparable["rules"], key=lambda rule: rule["type"])} == {**desired, "rules": sorted(desired["rules"], key=lambda rule: rule["type"])}
        if apply and not unchanged:
            if existing:
                api(f"repos/{repo}/rulesets/{existing['id']}", method="PUT", body=desired)
            else:
                api(f"repos/{repo}/rulesets", method="POST", body=desired)
        report.append({"repository": repo, "action": "unchanged" if unchanged else ("update" if existing else "create"),
                       "applied": apply and not unchanged, "setup_required": setup_required, "policy": desired})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["Meitou-Modding-Ecosystem", "TheIvoryDisaster"], default="Meitou-Modding-Ecosystem")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    plan = validate_plan(json.loads(Path("backlog/releases.json").read_text()))
    if args.validate_only:
        print("Validated explicit release policies for", len(plan["repositories"]), "repositories; no API calls made.")
        return
    token = os.environ.get("RELEASE_ADMIN_TOKEN")
    if not token:
        raise ValueError("RELEASE_ADMIN_TOKEN is required; the Projects-only token is insufficient")
    def api(path, method="GET", body=None):
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request("https://api.github.com/" + path, method=method, data=payload,
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "GutenStructure-release-policy"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return None if response.status == 204 else json.load(response)
        except urllib.error.HTTPError as error:
            raise GitHubFailure(error.code) from None
    if args.target == "Meitou-Modding-Ecosystem" and plan.get("policy_version") == 4:
        from scripts.permanent_branch_policy import synchronize as synchronize_permanent
        report = synchronize_permanent(api, plan, args.apply)
    elif args.target == "Meitou-Modding-Ecosystem" and plan.get("policy_version") == 3:
        from scripts.interim_review_policy import synchronize as synchronize_interim
        report = synchronize_interim(api, plan, args.apply)
    elif args.target == "Meitou-Modding-Ecosystem" and plan.get("policy_version") == 2:
        from scripts.branch_policy import synchronize as synchronize_tiers
        report = synchronize_tiers(api, plan, args.apply)
    else:
        report = synchronize(api, plan, args.target, args.apply)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

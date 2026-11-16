"""Preview/apply release rulesets for an exact, version-controlled repository list."""
import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from scripts.release_gate import ALLOWED


def desired_ruleset(checks):
    return {"name": "Release promotion", "target": "branch", "enforcement": "active", "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/release"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
          {"type": "pull_request", "parameters": {"required_approving_review_count": 2,
            "dismiss_stale_reviews_on_push": True, "require_code_owner_review": True,
            "require_last_push_approval": True, "required_review_thread_resolution": True}},
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


def ensure_not_weaker(existing, desired):
    if existing.get("conditions") != desired["conditions"]:
        raise ValueError("Existing Release promotion ruleset has a different branch scope; review manually")
    desired_by_type = {rule["type"]: rule for rule in desired["rules"]}
    for rule in existing.get("rules", []):
        kind, parameters = rule["type"], rule.get("parameters", {})
        if kind not in desired_by_type:
            raise ValueError("Existing release ruleset has additional controls; preserve them manually")
        if kind == "pull_request" and (parameters.get("required_approving_review_count", 0) > 2 or parameters.get("required_reviewers")):
            raise ValueError("Existing release review requirement is stronger; do not weaken it")
        if kind == "required_status_checks":
            expected = {(check["context"], check.get("integration_id")) for check in desired_by_type[kind]["parameters"]["required_status_checks"]}
            actual = {(check["context"], check.get("integration_id")) for check in parameters.get("required_status_checks", [])}
            if not actual.issubset(expected):
                raise ValueError("Existing release ruleset requires additional checks; preserve them manually")


def synchronize(api, plan, target, apply=False):
    validate_plan(plan)
    selected = [item for item in plan["repositories"] if item["repository"].split("/")[0] == target]
    report = []
    # Inspect every selected repository before mutating any.
    prepared = []
    for item in selected:
        repo = item["repository"]
        api(f"repos/{repo}/branches/release")
        owners = api(f"repos/{repo}/contents/.github/CODEOWNERS?ref=release")
        text = base64.b64decode(owners["content"]).decode()
        if not any(line.strip() and not line.lstrip().startswith("#") and "@" in line for line in text.splitlines()):
            raise ValueError("Release must contain an active CODEOWNERS file")
        rulesets = api(f"repos/{repo}/rulesets?includes_parents=false&per_page=100")
        if len(rulesets) >= 100:
            raise ValueError("Refusing an incomplete ruleset inventory")
        matching = [rule for rule in rulesets if rule["name"] == "Release promotion"]
        if len(matching) > 1:
            raise ValueError("Duplicate Release promotion rulesets; review manually")
        existing = api(f"repos/{repo}/rulesets/{matching[0]['id']}") if matching else None
        desired = desired_ruleset(item["checks"])
        if existing:
            ensure_not_weaker(existing, desired)
        prepared.append((repo, existing, desired))
    for repo, existing, desired in prepared:
        if apply:
            if existing:
                api(f"repos/{repo}/rulesets/{existing['id']}", method="PUT", body=desired)
            else:
                api(f"repos/{repo}/rulesets", method="POST", body=desired)
        report.append({"repository": repo, "action": "update" if existing else "create", "applied": apply, "policy": desired})
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
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"GitHub returned HTTP {error.code}; verify administration permission and branch setup") from None
    print(json.dumps(synchronize(api, plan, args.target, args.apply), indent=2))


if __name__ == "__main__":
    main()

# Organization branch policy

Applies to every Meitou-Modding-Ecosystem repo. **This table is the owner's approved design (2026-11-25). Change it only when the owner
asks; code, other docs and agents follow it, not the reverse.**

| Branch | Purpose | Required CI | Review policy |
| --- | --- | --- | --- |
| beta | Integrate development using sandbox hooks | Sandbox build, tests, Play deployment, applicable code scanning (`Development readiness`) | PR required, zero approvals |
| main | Assemble and review a release candidate | Same development checks as beta | PR required, **one** approval including code owners |
| release | Publish a production version | Development checks, upstream source compatibility, supported release compatibility, complete package validation (`Release readiness`) | PR required, **one** approval including code owners |
| Ordinary branches (feature, master, fork) | Work in progress | None | No protection |

One approval, not two: authors can't approve their own PRs, so one approval is the other maintainer's. A mod matures on `main` while its
engine hooks await upstream adoption; promotion to `release` is the compatibility boundary. The owner's `release-debugger` team (one person)
may bypass the main/release approval through a PR when necessary; CI is never bypassed, and GitHub logs each bypass in the ruleset insights.

## Enforcement structure

`scripts/development_branch_policy.py` (revision 6 in `backlog/releases.json`) implements the table as four rulesets per repo:

- **Meitou mandatory PR and CI**: beta/main/release; PR required, `Development readiness` (plus any existing build/security checks)
  required, force-push and deletion blocked, no bypass.
- **Meitou beta maintainer review**: beta; zero approvals.
- **Meitou main and release approval**: main/release; one approval including code owners, stale approvals dismissed; `release-debugger`
  PR-only bypass.
- **Meitou production compatibility**: release; `Release readiness` required, no bypass.

Independent security rules (code scanning, signatures) are kept. `release-debugger` is pinned by ID (`RELEASE_TEAM_ID` = 20828147 in
`scripts/release_gate.py`): reconciliation and the release gate accept a bypass only for that ID, so renaming or recreating the team
grants nothing until the ID is updated through a PR.

## Current and future repositories

The authoritative configuration is `backlog/releases.json` revision 6, implemented in `scripts/development_branch_policy.py`. **Configure release branch protections** runs hourly at minute 17 on GutenStructure main, and can be dispatched manually (organization, preview first, then apply). It discovers live public repositories under immutable org ID 357134506, including new repos and renames; the selected team receives repository write access if needed. Existing CI contexts are preserved/deduplicated; new repositories require `Release readiness` unless explicitly configured otherwise.

GitHub repository templates do **not** inherit rulesets, team assignments or environment settings. MeitouModTemplate supplies CI/source; scheduled discovery applies policy to each new public repo on its next run (up to about one hour, not immediate). Dispatch reconciliation during onboarding before relying on protected merges. Ensure the organization administration token covers All repositories, repository Administration read/write and Members read. No author build receives this token.

Organization-wide rulesets require compatible plan and organization-level permissions. Where unavailable, this scheduled per-repository reconciliation is the supported free-tier path. Future private repos need their plan/protection/execution permissions reviewed before coverage can be claimed; current org repos are public. The pipeline reports/fails on unsupported scope instead of exposing private names/code or weakening rules silently.

Required branch rules may target branches before they exist. Onboard their source and workflow through PRs; an expected check with no matching workflow will wait forever, so verify actual check runs on each relevant branch. CI requirements are not removed to accommodate missing workflows. See the completion report for existing readiness gaps.

## Publishing and safe promotion

The central release gate accepts the main/release approval rule above (at least one approval including code owners) for all organization repos. It still requires the current release head, matching tag/source identity and no visible release bypass other than the `release-debugger` PR-only bypass; hidden bypass lists rely on the scoped administration read-back/reconciliation. Historical workflow pins keep their old behavior: upgrade the caller's release gate and isolated publisher pins together through a reviewed PR after central release promotion. No tag or public mod release is created by changing protections.

GutenStructure is personally owned, outside this org: its PR+CI/zero-reviewer exception is unchanged. The custom App is no longer required. Remove/revoke its unused pilot key/environment/installation only after confirming no other intended consumer; never place it in organization workflows.

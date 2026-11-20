# Permanent organization branch policy — revision 4

Applies to every Meitou-Modding-Ecosystem repo, including Husbandry. The custom owner-author App pilot and temporary Husbandry exception are superseded.

| Branch | Policy |
| --- | --- |
| Ordinary branches, including master/fork | No branch protection |
| beta | PR and passing CI. super-maintainers may bypass review through a PR, including their own PRs. |
| main | PR, passing CI, one independent super-maintainers approval. No review bypass. |
| release | PR, passing CI, one independent super-maintainers approval. No review bypass. |

Native required-team review uses team ID 20738063 (`super-maintainers`). CODEOWNERS may still document ownership but is not an extra approval gate. Authors cannot approve themselves; beta's native review bypass implements the authorized self-merge exception. It can also be used for another author's beta PR. GitHub Actions has no review bypass; dependency-update bots need a maintainer review/merge.

## Enforcement structure

- **Meitou mandatory PR and CI**: beta/main/release; PR required, configured CI required, force-push/deletion blocked, no bypass actors.
- **Meitou beta maintainer review**: beta only; native one-team-approval rule with Team 20738063 PR-only bypass. It contains no CI/safety rules.
- **Meitou main and release approval**: main/release only; native one-team-approval rule and no bypass actors.

New reviewable commits dismiss stale approvals. No extra last-pusher approval, no extra bot-attribution approval, no additional CODEOWNER review. CI need not be strictly up to date with base; CI still must pass. Independent security/signature/code-scanning requirements are retained on protected branches. Ordinary development/mirror branches are not added to the protected scopes. Other inherited/custom-scoped protections are inspected rather than silently weakened.

## Current and future repositories

The authoritative configuration is `backlog/releases.json` revision 4, implemented in `scripts/permanent_branch_policy.py`. **Configure release branch protections** runs hourly at minute 17 on GutenStructure main, and can be dispatched manually (organization, preview first, then apply). It discovers live public repositories under immutable org ID 357134506, including new repos and renames; the selected team receives repository write access if needed. Existing CI contexts are preserved/deduplicated; new repositories require `Release readiness` unless explicitly configured otherwise.

GitHub repository templates do **not** inherit rulesets, team assignments or environment settings. MeitouModTemplate supplies CI/source; scheduled discovery applies policy to each new public repo on its next run (up to about one hour, not immediate). Dispatch reconciliation during onboarding before relying on protected merges. Ensure the organization administration token covers All repositories, repository Administration read/write and Members read. No author build receives this token.

Organization-wide rulesets require compatible plan and organization-level permissions. Where unavailable, this scheduled per-repository reconciliation is the supported free-tier path. Future private repos need their plan/protection/execution permissions reviewed before coverage can be claimed; current org repos are public. The pipeline reports/fails on unsupported scope instead of exposing private names/code or weakening rules silently.

Required branch rules may target branches before they exist. Onboard their source and workflow through PRs; an expected check with no matching workflow will wait forever, so verify actual check runs on each relevant branch. CI requirements are not removed to accommodate missing workflows. See the completion report for existing readiness gaps.

## Publishing and safe promotion

The central release gate accepts the exact permanent native main/release team policy for all organization repos. It still requires the current release head, matching tag/source identity and no visible release bypass; hidden bypass lists rely on the scoped administration read-back/reconciliation. Permanent native team authorization does not require CODEOWNERS validity. Historical workflow pins keep their old behavior: upgrade the caller's release gate and isolated publisher pins together through a reviewed PR after central release promotion. No tag or public mod release is created by changing protections.

GutenStructure is personally owned, outside this org: its PR+CI/zero-reviewer exception is unchanged. The custom App is no longer required. Remove/revoke its unused pilot key/environment/installation only after confirming no other intended consumer; never place it in organization workflows.

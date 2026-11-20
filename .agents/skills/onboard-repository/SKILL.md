---
name: onboard-repository
description: Onboard a Meitou repository to GutenStructure CI, reviewed release promotion, project tracking, and optional quota-controlled private artifacts.
---

# Onboard a repository

Use this skill when adding or repairing CI/release setup for an existing or new Meitou-Modding-Ecosystem repository. Read the repository's AGENTS.md, README and build manifests first. Use the GitHub connector for supported operations; use the GitHub-hosted administration/project workflows when this cloud workspace substitutes credentials or lacks the needed permissions.

## Boundaries

- GutenStructure is personally controlled. Never give organization authors administrative access to it or broad Azure roles.
- Scope organization operations to immutable organization ID `357134506`. GutenStructure is repository ID `1460291356`, personally owned by account ID `17211998`.
- Prefer free standard GitHub-hosted runners for public builds. Do not provision Azure runners or paid GitHub plans without a concrete reviewed need.
- No Azure credentials in PR builds, no `secrets: inherit`, no original Kenshi data in public caches/artifacts, no raw tokens in chat/code/logs/state committed to Git.
- Do routine read-only inspection and reversible preparation without repeated permission requests. Do not bypass required GitHub reviews, environment approvals, rulesets or an automatic approval rejection.

## 1. Inspect and classify

Inventory source/default/development branches, SDK/runtime pins, engine references/submodules, build/test/package commands, licenses, game-data requirements and existing checks. Update `docs/build-inventory.md` and `backlog/releases.json`. Do not claim full integration coverage when only compilation or engine-free rules were checked.

MeitouClient `master` is an upstream mirror; development uses `fork`. RivalryCore develops on `beta`, with existing stable work on `main`. Other repositories keep their development branches. Never rewrite an upstream mirror for organization-only CI.

## 2. Prepare unprivileged CI

Use `.github/workflows/build-dotnet.yml`, `build-python.yml`, or the UI compatibility workflow as appropriate. Pin each reference to a reviewed 40-character commit reachable from GutenStructure's `release` branch; do not pin production to an unreviewed feature branch or mutable tag. `examples/README.md` contains templates.

Run CI on development PRs/pushes and on PRs/pushes targeting `release`. Define a final `Release readiness` job that succeeds only when every required build/test/package prerequisite succeeded; skipped, cancelled or failed dependencies must not count as success. Keep the existing required check names until the ruleset migration is complete. Pin third-party actions by commit SHA, use read-only tokens and disable persisted checkout credentials. Cancel superseded PR builds.

For framework consumers, follow [dependency consumer CI](../../../docs/dependency-consumer-ci.md). Ensure the workflow is present in the beta PR merge tree, not just the default branch, and preserve required check names. Distinguish engine-free baseline checks from real-framework present/absent integration tests. Use immutable artifact tags and pinned digests; lock format and automatic downstream triggering remain separate design work in RivalryCore #62.

## 3. Bootstrap release and ownership

Create `release` from an explicitly identified stable commit. For a new/empty repo, first establish its initial source commit. Ensure GitHub's effective CODEOWNERS file is valid and has a fallback `*` owner covering all paths. Preserve existing path-specific ownership. Use the real repository's current users/teams; do not invent reviewers or silently substitute organization owners for code owners. A new bootstrap can name the personal owner as a fallback only when authorized; it does not authorize subsequent promotions.

Open configuration/promotion PRs to `release`. Do not cut production releases from a development branch. Nightlies may remain separate development prereleases.

## 4. Enforce permanent native policy

Use revision 4 in `scripts/permanent_branch_policy.py` and `docs/branch-policy.md` for every public organization repo, including Husbandry. Ordinary branches remain unprotected. Beta requires a PR and passing CI; only super-maintainers may bypass its separate review rule. Main/release require one independent super-maintainers approval and passing CI, with no review bypass. The native reviewing-team requirement is independent of CODEOWNERS. No custom App or GitHub Actions bypass is needed. GitHub cannot count self-approval; beta self-merges use only the authorized review-rule exemption.

Keep mandatory PR, CI, force-push/deletion protection in a separate no-bypass safety rule. Preserve required check names and independent security rules. Preview then apply Configure release branch protections on GutenStructure main, environment Default. Verify effective rules and actual CI runs; a ruleset file alone is not proof. Meitou-owned MEITOU_RELEASE_ADMIN_TOKEN must cover All repositories, repository Administration read/write and organization Members read. Personal settings use GUTENSTRUCTURE_ADMIN_TOKEN separately.

Reconciliation discovers current/future public repos hourly, verifies immutable org/team IDs, grants the selected team write access where missing, and requires configured CI (Release readiness for new repos). Templates do not copy repository settings. Run reconciliation manually during onboarding before expecting protected promotions to work. Private repositories/organization-wide plan support need separate validation; no new Azure access is implied. Missing branches and CI must be bootstrapped through reviewed PRs; do not remove CI requirements to unblock a missing workflow.

## 5. Gate production builds

Make production workflows depend on the SHA-pinned central `release-gate.yml`. It verifies the current release head, actual enforced native team-review ruleset, absence of bypass actors, and valid complete ownership. Tags must point at the current `release` head. Promote shared workflow changes to GutenStructure `release` through a checked PR before upgrading callers; its personal exception requires zero reviewers, not the organization independent-review rule. Preserve version/manifest checks and artifact completeness. Do not replace a missing proprietary-data build with a misleading partial production package.

Check protection through the API and run hosted CI. A branch existing or a JSON policy file being present does not prove enforcement. Authorized repository writers may still publish manually unless their permissions are restricted; never present the official workflow guard as a universal GitHub permission boundary.

## 6. Track the work

Add issue URLs and explicit field mappings to `backlog/project.json`. The Projects token is an **environment secret in Default**, named `MEITOU_PROJECT_TOKEN`. Run **Synchronize Meitou project** on main with apply=false, review the preview, then apply=true. It reuses existing cards and does not delete unrelated items. Unspecified fields stay manually managed. Add any newly approved repository to the synchronizer allowlist before configuring its issue URLs.

Attach every created PR to the current Codex task. Record blockers and acceptance criteria in issues; do not mark setup done merely because a PR was opened.

## 7. Optional Azure artifacts

Private artifacts are separate from public GitHub Releases. Use the quota broker; never grant repository jobs storage contributor roles. Add an explicit immutable repository/owner ID, allowed refs/subjects and approved central workflow SHA to broker policy only through reviewed promotion. Discovery of a new repository must not grant Azure publishing automatically. Verify measured upload limits, atomic per-repo/global quotas, replay handling, cross-repository isolation and download limits before enabling it.

Readers are explicit Entra user object IDs; GitHub usernames alone do not grant Azure access. The selected reader for the current phase is TheIvoryDisaster. Preserve this audience unless the owner changes it. Review a Terraform plan with a private state backend; never replace shared gutenhub resources or their lifecycle rules without importing and preserving unrelated projects. Production deployment must originate from the protected GutenStructure release branch. The personal repository has the zero-reviewer PR exception described below. No automatic Terraform apply or Azure access on PRs.

## Completion evidence

Report hosted check results, enforced rule evidence, reviewer requirements, build coverage limits, configured project cards, live Azure verification (when applicable), estimated cost and any remaining credentials/reviews. Keep pending source code, deployed infrastructure and enabled publishing clearly distinguished. Do not claim end-to-end readiness while release approvals, ownership, licensed assets or access configuration remain missing.

## GutenStructure personal exception and testing lane

GutenStructure alone requires PRs and passing CI on main, beta and release, but **zero required reviewers** and no mandatory code-owner approval. The owner does not intend to co-own it. Agents may review, validate and merge routine changes through one conceptually grouped PR; do not attempt a formal author self-approval through GitHub's review API.

If a change needs the owner's personal testing, open its PR into beta and await feedback before promoting beta to main or release. Keep personally tested changes out of production until that feedback arrives. Do not apply this exception to any organization repository. Restrict Default environment secrets to reviewed main/release branches before granting collaborator write access; those secrets must not be available to arbitrary PR code.

## Historical revision 3 (superseded by permanent revision 4)

The latest user instruction supersedes the older branch tiers for public org repos except Husbandry: see `docs/interim-review-policy.md`. Require one native super-maintainers approval on beta/main/release, no CODEOWNERS dependency or review bypass, preserve CI/security, and exclude Husbandry from every mutation. Probe/read back required-team API support before relaxing rules. Update immutable release-gate/package callers after central promotion; old pins are not automatically changed. The custom App rollout remains Husbandry-only until tested.

Permanent revision 4 in docs/branch-policy.md overrides every earlier temporary/pilot paragraph. Husbandry has no exception.

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

MeitouClient `master` is an upstream mirror; development uses `fork`. MeitouMods develops on `beta`, with existing stable work on `main`. Other repositories keep their development branches. Never rewrite an upstream mirror for organization-only CI.

## 2. Prepare unprivileged CI

Use `.github/workflows/build-dotnet.yml`, `build-python.yml`, or the UI compatibility workflow as appropriate. Pin each reference to a reviewed 40-character commit reachable from GutenStructure's `release` branch; do not pin production to an unreviewed feature branch or mutable tag. `examples/README.md` contains templates.

Run CI on development PRs/pushes and on PRs/pushes targeting `release`. Define a final `Release readiness` job that succeeds only when every required build/test/package prerequisite succeeded; skipped, cancelled or failed dependencies must not count as success. Keep the existing required check names until the ruleset migration is complete. Pin third-party actions by commit SHA, use read-only tokens and disable persisted checkout credentials. Cancel superseded PR builds.

## 3. Bootstrap release and ownership

Create `release` from an explicitly identified stable commit. For a new/empty repo, first establish its initial source commit. Ensure GitHub's effective CODEOWNERS file is valid and has a fallback `*` owner covering all paths. Preserve existing path-specific ownership. Use the real repository's current users/teams; do not invent reviewers or silently substitute organization owners for code owners. A new bootstrap can name the personal owner as a fallback only when authorized; it does not authorize subsequent promotions.

Open configuration/promotion PRs to `release`. Do not cut production releases from a development branch. Nightlies may remain separate development prereleases.

## 4. Enforce reviews and required CI

Use **Configure release branch protections** in GutenStructure (`main`, environment `Default`) to preview first, then apply the reviewed policy. Organization secret: `MEITOU_RELEASE_ADMIN_TOKEN`, owned by Meitou-Modding-Ecosystem with repository Administration read/write; choose All repositories for future-repository reconciliation. GutenStructure administration uses a separate personally scoped credential `GUTENSTRUCTURE_ADMIN_TOKEN`. Never print token values or pass either token to build jobs.

Organization main/release rules:

1. A pull request is required; direct/force pushes and deletion are blocked.
2. **Two distinct approving reviewers, including at least one applicable CODEOWNER.** The owner approval counts toward the two, not as a third review. Native ownership rules may require multiple applicable owners when different owned paths are changed.
3. Dismiss stale approvals, require approval after the last push, resolve review threads, and require up-to-date CI.
4. No bypass actors, including administrators or bots.

In organization repositories, GitHub authors cannot approve their own PRs. An owner-authored PR cannot satisfy ownership review if that author is the only applicable owner. Report the blocker and arrange another eligible code owner/reviewer through legitimate reviewed changes; never lower review counts, add a bypass, impersonate a reviewer or merge via another API.

Organization-wide rulesets need GitHub Team/Enterprise. The free-tier policy reconciles current/future public repos under the verified org ID. New repos need `release`, valid CODEOWNERS and `Release readiness` CI before official publishing. Do not expose future private repository names or code in public workflow logs; private-repository execution/plan support needs separate review.

## 5. Gate production builds

Make production workflows depend on the SHA-pinned central `release-gate.yml`. It verifies the current release head, actual enforced two-reviewer/code-owner ruleset, absence of bypass actors, and valid complete ownership. Tags must point at the current `release` head. Promote shared workflow changes to GutenStructure `release` through a checked PR before upgrading callers; its personal exception requires zero reviewers, not the organization two-reviewer rule. Preserve version/manifest checks and artifact completeness. Do not replace a missing proprietary-data build with a misleading partial production package.

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

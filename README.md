# GutenStructure

Personally controlled CI automation and Azure infrastructure for the Meitou Modding Ecosystem.

Standard GitHub-hosted runners build public repositories. Azure is reserved for workloads or artifact storage that need it; there is no Azure compute deployment in this baseline.

## Reusable builds

Call `.github/workflows/build-dotnet.yml` or `build-python.yml` from repository CI, pinned to a reviewed **40-character commit SHA**. See [caller examples](examples/README.md). These workflows have read-only repository permissions, no Azure authentication, no artifact publication, and no persisted checkout credentials. Repository build/test code is untrusted.

## Reusable mod packaging

`.github/workflows/package-meitou-mod.yml` packs one Meitou code mod and publishes it as a GitHub Release asset in the **calling** repository: a beta channel (immutable `<slug>-<version>-beta.<commit>` prereleases plus a rolling `<slug>-beta`) and a release channel (`<slug>-v<version>`, behind the caller's `release-gate.yml` job). The build runs in a read-only job; the publish job checks out nothing, runs no caller code and uses only the caller's own `GITHUB_TOKEN` with `contents: write`. It accepts no secrets, so no personal or GutenStructure credential reaches organization repositories. See [caller examples](examples/README.md).

## Framework lock

Mod repositories consume framework releases through `meitou.lock.json` and `msbuild/Meitou.Frameworks.targets`: hash-checked downloads, engine and range checks, and a local-clone override. See [framework lock](docs/framework-lock.md).

## Infrastructure and publishing

- [Build inventory](docs/build-inventory.md)
- [Release branch promotion](docs/releases.md)
- [Project synchronization](docs/project-sync.md)
- [Publishing boundary and rollout](docs/publishing.md)
- [Cost assumptions](docs/costs.md)
- [Daily PR digest](docs/pr-digest.md)
- [Terraform module](terraform/README.md)

Publishing is intentionally unavailable until centrally enforced identity and quota checks exist. The Terraform module creates storage containers and retention rules on a **dedicated** storage account; it does not grant workload access or adopt the existing shared account.

## Owner controls

`CODEOWNERS` requests review; it does not enforce approval. Before enabling Azure publishing, apply the [owner controls](docs/owner-controls.md): require PRs and passing CI, block force pushes/deletion, and require no reviewers in this personally owned repository. Only the personal owner should retain administration. Keep repository administration and Azure federation/RBAC administration under personal control. Review repository Actions defaults and third-party action permissions.

Do not commit credentials, state, saved plans or sensitive infrastructure output. Terraform state belongs in a private backend.

## Onboard a new repository

Agent instructions: [onboard-repository skill](.agents/skills/onboard-repository/SKILL.md). Detailed protection setup: [release promotion](docs/releases.md).

1. Inspect the repository's instructions, SDK/engine dependencies, existing tests and packaging requirements. Record actual coverage in the build inventory.
2. Add a small caller for the appropriate reusable build workflow. Pin it to a reviewed GutenStructure **release-branch commit SHA**, use read-only permissions, and run it on development and `release` PRs/pushes. Add a final `Release readiness` check that fails if any required dependency fails or is skipped.
3. Seed `release` from a known stable commit and provide a valid CODEOWNERS fallback covering all paths. Preserve repository-specific owners; native CODEOWNERS determines who can satisfy ownership review as maintainers change.
4. Preview/apply the protection plan using **Configure release branch protections**, environment **Default**. Current/future public repository reconciliation needs the Meitou-owned administration token to cover All repositories. New repositories receive no Azure permissions automatically.
5. Promote changes through a PR to `release`. Production workflows must pass the central release gate; production tags point at the current release head. Nightlies stay separate. Promote central workflow upgrades through GutenStructure release before updating callers.
6. Add tracking issues to `backlog/project.json`; preview then apply **Synchronize Meitou project**. The Projects token is stored in the **Default environment**, not exposed to build jobs.
7. Enable private Azure artifacts only after the separate broker policy, reader identity, quota checks and reviewed Terraform plan are ready. The current private-artifact audience is **TheIvoryDisaster**.

**Approvals (current revision):** ordinary branches are unprotected; `beta`/`main` require PRs and code-owner review, with PR-only review bypass for the selected `super-maintainers` team to self-merge. Separate CI/safety rules have no bypass. `release` requires **two distinct approving reviewers, including at least one applicable CODEOWNER**, with no bypass. Require fresh approvals, resolved threads and passing up-to-date CI. Code-owner approval counts toward the two; authors cannot approve their own PRs. Do not extend the beta/main exception to release or bypass CI. GitHub does not support formal author self-approval.

**GutenStructure exception:** `main`, `beta` and `release` require PRs and passing CI with **zero required reviewers** and no mandatory code-owner review. Agents may validate and merge routine changes through conceptually grouped PRs. Changes requiring your personal testing must target `beta` and wait for your feedback before promotion to `main` or `release`. You remain the sole administrator; no co-owner is required.

Secrets belong in GutenStructure's **Default environment**: `MEITOU_PROJECT_TOKEN` for project updates; `MEITOU_RELEASE_ADMIN_TOKEN` for organization repository protections. Personally owned GutenStructure protections use a separate `GUTENSTRUCTURE_ADMIN_TOKEN`. The Projects-only token cannot administer branch rules. Never put any token in a caller, source file, issue, chat or public artifact.

Organization-wide rulesets require GitHub Team/Enterprise. The free-tier reconciliation path covers future **public** repositories; future private repositories need a separately reviewed private execution path and plan support. Until protections are applied and verified, production gates must remain closed.

Dependency consumers: [Rivalry Core CI and promotion handoff](docs/dependency-consumer-ci.md), including the TWR baseline caller, beta bootstrap, approval requirements and deferred lock/trigger work.

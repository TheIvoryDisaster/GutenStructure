# GutenStructure

Personally controlled CI automation and Azure infrastructure for the Meitou Modding Ecosystem.

Standard GitHub-hosted runners build public repositories. Azure is reserved for workloads or artifact storage that need it; there is no Azure compute deployment in this baseline.

## Reusable builds

Call `.github/workflows/build-dotnet.yml` or `build-python.yml` from repository CI, pinned to a reviewed **40-character commit SHA**. See [caller examples](examples/README.md). These workflows have read-only repository permissions, no Azure authentication, no artifact publication, and no persisted checkout credentials. Repository build/test code is untrusted.

## Infrastructure and publishing

- [Build inventory](docs/build-inventory.md)
- [Release branch promotion](docs/releases.md)
- [Project synchronization](docs/project-sync.md)
- [Publishing boundary and rollout](docs/publishing.md)
- [Cost assumptions](docs/costs.md)
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

**Approvals:** organization repositories require **two distinct approving reviewers, including at least one applicable CODEOWNER**, on both `main` and `release`. Require fresh approvals, resolved threads and passing up-to-date CI. Code-owner approval counts toward the two; authors cannot approve their own PRs. Do not lower these requirements or add a bypass.

**GutenStructure exception:** `main`, `beta` and `release` require PRs and passing CI with **zero required reviewers** and no mandatory code-owner review. Agents may validate and merge routine changes through conceptually grouped PRs. Changes requiring your personal testing must target `beta` and wait for your feedback before promotion to `main` or `release`. You remain the sole administrator; no co-owner is required.

Secrets belong in GutenStructure's **Default environment**: `MEITOU_PROJECT_TOKEN` for project updates; `MEITOU_RELEASE_ADMIN_TOKEN` for organization repository protections. Personally owned GutenStructure protections use a separate `GUTENSTRUCTURE_ADMIN_TOKEN`. The Projects-only token cannot administer branch rules. Never put any token in a caller, source file, issue, chat or public artifact.

Organization-wide rulesets require GitHub Team/Enterprise. The free-tier reconciliation path covers future **public** repositories; future private repositories need a separately reviewed private execution path and plan support. Until protections are applied and verified, production gates must remain closed.

### Mod storefront publishing (beta spike)

[Steam Workshop and Nexus publishing](docs/mod-distribution.md) documents author setup, initial uploads, credential isolation and the release handoff. The original offline planner and CI preview perform **no uploads**. The author-owned workflow described below adds opt-in Nexus publishing; destination IDs and live author validation are pending. Changes need owner feedback on beta before production promotion.

Authors can call the [author-owned reusable publisher](docs/author-publisher.md) from their own personal repositories. Nexus is explicit opt-in with credentials kept in the author's environment; Steam remains preview-only. The beta PR requires owner testing before production promotion.

For adoption in your own repository, start with the [copyable caller](examples/author-publisher/publish.yml) and [setup, extension and troubleshooting guide](docs/author-publisher.md). Agents should use the dedicated [author publishing skill](.agents/skills/author-publishing/SKILL.md).

[RimWorld Workshop preparation](docs/rimworld-workshop.md) supports existing releases in a personally owned caller repository, including private sources. It validates/stages the release and generates a Workshop preview without any Steam credentials or upload operation.

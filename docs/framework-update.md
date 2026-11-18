# Framework update

[framework-update.yml](../.github/workflows/framework-update.yml) keeps a mod repository's [framework lock](framework-lock.md) on the newest
published releases. When a framework (Rivalry Core, Logistics Core, ...) publishes a release, the next run moves `meitou.lock.json` to it,
builds and tests the mod, and opens a PR into `beta` that it merges when the mod's CI is green. A PR that fails stays open as the regression
report. It polls releases on a schedule, so no framework repository needs a token for its dependents.

## Use it

`.github/workflows/framework-update.yml` in the mod repository:

```yaml
name: Framework update
on:
  schedule:
    - cron: '17 */6 * * *'
  workflow_dispatch:
permissions:
  contents: read
jobs:
  update:
    permissions:
      contents: write
      pull-requests: write
      actions: write
    uses: TheIvoryDisaster/GutenStructure/.github/workflows/framework-update.yml@<GutenStructure commit>
```

- The CI workflow (`ci-workflow`, default `ci.yml`) must accept `workflow_dispatch`: a PR opened by the workflow's token starts no
  workflows, so the update dispatches CI on its branch, and the checks land on the PR's commit.
- `build/gutenstructure` must be pinned to a GutenStructure commit that has `scripts/framework_update.py`.
- Repository settings > Actions > General: "Allow GitHub Actions to create and approve pull requests".

## What a run does

1. For each locked framework, finds the newest immutable release on `channel`: `release` (default) takes `<slug>-v<version>`; `beta` also
   takes `<slug>-<version>-beta.<commit>` snapshots. The rolling `<slug>-beta` never.
2. Hashes the release's zip and checks it against the release notes' `Zip SHA-256`; takes the engine commit from `Submodule engine at`. All
   locked frameworks must then name one engine commit, else the run fails.
3. With `widen-ranges` (default on), a mod whose `dependencies` range excludes the new version gets its upper bound raised to the next breaking
   version (`<0.7.0` to `<0.8.0` for 0.7.x; `<2.0.0` to `<3.0.0` for 2.x).
4. Moves `engine` to that commit, builds and tests `test-project` with the strict engine check.
5. Commits the lock, the widened manifests and the engine pointer to `framework-update/<channel>`, opens or updates one PR into `base`,
   dispatches CI on it and waits.
6. Merges it (`merge`, default on) when both the run's tests and CI pass. Org repositories allow this on `beta` only: GitHub Actions has
   PR-only review bypass there ([releases](releases.md)). Where a base branch's rules still need a review, the PR stays open, green, for a
   maintainer to merge. A failing PR stays open and the run fails.

A run that finds nothing newer, or the same releases an open PR already holds, changes nothing.

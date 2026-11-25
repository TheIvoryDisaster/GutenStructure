# Framework update

[framework-update.yml](../.github/workflows/framework-update.yml) keeps a mod repository's [framework lock](framework-lock.md) on the newest
published releases. When a framework (Rivalry Core, Logistics Core, ...) publishes a release, the next run moves `meitou.lock.json` to it,
builds and tests the mod, and opens a PR into `beta`. Under permanent revision 5, a super-maintainer reviews/merges it after CI passes. A PR that fails stays open as the regression
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
    with:
      channel: beta
      tools-ref: <the same GutenStructure commit>
    secrets:
      app-id: ${{ secrets.MEITOU_BOT_APP_ID }}
      app-key: ${{ secrets.MEITOU_BOT_KEY }}
```

Secrets `app-id`/`app-key` (optional, passed by name, never `secrets: inherit`): the org bot GitHub App (org secrets `MEITOU_BOT_APP_ID`,
`MEITOU_BOT_KEY`; Contents and Pull requests read/write). With them the PR is opened with the App's token, so the caller's `pull_request`
CI runs on it, beta's required check counts it and the workflow merges the PR once that run's Development readiness passes. Without them
the PR (workflow token) gets no `pull_request` CI: the workflow dispatches CI itself and a maintainer merges the PR.

- `channel: beta` for every dependent: each framework beta merge publishes an immutable snapshot, so a dependent's tests run against it
  within 6 hours and a failing PR reports the break before the framework's production release. `release` (the input's default) moves only on
  production tags.
- `base` (default `beta`) must be a branch the repository has: a repository with only `main` sets `base: main`.

- The CI workflow (`ci-workflow`, default `ci.yml`) must accept `workflow_dispatch`: a PR opened by the workflow's token starts no
  workflows, so the update dispatches CI on its branch, and the checks land on the PR's commit.
- `tools-ref` (the same commit as the `uses:` pin) runs the update script from that GutenStructure commit. Without it the script comes from
  `build/gutenstructure`, which must then be pinned to a commit that has `scripts/framework_update.py`.
- Repository settings > Actions > General: "Allow GitHub Actions to create and approve pull requests".

## What a run does

1. For each locked framework, finds the newest immutable release on `channel`: `release` (default) takes `<slug>-v<version>`; `beta` also
   takes `<slug>-<version>-beta.<commit>` snapshots. The rolling `<slug>-beta` never.
2. Hashes the release's zip and checks it against the release notes' `Zip SHA-256`; takes the engine commit from `Submodule engine at`. All
   locked frameworks must then name one engine commit, else the run fails.
3. With `widen-ranges` (default on), a mod whose `dependencies` range excludes the new version gets its upper bound raised to the next breaking
   version (`<0.7.0` to `<0.8.0` for 0.7.x; `<2.0.0` to `<3.0.0` for 2.x). The PR is then labelled `needs-release`: players' installed
   copies keep the old range until the mod is released, so a widened mod whose version is already released moves to the next patch
   ([versioning](versioning.md), "Automatic patch bumps").
4. Moves `engine` to that commit, builds and tests `test-project` with the strict engine check.
5. Commits the lock, the widened manifests and the engine pointer to `framework-update/<channel>`, opens or updates one PR into `base`,
   dispatches CI on it and waits.
6. Merges it (`merge`, default on) when the run's tests and the CI's Development readiness pass. Without the bot App (Secrets above)
   beta's required check refuses the merge ([policy](branch-policy.md)); the PR then stays open, green, for a maintainer to merge. A failing PR stays open and the run fails.

A run that finds nothing newer, or the same releases an open PR already holds, changes nothing.

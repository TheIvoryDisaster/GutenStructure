# Engine update

[engine-update.yml](../.github/workflows/engine-update.yml) keeps each mod repository's `engine` submodule on the newest upstream Meitou
build, so mods are always developed against the Meitou that testers run. It follows [versioning](versioning.md).

## Set up a caller

`.github/workflows/engine-update.yml` in the mod repository:

```yaml
name: Engine update
on:
  schedule:
    - cron: '23 */3 * * *'
  workflow_dispatch:
permissions:
  contents: read
jobs:
  update:
    permissions:
      contents: write
      pull-requests: write
      actions: write
    uses: TheIvoryDisaster/GutenStructure/.github/workflows/engine-update.yml@<commit>
    with:
      tools-ref: <commit>
    secrets:
      app-id: ${{ secrets.MEITOU_BOT_APP_ID }}
      app-key: ${{ secrets.MEITOU_BOT_KEY }}
```

Secrets `app-id`/`app-key` (optional, passed by name, never `secrets: inherit`): the org bot GitHub App (org secrets `MEITOU_BOT_APP_ID`,
`MEITOU_BOT_KEY`; Contents and Pull requests read/write). With them the PR is opened with the App's token, so the caller's `pull_request`
CI runs on it, beta's required check counts it and the workflow merges the PR once that run's Development readiness passes. Without them
the PR (workflow token) gets no `pull_request` CI: the workflow dispatches CI itself and a maintainer merges the PR.

Inputs: `base` (default `beta`), `ci-workflow` (default `ci.yml`, must accept `workflow_dispatch`), `test-project` (default `.`), `merge`
(default `true`), `tools-ref` (the same commit as the `uses:` pin), `dotnet-version`.

## What it does

- Picks the newest tag of VlcekM/MeitouClient: a nightly (`vX.Y.Z-nightly.<date>[.<n>]`, built from `master` twice a day when the game
  changed) or a full release, whichever is newer in SemVer.
- Does nothing when the engine is already on it, or when `meitou.lock.json` locks frameworks: that repository follows its frameworks' engine,
  and [framework-update](framework-update.md) moves it once the framework has moved.
- Otherwise moves together ([versioning](versioning.md), "`gameVersion`"):
  - the `engine` submodule to the tag's commit;
  - `Directory.Build.rsp` to `-p:AssemblyVersion=<X.Y.Z>.0`, where `X.Y.Z` is the tag's release (a nightly counts as the release it leads
    to, as the game does);
  - each mod's `gameVersion` floor to `>=X.Y.Z`, dropping a cap at or below it;
  - a mod version already released to the next patch (`scripts/release_bump.py`).
- Builds and tests on the new engine, commits to `engine-update/upstream`, opens `Meitou: Move engine to <tag>` labelled `needs-release`,
  waits for the caller's CI and merges when its Development readiness passes (with the bot App; see Secrets above).
- A red PR stays open: the new Meitou broke something. Port it in that PR (skill `meitou-engine-release`).

framework-update also moves the floor after it moves the engine to a lock's commit, when that commit carries a Meitou tag
(`scripts/engine_update.py --engine`).

## What it costs players

A floor on a nightly admits only that nightly and later. Players on the newest full release can't load a mod released from it until the
next full release ships; the [Meitou compatibility watch](meitou-compat.md) warns about it.

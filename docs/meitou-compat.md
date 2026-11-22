# Meitou compatibility watch

[meitou-compat.yml](../.github/workflows/meitou-compat.yml) checks a mod repository daily against the Meitou releases its players will run,
so a Meitou change that breaks a mod shows up as an issue before a player meets it. It follows [versioning](versioning.md).

## Set up a caller

`.github/workflows/meitou-compat.yml` in the mod repository:

```yaml
name: Meitou compatibility
on:
  schedule:
    - cron: '17 6 * * *'
  workflow_dispatch:
permissions:
  contents: write
  issues: write
  pull-requests: write
  actions: write
jobs:
  compat:
    uses: TheIvoryDisaster/GutenStructure/.github/workflows/meitou-compat.yml@<commit>
    with:
      tools-ref: <commit>
```

Inputs: `base` (default `beta`; a repository without one passes `main`), `ci-workflow` (default `ci.yml`, must accept `workflow_dispatch`),
`lift-caps` and `merge` (default `true`), `tools-ref` (the same commit as the `uses:` pin), `dotnet-version`.

## What it checks

- Builds each mod: a top-level folder holding `meitou.json` and `<Folder>/<Folder>.csproj`. The build fetches the locked frameworks.
- Runs [RefCheck](../tools/refcheck/Program.cs) on each mod assembly against:
  - the newest full Meitou release (`vX.Y.Z` tags of VlcekM/MeitouClient);
  - the newest nightly, when it is newer than that release;
  - the oldest full release each mod's `gameVersion` admits (its floor).
- Also checks each locked framework assembly against the same releases, where the framework's own `gameVersion` admits that release.
- RefCheck reports two kinds of break. A **missing member** is a method, constructor or field the DLL references by name and parameter types
  that the release lacks. A **newer stamp** is an engine assembly the DLL references at a higher version than the release's, which the game
  refuses.
- Checks that the newest full release is inside each `gameVersion`. A mod whose floor is above it (built for a Meitou only nightlies have
  yet) is a warning, and a release below a mod's floor isn't checked for that mod.
- Reads each release's code-mod API version (`Meitou.Modding.ModApi.Version`).

## What it does

- **One issue** labelled `meitou-compat`, opened, updated and closed by the watch. It lists each problem and a table of every check.
  - A problem against a full release or a floor fails the run.
  - A problem only in a nightly is a warning: it adds the label `meitou-compat: nightly` and doesn't fail the run.
- **Cap lift.** When the newest full release is above a `gameVersion` cap, the watch can lift it to the next patch above that release
  (`<0.22.2` to `<0.22.3` for 0.22.2). It does so when:
  - nothing is missing from that release;
  - its code-mod API version matches the newest release the range already admits.
  A lifted mod whose version is already released moves to the next patch ([versioning](versioning.md), "Automatic patch bumps").
  The watch then commits the manifests to `meitou-compat/cap-lift`, opens `Meitou: Admit <tag>` labelled `needs-release` and dispatches
  the caller's CI. It merges when CI is green and the branch rules allow, like [framework-update](framework-update.md).
- Where the code-mod API changed, the issue asks for a play test and a manual lift instead. RefCheck can't see behaviour: 0.22.2 made
  `HoldPlatoon` off-screen only, with every member still present.
- A missing member is a port: follow [versioning](versioning.md) "A breaking change".

## Run it locally

```sh
dotnet build <GutenStructure>/tools/refcheck/RefCheck.csproj -c Release -o /tmp/refcheck
python3 -I <GutenStructure>/scripts/meitou_compat.py --refcheck /tmp/refcheck/RefCheck.dll --out /tmp/compat
```

Run it from the mod repository's root. `--tags v0.22.0 v0.22.1` picks targets from the given tags instead of MeitouClient's.
`dotnet /tmp/refcheck/RefCheck.dll check <mod.dll> <folder with a release's Meitou*.dll>` checks one assembly.

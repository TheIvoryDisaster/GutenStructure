# Framework lock

A Meitou mod repository builds against frameworks (Rivalry Core, Logistics Core, ...) published as release assets in other repositories,
named in `meitou.lock.json` at its root and resolved by `msbuild/Meitou.Frameworks.targets`. The
[consumer smoke workflow](../.github/workflows/framework-consumer.yml) proves it on every change here: a repository with no framework source
builds and tests [a sample mod](../examples/framework-consumer) against `rivalry-core-v0.6.0`, and a wrong hash, engine or range fails.

## Set up a consumer

1. Add GutenStructure as a submodule pinned to a release commit:
   `git submodule add https://github.com/TheIvoryDisaster/GutenStructure.git build/gutenstructure`, then
   `git -C build/gutenstructure checkout --detach <release commit>`.
2. `Directory.Build.targets` at the repository root:
   ```xml
   <Project>
     <Import Project="build/gutenstructure/msbuild/Meitou.Frameworks.targets" />
   </Project>
   ```
3. `meitou.lock.json` at the repository root, one entry per framework in the chain, copied from each release's notes:
   ```json
   {
     "format": 1,
     "frameworks": [
       {
         "id": "rivalry.core",
         "repo": "Meitou-Modding-Ecosystem/MeitouMods",
         "tag": "rivalry-core-v0.6.0",
         "asset": "RivalryCore-0.6.0.zip",
         "sha256": "f2e90568678b6a8803d78ac3f254c172e024a2ebecbbc15ae1c157aaa4ebabd4",
         "folder": "RivalryCore",
         "engine": "1cc76a0bed94d55408e0521d10cf8c8c20c57417"
       }
     ]
   }
   ```
4. Add `deps/` to `.gitignore`.

## What a build does

- Applies to every project with a `meitou.json` (a mod: frameworks referenced with `Private="false"`, never shipped) and every test project
  (copied, so tests load them).
- Downloads each asset once from `https://github.com/<repo>/releases/download/<tag>/<asset>` into `deps/<tag>/`, checks its SHA-256, extracts
  it and references the assemblies its `meitou.json` lists. A wrong hash fails the build and leaves nothing in `deps/`.
- Checks every dependency range in the present manifests (the repository's mods and the locked frameworks) against the versions present; a
  missing non-optional dependency or a version outside the range fails the build.
- Checks that every locked framework names one engine commit and that `engine/` is checked out at it: an error on CI, a warning locally.
- `MeitouResolveFrameworks` also returns `MeitouFrameworkFolder` items (each extracted mod folder, `ModName` metadata) for a Play project to
  deploy.

## Build a framework from a local clone

In the consumer's git-ignored `Meitou.user.props`, imported by its `Directory.Build.props`:

```xml
<Project>
  <PropertyGroup>
    <MeitouFrameworkSources>C:\src\MeitouMods\RivalryCore\RivalryCore.csproj</MeitouFrameworkSources>
    <MeitouEngineDir>C:\src\MeitouMods\engine\</MeitouEngineDir>
  </PropertyGroup>
</Project>
```

- Each listed project (`;`-separated, full paths) replaces the locked asset with the same id (read from the `meitou.json` beside it) as a
  project reference; the engine check is skipped.
- `MeitouEngineDir` points the consumer's engine references at the clone's engine, so the build holds one engine. Consumer projects reference
  the engine as `$(MeitouEngineDir)src/...` for this to apply.
- Both settings reach the framework project as globals, so a framework that imports this file resolves its own frameworks from the same
  clones (chains); engine references drop them again, so the engine builds once.

## Moving the lock

A PR edits `meitou.lock.json` (and the engine submodule when the lock's engine changes). Pin immutable tags only: `<slug>-v<version>` or
`<slug>-<version>-beta.<commit>`, never the rolling `<slug>-beta`. In a chain, a layer moves its lock only after the layer it depends on has
published the release it locks.

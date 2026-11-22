# Versioning

How frameworks (Rivalry Core, Logistics Core, ...), mods and their Meitou ranges are versioned, so a new Meitou or framework release refuses
as few players' mods as possible. Meitou ships nightlies daily, so these rules are for agents to follow without being asked.

## What the loader does

- A mod whose `gameVersion` excludes the running Meitou is refused.
- A dependency, **optional ones included**, that is loaded with a version outside the dependent's range gets the **dependent** refused, not
  left out (MeitouClient `docs/modding-dependencies.md`, "Dependency state").
- A DLL built against a higher engine assembly version than the running game's is refused ("entry type ... is not in its assemblies"): .NET
  never binds a reference to an older assembly. Releases stamp the engine with the game's version (`0.22.1.0`); the submodule builds
  `1.0.0.0`.

## Frameworks (before 1.0)

- Bump the **minor** version only when the **dependent contract** changes: a public type, member or signature dependents call, or a
  documented behaviour they rely on. Each framework lists its contract (Rivalry Core: `.github/RELEASING.md`).
- Everything else is a **patch**: fixes, new optional members, internal changes, and a new Meitou target with the same contract (a port to a
  Meitou that removed something the framework used internally). Dependents' `<0.X+1.0` ranges keep working.
- A behaviour change dependents can observe but that keeps their code correct (e.g. a claim that frees a slot sooner) is a patch; one that
  makes their correct code wrong is a minor bump.

## Dependency ranges

`">=<first version with everything you use> <<next minor>"`, e.g. `>=0.6.2 <0.7.0`. Never cap below the next minor. A framework minor bump
needs a release of every dependent with the widened range: [framework-update](framework-update.md) widens it in the repository and labels
the PR `needs-release`.

## `gameVersion`

- **Floor**: the oldest Meitou release the mod is built and stamped for. Keep `Directory.Build.rsp` (`-p:AssemblyVersion=<floor>.0`) and
  the floor equal.
- **Cap**: only below a release where a break is **known** (RefCheck or a test found it), e.g. `<0.22.2` once 0.22.2 removed a member the
  mod calls. Never cap below an untested release ahead of time.
- When a full release is outside a cap and nothing broke, lift the cap to just above that release in a patch release.

## Engine pin

- A repository with a [framework lock](framework-lock.md) uses the locked frameworks' engine commit; framework-update moves both together.
- A repository without frameworks pins the `engine` submodule to an upstream Meitou release tag, not a development commit.

## A breaking change: what the agent does

1. Bump the framework's minor version in `meitou.json` (its contract guard test fails otherwise, where the framework has one).
2. Add a **Dependents** section to the PR body: each dependent repository, what it calls that changed, and what it must do.
3. After the framework's beta release is out, check each dependent's framework-update PR. Where its tests fail, open the fix PR in that
   repository; where they pass, it only needs the release its `needs-release` label asks for.
4. In a chain, the layer above moves only after the layer it depends on has published.

A Meitou change found by RefCheck follows the same steps in the repository that calls the removed member: a patch release that ports it, with
a `gameVersion` floor at the release that needs the port when the old and new calls can't coexist.

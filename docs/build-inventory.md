# Build inventory

Initial inspection: 2026-11-16. Recheck manifests before enabling each caller.

| Repository | Branch | Build/check | Additional requirements |
| --- | --- | --- | --- |
| MeitouClient | fork (master mirrors upstream) | .NET 11 build; tests excluding Slow/Bench for PRs | Release matrix: Windows, Linux, macOS; native dependencies; legacy macOS uses .NET 10 |
| RivalryCore | beta, main | .NET 11 build/test | Recursive pinned engine submodule; existing CI is the pilot for reusable .NET CI; Rivalry Core beta prereleases are the pilot for `package-meitou-mod.yml` |
| PZAKenshiMotionLab | master | Python pipeline/no-Pillow/fuzz checks | numpy/Pillow; Blender headless check is separate |
| TheWastelandRemembers | main | Engine-free C# rules tests; inspect Python checks | Release generation needs privately supplied Kenshi data and engine binaries |
| PZAMeitouUi | master | Validate through consuming probe | Source library; no standalone project in root |
| PZAMeitouUiProbe | master | PowerShell build and offline integration check | Sibling UI source checkout, engine binaries and licensed Kenshi resources |

Do not treat a skipped asset-dependent test as a verified integration build. Separate required engine-free checks from optional integration jobs. Never upload proprietary Kenshi resources to public artifacts or caches.

Roll out one repository at a time, preserving existing required check names until branch rules are migrated. Pin central workflows to reviewed commits. Cancel superseded PR builds and avoid packaging on documentation-only changes where the dependency graph permits it.

UI compile checks use the published Meitou 0.20.1 Windows release pinned by SHA-256, with companion source pinned by commit. They run without Kenshi assets. They do not claim to verify in-game behavior or the asset-dependent offline integration check.

## Framework dependents

Checked 2026-11-22 on each repository's integration branch. Every repository with a locked framework calls
[framework-update](framework-update.md) on `channel: beta` ([versioning](versioning.md)).

| Repository | Base | Locked frameworks | framework-update |
| --- | --- | --- | --- |
| AshenHand | beta | `rivalry-core-0.6.5-beta.39661ed` | `7bbd01b`, beta channel |
| Dustlife | main (no beta) | `rivalry-core-0.6.5-beta.39661ed` (Dustlife#4) | `7bbd01b`, beta channel, `base: main` |
| MeitouModTemplate | beta | none | `7bbd01b`, beta channel (copied into new repositories) |
| Bathhouse, WarOrchestration | beta | none | `7bbd01b`, beta channel |
| Husbandry, SquadArena, LogisticsCore | beta | none | no caller: add the template's when a framework is locked |
| TheWastelandRemembers | beta | no lock (reaches Rivalry Core by reflection) | no caller |


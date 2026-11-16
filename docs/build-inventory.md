# Build inventory

Initial inspection: 2026-11-16. Recheck manifests before enabling each caller.

| Repository | Branch | Build/check | Additional requirements |
| --- | --- | --- | --- |
| MeitouClient | fork (master mirrors upstream) | .NET 11 build; tests excluding Slow/Bench for PRs | Release matrix: Windows, Linux, macOS; native dependencies; legacy macOS uses .NET 10 |
| MeitouMods | beta, main | .NET 11 build/test | Recursive pinned engine submodule; existing CI is the pilot for reusable .NET CI |
| PZAKenshiMotionLab | master | Python pipeline/no-Pillow/fuzz checks | numpy/Pillow; Blender headless check is separate |
| TheWastelandRemembers | main | Engine-free C# rules tests; inspect Python checks | Release generation needs privately supplied Kenshi data and engine binaries |
| PZAMeitouUi | master | Validate through consuming probe | Source library; no standalone project in root |
| PZAMeitouUiProbe | master | PowerShell build and offline integration check | Sibling UI source checkout, engine binaries and licensed Kenshi resources |

Do not treat a skipped asset-dependent test as a verified integration build. Separate required engine-free checks from optional integration jobs. Never upload proprietary Kenshi resources to public artifacts or caches.

Roll out one repository at a time, preserving existing required check names until branch rules are migrated. Pin central workflows to reviewed commits. Cancel superseded PR builds and avoid packaging on documentation-only changes where the dependency graph permits it.

UI compile checks use the published Meitou 0.20.1 Windows release pinned by SHA-256, with companion source pinned by commit. They run without Kenshi assets. They do not claim to verify in-game behavior or the asset-dependent offline integration check.

# Author-controlled Nexus publishing

Steam Workshop updates now use the [local Workshop Watcher](workshop-watcher.md). This reusable publisher handles Nexus only; it never reads Steam credentials, generates VDFs or runs SteamCMD. It is staged on beta and requires a real author-owned upload test before promotion.

## Initial Nexus setup

Create the mod page and manually upload its first file on Nexus. In the Files tab enable Advanced to obtain the **file ID**, or find it in Manage Files. Use the existing file's v3 ID, not the mod ID, version ID or Workshop ID. The official Nexus-Mods/upload-action adds a version to that existing file; it does not create the initial page/file.

Create/use a personally owned publisher repository. Copy [the caller template](../examples/author-publisher/publish.yml) to `.github/workflows/publish.yml`; set the source repository and existing file ID as reviewed configuration. Replace the placeholder SHA with a reviewed 40-character GutenStructure commit reachable from release after testing. Do not expose file ID or source repository as arbitrary run inputs. Do not use `secrets: inherit`.

In the personal caller's Settings → Environments create `nexus-publish`. Restrict it to the default publishing branch and require your approval where supported by your GitHub plan. Keep prevent-self-review off if you both dispatch and approve. Add **environment secret `NEXUSMODS_API_KEY`**, obtained from https://www.nexusmods.com/settings/api-keys using the appropriate account/team upload rights. Never put another author's key in GutenStructure, an organization repo or Azure. Review the official action and current Nexus API terms before enabling uploads; this design uses author-initiated runs rather than background uploads using collected user keys.

## First test

Dispatch from your personal repo's default branch as its owner. Supply the exact public organization release tag, current protected release-head SHA, ZIP asset ID/hash and desired version. Leave `publish-nexus` false first. The preparation job verifies source organization ID, stable tag/commit, release protections, asset membership, size/hash and bounded archive paths. A `.mod` must exist; this Meitou/Kenshi adapter is not a generic RimWorld uploader. Current release-gate semantics require the tag at the *current* release head, so an old release may be rejected after later promotions.

Inspect the run summary. Then start a fresh dispatch with the same reviewed inputs and `publish-nexus: true`, and approve the environment. The upload job repeats validation after approval and uses the official action pinned to a full commit. It retains old versions and does not change the mod's displayed version or default mod-manager download. Confirm the resulting version receipt and downloaded ZIP hash on Nexus. Preview success does not prove authentication, upload rights or publication.

Receipts and plans are in the caller's run summary to avoid artifact-storage quota. Rerunning an existing run cannot upload; a fresh dispatch can still duplicate an upload. Inspect Nexus before retrying any ambiguous failure. Durable per-file deduplication and automated release-event publishing are not implemented. Keep updates manual/owner-initiated until the live API behavior and terms are confirmed.

## Steam cleanup

Rimshi's superseded hosted upload and preview workflows can be removed now that the watcher handles releases locally. Remove obsolete `STEAM_USERNAME`, `STEAM_PASSWORD` and `STEAM_GUARD_CODE` secrets from its `steam-publish` environment after confirming no remaining consumer. Retire that environment if unused. Keep the watcher, its local Steam session and its private-repository GitHub token: those serve the replacement path. Revoke unwanted Steam sessions through Steam; deleting a GitHub secret does not revoke a Steam session.

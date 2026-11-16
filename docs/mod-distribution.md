# Steam Workshop and Nexus release publishing spike

Status: **offline planning and tests only**, targeting GutenStructure `beta` for owner feedback. No author credentials are requested or read, and no upload code runs. Neither filling in IDs nor changing a workflow input can enable publishing; the planner rejects a registry with live publishing enabled. This is separate from private Azure debug artifacts.

## Proposed release path

A successful, complete build from the organization's protected `release` branch produces a versioned archive and SHA-256 manifest. After the central release gate and author environment approval, a trusted, SHA-pinned publisher consumes that exact artifact. Nexus receives the ZIP; Steam receives a verified staging tree from the same archive. Record GitHub SHA, version, payload hash and destination/version IDs as publication receipts. Retry each destination independently; a Nexus failure must not cause a second Steam upload.

Use a reusable publishing job in the original release workflow, after successful build/package jobs. A second workflow listening for a GitHub Release created with `GITHUB_TOKEN` will generally not be triggered. Do not rebuild from a mutable branch, execute scripts from mod artifacts, or load author credentials into builds or PR jobs. Release branch protection remains two approvals including an applicable CODEOWNER. Each author should approve use of their own publisher environment; this is an additional distribution approval, not a substitute for PR review.

## Author onboarding

| Service | Initial author setup | Later automation |
| --- | --- | --- |
| Nexus Mods | Create the mod page and upload its first file manually. Record the mod ID and the **file ID**, which is distinct from a version ID. Confirm the API-key owner may upload to that file. | The official action adds a new version to that existing file through its v3 API. It does not bootstrap a page or first file. |
| Steam Workshop | Recommended for Kenshi: publish the first item through FCS, accept the Workshop legal agreement, and record the item ID and publishing account. | Valve documents SteamCMD creation and updates, but Kenshi compatibility, publisher permissions and Steam Guard/session handling must be demonstrated on one existing item before enabling automation. |

The Nexus action was inspected at `98532f7670c27cbecc78fae03fa3e278147827e2`. Its required inputs are `api_key`, `file_id`, `filename` and `version`; `mod_id` is required for changelogs. Pin the reviewed action commit when implementation is enabled. API keys are user credentials and may cover other mods; do not assume file-level scoping. Confirm the author account and permissions with the author rather than inferring them from a GitHub username. Keep archive-old-version, default-download and mod-version changes disabled until tested.

SteamCMD uses a Steam account login, not merely a Steam Web API key. Steam Guard may require interactive authorization; do not promise password-only unattended publishing. A separate publishing account is an option only if its game access and permission to update the intended item are verified. Automation must use a positive existing `publishedfileid`, never zero or missing, to avoid duplicate pages. Generic SteamCMD support does not establish that Kenshi's Workshop path works; Valve describes this CLI path for testing. Subscriber installation and in-game loading are part of the acceptance test. If SteamCMD cannot correctly update Kenshi items, retain manual FCS publishing and automate only packaging, checksums and release instructions.

Do not paste credentials into chat or add them to registry files. Later, an author or the personal infrastructure owner must configure an author-specific protected environment in the trusted publishing repository. Store the Nexus key and Steam credentials/session material as secrets; approve only the intended release branch. Steam passwords/session files must never appear in command logs, Actions caches or artifacts. Session persistence, encryption, revocation and Steam Guard recovery need a tested design before a live Steam job is added. No shared credentials across authors and no `secrets: inherit`.

## What works now

`distribution/targets.json` registers Rivalry Core, Ashen Hand and Husbandry with empty destination IDs. This does not assert that anyone has publishing rights. The planner reports missing setup and always returns `would_publish: false`:

```sh
python scripts/distribution_plan.py --mod rivalry-core --version 1.2.3
python scripts/distribution_plan.py --mod rivalry-core --version 1.2.3 --archive /path/to/release.zip
python -m unittest discover -s tests -p test_distribution_plan.py -v
```

The optional ZIP check computes the payload digest, checks CRCs, rejects unsafe paths, links, encryption and duplicate names, bounds archive/expanded sizes, and requires an FCS `.mod` file. It does **not** prove that runtime DLLs, dependencies or licensed assets are correctly packaged. There is no extraction or code execution. The 96 MiB archive limit is a conservative spike limit, not a Steam/Nexus platform limit.

After an existing Workshop ID is recorded locally, `--vdf /tmp/workshop-preview.vdf --content-folder /tmp/verified-mod-content` writes a non-overwriting VDF preview. It includes no login or credentials and runs no command. The caller remains responsible for constructing and verifying a staging directory; no automatic unpacking is implemented. The CI/dispatch preview exercises plans with read-only repository access and no secrets. On a beta PR it runs via `pull_request`; manual dispatch becomes available after the workflow reaches the default branch.

## TODO before any live publisher

1. Author confirms each mod's public URLs, immutable Workshop/mod/file IDs, author identity and update rights. Record IDs through a reviewed registry PR; never infer them by matching a title.
2. Verify complete packaging and licenses for each mod, including Meitou runtime requirements. Use an author-approved low-risk test item and complete archive.
3. Test Nexus with that author's key: existing-file update, displayed version, download contents/hash and receipt. Test SteamCMD for Kenshi: authenticated existing-item update, Steam Guard, unchanged ownership, subscriber download and in-game load. Record the tested method or FCS fallback.
4. Design central secret isolation. Org owners must not gain personal publisher credentials by changing a caller workflow. Validate immutable owner/repo IDs, release SHA, exact pinned caller/publisher workflow, allowed target and artifact identity before releasing credentials. Untrusted caller inputs must not choose arbitrary file paths, commands, accounts or target IDs. Keep public builds separate from privileged publish jobs.
5. Add a live adapter only after owner feedback on the beta spike: explicit opt-in, author environment approval, pinned dependencies, audit receipts, duplicate/replay protection and partial-failure recovery. Validate that preview tests cannot reach live APIs. Do not use a dry-run success as proof of a successful upload.

These steps need author input later; none is needed to review the current offline spike. Track live validation in [MeitouMods #41](https://github.com/Meitou-Modding-Ecosystem/MeitouMods/issues/41) and [#42](https://github.com/Meitou-Modding-Ecosystem/MeitouMods/issues/42).

## Sources

- [Nexus official action and initial-file requirement](https://github.com/Nexus-Mods/upload-action/tree/98532f7670c27cbecc78fae03fa3e278147827e2)
- [Nexus API key settings](https://www.nexusmods.com/settings/api-keys)
- [Valve Workshop implementation / SteamCMD](https://partner.steamgames.com/doc/features/workshop/implementation)
- [Kenshi FCS Workshop publishing background](https://kenshi.fandom.com/wiki/Steam_Workshop)

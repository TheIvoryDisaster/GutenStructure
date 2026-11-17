# RimWorld Workshop update preparation

The reusable `.github/workflows/rimworld-workshop-preview.yml` consumes an existing release **in the personal caller repository**, including private repositories using that caller's read-only `GITHUB_TOKEN`. No cross-repository PAT, platform credentials, `secrets: inherit` or Azure access is required. It never logs into Steam or uploads. This is a separate preparation adapter from the Meitou-specific Nexus publisher; it does not weaken that publisher's protected-release requirements.

The caller supplies `release-tag`, `asset-id`, `expected-sha256`, `package-id` and an existing `workshop-item-id`. Pin the reviewed central workflow commit. The helper verifies the caller's immutable owner/repository IDs, personally owned source, stable release, tag ancestry in default-branch history, asset membership and GitHub/downloaded SHA-256. The default-branch ancestry check supports personal beta → main release processes; it does not prove PR approval or enforce the Meitou organization's two-review rule on personal repos.

The ZIP must have one mod root, valid `About/About.xml`, the expected package ID, matching `About/PublishedFileId.txt`, PNG `About/Preview.png` and mod assemblies for every advertised game version. It rejects traversal, duplicates, symlinks, encrypted archives, source/control metadata, known game/framework DLLs and oversized archives (96 MiB compressed / 512 MiB expanded). The plan and VDF are written to the caller run summary without consuming artifact storage. Optional `save-preview-artifact: true` retains the staged mod/plan/VDF for one day **in the caller repository**, if its artifact quota permits; default is false. No private mod content is uploaded to GutenStructure. Binary contents are not executed or proven to work in game.

The VDF has RimWorld app ID `294100` and a positive existing item ID. It omits visibility/title/description/previewfile. No claim is made that a future live SteamCMD update preserves remote metadata merely because those fields are omitted; that behavior must be verified before enabling an uploader. An unlisted item's visibility and ownership cannot be established by this offline preview. Zero/missing IDs are rejected to prevent accidentally creating new items.

## Local preview

After downloading your release ZIP through GitHub's normal authenticated access:

```sh
python -m scripts.rimworld_workshop --archive /path/to/mod.zip \
  --sha256 YOUR_64_CHARACTER_SHA256 --package-id YourAuthor.YourMod \
  --item-id YOUR_EXISTING_ITEM_ID --output /tmp/my-workshop-preview
```

The output directory must not already exist. No credentials are needed for local archive validation. The VDF's absolute content path is specific to the staging location: downloading an Actions artifact does not make the runner path valid locally. Regenerate for the local location rather than executing the runner VDF unchanged.

## Steam credentials: not needed yet

**Do not add Steam credentials to run this preview.** It has no Steam adapter or secret inputs. A successful dry run confirms artifact preparation, not Steam authentication, ownership, subscriber installation or upload compatibility.

If a future permitted and reviewed Steam adapter is enabled, credentials should stay in an environment named `steam-publish` in **your personal mod/publisher repository**, not GutenStructure or the organization. The prospective setup is:

1. Settings → Environments → New environment → `steam-publish`.
2. Require your review, restrict it to the personally approved publishing branch, and disable administrator bypass where supported. Confirm GitHub plan/visibility support. For an owner initiating and approving a run, environment prevent-self-review must be off; the future uploader also needs an explicit owner-only dispatch check. None of these controls is created by this preview PR.
3. Store the Steam **login account name** as environment variable `STEAM_USERNAME`, not the display name or Workshop ID. If password authentication is selected for that adapter, use environment secret `STEAM_PASSWORD`. These names are a proposal, **not consumed by the current workflow**. Do not place values in code, workflow inputs, chat or terminal command arguments.
4. Steam Guard remains enabled. A password alone may not authorize an ephemeral runner. Initial authorization may require the account owner's interactive approval. Do not store a one-time code as a permanent secret, disable MFA or upload an authenticator shared secret/recovery code. Any persisted session is itself a credential: its lifetime, encryption, revocation and handling outside caches/artifacts need a separately reviewed design before collection.
5. Approve only the exact item, release hash and tested uploader code. Keep builds/PRs and arbitrary repository commands outside the privileged job. Do not use shared team logins or give other authors access to this credential environment. Repository/runtime administrators remain trusted and can potentially misuse secrets despite encryption/masking.

For now, use RimWorld's built-in author-controlled publishing path for actual updates. Valve's [subscriber agreement](https://store.steampowered.com/subscriber_agreement/) restricts sharing/automation, while its [Workshop documentation](https://partner.steamgames.com/doc/features/workshop/implementation) describes SteamCMD uploads for testing. Permission for the intended production automation and RimWorld update behavior must be established before an unattended uploader is represented as ready. A Steam Web API key is not a replacement for publishing-account authentication.

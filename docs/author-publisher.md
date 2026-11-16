# Author-owned publisher repositories

GutenStructure supplies `.github/workflows/author-publish.yml`, which runs inside the **calling author's personal repository**. GutenStructure stores no author credentials and cannot dispatch those personal workflows merely by hosting reusable code. Authors pin the full reviewed workflow commit and control adoption of updates. An organization repository cannot call this implementation successfully: the verified caller must be personally owned, manually dispatched by its owner from its default branch, including the triggering actor on reruns.

Status: beta implementation, awaiting owner testing. **Nexus has an opt-in live upload job; Steam remains preview-only.** No live uploads have been tested or performed. Do not promote to production based on unit/CI tests alone.

## Setup for each author

1. Create a personal publishing repository under your own GitHub account. Use GitHub's supported reusable-workflow visibility settings; the central workflow must be accessible to that repository. Do not add organization owners as administrators. Contributors who can modify publishing code remain trusted; a private repository can reduce unnecessary access, but is not itself secret isolation.
2. Copy [the caller example](../examples/author-publisher/publish.yml) into `.github/workflows/publish.yml` on its default branch. Replace the workflow reference with a reviewed full GutenStructure SHA. During testing use the beta PR head you personally reviewed; production must use a reviewed SHA promoted to GutenStructure `release`. Never reference `main`, `beta`, a tag or an unreviewed moving ref for production.
3. Set your source repository and **existing** Nexus file / Kenshi Workshop item IDs in that reviewed caller configuration. Use the opaque v3 Nexus file identifier exposed by the official upload UI/API; do not substitute the legacy game-scoped version ID. Use `destination: nexus` if you are testing Nexus only, or `steam` for a Steam preview only. `both` means Nexus upload is available and Steam produces a preview; it does not mean both services were published. Nexus requires a manually created mod page and first file. Verify your Nexus team permission to update that file; use your individual key, never a shared login.
4. Create environment **nexus-publish** in your personal repository. Add `NEXUSMODS_API_KEY` as an environment secret there. Configure required review by you, restrict deployment branches to the default branch, and disable administrator bypass where supported. The owner both initiating and approving the run requires GitHub's “prevent self-review” option to be off; owner-only dispatch is separately checked by the workflow. Environment protection availability depends on repository visibility and your GitHub plan. If those controls are unavailable, do not represent the environment as approval-protected; retain preview/manual publication until you choose a supported configuration.
5. Start with `publish-nexus: false`. Supply the stable source release tag, exact current `release` head, ZIP asset ID, version and reviewed SHA-256. The preview checks source ownership, release protection/CODEOWNERS, tag commit, release-asset membership, GitHub asset digest and downloaded ZIP bytes. Missing asset digest fails closed. The source must be a public approved organization repo. Older release heads, drafts and prereleases are rejected. This does not prove complete runtime packaging or absence of licensed assets; review those too.
6. Inspect the credential-free plan and Steam VDF preview. For an author-approved Nexus test, start a new run with `publish-nexus: true`, then approve the environment job after checking its code and target. That job fetches and verifies the same hash again after approval. Only the pinned official Nexus upload action receives the key. Record its resulting version ID/receipt and verify the download on Nexus before further releases.

No author platform keys are passed with `workflow_call` secrets or `secrets: inherit`. The called job's `environment` resolves in the caller repository. Names in workflow inputs are configuration, not a way to access secrets in GutenStructure. Builds and author customization belong in separate unprivileged jobs before publishing; do not insert arbitrary commands or caller-controlled checkouts into the credential-bearing job.

## Platform policy boundaries

Nexus [officially supports individual team-member keys and author GitHub publishing](https://www.nexusmods.com/site/news/15454). Its [API policy](https://help.nexusmods.com/article/114-api-acceptable-use-policy) separately lists storing other users' keys on your server and use without user initiation as unacceptable. This design uses each author's own explicitly initiated workflow and own credential custody, matching the official author CI pattern; it does not collect third-party keys into GutenStructure or Azure. Obtain Nexus clarification/registration before changing it into a multi-user hosted credential service. Do not assume a key is scoped to a single mod; granted account permissions may be broader.

Steam's [subscriber agreement](https://store.steampowered.com/subscriber_agreement/) restricts account sharing and automation. Its [Workshop documentation](https://partner.steamgames.com/doc/features/workshop/implementation) documents SteamCMD uploads for testing. We have not established permission for unattended Kenshi production uploads or technical compatibility. This workflow therefore accepts **no Steam credentials** and executes no SteamCMD. The VDF is a preview referencing an existing item; it deliberately does not unpack the ZIP or create a staging tree. Use author-initiated FCS publishing until the permitted publishing method and Kenshi behavior are confirmed. A Steam group is not authorization to share a login.

## Remaining security limits

- GitHub/environment administrators and anyone able to replace trusted publishing code can potentially misuse runtime secrets. Encryption and log masking do not remove that trust. You retain that authority in your own repository. Do not put unrelated authors' secrets into your repo, even in differently named environments.
- Updating a GutenStructure pin changes trusted code. Review the whole change, including its internal pinned code/actions, before accepting it. The code repository cannot silently upgrade an existing immutable pin, although dependency/platform compromise remains a risk.
- Inputs fix the payload and target for that dispatch, not the platform token's overall authority. Other permitted Nexus team members may still publish independently outside this workflow.
- Nexus and Steam are not an atomic transaction. Nexus receipts contain the source SHA, payload digest and resulting version ID. Automatic rerun uploads are refused, but a fresh dispatch could still duplicate a version. Inspect the existing file after failures before starting another run; durable duplicate suppression is a later enhancement.
- A deployment approval does not make malicious code safe. Never execute mod payloads or repository build hooks in the publishing job. Complete game testing belongs in a separate isolated environment without keys.

## Test status and next steps

Unit tests cover owner-only dispatch, input injection, release/asset substitution, digest failures, download redirects and non-overwriting payload storage. CI validates the code without author credentials. The example intentionally requires author-specific replacements; no personal repo, secret, environment or live Nexus file has been configured by this PR. First owner test: create a personal caller, configure real IDs, run a preview against a complete stable release, then approve one Nexus update. Steam remains a documented no-op until its separate acceptance criteria are met.

## Extend the caller in your own repository

Keep GutenStructure's reusable publisher pinned, and add your own jobs around the `publish` job in the copied caller. GitHub calls reusable workflows at **job level**: a job with `uses:` cannot also contain `steps:`. Use `needs:` to connect separate jobs. A failed prerequisite prevents publication.

For example, add a credential-free author checklist job and make `publish` depend on it:

```yaml
jobs:
  author-checks:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - name: Check my release checklist
        run: echo 'Replace this step with your own checks; do not load publishing secrets here.'
  publish:
    needs: author-checks
    uses: TheIvoryDisaster/GutenStructure/.github/workflows/author-publish.yml@REPLACE_REVIEWED_40_CHARACTER_SHA
    # Keep the complete `with:` mapping from the caller template here.
```

That is a structural snippet, not a complete runnable workflow. Start with [publish.yml](../examples/author-publisher/publish.yml); preserve its `workflow_dispatch`, read-only permissions and full input mapping. Author checks may verify your checklist or test the mod in an isolated environment. A successful local rebuild does not replace the release ZIP selected by asset ID: the publisher always fetches the approved GitHub release asset itself. It does not accept a caller workspace path, arbitrary upload URL or caller-built Actions artifact.

To perform work after a successful Nexus upload, add another job with `needs: publish` and inspect `needs.publish.outputs.nexus-version-id`. It is empty during previews, so skip Nexus-specific follow-up when that output is empty. Keep the source version/hash and Nexus receipt together. Do not turn a receipt-processing failure into an automatic upload retry. Add notification credentials only to the separate notification job, with their own minimum permissions; the template does not send messages automatically.

For multiple mods, copy the caller into a separately named workflow for each mod and keep each destination ID fixed in its `with:` mapping. Use distinct author-owned environments when that separation helps your approvals. Every workflow still uses the same pinned reusable implementation. Do not accept arbitrary Nexus or Workshop IDs as public dispatch inputs. Separate environments do not narrow the Nexus API key's actual platform permissions or isolate credentials from the personal repository administrator.

To change how publishing itself works, open a grouped GutenStructure PR against `beta`, update the guide/tests, and test before promotion. Do not work around a blocked source gate, substitute a moving workflow reference, inject custom commands into the privileged job or introduce shared author credentials. Authors review and explicitly update their workflow pins after promotion; central updates never silently replace their chosen version.

## Caller input reference

| Input | Where the author gets it | Required behavior |
| --- | --- | --- |
| `source-repository` | Fixed caller configuration, e.g. `Meitou-Modding-Ecosystem/MeitouMods` | Public organization repository on the implementation's allowlist. New source repos require a reviewed implementation update. |
| `release-tag` | The source repo's published GitHub Release | Stable release, not a draft/prerelease; tag must resolve to `source-sha`. |
| `source-sha` | Source repo's current `release` branch commit | Full 40-character lowercase Git SHA. Historical release heads are intentionally rejected. |
| `asset-id` | GitHub release asset metadata | Positive numeric asset ID, not a workflow run ID or artifact ID. |
| `expected-sha256` | Author-reviewed release manifest, checked against GitHub metadata | 64 lowercase hexadecimal characters, without `sha256:`. Must match the GitHub asset digest and downloaded bytes. |
| `version` | Your intended published mod version | Letters/digits plus `.`, `+`, `_` or `-`, up to 64 characters, starting with a letter/digit. It is not automatically derived from the tag. |
| `destination` | Fixed caller configuration | `nexus`, `steam` or `both`; `both` still only previews Steam. Default is `both`. |
| `nexus-file-id` | Existing file's Nexus v3 identifier | Required for `nexus`/`both`; use the file/update-group ID, not its version ID. |
| `steam-item-id` | Existing Kenshi Workshop page | Required for `steam`/`both`; positive item ID, never zero. |
| `publish-nexus` | Owner's manual dispatch choice | Boolean; default `false`. `true` permits the live Nexus job after environment approval/configuration. |
| `publisher-environment` | Environment in the personal caller repo | Default `nexus-publish`; contains that author's `NEXUSMODS_API_KEY`. Configure protection before opting in. |

Retrieve non-secret release metadata with GitHub CLI, replacing the example tag:

```sh
gh api repos/Meitou-Modding-Ecosystem/MeitouMods/branches/release --jq '.commit.sha'
gh api repos/Meitou-Modding-Ecosystem/MeitouMods/releases/tags/v1.2.3 \
  --jq '{tag: .tag_name, assets: [.assets[] | {id, name, size, digest}]}'
```

If the release has more assets than the release response includes, use its `/releases/RELEASE_ID/assets` endpoint with pagination. Confirm you selected the ZIP for the correct mod and platform. GitHub metadata identifies the bytes; it does not prove the payload passed game testing. Do not paste platform credentials into these commands or documentation.

## First-run troubleshooting

| Symptom | Check |
| --- | --- |
| Workflow cannot be found | Replace the example SHA; verify the pinned commit contains `author-publish.yml`, the central repo is accessible, and the caller is on your default branch. |
| No **Run workflow** button | Commit the caller's `workflow_dispatch` workflow to the personal repo's default branch. |
| Owner/default-branch check fails | Run it yourself as the personal repo owner, from its default branch. Organization callers, collaborator dispatches and another user's reruns are intentionally rejected. |
| Release protection check fails | Fix source protections/CODEOWNERS through reviewed org changes; two approvals including a code owner are required. Do not weaken the gate in the personal caller. |
| Asset digest or source SHA fails | Check the selected asset/release, manifest and current release head. Missing GitHub digest is a blocker; changing the expected hash merely to silence a mismatch is unsafe. |
| ZIP rejected | Current bounds are 96 MiB compressed and 512 MiB expanded; an FCS `.mod` file is required. Unsafe paths, links, duplicates and encrypted ZIPs are rejected. Larger/other packages need a reviewed change. |
| Nexus key is empty | Put `NEXUSMODS_API_KEY` in the selected **environment of the personal caller repository**, not GutenStructure, an unrelated environment or the mod organization's repository. |
| Nexus job waits | Review the pending deployment in the personal caller's Actions run and approve it as the configured environment reviewer. |
| Steam was not uploaded | Expected: this version only generates a VDF preview and does not accept Steam credentials. |
| Upload failed or rerun refused | Inspect the Nexus file and prior run receipt first. An upload may have succeeded before a later step failed. Start another approved dispatch only after resolving that ambiguity. |

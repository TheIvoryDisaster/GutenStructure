# Meitou project synchronization

`backlog/project.json` is the explicit list of issues to add to organization Project 1. Run `scripts/sync_project.py --validate-only` offline. Remote runs preview by default; `--apply` adds missing cards and sets only fields explicitly declared in the manifest. Existing cards are reused, pagination is followed, and unknown fields/options abort before mutation. Cards absent from the manifest are never deleted or archived. The workflow serializes runs to prevent overlapping syncs.

The current cloud workspace substitutes its GitHub connector credential for supplied Authorization headers. Direct Projects access and repository administration return 403 even after CLI OAuth login. This is not evidence that the supplied personal token is invalid. Use the GitHub-hosted workflow instead; never put a token in the manifest, code, issues or chat.

## One-time owner setup

1. Open https://github.com/TheIvoryDisaster/GutenStructure/settings/secrets/actions/new .
2. Name the secret `MEITOU_PROJECT_TOKEN`. Set its value to the complete fine-grained token owned by Meitou-Modding-Ecosystem with organization Projects read/write permission. No broader organization or Azure permissions are needed. Issue resolution also requires visibility of the public issue URLs in the manifest.
3. Run **Actions > Synchronize Meitou project > Run workflow** from `main`, leaving `apply` false to preview.
4. Review the URLs and field updates, then run again with `apply` true.

The agent can dispatch subsequent runs using the existing connector after the secret is present. The token is exposed only to this dedicated main-branch workflow step, never PR builds. Only the personal owner should administer or modify this repository. Configure the owner protections described in `owner-controls.md` before granting collaborator write access.

Initial cards deliberately specify no status or priority until the project's actual options can be inspected. This preserves existing board choices. To manage a field, add e.g. `"fields": {"Status": "Todo"}` only when that exact option exists. Unspecified fields remain manually managed.

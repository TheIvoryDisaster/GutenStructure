# Testing a mod against Rivalry Core

The dependency path has beta evidence: TWR's agent reports that PR #7 downloaded and hash-checked `rivalry-core-0.6.0-beta.6e6ceb3`, then tested the DLL against official Meitou 0.20.1 and the 0.20.2 nightly. This is distinct from the baseline CI checks below; it is not evidence of a production release or automatic downstream testing.

## Unblock TWR's baseline CI

Copy [the caller example](../examples/dependent-mod-ci.yml) into `.github/workflows/ci.yml`, adapting paths and SDK versions for other consumers. For TWR it preserves `rules / build` and `python / build`, uses read-only permissions, and targets beta, main and release for both PRs and pushes. The .NET 10 engine-free rules project and Python compilation are baseline checks, not the .NET 11 real-Rivalry suite.

As inspected during this handoff, TWR #2 targets only main. Adding branch filters on main alone does not install a workflow into beta. Carry the CI change into the beta PR's merge tree: open a CI-only PR targeting beta, or merge the CI feature branch into the integration-test PR's source branch. Ensure the main-targeted CI PR also contains the expanded filters. Resolve conflicts through normal PRs; do not weaken required checks or bypass the release policy. Before merging TWR #7, verify both named checks succeeded on its latest head.

Keep the real dependency tests and `release_check.sh` instructions from TWR #7. Optional dependencies need tests with Rivalry Core both present and absent. Record the exact engine/runtime versions, source commit, immutable artifact tag and expected SHA-256 alongside the test result. Passing baseline checks must not be reported as passing those integration tests.

## Adopt the released shared packager

GutenStructure #24 promoted the packaging workflow and guard fixes to release at `0ef1d783148f161894193d1aa322650b88b75bd5`. The MeitouMods agent can replace its local reusable-workflow references in both beta and production callers with:

```yaml
uses: TheIvoryDisaster/GutenStructure/.github/workflows/package-meitou-mod.yml@0ef1d783148f161894193d1aa322650b88b75bd5
```

Keep existing inputs, caller-job `contents: write`, and the production job's explicit dependency on `release-gate.yml`. Do not pass `secrets: inherit`. Remove the mirrored local workflow/helper only after searching for all remaining references. Validate beta publication and its ZIP/checksum before promoting this migration; existing verified snapshots remain valid pins.

## Production and approvals

MeitouMods #68 is the separate production promotion. It requires two distinct reviewers, including an applicable code owner; author self-approval and the beta/main review bypass do not satisfy release policy. After merge, verify the manifest is 0.6.0 and create `rivalry-core-v0.6.0` at the current reviewed release head. Do not tag beta or the unmerged PR head. Verify the production workflow, artifact digest and release notes before consumers switch from their beta snapshot.

GutenStructure is the personal exception: PRs and passing CI, zero required reviewers. Changes needing owner testing go through beta and await feedback before promotion. Organization beta/main use code-owner review with the documented super-maintainers review-rule exception; mandatory CI remains enforced. See [release policy](releases.md).

## Deliberately deferred

MeitouMods #62 still owns the dependency lock format and automatic downstream test triggering. Keep immutable tags and explicitly recorded hashes; never use the rolling `rivalry-core-beta` alias as a CI pin or auto-update a dependency pin. Do not introduce an ad hoc lock schema or cross-repository publishing credentials to unblock baseline CI. For now, run the consumer's explicit integration checks and record evidence manually.

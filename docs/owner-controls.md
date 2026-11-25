# Personal owner controls

GutenStructure is owned by TheIvoryDisaster and is an explicit exception to the organization review policy. Require pull requests and passing CI on main, beta and release, with **zero required reviewers** and **no mandatory code-owner approval**. Keep force pushes/deletion blocked and bypass actors empty. The owner remains the sole administrator; organization owners inherit no access here.

Agents may validate and merge routine changes through conceptually grouped PRs. GitHub cannot record formal author self-approval. Changes needing the owner's personal testing target beta and wait for feedback before promotion to main or release. This exception does not apply to any repository in Meitou-Modding-Ecosystem: they follow docs/branch-policy.md.

The connector cannot administer rulesets. Apply the reviewed JSON in `docs/owner-controls.json` through GitHub's ruleset import UI, or use Configure release branch protections with target personal and a separately scoped `GUTENSTRUCTURE_ADMIN_TOKEN` in the Default environment. Do not reuse the organization administration credential for personally owned infrastructure.

Keep Default environment secrets restricted to reviewed main/release branches before granting anyone collaborator write access. Do not expose them to pull-request code or arbitrary feature branches. Use read-only default workflow tokens, disable Actions-created approvals, and retain secret scanning/push protection where available. CODEOWNERS remains ownership documentation; it does not impose a review requirement in this personal exception.


Organization repos follow the owner-approved table in docs/branch-policy.md. The personal GutenStructure exception remains unchanged.


## Verified personal protection setup

The saved `GUTENSTRUCTURE_ADMIN_TOKEN` passed the [read-only preview](https://github.com/TheIvoryDisaster/GutenStructure/actions/runs/44134957555) and [apply run](https://github.com/TheIvoryDisaster/GutenStructure/actions/runs/44135055837). Effective rules were independently read back for main, beta and release: required PRs, zero reviewers, no required code-owner/last-push approval, up-to-date `terraform` and `automation` checks, blocked force pushes/deletion and no bypass actors. Active ruleset ID: `27478119`. The import JSON now matches that deployed policy, including both required checks.

A docs-only staging PR can exercise the same required checks; it is not exempt because the change is small. These results verify the credential and configured rules, not a negative test using a separate collaborator account or the remaining Azure/Actions/secret boundaries tracked in [issue #2](https://github.com/TheIvoryDisaster/GutenStructure/issues/2). With zero required reviewers, any future repository writer must be treated as trusted until a different review policy is explicitly configured.

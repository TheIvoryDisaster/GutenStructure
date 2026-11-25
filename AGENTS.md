# GutenStructure agents

For repository onboarding or CI/release setup, read `.agents/skills/onboard-repository/SKILL.md` and each target repository's instructions.

Before changing a framework's public API, a mod's dependency range, `gameVersion` or engine pin, read docs/versioning.md and follow its
breaking-change steps (minor bump only for a dependent-contract change, a Dependents section in the PR, fix PRs in failing dependents).

Approved policy revision 6 supersedes revision 5 when activated. Beta requires PRs and Development readiness, zero approvals. Main requires development checks and two approvals including code owners. Release additionally requires upstream source/released compatibility and package validation. Managed rules have no bypass actors. Preserve independent security rules. See docs/development-production-policy.md. Keep the revision 5 reconciler active until consumer workflow migration is ready, then activate revision 6 in backlog/releases.json.

GutenStructure is personally controlled and outside that organization: main/beta/release require PRs and CI, zero reviewers. Agents may validate and merge routine PRs. Group related changes in one PR. Changes requiring owner testing target beta and await feedback before main/release promotion. Preserve beta/main/release policy consistency when promoting central code so old reconciliation cannot return.

Keep personally controlled workflows/Azure administration separate from organization-author builds. Never commit credentials, state/plans, original Kenshi assets or sensitive workflow output. Distinguish tested source, applied rules and deployed infrastructure. Do not bypass required CI, environment approvals or an automatic approval rejection. Beta's explicitly authorized review bypass does not waive CI or the mandatory PR.

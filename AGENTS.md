# GutenStructure agents

For repository onboarding or CI/release setup, read `.agents/skills/onboard-repository/SKILL.md` and each target repository's instructions.

Before changing a framework's public API, a mod's dependency range, `gameVersion` or engine pin, read docs/versioning.md and follow its
breaking-change steps (minor bump only for a dependent-contract change, a Dependents section in the PR, fix PRs in failing dependents).

Organization branch policy: the owner-approved table in docs/branch-policy.md is the source of truth (beta: PR, Development readiness, zero approvals; main: same checks, one approval including code owners; release: Release readiness, one approval including code owners; `release-debugger` PR-only bypass on the main/release approval). Never change review counts, required checks or bypasses unless the owner asks; make code and other docs match that table, not the reverse.

GutenStructure is personally controlled and outside that organization: main/beta/release require PRs and CI, zero reviewers. Agents may validate and merge routine PRs. Group related changes in one PR. Changes requiring owner testing target beta and await feedback before main/release promotion. Preserve beta/main/release policy consistency when promoting central code so old reconciliation cannot return.

Keep personally controlled workflows/Azure administration separate from organization-author builds. Never commit credentials, state/plans, original Kenshi assets or sensitive workflow output. Distinguish tested source, applied rules and deployed infrastructure. Do not bypass required CI, environment approvals or an automatic approval rejection. Beta's explicitly authorized review bypass does not waive CI or the mandatory PR.

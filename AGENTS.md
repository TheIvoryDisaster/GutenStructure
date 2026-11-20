# GutenStructure agents

For repository onboarding or CI/release setup, read `.agents/skills/onboard-repository/SKILL.md` and each target repository's instructions.

Permanent Meitou-Modding-Ecosystem policy (revision 4, all repos including Husbandry): ordinary branches are unprotected. Beta requires a PR and passing CI; super-maintainers has PR-only bypass of the separate review rule, including self-merges. Main/release require one independent super-maintainers approval plus passing CI, with no review bypass. Keep mandatory PR/CI safety in a no-bypass ruleset. GitHub Actions has no review bypass. Native team review does not depend on CODEOWNERS or a custom App. See docs/branch-policy.md. Earlier interim and Husbandry pilot instructions are superseded.

GutenStructure is personally controlled and outside that organization: main/beta/release require PRs and CI, zero reviewers. Agents may validate and merge routine PRs. Group related changes in one PR. Changes requiring owner testing target beta and await feedback before main/release promotion. Preserve beta/main/release policy consistency when promoting central code so old reconciliation cannot return.

Keep personally controlled workflows/Azure administration separate from organization-author builds. Never commit credentials, state/plans, original Kenshi assets or sensitive workflow output. Distinguish tested source, applied rules and deployed infrastructure. Do not bypass required CI, environment approvals or an automatic approval rejection. Beta's explicitly authorized review bypass does not waive CI or the mandatory PR.

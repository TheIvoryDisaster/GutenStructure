# Personal owner controls

GutenStructure is owned by TheIvoryDisaster and is an explicit exception to the organization review policy. Require pull requests and passing CI on main, beta and release, with **zero required reviewers** and **no mandatory code-owner approval**. Keep force pushes/deletion blocked and bypass actors empty. The owner remains the sole administrator; organization owners inherit no access here.

Agents may validate and merge routine changes through conceptually grouped PRs. GitHub cannot record formal author self-approval. Changes needing the owner's personal testing target beta and wait for feedback before promotion to main or release. This exception does not apply to any repository in Meitou-Modding-Ecosystem: their main/release branches require two approvals including a code owner.

The connector cannot administer rulesets. Apply the reviewed JSON in `docs/owner-controls.json` through GitHub's ruleset import UI, or use Configure release branch protections with target personal and a separately scoped `GUTENSTRUCTURE_ADMIN_TOKEN` in the Default environment. Do not reuse the organization administration credential for personally owned infrastructure.

Keep Default environment secrets restricted to reviewed main/release branches before granting anyone collaborator write access. Do not expose them to pull-request code or arbitrary feature branches. Use read-only default workflow tokens, disable Actions-created approvals, and retain secret scanning/push protection where available. CODEOWNERS remains ownership documentation; it does not impose a review requirement in this personal exception.


Organization policy revision 2 supersedes older main review counts: ordinary branches unprotected; beta/main use owner review with the selected super-maintainers team's PR-only review bypass; release retains two reviews including owner and no bypass. CI/safety remains separate with no bypass. See docs/releases.md. The personal GutenStructure exception remains unchanged.

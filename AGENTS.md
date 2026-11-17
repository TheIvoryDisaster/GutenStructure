# GutenStructure agents

For repository onboarding or CI/release setup, read `.agents/skills/onboard-repository/SKILL.md` and the instructions in each target repository.

For personal author publisher setup or extensions, read `.agents/skills/author-publishing/SKILL.md` and `docs/author-publisher.md`.

Keep personally controlled workflows and Azure administration separate from organization-author builds. In Meitou-Modding-Ecosystem, ordinary branches have no protection; beta/main require PRs and code-owner review, with the explicitly selected super-maintainers team permitted PR-only bypass of the review rule for self-merges. Keep CI/safety in a separate rule with no bypass. Release requires two approvals including an applicable code owner and no bypass actors. GitHub does not support formal author self-approval. GutenStructure is the personal-owner exception: require PRs and passing CI, but zero required reviewers and no mandatory code-owner review. Agents may validate and merge routine GutenStructure changes through PRs; GitHub does not support author self-approval.

Group conceptually related changes into one PR. Changes requiring the owner's personal testing must target beta and await feedback before beta is promoted to main or release. Do not bypass GitHub rules, environment approvals or an automatic approval rejection. Explicit updated user instructions take precedence over older repository guidance.

Never commit credentials, Terraform state/plans, original Kenshi assets or sensitive workflow output. Distinguish tested source, enforced policies and deployed infrastructure; a configuration file or passing unit test alone is not live enforcement.

# GutenStructure promotion

Require PRs and passing CI for main, beta and release, with zero required reviewers and no mandatory code-owner review. Agents may validate and merge routine changes through conceptually grouped PRs.

Changes requiring the owner’s personal testing target beta and await feedback before promotion to main or release. Production deployment must still use the current release head and the central gate. The owner remains the sole administrator.

Organization main/release branches require one approval including a code owner (docs/branch-policy.md); this personal exception does not extend to them. See docs/releases.md and the onboarding skill.

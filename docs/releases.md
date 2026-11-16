# Release promotion

Every managed repository has a `release` branch. Organization main/release branches require two reviews including an applicable code owner. GutenStructure is the explicit personal exception: main/beta/release require PRs and passing CI with zero required reviewers and no mandatory owner review. MeitouClient `master` stays an upstream mirror; development stays on `fork`. MeitouMods develops on `beta`; `main` is the existing stable source for the initial release branch. Other repositories initially seed release from their default branch. GutenStructure seeds release from main. Initial branch creation adds a fallback CODEOWNERS file where absent; it does not publish a release.

Organization production changes go through a PR to `release`; main has the same review policy. Required organization rules: **two approving reviews, including a code-owner review**, stale approvals dismissed, approval after the last push, resolved review threads, required CI up to date, no direct pushes/force pushes/deletion and no bypass actors. One code-owner approval counts toward the two; this is not three approvals. Never bypass the rules to accommodate a sole maintainer. GitHub authors cannot approve their own PRs: owner-authored promotions require another eligible code owner and another reviewer. Name additional trusted code owners explicitly before relying on that path.

The central production gate checks the exact release branch head and reads the enforced ruleset from GitHub. It refuses unprotected or weakly protected branches, bypass actors, other refs and tags pointing at older commits. Stable game/launcher/mod release workflows depend on this gate. Nightlies remain development prereleases, not production promotions. Do not rewrite MeitouClient master for fork-specific policy.

## Installing protections

The connector cannot administer rulesets. The reviewed plan is `backlog/releases.json`. `python -m scripts.apply_release_policy --validate-only` validates it offline. To preview remotely, configure a narrowly scoped administration credential:

- `MEITOU_RELEASE_ADMIN_TOKEN`: fine-grained token owned by Meitou-Modding-Ecosystem; repository Administration read/write for the six explicitly listed repositories. Public code visibility is needed to verify CODEOWNERS.
- `GUTENSTRUCTURE_ADMIN_TOKEN`: separately scoped personal token for GutenStructure Administration read/write.

Store these only as GitHub Actions secrets in GutenStructure, never in project/build workflows. Run **Configure release branch protections** on main with the matching target and apply=false. Review the rules, then rerun with apply=true. The script refuses to silently weaken existing stronger review requirements or discard additional checks. It neither deletes other rulesets nor grants collaborators administrative access. The Projects-only token cannot perform this operation.

Until that operation succeeds, release branches exist but protection enforcement is pending. The production gate must fail closed in that state. Existing workflows from historical commits cannot be retroactively changed; repository writers may also create GitHub Releases manually unless their repository permissions are restricted. These controls govern the official pipeline, and centrally owned Azure publishing must additionally enforce its own trusted workflow/identity boundary.

## Repository rollout

Configuration PRs target release and run CI there. Do not merge organization main/release configuration or promotion PRs without the requested two approvals including a code owner, even if a rule has not yet been installed. Routine GutenStructure PRs may be validated and merged by agents under its zero-reviewer exception. Changes requiring personal testing target beta and wait for owner feedback before main/release promotion. Engine and mod release workflows retain their packaging/version checks. Repositories without a production packaging workflow get the branch/review policy first; asset-dependent packaging is not replaced with an incomplete artifact. TWR still needs its licensed game-data path before a full content release can be automated.

## Future repositories and changing owners

The review rule uses each repository's native CODEOWNERS file, not a separate reviewer list. Changes to eligible code owners take effect through reviewed file changes; ownership teams follow their current membership. Every path needs a fallback owner entry, and the central gate also checks GitHub's CODEOWNERS errors. No organization-owner role is silently treated as an approval or bypass.

Organization-wide rulesets require GitHub Team or Enterprise. The free-tier fallback discovers current and future **public** repositories under immutable organization ID 357134506 and reconciles per-repository release rules daily. Use All repositories on the scoped organization administration token for future coverage. New repositories require a release branch, valid CODEOWNERS and a passing `Release readiness` check before publishing; missing setup is reported and the production gate blocks. Discovery does not grant Azure access or enable broker publishing. Private future repositories require a separately reviewed private execution path and a GitHub plan supporting their protections; their names/content are not exposed by this public workflow.

The administration job uses the `Default` environment. Enable its scheduled reconciliation only after this workflow has received the requested release-policy reviews. It does not bootstrap unknown source code, invent code owners, or weaken existing stronger rules.

Personal testing lane: open a conceptually grouped GutenStructure PR into beta, run automated checks there, and await owner feedback before promotion to main or release. Routine changes may be validated and merged by agents through PRs without formal author self-approval. Never apply that zero-reviewer exception to the organization.

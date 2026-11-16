# Production releases

Promote reviewed work with a pull request to `release`. It requires two approving reviewers, including an applicable owner from CODEOWNERS. Authors cannot approve their own PRs. Do not push directly or bypass the review requirement.

Run production release workflows from the current `release` head. Release tags must point at that same commit. The central gate checks both the head and the actual enforced ruleset; a branch name alone is insufficient. Nightlies remain separate prereleases. Repositories without production packaging retain their build checks until a complete package can be produced.

Required ruleset setup and owner instructions: https://github.com/TheIvoryDisaster/GutenStructure/blob/main/docs/releases.md . Protection enforcement requires the scoped administration secret; configuration alone does not enable it.

# Personal approval controls

Only TheIvoryDisaster was a repository administrator at inspection. Other organization owners have no inherited access to this personal repository.

GitHub prevents an author from approving their own PR. Changes created through the current connection are authored by TheIvoryDisaster. The proposed ruleset therefore allows **repository administrators to bypass only through a pull request**: with the owner as the only administrator, the owner can explicitly merge their own reviewed changes. Collaborators must not receive administrator access. Require the owner's CODEOWNER approval for collaborator changes; dismiss stale approvals and require the Terraform check.

The connection currently receives HTTP 403 when creating rulesets or accessing Actions administration. No ruleset was installed. The owner can apply the reviewable configuration from a CLI authenticated with repository administration permission:

```sh
gh api repos/TheIvoryDisaster/GutenStructure/rulesets --method POST --input docs/owner-controls.json
```

Apply once; for later edits update the existing ruleset ID rather than creating duplicates. Inspect the displayed rules and confirm the required check name after the first CI run. Repository administrators can ultimately change these controls. The personal account owner remains the authority; do not give organization authors administrative rights here.

Use read-only default workflow tokens, disable Actions-created PR approvals, and restrict allowed actions to reviewed dependencies. CODEOWNERS alone requests review and does not enforce it. Enable secret scanning and push protection where available. Plan/state/log confidentiality remains a separate concern.

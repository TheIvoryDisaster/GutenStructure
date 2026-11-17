---
name: author-publishing
description: Help a mod author adopt or extend GutenStructure's reusable publisher from their personal repository while retaining control of credentials and approvals.
---

# Configure an author-owned publisher

Use this skill for setting up, explaining, extending or troubleshooting an author's personal publishing repository. Read the target repository's AGENTS.md, `docs/author-publisher.md`, `examples/author-publisher/publish.yml` and the pinned `.github/workflows/author-publish.yml` before proposing changes. For organization source-build/release setup, also read `../onboard-repository/SKILL.md`.

## Workflow

1. Establish the author's personal GitHub repository, default branch, approved public source repository, existing destination IDs and intended mod/version. Read connected source metadata before asking for information it already provides. Never ask for platform credential values in chat.
2. Copy the complete caller template to `.github/workflows/publish.yml` in the author's repo. Replace every `REPLACE_*` value. Pin an explicitly reviewed full GutenStructure SHA; production pins must have reached GutenStructure `release` after beta feedback. Do not automatically adopt the newest SHA.
3. Keep source/destination configuration fixed in the reviewed caller. Explain every run input using the guide's input table. Use GitHub release **asset** IDs and the author's approved manifest hash, not Actions artifact IDs or a freshly rebuilt ZIP. The source tag must resolve to the current protected release head. The implementation supports only its explicit public organization allowlist; do not claim arbitrary repositories work.
4. Have the author configure their own `nexus-publish` environment and `NEXUSMODS_API_KEY`, required author review, default-branch deployment restrictions and disabled administrator bypass where supported. A sole owner initiating/approving requires environment prevent-self-review off. Verify plan/visibility support; an environment name alone is not an enforced approval. Never create or move someone else's key into GutenStructure/Azure. Do not use `secrets: inherit`.
5. Start with preview only (`publish-nexus: false`). Validate tag, source SHA, asset membership/digest, actual ZIP hash and packaging. Only the personal repo owner may dispatch on its default branch; the triggering actor is checked for reruns too. Do not bypass these checks to accommodate a collaborator or organization caller.
6. For extensions, add separate credential-free jobs and connect them with `needs:`. A job calling a reusable workflow cannot also have `steps:`. Keep all original required `with:` inputs. Do not add arbitrary scripts, caller-controlled checkout, mutable dependencies or mod-code execution to the credential-bearing publisher. The payload source remains the approved release asset.
7. For multiple mods, use separate named caller workflows with fixed target IDs; each author retains their own credential custody. For post-upload jobs, consume `needs.publish.outputs.nexus-version-id` and skip when empty (preview). Preserve publication receipts and avoid retrying uploads because a notification failed.
8. After explicit author approval, test one authorized Nexus update and verify its platform contents/receipt. No live upload test is authorized merely by an onboarding documentation request. Steam remains preview-only: accept no Steam secrets and do not add SteamCMD execution until permitted use and Kenshi compatibility are established.
9. Group changes in a PR. GutenStructure changes requiring owner testing target `beta` and await feedback before production promotion. Organization main/release PRs retain two reviews including CODEOWNER; GutenStructure itself retains its zero-reviewer PR exception. Personal caller rules follow that author's configured policy; do not impose the organization's review count on unrelated personal repos.

## Policy and trust

The guide links Nexus's official individual-key/team CI guidance, API custody policy and Valve account-sharing/automation terms. Do not claim a shared team login is compliant, keys are per-mod scoped, administrator access is harmless, or secret encryption eliminates runtime abuse. Recheck official policy before enabling a new custody or Steam automation design. Do not contact platforms or authors without authorization.

## Completion evidence

Report the caller PR, exact reviewed pin, unresolved placeholders, environment protection evidence where readable, preview checks and live-test status separately. Distinguish Nexus opt-in capability from an actual upload; `both` means Nexus plus Steam preview, not two successful uploads. Record that rerun uploads are blocked but fresh dispatches can still duplicate a version. Leave production promotion pending required owner feedback and never fabricate a receipt or successful game test.

## RimWorld preparation variant

Read `docs/rimworld-workshop.md` and `.github/workflows/rimworld-workshop-preview.yml` for RimWorld. This separate adapter reads an existing release from the personal caller repository (private supported with caller read-only GITHUB_TOKEN), validates About.xml/PublishedFileId/preview/assemblies and produces a no-login staging preview. Do not send private payloads to public central artifacts. Default-branch ancestry is checked, not organization release-review policy; do not claim approval enforcement from ancestry alone. No Steam credentials are requested or consumed. Proposed environment/credential names in the guide are future setup only. Steam Guard/session authorization, permitted automation, ownership and unlisted visibility preservation remain prerequisites for any later live adapter. Retain beta owner testing for changes needing personal verification.

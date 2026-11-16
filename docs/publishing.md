# Publishing boundary and rollout

## Trust

Other organization owners control their repositories; they must not control this repository or the Azure roles/federation governing personally funded storage. They may invoke an approved workflow repeatedly. Pinning and branch protection alone cannot enforce a spending quota.

The desired upload path is: unprivileged repository build -> reviewed central publication job -> quota broker -> short-lived, blob-scoped upload authorization. The broker validates GitHub issuer/audience, immutable caller owner/repository IDs, allowed ref/event, and the exact `job_workflow_ref` at a reviewed commit. Maintain an explicit allowlist; never trust an organization-name wildcard. Reject PR contexts.

The broker must atomically reserve per-repository daily bytes and upload count before issuing authorization, deduplicate run/attempt requests, constrain names/destinations, and enforce maximum artifact size and expiration. A SAS alone does not enforce content length: validate actual size, account for abandoned/oversized uploads, and stop issuing grants when limits are exhausted. Stronger streaming enforcement may require proxying uploads. Do not claim a hard spending cap: egress/requests and in-flight grants still need limits. Downloads require separate control.

Build outputs are data. Privileged jobs must not execute caller scripts, restore untrusted executable caches, unpack arbitrary archives, or dynamically load caller actions. Never pass Azure credentials to builds. Separate Terraform administrative identity from publication identities. No `secrets: inherit` in callers.

## Existing resources

Subscription: Mattaclysm's Test Space. Resource group `github`; shared StorageV2 Standard_LRS account `gutenhub`. Shared keys and public blob access disabled; HTTPS and TLS 1.2 required. Meitou identity `meitouclient-debug-upload` has container-scoped Blob Data Contributor on `meitouclient-debug`, with branch-only federation for the fork. Lifecycle deletion is three days; blob soft delete is disabled. This account also serves unrelated projects; never replace its whole lifecycle policy casually.

Control-plane inspection succeeded. This workspace's proxy denied access to `gutenhub.blob.core.windows.net`; the existing upload check subsequently succeeded from GitHub Actions on `fork` (run 43912337705). OIDC and upload access are verified from that runner; read-back, cleanup and cross-container denial remain unverified. Do not change Azure networking to work around a workspace proxy restriction.

## Implementation gates

1. Merge and protect the central CI foundation; enable reusable builds in MeitouMods first, then the remaining repositories using their actual dependency requirements.
2. Run the existing OIDC smoke check from the correct MeitouClient branch. Extend it to upload/read/hash/delete a tiny uniquely named blob and prove denial to a different project container. Keep existing federation while validating. Do not grant broader roles to make a failing check pass.
3. Implement and verify broker claim validation, atomic quotas and adversarial rejection cases before granting general publishing access. Keep its state private. Size the service within the $20 budget.
4. Configure exact workflow-bound trust. GitHub OIDC subject customization can include `job_workflow_ref`; Azure must match the reviewed workflow and allowed caller context. Preview flexible credentials are an alternative requiring separate compatibility review. Inspect the actual token claim shape without logging the token before migration.
5. Provision dedicated storage or carefully import existing resources into private Terraform state. Produce an owner-reviewed plan. No automated apply or Azure access in pull_request jobs.
6. Pilot successful publication and rejection of wrong repository/ref/workflow, duplicate and oversized requests. Remove branch-only upload trust after cutover. Expand the allowlist deliberately.

Documentation: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows

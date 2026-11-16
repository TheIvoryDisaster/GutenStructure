# GutenStructure

Personally controlled CI automation and Azure infrastructure for the Meitou Modding Ecosystem.

Standard GitHub-hosted runners build public repositories. Azure is reserved for workloads or artifact storage that need it; there is no Azure compute deployment in this baseline.

## Reusable builds

Call `.github/workflows/build-dotnet.yml` or `build-python.yml` from repository CI, pinned to a reviewed **40-character commit SHA**. See [caller examples](examples/README.md). These workflows have read-only repository permissions, no Azure authentication, no artifact publication, and no persisted checkout credentials. Repository build/test code is untrusted.

## Infrastructure and publishing

- [Build inventory](docs/build-inventory.md)
- [Publishing boundary and rollout](docs/publishing.md)
- [Cost assumptions](docs/costs.md)
- [Terraform module](terraform/README.md)

Publishing is intentionally unavailable until centrally enforced identity and quota checks exist. The Terraform module creates storage containers and retention rules on a **dedicated** storage account; it does not grant workload access or adopt the existing shared account.

## Owner controls

`CODEOWNERS` requests review; it does not enforce approval. Before enabling Azure publishing, apply the [owner controls](docs/owner-controls.md): require owner review for collaborator changes, block force pushes/deletion, and require CI. Only the personal owner should retain administration. Keep repository administration and Azure federation/RBAC administration under personal control. Review repository Actions defaults and third-party action permissions.

Do not commit credentials, state, saved plans or sensitive infrastructure output. Terraform state belongs in a private backend.

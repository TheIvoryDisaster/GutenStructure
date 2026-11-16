# Terraform foundation

`modules/repository-storage` manages private containers and a complete three-day-style retention policy on an existing **dedicated** storage account. It grants no RBAC roles and creates no federated credentials. Root deployment/backend configuration is deferred until storage ownership and the publishing broker are implemented.

Do not point this module at `gutenhub`: its account-level lifecycle policy also covers unrelated projects. Adopting that account requires importing and representing **all** existing rules first. Do not recreate live infrastructure because its Terraform source is missing.

Validation without Azure credentials:

```sh
terraform fmt -check -recursive terraform
terraform -chdir=terraform/modules/repository-storage init -backend=false
terraform -chdir=terraform/modules/repository-storage validate
```

Before deployment, configure an Azure Blob backend using Entra authentication in a separate private state container, restrict state access to the owner-controlled deployment identity, commit the root provider lock file, and review the plan for destructive changes. State/plan files may contain sensitive values. No storage account keys or client secrets in configuration. No automatic apply is provided.

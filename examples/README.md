# Caller examples

Replace `REVIEWED_COMMIT_SHA` with the approved 40-character GutenStructure commit SHA after merge. These are templates, not active callers.

MeitouMods (`.github/workflows/ci.yml`, preserve the required check name during migration):

```yaml
name: CI
on:
  pull_request:
    branches: [beta, main, release]
  push:
    branches: [beta, main, release]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  build:
    uses: TheIvoryDisaster/GutenStructure/.github/workflows/build-dotnet.yml@REVIEWED_COMMIT_SHA
```

MotionLab, after committing a reviewed dependency requirements file:

```yaml
jobs:
  build:
    uses: TheIvoryDisaster/GutenStructure/.github/workflows/build-python.yml@REVIEWED_COMMIT_SHA
    with:
      requirements: requirements-ci.txt
      test-command: |
        python tests/test_pipeline.py
        python tests/test_no_pillow.py
        python tests/fuzz/fuzz_glb.py 400
```

The Python command is intentionally repository-controlled and executes only on an unprivileged GitHub-hosted runner. Do not reuse this interface in publishing jobs.

## Personal mod publishing

Copy [the author publisher caller](author-publisher/publish.yml) to your own personal repository. Follow the [setup and extension guide](../docs/author-publisher.md) for required replacements, input values, author-owned environment secrets, approval configuration, additional jobs, multiple mods and troubleshooting. Nexus uploads require explicit opt-in; Steam is preview-only. The dedicated [author publishing skill](../.agents/skills/author-publishing/SKILL.md) guides agents assisting with setup. This beta implementation still needs owner testing before production promotion.

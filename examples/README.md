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

MeitouMods framework prereleases (`.github/workflows/rivalry-core-beta.yml`), on pushes to `beta`:

```yaml
name: Rivalry Core beta
on:
  push:
    branches: [beta]
    paths: [RivalryCore/**, engine, Directory.Build.props, .github/workflows/rivalry-core-beta.yml]
permissions:
  contents: read
jobs:
  rivalry-core:
    permissions:
      contents: write
    uses: TheIvoryDisaster/GutenStructure/.github/workflows/package-meitou-mod.yml@REVIEWED_COMMIT_SHA
    with:
      mod-folder: RivalryCore
      slug: rivalry-core
      channel: beta
      test-project: RivalryCore.Tests
      empty-data-mod: true
```

For production, a tag-triggered caller runs `release-gate.yml` first and calls the same workflow with `channel: release` and `needs: [release-gate]`.
Grant `contents: write` only to the calling job, and never pass `secrets:`.

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

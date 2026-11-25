# Development and production policy

Revision 6 replaces revision 5 when activated in backlog/releases.json.

Beta requires a PR, Development readiness and existing independent security checks, with zero reviews. Main requires the same checks and two reviews including code owners. Release adds Release readiness and requires two reviews including code owners. All managed safety and review rules have empty bypass lists. Ordinary feature branches remain unprotected.

Development readiness aggregates existing builds, tests and Play deployment against the repository's pinned engine and framework dependencies. Engine release diagnostics remain visible on development PRs and do not join this aggregate. Release readiness requires development, upstream source compatibility, released engine compatibility and applicable package validation only when targeting release. Failed, skipped and cancelled required jobs block the corresponding aggregate.

Upstream source compatibility records the resolved VlcekM/MeitouClient master commit and builds/tests against it in a separate job, without the lock's engine check (locked frameworks are built on the pinned engine, not master). Released compatibility checks the sandbox-built mod and locked framework assemblies using the existing compatibility tool against current released engine binaries and manifest floors. Nightly diagnostics remain advisory.

The reusable production packager independently requires upstream and released compatibility, including tag-triggered runs. Its existing package completeness and checksum checks run before the write-token publisher receives an artifact. Beta packages retain their sandbox commit and dependency identity in notes and locks.

Activate only after the workflow migration is prepared for every applicable branch. Promote the shared workflows through checked PRs to GutenStructure release, then use immutable central references in consumers. Do not change engine pins, dependency ranges, gameVersion or mod versions during this migration.

Engine mirrors and repositories without Meitou mod manifests retain their own build/test coverage. Empty, inaccessible and missing-workflow repositories must be reported explicitly. A source PR, a preview and an applied ruleset are distinct rollout states. Existing code-scanning rules must survive reconciliation.

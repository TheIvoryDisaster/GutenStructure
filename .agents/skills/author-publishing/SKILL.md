---
name: author-publishing
description: Set up an author-owned Nexus publisher and the separate local Steam Workshop Watcher.
---

Read docs/nexus-publishing.md and docs/workshop-watcher.md. Nexus uses the author's personal caller repo/environment and a SHA-pinned official upload action. Initial mod page and first file must exist. Configure file IDs in reviewed source, validate the exact stable protected release ZIP/hash with publish-nexus=false, then use an explicit owner dispatch and environment approval for the live test. Never collect authors' keys centrally or pass secrets: inherit. Do not claim preview tests prove live uploads. Do not silently enable scheduled/event-driven uploads; current design is owner-initiated. Steam is local via Workshop Watcher: do not restore hosted passwords, Guard codes or authenticator seeds. Preserve local watcher files and its GitHub read credential during cleanup. Promote beta to main/release only after owner feedback on live behavior.

# Daily PR digest

`.github/workflows/pr-digest.yml` posts a discussion in GutenStructure's **Announcements** category at 07:07 New York time every
day. It covers pull requests opened, updated, merged or closed during the previous New York calendar day in every public,
unarchived Meitou-Modding-Ecosystem repository plus GutenStructure.

- Reads use only the workflow's `GITHUB_TOKEN` (public data). No admin token: PR text is untrusted input to a model.
- Each active repository gets one GitHub Models call (`openai/gpt-4.1-mini`, `models: read`, free tier). A failed call falls back
  to the plain listing; the listing is always included, folded under the summary.
- `@` mentions are defused so the digest pings nobody.
- Two cron entries (11:07 and 12:07 UTC) cover daylight saving time; a step skips the one that isn't 07:07 in New York.
- Scheduled runs fire only from `main`. Run it by hand from Actions → Daily PR digest; tick **post** to publish the discussion,
  otherwise the digest appears only in the run summary.
- Requires Discussions enabled on GutenStructure with an `Announcements` category.

Locally: `GITHUB_TOKEN=<token> python -m scripts.pr_digest --model ""` writes `digest.md`.

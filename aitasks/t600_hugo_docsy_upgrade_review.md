---
priority: low
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [documentation]
created_at: 2026-04-20 10:12
updated_at: 2026-04-21 13:29
boardcol: backlog
boardidx: 70
---

Review whether the project's Hugo and Docsy versions are worth upgrading, and if so, upgrade both the local dev environment and the GitHub Actions release workflow that builds and publishes the website.

## Context

Raised during t594_3 (onboarding flow sweep) review. The website builds successfully with the current Hugo version (`hugo v0.157.0+extended+withdeploy linux/amd64`, per `cd website && hugo build --gc --minify` output during verification). Docsy is pulled as a Hugo theme module. Neither has been audited against upstream recent-release history in a while, and the release workflow pins a specific Hugo version that can drift.

The CLAUDE.md project-overview section states requirements: `Hugo extended (>=0.155.3), Go (>=1.23), Dart Sass, Node.js (18+)`. The project runs above the floor today; the question is whether a higher version brings useful features or fixes.

## Goals

1. **Audit current versions.**
   - Local: Hugo extended 0.157.0 (per recent build output), Docsy version — check `website/go.mod` or `website/hugo.yaml` module pin.
   - GitHub Actions release workflow: grep `.github/workflows/` for the Hugo version pin and Docsy module reference.
2. **Check upstream releases.**
   - Hugo: latest stable release notes since 0.157.0.
   - Docsy: latest stable release notes since the pinned version.
3. **Decide whether to upgrade.**
   - Upgrade if there are material bug fixes, security advisories, or features relevant to aitasks' docs (e.g., taxonomy rendering improvements relevant to the t594_7 label-support work).
   - Skip if release notes show only churn or breaking changes without payoff.
4. **If upgrading:** update both the local install instructions (if any — e.g., in `installation/_index.md` or `ait setup`-installed versions) AND the GitHub Actions release workflow pin. Rebuild the website locally and verify the release workflow still passes.

## Key Files to Investigate

- `website/hugo.yaml` — top-level Hugo config, may pin theme version.
- `website/go.mod` / `website/go.sum` — Hugo module dependencies (Docsy is typically a Go module).
- `.github/workflows/*.yml` — release workflow. Look for `peaceiris/actions-hugo` or equivalent version pin.
- `CLAUDE.md` §"Website (Hugo/Docsy)" — documented minimum versions.
- `install.sh` — check if Hugo is mentioned as a framework dependency (it is not currently, since Hugo is only needed for website builds, not runtime).

## Reference Files for Patterns

- t594_2 archive plan — demonstrates conservative dedup stance; applies here: don't upgrade unless there's a real reason.

## Implementation Plan (sketch)

1. **Read current versions** from `website/go.mod`, `website/hugo.yaml`, and `.github/workflows/*.yml`.
2. **Check upstream release notes** — Hugo releases page, Docsy releases page.
3. **Produce a short upgrade report**: current versions, latest versions, diff summary, recommendation (upgrade / skip), and reasoning.
4. **If upgrading:** update `go.mod`, the workflow pin, and CLAUDE.md's minimum-version line if any changes the floor.
5. **Verify** — local `hugo build --gc --minify` succeeds with the new version; GitHub Actions workflow passes on a PR.

## Verification Steps

- `cd website && hugo build --gc --minify` succeeds after any changes.
- `.github/workflows/*.yml` Hugo-version pin matches the local version.
- Release workflow run (triggered via a test branch or PR) passes.
- No visual regressions on the built site (spot-check 3–5 pages).

## Notes

- This is a **parent task**, not a sibling of t594. Reason: t594 scope is "website documentation coherence" (content-level sweeps); Hugo/Docsy version management is infrastructure/build-system concern and doesn't belong under t594.
- If the sibling task t594_7 (Docsy label support) lands first and requires a newer Hugo/Docsy for taxonomy features, that would be a trigger to upgrade — mention this dependency if it surfaces during the audit.
- Priority is `low` — not blocking anything until a specific upstream feature or CVE changes that.

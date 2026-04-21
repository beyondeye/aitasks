---
Task: t600_hugo_docsy_upgrade_review.md
Worktree: (none — working on current branch per profile `fast`)
Branch: main
Base branch: main
---

# Plan: Hugo/Docsy upgrade review (t600)

## Context

The GitHub Actions release workflow pins `hugo-version: '0.155.3'` while the local dev env is already at `0.157.0+extended+withdeploy`. The task asks whether Hugo and Docsy are worth upgrading, and to align both local dev and CI if so.

## Audit results

| Component | Current | Latest (2026-04-21) | Source |
|-----------|---------|---------------------|--------|
| Hugo (CI pin) | 0.155.3 | **0.160.1** (2026-04-08) | `.github/workflows/hugo.yml:59` |
| Hugo (`hugo.toml` min) | 0.155.3 | — | `website/hugo.toml:13` |
| Hugo (CLAUDE.md doc) | >=0.155.3 | — | `CLAUDE.md:27` |
| Hugo (README table) | 0.155.3 | — | `website/README.md:11` |
| Docsy | 0.14.3 | **0.14.3** (already current) | `website/go.mod:5` |
| Go (setup-go) | 1.25.7 | — | `website/go.mod:3` (via `go-version-file`) |

Releases between 0.155.3 and 0.160.1 of note:

- **v0.158.0** — upgrades to Go 1.26.1, which addresses **CVE-2026-27142** (template security).
- **v0.159.2** — security fix for potential **XSS in Markdown links/images**.
- v0.159.0 — improved multi-module Node.js/npm workspace support.
- v0.160.0 — CSS variable injection via `css.Build`, Position-method accuracy fixes.
- v0.160.1 — panic/regression fixes.

## Recommendation: **UPGRADE Hugo → 0.160.1**. Skip Docsy (already current).

Rationale: two security fixes (CVE-2026-27142 and a Markdown-link XSS) land in the 0.158/0.159 range — material enough to justify the bump. Docsy is already at its latest stable, so no Docsy change is needed.

## Implementation

Four files touch a pinned Hugo version. All four must move together so CI, local dev, and docs agree.

### 1. `.github/workflows/hugo.yml:59`

```diff
-          hugo-version: '0.155.3'
+          hugo-version: '0.160.1'
```

### 2. `website/hugo.toml:13`

```diff
   [module.hugoVersion]
     extended = true
-    min = "0.155.3"
+    min = "0.160.1"
```

This will enforce 0.160.1 as the floor for anyone running `hugo build` locally — consistent with bumping CI.

### 3. `CLAUDE.md:27`

```diff
-Requires: Hugo extended (>=0.155.3), Go (>=1.23), Dart Sass, Node.js (18+).
+Requires: Hugo extended (>=0.160.1), Go (>=1.23), Dart Sass, Node.js (18+).
```

### 4. `website/README.md:11`

```diff
-| [Hugo](https://gohugo.io/) extended edition | 0.155.3 | Static site generator |
+| [Hugo](https://gohugo.io/) extended edition | 0.160.1 | Static site generator |
```

No Docsy / Go / Node version changes.

## Verification

1. **Local Hugo version check.** `hugo version` currently reports `v0.157.0+extended+withdeploy`. After bumping the `min` in `hugo.toml` to 0.160.1, the local build will fail until the binary is upgraded. Call this out explicitly — the user will need to run `sudo pacman -S hugo` (Arch) / `brew upgrade hugo` (macOS) / re-download the `.deb` (Ubuntu) to clear the floor.
2. **Local build** (after upgrading local Hugo): `cd website && hugo build --gc --minify` must succeed with no errors and no new warnings vs the previous build.
3. **Spot-check the rendered site**: run `./serve.sh` and load 3–5 pages (homepage, `/docs/`, one blog post, one installation page) — no visual regressions.
4. **CI run**: push on a branch, confirm the `Deploy Hugo site to Pages` workflow (`hugo.yml`) completes the build step successfully with the new pin.

## Out of scope

- Docsy version bump (already at latest 0.14.3).
- Go / Node.js version bumps.
- Any content-level doc changes (this is version-pin-only; see t594_* tasks for content sweeps).

## Post-Implementation

Follow Step 9 of the shared task-workflow for commit + archive. Proposed commit subject:

```
chore: Upgrade Hugo pin to 0.160.1 (t600)
```

Plan-file commit follows standard `ait: Update plan for t600`.

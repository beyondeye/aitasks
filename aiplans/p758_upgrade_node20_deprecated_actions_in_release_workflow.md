---
Task: t758_upgrade_node20_deprecated_actions_in_release_workflow.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Context

The `Release Packaging` workflow surfaced Node 20 deprecation warnings on the
`v0.20.0` release run (see issue body of t758): `actions/checkout@v4` and
`softprops/action-gh-release@v2` are both bundled against Node 20, which is
being phased out on GitHub-hosted runners. The actions still execute, but the
warnings will become hard failures once GitHub retires Node 20.

The task asks us to bump every reference to the latest Node 24-bundled major,
keeping versions consistent across all workflow files (not just
`release-packaging.yml`).

## Latest majors (verified via `gh api` on 2026-05-11)

| Action                          | Current in repo      | Latest major  | Notes                                    |
|---------------------------------|----------------------|---------------|------------------------------------------|
| `actions/checkout`              | `@v4` (6×), `@v5` (1×) | `v6.0.2`     | v5 introduced Node 24; v6 keeps it       |
| `softprops/action-gh-release`   | `@v2` (2×)           | `v3.0.0`      | v3 is purely a Node 20 → Node 24 bump; no API changes |

`softprops/action-gh-release@v3.0.0` release notes (verified): *"a major release
that moves the action runtime from Node 20 to Node 24"* — no breaking input/output
changes, so the existing `files:`, `body_path:`, and `generate_release_notes:`
usage in `release.yml` is unaffected.

`actions/checkout@v6` is also a clean drop-in (Node 24 + a creds-persistence
internal change, no input API changes).

# Plan

## 1. Bump `actions/checkout` to `@v6` in all workflows

Currently the repo is split: 6 references on `@v4` and 1 already on `@v5`.
Unify everything on `@v6` to satisfy the "keep versions consistent" requirement
and to be done with the next bump cycle (v5 was a stepping stone — already
superseded by v6 in November 2025).

Touch:

- `.github/workflows/hugo.yml:32` — `actions/checkout@v4` → `actions/checkout@v6`
- `.github/workflows/release-packaging.yml:28` — `actions/checkout@v4` → `actions/checkout@v6`
- `.github/workflows/release-packaging.yml:84` — `actions/checkout@v4` → `actions/checkout@v6`
- `.github/workflows/release-packaging.yml:123` — `actions/checkout@v4` → `actions/checkout@v6`
- `.github/workflows/release-packaging.yml:187` — `actions/checkout@v4` → `actions/checkout@v6`
- `.github/workflows/release.yml:28` — `actions/checkout@v4` → `actions/checkout@v6`
- `.github/workflows/contribution-check.yml:16` — `actions/checkout@v5` → `actions/checkout@v6`

Use `Edit` with `replace_all=true` on each file (the `actions/checkout@vX`
string is uniquely shaped per file but appears multiple times in
`release-packaging.yml`, so `replace_all` is the cleanest path).

## 2. Bump `softprops/action-gh-release` to `@v3`

Touch:

- `.github/workflows/release.yml:145` — `softprops/action-gh-release@v2` → `softprops/action-gh-release@v3`
- `.github/workflows/release.yml:154` — `softprops/action-gh-release@v2` → `softprops/action-gh-release@v3`

Both occurrences are in `release.yml`; one `Edit` with `replace_all=true`
covers them.

## 3. Sanity sweep

After edits, re-run the same audit grep from the task body to confirm zero
`@v4` / `@v5` / `@v2` stragglers for these two actions:

```bash
grep -rn 'actions/checkout@\|softprops/action-gh-release@' .github/
```

Expected output: only `@v6` for checkout and `@v3` for action-gh-release.

# Verification

Local verification is necessarily limited — these workflows only run on the
GitHub-hosted runner. The end-to-end verification is the next release run
(deferred to whenever the next tag is cut). For this task:

1. **Static audit** — run the grep above, confirm every reference is on the
   target major.
2. **YAML well-formedness** — `python3 -c 'import yaml; [yaml.safe_load(open(f)) for f in ("'"'"'.github/workflows/contribution-check.yml'"'"'","'"'"'.github/workflows/hugo.yml'"'"'","'"'"'.github/workflows/release-packaging.yml'"'"'","'"'"'.github/workflows/release.yml'"'"')]'`
   to ensure no accidental indentation/structural change.
3. **No tests broken** — none of the existing `bash tests/*` cover workflow
   contents; nothing to re-run here.
4. **Deferred (out-of-scope for closing this task)** — confirm zero Node 20
   warnings on the next real release run. The task body already calls this
   out as the long-form verification path; not required to close.

# Out of scope

- Anything in `nfpm` packaging (t757 territory).
- Maintainer-secret gating.
- Other unrelated workflow improvements (caching, matrix tweaks, etc.).

# Post-Implementation (Step 9 reminder)

This task uses no worktree; merge step is a no-op. After Step 8 review, the
`aitask_archive.sh` script will move the task file and plan to `archived/`
and commit.

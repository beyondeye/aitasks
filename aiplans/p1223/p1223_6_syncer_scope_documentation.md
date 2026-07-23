---
Task: t1223_6_syncer_scope_documentation.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_1_*.md, aitasks/t1223/t1223_2_*.md, aitasks/t1223/t1223_3_*.md, aitasks/t1223/t1223_4_*.md, aitasks/t1223/t1223_5_*.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_*_*.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
---

# p1223_6 — Syncer scope documentation

> The task file `aitasks/t1223/t1223_6_syncer_scope_documentation.md` carries the
> full section-by-section outline. This plan is the execution view. Parent
> design: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.

## Goal

Rewrite `website/content/docs/tuis/syncer/_index.md` so the syncer reads as a
cross-repo **sync console** (branches, versions, settings), and document the five
behaviors a user would otherwise get wrong.

## Steps

1. Read `aidocs/framework/documentation_conventions.md` (current-state-only, no
   version history in the body, generic phrasing over named coding agents) and
   the CLAUDE.md `ait setup` vs `ait upgrade` verb rule.
2. **Verify every claim against the as-built code**, not against the parent plan
   — siblings may have adjusted details. Run any command or grep you cite before
   publishing it.
3. Reframe the intro/Purpose around per-repo *state*; keep the cross-repo framing
   from t1138 and the existing page structure, extending rather than
   restructuring.
4. Layout: three tabs (Branches, Versions, Settings) with each tab's columns.
5. **Framework versions** section — columns; `Latest` resolved once per refresh
   and shared; fetch-off (`f`) means no network call and a stale marker; the
   upgrade action running that repo's own `ait upgrade` then `ait setup` in a
   spawned shell rooted in the target (they have no `--dir`, which is why a shell
   in the repo is used and why `ait setup` can still prompt there).
6. Document the five non-obvious behaviors explicitly:
   - upgrade is **refused** (not warned) on a target with a framework TUI or
     agent pane running, and the message names the windows to close;
   - the **declared detection bound** — tmux-session-scoped only; an `ait`
     command in an unrelated terminal, a detached process, or another machine
     sharing the checkout is invisible. Do not imply coverage the code lacks;
   - **self-upgrade exits the TUI first**, then runs in the vacated window, and
     why (the upgrade replaces the framework files the running TUI shells out to);
   - the State column reads `upgrading…` then `re-check needed` — the syncer
     **never reports success it did not observe**;
   - settings pushes always ask the **layer**, and a project write can be
     **masked** by the destination's local override (document the three choices
     and what each leaves on disk).
7. **Cross-repo settings** section — v1 covers the default code agent per
   operation only; the matrix shows effective value + provenance marker; per-repo
   `models_<agent>.json` means a value can be rejected in a destination; a
   project-layer push leaves an **uncommitted change in the destination repo**
   the user must commit there.
8. Keys table — new keys with their tab scope; Branches keys are inert on other
   tabs; keep the existing rebind/`?` note.
9. "Adding another synced setting" subsection pointing at the as-built module.
10. Update `website/content/docs/tuis/_index.md`'s syncer blurb if stale, and
    check `website/content/docs/commands/sync.md` does not imply the syncer is
    git-only.

## Verification

- `cd website && npm install && hugo build --gc --minify` succeeds (the build fails on any broken `{{< relref >}}`).
- `grep -rn "syncer" website/content/ | grep -v "tuis/syncer"` shows no stale cross-references describing the syncer as git-only.
- The page body contains no version history or changelog prose (current-state-only rule).
- `ait upgrade` and `ait setup` are each used per the CLAUDE.md verb semantics.
- All five non-obvious behaviors are documented: the active-target refusal, the declared detection bound, the self-upgrade exit, the "result unknown" reporting, and the settings layer prompt with masking.
- No specific coding agent is named where generic phrasing works.
- Every command or path cited in the page was executed or checked against the as-built code before publishing.

## Out of scope

Behavior changes. If verification finds the docs describe something the code does
not do, the **code** is the source of truth — file the discrepancy rather than
quietly editing the page.

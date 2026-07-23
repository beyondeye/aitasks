---
Task: t1223_5_settings_tab_and_push_action.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_1_*.md, aitasks/t1223/t1223_2_*.md, aitasks/t1223/t1223_3_*.md, aitasks/t1223/t1223_4_*.md, aitasks/t1223/t1223_6_*.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_*_*.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
---

# p1223_5 — Settings tab and push action

> The task file `aitasks/t1223/t1223_5_settings_tab_and_push_action.md` carries
> the full flow and the provenance-marker table. This plan is the execution view.
> Parent design: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`
> (contract **D**).

## Goal

Fill the `tab_settings` pane with a repo × operation matrix of the default code
agent, showing divergence at a glance, and add a push action that brings repos
into agreement. This child **renders and routes** — all value logic lives in
`lib/cross_repo_settings.py` (t1223_4).

## Steps

1. Read `aidocs/framework/tui_conventions.md`; note the render-level
   verification rule (assert `widget.render().plain`, prefer `markup=False`).
2. **Matrix model** — pure helper `build_settings_matrix(diff) -> list[SettingsRow]`
   so divergence and marker logic is testable without a running app. Rows =
   operations, columns = repos labelled by `build_labels()`. Cell text is the
   **effective** value plus a provenance marker: `(local)` / bare (project) /
   `(seed)` / `(default)` / the literal `conflict`. Divergent rows highlighted.
   Opaque positional row keys (`s0`, `s1`, …) + lookup map, mirroring `RowSpec`
   and the Versions rows from t1223_3.
3. **Data load** — `diff_across_repos(roots)` in a thread worker (it shells
   `resolve_agent_string` per repo), reusing the existing coalescing /
   generation-guard machinery. Never re-read on every keypress.
4. **Push action** — key on the Settings tab, gated via `check_action` +
   `_active_tab()`, routed through `ShortcutsMixin` (scope `"syncer"`):
   1. source value (default: the highlighted cell; allow choosing another repo's
      value for that operation);
   2. destinations (multi-select — this writes one config key, not framework
      files);
   3. **layer prompt, always asked, no default** — project (git-tracked, shared)
      vs local (gitignored, personal);
   4. `plan_push` per destination, branching on the typed outcome:
      `ok` → apply · `noop` → report "already matches", apply nothing ·
      `rejected(reason)` → surface destination **and** reason, apply nothing for
      it while siblings still proceed · `masked(masking_value)` → the **three-way
      prompt with no default**: cancel this destination / write local instead /
      clear the local override and write project. The prompt must state the
      masking value and that a project write would otherwise have no effect;
   5. apply, refresh affected rows, and report a **per-destination summary**
      (applied / noop / rejected-with-reason / cancelled) — a single "done" is
      insufficient when destinations diverge.
5. **Failure handling** — a raising write (contract E fail-closed cases) is
   caught per destination, reported by name, and must not abort the remaining
   destinations.

## Verification

- `bash tests/test_syncer_rows.py` passes.
- `build_settings_matrix` renders the right marker for each provenance, and a `conflict` cell renders the literal `conflict` rather than any value.
- Divergence flagging: an all-equal row is not flagged, a row with one differing repo is flagged, and a row containing a `conflict` cell is flagged.
- Render-level: the settings table's cell text for a fixture matrix matches the expected strings including provenance suffixes.
- An `ok` outcome calls `apply_push` exactly once with the chosen layer; a `noop` outcome does not call `apply_push` at all.
- The `masked` three-way prompt routes correctly: cancel performs no `apply_push`; "write local" calls `apply_push(layer='local', clear_mask=False)`; "clear and write project" calls `apply_push(layer='project', clear_mask=True)`.
- A `rejected` outcome surfaces its specific reason string, skips `apply_push` for that destination, and still applies a sibling `ok` destination.
- A destination whose `apply_push` raises is reported by name and the remaining destinations still process.
- The push key is inert on `tab_branches` and `tab_versions`.
- Single-repo mode: with fewer than 2 repos the Settings tab renders read-only and the push action is unavailable.

## Out of scope

Settings other than the default code agent per operation; any change to the value
logic (belongs in t1223_4).

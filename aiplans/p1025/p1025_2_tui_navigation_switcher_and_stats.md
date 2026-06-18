---
Task: t1025_2_tui_navigation_switcher_and_stats.md
Parent Task: aitasks/t1025_design_project_group_grouping_and_tui_navigation.md
Sibling Tasks: aitasks/t1025/t1025_1_*.md, aitasks/t1025/t1025_3_*.md, aitasks/t1025/t1025_4_*.md
Archived Sibling Plans: aiplans/archived/p1025/p1025_1_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-18 15:56
---

# Plan: two-axis TUI navigation — switcher + stats (t1025_2)

## Context

Second child of t1025. t1025_1 landed the **data layer** (now archived): a pure
`group_sessions(sessions, selected_group) -> GroupedSessions(ring, groups)` and a
discovery-resolved `AitasksSession.project_group` (validated slug or `None`; the
registry `-` sentinel never surfaces on a session). This child **wires that model
into the two interactive multi-session TUIs** so the user navigates by two axes:

- **left / right** → cycle the *derived ring* (selected group's repos + any live
  out-of-group repo), not the flat session list.
- **`[` / `]`** → cycle which *project-group* is selected, re-deriving the ring.

No new grouping logic is written here — the TUIs **consume** the already-tested
pure function (`tests/test_project_groups.py` from t1025_1 covers it). See parent
plan `aiplans/p1025_*.md`.

## Verification of plan against current code (verify-path findings)

Checked every cited symbol/line against the current tree. The approach is sound;
the adjustments below fold in (including the six plan-review concerns raised
before approval):

1. **Line numbers drifted** (additive edits, nothing structural moved):
   - switcher `_cycle_session` is now `tui_switcher.py:855`; BINDINGS at `:432`;
     `on_mount` at `:479` (calls `_init_multi_state` → discovery).
   - stats `_cycle_session` at `stats_app.py:487`; `_build_session_items` at
     `:317`; BINDINGS at `:144`.
2. **stats `[` / `]` are ALREADY bound** (`stats_app.py:155-156`) to
   `prev_window` / `next_window`. There is **no hard collision**: those handlers
   are pane-aware — on the `agents.verified` / `agents.usage` panes they cycle the
   ranking *time-window*; on every other pane they are no-ops. Group cycling
   therefore **extends** `action_prev_window` / `action_next_window` with a
   fall-through on non-agents panes, exactly mirroring how `action_prev_verified_op`
   (`:426-433`) already falls through `left` to `_cycle_session` only when not on an
   agents pane. (The parent task's "`add [`/`]` at :153-154" mis-cited the line and
   did not spell out the overload — resolved here.)
3. **monitor / minimonitor need NO code change.** They already pre-select the
   focused/followed agent's session via `_switcher_selected_session`
   (`monitor_app.py:885`, `minimonitor_app.py:761`) → `TuiSwitcherMixin.
   action_tui_switcher` (`tui_switcher.py:1131-1144`) →
   `TuiSwitcherOverlay(selected_session=…)`, and the overlay sets
   `self._session = selected_session or session` (`:458`). The cross-group-follow
   requirement is satisfied **inside the switcher's `on_mount`** by deriving the
   default selected group from `self._session` (the operating/selected session),
   NOT `self._attached_session`. So the parent's "Key Files to Modify" entry for
   monitor/minimonitor collapses to a *verification* item, shrinking blast radius.
4. **Bootstrap drops `project_group` (review concern #1, HIGH).**
   `_ensure_session_live` (`tui_switcher.py:595-600`) flips a registered-inactive
   entry to live by **reconstructing** `AitasksSession(session, project_root,
   project_name, is_live=True)` — which silently resets the frozen dataclass's
   `project_group` (and `is_stale`) to their defaults (`None` / `False`). Today
   that is invisible; once grouped navigation reads `project_group`, selecting a
   registered inactive grouped project and bootstrapping it would make it go
   **ungrouped** mid-session. Fixed in Step 1 with `dataclasses.replace(entry,
   is_live=True)` (preserves every other field). `dataclasses` is not yet imported
   in this module — add the import.

> **Supersedes stale task-file wording (review concern #2, HIGH).** The task file
> `aitasks/t1025/t1025_2_*.md` (Implementation Plan step 1, line 49) and the
> pre-verify plan said the default group comes from the **attached** session.
> That is WRONG for cross-group preselection: opening the switcher from project A
> while focused on project B must default to **B's** group. **This plan is the
> source of truth: the default keys off `self._session` (the selected/operating
> session), never `self._attached_session`.** The implementer must follow the
> plan, not the stale task text; Step 1 also updates the task-file sentence in the
> same change so the two stop disagreeing.

## Steps

0. **Shared pure helpers in `agent_launch_utils.py` (in-task, unit-tested)** —
   review concern #5: the default-group-resolution rule is central enough that
   duplicating it across the two TUIs is the real drift risk, so extract it **now**
   (not as an after-task) beside `group_sessions`:
   - `default_selected_group(sessions, selected_session_name) -> str | None` —
     if a session with `.session == selected_session_name` exists, return **its**
     `project_group` (which may legitimately be `None` ⇒ the ungrouped bucket);
     else return the first entry of `group_sessions(sessions, None).groups`
     (sorted real groups, then `PROJECT_GROUP_UNGROUPED_LABEL`), or `None` when
     `sessions` is empty. **Precise contract:** "selected session's group, else
     first groups entry" — `None` here means *ungrouped*, not "first real group".
   - `advance_selected_group(groups, current, step) -> str | None` — index-wrap a
     `[`/`]` step over the `group_sessions(...).groups` list (returns `current`
     when `groups` is empty). Trivial but shared so both TUIs wrap identically.
   - Unit-test both in `tests/test_project_groups.py` (alongside the existing
     `group_sessions` tests): named-session-found (grouped + ungrouped cases),
     named-session-absent → first group, empty input, wrap-around forward/back.
   Both TUIs call these — no TUI re-implements the rule. This leaves only the
   widget-touching cycle wiring (different widgets per TUI) duplicated; see Risk.

1. **TUI switcher** (`.aitask-scripts/lib/tui_switcher.py`):
   - Add `import dataclasses` (currently absent) and **fix the bootstrap field
     loss** (finding #4 / concern #1): in `_ensure_session_live` (`:595-600`)
     replace the hand-rebuilt `AitasksSession(...)` with
     `self._all_sessions[idx] = dataclasses.replace(entry, is_live=True)` so
     `project_group` (and `is_stale`) survive bootstrap.
   - Add `self._selected_group: str | None` state in `__init__` (`:445-469`),
     initialized in `on_mount` (`:479`) **after** `_init_multi_state` resolves
     `self._all_sessions`, via
     `default_selected_group(self._all_sessions, self._session)` (Step 0).
     Keying off `self._session` — **not** `self._attached_session` — is what makes
     cross-group preselection follow the preselected session (finding #3 +
     superseded task text).
   - `_cycle_session` (`:855-875`): cycle the **derived ring**
     `group_sessions(self._all_sessions, self._selected_group).ring` (by
     `.session` name), not flat `self._all_sessions`. Keep the existing
     `SkipAction` priority-binding guard and the `< 2` short-circuit (apply the
     `< 2` check to the *ring* length).
   - BINDINGS (`:432-443`): add
     `Binding("[", "prev_group", "Prev group", show=False, priority=True)` and
     `Binding("]", "next_group", "Next group", …)`; add `action_prev_group` /
     `action_next_group` beside `action_prev_session` (`:849-853`) that set
     `self._selected_group = advance_selected_group(group_sessions(...).groups,
     self._selected_group, ±1)`, re-derive the ring, **re-point `self._session` to
     a ring member when the current selection fell out of the new ring**, then run
     the same refresh trio as `_cycle_session` (`_render_session_row()` +
     `_render_desync_line()` + `_populate_list_for()`). Guard with the same
     `SkipAction` pattern.
   - Render the selected-group label in the session row (`_render_session_row`,
     `:671-705`) — e.g. prefix `Group: <name>  Session: …` — so the active axis is
     visible. Only show when `_multi_mode` and ≥1 real group exists.
   - Update the stale task-file sentence (line 49, "attached session") to
     "selected session" in the same change (concern #2). The task file lives on
     the aitask-data branch → commit via `./ait git`.
2. **stats TUI** (`.aitask-scripts/stats/stats_app.py`):
   - Add `self._selected_group` state (`__init__` `:162`), default resolved in
     `on_mount` (`:242`) via `default_selected_group(self.sessions,
     self.selected_session)` (Step 0). When `selected_session == ALL_SESSIONS_KEY`
     it is not in `self.sessions`, so the helper returns the first group — correct
     (the aggregate is group-agnostic).
   - **Single ring builder** — add a small `_session_ring()` helper that returns
     `[s.session for s in group_sessions(self.sessions, self._selected_group).ring]
     + [ALL_SESSIONS_KEY]`, layering the aggregate as a fixed final member **here**
     (NOT inside pure `group_sessions()`). `_cycle_session` (`:487-513`) and the
     group-cycle path both use it, so left/right reaches the aggregate and `[`/`]`
     never selects it.
   - `_build_session_items` (`:317-325`): unchanged structurally; the sidebar
     still lists all sessions + the aggregate.
   - `action_prev_window` / `action_next_window` (`:444-448`): extend with a
     pane-guarded fall-through — on `agents.verified` / `agents.usage` panes call
     `_cycle_window` (existing); `elif self.multi_session:` advance
     `self._selected_group` (via `advance_selected_group`), re-derive the ring,
     and **if the current `selected_session` is no longer in the ring, re-point it
     to the ring's first member AND mirror the `#session_list` highlighted index**
     using the SAME sidebar-sync block `_cycle_session` already runs (`:499-506`)
     — otherwise the highlighted row, the title, and the loaded data disagree
     (concern #3). Refactor that sidebar-mirror + `_load_data/_update_title/
     _refresh_current_pane` tail into a shared `_apply_session_selection(new_key)`
     so both `_cycle_session` and the group-cycle path stay in lockstep. No new
     BINDINGS line — `[`/`]` are already bound (`:155-156`); only the action
     bodies grow.
   - **Footer labels (concern #4):** the existing `[`/`]` bindings read
     `"prev window"` / `"next window"`; after the overload they mean *time-window*
     on the two agents panes and *project-group* elsewhere. Relabel to
     `"prev win/grp"` / `"next win/grp"` (or similar) so the footer is not
     misleading, and spell the dual meaning out in the conventions doc (Step 4).
3. **Monitor / minimonitor:** **verification only** (finding #3) — confirm the
   switcher opens with its selected group following the preselected session's
   group. No code edit expected; if the manual/headless check shows the default
   group keys off the attached (not selected) session, fix it in
   `tui_switcher.on_mount` (step 1), not in the monitor files.
4. **Conventions doc** — update `aidocs/framework/tui_conventions.md` (the "TUI
   switcher shortcuts act on the *selected* session" section, `:174-211`) with the
   two-axis model (`[`/`]` = group axis, left/right = ring axis), the stats
   `[`/`]` **pane-guarded dual meaning** (time-window on agents panes, project-
   group elsewhere — concern #4), and the aggregate-as-fixed-ring-member rule, in
   the same commit so the doc never lags the binding.

## Verification

- **Pure helpers** (`tests/test_project_groups.py`) — `default_selected_group`
  and `advance_selected_group` per Step 0 (named-found grouped/ungrouped,
  named-absent → first group, empty, wrap-around). These are the central
  drift-risk units, so they are tested directly, not only through the TUIs.
- **Headless ring-derivation through the real entry points** — extend
  `tests/test_multi_session_primitives.sh` and `tests/test_multi_session_monitor.sh`
  (and/or `tests/test_project_groups.py`): drive `_cycle_session` /
  `action_next_group` on a constructed `TuiSwitcherOverlay` / stats app with a
  fixture session set spanning ≥2 groups + a live out-of-group repo, asserting:
  - `[` / `]` advances the selected group; left/right stays within the ring.
  - a live-but-out-of-group repo appears in the ring while a different group is
    selected; a stale out-of-group repo does not.
  - stats: `ALL_SESSIONS_KEY` is reachable by left/right and **unaffected** by
    `[` / `]`; on `agents.verified` / `agents.usage` panes `[` / `]` still cycle
    the time-window (no regression); after a group-cycle that re-points the
    selected session, the `#session_list` highlighted index, title, and loaded
    data agree (concern #3 — via `_apply_session_selection`).
  - cross-group preselection: opening the switcher with `selected_session` in
    group B sets `_selected_group = B` (monitor + minimonitor paths).
  - **bootstrap retains group (concern #1/#6):** a registered **inactive grouped**
    entry, after `_ensure_session_live` flips it live, still carries its
    `project_group` in the cached `self._all_sessions` slot (assert via
    `dataclasses.replace` preserving the field) — so it stays in its group's ring
    rather than silently dropping to ungrouped.
- No regression for `TuiSwitcherMixin` consumers (board / codebrowser / brainstorm)
  — the switcher with one ungrouped session still cycles the flat ring.
- `shellcheck` n/a (Python); run the Python test suite
  (`tests/run_all_python_tests.sh`) and the two bash multi-session tests.
- Manual smoke (covered live by sibling t1025_5): launch `ait board` / switcher
  with ≥2 groups + a live out-of-group session.

## Risk

### Code-health risk: medium
- Touches the two shared multi-session TUIs (`tui_switcher.py`, `stats_app.py`);
  the switcher is consumed by board / codebrowser / brainstorm / monitor /
  minimonitor, so a regression in `_cycle_session` or the BINDINGS has wide blast
  radius. · severity: medium · → mitigation: covered in-task by extending the
  headless primitives/monitor tests + the no-regression assertion for
  TuiSwitcherMixin consumers.
- stats `[` / `]` overload (group cycling vs existing time-window cycling on the
  agents panes) must be pane-guarded correctly or it silently breaks the ranking
  time-window navigation. · severity: medium · → mitigation: covered in-task by
  the "agents-pane `[`/`]` still cycles the window" regression assertion.
- `_ensure_session_live` bootstrap previously rebuilt the session dataclass and
  would drop `project_group`. · severity: medium · → mitigation: covered in-task
  by the `dataclasses.replace` fix (Step 1) + the bootstrap-retains-group test
  (concern #1/#6).
- The **central** default-resolution rule is now a shared, unit-tested pure
  helper (`default_selected_group`/`advance_selected_group`, Step 0), so the main
  drift risk is removed in-task. What remains duplicated is the per-TUI
  **widget-wiring** of a group cycle (switcher session-row vs stats sidebar +
  title + panes), which is genuinely TUI-specific. · severity: low ·
  → mitigation: consolidate_group_cycle_wiring

### Planned mitigations
- timing: after | name: consolidate_group_cycle_wiring | type: refactor | priority: low | effort: low | addresses: code-health (residual per-TUI group-cycle widget-wiring duplication; the central default-resolution is already shared in-task via Step 0) | desc: If the switcher and stats group-cycle action bodies prove meaningfully duplicative after implementation, factor the common "advance group → re-derive ring → re-point selection → refresh" sequence into a shared mixin/helper; the pure default-resolution already lives in `agent_launch_utils.py`.

### Goal-achievement risk: low
- Approach consumes the already-built, already-tested pure `group_sessions()`
  from t1025_1; the contract was verified against current code and every
  requirement (two axes, out-of-group live in ring, aggregate untouched,
  cross-group preselection) maps to a concrete step. · severity: low
- The cross-group-preselection requirement is satisfied structurally (default
  group derived from `self._session`), removing the monitor/minimonitor code
  edits the parent assumed — lower delivery risk, not higher. · severity: low

## Step 9
Standard child archival (see parent plan / task-workflow Step 9). Final
Implementation Notes must record, for siblings t1025_3 (settings editor) and
t1025_4 (docs): the new shared `default_selected_group` / `advance_selected_group`
helpers in `agent_launch_utils.py` (reuse them, don't re-derive); the
`dataclasses.replace` bootstrap fix in `_ensure_session_live`; the stats `[`/`]`
pane-guarded dual meaning + relabel; the aggregate-as-fixed-ring-member layering
(`_session_ring`); the `_apply_session_selection` sidebar-sync helper; and that
monitor/minimonitor were verification-only.

## Final Implementation Notes

- **Actual work done:** Implemented the two-axis navigation as planned.
  `agent_launch_utils.py`: added pure `default_selected_group` +
  `advance_selected_group` beside `group_sessions` (Step 0). `tui_switcher.py`:
  `import dataclasses`; `_ensure_session_live` now `dataclasses.replace(entry,
  is_live=True)` (preserves `project_group`/`is_stale`); `_selected_group` state
  defaulted in `on_mount` from `self._session`; `_ring_names()` +
  `_refresh_after_cycle()` + `_switcher_list_or_skip()` helpers; ring-based
  `_cycle_session`; `[`/`]` bindings → `action_prev/next_group` → `_cycle_group`
  (re-derive ring, re-point `self._session` if it fell out); selected-group label
  in `_render_session_row` + `[/]` group hint in `_render_hint`. `stats_app.py`:
  `_selected_group` state; `_session_ring()` (aggregate `ALL_SESSIONS_KEY`
  layered last); `_apply_session_selection()` shared by session + group cycling;
  `action_prev/next_window` → `_cycle_window_or_group` pane-guarded fall-through
  (time-window on `agents.verified`/`agents.usage`, project-group elsewhere);
  `[`/`]` footer labels → `win/grp`. `aidocs/framework/tui_conventions.md`:
  two-axis model section. Also corrected the stale task-file "attached session"
  wording (committed separately via `./ait git`).

- **Deviations from plan:** stats `_selected_group` is resolved in `__init__`
  (right after `selected_session`), not in `on_mount` as written — the
  resolution is pure (no widgets), so `__init__` is simpler and avoids any
  pre-mount `None` window; functionally identical. The switcher keeps the plan's
  `on_mount` timing because its `self._session` may be re-pointed by
  `_init_multi_state`.

- **Issues encountered:** A Rich-markup escaping bug in the first `_render_hint`
  attempt rendered `[/]]` (stray `]`); fixed to `\[/]` → `[/]` (verified via a
  `rich.Text.from_markup` render probe). The bootstrap field-drop in
  `_ensure_session_live` (planned finding #4) was confirmed real against the
  current code and fixed with `dataclasses.replace`.

- **Key decisions:** (1) The central default-resolution rule was pulled into a
  shared, unit-tested pure helper (`default_selected_group`) in-task rather than
  deferred, removing the main cross-TUI drift risk at the source (review concern
  #5). (2) The "All sessions" aggregate is layered onto the ring by each TUI's
  ring builder (`_session_ring`), never inside pure `group_sessions()`, so
  left/right reaches it while `[`/`]` never selects it. (3) Cross-group
  preselection is structural: the switcher defaults its group off `self._session`
  (the operating/selected session), so monitor/minimonitor needed no code change
  — verified by the Pilot test.

- **Upstream defects identified:** None. (The `_ensure_session_live` bootstrap
  field-drop was a pre-existing latent defect in the same module being edited and
  was fixed in-task, not deferred — so no separate follow-up is warranted.)

- **Notes for sibling tasks (t1025_3 settings editor / t1025_4 docs):**
  - Import and reuse `default_selected_group(sessions, selected_session_name)`
    and `advance_selected_group(groups, current, step)` from
    `agent_launch_utils.py` — do NOT re-derive the default/advance rules. `None`
    from `default_selected_group` means the *ungrouped bucket*, not "first real
    group".
  - The aggregate-as-fixed-ring-member pattern lives in the TUI ring builder
    (`stats_app._session_ring`), not in `group_sessions`. Any new consumer that
    needs a pinned, group-agnostic ring entry should layer it the same way.
  - The shared `_apply_session_selection` (stats) keeps the sidebar highlight,
    title, and loaded data in lockstep — route any new selection change through
    it, not through a bespoke `selected_session =` assignment.
  - A confirmed `after` risk-mitigation task (`consolidate_group_cycle_wiring`)
    was queued for the residual per-TUI group-cycle widget-wiring duplication.

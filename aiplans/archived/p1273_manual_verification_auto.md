# Plan: Manual verification (auto-execution) — t1273

Task: `aitasks/t1273_manual_verification_bytrail_refresh_semantics_followup.md`
Verifies: t1268 (By-Trail refresh semantics and key/footer contract)
Working directory: `/home/ddt/Work/aitasks` (current branch, profile `fast`)
Strategy: autonomous auto-verification (`auto-verification.md` §2a)

## Approach

Every item was driven against a **real `ait board`** running in a detached tmux
session (200x45, later 400x50 to un-truncate the footer), against the real
repository and the real trail artifact. Assertions are on captured pane content
(`tmux capture-pane -p`), not on model state.

Two items needed instrumentation, both documented in their log entries below:

- **Item 4** — the artifact-version watch. The `R` launch, the tmux window, the
  off-thread baseline read and the watch install were all real; the *new
  artifact version* was published out-of-band with `ait artifact update`
  instead of being authored by the launched agent.
- **Item 5** — the pending-footer transient. `pilot.pause()` drains the whole
  worker in one tick, so the window is unobservable headlessly; the real
  `_trail_versions` was wrapped with an 0.8s sleep to make it samplable. The
  flag/`refresh_bindings` logic itself is untouched.

### Fixture

To avoid launching a real model-authored refresh against the user's own trail,
a fixture trail artifact `art:trail-t1273-verify` was created on t1273 (a copy
of `art:trail-gates-framework-landing`'s document with a distinct
`trail_id`/`title`) and used for items 4 and 5. It was removed at the end
(`ait artifact rm 1273 art:trail-t1273-verify`); `ait artifact list` shows only
the original trail again.

## Execution Log

### Item 1 — footer contract in By-Trail, and revert on leaving

- Approach: TUI interaction (tmux), footer row capture.
- Action run: `z` → selector → `Enter` (activate trail) → capture last pane row;
  then `a` → capture last pane row.
- Output (trimmed):
  - By-Trail: `? Keys  q Quit  ⏎ View/Edit  r Refresh  R Agent Refresh  d Freshness  s Select Trail  S Sync  n New Task  O Options`
  - after `a`: `? Keys  q Quit  shift+→ Task > … r Refresh  s Sync  C Commit All  n New Task  ^→ Move Col > …`
- Verdict: **pass** — labels and order match exactly, and the generic pair plus
  `C Commit All` come back on leaving.

### Item 2 — `r` is a local recompute of an on-disk status change

- Approach: file mutation + TUI interaction, polled at 50 ms.
- Action run: edited `aitasks/t635/t635_30_task_gate_editing_surface.md`
  `status: Ready` → `Postponed`; confirmed the card was *unchanged* without a
  keypress; sent `r`; polled the card's column slice until it changed; restored
  the file to `Ready` and re-rendered.
- Output (trimmed): baseline `📋 Ready` → (no keypress) `📋 Ready` → after `r`,
  `📋 Postponed` at **0.33 s**; no modal on screen (`Select trail` /
  `Implementation Trail` / `Enter to activate` all absent).
- Verdict: **pass**. `t635_30` was restored and is clean in `ait git status`.

### Item 3 — `d` banner transitions + per-card drift markers

- Approach: TUI interaction; six pane captures at 1 s intervals after `d`.
- Output (trimmed):
  - Drift markers: present and detail-bearing, on the owning cards, including
    the archived ghost — `╏ ✔ aitasks#1264 ╏ / ╏ 👻 archived — read-only ╏ /
    ╏ ⚠ task_completed: aitasks#1264 compl ╏`.
  - Banner: **absent in every frame** — no `⟳ checking freshness…`, no
    `⚠ stale:`. No `sub_title` text at all is drawn by the board (not even the
    default `Auto-refresh: off`): `KanbanApp.compose` yields a `Header`, but the
    board CSS also declares `#filter_area { dock: top; … }`, and that second
    top-docked widget takes row 0. Reproduced minimally on the same
    pypy/Textual 8.2.7: the header row appears with `dock: top` removed and
    vanishes with it added. Headless `run_test` reports the Header as
    `display=True, region=(0,0,120,1)`, so `sub_title`-level tests cannot see it.
- Verdict: **fail** → **t1278**.

### Item 4 — post-`R` artifact-version watch picks up a new document

- Approach: real launch + out-of-band version publish (see Approach note).
- Action run: `R` on the fixture trail → `AgentCommandScreen` showed
  `claude --model claude-opus-5 /aitask-trail\ --refresh\ art:trail-t1273-verify`
  → confirmed → agent started in tmux window `agent-trail-trail-t1273-verify`;
  then `ait artifact update art:trail-t1273-verify v2.json` (v2 renames wave 1
  to `W1 · WATCH-PICKUP-MARKER`); polled the board pane every 0.5 s.
- Output (trimmed): `Trail artifact updated — reloading` at **13.1 s**; the new
  wave title rendered at **13.6 s** — inside the 20 s `TRAIL_WATCH_INTERVAL`,
  with no keypress.
- Verdict: **pass**.

### Item 5 — double `R`, and the footer while a launch is pending

- Approach: TUI interaction (tmux) + headless drive of the real `KanbanApp`
  with `launch_in_tmux` stubbed.
- Output (trimmed):
  - Footer half: with `_trail_launch_pending` True, `trail_refresh_agent` is
    absent from `screen.active_bindings`; it returns after the launch completes
    and `_trail_watch_timer` is installed. **Holds.**
  - No-op half: the second `R` is consumed by `AgentCommandScreen`, which binds
    `r`/`R` → `run` (`agent_command_screen.py:339-340`). Live, it closed the
    dialog and started a real agent; headless, `launch_in_tmux` was called
    exactly once and the screen returned to the board. The board's own guard in
    `action_trail_refresh_agent` is never reached. **Fails.**
- Verdict: **fail** → **t1279**.

### Item 6 — `C` is hidden in By-Trail

- Approach: TUI interaction; screen diff.
- Action run: made a task modified (the checklist marks on t1273) so
  `C Commit All` was live in All view; switched to By-Trail; captured; sent `C`;
  captured again.
- Output (trimmed): `C Commit All` present in the All footer, absent from the
  By-Trail footer; the two captures are byte-identical after `C`; `ait git
  status` still shows `M aitasks/t1273_…md` (nothing was committed).
- Verdict: **pass**.

### Item 7 — `S` runs `ait sync`

- Approach: TUI interaction + git ground truth on the data worktree.
- Output (trimmed): toast `Sync: Pushed`; `.aitask-data` went from `16 0` to
  `0 0` against upstream, with the in-progress checklist marks auto-committed
  (`ait: Auto-commit task changes before sync`). Post-sync the board runs
  `load_tasks` + `refresh_board(refresh_locks=True)` and re-runs the trail drift
  check.
- Verdict: **pass**, with the scope note that nothing was behind, so the "cards
  reflect what was pulled" half exercised only the reload path already proven in
  item 2.

### Item 8 — cancelled selector leaves only `s` / `S`

- Approach: TUI interaction; footer capture.
- Output (trimmed): `? Keys  q Quit  ⏎ View/Edit  s Select Trail  S Sync  n New
  Task  O Options` — `r`, `d`, `R` all absent, matching the "every refresh key
  needs a trail to act on" gate.
- Verdict: **pass**.

### Item 9 — selection-modal badge says "(recorded)"

- Approach: TUI interaction; modal row capture.
- Output (trimmed): `Gate framework landing order (t635 topic)   owner t635 ·
  ad_hoc · ✓ current (recorded) · 2026-07-27T08:59:52Z`.
- Verdict: **pass**.

### Item 10 — By-Trail flows end-to-end in tmux

- Approach: the whole checklist above was driven against a live `ait board` in
  tmux — view switch, selector open/cancel/activate, `r`, `d`, `R`, `C`, `S`,
  footer transitions across views, and the watch pickup.
- Verdict: **pass** (two defects surfaced: items 3 and 5).

## Cleanup

- Fixture artifact `art:trail-t1273-verify` removed from t1273
  (`ait artifact rm`); `ait artifact list` shows only
  `art:trail-gates-framework-landing`.
- `aitasks/t635/t635_30_task_gate_editing_surface.md` restored to
  `status: Ready` (clean in `ait git status`).
- tmux sessions `vt1273` / `vt2` (board) and the `hdrtest*` probe sessions
  killed.
- Scratch files under
  `/tmp/claude-1000/-home-ddt-Work-aitasks/…/scratchpad/vt1273/` are outside the
  repo and need no removal.
- **Outstanding:** the agent window spawned by item 5's double-`R`
  (`aitasks:10`, `agent-trail-trail-t1273-verify`, PID 1160763) is still
  running; killing it was blocked by the sandbox, so it must be closed by hand.
  Its target handle no longer exists, so it cannot write anything.

## Outcome

8 pass, 2 fail (items 3 and 5 → t1278, t1279), 0 skip, 0 defer.

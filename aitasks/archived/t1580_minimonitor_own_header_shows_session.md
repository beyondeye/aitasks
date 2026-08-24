---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-23 16:26
updated_at: 2026-08-24 13:33
completed_at: 2026-08-24 13:33
---

## Problem

In `ait minimonitor`, the docked top panel that identifies the agent this
minimonitor was spawned for shows only `── this agent ──` (or `── this window ──`)
above the tmux window name and task title. It never says which repo/project that
agent belongs to.

Every *other* agent in the list is grouped by repo — `_rebuild_pane_list` emits a
`format_session_divider(session_name)` rule whenever the session changes — so the
followed agent is the one entry on screen with no project context. In a
multi-repo tmux setup this makes the top panel ambiguous: the user can see which
repo each listed agent is in, but not which repo their *own* agent is in.

## Requested change

Expand the `── this agent ──` header line with the associated tmux session name,
e.g. `── this agent · aitasks_mobile ──` (exact separator/format to be settled in
planning).

## Findings from exploration

- The header is mounted in `_maybe_build_own_agent_panel`
  (`.aitask-scripts/monitor/minimonitor_app.py:~1882`) as
  `Static(f"[dim]── {label} ──[/]", classes="mini-own-header")`, where `label` is
  `"this agent"` when the own pane is `PaneCategory.AGENT` and `"this window"`
  otherwise. The panel is built **once** and never rebuilt, which is fine here:
  the session of the followed pane does not change over the minimonitor's
  lifetime.
- **Zero row cost.** `.mini-own-header` is `height: 1` and `_OWN_PANEL_MAX_ROWS`
  (minimonitor_app.py:~465) budgets it as exactly 1 row regardless of its text,
  so putting the session on this line does *not* require bumping
  `_OWN_PANEL_MAX_ROWS` or `_MAX_CHROME_ROWS`. This is why the header line is
  preferable to an extra identity row inside `_own_agent_identity_text`, which
  would cost a row and force both constants (and the 40x12 pane-list floor in
  `tests/test_minimonitor_top_chrome_render.py`) to be re-derived.
- **Width is the real constraint.** With `padding: 0 1` a 40-column companion
  pane leaves ~38 usable cells; `── this agent ──` is 15. A long session name
  must be truncated (or the header degrades gracefully back to the bare label),
  otherwise the `height: 1` rule clips the trailing `──` and the line reads as
  broken. Note `_target_width` is configurable, so the budget must be derived
  from it, not from a hardcoded 40.
- **Source of the value.** `own_snap.pane.session_name` (populated by discovery;
  documented as `""` only when a `PaneInfo` is constructed outside a list-panes
  path — fall back to `self._session` in that case).
- **Session name vs project name.** The other agents' dividers show the *tmux
  session* name, so using the session name here is the consistent choice. Be
  aware of the caveat documented on `AitasksSession` in
  `.aitask-scripts/lib/agent_launch_utils.py`: tmux session names are not unique
  across repos — unconfigured repos all fall back to the literal `"aitasks"` —
  and the truly distinguishing display value is
  `project_name = basename(project_root)`. A seam already exists to resolve it:
  `_root_for_snap(snap)` (minimonitor_app.py:~1296) →
  `monitor.get_session_to_project_mapping()`, which matters because in
  multi-session mode the followed pane may belong to a different project than
  `self._project_root`. Planning should decide session-name-only vs.
  session-name-with-project-basename-fallback.
- **Single-session mode.** The session divider renders only when
  `monitor.multi_session` is true, so in single-session mode this header would be
  the *only* repo signal on screen — an argument for showing it unconditionally
  rather than gating it on multi-session mode.

## Constraints / existing guards to respect

- `tests/test_monitor_session_divider.py::test_own_panel_header_stays_dim` is a
  deliberate negative control: it asserts this header keeps its `dim` style and
  does **not** take the divider's cyan or the section header's colour. The
  appended session name must stay dim — do not reuse
  `format_session_divider` styling here.
- `tests/test_minimonitor_top_chrome_render.py` asserts `"this agent"` appears in
  the flattened header row and pins `_OWN_PANEL_MAX_ROWS` / the chrome budget;
  the substring must survive whatever format is chosen.
- `tests/test_minimonitor_other_section.py` asserts both the `"this agent"` and
  `"this window"` variants — the `"this window"` (renamed-window) path needs the
  same treatment or an explicit decision to leave it bare.

## Acceptance criteria

- The minimonitor own-agent panel header names the tmux session of the followed
  agent, in both the `this agent` and `this window` states (or with a documented
  decision for the latter).
- The header still occupies exactly one row at every supported `_target_width`,
  with a long session name truncated rather than clipped or wrapped.
- The header keeps its dim style; the divider/section-header colours stay
  reserved for the pane list.
- A test pins the rendered header content (including the truncation boundary) and
  the existing guards above still pass.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-24T09:58:47Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-24T10:29:12Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-24T10:33:08Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:4b14ffb4d06c6910

> **✅ gate:risk_evaluated** run=2026-08-24T10:33:08Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1580/risk_evaluated_2026-08-24T10:33:08Z-risk_evaluated-a1.log`

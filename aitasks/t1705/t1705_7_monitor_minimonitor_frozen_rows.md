---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1705_6]
issue_type: feature
status: Implementing
labels: [minimonitor, aitask_monitor, aitask_monitormini, tui, textual, agent_marks, session_persistence, python, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
implemented_with: claudecode/opus5
created_at: 2026-09-04 16:06
updated_at: 2026-09-09 12:18
---

## Context

Seventh child of t1705 (frozen code agents). Surfaces the frozen state in
**both** monitor TUIs and wires the user-facing keys. A frozen agent is
listed as an agent-like row — no live state dot, no status, **no capture,
no prompt/idle detection** — exactly the shape t1685 gave `parked`, but
sourced from the pane option `@aitask_frozen` (read in
`_LIST_PANES_FORMAT`, appended by t1705_4) rather than from a marks pair.
Decided with the user (**PINNED**): `frozen` **coexists** with the
priority/parked mark — the row composes both glyphs, `<mark glyph><F> <name>
frozen`; `frozen` wins for *behaviour* (exclusion, filter, keys), the mark
glyph is display-only on a frozen row, and the `space` mark cycle stays
enabled. The parent plan (§B/§C/§D) and this child's plan
(`aiplans/p1705/p1705_7_monitor_minimonitor_frozen_rows.md`) are normative;
`aiplans/archived/p1685_park_code_agents_tristate_mark_and_visibility_toggle.md`
is the site-by-site template (its `## Final Implementation Notes` record the
10-row hint budget, the `SimpleNamespace` doubles, and the class-level floor
lessons — read them first).

## Deliverables

1. **`monitor_core.py`** — `PaneSnapshot.frozen: bool = False` +
   `frozen_record_id: str = ""` (from `TmuxPaneInfo.frozen_record`, parsed
   by t1705_4); `_frozen_snapshot()` beside `_parked_snapshot()` (:1045-1068,
   outside `_apply_bookkeeping`); `ClassifyResult.frozen`; in
   `capture_all_classified_async` (:2886-2942) split frozen panes out **after**
   `_record_discovery_facts` exactly like parked, re-inject as
   `ClassifyResult(compare_value="", frozen=True)`; `commit_snapshots`
   (:3019-3027) routes to `_frozen_snapshot`. No `set_frozen_agents`
   publish-down is needed — the pane option is in the discovery row — but
   keep the `category == AGENT` guard.
2. **`monitor_shared.py`** — `FROZEN_GLYPH = "F"` beside `PARK_GLYPH`
   (:240-252) with the same measurement rationale (`U+0046`, covered by both
   supported families, not emoji-capable — regenerate
   `tests/data/font_coverage.json` via `tests/tools/regen_font_coverage.py`
   and extend `tests/test_mark_glyphs_single_source.py`); `format_frozen_row_prefix(kind)`
   returning `format_mark_glyph(kind) + "[bold cyan]F[/]"`; `_hide_frozen`
   class floor + `_init_agent_marks` default; `_is_frozen(snap)`;
   `action_toggle_frozen_visibility` (`F`); `_maybe_purge_sessions()` twin of
   `_maybe_purge_marks()` (:888+) dispatched — never awaited — from the same
   maintenance tick with the same startup grace, writing the observation file
   with `panes=` (`PANE` rows from `TmuxMonitor.last_discovered_panes()`)
   and calling `aitask_agent_sessions.sh purge --observed` **and**
   `aitask_frozen.sh reconcile`; the shared `_run_marks_cmd` seam.
3. **Both apps — every partition site** (the parked list in the parent
   plan's survey): row render (`minimonitor_app.py:2249-2270`,
   `monitor_app.py:1714-1732`) → `f"{prefix} {name}  [dim]frozen[/]"` with
   the mark glyph from `_mark_kind(snap)`; `_rebuild_pane_list` filter
   (`_hide_frozen and s.frozen`); `_compute_completed_panes` skip; monitor
   `_maybe_auto_switch` ×3, concern auto-offer, signature scan, preview
   placeholder (`This agent is frozen — press R to restore, p to re-pick.`),
   `_focus_next_visible_card` / `_hand_off_focus_before_hiding`; session-bar
   terms: minimonitor `Nf` (`[dim]{n}f[/]`) after `Np`, monitor `N frozen`
   after `N parked`; both **independent of the filter** and both leave the
   three live buckets (`live = [a for a in agents if not a.parked and not
   a.frozen]`).
4. **Keys** (check collisions against each app's BINDINGS first — `z`/`Z`
   are proposals): minimonitor `z` = freeze the **followed** agent (own-agent
   resolution like `action_toggle_mark`'s override, :5028-5052; confirm
   dialog reusing `KillConfirmDialog`'s shape: "Freeze t1705 — the process
   ends; output is kept and restorable"), `Z` = Freeze-All (confirm, lists
   the count), `R` = restore / `p` = re-pick on a **frozen** focused row
   (`p` keeps its pick semantics on a live row — guard on `snap.frozen` in
   the action, not just the binding), `k` on a frozen row = drop
   (KillConfirmDialog text says "remove frozen record and capture"), `F` =
   filter; monitor: same actions on the focused card, `Z` in the Footer.
   All mutations shell out: freeze via
   `subprocess` to `aitask_frozen.sh freeze <pane>`/`--all` (dispatched via
   the `_run_marks_cmd` seam, result line → `notify`), restore/re-pick via
   `TmuxClient.run(["run-shell","-b", …])`, drop via `aitask_agent_sessions.sh
   drop` + `kill_agent_pane_smart` rule. Minimonitor hint text: fold
   `z:freeze F:frozen` onto an existing line — **ten rows, not eleven**
   (`test_minimonitor_top_chrome_render` pins it; `KEY_HINTS_TEXT`
   :781-797); parity test `test_key_hints_surface_every_binding`
   (`tests/test_minimonitor_concern_action.py:3053-3064`) must stay green.
5. **Docked own-panel (minimonitor)** — when the followed agent is frozen
   (this window's own pane is the stand-in), `_refresh_own_live_state`
   shows `F frozen <frozen_at>` and no phase line; `n` (next sibling) stays
   enabled; the companion does **not** auto-despawn (the stand-in counts as
   a real agent, t1705_4's cleanup rule).
6. **Restore feedback**: after `R`/`p`, poll `SessionsView` (1 s, bounded by
   `restore_ack_grace` + 5 s) and `notify` the outcome line
   (`RESTORED … hook` / `… liveness — capture kept` / `RESTORE_FAILED …`).

## Tests (mirror `tests/test_monitor_parked_capture.py` and
`tests/test_monitor_parked_filter.py` case for case)

`tests/test_monitor_frozen_capture.py`: a frozen pane is never captured or
classified (recorded call args, negative control), still commits a
`frozen=True, content=""` snapshot, survives discovery, only AGENT panes are
freezable, shadow panes never filtered. `tests/test_monitor_frozen_filter.py`:
row render (glyph composition for none/priority/parked marks; forbids
`● ◆ ≈ = IDLE PROMPT Active` on a frozen row; positive control), mounted
row, `F` filter both apps + no collision, hint row exists and hints stay
ten rows, focus handoff cases, preview placeholder, session-bar partition
(frozen leaves every live bucket; term present, absent at zero, independent
of the filter), auto-switch never picks a frozen pane, `p`/`R`/`k`/`z`
actions produce the exact subprocess / `run-shell -b` argv (fake seams) and
are refused on a live row where they must be, `space` cycle still works on
a frozen row, own-panel frozen render. Complete every hand-rolled
`SimpleNamespace` snapshot double in the seven test modules t1685 listed
(add `frozen=False`, `frozen_record_id=""`) rather than making renderers
defensive.

## Key files

- Edit: `monitor/monitor_core.py`, `monitor/monitor_shared.py`,
  `monitor/minimonitor_app.py`, `monitor/monitor_app.py`,
  `tests/data/font_coverage.json` (+ generator), `tests/test_mark_glyphs_single_source.py`,
  `tests/test_monitor_agent_marks.py`, the seven double-bearing test modules.
- New: the two test modules above.

## Reference patterns

- `aiplans/archived/p1685_…md` §4–§9 and its notes; `monitor_shared.py:237-295`
  (glyphs, `format_mark_glyph` raise-on-unknown — do **not** add `frozen`
  as a mark kind), `:361-384`, `:455-490`, `:629-673`, `:790-886`
  (maintenance tick, observation writer); `minimonitor_app.py:1532-1561`
  (`_refresh_data` ordering), `:1758-1783`, `:2159-2226` (session bar),
  `:2496-2545`, `:2856-2896` (`k` flow), `:2898-2938` (`n`), `:5028-5052`;
  `monitor_app.py:385-392`, `:1010-1048`, `:1622-1732`, `:1819-1831`,
  `:1955-1968`, `:2658-2710`; `aidocs/framework/tui_conventions.md`
  (keybinding registration, hover/focus rules).

## Verification

```bash
bash tests/run_all_python_tests.sh                    # both frozen suites + parked suites + chrome render + hints parity
python3 tests/tools/regen_font_coverage.py && git diff --stat tests/data/font_coverage.json
bash tests/test_multi_session_monitor.sh tests/test_multi_session_minimonitor.sh
./ait minimonitor   # manual: freeze the followed agent with z on an isolated server first
```
The live parts (freezing from the TUI) are tmux-stress — try them on an
isolated server or a throwaway `-L` socket, never on the user's `ait` server
from inside an agent pane.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705_6** id=2026-09-09T06:09:42Z.a4ee0adf046aa754e79a9db6 from=t1705_6 from_verified=yes at=2026-09-09T06:09:42Z base=ccff05e3d1d4c360e6ea81a91bc81413825691fa base_branch=main dirty=yes host=Darios-Mac-mini.local
>
> | t1705_6 changed code t1705_7 builds on. Three things, all in shipped files.
> | 
> | 1. `kill_agent_pane_smart`'s frozen branch is now KILL-THEN-DROP (it was
> |    drop-then-kill). The old order had an unrecoverable failure mode: a failed
> |    kill left a live pane still stamped `@aitask_frozen=<id>` whose record and
> |    capture were already gone, and `reconcile` iterates RECORDS, so nothing could
> |    repair it. Kill-first leaves `frozen` record + gone pane on failure, which is
> |    reconcile's benign `KEEP:<id>|pane_gone` row. Do not reorder it back.
> | 
> | 2. The pane-classification rule moved out of that method into module-level
> |    `FROZEN_AWARE_PANE_FORMAT` + `classify_window_panes` in `monitor_core.py`,
> |    so the frozen-agent coordinator is a second CALL SITE rather than a fourth
> |    copy. The format gained `#{pane_dead}` and is now 6 fields — anything that
> |    builds a row for it must match, because `classify_window_panes` silently
> |    SKIPS a wrong-arity row (that already bit `tests/test_monitor_companion_filter.py`:
> |    every pane vanished and the verdict flipped `pane` -> `window`). Its `_line`
> |    fixture now derives the row FROM the format for that reason.
> | 
> | 3. `aitask_frozen.sh drop <id>` exists now, and it is what a minimonitor/monitor
> |    `k` on a frozen row should shell out to (via `run-shell -b`). It claims the
> |    record with `lease-take`, preflights the pane against the live server,
> |    kills, verifies gone, then deletes with `drop --nonce`. `restore_begin` now
> |    REFUSES a live lease, so a restore can no longer start inside that window.
> |    Wire lines: `DROPPED:` / `DROP_REFUSED:<id>|in_flight` /
> |    `DROP_FAILED:<id>|<stage>` / `DROP_ABORTED:<id>|raced`.
> | 
> | Advisory only — verify against the tree before relying on any of it.
> | Not yet run anywhere: `tests/test_cleanup_rule_parity.sh` (it refuses while the
> | `-L ait` server is alive). Tracked as a t1705_11 checklist item.

> **👁 note:read** id=2026-09-09T07:03:59Z.dbd5412d903cdb24a48bc9b6 by=t1705_7 at=2026-09-09T07:03:59Z mode=explicit ids=2026-09-09T06:09:42Z.a4ee0adf046aa754e79a9db6

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-09T09:18:53Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-09T13:26:34Z status=pass attempt=1 type=human

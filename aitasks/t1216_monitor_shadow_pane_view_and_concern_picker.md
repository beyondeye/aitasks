---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitor, shadow, tui]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-22 14:42
updated_at: 2026-07-22 14:42
---

## Goal

Make `ait monitor` (the full monitor) shadow-aware, so it is usable again as the
primary "switch quickly between sessions/agents" TUI for a workflow that leans
heavily on shadow agents. Today the shadow companion is only reachable from
`ait minimonitor`, which forces the user to abandon the full monitor's
multi-session switching. Specifically, `ait monitor` must be able to:

1. **Show the shadow pane** associated with a followed/selected agent — not just
   the one-glyph status indicator landed by t1133.
2. **Interact with both** the agent pane and its shadow pane (view + key
   forwarding), without leaving the monitor.
3. **Port the concern parsing and concern-choice dialog** from minimonitor
   (`c` / auto-offer), so shadow concerns can be picked and forwarded from the
   full monitor too.

## Motivation

The user's workflow shifted to heavy shadow-pane use, and `ait monitor` — which
was the best tool for quickly switching between sessions — became unusable for
it, because it neither shows the shadow pane nor understands the concern block
format. Restoring parity removes the forced choice between "good session
switching" (monitor) and "shadow access" (minimonitor).

## Exploration findings (from /aitask-explore, 2026-07-22)

### Most of the machinery already exists — this is largely wiring, not new capability

**Pane view + interaction already exist in monitor.** `monitor_app.py` is a
two-zone app (`Zone.PANE_LIST` / `Zone.PREVIEW`, `Zone` enum ~L81, `ZONE_ORDER`
~L86). The PREVIEW zone already:
- renders live captured pane content — `_update_content_preview` (~L1162, with a
  render-generation guard, PAUSED/LIVE badge, frozen branch) and
  `_apply_preview_render` (~L1259, offloaded `_ansi_to_rich_text` via
  `TmuxMonitor._run_offloaded`);
- keeps per-pane scroll anchors (`_preview_scroll_state`, `_record_preview_scroll`
  ~L642, `_locate_anchor` ~L625) and preview sizes (`PREVIEW_SIZES` ~L98,
  `_apply_preview_size` ~L1554);
- runs a faster tick while focused (`_manage_preview_timer` ~L1420, 0.3s);
- **forwards every keystroke to tmux while in PREVIEW** — `on_key` ~L1448 →
  `_forward_key_to_tmux` ~L1494 → `monitor_core.forward_key`.

So "see a pane and type into it" is solved. What is missing is a way to make the
preview (and the interaction target) point at the **shadow** pane instead of the
selected agent pane.

**Shadow state is already in monitor at zero extra tmux cost.** t1133 landed:
- `_LIST_PANES_FORMAT` (`monitor_core.py` ~L1145) carries
  `#{@aitask_shadow_target}` as its 9th field;
- `_parse_list_panes` (~L1152) returns `(agent_panes, shadow_panes)` and keeps
  shadow panes **out of `_pane_cache`** (cache-boundary invariant, re-enforced in
  `commit_snapshots` ~L1721-1727);
- `capture_all_classified_async` (~L1639) captures shadows in the **same async
  gather** as agents (~L1657-1665) — no extra round-trips;
- `get_shadow_snapshot(followed_pane_id)` (~L1483) returns a full live
  `PaneSnapshot` for the shadow.

`monitor_app._format_agent_card_text` (~L1019) consumes this only to draw
`format_shadow_glyph` (`monitor_shared.py` ~L87). The snapshot's `.content` is
already there and unused.

**Concern machinery is already shared code, just unwired in monitor.**
- `monitor/concern_parser.py` is pure (no tmux, no Textual): markers
  `===AITASK-CONCERNS===` / `===END-CONCERNS===`, `_ITEM` regex,
  `Concern` NamedTuple, `_last_block_region` (last-block-wins), `_join_split_marker`
  (t1167 hard-wrap repair), `parse_concerns` (forgiving, hotkey path),
  `has_concern_block` (strict, auto-offer trigger), `build_clipboard_payload` +
  `DEFAULT_PREAMBLE`. Its only import site today is `minimonitor_app.py`.
  Format spec: `.claude/skills/aitask-shadow/concern-format.md`.
- `ConcernPickerModal` **already lives in `monitor_shared.py` (~L594)** with
  `_ConcernRow` (~L512) and `_CONCERN_BADGE` (~L505). Its docstring already
  claims "Shared by the full monitor and minimonitor (both push it)" — but
  `monitor_app.py` never pushes it. It is already parameterized (`narrow: bool`
  for the 40-col column, `stale: bool` banner), carries its own `DEFAULT_CSS` for
  multi-App use, and does not touch the clipboard (caller owns it).

### The real design work

**1. "Which agent?" resolver mismatch — the single biggest coupling.**
Every minimonitor shadow action begins with `_find_own_agent_snapshot()`
(`minimonitor_app.py` ~L506), which resolves *the one followed agent* from
`TMUX_PANE`'s window index. The full monitor has **no followed agent** — it has
`_focused_pane_id` (`_get_focused_pane_id` ~L1520), i.e. the currently selected
card, which changes as the user navigates. Every ported action
(`action_pick_concerns` ~L1397, `_maybe_offer_concerns` ~L1446,
`action_launch_shadow` ~L1066 / `action_launch_shadow_pick` ~L1108) needs its
agent-resolution parameterized rather than copied.

**2. Single-agent scalars must become per-pane maps.**
Minimonitor's freshness/staleness state is scalar because there is exactly one
followed agent: `_shadow_feedback_stale` (~L272), `_shadow_freshness_tick`
(~L277), `_set_shadow_stale_banner` (~L1321, hard-codes
`query_one("#mini-shadow-stale")`), `_update_shadow_freshness` (~L1333),
`_format_stale_duration` (~L1386, pure `@staticmethod`). In the full monitor these
must be keyed per followed-pane. `_last_concern_block_payload` (~L267) is already
keyed by shadow pane id, but the auto-offer loop around it assumes one agent per
tick — an auto-offer across N visible agents needs an explicit policy (offer only
for the selected/focused agent? badge the card instead of popping a modal?).

**3. Capture contract mismatch — two capture paths are required.**
`concern_parser` requires **wrap-joined, ANSI-free** text (see its module
docstring ~L11-15); minimonitor satisfies this by shelling out to
`aitask_shadow_capture.sh` (`capture-pane -p -J`, no `-e`) via
`_capture_shadow_text` (~L1290, 3s hard timeout `_SHADOW_CAPTURE_TIMEOUT`).
`monitor_core._capture_args` (~L1452) uses `-p -e` **without `-J`** — ANSI-laden
and soft-wrap-split. That is exactly what `_ansi_to_rich_text` wants for a
**preview render**, but it is **not parseable for concerns**. So the tick snapshot
feeds the shadow preview, and a separate on-demand `-J` capture feeds the picker.
Do not try to serve both from one capture.

### Cleanly liftable (per exploration)

- `match_shadow_pane(list_output, followed_pane_id)` (`minimonitor_app.py` ~L101)
  — module-level, pure, newest-`%N`-wins; importable as-is. Note it duplicates
  `monitor_core._pane_id_num` (~L294) via its own `_pane_id_sort_key` (~L89).
- `_shadow_query_args` (~L1256) / `_find_shadow_pane_for_sync` (~L1264) /
  `_find_shadow_pane_for` (~L1279) — only need a `TmuxMonitor`.
- `_capture_shadow_text` (~L1290) — only touches `_SCRIPT_DIR` + asyncio.
- `_format_stale_duration` (~L1386) — pure.
- `_spawn_shadow` (~L1172) — needs `(full_cmd, followed_pane, task_id,
  target_root, snap, monitor)`; the one host coupling is `os.environ["TMUX_PANE"]`
  (~L1248) used as the companion pane for `attach_shadow_cleanup_hook`, which is
  minimonitor-shaped and must be parameterized if `e`/`E` are also ported.

Prefer **lifting into `monitor_core.py` / `monitor_shared.py`** over copying —
t1133's own task notes already flagged the parallel-reimplementation risk for the
shadow reverse lookup, and `monitor_app.py` / `minimonitor_app.py` already carry
a known duplication set (`_detect_tmux_session`, `_load_project_tmux_config`,
`_root_for_snap`, `_rebuild_session_bar`, `_restore_focus`,
`_get_focused_pane_id`, `_switcher_selected_session`, several `action_*`).

### Open design questions for planning

- **Shadow display shape:** does the shadow get its own row in the pane list
  (currently shadows are deliberately excluded from the list), a split/toggle
  inside the existing PREVIEW zone, or a third zone? Whatever is chosen must not
  un-hide shadows from agent lists / kill / sibling logic — the discovery-drop is
  load-bearing for desktop semantics (and t1118 documents the same constraint for
  applink).
- **Interaction targeting:** how does the user say "type into the shadow, not the
  agent"? A zone/target toggle keyed off `_focused_pane_id` → its shadow.
- **Auto-offer policy** with N agents on screen (see item 2 above).
- **Scope of the `e` / `E` spawn port** — is spawning a shadow from the full
  monitor in scope, or view + concerns only? (`_spawn_shadow` is liftable but
  carries the `TMUX_PANE` companion-pane coupling.)

### Existing tests to extend (not duplicate)

`tests/test_concern_parser.py`, `tests/test_concern_picker_modal.py`,
`tests/test_minimonitor_concern_action.py` (`MatchShadowPaneTests`,
`ActionPickConcernsTests`, `AutoOfferTests`, `ShadowFreshnessTests`),
`tests/test_minimonitor_shadow_pick.py`, `tests/test_monitor_shadow_status.py`
(`_parse_list_panes` split, cache boundary, batch capture, lifecycle, duplicate
shadows, supersession, `get_shadow_snapshot`), `tests/test_no_raw_tmux.sh`.

## Coordination

- **t1118 — `mobile_shadow_agent_driving_over_applink`** (`xdeprepo:
  aitasks_mobile`, children t1118_1..t1118_5) covers bringing the same shadow
  capability to the mobile companion over applink. It independently documented
  the "shadow panes are dropped from discovery" foundational gap. These two tasks
  are **not** folds of each other — but whichever lands first should keep the
  shadow-exposure seam reusable by the other, and the desktop discovery-drop must
  remain intact in both.
- Builds directly on **t1133** (`shadow_agent_status_icon_monitor`, Done) — the
  off-loop shadow-state detection seam and `get_shadow_snapshot` are its output.
- Adjacent, not overlapping: t1053 (minimonitor concern picker manual
  verification), t1113 (shadow freshness manual verification), t996 (shadow
  resizes own pane), t1159 (shadow review loop automation).

## Acceptance criteria

- From `ait monitor`, the shadow pane bound to a selected agent can be viewed
  live (content, not just a status glyph).
- From `ait monitor`, keystrokes can be directed at either the agent pane or its
  shadow pane, with an unambiguous, visible indication of the current target.
- From `ait monitor`, shadow concerns can be parsed and picked through the
  existing `ConcernPickerModal`, with the same clipboard payload semantics as
  minimonitor (`build_clipboard_payload` + `DEFAULT_PREAMBLE`).
- Shadow panes remain excluded from the agent pane list / kill / sibling / next-
  sibling logic — the existing discovery-drop invariant is preserved and covered
  by a negative-control test.
- Ported logic is **shared** (lifted into `monitor_core.py` / `monitor_shared.py`
  and imported by both apps), not copy-pasted into `monitor_app.py`; no second
  implementation of concern parsing, shadow lookup, or the picker modal exists.
- Per-tick tmux traffic does not increase for users with no shadow panes, and
  shadow work stays off the Textual event loop (t1111 offload seam).
- `bash tests/test_no_raw_tmux.sh` and the existing monitor/minimonitor/shadow
  test files pass, extended to cover the new monitor-side paths.

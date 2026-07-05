---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [monitor, tui, shadow]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-05 22:48
updated_at: 2026-07-05 22:48
---

## Goal

In `ait monitor` and `ait minimonitor`, when a monitored code-agent window has a
**linked shadow agent**, show a small **colored icon (icon only, no text)** for the
shadow's live state — **idle / active / prompt** — reusing the existing agent
state-detection semantics. The shadow-state detection MUST be built on top of the
**performant, off-loop detection seam introduced by t1111** (monitor UI-thread
offload), not as new synchronous per-tick work on the Textual event loop.

## Design (agreed)

- Use a **distinct glyph** for the shadow status — a different shape from the
  code-agent's own status dot `●` (e.g. `◆`/`◇` or similar) — so the two are
  visually separable at a glance.
- Render the two glyphs **one after the other, before the agent name**:
  `<agent ●> <shadow ◆> <compare-glyph> <window_index:name> <status text>`.
- Color the shadow glyph by the shadow's state using the **same color mapping**
  as the agent dot: magenta = prompt (`awaiting_input`), yellow = idle, green =
  active. When the window has **no** linked shadow, render nothing extra (no
  placeholder), so non-shadowed rows are unchanged.

## Current state (exploration findings)

State detection & rendering (`.aitask-scripts/monitor/`):
- Agent state is a two-axis pair on `PaneSnapshot` (`monitor_core.py:326`):
  `is_idle`/`idle_seconds` and `awaiting_input`/`awaiting_input_kind`. Derived
  priority: **PROMPT (`awaiting_input`) > IDLE (`is_idle`) > active**.
- Pure classifier: `classify_content(content, mode, prompt_patterns, category)`
  at `monitor_core.py:175` — ANSI-strip + last-6-lines prompt scan against
  `prompt_patterns.py`.
- Colored-dot convention + shared formatters in `monitor_shared.py:53-71`
  (`format_pane_status`, `format_compare_mode_glyph`).
- Icon-injection sites (already hold `snap.pane.pane_id`):
  - Full monitor: `_format_agent_card_text`, f-string at `monitor_app.py:1027-1030`.
  - Minimonitor: `_agent_card_text`, line built at `minimonitor_app.py:634`.

Shadow linkage (reverse lookup already exists — reuse, don't reinvent):
- Shadow panes carry the followed agent's pane id in the `@aitask_shadow_target`
  pane option (`monitor_core.py:274`).
- `match_shadow_pane(list_output, followed_pane_id)` (pure matcher,
  `minimonitor_app.py:99-125`) + `_shadow_query_args()` + async
  `_find_shadow_pane_for(followed_pane_id)` (`minimonitor_app.py:1164-1196`)
  already resolve a followed pane -> its shadow pane id. **Promote/lift these
  from `minimonitor_app.py` into `monitor_core.py`** so the full monitor can
  reuse them too (avoid a parallel reimplementation).

Key wrinkle — shadow panes are excluded from snapshots:
- `_parse_list_panes` drops any pane where `is_shadow_target(...)` is true
  (`monitor_core.py:1141-1142`). So a shadow's state is NOT in `self._snapshots`.
  The feature must do a **dedicated capture + `classify_content`** on the shadow
  pane (or add a dedicated shadow-status query path). This is the extra per-tick
  work that MUST be offloaded.

## Coordination with t1111 (monitor performance) — REQUIRED

t1111 is the monitor UI-thread offload effort. Status at creation: t1111_1..4
**Done**, t1111_5 (preview render offload) **Implementing**, t1111_6 (manual
verification) **Ready**. t1111_4 (Done) established the codebase's first UI-thread
offload seam in `monitor_core.py`:
- pure `classify_content` -> `ClassifyResult` -> `PaneSnapshot`,
- single injectable offload helper `TmuxMonitor._run_offloaded(fn)`,
- one off-loop batch per tick (`capture_all_classified_async` / `_classify_batch`
  / `commit_snapshots`),
- monotonic generation token (`_capture_generation` / `_next_generation`) to
  discard stale results.

This feature adds an **extra tmux capture + regex scan per shadow per tick** —
exactly the kind of per-tick CPU/IO work t1111 moved off the loop. It MUST fold
into the offloaded batch, honoring the t1111 **concurrency invariants A–G**
(`aiplans/p1111_monitor_ui_thread_offload_perf.md`):
- **A:** offloaded workers are pure compute — no `self.query`, no widget,
  reactive attr, or DOM access.
- **B:** shared mutable state written only on the loop.
- **E:** ONE off-loop batch per cycle — no per-shadow fan-out of `to_thread`.
- **F:** route every offload through the one `_run_offloaded` helper; guard with
  the generation token.

Concretely: extend the classify batch to also capture+classify linked shadow
panes (batched with the agent panes, not a synchronous side call), carry the
shadow's state on `PaneSnapshot` (or a parallel shadow-state field), and render
the shadow glyph on the loop. Do NOT add a synchronous shadow capture on the UI
thread. Coordinate landing after the t1111 offload architecture is stable
(t1111_4 seam is the hard prerequisite; it is already merged).

Note: minimonitor thread-offload propagation was explicitly deferred by t1111
(`p1111` "Deferred"). If the shadow-icon work in minimonitor introduces per-tick
capture on the loop there, weigh doing the minimonitor offload as part of / a
sibling of this task rather than regressing minimonitor responsiveness.

## Acceptance criteria

- A code-agent window with a linked shadow shows a second, distinctly-shaped
  colored glyph (before the name, after the agent's own glyph) reflecting the
  shadow's idle/active/prompt state, in BOTH `ait monitor` and `ait minimonitor`.
- Windows without a linked shadow are visually unchanged.
- Shadow pane discovery reuses the promoted `match_shadow_pane` /
  `_find_shadow_pane_for` seam (single implementation shared by both TUIs), not a
  duplicate.
- Shadow-state detection reuses `classify_content` and runs through the t1111
  offload batch/`_run_offloaded` seam with generation-guarding; it adds no new
  synchronous per-tick tmux capture or regex work on the event loop, and no
  widget access inside offloaded workers (invariants A/B/E/F).
- The shadow-glyph color mapping matches the agent-dot mapping (magenta/yellow/
  green) and is defined once (shared formatter in `monitor_shared.py`).
- Tests: a pure test for `match_shadow_pane` promotion + the shadow-state batch
  (golden/equivalence that the offloaded shadow classification matches a direct
  synchronous `classify_content`), and a render-level assertion of the two-glyph
  row (assert `widget.render().plain`) for shadowed vs non-shadowed rows in both
  TUIs.

## Out of scope

- The shadow-feedback *staleness* indicator (distinct concern; see t1113 /
  `@aitask_shadow_analyzed_at` freshness path) — this task is the shadow's live
  execution state, not analysis freshness.

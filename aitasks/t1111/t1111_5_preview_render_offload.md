---
priority: high
effort: medium
depends: [t1111_4]
issue_type: performance
status: Ready
labels: [monitor, tui, performance]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-02 14:43
updated_at: 2026-07-02 14:43
---

Offload the **preview render** (`_ansi_to_rich_text`) off the UI thread —
eliminates the active-agent focus-switch lag.

## Context
Part of t1111 (`ait monitor` UI-thread offload). **Depends on t1111_2 and t1111_4.**
Empirical finding: with all agents idle the switch is fast, but as soon as one agent
is active the switch lags. Root cause: the single `_update_content_preview` →
`_ansi_to_rich_text` (`monitor_shared.py:74-93`) → `Text.from_ansi` render of the
focused pane runs on the UI thread, and its cost scales with the ANSI-escape density
of the content — an active agent's churny/colored output parses expensively.
t1111_2 removes the *redundant* second render (~2× win); this task removes the
*single* render from the UI thread.

## Key files to modify
- `.aitask-scripts/monitor/monitor_app.py` (`_update_content_preview`,
  `on_descendant_focus`).
- `.aitask-scripts/monitor/monitor_shared.py` (`_ansi_to_rich_text` split).

## Approach
1. Split `_ansi_to_rich_text` into a **pure builder** producing the Rich `Text`
   (the CPU-heavy `from_ansi` + per-line regex) and the application step
   `preview.update(text)` (stays on the loop).
2. `_update_content_preview`'s render branch computes the `Text` via the offload seam
   (`_run_offloaded` from t1111_4). `on_descendant_focus` is sync, so drive the
   offloaded render through a small async helper (`call_later`/`run_worker`) or make
   the preview-update path async. Apply `preview.update(text)` + scroll restore back
   on the loop.
3. **Reuse t1111_4's serialization discipline:** prefer
   `@work(thread=True, group="preview", exclusive=True)` so rapid arrow-nav
   supersedes stale renders natively; keep the generation token so a late `to_thread`
   result for a pane you already switched away from is discarded — never overwrites
   the current preview.
4. Preserve fast-paths: the frozen branch (`same_pane and (is_paused or
   user_is_scrolling)` at 1156) and header-only update must short-circuit **before**
   scheduling any offload (no thread hop when nothing will render).

## Concurrency & async safety contract (BINDING — invariants A–G, shared with t1111_4)
- **A** pure builder only, no widget access off-loop.
- **C/F** reuse `_run_offloaded` + generation token; `@work exclusive` group
  "preview". Test: stale-render discard + negative control.
- **D** fail closed on a raising `from_ansi` → fall back to raw/prior content.
- **G** schedule `call_after_refresh` scroll-restore AFTER `preview.update`; read
  `self._snapshots.get(pane_id)` defensively (a concurrent refresh may have replaced
  the dict) — stale ⇒ discard via generation, never `KeyError`.

## Reference patterns
- `_finalize_capture` offload seam established in t1111_4 (reuse `_run_offloaded`).
- Existing preview scroll-restore logic in `_update_content_preview` (1160-1193).

## Verification
- New `tests/test_monitor_preview_offload.py`: (a) unit-test the pure `Text`-builder
  on ANSI-heavy fixtures; (b) render-equivalence vs the current synchronous
  `_ansi_to_rich_text`; (c) **stale-render discard** — two rapid switches whose
  offloaded renders resolve out of order → preview shows the last-focused pane
  (generation check), with a negative control; (d) frozen/paused and header-only
  branches never schedule an offload.
- Manually (t1111_6 covers this): `ait monitor` with ≥1 active `agent-*` window →
  switching to/among agents stays instant.

## Risk
code-health medium (extends threading to the render path),
goal medium (directly targets the user-reported active-agent lag).
Risk-gated: declares `risk_evaluated`; re-run risk evaluation at pick time.

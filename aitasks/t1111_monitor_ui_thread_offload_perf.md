---
priority: high
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [monitor, tui, performance]
gates: [risk_evaluated]
children_to_implement: [t1111_1, t1111_2, t1111_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-02 08:32
updated_at: 2026-07-02 14:43
---

`ait monitor` becomes sluggish as the number of monitored agents grows: a ~0.5s
lag when switching the focused agent, and a longer freeze on every 3s status
refresh (idle/prompt/active recompute). Root cause in both cases: CPU/IO work
runs on the Textual **event-loop thread** and scales linearly with agent count.
The `tmux -C` control backend already runs on a bg thread (t719_2), but all
result-processing, formatting, and several sync tmux calls run on the UI loop.

## Root causes (investigated t???)

### 3-second freeze — `_refresh_data` (monitor_app.py:685, async def on set_interval(3s))
Runs on the UI thread; everything inside it blocks input. Per tick, per agent:
1. **Captures serialized, not concurrent.** `capture_all_async` uses
   `asyncio.gather` (monitor_core.py:1327-1340) but the single `tmux -C` channel
   has one write-lock + one FIFO reader loop (monitor_core.py:294-298, 409-447),
   so M capture-pane + N list-panes round-trips run one-at-a-time. Linear in N.
2. **Per-agent CPU:** `_strip_ansi` (regex over 200 captured lines) + prompt-
   pattern regex scan in `_finalize_capture` (monitor_core.py:1183-1206).
3. **Per-agent disk I/O:** `_gate_cache.clear()` fires every tick
   (monitor_app.py:702), so `_format_agent_card_text` → `GateSummaryCache.
   summary_for` re-reads each task's gate ledger from disk every 3s
   (monitor_core.py:1617-1637).
4. **Sync blocking tmux calls on the UI thread:** `_consume_focus_request`
   (show-environment, monitor_app.py:784), `_rebuild_session_bar` →
   `_read_attached_session` (display-message, monitor_app.py:962), and
   `_get_desync_summary(cwd)` (monitor_app.py:915).

### ~0.5s focus-switch lag — `on_descendant_focus` (monitor_app.py:1354, sync)
Arrow-nav → `.focus()`, fully synchronous. Does NOT re-capture tmux (content is
stale-from-snapshot), but per keystroke it:
1. **Renders the preview twice** — `on_descendant_focus` calls
   `_update_content_preview()`, then `_update_zone_indicators()` calls it again
   (monitor_app.py:1238). Each render is `_ansi_to_rich_text` over ~200 lines
   (2 regex/line + `Text.from_ansi` + `preview.update` reflow + deferred scroll
   restore) — the second render is pure waste (`same_pane` is False on a switch).
2. **O(agents) DOM churn:** `_nav_within_zone` queries all `PaneCard`s
   (monitor_app.py:1277), then `_update_selected_card_indicator` queries them all
   again + `set_class` per card (monitor_app.py:1245-1252).

### Architectural observation
Only the focused pane is ever displayed, yet the 3s tick does full 200-line
capture + strip + regex + gate-disk-read for **every** agent (non-focused agents
need only a status dot), and the switch does redundant double-render + full card
iteration.

## Fix directions (to be validated/scoped during planning)
1. **Move refresh heavy work off the UI thread** — run capture + strip/regex +
   gate reads in a `@work(thread=True)` worker (or run_in_executor), then apply
   only widget updates back on the UI thread via the Textual message/callback
   path. This is the primary lever for the freeze.
2. **Kill the double `_update_content_preview` on focus switch** and stop the
   O(N) re-query — track the previously-selected card and flip only two cards'
   `selected` class.
3. **Cache gate-ledger reads with mtime** instead of clearing `_gate_cache`
   every tick.
4. **Eliminate the sync tmux calls** inside `_refresh_data` (fold them into the
   async capture batch, or cache attached-session / desync summary).
5. **Tiered polling** — full 200-line capture/ANSI-render only for the focused
   pane; a minimal status probe (fewer lines / tail only) for non-focused
   agents. Ties into pending t719_3 (adaptive polling) and t719_4 (pipe-pane
   push) — coordinate rather than duplicate.

Consider profiling (py-spy) first to confirm which cost dominates before scope
is locked, and splitting into children by testability (thread-offload seam,
switch-path fix, gate-cache, tiered polling) if effort warrants.

## Related tasks (references, not folded)
- **t719** (parent, has children) / **t719_3** adaptive polling (Postponed) /
  **t719_4** pipe-pane push — the planned longer-term direction for the poll
  loop; coordinate fix #5 with these.
- **t257** performance when changing selection — analogous UI-thread render cost,
  but in codebrowser (different TUI).
- See `aidocs/framework/python_tui_performance.md` (Monitor refresh loop section)
  and `aidocs/framework/tui_conventions.md` / `tmux_gateway.md`.

## Cross-agent note
Changes here are to `.aitask-scripts/monitor/*` (monitor_app.py / monitor_core.py)
— framework Python, not skill markdown, so no cross-agent skill port needed.
The same hot-path pattern likely affects **minimonitor** (minimonitor_app.py);
evaluate whether the thread-offload fix should apply there too.

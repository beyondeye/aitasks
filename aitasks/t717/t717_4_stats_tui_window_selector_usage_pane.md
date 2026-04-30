---
priority: medium
effort: high
depends: [t717_3]
issue_type: feature
status: Implementing
labels: [verifiedstats, statistics, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-30 00:19
updated_at: 2026-04-30 12:30
---

## Context

Fourth child of t717. Surfaces the new schema (`prev_month` bucket and `usagestats` block, added by t717_1 and t717_2) in the stats TUI:

1. The verified-rankings pane currently shows all-time scores only. Add a window selector so users can switch between `all_time`, `recent` (current+prev_month), `month`, `prev_month`, `week`.
2. Add a parallel **Usage rankings** pane mirroring the verified pane structure but reading `usagestats` (no scores, just run counts).

This lets users audit ranking changes after a model release: "did the new model already overtake the incumbent in recent usage?", "is the recent-window score consistent with the all-time score?".

## Key Files to Modify

- `.aitask-scripts/stats/stats_data.py` — extend the rankings loader for new windows; add `load_usage_rankings()`.
- `.aitask-scripts/stats/stats_app.py` — Textual app: add window cycling on the verified pane; add the new usage pane.
- `.aitask-scripts/aitask_stats.py` — minimal: tolerate the new fields in the CLI text/CSV output paths. If existing exports surface verified data, optionally add a column for recent-window score; if scope creep, defer.

## Reference Files for Patterns

- `stats_data.py:234-384` — existing `load_verified_rankings()` builds `by_window` keyed currently by `all_time`, `month`, `week`. Extend the bucket-iteration loop to also build entries for `prev_month` and a synthesized `recent` window.
- `stats_data.py:130-145` — `VerifiedModelEntry` and `VerifiedRankingData` dataclasses; mirror them as `UsageModelEntry`, `UsageRankingData` (no `score` field, just `runs`).
- `stats_app.py:420-431` — `action_prev_verified_op` / `action_next_verified_op` arrow-cycling pattern for op selection. The new window cycler should follow the same pattern but on its own keys (use `[` / `]` per CLAUDE.md "Pane-internal cycling" guidance — though that doc says ←/→ for cycling, ←/→ are already taken here for op cycling, so brackets are the correct fallback).
- `stats_app.py` pane composition — find the existing verified pane mounting code; the new usage pane mounts the same way with its own widget ID.
- CLAUDE.md "Contextual-footer ordering" — when adding new keybindings to a pane's footer, keep uppercase siblings adjacent to lowercase primaries.

## Implementation Plan

1. **`stats_data.py` — extend `load_verified_rankings`:**
   - Extend the bucket loop to also emit entries for `prev_month` window and a synthesized `recent` window (where `runs = month.runs + prev_month.runs`, `score_sum = month.score_sum + prev_month.score_sum`, `score = round(score_sum / runs)` if runs > 0).
   - Result: `by_window[op][provider]` keys include `all_time`, `recent`, `month`, `prev_month`, `week`.
   - Make sure `all_providers` aggregation also computes the new windows.
   - Existing callers that read `by_window[...]["all_time"]` continue to work unchanged.

2. **`stats_data.py` — add `load_usage_rankings`:**
   - Mirror `load_verified_rankings` structure. Read `usagestats[op]` from each model file.
   - `UsageModelEntry`: `cli_id, display_name, provider, runs` (no score).
   - `UsageRankingData`: `by_window: {op: {provider: {window: [UsageModelEntry, ...]}}}, operations: List[str]`.
   - Same window keys: `all_time`, `recent`, `month`, `prev_month`, `week`.
   - Reuse `canonical_model_id` and `model_display_from_cli_id` for cross-provider aggregation.

3. **`stats_app.py` — verified pane window selector:**
   - Add `_verified_window` state attribute defaulting to `"recent"` (the most useful default).
   - Add `WINDOWS = ["all_time", "recent", "month", "prev_month", "week"]` ordering constant.
   - Add bindings:
     - `Binding("[", "prev_verified_window", "Prev window", show=True)` (priority=False — pane-scoped)
     - `Binding("]", "next_verified_window", "Next window", show=True)`
     - Action handlers cycle `_verified_window` and re-render the rankings table.
   - Both bindings must guard on the active pane being the verified pane (per CLAUDE.md: `self.screen.query_one(...)` not `self.query_one(...)`, raise `SkipAction` on guard miss).
   - Render the active window in the pane's header text (e.g., `"Verified rankings — recent (Sh+[/] to switch)"`).
   - DataTable rendering reads `verified_data.by_window[op][provider][_verified_window]` instead of hard-coded `"all_time"`.

4. **`stats_app.py` — new usage pane:**
   - Add a third tab/pane in the existing `agents` view (alongside `verified` and any others), or follow whatever the existing pane structure looks like.
   - State: `_usage_window` (default `"recent"`), independent from verified window.
   - Bindings: same `[` / `]` cycling, guarded on pane id.
   - Op cycling: same `←` / `→` pattern, also guarded on pane id.
   - Header: `"Usage rankings — <window> (Sh+[/] to switch)"`.
   - DataTable columns: provider, model, runs (no score column).

5. **`aitask_stats.py` — defensive read of new fields:**
   - Wherever the CLI text/CSV path reads verified data, ensure `prev_month` and `recent` are accepted without crashing.
   - If the CSV exports a "verified score" column, add an optional `--window <key>` flag to choose which window's score to export. Default unchanged (`all_time`) for backward compatibility.

## Verification Steps

1. `python3 -m py_compile .aitask-scripts/stats/stats_data.py .aitask-scripts/stats/stats_app.py .aitask-scripts/aitask_stats.py` — must succeed.
2. Existing stats tests (if any under `tests/`) still pass.
3. Manual TUI: `./ait stats tui`:
   - Navigate to verified pane. Press `]` repeatedly: header cycles `recent → week → all_time → month → prev_month → recent`. Rankings table updates.
   - Switch to usage pane. Same cycling works.
   - Op cycling (`←` / `→`) still works in both panes.
   - Footer hints reflect the new keys.
4. CLI: `./ait stats` (text) — output unchanged for default invocation. With `--window recent` (if implemented), shows recent-window scores.
5. With a fresh `models_*.json` (no `prev_month`, no `usagestats`), TUI does not crash; ranking shows what data exists.

## Notes for sibling tasks (t717_5)

- This task creates the surfaces that t717_5 (manual verification) will exercise. Make sure the headers are explicit about which window is active and which keys cycle them — the manual checklist will reference those labels.

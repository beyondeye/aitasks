---
Task: t717_4_stats_tui_window_selector_usage_pane.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Sibling Tasks: aitasks/t717/t717_1_verifiedstats_prev_month_schema.md, aitasks/t717/t717_2_usagestats_live_hook.md, aitasks/t717/t717_3_agent_picker_recent_modes.md
Archived Sibling Plans: aiplans/archived/p717/p717_*_*.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
---

# t717_4 — Stats TUI: window selector + usage pane

## Goal

Surface the new schema in the stats TUI:

1. Verified-rankings pane gains a window selector (`all_time` / `recent` / `month` / `prev_month` / `week`).
2. New parallel "Usage rankings" pane reading `usagestats`, with the same window selector.

## Pre-requisites

- t717_1 archived (verifiedstats prev_month exists).
- t717_2 archived (usagestats block populated by live hook).

## Implementation

### 1. `stats_data.py` — extend `load_verified_rankings` for new windows

In `.aitask-scripts/stats/stats_data.py`:

- The existing `by_window[op][provider]` dict currently has keys `all_time`, `month`, `week`.
- Extend the per-model bucket loop to also produce entries for:
  - `prev_month` window — straight read of `verifiedstats[op].prev_month`.
  - `recent` window — synthesized: `runs = month.runs + prev_month.runs`, `score_sum = month.score_sum + prev_month.score_sum`, `score = round(score_sum / runs)` if runs > 0, else 0.
- All-providers aggregation must compute the new windows the same way (sum across providers per canonical model id).
- Existing callers reading `by_window[...]["all_time"]` or `["month"]` continue to work without changes.

Pattern (per-model loop):

```python
windows = {
    "all_time": vs[op].get("all_time", {}),
    "month":    vs[op].get("month", {}),
    "prev_month": vs[op].get("prev_month", {}),
    "week":     vs[op].get("week", {}),
}
mo = windows["month"]
pm = windows["prev_month"]
recent_runs = mo.get("runs", 0) + pm.get("runs", 0)
recent_sum  = mo.get("score_sum", 0) + pm.get("score_sum", 0)
windows["recent"] = {
    "runs": recent_runs,
    "score_sum": recent_sum,
}
for window_key, bucket in windows.items():
    runs = bucket.get("runs", 0)
    if runs <= 0:
        continue
    score = round(bucket.get("score_sum", 0) / runs)
    by_window[op][provider].setdefault(window_key, []).append(
        VerifiedModelEntry(cli_id=..., display_name=..., provider=provider, score=score, runs=runs)
    )
```

### 2. `stats_data.py` — add `load_usage_rankings`

```python
@dataclass
class UsageModelEntry:
    cli_id: str
    display_name: str
    provider: str
    runs: int


@dataclass
class UsageRankingData:
    by_window: Dict[str, Dict[str, Dict[str, List[UsageModelEntry]]]]
    operations: List[str]


def load_usage_rankings(project_root: Optional[Path] = None) -> UsageRankingData:
    """Mirror of load_verified_rankings, reading usagestats; no scores."""
    ...
```

Same window keys (`all_time`, `recent`, `month`, `prev_month`, `week`). Reuse `canonical_model_id` and `model_display_from_cli_id` for cross-provider aggregation. Discover the operations list from the union of all skills present across all model files.

### 3. `stats_app.py` — verified pane window selector

Add state attribute:

```python
class StatsApp(App):
    _verified_window: str = "recent"   # default to recent
    _usage_window: str = "recent"

    WINDOWS: list[str] = ["recent", "all_time", "month", "prev_month", "week"]
```

Add bindings:

```python
Binding("[", "prev_verified_window", "Prev window", show=True, priority=False),
Binding("]", "next_verified_window", "Next window", show=True, priority=False),
```

`[` and `]` chosen because:
- `←` / `→` are already taken by op cycling (existing behavior preserved).
- `Shift+←` / `Shift+→` belong to the agent picker, not stats TUI.
- Per CLAUDE.md "Pane-internal cycling uses ←/→ when there is no conflict, brackets when there is."

Action handlers:

```python
def action_prev_verified_window(self) -> None:
    if not self._guard_pane("verified"):
        from textual.actions import SkipAction
        raise SkipAction
    idx = self.WINDOWS.index(self._verified_window)
    self._verified_window = self.WINDOWS[(idx - 1) % len(self.WINDOWS)]
    self._refresh_verified_pane()
```

(Same pattern for next, and for usage pane on its own state attribute.)

`_guard_pane(name)` reads the active pane id via `self.screen.query_one(...)` (per CLAUDE.md `App.query_one` gotcha) and returns whether the named pane is active.

Render the active window in the pane header:

```python
header = f"Verified rankings — {self._verified_window} (Sh+[/] to switch)"
```

Wait, [ and ] are not Shift-prefixed on US keyboards (they're shift+square brackets but that's the key itself, no Shift modifier in Textual binding). Use literal `[` / `]`. Header hint: `"[/] to switch window, ←/→ for op"`.

### 4. `stats_app.py` — new usage pane

Mount a new pane (tab/section, depending on existing structure) with id `usage_rankings`. Compose a DataTable with columns `provider`, `model`, `runs`. Same op cycling as verified pane (separate state). Same window cycling on `[` / `]` (guarded on pane id).

Footer hints (per CLAUDE.md "Contextual-footer ordering" — keep adjacent siblings together):

```
←  →  d  D  [  ]  ?  q
op nav  detail  window  help quit
```

Add the new pane id to whatever pane-id list governs the bindings' guard.

### 5. `aitask_stats.py` — defensive read

- Wherever the CLI text or CSV path reads verified data, ensure the new `prev_month` and `recent` keys don't cause crashes (use `.get(...)` defensively).
- Optional new flag `--window <key>` (default `all_time`) to choose which window's score appears in the verified-export column.
- If existing exports don't surface verified detail, no change here — defer.

### 6. Defensive cold-start

Models without `prev_month` or `usagestats`: the loaders should produce empty windows for those models, NOT crash. The `UsageRankingData` for cold-start has an empty operations list and empty by_window dict — TUI should display "(no usage data yet)" placeholder.

## Verify

1. Syntax: `python3 -m py_compile .aitask-scripts/stats/stats_data.py .aitask-scripts/stats/stats_app.py .aitask-scripts/aitask_stats.py`.
2. Existing stats tests (if any under `tests/`) still pass.
3. Manual `./ait stats tui`:
   - Verified pane → `]` cycles header `recent → all_time → month → prev_month → week → recent`.
   - Each window reorders the rankings table.
   - Switch to usage pane → `]` cycles same windows independently.
   - `←` / `→` still cycles ops in both panes.
   - Footer hints are correct and match CLAUDE.md ordering rules.
4. Cold-start: temporarily mv `aitasks/metadata/models_codex.json` aside, re-run TUI — no crash, codex absent from rankings.
5. CLI: `./ait stats` text — output unchanged for default invocation. With `--window recent` (if implemented): shows recent-window scores instead of all-time.

## Verification (manual checklist for t717_5)

- [ ] Stats TUI verified pane has window selector (`[` / `]`).
- [ ] Default window is `recent`.
- [ ] All 5 windows produce non-error output (data may be empty for fresh models).
- [ ] Stats TUI usage pane exists and is reachable.
- [ ] Usage pane cycles ops with `←` / `→`.
- [ ] Usage pane cycles windows with `[` / `]`.
- [ ] CLI `./ait stats` does not crash on the new schema.

## Notes

- The recent-window math is the same as in t717_3's `_recent_aggregate`. If there's a clean way to share it (e.g., import from `stats_data` into `agent_model_picker`, or extract to a third module), prefer that — but a duplicated 3-line helper is acceptable to avoid adding a cross-cutting module dependency.

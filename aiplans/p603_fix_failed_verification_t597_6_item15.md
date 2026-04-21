---
Task: t603_fix_failed_verification_t597_6_item15.md
Base branch: main
plan_verified: []
---

# Plan: t603 — Fix verified-rankings pane under-count

## Context

Manual-verification task t597_6 item #15 ("Agents & Models (per-agent, per-model, verified rankings)") failed with the observation that the **verified-rankings pane renders, but the number of runs displayed is very small** against the current archived dataset. The per-agent and per-model panes in the same preset render normally.

Root cause (confirmed by exploration, not a data-layer bug):

- `.aitask-scripts/stats/panes/agents.py:55` picks `op = vdata.operations[0]` to show.
- `.aitask-scripts/stats/stats_data.py:359` returns `operations=sorted(all_ops)` — so `operations[0]` is the **alphabetically first** op.
- Alphabetically first op in the real data is `changelog` with 7 runs. Meanwhile `pick` has 342 runs, `explore` 32, `qa` 12, `test_414_flags` 12, `revert` 1, `wrap` 1. The pane silently shows the 7-run operation and never surfaces the rest.
- The p597_3 plan explicitly noted this as a simplification ("Pick one op (e.g. first in `vdata.operations`)") — t603 is the follow-through that turns the "one op" view into a navigable one.

Per user selection during planning, the chosen UX is **"Most-used op first + keyboard selector"**: default to the operation with the most all-time runs, and let the user cycle operations with **← / →** arrow keys. The current operation name + run count is shown in a header above the DataTable so the user always knows which slice they are looking at.

Key binding safety:
- `StatsApp.BINDINGS` (`.aitask-scripts/stats/stats_app.py:110-120`) does not claim `left` / `right`.
- The sidebar `ListView` is vertical and ignores left/right, so arrows bubble up to the App-level bindings.
- The verified-rankings `DataTable` is created with `cursor_type="row"` so it does not consume left/right for cell navigation.
- Bindings are hidden from the footer (`show=False`) to avoid clutter on non-verified panes; the pane header surfaces the hint inline when the verified pane is active.

## Files to Modify

### 1. `.aitask-scripts/stats/panes/agents.py` (primary change)

Replace the current `_render_verified()` with a stateful widget-based implementation.

**Add module-level helper:**

```python
def _ops_sorted_by_runs(vdata: VerifiedRankingData) -> list[str]:
    """Operations sorted by all_providers/all_time run count, desc."""
    def total_runs(op: str) -> int:
        entries = vdata.by_window.get(op, {}).get("all_providers", {}).get("all_time", [])
        return sum(e.runs for e in entries)
    ranked = [(op, total_runs(op)) for op in vdata.operations]
    ranked = [(op, n) for op, n in ranked if n > 0]
    ranked.sort(key=lambda x: (-x[1], x[0]))
    return [op for op, _ in ranked]
```

**Replace the single DataTable mount with a header Static + DataTable pair, wrapped in a custom container:**

```python
from textual.containers import Vertical
from textual.widgets import Static

class VerifiedRankingsPane(Vertical):
    """Pane that renders one op at a time with `[` / `]` to cycle."""

    DEFAULT_CSS = """
    VerifiedRankingsPane { height: auto; }
    VerifiedRankingsPane > #verified_header { height: auto; padding: 0 0 1 0; }
    """

    def __init__(self, vdata: VerifiedRankingData) -> None:
        super().__init__()
        self._vdata = vdata
        self._ops = _ops_sorted_by_runs(vdata)
        self._op_idx = 0
        self._header: Static | None = None
        self._table: DataTable | None = None

    def compose(self):
        self._header = Static(id="verified_header")
        yield self._header
        self._table = DataTable(zebra_stripes=True, cursor_type="row")
        yield self._table

    def on_mount(self) -> None:
        self._table.add_columns("Rank", "Model", "Provider", "Score", "Runs")
        self._populate()

    def _populate(self) -> None:
        assert self._header is not None and self._table is not None
        if not self._ops:
            self._header.update("[dim]No verified rankings with runs[/dim]")
            return
        op = self._ops[self._op_idx]
        entries = (
            self._vdata.by_window.get(op, {})
            .get("all_providers", {})
            .get("all_time", [])
        )
        total_runs = sum(e.runs for e in entries)
        nav_hint = (
            "  [dim]← prev op · next op →[/dim]" if len(self._ops) > 1 else ""
        )
        self._header.update(
            f"Operation: [b]{op}[/b]  ({total_runs} runs){nav_hint}"
        )
        self._table.clear(columns=False)
        for rank, entry in enumerate(entries, start=1):
            self._table.add_row(
                str(rank),
                entry.display_name,
                entry.provider,
                str(entry.score),
                str(entry.runs),
            )

    def cycle_op(self, delta: int) -> None:
        if len(self._ops) <= 1:
            return
        self._op_idx = (self._op_idx + delta) % len(self._ops)
        self._populate()


def _render_verified(stats: StatsData, container: Container) -> None:
    vdata = load_verified_rankings()
    if not vdata.operations or not _ops_sorted_by_runs(vdata):
        empty_state(container, "No verified rankings available")
        return
    container.mount(VerifiedRankingsPane(vdata))
```

Keep the `register(PaneDef("agents.verified", …, _render_verified))` line unchanged — the pane-def signature is preserved.

### 2. `.aitask-scripts/stats/stats_app.py` (add cycle bindings)

Add two App-level bindings (right after the existing `Binding("e", …)` line, before `Binding("q", …)`):

```python
Binding("left", "prev_verified_op", "Prev op", show=False),
Binding("right", "next_verified_op", "Next op", show=False),
```

Textual's canonical key names for the arrow keys are `"left"` / `"right"`. The sidebar ListView only handles up/down, and the new `VerifiedRankingsPane` DataTable uses `cursor_type="row"` so it does not consume left/right either — the App-level binding will fire.

Add the matching actions, guarded by the currently-visible pane id (mirrors existing `action_new_custom`'s "only if focused" style). Place them near `action_refresh` / `action_new_custom`:

```python
def _current_pane_id(self) -> str | None:
    sidebar = self.query_one("#sidebar", ListView)
    idx = sidebar.index
    if idx is None or idx < 0 or idx >= len(self.active_layout):
        return None
    return self.active_layout[idx]

def action_prev_verified_op(self) -> None:
    self._cycle_verified_op(-1)

def action_next_verified_op(self) -> None:
    self._cycle_verified_op(+1)

def _cycle_verified_op(self, delta: int) -> None:
    if self._current_pane_id() != "agents.verified":
        return
    from stats.panes.agents import VerifiedRankingsPane  # local import avoids circular
    try:
        pane = self.query_one("#content VerifiedRankingsPane", VerifiedRankingsPane)
    except Exception:
        return
    pane.cycle_op(delta)
```

(Import lives inside the function to match the existing habit of minimal top-level imports from pane modules; `StatsApp` currently imports only `PANE_DEFS`.)

### 3. `tests/test_stats_verified_rankings.sh` (new — lightweight unit test)

Follow the `tests/test_stats_data.sh` pattern: bash wrapper + embedded `python3 - <<'PY'` blocks. Tests:

- `_ops_sorted_by_runs` orders ops by all-time `all_providers` runs desc, tie-broken by name asc.
- Operations with zero runs are excluded.
- Against the real repo data, `_ops_sorted_by_runs(load_verified_rankings())[0] == "pick"` (current dataset has pick as the most-used; if this ever changes, the test may need adjustment — document that in a comment).
- `VerifiedRankingsPane` constructs without error and `cycle_op(±1)` wraps correctly (no Textual app run needed — just instantiate and call, checking `_op_idx`).

## Verification

Run these after implementation:

1. **Unit test:** `bash tests/test_stats_verified_rankings.sh` — expect all PASS.
2. **Existing regression:** `bash tests/test_stats_data.sh` — expect no regressions.
3. **Interactive smoke test:** `ait stats-tui`
   - Pick the "Agents & Models" preset (or a custom layout that includes `agents.verified`).
   - Highlight the "Verified rankings" sidebar entry.
   - Expected: header shows `Operation: pick  (342 runs)  ← prev op · next op →`. Table rows rank the models with `pick` runs.
   - Press → → header shows next op (e.g. `explore  (32 runs)`), table repopulates.
   - Press ← → wraps back through ops in reverse.
   - Sidebar ↑/↓ still navigates panes normally (left/right are only consumed when the verified pane is visible).
   - Switch to a non-verified pane and press → / ← — no-op (guarded by `_current_pane_id()`).
   - Quit cleanly with `q`.
4. **Lint:** `shellcheck tests/test_stats_verified_rankings.sh`.

## Out of Scope

- Changing the `load_verified_rankings()` schema or data shape.
- Adding provider selection (the pane hard-codes `all_providers`). Still appropriate — per-provider breakdown is not the user-reported gap.
- Adding a footer-level binding display. The pane-level hint in the header suffices and keeps the footer clean across other panes.

## Step 9 Reference

After implementation and user approval, complete Post-Implementation (Step 9 of `.claude/skills/task-workflow/SKILL.md`):
- No separate branch (profile `fast` with `create_worktree: false`) — skip merge/worktree cleanup.
- Run `verify_build` if configured (see `aitasks/metadata/project_config.yaml`).
- Archive with `./.aitask-scripts/aitask_archive.sh 603`.
- `./ait git push`.
- Satisfaction feedback (Step 9b).

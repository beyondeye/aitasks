---
Task: t717_4_stats_tui_window_selector_usage_pane.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Sibling Tasks: aitasks/t717/t717_5_manual_verification_codeagent_usage_stats.md, aitasks/t717/t717_6_dedupe_verify_path_model_detection.md
Archived Sibling Plans: aiplans/archived/p717/p717_1_verifiedstats_prev_month_schema.md, aiplans/archived/p717/p717_2_usagestats_live_hook.md, aiplans/archived/p717/p717_3_agent_picker_recent_modes.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 12:42
---

# t717_4 — Stats TUI: window selector + usage pane

## Context

After siblings t717_1 (verifiedstats `prev_month` bucket) and t717_2 (parallel `usagestats` block + live hook) landed, two new data shapes exist that the stats TUI does not yet surface:

1. **Recent-window verified scores** — `month + prev_month` aggregated. Lets users see whether a new model has overtaken an incumbent without the noise of years-old scores.
2. **Usage rankings** — `usagestats[op]` populated unconditionally by the live hook, so codex-class agents (which skip every `AskUserQuestion` after `ExitPlanMode`) finally show up where verifiedstats was always blank.

This task adds:
- A window selector on the existing verified pane (cycle through `recent / all_time / month / prev_month / week`), default `recent`.
- A new sibling pane `agents.usage` with the same window selector, reading `usagestats`.
- Defensive cold-start handling so the panes work on models with no `prev_month` / `usagestats` yet.

Sibling t717_5 will manually verify the surfaces this task creates.

## Verification result (verify path, 2026-04-30)

The pre-existing plan was checked against the current codebase. Findings + corrections:

- `stats_data.py:128-143` — `VerifiedModelEntry` and `VerifiedRankingData` exist as documented. Extend rather than duplicate. ✓
- `stats_data.py:234-384` — `load_verified_rankings()` builds `by_window[op][provider][window]` keyed today by `all_time`, `month`, `week`. The per-provider loop (~lines 295-313) and the all-providers aggregation (~lines 315-373) both need extending for `prev_month` and `recent`. Defensive `.get(...)` reads already protect cold-start models. ✓
- `stats_app.py:420-431` — `action_prev_verified_op` / `action_next_verified_op` already dispatch to `_cycle_verified_op(delta)` which forwards to `pane.cycle_op(delta)`. **Correction:** the pre-existing plan stored `_verified_window` / `_usage_window` as App-level state on `StatsApp`. The actual codebase keeps cycling state on the pane object (`VerifiedRankingsPane._op_idx` at `panes/agents.py:74`). Window state must follow the same pattern — store on the pane, not on the app. App-level binding handlers call `pane.cycle_window(delta)` analogous to existing `pane.cycle_op(delta)`.
- `panes/agents.py:62-119` — `VerifiedRankingsPane._populate()` is where the DataTable is rendered, NOT in `stats_app.py`. The pre-existing plan's instruction to "DataTable rendering reads `verified_data.by_window[op][provider][_verified_window]`" applies in `_populate()`, not in `stats_app.py`.
- `panes/base.py` + `panes/__init__.py` — `PANE_DEFS` registry. New panes register via `register(PaneDef(id, title, category, render_fn))` at module import. The new pane will be `agents.usage` (mirrors `agents.verified` id format).
- `stats_config.py:17-23` `DEFAULT_PRESETS` and project-level `aitasks/metadata/stats_config.json` — the `agents` preset lists `["agents.per_agent", "agents.per_model", "agents.verified"]`. Append `"agents.usage"` to both so users see the new pane in the default layout. Per CLAUDE.md "No auto-commit/push of project-level config from runtime TUIs," runtime TUI saves are disallowed — but this is a one-time implementation commit, which is explicitly permitted by the same rule ("First-time ship of a project-level file is a one-time implementation commit").
- `aitask_stats.py:367-411` `render_verified_rankings` — already uses `.get("all_time", [])` defensively. The existing "This month" column won't show prev_month, but it won't crash either. **Correction:** the optional `--window` CLI flag in the pre-existing plan is dropped per "don't add features beyond what task requires." Defensive reads alone satisfy the requirement.
- `models_claudecode.json` — schema confirmed: `verifiedstats[op]` has `all_time / prev_month / month / week`; `usagestats[op]` has `all_time / prev_month / month / week` (no `score_sum`). Cold-start `prev_month` is `{"period": "", "runs": 0, "score_sum": 0}` (or `runs: 0` for usagestats).
- Sibling t717_3's `_recent_aggregate` helper in `agent_model_picker.py` is the canonical formulation. Per t717_3's "Notes for sibling tasks" and CLAUDE.md "Refactor duplicates before adding to them": the helper is 3-4 lines, picker uses Path-based module loading without `stats_data` import; a one-line duplicate in `stats_data.py` is cheaper than introducing a cross-module dependency. Mirror the helper, do not extract.

Conclusion: plan is sound in spirit; the implementation steps below correct the pane-state architecture and pane-registration details and drop the optional CLI flag.

## Implementation

### 1. `stats_data.py` — recent-window aggregate helper

Add near `bucket_avg()` (line 146):

```python
def recent_aggregate(buckets: dict) -> Tuple[int, int]:
    """Return (runs, score_sum) summed across month + prev_month.

    Mirrors agent_model_picker._recent_aggregate. Duplicated rather than
    extracted: picker uses Path-based module loading without stats_data
    dependency, so the one-line helper is cheaper to duplicate than to wire
    a cross-module import.
    """
    mo = buckets.get("month", {})
    pm = buckets.get("prev_month", {})
    runs = mo.get("runs", 0) + pm.get("runs", 0)
    sum_ = mo.get("score_sum", 0) + pm.get("score_sum", 0)
    return runs, sum_
```

### 2. `stats_data.py` — extend `load_verified_rankings()` for new windows

Two changes inside `load_verified_rankings()`:

**(a) Per-model raw collection (~lines 263-281):** include `prev_month` alongside `month` / `week` so the aggregator has it.

```python
raw[key][op] = {
    "all_time":   {"runs": at_runs, "score_sum": at.get("score_sum", 0)},
    "prev_month": buckets.get("prev_month", {}),
    "month":      buckets.get("month", {}),
    "week":       buckets.get("week", {}),
}
```

**(b) Per-provider entries (~lines 292-313):** add `prev_month` and `recent` to the dict factory and emit entries for both. `recent = month + prev_month` per provider.

```python
for (agent, cli_id), entry_ops in raw.items():
    if op not in entry_ops:
        continue
    buckets = entry_ops[op]
    if agent not in by_window[op]:
        by_window[op][agent] = {w: [] for w in WINDOW_KEYS}
    display = model_display_from_cli_id(cli_id)
    at = buckets["all_time"]
    by_window[op][agent]["all_time"].append(
        VerifiedModelEntry(cli_id, display, agent, bucket_avg(at["runs"], at["score_sum"]), at["runs"])
    )
    for win in ("month", "prev_month", "week"):
        wb = buckets.get(win, {})
        w_runs = wb.get("runs", 0)
        if w_runs > 0:
            by_window[op][agent][win].append(
                VerifiedModelEntry(cli_id, display, agent, bucket_avg(w_runs, wb.get("score_sum", 0)), w_runs)
            )
    # Recent = month + prev_month
    r_runs, r_sum = recent_aggregate(buckets)
    if r_runs > 0:
        by_window[op][agent]["recent"].append(
            VerifiedModelEntry(cli_id, display, agent, bucket_avg(r_runs, r_sum), r_runs)
        )
```

Define `WINDOW_KEYS` as a module-level constant:

```python
WINDOW_KEYS: Tuple[str, ...] = ("all_time", "recent", "month", "prev_month", "week")
```

**(c) All-providers aggregation (~lines 315-373):** mirror the per-provider extension. Extend the `grouped` defaultdict factory to include `prev_month`:

```python
grouped: Dict[str, Dict[str, dict]] = defaultdict(lambda: {
    "all_time":   {"runs": 0, "score_sum": 0},
    "month":      {"runs": 0, "score_sum": 0, "period": ""},
    "prev_month": {"runs": 0, "score_sum": 0, "period": ""},
    "week":       {"runs": 0, "score_sum": 0, "period": ""},
})
```

Extend the period-aware loop (~line 335) to also process `prev_month`:

```python
for win in ("month", "prev_month", "week"):
    ...  # existing period-matching aggregation
```

After the per-canonical loop builds `grouped`, synthesize `recent` per canonical model and emit `ap_entries`:

```python
ap_entries: Dict[str, List[VerifiedModelEntry]] = {w: [] for w in WINDOW_KEYS}
for canon, windows in grouped.items():
    at = windows["all_time"]
    if at["runs"] > 0:
        ap_entries["all_time"].append(VerifiedModelEntry(...))
    for win in ("month", "prev_month", "week"):
        wb = windows[win]
        if wb["runs"] > 0:
            ap_entries[win].append(VerifiedModelEntry(...))
    # Recent across this canonical model
    mo = windows["month"]
    pm = windows["prev_month"]
    r_runs = mo["runs"] + pm["runs"]
    r_sum  = mo["score_sum"] + pm["score_sum"]
    if r_runs > 0:
        ap_entries["recent"].append(
            VerifiedModelEntry(
                canonical_cli.get(canon, canon),
                canonical_display.get(canon, canon),
                "all_providers",
                bucket_avg(r_runs, r_sum),
                r_runs,
            )
        )
by_window[op]["all_providers"] = ap_entries
```

The final sort loop (~lines 376-382) iterates all windows already; no change needed.

### 3. `stats_data.py` — add usage rankings dataclasses + loader

```python
@dataclass
class UsageModelEntry:
    """A single model's usage count for ranking display."""
    cli_id: str
    display_name: str
    provider: str
    runs: int


@dataclass
class UsageRankingData:
    """Usage rankings by operation, provider, and time window."""
    by_window: Dict[str, Dict[str, Dict[str, List[UsageModelEntry]]]]
    operations: List[str]


def load_usage_rankings(project_root: Optional[Path] = None) -> UsageRankingData:
    """Mirror of load_verified_rankings, reading usagestats; no scores."""
    _, _, metadata_dir = _paths_for(project_root)
    agents = ("claudecode", "codex", "geminicli", "opencode")

    raw: Dict[Tuple[str, str], Dict[str, Dict[str, dict]]] = {}
    for agent in agents:
        path = metadata_dir / f"models_{agent}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for model in payload.get("models", []):
            cli_id = model.get("cli_id", "")
            ustats = model.get("usagestats")
            if not isinstance(ustats, dict) or not ustats or not cli_id:
                continue
            key = (agent, cli_id)
            raw[key] = {}
            for op, buckets in ustats.items():
                if not isinstance(buckets, dict):
                    continue
                at = buckets.get("all_time")
                if not isinstance(at, dict):
                    continue
                at_runs = at.get("runs", 0)
                if at_runs <= 0:
                    continue
                raw[key][op] = {
                    "all_time":   {"runs": at_runs},
                    "prev_month": buckets.get("prev_month", {}),
                    "month":      buckets.get("month", {}),
                    "week":       buckets.get("week", {}),
                }

    if not raw:
        return UsageRankingData(by_window={}, operations=[])

    all_ops: set = set()
    for entry_ops in raw.values():
        all_ops.update(entry_ops.keys())

    by_window: Dict[str, Dict[str, Dict[str, List[UsageModelEntry]]]] = {}
    for op in sorted(all_ops):
        by_window[op] = {}
        for (agent, cli_id), entry_ops in raw.items():
            if op not in entry_ops:
                continue
            buckets = entry_ops[op]
            if agent not in by_window[op]:
                by_window[op][agent] = {w: [] for w in WINDOW_KEYS}
            display = model_display_from_cli_id(cli_id)
            at = buckets["all_time"]
            by_window[op][agent]["all_time"].append(
                UsageModelEntry(cli_id, display, agent, at["runs"])
            )
            for win in ("month", "prev_month", "week"):
                wb = buckets.get(win, {})
                w_runs = wb.get("runs", 0)
                if w_runs > 0:
                    by_window[op][agent][win].append(
                        UsageModelEntry(cli_id, display, agent, w_runs)
                    )
            mo = buckets.get("month", {})
            pm = buckets.get("prev_month", {})
            r_runs = mo.get("runs", 0) + pm.get("runs", 0)
            if r_runs > 0:
                by_window[op][agent]["recent"].append(
                    UsageModelEntry(cli_id, display, agent, r_runs)
                )

        # All-providers aggregation by canonical model id
        grouped: Dict[str, Dict[str, dict]] = defaultdict(lambda: {
            "all_time":   {"runs": 0},
            "month":      {"runs": 0, "period": ""},
            "prev_month": {"runs": 0, "period": ""},
            "week":       {"runs": 0, "period": ""},
        })
        canonical_display: Dict[str, str] = {}
        canonical_cli: Dict[str, str] = {}
        for (agent, cli_id), entry_ops in raw.items():
            if op not in entry_ops:
                continue
            canon = canonical_model_id(cli_id)
            if canon not in canonical_display:
                canonical_display[canon] = model_display_from_cli_id(cli_id)
                canonical_cli[canon] = cli_id
            buckets = entry_ops[op]
            grouped[canon]["all_time"]["runs"] += buckets["all_time"]["runs"]
            for win in ("month", "prev_month", "week"):
                wb = buckets.get(win, {})
                w_runs = wb.get("runs", 0)
                w_period = wb.get("period", "")
                if w_runs <= 0 or not w_period:
                    continue
                g = grouped[canon][win]
                if not g["period"]:
                    g["period"] = w_period
                if g["period"] == w_period:
                    g["runs"] += w_runs

        ap_entries: Dict[str, List[UsageModelEntry]] = {w: [] for w in WINDOW_KEYS}
        for canon, windows in grouped.items():
            at = windows["all_time"]
            if at["runs"] > 0:
                ap_entries["all_time"].append(
                    UsageModelEntry(
                        canonical_cli.get(canon, canon),
                        canonical_display.get(canon, canon),
                        "all_providers",
                        at["runs"],
                    )
                )
            for win in ("month", "prev_month", "week"):
                wb = windows[win]
                if wb["runs"] > 0:
                    ap_entries[win].append(
                        UsageModelEntry(
                            canonical_cli.get(canon, canon),
                            canonical_display.get(canon, canon),
                            "all_providers",
                            wb["runs"],
                        )
                    )
            mo = windows["month"]
            pm = windows["prev_month"]
            r_runs = mo["runs"] + pm["runs"]
            if r_runs > 0:
                ap_entries["recent"].append(
                    UsageModelEntry(
                        canonical_cli.get(canon, canon),
                        canonical_display.get(canon, canon),
                        "all_providers",
                        r_runs,
                    )
                )
        by_window[op]["all_providers"] = ap_entries

    def _sort_key(e: UsageModelEntry) -> Tuple[int, str]:
        return (-e.runs, e.display_name)

    for op in by_window:
        for provider in by_window[op]:
            for win in by_window[op][provider]:
                by_window[op][provider][win].sort(key=_sort_key)

    return UsageRankingData(by_window=by_window, operations=sorted(all_ops))
```

### 4. `panes/agents.py` — extend `VerifiedRankingsPane` with window cycling

```python
WINDOWS = ("recent", "all_time", "month", "prev_month", "week")
DEFAULT_WINDOW_IDX = 0  # "recent"


class VerifiedRankingsPane(Vertical):
    """Verified-rankings pane: header + DataTable, cyclable with ← / → for op,
    [ / ] for window."""

    DEFAULT_CSS = """
    VerifiedRankingsPane { height: auto; }
    VerifiedRankingsPane > #verified_header { height: auto; padding: 0 0 1 0; }
    """

    def __init__(self, vdata: VerifiedRankingData) -> None:
        super().__init__()
        self._vdata = vdata
        self._ops = _ops_sorted_by_runs(vdata)
        self._op_idx = 0
        self._window_idx = DEFAULT_WINDOW_IDX
        self._header: Static | None = None
        self._table: DataTable | None = None

    # compose / on_mount unchanged

    def _populate(self) -> None:
        assert self._header is not None and self._table is not None
        if not self._ops:
            self._header.update("[dim]No verified rankings with runs[/dim]")
            return
        op = self._ops[self._op_idx]
        window = WINDOWS[self._window_idx]
        entries = (
            self._vdata.by_window.get(op, {})
            .get("all_providers", {})
            .get(window, [])
        )
        total_runs = sum(e.runs for e in entries)
        op_hint = "  [dim]← prev op · next op →[/dim]" if len(self._ops) > 1 else ""
        win_hint = "  [dim][ prev win · next win ][/dim]"
        self._header.update(
            f"Operation: [b]{op}[/b]  Window: [b]{window}[/b]  ({total_runs} runs){op_hint}{win_hint}"
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

    def cycle_window(self, delta: int) -> None:
        self._window_idx = (self._window_idx + delta) % len(WINDOWS)
        self._populate()
```

### 5. `panes/agents.py` — add `UsageRankingsPane` and register it

Add a parallel `_ops_sorted_by_runs` analog for usage data (or generalize):

```python
def _usage_ops_sorted_by_runs(udata: UsageRankingData) -> list[str]:
    """Operations with > 0 all_providers/all_time usage, desc by run count."""
    def total_runs(op: str) -> int:
        entries = udata.by_window.get(op, {}).get("all_providers", {}).get("all_time", [])
        return sum(e.runs for e in entries)

    ranked = [(op, total_runs(op)) for op in udata.operations]
    ranked = [(op, n) for op, n in ranked if n > 0]
    ranked.sort(key=lambda x: (-x[1], x[0]))
    return [op for op, _ in ranked]


class UsageRankingsPane(Vertical):
    """Usage-rankings pane: header + DataTable, cyclable with ← / → for op,
    [ / ] for window."""

    DEFAULT_CSS = """
    UsageRankingsPane { height: auto; }
    UsageRankingsPane > #usage_header { height: auto; padding: 0 0 1 0; }
    """

    def __init__(self, udata: UsageRankingData) -> None:
        super().__init__()
        self._udata = udata
        self._ops = _usage_ops_sorted_by_runs(udata)
        self._op_idx = 0
        self._window_idx = DEFAULT_WINDOW_IDX
        self._header: Static | None = None
        self._table: DataTable | None = None

    def compose(self):
        self._header = Static(id="usage_header")
        yield self._header
        self._table = DataTable(zebra_stripes=True, cursor_type="row")
        yield self._table

    def on_mount(self) -> None:
        assert self._table is not None
        self._table.add_columns("Rank", "Model", "Provider", "Runs")
        self._populate()

    def _populate(self) -> None:
        assert self._header is not None and self._table is not None
        if not self._ops:
            self._header.update("[dim]No usage rankings yet[/dim]")
            return
        op = self._ops[self._op_idx]
        window = WINDOWS[self._window_idx]
        entries = (
            self._udata.by_window.get(op, {})
            .get("all_providers", {})
            .get(window, [])
        )
        total_runs = sum(e.runs for e in entries)
        op_hint = "  [dim]← prev op · next op →[/dim]" if len(self._ops) > 1 else ""
        win_hint = "  [dim][ prev win · next win ][/dim]"
        self._header.update(
            f"Operation: [b]{op}[/b]  Window: [b]{window}[/b]  ({total_runs} runs){op_hint}{win_hint}"
        )
        self._table.clear(columns=False)
        for rank, entry in enumerate(entries, start=1):
            self._table.add_row(
                str(rank),
                entry.display_name,
                entry.provider,
                str(entry.runs),
            )

    def cycle_op(self, delta: int) -> None:
        if len(self._ops) <= 1:
            return
        self._op_idx = (self._op_idx + delta) % len(self._ops)
        self._populate()

    def cycle_window(self, delta: int) -> None:
        self._window_idx = (self._window_idx + delta) % len(WINDOWS)
        self._populate()


def _render_usage(stats: StatsData, container: Container) -> None:
    udata = load_usage_rankings()
    if not _usage_ops_sorted_by_runs(udata):
        empty_state(container, "No usage rankings available yet")
        return
    container.mount(UsageRankingsPane(udata))


register(PaneDef("agents.usage", "Usage rankings", "Agents", _render_usage))
```

Update the import line at top of `panes/agents.py`:

```python
from stats.stats_data import (
    StatsData,
    UsageRankingData,
    VerifiedRankingData,
    build_chart_title,
    chart_totals,
    codeagent_display_name,
    load_usage_rankings,
    load_verified_rankings,
)
```

### 6. `stats_app.py` — App-level bindings for `[` / `]`

Add to `BINDINGS` (~lines 141-154), after the existing `right` binding:

```python
Binding("[", "prev_window", "[ Window", show=True),
Binding("]", "next_window", "] Window", show=True),
```

Add action handlers (near `action_prev_verified_op`, ~line 420):

```python
def action_prev_window(self) -> None:
    self._cycle_window(-1)

def action_next_window(self) -> None:
    self._cycle_window(+1)

def _cycle_window(self, delta: int) -> None:
    pane_id = self._current_pane_id()
    if pane_id == "agents.verified":
        from stats.panes.agents import VerifiedRankingsPane
        try:
            pane = self.query_one("#content VerifiedRankingsPane", VerifiedRankingsPane)
        except Exception:
            return
        pane.cycle_window(delta)
    elif pane_id == "agents.usage":
        from stats.panes.agents import UsageRankingsPane
        try:
            pane = self.query_one("#content UsageRankingsPane", UsageRankingsPane)
        except Exception:
            return
        pane.cycle_window(delta)
    # Other panes: silent no-op (matches existing _cycle_verified_op fall-through pattern).
```

Also extend `action_prev_verified_op` / `action_next_verified_op` to handle `agents.usage` — the existing `←` / `→` handlers should cycle the usage pane's op too. Generalize:

```python
def action_prev_verified_op(self) -> None:
    pane_id = self._current_pane_id()
    if pane_id == "agents.verified":
        self._cycle_verified_op(-1)
    elif pane_id == "agents.usage":
        self._cycle_usage_op(-1)
    elif self.multi_session:
        self._cycle_session(-1)

def action_next_verified_op(self) -> None:
    pane_id = self._current_pane_id()
    if pane_id == "agents.verified":
        self._cycle_verified_op(+1)
    elif pane_id == "agents.usage":
        self._cycle_usage_op(+1)
    elif self.multi_session:
        self._cycle_session(+1)

def _cycle_usage_op(self, delta: int) -> None:
    if self._current_pane_id() != "agents.usage":
        return
    from stats.panes.agents import UsageRankingsPane
    try:
        pane = self.query_one("#content UsageRankingsPane", UsageRankingsPane)
    except Exception:
        return
    pane.cycle_op(delta)
```

(Optional rename later — for this task, the existing action names `action_prev_verified_op` / `action_next_verified_op` stay since they're load-bearing in `BINDINGS`.)

### 7. `stats_config.py` + `aitasks/metadata/stats_config.json` — register pane in default layout

In `stats_config.py:17-23`, append `"agents.usage"` to the `agents` preset:

```python
DEFAULT_PRESETS: dict[str, list[str]] = {
    ...
    "agents":   ["agents.per_agent", "agents.per_model", "agents.verified", "agents.usage"],
    ...
}
```

Mirror in the project-level file `aitasks/metadata/stats_config.json`:

```json
{
  "presets": {
    ...
    "agents":   ["agents.per_agent", "agents.per_model", "agents.verified", "agents.usage"],
    ...
  }
}
```

This is a one-time implementation commit (per CLAUDE.md), permitted alongside the code shipping the new pane.

### 8. `aitask_stats.py` — defensive read confirmation

No code change required. `render_verified_rankings` (line 367) already uses `.get("all_time", [])` defensively, so the new `prev_month` / `recent` keys do not crash anything. The optional `--window` CLI flag from the pre-existing plan is dropped — adds surface area for a TUI-shaped feature without a clear CLI use case.

Update the `__all__` export list in `aitask_stats.py:64-100` to include the new public names (`UsageModelEntry`, `UsageRankingData`, `load_usage_rankings`, `recent_aggregate`, `WINDOW_KEYS`) so existing test patterns that import from `aitask_stats` keep working.

## Key Files to Modify

- `.aitask-scripts/stats/stats_data.py` — add helper, dataclasses, loader; extend `load_verified_rankings`.
- `.aitask-scripts/stats/panes/agents.py` — extend `VerifiedRankingsPane`, add `UsageRankingsPane` + render func + register.
- `.aitask-scripts/stats/stats_app.py` — add `[` / `]` bindings + handlers; extend op-cycle handlers to dispatch to usage pane.
- `.aitask-scripts/stats/stats_config.py` — append `agents.usage` to `DEFAULT_PRESETS["agents"]`.
- `aitasks/metadata/stats_config.json` — append `agents.usage` to project-level `agents` preset.
- `.aitask-scripts/aitask_stats.py` — extend `__all__` with new public names.

## Reference Files for Patterns

- `agent_model_picker.py` `_recent_aggregate` (from t717_3) — canonical recent-window math; mirror in `stats_data.py`.
- `panes/agents.py` `VerifiedRankingsPane` — pane state pattern (`_op_idx`); extend with `_window_idx`.
- `stats_app.py:420-431` — App-level binding handler pattern; mirror for window cycling.
- `panes/base.py` `register(PaneDef(...))` — pane registration mechanism.

## Verify

1. **Syntax check:**
   ```bash
   python3 -m py_compile .aitask-scripts/stats/stats_data.py \
                         .aitask-scripts/stats/panes/agents.py \
                         .aitask-scripts/stats/stats_app.py \
                         .aitask-scripts/stats/stats_config.py \
                         .aitask-scripts/aitask_stats.py
   ```

2. **Existing stats tests still pass** (if any):
   ```bash
   ls tests/test_stats* 2>/dev/null && bash tests/test_stats*.sh
   ```

3. **CLI sanity:**
   ```bash
   ./ait stats
   ```
   Output unchanged for default invocation; verified rankings section continues to render. No crash from new `prev_month` keys.

4. **TUI manual check:** `./ait stats tui`
   - Navigate to "Verified rankings" pane (default in `agents` preset).
   - Header shows `Operation: pick  Window: recent  (N runs)` plus hint text.
   - Press `]` → cycles `recent → all_time → month → prev_month → week → recent`. Table updates each cycle.
   - Press `←` / `→` → cycles ops as before.
   - Navigate to new "Usage rankings" pane.
   - Header / cycling works identically; columns are `Rank, Model, Provider, Runs` (no Score).
   - Cold-start defense: temporarily `mv aitasks/metadata/models_codex.json /tmp/`. Re-launch TUI. Both panes still render; codex absent from rankings; no crash. Restore.

## Verification (manual checklist for t717_5)

- [ ] Stats TUI verified pane has window selector keyed `[` / `]`.
- [ ] Default window is `recent`.
- [ ] All 5 windows produce non-error output (data may be empty for fresh models).
- [ ] Stats TUI `agents.usage` pane exists and is reachable from default `agents` preset.
- [ ] Usage pane cycles ops with `←` / `→`.
- [ ] Usage pane cycles windows with `[` / `]`.
- [ ] CLI `./ait stats` does not crash on the new schema; verified-rankings section still renders.
- [ ] Removing a `models_*.json` file does not crash either pane.

## Out of scope

- The optional `--window <key>` CLI flag (deferred — no clear CLI use case yet).
- Extracting `_recent_aggregate` to a shared module (the picker uses Path-based loading and has no `stats_data` dependency; one-line duplication is preferred per t717_3 notes).
- Any layout-export mechanism in the TUI (project-level `stats_config.json` is updated as a one-time implementation commit, not via runtime save).
- Changing op-sort order based on the active window (kept stable on all-time runs to avoid op-shuffle when the user changes windows).

## Notes for sibling tasks (t717_5)

- The pane headers are explicit about which window is active and which keys cycle them — the manual checklist references those labels (`Window: recent`, `[ prev win · next win ]`).
- Both `[` / `]` are App-level bindings, so they appear in the footer alongside `←` / `→`. The checklist verifier should see them in the footer hint list.
- If t717_5 surfaces a UX issue (e.g., users miss the in-header window indicator), defer fixes to a follow-up task rather than amending t717_4 mid-stream.

## Step 9: Post-Implementation

Standard archival via `./.aitask-scripts/aitask_archive.sh 717_4`. Folded tasks: none.

## Post-Review Changes

### Change Request 1 (2026-04-30 12:50)
- **Requested by user:** The in-pane window-cycle hint `[ prev win · next win ]` was unclear — even spelling out "prev window / next window" felt ambiguous. Clarify what is being cycled.
- **Changes made:** Replaced the hint string in both `VerifiedRankingsPane._populate()` and `UsageRankingsPane._populate()` (`panes/agents.py` lines 110, 197) with `press [ or ] to switch time window`, with the bracket key chars rendered bold. Bold tags use Rich's `[b]\[[/b]` (escaped) for `[` and `[b]][/b]` for `]` (Rich does not escape `]`).
- **Files affected:** `.aitask-scripts/stats/panes/agents.py`

### Change Request 2 (2026-04-30 12:53)
- **Requested by user:** Footer binding labels `[ Window` and `] Window` are still unclear. Use `prev window` / `next window` instead.
- **Changes made:** Renamed the two Binding descriptions in `stats_app.py` BINDINGS list: `Binding("[", "prev_window", "prev window", show=True)` and `Binding("]", "next_window", "next window", show=True)`. The footer renders `[: prev window  ]: next window` (key column comes from the binding key arg).
- **Files affected:** `.aitask-scripts/stats/stats_app.py`

## Final Implementation Notes

- **Actual work done:**
  - **`stats_data.py`**: added `WINDOW_KEYS = ("all_time", "recent", "month", "prev_month", "week")`, `recent_aggregate(buckets) -> (runs, score_sum)` helper (mirror of picker's `_recent_aggregate`), and the `UsageModelEntry` / `UsageRankingData` dataclasses. Extended `load_verified_rankings()`: per-model raw collection now carries `prev_month`; the per-provider loop emits entries for `prev_month` and synthesizes `recent`; the all-providers `grouped` defaultdict factory was extended with `prev_month`, the period-aware loop now also processes `prev_month`, and per-canonical `recent` is synthesized from `month + prev_month` after grouping. Added new `load_usage_rankings()` mirroring the verified shape but without `score_sum` (sort key is `-runs, display_name`); cold-start defensive — empty `usagestats` returns empty `UsageRankingData`.
  - **`panes/agents.py`**: added module-level `WINDOWS = ("recent", "all_time", "month", "prev_month", "week")` and `DEFAULT_WINDOW_IDX = 0`. Extended `VerifiedRankingsPane` with `_window_idx` state, `cycle_window(delta)` method, and `_populate()` now reads `by_window[op][provider][WINDOWS[_window_idx]]` instead of hardcoded `all_time`. Header now displays `Operation: <op>  Window: <window>  (N runs)` plus dynamic op/window hints. Added a parallel `UsageRankingsPane` class mirroring the verified pane (columns: Rank/Model/Provider/Runs — no Score), `_usage_ops_sorted_by_runs` helper, `_render_usage` render function, and `register(PaneDef("agents.usage", "Usage rankings", "Agents", _render_usage))`.
  - **`stats_app.py`**: added two App-level bindings `Binding("[", "prev_window", "prev window", show=True)` and `Binding("]", "next_window", "next window", show=True)`. New action handlers `action_prev_window` / `action_next_window` dispatch to `_cycle_window(delta)` which checks `_current_pane_id()` and forwards to the appropriate pane's `cycle_window`. Extended `action_prev_verified_op` / `action_next_verified_op` to also dispatch to `agents.usage` via a new `_cycle_usage_op(delta)` helper paralleling the existing `_cycle_verified_op`.
  - **`stats_config.py`**: appended `"agents.usage"` to `DEFAULT_PRESETS["agents"]`.
  - **`aitasks/metadata/stats_config.json`**: mirrored the preset addition (one-time implementation commit per CLAUDE.md "First-time ship of a project-level file is a one-time implementation commit" — runtime TUI saves to project-level files remain disallowed).
  - **`aitask_stats.py`**: extended the `from stats.stats_data import (...)` block and the `__all__` re-export list with `UsageModelEntry`, `UsageRankingData`, `WINDOW_KEYS`, `load_usage_rankings`, `recent_aggregate`. No CLI logic change — `render_verified_rankings` already used `.get("all_time", [])` defensively.
- **Deviations from plan:**
  - The pre-existing plan stored window state on the App (`StatsApp._verified_window` / `_usage_window`); the verify-path correction moved that state onto each pane (`_window_idx`) to match the existing `_op_idx` pattern. App-level binding handlers dispatch to the pane's `cycle_window`, identical to how `cycle_op` is dispatched. This was foreshadowed in the plan's "Verification result" section.
  - The optional `--window <key>` CLI flag from the pre-existing plan was dropped per "don't add features beyond what task requires." Defensive `.get(...)` reads in `aitask_stats.py:render_verified_rankings` already prevent any crash on the new schema, and the CLI report's "This month" column continues to render as before.
  - Two post-review change requests adjusted the in-pane window-cycle hint and the footer binding labels (logged above as Change Requests 1 and 2). No code-path or data-shape changes — pure UX-text tightening.
- **Issues encountered:**
  - Working tree contained pre-existing in-flight changes from prior sessions (modified `brainstorm/`, `codebrowser/`, `lib/section_viewer.py`; untracked `monitor/tmux_control.py`, junk python files at repo root, etc.) — already documented in t717_2's Final Implementation Notes. Stayed isolated: only the t717_4-relevant files were staged for the implementation commit.
  - Initial Rich-markup attempt for the in-pane hint used `\\]` to escape `]`, which Rich rendered as a literal backslash. Confirmed via a small console test that Rich's `[`-escape (`\[`) is asymmetric — `]` does not need escaping. Adjusted accordingly.
- **Key decisions:**
  - Pane state vs App state (verified-path correction): kept window state on the pane to match the existing `_op_idx` pattern. Means the window resets to `recent` whenever the user navigates away and back to the pane (parallel to op resetting to the first op). Predictable and consistent; the alternative (App-level state) would require global state management for two independent panes.
  - Op sort order kept stable on `all_time` runs even when the user switches to a different window. Avoids op-list shuffling mid-cycle, which would be confusing.
  - `_recent_aggregate` helper duplicated in `stats_data.py` rather than extracted from `agent_model_picker.py`. Picker uses Path-based module loading without `stats_data` import; coupling them via a shared module would introduce a cross-module dependency for ~5 lines of math. t717_3's "Notes for sibling tasks" explicitly recommended this trade-off.
  - Project-level `aitasks/metadata/stats_config.json` is updated as a one-time implementation commit alongside the code shipping the new pane. Per CLAUDE.md "No auto-commit/push of project-level config from runtime TUIs" the rule targets runtime TUI saves, not implementation commits — explicitly carved out by the same paragraph.
- **Upstream defects identified:** None.
- **Notes for sibling tasks (t717_5):**
  - Pane headers now display `Operation: <op>  Window: <window>  (N runs)` followed by dynamic hints. Manual checklist can grep for the literal string `Window: recent` to confirm the default window is correct.
  - Footer hint shows `[: prev window  ]: next window` alongside the existing `←: ← Cycle  →: → Cycle`. The verifier should see all four hints in the footer when standing on either `agents.verified` or `agents.usage`.
  - In-pane hint reads `press [ or ] to switch time window` (bracket key chars bolded). Use this exact phrasing in the manual checklist for at-a-glance recognition.
  - `agents.usage` is now part of the default `agents` preset. Users with a customized layout (saved in `stats_config.local.json`) will need to add it manually via the `+ New custom` flow — this is expected behavior, not a bug to chase.

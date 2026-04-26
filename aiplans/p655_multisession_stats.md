---
Task: t655_multisession_stats.md
Base branch: main
plan_verified: []
---

# Plan: t655 — Multi-session aggregate stats in `ait stats` TUI

## Context

`ait stats-tui` (launched by `.aitask-scripts/aitask_stats_tui.sh` → `stats/stats_app.py`) currently scans `aitasks/archived/` relative to the current working directory. Because each tmux session in this framework is rooted in its own aitasks project, the TUI implicitly shows stats only for the project of the session it was launched from.

When several aitasks projects coexist on the same tmux server (one session per project), there is no way to view stats for *another* session's project, nor an aggregate across all of them. Per t655, the user wants:

1. A way to cycle the TUI's data scope between detected sessions and an "All sessions (aggregate)" view.
2. A new pane showing per-session totals (today / 7d / 30d) as a comparison bar chart.
3. No behavior change when only one aitasks session is detected.

User-confirmed UX:
- Single-view with cycling selector at the top of the left column (mirroring the TUI switcher pattern), default = current attached session.
- Extra pane: per-session totals bar chart with three metrics per session (today, 7d, 30d).
- Hide the selector entirely when <2 aitasks sessions are detected — preserves today's behavior.

## Approach

Refactor the data layer to be project-root parameterizable, add a session-selector widget to the TUI's left column (only when ≥2 sessions are detected), and add one new pane for the per-session comparison.

The data layer is a clean place to inject scoping because all path inputs in `stats_data.py` derive from a single module-level `TASK_DIR = Path("aitasks")`. We thread a `project_root: Path | None = None` parameter through `collect_stats()` and its helpers; default `None` keeps every existing caller (CLI report, current TUI) working unchanged.

The TUI gains a `Vertical` selector widget at the top of `#left_column` that lists the discovered sessions plus an "All sessions" entry. Selecting a row triggers `_load_data()` which calls `collect_stats(project_root=...)` once per session it has not seen before, caches the result, and either returns a single `StatsData` or a merged one (new helper `merge_stats_data()`).

Session detection reuses the existing `discover_aitasks_sessions()` from `lib/agent_launch_utils.py` — same primitive used by `tui_switcher.py`. The "current" session is detected via `$TMUX` (already done in `tui_switcher.py:57` and `:_detect_current_session` flow) and used as the default selection.

## Critical files

- `.aitask-scripts/stats/stats_data.py` — parameterize project_root, add `merge_stats_data()`
- `.aitask-scripts/stats/stats_app.py` — add session selector widget, multi-session data loading, key bindings
- `.aitask-scripts/stats/panes/sessions.py` — NEW file, the per-session totals pane
- `.aitask-scripts/stats/panes/__init__.py` — register the new module
- `.aitask-scripts/stats/stats_config.py` — add a "sessions" preset (only useful in multi-session mode)

## Implementation steps

### 1. Refactor `stats_data.py` to accept a `project_root` parameter

Add a small helper that resolves paths from a project root, keeping module-level constants as backward-compat defaults:

```python
def _paths_for(project_root: Path | None) -> tuple[Path, Path, Path]:
    base = project_root if project_root is not None else Path.cwd()
    task_dir = base / "aitasks" if project_root is not None else TASK_DIR
    return task_dir, task_dir / "archived", task_dir / "metadata"
```

(Behavior: `project_root=None` → use the existing relative `TASK_DIR` so cwd-based callers work unchanged. `project_root=<path>` → absolute paths under that root.)

Thread the `project_root` argument through:
- `collect_stats(today, week_start_dow, project_root=None)` — pass through to its helpers and `iter_archived_markdown_files`.
- `iter_archived_markdown_files(project_root=None)` — compute `archive_dir = _paths_for(project_root)[1]` and pass it to `iter_all_archived_markdown`.
- `load_model_cli_ids(project_root=None)` and `load_verified_rankings(project_root=None)` — use `_paths_for(project_root)[2]` for `metadata_dir`.
- `get_valid_task_types(project_root=None)` — use `_paths_for(project_root)[0] / "metadata" / "task_types.txt"`.

Inside `collect_stats()`, replace the bare `iter_archived_markdown_files()` and `load_model_cli_ids()` calls with the parameterized versions.

Verification: run `./.aitask-scripts/aitask_stats.sh` (the legacy CLI) and confirm output is unchanged when `project_root` is left as default.

### 2. Add `merge_stats_data()` helper to `stats_data.py`

```python
def merge_stats_data(parts: list[StatsData]) -> StatsData:
    """Sum/union per-session StatsData objects into one aggregate."""
```

Implementation strategy:
- Counters: `Counter()` + sum via `+=` — no key collisions because `daily_counts` keys are dates, `(label, week_offset)` keys, etc. (task_ids would collide only in `daily_tasks`, which is fine — values are appended lists).
- Sets (`all_labels`, `all_codeagents`, `all_models`): union with `|=`.
- Display name dicts (`codeagent_display_names`, `model_display_names`): merge with later wins (display names should be stable across projects).
- `daily_tasks: Dict[date, List[str]]` — extend lists. Add a project prefix to task IDs to keep them unique in the merged view: `f"{project_name}/{task_id}"`. This requires `merge_stats_data` to receive a parallel list of project names, OR — simpler — leave task IDs unprefixed because no current pane displays the raw task_ids. Confirm by `grep -n "daily_tasks" .aitask-scripts/stats/`. **Decision**: leave as plain extend; revisit only if a pane surfaces individual task IDs.
- `csv_rows`: concat in order.
- Scalars (`total_tasks`, `tasks_7d`, `tasks_30d`): sum.

Edge case: `parts == []` → return an empty `StatsData` (use the same empty-init pattern as inside `collect_stats`).

### 3. Extend `StatsApp` with session detection and per-session caching

Modify `stats_app.py`:

```python
from lib.agent_launch_utils import discover_aitasks_sessions, AitasksSession
from stats.stats_data import StatsData, collect_stats, merge_stats_data

def __init__(self) -> None:
    super().__init__()
    self.current_tui_name = "stats"
    self.config: dict = stats_config.load()
    self.active_layout: list[str] = self._resolve_layout()
    self.sessions: list[AitasksSession] = discover_aitasks_sessions()
    self.multi_session: bool = len(self.sessions) >= 2
    self._session_cache: dict[str, StatsData] = {}  # keyed by session name
    self.selected_session: str = self._default_selection()  # session name or "__all__"
    self.stats_data: StatsData | None = None
```

Helpers:
- `_default_selection()` — read `os.environ.get("TMUX")`, match against `self.sessions` to find the attached session; fall back to the first session if no match.
- `_session_key_to_label(key)` — `key="__all__"` → `"All sessions (aggregate)"`, else use `f"{sess.session} ({sess.project_name})"`.

`_load_data()` becomes session-aware:

```python
def _load_data(self) -> None:
    if not self.multi_session:
        self.stats_data = collect_stats(date.today(), 1)  # unchanged
        return
    if self.selected_session == "__all__":
        parts = [self._stats_for(s) for s in self.sessions]
        self.stats_data = merge_stats_data(parts)
    else:
        sess = next(s for s in self.sessions if s.session == self.selected_session)
        self.stats_data = self._stats_for(sess)

def _stats_for(self, sess: AitasksSession) -> StatsData:
    cached = self._session_cache.get(sess.session)
    if cached is None:
        cached = collect_stats(date.today(), 1, project_root=sess.project_root)
        self._session_cache[sess.session] = cached
    return cached
```

`action_refresh()` clears the cache before reloading.

### 4. Add the session selector widget to the left column

Modify `compose()` so the left column gains a top section *only* when `multi_session` is true:

```python
with Vertical(id="left_column"):
    if self.multi_session:
        with Vertical(id="session_panel"):
            yield Label("Session", id="session_panel_title")
            yield ListView(*self._build_session_items(), id="session_list")
    yield ListView(*self._build_sidebar_items(), id="sidebar")
    with Vertical(id="layout_panel"):
        ...
```

CSS: give `#session_panel` `height: auto; max-height: 30%; border-bottom: tall $accent;` so it sits above the sidebar with a visual divider, mirroring the existing layout-panel pattern.

`_build_session_items()` returns one `_SessionItem(ListItem)` per detected session plus an "All sessions" item at the end. Each carries a `session_key` attribute (`session name` or `"__all__"`). Pre-select the row matching `self.selected_session` via `index = ...` after mount.

Selection handler:

```python
async def on_list_view_selected(self, event: ListView.Selected) -> None:
    item = event.item
    if isinstance(item, _LayoutListItem):
        await self._activate_layout_item(item)
    elif isinstance(item, _SessionItem):
        if item.session_key != self.selected_session:
            self.selected_session = item.session_key
            self._load_data()
            self._refresh_current_pane()
            self.notify(f"Session: {self._session_key_to_label(item.session_key)}", timeout=1)
```

Highlight handler (highlight-only preview is overkill for sessions — they're list items selected with Enter, matching the layout-panel UX).

Tab focus cycle: extend `_cycle_focus()` to include the session list when present:
- Single-session mode: sidebar ↔ layouts (unchanged).
- Multi-session mode: session_list → sidebar → layouts → session_list.

Update `_apply_focus_hint()` to add/remove the `focused_panel` class on the session list as well.

### 5. New per-session totals pane (`panes/sessions.py`)

Create `.aitask-scripts/stats/panes/sessions.py`:

```python
from .base import PaneDef, register, render_chart, empty_state

def _render_totals(stats, container):
    # Sessions only mean something in multi-session mode; in single-session
    # mode this pane is harmless but degenerate (one bar group).
    sessions = stats.session_breakdown  # see Note below
    if not sessions:
        empty_state(container, "Per-session breakdown unavailable")
        return
    labels = [s.project_name for s in sessions]
    today = [s.tasks_today for s in sessions]
    seven = [s.tasks_7d for s in sessions]
    thirty = [s.tasks_30d for s in sessions]

    def _setup(plt):
        plt.multiple_bar(labels, [today, seven, thirty],
                         labels=["Today", "7d", "30d"])
        plt.title("Per-session totals")
    render_chart(_setup, container)

register(PaneDef(
    id="sessions.totals",
    title="Per-session totals",
    category="Sessions",
    render=_render_totals,
))
```

Register the module in `panes/__init__.py`:

```python
from . import overview, labels, agents, velocity, sessions  # noqa: F401
```

**Note on `session_breakdown`**: This pane needs per-session figures. Two implementation options:

1. **Carry per-session breakdown on `StatsData`**: Add an optional `session_breakdown: list[SessionTotals] | None` field (default `None`). `StatsApp._load_data()` populates it in multi-session mode by computing `(name, today_count, 7d_count, 30d_count)` from each cached `StatsData` *before* merging. The pane reads it directly.

2. **Recompute in the pane**: Pane reads sessions from a global / shared state. Less clean.

Use option 1. Add `SessionTotals` dataclass and the optional field in `stats_data.py`, populate from `StatsApp._load_data()`. `tasks_today` derives from `daily_counts.get(date.today(), 0)`. Keep `session_breakdown=None` in single-session mode so the pane displays "Per-session breakdown unavailable" gracefully.

### 6. Add a "sessions" layout preset

In `stats_config.py`, extend the presets dict:

```python
"sessions": ["sessions.totals", "overview.summary", "overview.daily"],
```

This preset exists in the config regardless of mode (presets are static), but `sessions.totals` gracefully shows the "unavailable" message in single-session mode.

### 7. Key bindings

Add a binding only meaningful in multi-session mode (still safe to register unconditionally — it no-ops when there's no session list to focus):

```python
Binding("s", "focus_sessions", "Sessions"),
```

Action:
```python
def action_focus_sessions(self) -> None:
    if not self.multi_session:
        return
    self.query_one("#session_list", ListView).focus()
    self._apply_focus_hint()
```

Footer auto-updates from `BINDINGS`, so `s` shows up. The existing `c` (Layouts), `r` (Refresh), `n` (New custom), `q` (Quit) bindings stay untouched. Left/Right (used by `prev/next_verified_op` on the agents.verified pane) are not reused — session cycling happens via Up/Down within the focused session ListView, which is Textual's default.

### 8. Header / status line

After loading data, update the App title to make the active scope visible:

```python
def _update_title(self) -> None:
    if self.multi_session:
        label = self._session_key_to_label(self.selected_session)
        self.title = f"ait stats — {label}"
    else:
        self.title = "ait stats"
```

Call from `on_mount()` and after every session change.

## Out of scope (defer)

- The CLI report (`aitask_stats.py` / `aitask_stats.sh`) is **not** modified. Adding a `--project-root` or `--all-sessions` flag is a separate task; the data layer refactor (step 1) makes it trivial later.
- No new tests added — the test suite is bash and `stats_data.py` has no existing pytest harness in this repo. Manual verification (below) is the validation path.
- No changes to `panes/__init__.py` other than the one new import.

## Verification

End-to-end manual test (requires ≥2 aitasks projects in tmux sessions):

1. Single-session sanity: from a fresh shell with no tmux running, launch `./.aitask-scripts/aitask_stats_tui.sh`. Confirm no session selector appears, sidebar contains the standard panes, all charts render the same as before. `q` quits.
2. Run the existing CLI report:
   ```bash
   ./.aitask-scripts/aitask_stats.sh
   ```
   Confirm output is byte-identical to a pre-change run (capture before/after with `> /tmp/before.txt` / `> /tmp/after.txt`, `diff` should be empty). Validates the data-layer refactor is backward-compatible.
3. Multi-session: in tmux, attach a session for this project (`aitasks`) and a second session whose pane cwd is inside another aitasks project (or set `AITASKS_PROJECT_<sess>` via `tmux set-environment -g`). Run `ait stats-tui`.
   - Confirm session selector appears at top-left.
   - Default selection = attached session.
   - Switching to the other session re-renders all panes with that project's numbers.
   - Switching to "All sessions (aggregate)" shows summed totals; e.g., the "Total" card on `overview.summary` equals the sum of the per-session totals.
   - Apply the new "sessions" preset (Layouts → sessions). Confirm the "Per-session totals" pane shows one bar group per detected session with three bars (today/7d/30d) per group and that the values match what each individual session shows.
4. `r` (refresh) clears the per-session cache and reloads.
5. Step 9 (Post-Implementation): merge to main per the standard workflow in `.claude/skills/task-workflow/SKILL.md`.

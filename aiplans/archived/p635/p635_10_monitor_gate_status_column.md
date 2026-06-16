---
Task: t635_10_monitor_gate_status_column.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_11_*.md … t635_22_*.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_*.md … p635_9_board_inflight_action_view.md
Base branch: main
---

# t635_10 — Monitor gate-status column

## Context

Phase 3 of the gate-framework integration roadmap
(`aidocs/gates/integration-roadmap.md`) asks the monitor TUIs to surface a
compact per-task gate summary (e.g. `3/4 pass, 1 pending`) so a watcher can see,
at a glance, where each in-flight task sits in its gate ledger. The shared
Python derivation module (`t635_8`, `.aitask-scripts/lib/gate_ledger.py`) and the
board In-Flight view (`t635_9`) already landed; the board's
`Final Implementation Notes` explicitly point here:

> t635_10 can use the same `TaskManager.gate_state_for` pattern for
> monitor-visible gate status instead of adding a second parser path.

This task adds that summary to `ait monitor` and (where the narrow layout
allows) `ait minimonitor`, reusing the shared parser as the single source of
truth. Tasks without a gate ledger show nothing — no column noise for the common
ungated case. Display-only for v1 (no new keybindings).

## Approach

Reuse the **shared parser** `gate_ledger.read_task_gate_state` (one derivation
path, mirroring the board) and render a compact one-line summary derived from the
recorded gate runs (`TaskGateState.current`). Mirror the board's **per-refresh
cache + fail-closed** discipline so a live-growing ledger updates each cycle and
an unparseable ledger never breaks the monitor.

**Project-root correctness (must-fix).** `TaskInfo.task_file` is stored
**relative** to the owning project root (`monitor_core.py:1816`,
`str(task_path.relative_to(root))`) and `tests/test_task_info_cache_archived.py`
asserts that relative form — so it cannot be passed to
`read_task_gate_state`, which would resolve it against the current working
directory and read the wrong file (or nothing) in cross-session / multi-project
monitor mode. Fix: add an **absolute** path field `task_file_abs` to `TaskInfo`
(the project roots are absolute — `agent_launch_utils.py:115`, and the local
root uses `.resolve()` — so `str(task_path)` is a stable absolute path), and have
the gate cache key + parse off `task_file_abs`, never the relative `task_file`.

Four pieces, smallest blast radius:

1. A pure, unit-testable formatter in the shared parser module
   (`compact_gate_summary`).
2. An absolute `task_file_abs` field on `TaskInfo`, plus a small per-refresh
   cache object in `monitor_core.py` (`GateSummaryCache`), re-exported via
   `monitor_shared.py` next to `TaskInfoCache`, consumed identically by both apps.
3. One render-site edit in the full monitor's `_format_agent_card_text`, plus a
   cache-clear in its refresh loop.
4. One render-site edit in the minimonitor **general pane list**
   (`_agent_card_text`) only — explicitly **not** the static docked
   followed-agent panel (see §4) — plus a cache-clear in its refresh loop.

## Key changes

### 1. `.aitask-scripts/lib/gate_ledger.py` — add `compact_gate_summary`

Add a pure function (near `format_status`, ~line 252) that turns a
`TaskGateState` into the compact column string. Derives over the recorded gate
runs (`state.current`, i.e. last-run-per-gate) — **not** `declared_gates`, which
is empty today (no task declares `gates:` yet), so a declared-based count would
read `0/0` for everything. The registry is not needed (pure status counting), so
no `gates.yaml` lookup.

```python
def compact_gate_summary(state: TaskGateState) -> str:
    """Compact one-line gate summary for monitor TUI columns.

    Derived from the recorded gate runs (last run per gate). Returns ``""``
    when no gate runs are recorded (caller shows no column). Example output:
    ``"3/4 pass, 1 pending"`` or ``"2/2 pass"`` or ``"1/3 pass, 1 pending, 1 failed"``.
    """
    runs = list(state.current.values())
    if not runs:
        return ""
    total = len(runs)
    n_pass = sum(1 for r in runs if r.status == "pass")
    n_fail = sum(1 for r in runs if r.status in ("fail", "error"))
    n_pending = total - n_pass - n_fail
    parts = [f"{n_pass}/{total} pass"]
    if n_pending:
        parts.append(f"{n_pending} pending")
    if n_fail:
        parts.append(f"{n_fail} failed")
    return ", ".join(parts)
```

(`GateRun.status` is the existing property at `gate_ledger.py:32-34`,
`fields.get("status", "?")`.)

### 2. `.aitask-scripts/monitor/monitor_core.py` — `task_file_abs` + `GateSummaryCache`

**2a. Add an absolute path field to `TaskInfo`** (dataclass at line 1474). Append
a defaulted field so the one keyword-arg test stub
(`tests/test_kill_confirm_dialog.py:64`) keeps working unchanged and dataclass
field-ordering stays valid:

```python
@dataclass
class TaskInfo:
    ...
    plan_content: str | None
    task_file_abs: str = ""   # absolute path; task_file stays relative (display/tests)
```

In `_resolve` (the single real construction site, line 1813), set it from the
already-absolute `task_path`:

```python
        return TaskInfo(
            task_id=task_id,
            task_file=str(task_path.relative_to(root)),
            task_file_abs=str(task_path),
            ...
        )
```

(Keep `task_file` relative — `tests/test_task_info_cache_archived.py` asserts the
relative form and it is the display value.)

**2b.** `monitor_core.py` already inserts `lib/` onto `sys.path` (lines 34-39), so
add `import gate_ledger  # noqa: E402` with the other lib imports (~line 49). Add
the cache class next to `TaskInfoCache`:

```python
class GateSummaryCache:
    """Per-refresh compact gate-summary cache for the monitor TUIs.

    Mirrors the board's gate cache (aitask_board.TaskManager.gate_state_for):
    cleared each refresh cycle so a live-growing ledger updates, while a re-read
    is avoided when the same card is formatted twice in one frame. Fails closed
    to "" (no column) on any parse/IO error — a malformed ledger must never
    break the monitor. Keyed by resolved task-file path (already project-correct
    via TaskInfoCache, so cross-project safe).
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def clear(self) -> None:
        self._cache.clear()

    def summary_for(self, info: "TaskInfo | None") -> str:
        # Key + parse off the ABSOLUTE path (task_file_abs), never the relative
        # task_file — the relative form is cwd-dependent and wrong in
        # cross-session monitor mode.
        if info is None or not info.task_file_abs:
            return ""
        key = info.task_file_abs
        if key in self._cache:
            return self._cache[key]
        summary = ""
        try:
            # Cheap prefilter on the already-loaded body before the full parse;
            # the full state re-reads the file (matches the board: has_ledger
            # from content, state from filepath).
            if gate_ledger.has_gate_markers(info.body or ""):
                state = gate_ledger.read_task_gate_state(info.task_file_abs)
                summary = gate_ledger.compact_gate_summary(state)
        except Exception:
            summary = ""
        self._cache[key] = summary
        return summary
```

Re-export it from `monitor_shared.py` by adding `GateSummaryCache` to the
existing `from monitor_core import (… TaskInfo, TaskInfoCache, …)` re-export
block (lines 23-25).

### 3. `.aitask-scripts/monitor/monitor_app.py` — full monitor render + cache clear

- Add `GateSummaryCache` to the `from monitor.monitor_shared import (…)` list
  (lines 34-35).
- Instantiate beside the task cache (`monitor_app.py:455`):
  `self._gate_cache = GateSummaryCache()`.
- Clear it at the top of `_refresh_data` (`~line 684`), alongside the existing
  refresh bookkeeping: `self._gate_cache.clear()`.
- In `_format_agent_card_text` (lines 963-987), after the existing title line
  append a gate line only when non-empty:

```python
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if task_id:
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info:
                text += f"\n     [dim italic]t{task_id}: {info.title}[/]"
                gates = self._gate_cache.summary_for(info)
                if gates:
                    text += f"\n     [dim]gates: {gates}[/]"
        return text
```

(The card text is rebuilt every refresh — both the fast-path in-place update at
`monitor_app.py:1047-1050` and the full rebuild call `_format_agent_card_text`,
so the line stays current with no extra wiring.)

### 4. `.aitask-scripts/monitor/minimonitor_app.py` — general pane list only

**Scope decision (explicit — no "free both surfaces" assumption).** Minimonitor
has two agent surfaces: the **general pane list** (`_rebuild_pane_list` → cards
built via `_agent_card_text`, line 634) and the **docked followed-agent panel**
(`_maybe_build_own_agent_panel`, line 594, built via `_own_agent_identity_text`).
These do **not** share a renderer. The docked panel is built **once** and is
intentionally static — its docstring (lines 577-580) states it "is not rebuilt on
each refresh cycle and carries no live status badge (per the followed-agent UX)".
A *live* gate summary there would either contradict that design (force a refresh)
or be frozen at build time (misleading). So for v1 the gate summary is scoped to
the **general pane list only**; the docked followed-agent panel is intentionally
excluded.

Consequence to call out honestly: the general list *excludes* the followed agent
(line 611-615, `pane_id != own_pane_id`), so in **minimonitor** the followed
agent shows no gate line. That same agent **is** covered in full `ait monitor`
(which has no separate docked panel — every agent pane goes through
`_format_agent_card_text`). This matches the task's "where layout allows" /
"display-only v1" scope; covering the docked panel can be a later follow-up.

Layout: minimonitor already wraps the task title onto its own dim second line
(`minimonitor_app.py:549`); the gate summary is short and only appears for gated
tasks, so a conditional third dim line does not crowd the common (ungated) case.

- Add `GateSummaryCache` to the `from monitor.monitor_shared import (…)` list
  (lines 35-36).
- Instantiate beside the task cache (`minimonitor_app.py:188`):
  `self._gate_cache = GateSummaryCache()`.
- Clear it at the top of minimonitor's refresh loop (the `_refresh_*` method
  that already calls `update_session_mapping`, ~line 351-357).
- In `_agent_card_text` (general pane list only), inside the existing `if info:`
  block after the title line (`minimonitor_app.py:545-549`):

```python
            if info:
                title = info.title
                if len(title) > 30:
                    title = title[:29] + "…"
                line1 += f"\n  [dim]{title}[/]"
                gates = self._gate_cache.summary_for(info)
                if gates:
                    line1 += f"\n  [dim]gates: {gates}[/]"
```

Leave `_own_agent_identity_text` and `_maybe_build_own_agent_panel` untouched.

## Test plan

Two focused test files (testability-first: each new unit owns its test):

1. **`tests/test_gate_ledger_python_parser.py`** — add a `test_compact_gate_summary()`
   (registered in `main()`) exercising the pure formatter against in-memory
   `TaskGateState`s built via `read_task_gate_state` on fixture text:
   - no recorded runs → `""`;
   - all pass → `"2/2 pass"`;
   - mixed pass/pending (one gate recorded `status=pending` / a non-pass) →
     `"3/4 pass, 1 pending"`;
   - a failed gate → summary includes `"1 failed"`;
   - last-run-wins: a gate re-recorded pass after a fail counts once as pass.

2. **`tests/test_monitor_gate_summary.py`** (new, mirrors
   `tests/test_task_info_cache_archived.py` import style:
   `from monitor.monitor_shared import GateSummaryCache, TaskInfoCache`) —
   `GateSummaryCache` + the `task_file_abs` resolution, against on-disk task
   fixtures in a `tempfile` dir:
   - a task file with gate markers → expected compact summary;
   - a task file with no markers → `""` (no column);
   - `info=None` / empty `task_file_abs` → `""`;
   - fail-closed: a `task_file_abs` pointing at a missing/unreadable path → `""`
     (no exception);
   - caching: second `summary_for` for the same path does not re-read
     (monkeypatch `gate_ledger.read_task_gate_state` to count calls);
   - `clear()` empties the cache;
   - **cwd-independence (the must-fix):** resolve a `TaskInfo` via `TaskInfoCache`
     whose project root is the tempdir, then `os.chdir` to an *unrelated*
     directory (cwd ≠ project root) and assert `summary_for(info)` still returns
     the correct summary — proving it parses `task_file_abs`, not the relative
     `task_file`. Also assert `info.task_file_abs` is absolute and points inside
     the project root while `info.task_file` stays relative. (Restore cwd in a
     `finally`.)

## Verification

```bash
# pure parser + new formatter
python tests/test_gate_ledger_python_parser.py
# new cache unit
python tests/test_monitor_gate_summary.py
# full python suite (monitor apps compile + existing behavior intact)
bash tests/run_all_python_tests.sh
# syntax
python -m py_compile \
  .aitask-scripts/lib/gate_ledger.py \
  .aitask-scripts/monitor/monitor_core.py \
  .aitask-scripts/monitor/monitor_shared.py \
  .aitask-scripts/monitor/monitor_app.py \
  .aitask-scripts/monitor/minimonitor_app.py
```

Manual smoke (optional, covered by the aggregate manual-verification sibling
`t635` already tracks): launch `ait monitor` with an agent pane whose task has a
recorded gate ledger and confirm the `gates: …` line appears and updates; confirm
ungated tasks show no extra line.

Docs: this is a display-only TUI change with no new keybinding or command; the
comprehensive website sweep is owned by `t635_18` (which `depends:` on t635_10).
No incremental website page is added here — there is no new user-facing command
or shortcut surface to document, only an additional read-only line in an existing
card. (If desired during review, a one-line mention can be added to the monitor
TUI doc, but it is not required by the current-state rule.)

## Step 9 — Post-Implementation

Standard archival per `task-workflow` Step 9: merge approval, archive via
`./.aitask-scripts/aitask_archive.sh 635_10`, push. Child plan archives to
`aiplans/archived/p635/`.

## Risk

### Code-health risk: low
- Additive: one pure function in the shared parser, one defaulted `TaskInfo`
  field, one small cache class, and two conditional render lines guarded behind
  `has_gate_markers`. No existing code path changes behavior when a task has no
  ledger (the overwhelming common case). The new `TaskInfo.task_file_abs` field
  has a default and only one real construction site, so it cannot break existing
  `TaskInfo` consumers or the keyword-arg test stub. · severity: low ·
  → mitigation: none needed
- Cross-session path correctness: addressed directly — the cache parses the
  absolute `task_file_abs`, with an explicit cwd ≠ project-root test. Without
  this the summary would silently read the wrong file under multi-project
  monitoring. · severity: low (mitigated in-design) · → mitigation: covered by
  the cwd-independence test
- Per-refresh file read for gated panes every ~3s: bounded (a handful of agent
  panes), gated by the cheap `has_gate_markers` prefilter on already-loaded body
  text, and cached within a frame — mirrors the board's accepted cost.
  · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- Summary denominator choice (recorded runs vs declared gates): deriving over
  `state.current` is the only meaningful option today since `declared_gates` is
  empty framework-wide; matches the roadmap example `3/4 pass, 1 pending` and the
  board's `state.current`-based display. · severity: low · → mitigation: none needed
- Minimonitor coverage gap: the gate summary is scoped to the general pane list,
  so the followed agent (shown only in the static docked panel) has no gate line
  in minimonitor — an explicit, documented v1 scope choice; that agent is fully
  covered in `ait monitor`. · severity: low · → mitigation: optional follow-up to
  cover the docked panel
- Minimonitor layout: a conditional third line could crowd the ~40-col pane, but
  it appears only for gated tasks (rare today) and reuses the existing
  wrapped-line pattern. · severity: low · → mitigation: none needed

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned.
  1. `gate_ledger.compact_gate_summary(state)` — pure formatter over
     `state.current` (last-run-per-gate): `"N/M pass[, K pending][, J failed]"`,
     or `""` when no runs.
  2. `TaskInfo.task_file_abs` (absolute, defaulted to `""`) set in
     `TaskInfoCache._resolve`; `task_file` kept relative (display value + asserted
     by `test_task_info_cache_archived.py`). New `GateSummaryCache` in
     `monitor_core.py` — per-refresh, fail-closed to `""`, keyed/parsed off the
     **absolute** path; re-exported via `monitor_shared.py`.
  3. `monitor_app.py` — instantiate `_gate_cache`, `clear()` in `_refresh_data`,
     render a `gates: …` dim line in `_format_agent_card_text`.
  4. `minimonitor_app.py` — same wiring in the **general pane list**
     (`_agent_card_text`) only; the static docked followed-agent panel
     (`_own_agent_identity_text`) is intentionally left untouched.
- **Deviations from plan:** None.
- **Issues encountered:** The aggregate `tests/run_all_python_tests.sh` reports 3
  failures in `tests/test_brainstorm_node_action_modal.py`
  (`BrainstormApp._selection` AttributeError). These are **pre-existing,
  unrelated, and order-dependent**: `brainstorm_app.py` and the brainstorm tests
  were already uncommitted/dirty at session start (separate WIP), the test passes
  cleanly in isolation (`python -m unittest tests.test_brainstorm_node_action_modal`
  → 25/25 OK), and this task touches no brainstorm code. Not addressed here.
- **Key decisions:** Single derivation path — reuse `lib/gate_ledger.py` (the
  t635_8 shared parser) and mirror the board's per-refresh cache + fail-closed
  discipline rather than forking a second parser. The summary derives over
  recorded runs (`state.current`), not `declared_gates` (empty framework-wide
  today). The relative-vs-absolute `task_file` split was the key correctness fix
  (caught in plan review): a relative path is cwd-dependent and wrong under
  cross-session/multi-project monitoring — covered by a `cwd != project-root` test.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - `gate_ledger.compact_gate_summary(state)` is the reusable compact formatter;
    `monitor_core.GateSummaryCache` is the reusable monitor-side cache (both
    re-exported from `monitor_shared`). Future TUI gate displays should consume
    these, not re-parse.
  - `TaskInfo.task_file` is **relative** to the project root; use the new
    `TaskInfo.task_file_abs` whenever you need to open the task file from monitor
    code (the relative form breaks in cross-session mode).
  - Minimonitor's docked followed-agent panel is built once and static by design;
    covering it with live gate status is a deliberate v1 gap (optional follow-up).
- **Verification:** `python tests/test_gate_ledger_python_parser.py` (33/33);
  `python tests/test_monitor_gate_summary.py` (6/6);
  `python tests/test_task_info_cache_archived.py`, `tests/test_kill_confirm_dialog.py`
  (TaskInfo stub OK); `python -m py_compile` of all 5 touched modules + both test
  files.

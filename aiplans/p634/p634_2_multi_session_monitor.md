---
Task: t634_2_multi_session_monitor.md
Parent Task: aitasks/t634_multi_session_tmux_support.md
Sibling Tasks: aitasks/t634/t634_3_two_level_tui_switcher.md
Archived Sibling Plans: aiplans/archived/p634/p634_1_discovery_and_focus_primitives.md
Worktree: (none — working on current branch per profile `fast`)
Branch: main
Base branch: main
---

# p634_2 — Multi-session tmux monitor

## Context

`ait monitor` today observes panes in a single tmux session (`TmuxMonitor.session: str`). A user running multiple aitasks projects in parallel needs ONE monitor view that shows every code agent across every aitasks session on the current tmux server, tagged by project, with cross-session focus handoff.

**Core UX invariant:** when `multi_session` is active, every agent from every aitasks session appears in **one single unified list** — there is no per-session grouping, no separate sub-sections, no "expand to see other sessions" gesture. The whole point is at-a-glance status of ALL active code agents on the box. The session tag prefix on each row is the only thing that distinguishes which project a given agent belongs to. The same invariant applies to the minimonitor follow-up (t634_5).

**Config surface (v1):** none. No new YAML key. Multi-session is the built-in default behavior (code default `True`); the runtime `M` binding in monitor and minimonitor is the sole user-facing control for showing/hiding agents from other sessions. The discovery primitives already restrict to "aitasks-like" sessions (registry hit or pane cwd walk-up to `aitasks/metadata/project_config.yaml`), so the population is self-bounded — there is no allow-list, no exclude-list, no per-session knobs. If a user never opens a second aitasks project in tmux, multi-session behaves identically to single-session.

t634_1 landed the two shared primitives (`discover_aitasks_sessions()`, `switch_to_pane_anywhere(pane_id)`) plus the `AITASKS_PROJECT_<sess>` tmux-env registry already populated by `ait ide`. This task extends `TmuxMonitor` and `MonitorApp` to consume those primitives when opted in via `tmux.monitor.multi_session: true` in `project_config.yaml`, with a runtime `M` toggle on the monitor footer.

Single-session mode remains bit-identical to today.

## Files to modify

Core:
- `.aitask-scripts/monitor/tmux_monitor.py` — `TmuxPaneInfo` + `TmuxMonitor` constructor + pane discovery + switch/kill/companion helpers.
- `.aitask-scripts/monitor/monitor_app.py` — `MonitorApp` constructor + `on_mount` rename-dialog short-circuit + session bar + pane-card formatting + `M` binding.

Docs:
- `website/content/docs/tuis/monitor/reference.md` — document the `M` runtime toggle.

Tests:
- `tests/test_multi_session_monitor.sh` — new; mirrors `tests/test_multi_session_primitives.sh` layout.

No changes to `minimonitor_app.py`, `monitor_shared.py`, `aitask_ide.sh`, `seed/project_config.yaml`, or `aitasks/metadata/project_config.yaml` (no config key in this task; t634_5 will add the `M` binding to minimonitor).

---

## Step 1 — `TmuxPaneInfo` gains `session_name`

In `tmux_monitor.py` (around line 93):

```python
@dataclass
class TmuxPaneInfo:
    window_index: str
    window_name: str
    pane_index: str
    pane_id: str
    pane_pid: int
    current_command: str
    width: int
    height: int
    category: PaneCategory
    session_name: str = ""   # new; set by discovery, "" in legacy single-session paths
```

Default `""` preserves backward compatibility for any external caller. Every code path that constructs `TmuxPaneInfo` inside this file (`_parse_list_panes`, `discover_window_panes`) must populate it:

- `_parse_list_panes(stdout, session_name)` — new required parameter; callers pass the session being listed.
- `discover_window_panes(window_id)` — populate `session_name = self.session` (single-session helper; unaffected by multi mode).

## Step 2 — `TmuxMonitor` multi-session attributes

Extend `__init__` (line 115):

```python
def __init__(
    self,
    session: str,
    capture_lines: int = 200,
    idle_threshold: float = 5.0,
    exclude_pane: str | None = None,
    agent_prefixes: list[str] | None = None,
    tui_names: set[str] | None = None,
    multi_session: bool = True,        # default ON — see Context "Config surface"
):
    ...
    self.multi_session = multi_session                       # mutable; `M` toggle flips it
    self._sessions_cache: tuple[float, list[AitasksSession]] | None = None
    self._sessions_cache_ttl = 10.0   # seconds
```

Add a private helper `_discover_sessions_cached() -> list[AitasksSession]` that calls `discover_aitasks_sessions()` but memoizes for `_sessions_cache_ttl` seconds. Rationale (from review): discovery runs `tmux list-sessions` + one `list-panes -s` per session serially; caching for 10s avoids paying that cost every 1s refresh tick. Cache invalidation hooks: `M` toggle calls `self._sessions_cache = None` so the first post-toggle refresh re-queries immediately.

Import `AitasksSession` and `discover_aitasks_sessions` (and keep the existing `tmux_session_target`/`tmux_window_target` imports) from `agent_launch_utils`.

## Step 3 — Multi-session `discover_panes` / `discover_panes_async`

Single-session path unchanged. Add a multi branch. The set of sessions to enumerate is just whatever `discover_aitasks_sessions()` returns (already self-bounded to aitasks-like sessions), sorted by name for stable display:

```python
def _target_sessions(self) -> list[str]:
    """Resolve the list of tmux session names to enumerate in multi mode."""
    return sorted(s.session for s in self._discover_sessions_cached())
```

Async discovery aggregates concurrently via `asyncio.gather` and returns a SINGLE merged list (no per-session bucketing — the unified-list invariant from the Context section):

```python
async def discover_panes_async(self) -> list[TmuxPaneInfo]:
    if not self.multi_session:
        # existing single-session branch — unchanged
        rc, stdout = await _run_tmux_async([
            "list-panes", "-s", "-t", tmux_session_target(self.session),
            "-F", self._LIST_PANES_FORMAT,
        ])
        if rc != 0:
            return []
        return self._parse_list_panes(stdout, self.session)

    sessions = self._target_sessions()
    results = await asyncio.gather(*[
        _run_tmux_async([
            "list-panes", "-s", "-t", tmux_session_target(sess),
            "-F", self._LIST_PANES_FORMAT,
        ]) for sess in sessions
    ])
    panes: list[TmuxPaneInfo] = []
    for sess, (rc, stdout) in zip(sessions, results):
        if rc != 0:
            continue
        panes.extend(self._parse_list_panes(stdout, sess))
    panes.sort(key=lambda p: (p.session_name, p.window_index, p.pane_index))
    return panes
```

Sync `discover_panes` follows the same shape without `asyncio.gather` (serial).

`_parse_list_panes(stdout, session_name)` populates each constructed `TmuxPaneInfo(..., session_name=session_name)` and caches into `_pane_cache` keyed by `pane_id` (globally unique — no change).

Companion filter (`_is_companion_process`) is PID-based → already cross-session correct.
`exclude_pane` check is pane-id-based → cross-session correct.

## Step 4 — Cross-session safety for `switch_to_pane` / `find_companion_pane_id` / `kill_agent_pane_smart`

**`switch_to_pane(pane_id, prefer_companion)`** (line 373). Branch on pane session:

```python
def switch_to_pane(self, pane_id: str, prefer_companion: bool = False) -> bool:
    pane = self._pane_cache.get(pane_id)
    if pane is None:
        return False
    # Cross-session: teleport via the shared primitive.
    if self.multi_session and pane.session_name and pane.session_name != self.session:
        return switch_to_pane_anywhere(pane_id)
    # Same-session: existing path (companion-aware).
    target_session = pane.session_name or self.session
    subprocess.run(
        ["tmux", "select-window", "-t",
         tmux_window_target(target_session, pane.window_index)],
        capture_output=True, timeout=5,
    )
    target_pane = pane_id
    if prefer_companion:
        companion = self.find_companion_pane_id(pane.window_index, target_session)
        if companion:
            target_pane = companion
    result = subprocess.run(
        ["tmux", "select-pane", "-t", target_pane],
        capture_output=True, timeout=5,
    )
    return result.returncode == 0
```

Import `switch_to_pane_anywhere` at top of file. Preserve companion UX intra-session; teleport only when truly cross-session.

**`find_companion_pane_id(window_index, session=None)`** — add a `session` parameter defaulting to `self.session`. Build the window target with the passed session so companion lookup works for cross-session panes (caller in the same-session branch above already passes `target_session`).

**`kill_agent_pane_smart(pane_id)`** (line 455). Line 468 builds `window_target` from `self.session`; that's the bug the reviewer flagged. Change to:

```python
target_session = pane.session_name or self.session
window_target = tmux_window_target(target_session, pane.window_index)
```

`kill_pane` and `kill_window` already operate by pane_id → no change.

## Step 5 — `MonitorApp` wiring

Constructor (`monitor_app.py:459`): add `multi_session: bool = True` param; store as `self._multi_session`. No config read — the built-in default is the starting state; the `M` binding is the sole user control.

`on_mount()`: wrap the `SessionRenameDialog` guard in `if not self._multi_session and self._expected_session and ...`. In multi mode, skip straight to `self._start_monitoring()`.

`_start_monitoring()`: pass the new flag to `TmuxMonitor(...)`:

```python
self._monitor = TmuxMonitor(
    session=self._session,
    capture_lines=self._capture_lines,
    idle_threshold=self._idle_threshold,
    multi_session=self._multi_session,
    **kwargs,
)
```

### Session bar

Replace `_rebuild_session_bar()`:

```python
def _rebuild_session_bar(self) -> None:
    total = len(self._snapshots)
    bar = self.query_one("#session-bar", SessionBar)
    auto_tag = "  [bold yellow][AUTO][/]" if self._auto_switch else ""
    if self._monitor and self._monitor.multi_session:
        sessions = {s.pane.session_name for s in self._snapshots.values() if s.pane.session_name}
        attached = self._read_attached_session() or self._session
        bar.update(
            f"tmux Monitor — {len(sessions)} session{'s' if len(sessions) != 1 else ''} "
            f"· {total} pane{'s' if total != 1 else ''} · multi "
            f"(attached: {attached})"
            f"{auto_tag}  [dim]Tab: switch panel · M: toggle multi[/]"
        )
    else:
        bar.update(
            f"tmux Monitor — session: {self._session} "
            f"({total} pane{'s' if total != 1 else ''})"
            f"{auto_tag}  [dim]Tab: switch panel[/]"
        )
```

Add `_read_attached_session()` helper that runs `tmux display-message -p '#S'` (reuse the existing `_detect_tmux_session` pattern at line 1588 but don't require `TMUX` env, since in multi mode the attached session may have changed after a teleport).

### Pane card formatting

The existing `_rebuild_pane_list()` structure stays exactly as-is: ONE `"CODE AGENTS (N)"` section with all agents in a single sorted list, ONE `"OTHER (N)"` section. No per-session sub-headers, no nesting, no separators between projects. This preserves the at-a-glance invariant: every active code agent on the box, in one column, ordered for stable scanning.

In multi mode, prepend a session tag built from a `{session_name: project_name}` lookup rebuilt once per refresh. Implementation: in `_rebuild_pane_list()`, before formatting cards, call `session_tags = self._build_session_tags()`:

```python
def _build_session_tags(self) -> dict[str, str]:
    if not (self._monitor and self._monitor.multi_session):
        return {}
    return {s.session: s.project_name
            for s in self._monitor._discover_sessions_cached()}
```

Pass `session_tags` through to the card formatters and prepend `[{tag}] ` when non-empty:

```python
def _format_agent_card_text(self, snap: PaneSnapshot, session_tags: dict[str, str]) -> str:
    tag = ""
    if session_tags:
        name = session_tags.get(snap.pane.session_name, snap.pane.session_name or "?")
        tag = f"[magenta][{name}][/] "
    ...  # existing logic, inserting {tag} after the leading space
```

Single-session unchanged (`session_tags={}` → `tag=""`).

### `M` runtime toggle

This is the keyboard shortcut for the "show / hide agents from other sessions" feature — paired with the persistent `tmux.monitor.multi_session` config key. Both layers exist for the same flag: config is the persistent default; `M` is the instant flip without leaving the TUI.

Add to `BINDINGS`:

```python
Binding("M", "toggle_multi_session", "Multi"),
```

Action:

```python
def action_toggle_multi_session(self) -> None:
    if self._monitor is None:
        return
    self._monitor.multi_session = not self._monitor.multi_session
    self._monitor._sessions_cache = None   # force immediate rediscover
    state = "ON" if self._monitor.multi_session else "OFF"
    self.notify(f"Multi-session {state}", timeout=3)
    self.call_later(self._refresh_data)    # reflect change on next paint
```

In-memory only; not written to config (per CLAUDE.md: "No auto-commit/push of project-level config from runtime TUIs"). To make a change persistent, the user edits `project_config.yaml` (or, once t634_4 ships, uses the `ait settings` toggle).

### `main()` threading

No changes at `monitor_app.py:1648` — `multi_session` is not sourced from config. The `MonitorApp` default (`True`) is what users get on every invocation; they flip it at runtime with `M` as needed. The existing `MonitorApp(...)` call site remains unchanged.

## Step 6 — Website docs

Edit `website/content/docs/tuis/monitor/reference.md`:

- Add a short "Multi-session view" subsection describing the feature and the `M` keyboard shortcut. Content: "By default the monitor shows every active code agent across every aitasks session on this tmux server in a single unified list — sessions are auto-discovered via the `AITASKS_PROJECT_<session>` registry (set by `ait ide`) and pane cwd walk-up. Press `M` to toggle to a single-session view (showing only agents in the currently-attached session). The toggle lives for the current monitor session; there is no persistent config key."
- Add `M` to the keybindings reference table (alongside existing `s`, `i`, `r`, `k`, etc.).
- **Do NOT** add a config-table row — there is no YAML key for this feature.

Per CLAUDE.md docs rule: current-state only — describe the feature positively, no version history or migration notes.

## Step 7 — Tests (`tests/test_multi_session_monitor.sh`)

Mirror the layout of `tests/test_multi_session_primitives.sh`:

Tier 1 (no tmux required, mock-based, always run):

1. `TmuxPaneInfo` has `session_name` field with default `""` (unittest via `dataclasses.fields`).
2. `TmuxMonitor(multi_session=True)`: mock `discover_aitasks_sessions()` → two fake sessions; mock `subprocess.run` for `list-panes -s` → returns different pane sets per session. Assert:
   - `discover_panes()` returns the union, each pane has correct `session_name`.
   - Result is sorted by `(session_name, window_index, pane_index)`.
3. `TmuxMonitor(multi_session=False).discover_panes()`: mock asserts exactly ONE `list-panes -s -t =<self.session>` call (regression: no multi-session code path touches single-session).
4. `switch_to_pane(cross_session_pane_id)` in multi mode: mock `switch_to_pane_anywhere`; assert it is called exactly once, and `select-window`/`select-pane` are NOT issued directly.
5. `switch_to_pane(same_session_pane_id)` in multi mode: mock asserts the existing `select-window`+`select-pane` path runs (no `switch-client`), preserving companion UX.
6. `kill_agent_pane_smart` on a cross-session pane: mock asserts the `list-panes` call uses `tmux_window_target(pane.session_name, ...)`, NOT `self.session`.
7. `_is_companion_process` still filters monitor/minimonitor PIDs in multi mode (regression).
8. `exclude_pane` still filters the current pane id in multi mode (regression).
9. `MonitorApp(multi_session=True)` (default) has the `M` binding registered and its `action_toggle_multi_session` handler flips `self._monitor.multi_session` and invalidates the session cache. Mock-based sanity check; no Textual runtime needed.

Tier 2 (gated on `command -v tmux`, isolated via `TMUX_TMPDIR`):

11. Create two fake aitasks sessions `msA`/`msB` in temp dirs containing `aitasks/metadata/project_config.yaml`. Launch dummy `sleep` panes in each. Construct real `TmuxMonitor(multi_session=True)`. Assert `discover_panes()` returns panes from both, correctly tagged.
12. Kill session `msA` between refreshes. Assert `discover_panes()` returns only `msB` (cache invalidated + stale pane ids dropped from `_pane_cache`).

Skip-on-no-tmux pattern (copy from `test_multi_session_primitives.sh`):

```bash
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — Tier 2 skipped"
    # summary + exit 0
fi
```

## Out of scope (deferred to follow-up child tasks under t634)

This task ships multi-session behavior in the main monitor — the `TmuxMonitor` / `MonitorApp` changes, the `M` runtime toggle, and the `ait monitor` reference docs. Two follow-ups, each tracked as its own child task created in **Step 8** below:

- **t634_4 — Minimonitor multi-session awareness.** The per-window minimonitor companion (`minimonitor_app.py`) is still session-local. Teaching it to show every active code agent across every aitasks session in the same unified list (and adding the matching `M` keyboard shortcut) belongs in a dedicated task. Per the t634_2 task description, `action_switch_to_monitor()`'s env-var dance stays per-session; cross-session focus is the main monitor's job via `switch_to_pane_anywhere`.
- **t634_5 — Documentation polish for `ait monitor`.** Once t634_4 (minimonitor) lands, the website docs need a refresh to describe the full cross-TUI multi-session story end-to-end. The subsection added in Step 6 of THIS task covers only the main monitor's `M` binding — it does not describe the minimonitor counterpart or cross-TUI handoff.

Also explicitly out of scope:

- **`tmux.monitor.multi_session` YAML key** — deliberately not added. The `M` runtime binding is the sole user control; there is no persistent config. This keeps the config surface minimal and avoids the settings-UI work that a config key would imply.
- **`ait settings` integration** — with no config key, nothing to expose.
- **`monitor_shared.py` helper** — no helper needed; session-tag formatting is inline in `monitor_app.py`.

## Verification

Automated:

```bash
bash tests/test_multi_session_monitor.sh
shellcheck tests/test_multi_session_monitor.sh
python3 -c 'import ast; ast.parse(open(".aitask-scripts/monitor/tmux_monitor.py").read())'
python3 -c 'import ast; ast.parse(open(".aitask-scripts/monitor/monitor_app.py").read())'
```

Regression: the primitives test must keep passing:

```bash
bash tests/test_multi_session_primitives.sh
```

Manual (optional sanity — covered more broadly by the parent task t634's aggregate manual-verification sibling if one is filed):

1. With only ONE aitasks tmux session running, open `ait monitor`. It behaves visually like today (one session's worth of agents in the list). Title bar reads `"tmux Monitor — 1 session · N panes · multi (attached: <sess>)"`; each row is tagged with the single session's project name.
2. Start a second aitasks project in a new tmux session (via `ait ide` from the second repo — registers `AITASKS_PROJECT_<sess>`). Refresh: `ait monitor` now shows both projects' agents in a SINGLE list, each row tagged with its project name. Title bar shows `"2 sessions · N panes · multi"`.
3. Press Enter on a cross-project pane → client teleports via `switch_to_pane_anywhere`; focus lands correctly.
4. Press `M` → notification "Multi-session OFF". Pane list shrinks to only the attached session's agents. Press `M` again → multi view restored.
5. `SessionRenameDialog` does NOT fire in multi mode, even if the attached session name doesn't match `tmux.default_session`. Toggle to single-session with `M` → the rename prompt still does not fire (it only matters at `on_mount`).

## Gotchas to address during implementation

- `display-message -p '#S'` requires a client to be attached; guard against empty output and fall back to `self._session`.
- `_pane_cache` stale-pruning on session disappearance already works because `_clean_stale` compares against the current snapshot keys — verify by adding the Tier 2 test for killed-session pane eviction.
- `_consume_focus_request` / `_clear_focus_request` in `monitor_app.py` read `AITASK_MONITOR_FOCUS_WINDOW` from `self._session` only. Per the review, this is intentional — minimonitor focus handoff is scoped to the session it lives in. Add a short code comment to prevent future confusion, but do not change behavior.
- `_detect_tmux_session` at line 1588 requires `TMUX` env; the multi-mode title bar needs the CURRENT attached session even after teleport — use a separate helper that reads `display-message` unconditionally.
- When `multi_session=True` but tmux has zero aitasks sessions, `discover_panes()` returns `[]`. UI should render "0 sessions · 0 panes · multi" without crashing.

## Step 8 — Create follow-up child tasks (t634_4, t634_5)

Before committing the main implementation, seed the two follow-up tasks as explicit deliverables of this session. Each is created with the Batch Task Creation Procedure (`task-creation-batch.md`) with mode `child`, parent `634`. The task content below is the brief used to seed each child file — full descriptions are written at creation time, not stored long-form in this plan.

### t634_4 — Minimonitor multi-session awareness

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --parent 634 \
  --name minimonitor_multi_session \
  --priority medium --effort medium \
  --issue-type feature \
  --labels tmux,aitask_monitormini \
  --depends t634_2 \
  --desc-file <tmp_desc_4>
```

`<tmp_desc_4>` brief:

- **Context:** t634_2 added multi-session awareness to the main monitor and the `M` runtime toggle. The per-window minimonitor (`.aitask-scripts/monitor/minimonitor_app.py`) is still session-local.
- **Core requirement (matches t634_2):** when multi_session is active, the minimonitor MUST show every active code agent across every aitasks session in a single unified list (not a counter, not "expand to view"). Same at-a-glance invariant as the main monitor; the minimonitor is just the more compact, per-window incarnation of the same view.
- **Required `M` keyboard shortcut:** mirror the main-monitor `M` binding added in t634_2 — instant toggle of the multi_session flag for this minimonitor instance, in-memory only, with a `notify(...)` confirmation. Same key, same semantics, so users learn one binding for both TUIs. No config key (matches t634_2); default is `multi_session=True`.
- **Key files:** `.aitask-scripts/monitor/minimonitor_app.py` (route discovery through the same multi-session `TmuxMonitor` path added in t634_2, format rows with the session tag prefix, register the `M` binding and toggle action). Reuse the `_build_session_tags` helper added on `MonitorApp` — extract to `monitor_shared.py` if both TUIs need it.
- **Open implementation question** (decide during planning, not at task-create time):
  - Does pressing `M` in minimonitor → switch to main monitor implicitly enable `multi_session` on the main monitor instance if currently off, or only switch focus? (Recommend: only switch focus; main-monitor toggle is its own action.)
- **Dependency:** Blocked on t634_2 (needs `TmuxPaneInfo.session_name`, the cached `discover_aitasks_sessions()` accessor, and the `TmuxMonitor.multi_session` attribute).

### t634_5 — Documentation polish for `ait monitor`

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --parent 634 \
  --name docs_multi_session_polish \
  --priority low --effort low \
  --issue-type documentation \
  --labels website,documentation \
  --depends t634_4 \
  --desc-file <tmp_desc_5>
```

`<tmp_desc_5>` brief:

- **Context:** t634_2 added a short "Multi-session view" subsection to `website/content/docs/tuis/monitor/reference.md` covering the main monitor's `M` binding. Once t634_4 (minimonitor) lands, the docs need a refresh to describe the full cross-TUI story end-to-end.
- **Key files:**
  - `website/content/docs/tuis/monitor/reference.md` — expand the multi-session section to cover the minimonitor counterpart and any handoff behavior between the two TUIs.
  - Any cross-references in `website/content/docs/workflows/` that mention single-session monitor assumptions.
- **Per CLAUDE.md docs rule:** current-state only — no version history, no "previously" callouts.
- **Dependency:** Blocked on t634_4 so the documented behavior matches what shipped.

These two creations run before implementation begins (as part of this planning step), so the follow-ups are committed alongside the t634_2 plan and won't get lost if the main work takes multiple sessions. Verify each child file landed and was committed by `aitask_create.sh` (it commits via `./ait git` automatically) before moving on.

## Step 9 — Post-implementation

Per the shared workflow:

- `aitask-pick` Step 8 — present `git status` / `git diff --stat` for review. On "Commit changes", commit code files under `.aitask-scripts/`, `website/`, and `tests/` with `feature: Add multi-session tmux monitor (t634_2)`. Commit the plan file separately via `./ait git`.
- `aitask-pick` Step 8c — offer a manual-verification follow-up task if the user wants TUI-flow coverage that automated tests can't exercise.
- `aitask-pick` Step 9 — archive t634_2 (child). t634_4 and t634_5 remain pending (t634_5 depends on t634_4). Parent t634 auto-archives once all non-archived children (t634_3 plus the two new ones) complete.

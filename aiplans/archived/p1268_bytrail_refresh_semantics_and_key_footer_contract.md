---
Task: t1268_bytrail_refresh_semantics_and_key_footer_contract.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1268 — By-Trail refresh semantics and key/footer contract

## Context

The board's By-Trail view (`.aitask-scripts/board/aitask_board.py`) shows task
statuses that cannot be refreshed from inside the view, and its footer
advertises actions that do something else. Observed: a task rendered `Ready`
while its file on disk had said `Implementing` for hours, with no key able to
fix it.

Verified live during planning (2026-07-27):

- `refresh_board()` (:5790) unconditionally calls `manager.refresh_git_status()`
  (:971 — `git status --porcelain`, 5 s timeout) and, with `refresh_locks=True`,
  `manager.refresh_lock_map()` (:993 — `aitask_lock.sh --list`, 10 s timeout),
  **both synchronous on the UI thread**. `_refresh_board_data()` (:5765) uses
  exactly that path, so it is *not* a zero-subprocess route.
- **But the By-Trail view consumes none of that state.** Every reader of
  `modified_files` / `lock_map` / `xdep_status_cache` lives in `TaskCard.compose`
  (:1561-1634), which `TrailTaskCard.compose` (:1858) and `TrailGhostCard.compose`
  (:1902) **fully override**. So a trail-only render can skip the git/lock work
  with zero behavioural loss — it removes work the view never used.
- `manager.load_tasks()` (:834-857) is pure file I/O — no subprocess.
- `aitask_trail_gather.sh drift` is read-only and ran in **0.51 s**, emitting
  per-task `DRIFT:<code>|<task_ref>|<detail>` lines that reach only the subtitle
  (:5741) and `TrailDetailScreen` (:2272) — never the owning card.
- `r` instead launches `/aitask-trail --refresh` (`_launch_trail`, :7145) on
  `claudecode/opus5`, re-authoring the whole trail JSON.
- `check_action` (:5495) has `bytrail` cases for six action groups but none for
  `commit_all`, `sync_remote`, or `refresh_board`; `action_sync_remote` returns
  at :7258 before `_run_sync`, so `ait sync` is unreachable from By-Trail.
- `_trail_versions` (:665) returns `[]` on **every** failure (non-zero exit,
  timeout, missing script) — indistinguishable from a real listing.
- `manager.auto_refresh_minutes` defaults to `0` and this repo's
  `board_config.json` has no `settings` block, so `_auto_refresh_tick` never runs.

**Outcome:** an escalating, honestly-labelled refresh ladder in By-Trail, drift
reasons on the owning cards, and a footer that matches what the keys do.

## Design decisions

### Footer mechanism (AC6): duplicate keys, distinct actions, `check_action` gating

Verified against installed Textual 8.2.7 on both paths:

- **Dispatch** (`app.py:3983-3987`): `_check_bindings` walks *every* binding for
  a key in declaration order; `run_action` (`app.py:4245`) returns `False` when
  `check_action` is falsy, so it falls through to the next binding for that key.
- **Footer** (`screen.py:471-479`): `active_bindings` does `continue` on
  `action_state is False`, so a hidden binding yields its key slot to the next
  one, which carries its own `description`.

The board **never calls `refresh_bindings()`**, and Textual's `Footer` only
relabels on `bindings_updated_signal` (`_footer.py:330`) — so it must be added.
The registry keys defaults on `(scope, action)` (`keybinding_registry.py:135`),
so two actions sharing `r` is fine and both stay independently rebindable.

### Key ladder in By-Trail

| Key | Outside By-Trail | In By-Trail | Cost |
|---|---|---|---|
| `r` | `refresh_board` "Refresh" | `trail_refresh_local` "Refresh" | **0 subprocess**, instant |
| `d` | *(hidden)* | `trail_refresh_drift` "Freshness" | artifact get + drift, async |
| `R` | *(hidden)* | `trail_refresh_agent` "Agent Refresh" | opus5 agent, minutes |
| `s` | `sync_remote` "Sync" | `trail_select` "Select Trail" | discovery rescan |
| `S` | *(hidden)* | `trail_sync` "Sync" | `ait sync` |
| `C` | `commit_all` "Commit All" | **hidden** | — |

`R`, `S`, `d` are free at app level (they exist only inside `TaskDetailScreen`,
:4093-4098, a modal with its own binding namespace).

### `C` Commit All (AC7): hidden, not scoped

`get_modified_tasks()` (:1236) scans `task_datas` + `child_task_datas` repo-wide,
so `C` in By-Trail commits non-member tasks. A trail is a *reading* projection,
not an ownership boundary — hiding matches every other `bytrail` gate already in
`check_action`. Rationale goes in the code.

## Changes — `.aitask-scripts/board/aitask_board.py`

### 1. Trail-only render path (fixes AC1 and the drift-callback freeze)

The single most important change. New method, used by every By-Trail refresh:

```python
def _rerender_trail(self, refocus_filename: str = ""):
    """Re-mount the By-Trail lanes from in-memory state only.

    Deliberately does NOT call refresh_git_status() / refresh_lock_map() /
    xdep_status_cache.clear(): TrailTaskCard and TrailGhostCard fully override
    TaskCard.compose and read none of that state (the only readers are at
    TaskCard.compose :1561-1634). Routing By-Trail through the generic
    refresh_board() would block the UI thread on `git status` (5s timeout) and
    `aitask_lock.sh --list` (10s timeout) to produce an identical render."""
    if self.base_filter != "bytrail":
        return
    refocus_col_id = self._get_focused_col_id() or ""
    container = self.query_one("#board_container")
    container.remove_children()
    self._render_bytrail(container)
    self.call_after_refresh(self.apply_filter)
    self._queue_refocus(refocus_filename, refocus_col_id)
```

`_render_bytrail` already calls `_refresh_subtitle()` on every path.

### 2. The three refresh actions (AC1, AC2, AC4)

`action_refresh_board` (:5777) loses its `bytrail` branch — `r` outside By-Trail
is unchanged, and inside it never fires (gated). New actions:

```python
def action_trail_refresh_local(self):
    """`r` in By-Trail: reload task files from disk and re-project the CACHED
    trail document. Zero subprocesses, no agent, no artifact read (AC1)."""
    if self._modal_is_active():
        return
    focused = self._focused_card()
    refocus = focused.task_data.filename if focused else ""
    self.manager.load_tasks()        # pure file I/O
    self._rerender_trail(refocus)

def action_trail_refresh_drift(self):
    """`d` in By-Trail: re-fetch the stored artifact and re-run the read-only
    drift check (AC2). Never writes the artifact."""
    if self._modal_is_active():
        return
    self._reload_active_trail()

def action_trail_refresh_agent(self):
    """`R` in By-Trail: launch /aitask-trail --refresh (AC4)."""
    if self._modal_is_active() or not self.active_trail_handle:
        return
    handle_id = self.active_trail_handle
    if handle_id.startswith("art:"):
        handle_id = handle_id[len("art:"):]
    # The watch is armed inside _launch_trail's result callback, on a
    # CONFIRMED launch only -- not here. _launch_trail merely pushes a
    # confirmation dialog (:7182); arming at this point would orphan a watch
    # on cancel, burn the tick ceiling while the dialog sits open, and let an
    # unrelated version bump stop the watch before the agent ever writes.
    self._launch_trail(["--refresh", self.active_trail_handle], handle_id,
                       watch_handle=self.active_trail_handle)
```

`_reload_active_trail` re-fetches the blob off the UI thread, mirroring the
existing `_trail_drift_worker` supersession pattern:

```python
def _reload_active_trail(self):
    if self.base_filter != "bytrail" or not self.active_trail_handle:
        return
    self._trail_gen += 1
    self._trail_drift = None
    self._refresh_subtitle()          # back to "⟳ checking freshness…"
    self._trail_reload_worker(self._trail_gen, self.active_trail_handle)

@work(thread=True)
def _trail_reload_worker(self, gen: int, handle: str):
    doc, error, versions = load_trail_blob(handle)
    self.app.call_from_thread(self._on_trail_reload, gen, handle,
                              doc, error, versions)

def _on_trail_reload(self, gen, handle, doc, error, versions):
    if (gen != self._trail_gen or self.base_filter != "bytrail"
            or handle != self.active_trail_handle):
        return
    self._trail_doc = doc
    self._trail_error = error
    self._trail_versions_fallback = list(versions)
    # The discovery cache still holds the OLD doc for this handle; drop it so a
    # later `s` re-select cannot resurrect it.
    self._trail_infos = None
    self._rerender_trail()
    if doc is not None and not error:
        self._start_trail_drift()
    self._refresh_subtitle()
```

`load_trail_blob` (:680) is the existing targeted loader — no full
`discover_trails` rescan.

### 3. Artifact-version watch — automatic pickup after the agent finishes (AC5)

`on_trail_result` fires when the *launch dialog* closes; a tmux-launched agent
finishes minutes later. A bounded version watch closes that gap.

**Armed only on a confirmed launch.** `_launch_trail` (:7145) merely pushes an
`AgentCommandScreen` (:7182); the agent runs inside `on_trail_result` and only
for `result == "run"` or a `TmuxLaunchConfig`. Arming before that would orphan a
watch when the user cancels, consume the tick ceiling while the dialog sits open,
and let an unrelated version bump stop the watch before the agent ever writes.
So `_launch_trail` grows an optional `watch_handle` and arms inside the callback:

Capturing the baseline and *installing* the watch are separate steps: the
baseline is read before the launch call (the agent may write the moment it
starts), but the watch is installed only once the launch actually succeeded.

```python
def _launch_trail(self, op_args, window_suffix, watch_handle: str = ""):
    ...
    def on_trail_result(result):
        if result == "run":
            # Baseline BEFORE dispatch; watch installed only after it.
            baseline = _trail_versions(watch_handle) if watch_handle else None
            self.run_dialog_command(screen.full_command)
            if watch_handle:
                self._install_trail_watch(watch_handle, baseline)
            self._after_trail_launch()
            return

        if isinstance(result, TmuxLaunchConfig):
            baseline = _trail_versions(watch_handle) if watch_handle else None
            _pid, err = launch_in_tmux(screen.full_command, result)
            if err:
                # launch_in_tmux returns (pane_pid, error): a non-None error
                # means the agent NEVER started. Install nothing, and leave a
                # watch from an earlier launch untouched. reload=False: no
                # agent ran, so there is nothing new to fetch.
                self.notify(err, severity="error")
                self._after_trail_launch(reload=False)
                return
            if result.new_window:
                maybe_spawn_minimonitor(result.session, result.window)
            if watch_handle:
                self._install_trail_watch(watch_handle, baseline)
            self._after_trail_launch()
            return

        # Cancelled / dismissed: nothing launched, and THIS dialog armed
        # nothing. A watch from an earlier still-running agent MUST survive —
        # stopping it here would strand that agent's eventual write. Also skip
        # the artifact re-fetch: nothing can have changed because of a cancel.
        self._after_trail_launch(reload=False)

def _after_trail_launch(self, reload: bool = True):
    """Post-dialog refresh. Immediate pickup for the synchronous `run` case;
    the installed watch covers the async tmux case."""
    if self.base_filter == "bytrail" and self.active_trail_handle:
        if reload:
            self._reload_active_trail()
        else:
            self._rerender_trail()
    else:
        self.refresh_board()
```

The immediate `_reload_active_trail()` catches the synchronous in-dialog `run`
case; the armed watch catches the tmux case. They are independent by design,
which is exactly why the watch cannot key off `_trail_gen` (see below).

State in `__init__` (:5480 block) and module constants:

```python
TRAIL_WATCH_INTERVAL = 20      # seconds between polls
TRAIL_WATCH_MAX_TICKS = 90     # ~30 min ceiling, then give up

self._trail_watch_timer = None
self._trail_watch_handle = ""
self._trail_watch_baseline: list | None = None
self._trail_watch_ticks = 0
self._trail_watch_busy = False
self._trail_watch_gen = 0      # dedicated supersession token (NOT _trail_gen)
```

**Why a dedicated token.** Stopping the watch cancels the timer but cannot cancel
an in-flight `_trail_watch_worker` thread, and `_trail_gen` does not change when a
watch is re-armed for the *same* handle — so a stale callback would satisfy every
handle/view guard and corrupt the newer watch (clearing its busy flag, or
comparing its own stale listing against the new baseline and firing a false
"changed"). `_trail_watch_gen` is bumped on **every** start and **every** stop,
and is checked *before* any state mutation:

```python
def _stop_trail_watch(self):
    self._trail_watch_gen += 1          # invalidate any in-flight worker
    if self._trail_watch_timer is not None:
        self._trail_watch_timer.stop()
    self._trail_watch_timer = None
    self._trail_watch_handle = ""
    self._trail_watch_baseline = None
    self._trail_watch_ticks = 0
    self._trail_watch_busy = False

def _install_trail_watch(self, handle: str, baseline):
    """Install (or replace) the watch for `handle`, keyed to `baseline`.

    Called ONLY after a launch actually succeeded — never from the cancel or
    tmux-failure paths, which must leave an earlier watch alone."""
    if not baseline:
        # Unreadable reference point (see _trail_versions: [] on every
        # failure). Returning BEFORE _stop_trail_watch is deliberate — tearing
        # down first would destroy a still-valid watch from an earlier
        # in-flight refresh and put nothing in its place. Better to keep
        # watching the older baseline than to watch nothing.
        return
    self._stop_trail_watch()            # bumps the token, kills the old timer
    self._trail_watch_gen += 1          # this watch's own token
    self._trail_watch_handle = handle
    self._trail_watch_baseline = baseline
    self._trail_watch_ticks = 0
    self._trail_watch_busy = False
    self._trail_watch_timer = self.set_interval(
        TRAIL_WATCH_INTERVAL, self._trail_watch_tick, name="trail_watch")

def _trail_watch_tick(self):
    handle = self._trail_watch_handle
    if (self.base_filter != "bytrail" or not handle
            or handle != self.active_trail_handle):
        self._stop_trail_watch()
        return
    self._trail_watch_ticks += 1
    if self._trail_watch_ticks > TRAIL_WATCH_MAX_TICKS:
        self._stop_trail_watch()
        return
    if self._trail_watch_busy:          # a slow poll is still in flight
        return
    self._trail_watch_busy = True
    self._trail_watch_worker(self._trail_watch_gen, handle)

@work(thread=True)
def _trail_watch_worker(self, watch_gen: int, handle: str):
    versions = _trail_versions(handle)
    self.app.call_from_thread(self._on_trail_watch, watch_gen, handle, versions)

def _on_trail_watch(self, watch_gen, handle, versions):
    # Token check FIRST: a stale callback must not clear the newer watch's
    # busy flag or be compared against the newer watch's baseline.
    if watch_gen != self._trail_watch_gen:
        return
    self._trail_watch_busy = False
    if (self.base_filter != "bytrail" or handle != self.active_trail_handle
            or handle != self._trail_watch_handle):
        self._stop_trail_watch()
        return
    # _trail_versions() returns [] for EVERY failure (non-zero exit, timeout,
    # missing script) — indistinguishable from a real listing. Treat it as
    # "no signal, poll again", never as a version change.
    if not versions:
        return
    if versions == self._trail_watch_baseline:
        return
    self._stop_trail_watch()
    self.notify("Trail artifact updated — reloading")
    self._reload_active_trail()
```

Invariants, each pinned by a test:

- **Installed only after a launch actually succeeded** — baseline read before the
  launch call, watch installed after it returns successfully. A cancel or a
  `launch_in_tmux` error installs nothing and leaves an earlier watch running.
- **No overlapping workers** — `_install_trail_watch` stops first (mirroring
  `_start_auto_refresh_timer` :5691); `_trail_watch_busy` skips a tick while a
  poll is in flight; `_trail_watch_gen` retires any thread that outlives its watch.
- **Callbacks guarded** by the watch token (checked first), `base_filter`, the
  active handle, and the watch handle.
- **Stops on** version change, leaving By-Trail (`_set_base_filter`), trail change
  (`_activate_trail`), tick ceiling, cancellation, and app exit (Textual stops App
  timers on teardown; the explicit stops cover every in-session path).
- **Transient failure ⇒ retry** — an empty listing returns without stopping.
- **Independent of `_trail_gen`** — `_reload_active_trail()` bumps `_trail_gen`
  and must not disarm a watch that is still waiting for the agent's write.

### 4. Drift reasons onto cards (AC3)

Pure module-level helpers next to `_trail_badge_text` (:1836):

```python
def trail_drift_by_ref(reasons) -> dict:
    """Group drift reasons by owning task ref.

    Trail-level reasons (task_ref "-", e.g. input_missing) and reasons naming a
    non-member task (new_related_task) have no owning card; they are dropped
    here and stay visible in the subtitle count and the detail modal."""
    by_ref: dict = {}
    for code, task_ref, detail in reasons or []:
        if not task_ref or task_ref == "-":
            continue
        by_ref.setdefault(str(task_ref), []).append((code, task_ref, detail))
    return by_ref


def _trail_drift_text(reasons, max_shown: int = 2, max_detail: int = 48) -> str:
    """Literal per-card drift marker (markup=False), detail included.

    The detail is what makes the marker actionable ("status 'Ready' ->
    'Implementing'"), so it is rendered, not just the code. Bounded by
    max_shown reasons and a truncated detail; the full list stays in
    TrailDetailScreen."""
    if not reasons:
        return ""
    parts = []
    for code, _ref, detail in reasons[:max_shown]:
        detail = " ".join(str(detail or "").split())
        if len(detail) > max_detail:
            detail = detail[:max_detail - 1].rstrip() + "…"
        parts.append(f"{code}: {detail}" if detail else str(code))
    extra = len(reasons) - max_shown
    if extra > 0:
        parts.append(f"(+{extra} more)")
    return "⚠ " + " · ".join(parts)
```

- `TrailEntryView` (:485): add `drift_reasons: list = field(default_factory=list)`.
- `build_trail_lanes` (:527): new optional trailing param `drift_by_ref=None`;
  resolve `(drift_by_ref or {}).get(str(entry.get("task")), [])` once per entry
  and pass it into all four `TrailEntryView(...)` constructions. Keying on the
  **raw entry ref** is what makes ghosts work for free (AC3's ghost requirement).
- `_build_active_trail_lanes` (:7016): pass
  `trail_drift_by_ref(self._trail_drift[1] if self._trail_drift else [])`.
- Both card `compose`s: after the badges label, yield when non-empty:
  ```python
  drift = _trail_drift_text(self.trail_view.drift_reasons)
  if drift:
      yield Label(drift, classes="task-info trail-drift", markup=False)
  ```
- CSS (:5259 block): `.trail-drift { color: #FFB86C; }` (the amber already used
  by `.task-modified`).
- `_on_trail_drift` (:7108) currently only calls `_refresh_subtitle()`, so markers
  would never appear. Inside its existing supersession guard, call
  `self._rerender_trail(refocus)` — **not** `refresh_board()`, which would put
  up to 15 s of git/lock subprocesses on the UI thread from an async callback.

### 5. Sync from By-Trail (AC8)

```python
def action_trail_sync(self):
    """`S` in By-Trail: ait sync, then the local recompute (AC8)."""
    if self._modal_is_active():
        return
    self.push_screen(LoadingOverlay("Syncing with remote..."))
    self._run_sync(show_notification=True, show_overlay=True)
```

`_run_sync` already ends (:7305-7306) with `load_tasks` +
`refresh_board(refresh_locks=True)`, which re-projects in By-Trail. Sync is
already a heavyweight remote operation, so the generic path is fine here; append
one line so a sync that pulled new task data also refreshes the verdict:

```python
if self.base_filter == "bytrail" and self.active_trail_handle:
    self.app.call_from_thread(self._start_trail_drift)
```

Remove the now-unreachable `bytrail` branch in `action_sync_remote`
(:7258-7262) — `s` in By-Trail is the new `trail_select` action.

### 6. Bindings and gating (AC6, AC7)

In `BINDINGS` (:5410), keep the existing `r`/`s` entries and add the By-Trail
duplicates *after* them so declaration order is deterministic:

```python
Binding("r", "trail_refresh_local", "Refresh"),
Binding("d", "trail_refresh_drift", "Freshness"),
Binding("R", "trail_refresh_agent", "Agent Refresh"),
Binding("s", "trail_select", "Select Trail"),
Binding("S", "trail_sync", "Sync"),
```

In `check_action` (:5495): `refresh_board` / `sync_remote` → `False` in
`bytrail`; the five new actions → `False` when not `bytrail`; `commit_all`
(:5573) → `False` in `bytrail`, above the existing `get_modified_tasks()` check,
with the rationale comment. Call `self.refresh_bindings()` in `_set_base_filter`
(after the By-Trail block at :6219-6229) and in `_activate_trail` (:7077).

### 7. Per-card hint line (AC6)

`TrailTaskCard.compose` (:1873) prints `[enter details] [r refresh] [s select]`
— `s` there contradicts the footer's "Sync", and neither key is card-scoped.
Reduce it to the one genuinely card-scoped action, keeping `markup=False` (which
`test_trail_task_card_badges_and_strike` pins as a literal-bracket control):

```python
yield Label("[enter details]", classes="task-info trail-ops", markup=False)
```

### 8. Recorded-freshness badge

In `_trail_stored_freshness` (:2115): `"✓ current (recorded)"` and
`f"⚠ stale ({n}, recorded)"`, with a comment that this is the write-time
verdict, not a live check.

## Tests — `tests/test_board_bytrail_view.py`

The existing `_enter_synthetic_bytrail` (:82) stubs `_start_trail_drift` and
injects state, which is right for footer/model tests but **cannot** prove the
refresh path works. Two tests therefore use real on-disk task data through the
sanctioned `TASK_DIR` seam (`config_utils.py:36`), following the
`_load_board_module` idiom in `tests/test_board_archived_relation_lookup.py:41`.

1. **`test_local_refresh_spawns_no_subprocess`** (AC1, AC9 negative control) —
   **does not stub the implementation.** Load the board with `TASK_DIR` pointed at
   a temp tree, enter By-Trail with a synthetic doc, then patch `subprocess.run`
   with a recorder and call the **real** `action_trail_refresh_local()`. Assert
   `seen == []` and that `_launch_trail` was never reached. This is the test the
   old plan got wrong: spying `_refresh_board_data` and then checking subprocesses
   never executes the subprocess-producing path.
   *Discrimination check:* pointing the action at `_refresh_board_data` instead
   must make this test fail (`git status` + `aitask_lock.sh` appear in `seen`).
2. **`test_local_refresh_picks_up_on_disk_status_change`** (AC1) — write a real
   task file with `status: Ready`, render the card and assert `📋 Ready`; then
   **rewrite the file on disk** to `status: Implementing`, call the real
   `action_trail_refresh_local()`, and assert the card renders `📋 Implementing`
   via `widget.render().plain`.
   *Discrimination check:* deleting `manager.load_tasks()` from the action must
   make this test fail — which the old in-memory-mutation version could not.
3. **`test_drift_reasons_render_detail_on_owning_card`** (AC3) — assert the card
   renders the code **and** its detail (`status_changed: status 'Ready' ->
   'Implementing'`), that a **ghost** entry renders its own marker, and that
   `_trail_drift_text` truncates and emits `(+N more)` past `max_shown`. Unit-test
   `trail_drift_by_ref` for dropping `-` refs and grouping multiple codes.
4. **`test_drift_callback_spawns_no_subprocess`** (drift-callback freeze) — with
   `subprocess.run` recorded, call `_on_trail_drift(gen, handle, "STALE", [...])`
   directly and assert no subprocess ran and the markers appeared. Pins that the
   callback uses `_rerender_trail`, not `refresh_board`.
5. **Version watch — launch lifecycle** (AC5). Drive `_launch_trail`'s
   `on_trail_result` directly with each result kind:
   - `action_trail_refresh_agent()` alone (dialog still open) installs **no**
     watch and captures **no** baseline — an ordering spy asserts
     `_trail_versions` was not called;
   - `"run"` and a successful `TmuxLaunchConfig` each install exactly one watch,
     with the baseline captured **before** the launch call (ordering spy over
     `_trail_versions` vs `run_dialog_command` / `launch_in_tmux`);
   - a failed baseline (`_trail_versions` → `[]`) never starts a watch;
   - **failed baseline while an earlier watcher is active**: a *successful*
     second launch whose baseline read returns `[]` must leave the earlier
     watch's timer, handle and baseline fully intact — `_stop_trail_watch` is
     not reached. The negative control for the teardown-before-validate ordering;
   - **cancel with an existing watcher**: arm a watch via a first successful
     launch, then open a second dialog and cancel it — assert the original timer,
     handle and baseline are all **unchanged**, that `_stop_trail_watch` was not
     called, and that no artifact fetch (`load_trail_blob`) ran;
   - **tmux launch failure**: `launch_in_tmux` returning `(None, "boom")` installs
     **no** watch, surfaces the error notification, leaves a pre-existing watch
     from an earlier launch untouched, and performs **no** `load_trail_blob`
     call (asserted directly — the failed-launch path must not re-fetch);
   - a successful launch while a watch is already armed **replaces** it — exactly
     one live timer, and the new baseline in effect.
6. **Version watch — supersession** (the stale-worker hazard):
   - **restart the same-handle watch while an earlier worker is in flight**:
     arm, dispatch a tick, arm again, then deliver the *first* worker's callback
     — assert it is discarded, that the new watch's `_trail_watch_busy` is
     untouched, and that no reload fired even when the stale listing differs
     from the new baseline;
   - a callback arriving after `_stop_trail_watch()` is discarded;
   - `_reload_active_trail()` (which bumps `_trail_gen`) does **not** disarm an
     armed watch — the negative control for keying off the wrong token;
   - arming twice leaves exactly one live timer;
   - a tick while `_trail_watch_busy` spawns no second worker.
7. **Version watch — polling semantics**:
   - `versions == []` (transient failure) → no reload **and** watch still armed;
   - unchanged versions → no reload; changed → `_reload_active_trail` once, watch
     stopped, notification raised;
   - foreign handle and `base_filter != "bytrail"` each discarded;
   - leaving By-Trail, switching trail, and exceeding `TRAIL_WATCH_MAX_TICKS`
     each stop the watch.
8. **`test_bytrail_footer_labels`** (AC6) — the five new actions present in
   `_footer_actions` and `refresh_board`/`sync_remote`/`commit_all` absent in
   By-Trail, and the inverse outside. Assert the label strings via
   `active_bindings[...].binding.description` (stable) rather than the rendered
   `Footer` (version-brittle).
9. **`test_duplicate_key_dispatch_falls_through`** — the structural guard for the
   Textual-internal behaviour this design depends on. Via the pilot, press `r` in
   By-Trail and assert the local action ran and the generic one did not; press `r`
   in the default view and assert the inverse; same for `s`. If a future Textual
   release changes duplicate-key resolution, this test finds out, not a user.
10. **`test_commit_all_hidden_in_bytrail`** (AC7) — `False` even with modified
   tasks present.
11. **`test_hint_line_matches_footer`** (AC6) — `.trail-ops` contains
   `[enter details]` and no longer names `r` or `s`.
12. **Update `test_refresh_launch_args`** (:585) — call
    `action_trail_refresh_agent()`, keep the `agent-trail-trail-demo` window-name
    pin, and assert `action_trail_refresh_local()` launches nothing.
13. **Update `test_auto_refresh_tick_never_launches_in_bytrail`** (:471) — under
    the new contract the tick and `action_trail_refresh_local` both stay off the
    launch path and only `action_trail_refresh_agent` launches.
14. **Update `test_footer_gating_in_bytrail`** (:351) — add the three
    newly-hidden actions.

## Verification

```bash
python3 tests/test_board_bytrail_view.py          # primary suite
python3 tests/test_board_inflight_view.py         # shared card/footer seams
python3 tests/test_board_archived_relation_lookup.py
python3 tests/test_shortcut_scopes.py             # new bindings register cleanly
python3 -m pyflakes .aitask-scripts/board/aitask_board.py
```

**Prove the harness can fail** before finalising — run each discrimination check
above (revert the behaviour, confirm the suite exits non-zero, restore). A
passing suite pins nothing until each guarded regression actually makes it exit 1.

Manual, against the real trail that reproduced the bug:

```bash
ait board          # z → s → art:trail-gates-framework-landing
```
- Footer reads `r Refresh  d Freshness  R Agent Refresh  s Select Trail  S Sync`.
- Edit a member task's `status:` on disk, press `r` → the card updates with no
  agent dialog and no perceptible delay.
- Press `d` → banner returns to `⟳ checking freshness…` then `⚠ stale: N`, and
  detail-bearing drift markers appear on the owning cards (this trail currently
  drifts on t1220/t1265/t635_34 plus archived t1264 → a ghost card).
- Press `C` → nothing (hidden). Press `a` → footer reverts to
  `r Refresh  s Sync  C Commit All`.
- Press `R`, launch into tmux, let the skill land a new artifact version → within
  ~20 s the board notifies "Trail artifact updated — reloading" and re-renders
  with no keypress.

## Risk

### Code-health risk: medium
- The per-view footer relies on Textual's duplicate-key resolution in both
  `_check_bindings` and `active_bindings`. Verified against installed 8.2.7, but
  it is an *internal* behaviour an upgrade could change, and the failure mode is
  silent (wrong action on a keypress) · severity: medium · → mitigation: pinned
  in-task by test 7
- `_rerender_trail` deliberately diverges from `refresh_board` by skipping
  git/lock refresh. Correct today because both trail cards fully override
  `TaskCard.compose`; if a future card variant reads `is_modified`/`lock_map`, it
  would silently render stale · severity: medium · → mitigation: the divergence
  and its precondition are documented in the method docstring, and t1210_5 (which
  adds By-Trail move commands touching `boardcol`) is explicitly routed to this
  helper
- The version watch adds a polling timer — a new lifecycle object that could leak
  or double-fire · severity: medium · → mitigation: stop-then-start idiom
  (mirroring `_start_auto_refresh_timer` :5691), busy flag, tick ceiling, and one
  test per invariant
- `check_action` is on the hot path for every footer refresh and key dispatch;
  eight new branches risk mis-ordering an `elif` · severity: low · → mitigation:
  existing `test_footer_gating_in_bytrail` + `test_focused_ghost_footer_regression`
  are extended, not replaced

### Goal-achievement risk: low
- AC5 is now delivered in-task by the version watch rather than deferred; the
  residual gap is an agent that finishes after the ~30 min tick ceiling, or a
  version listing that never becomes readable · severity: low · → mitigation:
  the ceiling is a named constant and `d` remains the manual fallback
- Drift markers show a truncated detail; a very long detail is legible only in
  the detail modal · severity: low · → mitigation: bounded by `max_detail` with
  an explicit ellipsis, full text in `TrailDetailScreen`

## Coordination

`t1210_5` (Ready, unstarted, no plan) adds `m`/`M` plus new `bytrail`
`check_action` cases in these same regions, and already states it will "reuse
whatever t1268 lands rather than adding a second reload route" — `_rerender_trail`
(after a `load_tasks()`) is that route. This task lands first; t1210_5 rebases
onto the new BINDINGS block and the `refresh_bindings()` calls. The
forward-reference comment at :5615 stays.

Per `aidocs/framework/tui_conventions.md` ("TUI footer must surface every
operation on the affected tab/screen"), the By-Trail binding set is audited here:
every key reachable in By-Trail is footer-visible with a truthful label, and no
`show=False` app binding remains reachable-but-hidden there except the
view-switch radio (`a/l/f/i/y/z/g/t`), which stays hidden because the
`ViewSelector` widget already renders it.

## Final Implementation Notes

- **Actual work done:** All 9 acceptance criteria implemented in
  `.aitask-scripts/board/aitask_board.py`, with `tests/test_board_bytrail_view.py`
  grown from 22 to 65 tests. The refresh ladder (`r` local / `d` freshness /
  `R` agent), per-card drift markers, the artifact-version watch, By-Trail
  `ait sync` on `S`, `C` hidden, per-view footer labels, and the
  recorded-freshness relabel all landed as planned.

- **Deviations from plan:** Five, all from review rounds that found real
  defects in the plan as approved:
  1. **`_rerender_trail` replaced `_refresh_board_data` for AC1.** The plan's
     route was not zero-subprocess: `refresh_board()` unconditionally calls
     `refresh_git_status()` (`git status`, 5 s timeout) and, with
     `refresh_locks=True`, `refresh_lock_map()` (`aitask_lock.sh --list`,
     10 s), both on the UI thread. Safe to skip because `TrailTaskCard` /
     `TrailGhostCard` fully override `TaskCard.compose`, the only reader of
     `modified_files` / `lock_map` / `xdep_status_cache` — recorded as an
     explicit precondition in the method docstring.
  2. **AC5 promoted into this task** rather than deferred to a follow-up (a
     follow-up cannot satisfy its parent's AC). The version watch is armed
     only after a launch actually succeeded, with the baseline read *before*
     the launch call.
  3. **Baseline read moved off the UI thread** (`_trail_baseline_worker`);
     `_trail_versions` shells out with a 15 s timeout and ran inline on the
     screen-result callback. The launch happens in the worker's callback, so
     baseline-before-launch ordering is preserved.
  4. **`canonical_trail_ref` added.** `build_trail_lanes` keyed drift lookups
     on the raw stored ref, but `trail_gather.cmd_drift` emits reasons against
     `inp.canonical`; a trail storing the tolerated `aitasks#t42` spelling
     resolved to a live card with an empty reason list (AC3 silently failing).
     Both sides now canonicalize.
  5. **`_trail_launch_pending` guard added.** A consequence of (3): the dialog
     closes before the baseline lands, so a second confirmed `R` in that
     window would spawn a second refresh agent.

- **Issues encountered:**
  - *Concurrent session in the same worktree.* `.aitask-scripts/lib/gate_ledger.py`
    was half-saved by another session mid-run (`NameError: NamedTuple`),
    failing 14 unrelated board test files. Diagnosed by proving HEAD's copy
    imports cleanly and the breakage lived only in the uncommitted diff; it
    settled on its own. Only this task's two paths were ever staged.
  - *Thread-leak assertion was wrong, not the code.* The first version
    asserted an absolute `threading.active_count()` and failed (`baseline=1
    now=2`). Textual dispatches thread workers onto a pool, so the first run
    legitimately adds a persistent thread. Rewritten to warm the pool, then
    assert no growth across subsequent runs; the weaker-but-true guarantee is
    documented on `ThreadWorkerTests` so it is not re-tightened.
  - *Footer relabel needs an explicit signal.* Textual's `Footer` recomposes
    only on `bindings_updated_signal`, and the board never called
    `refresh_bindings()`. Added at every view/trail transition and on both
    `_trail_launch_pending` edges — without the latter the `FooterKey` widget
    stayed on screen advertising a no-op key while `active_bindings` had
    already dropped it.

- **Key decisions:**
  - *Per-view footer labels via duplicate-key bindings.* Verified against the
    installed Textual 8.2.7 that a repeated key falls through `check_action`
    on both the dispatch path (`app.py` `_check_bindings` → `run_action`) and
    the footer path (`screen.py` `active_bindings`). Because this leans on
    library internals, `test_duplicate_key_dispatch_falls_through` pins it so
    a Textual upgrade surfaces the change in CI rather than in a user's hands.
    Bindings are declared so each uppercase sibling sits next to its lowercase
    primary, satisfying the footer-ordering rule in `tui_conventions.md`.
  - *`C` hidden in By-Trail rather than scoped* to trail members:
    `get_modified_tasks()` is repo-wide and a trail is a reading projection,
    not an ownership boundary. Rationale is in the code.
  - *`_trail_watch_gen` is separate from `_trail_gen`* — the post-launch
    reload bumps `_trail_gen` while the agent is still running, so keying the
    watch off it would silently disarm the poller. A negative-control test
    pins that independence.
  - *`_trail_versions()` returning `[]` is treated as "no signal, retry"*,
    never as a version change: it returns `[]` for every failure mode
    (non-zero exit, timeout, missing script), indistinguishable from a real
    listing.
  - *Verification method.* A mutation harness (16 mutations) proves every
    guard actually fails when its behaviour regresses; a passing suite alone
    would have pinned nothing. It restores from a byte copy — never
    `git checkout --`, which would have destroyed the concurrent sessions'
    uncommitted work — and asserts the restored file matches byte-for-byte.

- **Upstream defects identified:** None

- **Verification results:** 65 tests in `tests/test_board_bytrail_view.py`; all
  19 `tests/test_board_*.py` files plus `tests/test_shortcut_scopes.py` pass;
  16/16 mutations caught. Lint: `python3 -m pyflakes` on the board module
  reports **7 findings, all pre-existing at HEAD** (unused imports: `json`,
  four `task_yaml` symbols, `textual.screen.Screen`,
  `topic_semantics.task_anchor_id`) and **0 introduced by this change** —
  measured by diffing against `git show HEAD:` of the same file, since the
  bare command cannot be honestly reported as passing. The test file lints
  clean.

- **Not done — manual verification:** The plan's manual pass (live footer text,
  `r`/`d` against `art:trail-gates-framework-landing`, and the
  `R` → tmux → auto-reload path) needs a real terminal and was not performed.
  The footer was instead captured headlessly:
  `r Refresh   R Agent Refresh   d Freshness   s Select Trail   S Sync`.
  A manual-verification follow-up is offered at Step 8c.
- **Manual-verification failure:** item "Press `d` — banner returns to `⟳ checking freshness…` then `⚠ stale: N`, and detail-bearing drift markers appear on the owning cards (including an archived member rendered as a ghost card)" failed; follow-up task t1278.

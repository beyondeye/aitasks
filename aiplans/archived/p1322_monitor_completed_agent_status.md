---
Task: t1322_monitor_completed_agent_status.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1322 — COMPLETED agent status in monitor / minimonitor

## Context

`ait monitor` and `ait minimonitor` classify every agent pane into three states
rendered as a colored `●` plus a badge: `PROMPT` (bold magenta), `IDLE`
(yellow), `Active` (green). That vocabulary cannot express the most common
end-state of a task-bound agent: **finished, because its task was archived**.
A completed `agent-pick-<id>` pane reads `IDLE 412s` in yellow — visually
identical to an agent that hung. Telling them apart today means opening the
task-info dialog.

This adds a fourth state, **COMPLETED**, shown when the pane's resolved task is
`Done` / archived.

The signal is already reachable: `aitask_archive.sh` writes `status: Done` then
moves the file to `aitasks/archived/`, and `TaskInfoCache._resolve`
(`monitor_core.py:2703`) already searches both locations. Both TUIs already
resolve task info for every agent pane on every 3 s tick. **The blocker is that
`TaskInfoCache` never re-reads**: `_cache` (`monitor_core.py:2497`) is keyed by
`(session_name, task_id)` with no TTL and no file-identity key, so a task
archived mid-session serves its pre-archival `TaskInfo` forever.

## Decisions (confirmed with the user)

| Decision | Choice |
|---|---|
| Precedence | `PROMPT > COMPLETED > IDLE > Active` — a prompt is still actionable |
| Color | `bold blue` — distinct from magenta/yellow/green, legible on both themes |
| applink | Emit the already-resolved `info.status` as an optional payload field |
| Session bars | Add `N done`, decremented out of the idle count |
| minimonitor docked panel | **Leave static** — no COMPLETED there (documented) |

---

## Part 1 — `TaskInfoCache` freshness (`monitor_core.py`)

### 1a. Sample the file identity BEFORE the content read

`GateSummaryCache.summary_for` (`:2450`) stats before it reads, so its identity
can never be newer than its content. Mirror that ordering exactly. Stat-ing
*after* `_resolve`'s `read_text` would be a silent, permanent staleness bug:
`aitask_archive.sh:154-165` rewrites via `sed -i` and `awk > tmp && mv` —
**rename-based**, so a read racing a rewrite returns the old inode's bytes while
a post-read stat samples the new one, pinning stale content under a fresh key.

Add a defaulted field to `TaskInfo` (`:2401`), alongside `task_file_abs`:

```python
    # File identity (st_mtime_ns, st_size) of task_file_abs, sampled BEFORE the
    # content read in _resolve — never after. The archive script's rewrites are
    # rename-based, so a read racing a rewrite returns the OLD bytes; an
    # identity sampled after that read belongs to the NEW file and would pin
    # stale content permanently. None => always re-resolve.
    file_identity: tuple[int, int] | None = None
```

Module-level helper next to `GateSummaryCache`:

```python
def _file_identity(path: str) -> tuple[int, int] | None:
    """(st_mtime_ns, st_size) for path, or None if it cannot be stat'ed.

    Same key as GateSummaryCache — deliberately, so two caches over the same
    file can never disagree about whether it changed.
    """
    if not path:
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)
```

In `_resolve` (`:2703`), between `if task_path is None: return None` and the
`read_text`, capture `identity = _file_identity(str(task_path))` and pass
`file_identity=identity` into the `TaskInfo(...)` construction.

**Do not change `_resolve`'s signature** — `tests/test_task_info_cache_archived.py`
calls it directly in 7 tests.

### 1b. Cache entry + `get_task_info`

Negative entries have no path to stat, so they need their own state:

```python
@dataclass
class _TaskEntry:
    info: TaskInfo | None
    miss_at: float = 0.0     # monotonic time of the last failed _resolve
    miss_count: int = 0      # consecutive failed _resolves
```

`get_task_info` rejects the cached answer three ways — identity changed (in-place
`Ready`→`Done` edit), stat raises (the file **moved** to `archived/`), or a
negative entry whose bounded retry is due:

```python
    _MISS_RETRY_SCHEDULE: tuple[float, ...] = (5.0, 15.0, 60.0)
    _now = staticmethod(time.monotonic)   # injectable for deterministic tests

    def get_task_info(self, task_id, session_name=""):
        key = (session_name, task_id)
        entry = self._cache.get(key)
        if entry is not None:
            info = entry.info
            if info is not None:
                # `is not None` guard matters: _file_identity returns None on
                # OSError, and None == None would serve a stale entry for a
                # file we can no longer stat.
                if (info.file_identity is not None
                        and _file_identity(info.task_file_abs) == info.file_identity):
                    return info
            elif not self._miss_retry_due(entry):
                return None
        return self._store(key, self._resolve(task_id, session_name), entry)
```

`invalidate` stays byte-identical (`self._cache.pop(key, None)`) — popping also
resets the miss budget, which is exactly what a user-initiated refresh wants.

**Critically: on `OSError` this must RE-RESOLVE, not fail closed.**
`GateSummaryCache` fails closed to `""` on OSError — right for a decorative gate
column, wrong here. Failing closed would blank the pane's task title on exactly
the tick the task completes.

### 1c. Why one `os.stat` per pane per tick is the right cost

Measured on this repo (`aitasks/` 189 files, `aitasks/archived/` 190):

| operation | cost |
|---|---|
| `os.stat`, warm path | **0.65 µs** |
| full `_resolve` miss (2 × `is_dir` + 2 × glob) | **~125 µs** |

At a realistic worst case of 40 agent panes that is **26 µs per 3 s tick** — three
orders of magnitude below the tmux `capture-pane` + prompt-regex work already on
that tick. Rejected alternatives: a directory-mtime gate misses the in-place
`status:` edit entirely (and `aitasks/` is a symlink into a separate worktree); a
sentinel file written by `aitask_archive.sh` is a cross-language contract that
rots silently; inotify is a new dependency and a new NFS/overlayfs failure mode.
All to save 26 µs.

### 1d. Bounded retry for negative entries — mandatory, not optional

This change *introduces* the risk: pre-fix a resolved entry was immortal;
post-fix an `ENOENT` during any sub-millisecond rename window inside
`archive_move` can trigger a re-resolve that legitimately finds nothing and
poisons the slot forever, losing both the title and the badge.

Permanent misses (tar-bundled `archived/_b0/old*.tar.zst`, folded-away tasks) must
not be re-globbed forever; transient ones (rename windows, a `git pull` in the
data worktree) usually resolve within seconds.

**But the backoff must never terminate.** A schedule that stops after
`5 + 15 + 60 s` assumes every transient is short. It is not: this repo's own
`aitask_pick_own.sh --sync` currently reports *"31 commit(s) not pushed — data
worktree has unstaged changes blocking rebase"*, and an interrupted archive or a
long reconciliation in `.aitask-data` can hold `aitasks/` in an unresolvable
state for minutes. A terminating budget would leave that pane permanently
task-less — no title, no COMPLETED — until some unrelated explicit
`invalidate()` happened to fire, which is precisely the eventual-consistency
guarantee this feature needs.

So the schedule backs off to a **sparse steady state and stays there**:

```python
    # Backoff steps, then a sparse terminal interval repeated forever. The
    # terminal step must exist: a budget that stops permanently poisons a pane
    # whose miss outlived the budget (interrupted archive, long .aitask-data
    # reconciliation), and nothing else guarantees recovery.
    _MISS_RETRY_SCHEDULE: tuple[float, ...] = (5.0, 15.0, 60.0)
    _MISS_RETRY_TERMINAL: float = 300.0
```

`_miss_retry_due` clamps past the end of the schedule to `_MISS_RETRY_TERMINAL`
instead of returning `False`. Steady-state cost for a genuinely permanent miss
(a bundled task) is **one `_resolve` per 5 minutes per pane** — at the pessimistic
~1.2 ms figure below, 0.0004 % of one core. That is the correct price for
guaranteed recovery.

Contrast the unbounded alternative that this replaces: a per-tick re-glob on a
project that has not run `ait zip-old` (1000+ archived files, ~1.2 ms/resolve)
would burn ~12 ms of synchronous event-loop time every 3 s, forever, to
re-discover the same "no".

### 1e. Keep every existing `invalidate()` call site

Sites: `monitor_app.py:2321,2423,2555`; `minimonitor_app.py:942,1520`;
`applink/router.py:591,637,663`. They are no longer needed for the in-place-edit
case, but they remain the **only immediate retry for a cached negative** (a
backoff that isn't due would otherwise return `None` again to a user's explicit
gesture), and the only thing that re-decides `_resolve`'s active-beats-archived
precedence when both copies exist. Cost on those paths is zero — all are
keypress/dialog/RPC handlers.

### 1f. Keep `update_session_mapping`'s `clear()` — and say why in its docstring

`:2510` clears `_cache` when the session→project mapping changes. This is the one
staleness class the identity key **structurally cannot catch**: if a session's
root changes, the old root's path may still stat fine (a real `t100` in the
fallback project), and the identity gate would serve the wrong project's task
indefinitely with no signal. Document it so a later reader does not delete it as
redundant.

### 1g. Rewrite `blocking_dependencies`' docstring and its negative control

`blocking_dependencies` (`:2586`) calls `get_task_info(dep)`, so its docstring
paragraph — *"a cached read would report a long-completed dependency as still
blocking… `refresh=False` exists so tests can exercise the stale path as a
negative control"* — becomes false. **Verified breakage:**
`tests/test_minimonitor_pick_by_number.py:359` `test_negative_control_stale_read_without_refresh`
rewrites `t1200` `Ready`→`Done` at the same path and asserts `refresh=False`
still reports `["1200"]`; post-fix it returns `[]`.

Keep the test, replace its *mechanism*: prove the cache is populated with a
`_resolve` call-counting spy over an **unchanged** file — `refresh=False` ⇒
`_resolve` ran once (identity gate served cache), `refresh=True` ⇒ ran twice.

---

## Part 2 — The status ladder (`monitor_shared.py`)

COMPLETED is derived from the **task**, not the snapshot, and a shadow pane has
no task of its own. So it must be an explicit opt-in parameter — never inferred
inside the shared helper, or `format_shadow_glyph` would start colouring shadows
by their followed agent's task state.

```python
def is_task_completed(info: "TaskInfo | None") -> bool:
    """True when a pane's resolved task is finished — status Done, or the file
    already lives under aitasks/archived/. Both are checked because
    aitask_archive.sh sets the status BEFORE it moves the file, so a tick can
    land between the two."""
    if info is None:
        return False
    if info.status.strip() == "Done":
        return True
    return "/archived/" in info.task_file_abs.replace(os.sep, "/")


def _state_color(snap, completed: bool = False) -> str:
    if getattr(snap, "awaiting_input", False):
        return "bold magenta"
    if completed:
        return "bold blue"
    if snap.is_idle:
        return "yellow"
    return "green"


def format_state_dot(snap, completed: bool = False) -> str: ...
def format_pane_status(snap, completed: bool = False) -> str:
    # ... "[bold blue]DONE {int(snap.idle_seconds)}s[/]" in the completed branch
```

`format_shadow_glyph` keeps its single-argument signature and never passes
`completed` — pinned by a test.

All four keep `completed` **defaulted to False**, so the existing pure-formatter
tests at `tests/test_monitor_shadow_status.py:395-419` stay byte-identical.

---

## Part 3 — One per-refresh completed set per app

Compute `self._completed_pane_ids: frozenset[str]` **once per refresh cycle** and
read it from the card builder, the session bar, and auto-switch. Not per-builder:
the bars have no task-cache access in their bodies, so a per-surface computation
would run the resolve loop 2-3× per tick and could disagree within one tick
("2 done" beside 3 COMPLETED badges).

**The decisive argument is ordering.** A completed agent is idle forever and,
sorted by `idle_seconds` descending, would **permanently capture auto-switch
focus** — the monitor would park on a finished agent and never surface a live one
needing input. That is a regression this feature introduces unless auto-switch is
taught about COMPLETED, and only a precomputed set makes it available that early.

Shared helper (identical body in both apps):

```python
    def _compute_completed_panes(self) -> frozenset[str]:
        done: set[str] = set()
        for pid, snap in self._snapshots.items():
            if snap.pane.category != PaneCategory.AGENT:
                continue
            task_id = self._task_cache.get_task_id_for_pane(snap.pane)
            if not task_id:
                continue
            if is_task_completed(
                self._task_cache.get_task_info(task_id, snap.pane.session_name)
            ):
                done.add(pid)
        return frozenset(done)
```

### `monitor_app.py`

- **`:566`** — init `self._completed_pane_ids: frozenset[str] = frozenset()`.
  Empty init keeps `action_toggle_auto_switch` (`:2267`, which rebuilds outside
  `_refresh_data`) safe; that keypress path reuses the last tick's set rather
  than triggering an N-stat fan-out.
- **`:891`** in `_refresh_data` — recompute immediately after the
  `update_session_mapping(...)` block and **before** `_maybe_auto_switch`
  (`:928`). Verified ordering: `update_session_mapping` `:889` →
  auto-switch `:928` → `_rebuild_session_bar` `:936` → `_rebuild_pane_list` `:945`.
- **`_maybe_auto_switch` `:1056`** — exclude completed panes from both the
  `awaiting` and `idle_agents` comprehensions, **and** from the
  "current pane already needs attention, keep it" early return (`:1071`) — a
  completed current pane must not be kept.
- **`_rebuild_session_bar` `:1195`** — the counters must partition the agents
  exactly as the badges do, so **every bucket honours `PROMPT > COMPLETED > IDLE`**.
  It is not enough to subtract completed from idle: a completed agent parked on
  its final feedback prompt is *both* awaiting and completed, and would otherwise
  be counted in `awaiting` **and** `done` while its badge reads `PROMPT`.

  ```python
  awaiting_count = sum(1 for a in agents if getattr(a, "awaiting_input", False))
  done_count = sum(
      1 for a in agents
      if a.pane.pane_id in self._completed_pane_ids
      and not getattr(a, "awaiting_input", False)
  )
  idle_count = sum(
      1 for a in agents
      if a.is_idle
      and not getattr(a, "awaiting_input", False)
      and a.pane.pane_id not in self._completed_pane_ids
  )
  ```

  Each agent now lands in **at most one** bucket, matching its rendered badge.
  Test this explicitly: an agent that is completed *and* awaiting counts once, as
  awaiting.
- **`_format_agent_card_text` `:1255`** — pass
  `completed=(snap.pane.pane_id in self._completed_pane_ids)` to
  `format_state_dot` and `format_pane_status`. `format_shadow_glyph` is left
  untouched.

  **The set is the SOLE source of the card's completed flag.** The builder also
  calls `get_task_info` for the title and gate summary, but that second lookup
  must **never** re-derive completion via `is_task_completed`: an archive landing
  between the set computation and the card build would flip the identity gate and
  make the badge disagree with the session bar and the auto-switch decision for a
  tick. The title may come from the later lookup; the state may not. Guard this
  with a test that stubs the set to disagree with the on-disk task and asserts the
  badge follows the set.
- **Legend** — append a compact dim legend to the `CODE AGENTS (n)` section
  header. That text is built in **two** places (fast path `:1344`, slow path
  `:1388`); extract a single `_agents_header_text(n)` helper used by both rather
  than duplicating a third variant.

### `minimonitor_app.py`

- **`:244`** — same field init.
- **`:438`** in the refresh loop — recompute after `self._gate_cache.clear()`,
  before `_rebuild_session_bar`.
- **`_rebuild_session_bar` `:573`** — same three-way partition as the full
  monitor (done excludes awaiting; idle excludes both); the bar is tight
  (`multi: 2s · 5a`), so use the compact `{n}d` form.
- **`_agent_card_text` `:606`** — same set-sourced `completed=` pass-through,
  under the same "set is the sole source" rule.
- **`_own_agent_identity_text` `:648` — deliberately unchanged.** The docked
  followed-agent panel stays static per the user's decision; record that in its
  docstring so the omission reads as a choice, not an oversight.
- `_check_auto_close` (`:463`) is **not** touched — whether completion should
  drive auto-close is a separate product question.

---

## Part 4 — `agent-resume-<id>` and applink

**Regex** (`monitor_core.py:2387`): extend to
`^agent-(?:pick|qa|resume)-(\d+(?:_\d+)?)$`. `agent-resume-<num>` windows
(`board/aitask_board.py:7918`) currently resolve to no task id at all, so those
agents show no task info and could never show COMPLETED. Unit-test the regex
against every window name the launch sites actually emit: `monitor_app.py:2507,2587`,
`minimonitor_app.py:1016`, `board/aitask_board.py:6989,7161,7918`,
`codebrowser/history_screen.py:430`. `agent-explore-*` / `agent-raw-*` must keep
resolving to `None`.

**applink** (`applink/pusher.py:388`): `_send_pane_status` already resolves the
`TaskInfo` at `:395` and reads only `.title`, discarding `.status`. Emit it as an
optional payload field alongside the existing conditional `title`.
`aidocs/applink/monitor_port_design.md:154` already promises status rides this
push. Per `aidocs/applink/protocol.md:204` a new optional field is **additive —
no `v` bump**. The `not_idle` restart gate in `router.py:577` is left alone.

Read it exactly as the title is read — `getattr(info, "status", None)`, inside
the existing `try/except`, emitted only when truthy. This is not defensive
styling: `tests/test_applink_pusher.sh:122-136`'s `FakeTaskResolver` returns
`SimpleNamespace(title=title)` with **no `status` attribute**, so a direct
`info.status` would raise inside the best-effort block and silently drop the
title too. The fake gains a `statuses` map in the same change.

**Extend `tests/test_applink_pusher.sh`** to mirror the three title cases it
already pins — otherwise the field could be omitted entirely, sent empty on a
miss, or break the best-effort contract while every monitor test still passes:

| existing title assertion | new status assertion |
|---|---|
| `:235` omits `title` when no resolver is injected | omits `status` in the same frame |
| `:253` carries `title` when the resolver returns info | carries `status` (`"Done"`) from the same lookup |
| `:270` still emits when the resolver **raises** | still emits, with neither `title` nor `status`, `task_id` intact |

Plus one case the title has no analogue for: a resolver returning an info object
whose `status` is empty must omit the key rather than send `""`.

---

## Part 5 — Tests

New `tests/test_task_info_cache_freshness.py`, stdlib `unittest` (**pytest is not
installed** — the runner falls back to `unittest discover`; bootstrap `sys.path`
from `__file__` as `test_task_info_cache_archived.py:16` does, since the runner
unsets `PYTHONPATH`). Spy on `TaskInfoCache._resolve` with a call counter, inject
the clock via `cache._now`, bump mtimes with
`os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))` — no sleeps
(`aidocs/framework/testing_conventions.md`).

| test | pins |
|---|---|
| `test_archive_move_reresolves_to_archived` | **the feature.** Write Ready, resolve, rewrite Done + `shutil.move` to `archived/`, assert `status == "Done"` and path contains `archived`. Reverting the fix fails on `AssertionError: 'Ready' != 'Done'`. `assertIsNotNone` guards against the *wrong* fix (fail-closed on OSError). |
| `test_unchanged_file_resolved_once` | **cost negative control** — two calls ⇒ `_resolve` ran once. Fails if someone "fixes" this by dropping the cache. |
| `test_in_place_status_edit_is_seen` | the pre-move `Ready`→`Done` rewrite |
| `test_same_mtime_different_size_is_seen` | keying on `st_mtime_ns` alone (needed separately: `shutil.move` preserves mtime, so the move case is caught by ENOENT, not by size) |
| `test_identity_sampled_before_read` | the §1a ordering trap — patch `read_text` to bump mtime as a side effect |
| `test_negative_entry_not_reglobbed_every_call` | unbounded per-tick re-glob |
| `test_negative_entry_retried_after_backoff` | permanent poisoning after an archive-window race |
| `test_negative_retry_backs_off_but_never_stops` | **the recovery guarantee.** Miss, advance the clock past every schedule step, assert the retry interval has grown to `_MISS_RETRY_TERMINAL` and is still firing; then create the file, advance past one terminal interval, assert it resolves. Fails if the schedule ever terminates. |
| `test_negative_retry_is_sparse_at_steady_state` | the cost side of the same knob — over a long simulated span the resolve count tracks the terminal interval, not the tick rate |
| `test_update_session_mapping_still_clears` | §1f — the silent wrong-project bug |
| `test_explicit_invalidate_resets_miss_budget` | §1e |

Render-level tests extend `tests/test_monitor_shadow_status.py`'s existing
idioms — `app._format_agent_card_text(snap)` / `app._agent_card_text(snap)` for
markup assertions, and the mounted `run_test(size=(100,30))` +
`card.render().plain` pattern (`:490`) for the composited row. Per that file's
own convention (`:422`), colour is asserted on the **raw markup** string and
glyph presence/ordering on `.plain`. Add:

- all four states from **both** builders (there is zero coverage today);
- a **byte-identity negative control** — a non-completed row is byte-identical to
  the pre-change output (the idiom at `:452`);
- `format_shadow_glyph` never renders blue (shadows have no task);
- **the counter partition** — an agent that is completed **and** awaiting is
  counted once, as awaiting, in **both** bars; a completed non-awaiting agent
  counts as done and not as idle. The sum of the three buckets never exceeds the
  agent count;
- **the set is the sole source of the badge** — stub `_completed_pane_ids` to
  disagree with the on-disk task and assert the badge follows the set, not the
  card builder's own `get_task_info` lookup;
- `_maybe_auto_switch` never selects a completed pane, and does not keep one.

Rewrite `tests/test_minimonitor_pick_by_number.py:359` per §1g.

## Verification

```bash
# targeted first — the runner's -k filter runs nothing under unittest
/home/ddt/.aitask/venv/bin/python tests/test_task_info_cache_freshness.py
/home/ddt/.aitask/venv/bin/python tests/test_task_info_cache_archived.py
/home/ddt/.aitask/venv/bin/python tests/test_monitor_shadow_status.py
/home/ddt/.aitask/venv/bin/python tests/test_minimonitor_pick_by_number.py
/home/ddt/.aitask/venv/bin/python tests/test_monitor_gate_cache.py

bash tests/test_applink_pusher.sh      # self-contained; prints its own PASS/FAIL

bash tests/run_all_python_tests.sh     # read ONLY the last line for the verdict
```

Then a **live check in a real terminal** — a rendered-string assertion cannot
prove legibility: launch `ait monitor` beside an agent whose task is archived and
confirm the blue dot, the badge, the `N done` counter and the legend, at both a
wide terminal and minimonitor's narrow docked width.

Docs: correct `aidocs/framework/monitor_idle_and_prompt_detection.md` — it names
`tmux_monitor.py` as the home of `_finalize_capture` (moved to `monitor_core.py`;
that module is now a re-export shim), its "three sites consume
`awaiting_input`/`is_idle`" list predates the applink pusher/router consumers and
the `_state_color` / `format_state_dot` / `format_shadow_glyph` split, and it must
document the fourth state and the new precedence.

Step 9 (Post-Implementation) handles merge, gate run, and archival.

## Final Implementation Notes

- **Actual work done:** All five parts landed as planned. `TaskInfoCache` is now
  identity-keyed on `(st_mtime_ns, st_size)` with `_TaskEntry` slots; the ladder
  gained COMPLETED via an explicit `completed` parameter; both apps compute a
  per-refresh `_completed_pane_ids` set that is the sole source for the card
  badge, the three-way bar counters and the auto-switch filter; `_TASK_ID_RE`
  covers `agent-resume-`; `pane_status` carries an optional `status`. 38 new
  tests across two new files, plus 6 new checks in `test_applink_pusher.sh`.

- **Deviations from plan:**
  1. **Colour changed from `bold blue` to `bold dodger_blue1`.** The plan's own
     live-terminal verification step caught what no string assertion could:
     Textual resolves `blue` to `#000080` — a **1.09:1** contrast ratio against
     the `#1a1a1a` card background, effectively invisible — and even bolded it
     only reaches `#0000ff` (2.03:1), worse than every other state.
     `dodger_blue1` (`#0087ff`) measures 4.90:1. Confirmed by tmux capture
     (`38;5;33`). This preserves the user's "blue, not cyan" decision.
  2. **Negative-retry schedule made non-terminating.** The plan originally
     stopped after `5+15+60s`; a review concern showed that a miss outliving the
     budget (interrupted archive, long `.aitask-data` reconciliation) would
     poison a pane permanently. It now decays to a sparse 300s interval and
     never stops. Risk downgraded medium → low as a result.
  3. **`blocking_dependencies` docstring correction was NOT committed here.**
     That method does not exist at HEAD — it is part of the concurrent t1310
     work — so the correction lives in the working tree and will land with
     t1310's own commit.

- **Issues encountered:**
  - **Concurrent session overlap.** t1310 (status `Implementing`) had
    uncommitted work interleaved with mine in `monitor_core.py`,
    `monitor_shared.py` and `minimonitor_app.py`, and owns the *untracked*
    `tests/test_minimonitor_pick_by_number.py`. Per user decision the commit was
    built by **surgical hunk splitting**: t1322-only file contents were
    reconstructed from HEAD by anchored replacement, verified to contain zero
    t1310 identifiers, and proven self-consistent by running 13 monitor/applink
    suites against an isolated export of HEAD + only those files. Staged content
    therefore differs from the working tree by design.
  - **A predicted test breakage was real.** My change made
    `test_negative_control_stale_read_without_refresh`
    (`tests/test_minimonitor_pick_by_number.py:359`) fail, exactly as the plan
    predicted — its mechanism (rewrite the file, assert the stale answer
    persists) no longer discriminates once the cache is identity-keyed. Rewritten
    to count `_resolve` calls over an unchanged file. That file is t1310's, so
    the fix is left in the working tree for their commit.
  - **Test-harness discrimination was verified, not assumed.** Three negative
    controls: neutralising `_file_identity` fails 4 freshness tests (including
    the archive-move test with the predicted `'Ready' != 'Done'`); unfiltering
    auto-switch fails both focus tests; and the done/awaiting double-count was
    shown to produce `1 done` alongside `1 awaiting` under the buggy variant.

- **Key decisions:**
  - Identity sampled **before** the content read (the archive script's rewrites
    are rename-based, so stat-after-read would pin stale content permanently).
  - `OSError` **re-resolves** rather than failing closed like `GateSummaryCache`
    — failing closed would blank the task title on the very tick it completes.
  - `completed` is an explicit parameter, never inferred inside `_state_color`,
    so `format_shadow_glyph` can never colour a task-less shadow pane.
  - The per-refresh set (not a per-surface lookup) is the sole state source, so
    the badge, the counters and auto-switch cannot disagree within a tick.
  - `update_session_mapping`'s `clear()` documented as **not** redundant — it is
    the one staleness class the identity key structurally cannot catch.

- **Upstream defects identified:**
  - `tests/test_multi_agent_window_substrate.sh:90-92 — pre-existing failure: "discovery keeps exactly one real agent" / "discovery kept the agent pane (%1)" fail and the embedded Python then raises AttributeError: 'list' object has no attribute 'pane_id'. Reproduces with all t1322 changes stashed, so it predates this task; _parse_list_panes appears to no longer filter shadow/companion panes as the test expects.`
  - `.aitask-scripts/board/aitask_board.py — uncommitted concurrent change makes tests/test_board_work_report.py::test_hidden_cards_still_listed fail in the live tree; the same test passes at HEAD and with only t1322's changes applied. Belongs to the concurrent board work, not to t1322.`

## Risk

### Code-health risk: medium
- `TaskInfoCache` is shared substrate, not a TUI detail: beyond the two monitors
  it backs `applink/server.py:195`, `applink/router.py` and `applink/pusher.py`.
  Changing its caching semantics changes behaviour for consumers this task does
  not exercise. · severity: medium · → mitigation: none (declined at planning)
- The change converts an immortal-entry cache into one that can now return
  `None` where it previously could not (a re-resolve landing inside an
  `archive_move` rename window, or during a long `.aitask-data` reconciliation).
  Contained in-design by a backoff that **never terminates** — it decays to a
  sparse 5-minute retry rather than stopping — so recovery is guaranteed rather
  than dependent on an unrelated explicit `invalidate()`. Residual risk is the
  correctness of that state machine, pinned by two dedicated tests.
  · severity: low · → mitigation: none (declined at planning)
- The identity-must-be-sampled-before-the-read ordering is invisible on
  inspection — stat-after-read looks correct and would pin stale content
  permanently. Guarded by one test whose absence would not be noticed.
  · severity: medium · → mitigation: none (declined at planning)
- Parallel edits to two apps (`monitor_app` / `minimonitor_app`) that already
  carry hand-rolled duplicates of the status ladder. Mitigated in-plan by
  extracting shared helpers (`is_task_completed`, `_compute_completed_panes`,
  `_agents_header_text`) rather than adding a fourth and fifth copy.
  · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The approach is verified against source rather than assumed: the completion
  signal, the archived-search in `_resolve`, the per-tick resolve, and the
  precise cache defect were each read directly, and the one predicted test
  breakage was confirmed by reading the test. All four product decisions are
  user-confirmed.
- Residual: "distinct at a glance" is a legibility claim that a rendered-string
  assertion cannot prove — `bold blue` could read poorly on some terminal
  themes, and minimonitor's docked column is narrow. Covered by the live-terminal
  check in Verification, not by the test suite. · severity: low
  · → mitigation: none needed


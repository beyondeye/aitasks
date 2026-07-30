---
Task: t1326_cross_repo_agent_marks.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1326 — Cross-repo prioritized-agent marks

## Context

When following many codeagents in `ait minimonitor` / `ait monitor`, they are not
equally important. There is no way to flag one as prioritized, and no way for
that flag to be visible from the monitor TUIs running in *other* repos even
though the same person drives all of them.

This adds a single-key toggle that marks an agent as prioritized, renders it as a
distinct always-on glyph in the agent row, and persists marks in one per-user
file outside every repo so all monitor instances — in any repo — agree. Stale
entries are purged automatically.

This is the **first persisted state** for the monitor TUIs: today
`.aitask-scripts/monitor/` has no on-disk state at all.

## Decisions (confirmed with the user)

| Decision | Choice |
|---|---|
| Store path | `~/.config/aitasks/agent_marks.json`, env-overridable |
| Toggle key | `space` (precedent: `_ConcernRow.on_key`, `monitor_shared.py:927`) |
| Glyph | Always-on pair `★` / `☆` |
| Scope | Visual only — no reordering, no counters |
| Write lock | Bash wrapper holds `registry_lock.sh`; Python primitive is lock-free |
| Followed agent | Not markable (docked panel stays static by design) |
| Purge | Per-tick filter on read; periodic materialization; fail-closed liveness |

## Design

### 1. Identity — `(realpath(project_root), window_name)`

**Not** the session name. `AitasksSession.key`
(`.aitask-scripts/lib/agent_launch_utils.py:126-141`) documents that the tmux
session name is *not* unique across repos — unconfigured repos all fall back to
the literal `"aitasks"`. `realpath(project_root)` is the canonical identity.
`pane_id` (`%N`) is recycled across tmux server restarts and is not durable.

Both TUIs already resolve a per-snapshot root: `MonitorApp._root_for_snap`
(`monitor_app.py:857-869`) and `MiniMonitorApp._root_for_snap`
(`minimonitor_app.py:529-537`), both backed by the free-on-cache-hit
`TmuxMonitor.get_session_to_project_mapping()` (`monitor_core.py:1358-1365`).

Canonicalize with `os.path.realpath` on **both** the write and the read side, so
a mark written from a symlinked checkout matches a read from the real path.

### 2. New module — `.aitask-scripts/lib/agent_marks.py`

Pure, lock-free store + policy. No Textual, no tmux, no subprocess imports, so it
unit-tests standalone. `lib/` is already on `sys.path` for the monitor package
(`monitor_shared.py:14-16`).

Follows the `attachment_meta.py` contract verbatim: *"LOCK-FREE PRIMITIVE: this
script NEVER takes a lock — callers own concurrency."*

**On-disk schema** (JSON; `json` is stdlib — the repo has no PyYAML dependency):

```json
{
  "version": 1,
  "marks": [
    { "root": "/home/ddt/Work/aitasks", "window": "agent-pick-1326", "marked_at": 1785312000 }
  ]
}
```

A flat record list, not a nested dict: human-inspectable, and per-row lookup cost
is irrelevant because the reader materializes a `set[(root, window)]` once per
re-read. `version` is checked on load; an unknown/newer version is treated as
unreadable (render nothing) and the writer **refuses to overwrite** it.

**Public API:**

```python
MARKS_ENV       = "AITASKS_AGENT_MARKS_FILE"     # mirrors AITASKS_PROJECTS_INDEX
TTL_ENV         = "AITASKS_AGENT_MARK_TTL_DAYS"
DEFAULT_TTL_DAYS = 2.0
SCHEMA_VERSION  = 1

class MalformedMarksError(Exception): ...        # cf. userconfig_persist.py:36-45

def marks_path() -> Path
def mark_key(root, window) -> tuple[str, str]    # realpath(root), window

def load(path=None) -> MarksFile                 # raises MalformedMarksError
def load_safe(path=None) -> MarksFile            # never raises; empty on error
def dump(mf, path=None) -> None                  # atomic write, mode 0600

# Pure policy — all return the DROPPED records, not a bare bool
def toggle(mf, root, window, *, now=None) -> ToggleResult   # .now_marked, .record
def expire(mf, *, ttl_days=None, now=None) -> list[MarkRecord]
def sweep_liveness(mf, observed: dict[str, set[str]]) -> list[MarkRecord]

class MarksView:                                 # the TUI-side cached reader
    def refresh(self) -> bool                    # True iff re-read
    def is_marked(self, root, window) -> bool
```

- **Atomic write** modelled on `config_utils.py:162-228` — resolve `realpath`
  first so `os.replace` cannot clobber a symlink; preserve the existing mode so
  `mkstemp`'s 0600 is not downgraded; no `fsync` (atomic *visibility*, matching
  `gate_ledger` / `attachment_meta`).
- **`MarksView` cache key is `(st_mtime_ns, st_size)`**, not bare `mtime` —
  coarse mtime granularity is a real staleness trap. This is exactly what
  `GateSummaryCache` already does (`monitor_core.py`, pinned by
  `tests/test_monitor_gate_cache.py`). Per-tick cost when unchanged is one
  `os.stat`.
- **Corruption is asymmetric by design.** The read path (`load_safe`) fails
  *safe*: malformed JSON, a truncated file, a directory at the path, or an
  unreadable file all yield an empty view and never crash the refresh tick. The
  write path (`load`) fails *loud*: it raises rather than silently round-tripping
  a corrupt file back as `{}` and destroying the user's marks.
- **`__main__` CLI** (`toggle` / `list` / `purge`) so the bash wrapper can drive
  it, following the `agent_launch_utils.py:1674+` argparse precedent.

### 3. New wrapper — `.aitask-scripts/aitask_agent_marks.sh`

Owns the mutex; the only writer. Mirrors `aitask_projects.sh:40-61`:

```bash
MARKS_FILE="${AITASKS_AGENT_MARKS_FILE:-$HOME/.config/aitasks/agent_marks.json}"
MARKS_LOCK_DIR="${MARKS_FILE}.lockd"      # derived, so the env override carries
```

| Verb | Output | Exit |
|---|---|---|
| `toggle <root> <window>` | `MARKED:<root>\|<window>` or `UNMARKED:…` | 0 |
| `purge --observed <file>` | `PURGED:<n>` (+ `DROPPED:<root>\|<window>\|<reason>`) | 0 |
| `list` | one `MARK:<root>\|<window>\|<marked_at>` per entry | 0 |
| any, lock busy | `LOCK_BUSY` | 3 |
| any, corrupt file | `ERROR:<msg>` | 4 |

**Lock timeout is 2s for `toggle`**, not the 10s default: this is on a keypress
path. `registry_lock.sh` returns 1 rather than proceeding, so on busy the wrapper
writes nothing and exits 3 — never write unlocked.

`list` is a convenience/debug verb and reads under the lock for a consistent
snapshot; the TUIs do **not** use it (they read the file directly, lock-free —
`os.replace` makes every read see one whole generation).

### 4. Render helper — `.aitask-scripts/monitor/monitor_shared.py`

Beside the other glyph formatters (`format_state_dot` :110, `format_shadow_glyph`
:122):

```python
MARK_GLYPH  = "★"   # prioritized
MARK_EMPTY  = "☆"   # not prioritized

def format_mark_glyph(marked: bool) -> str:
    """Always-on ★/☆ pair for the user's prioritized-agent mark.

    Unlike :func:`format_shadow_glyph`, this NEVER returns "" — the pair is
    always-on by explicit decision (t1004 convention, cf. the board/brainstorm
    ☑/☐), so an unmarked agent reads as *deliberately unmarked* rather than as
    a row that forgot to render. Bold yellow for marked matches the repo-wide
    marked=bold-yellow convention (brainstorm/widgets.py:419).
    """
    return f"[bold yellow]{MARK_GLYPH}[/]" if marked else f"[dim]{MARK_EMPTY}[/]"
```

`★`/`☆` and not `☑`/`☐`: the checkbox pair already means "selected for this
action" in `_ConcernRow` (`monitor_shared.py:913`) in the same module. It is also
shaped distinctly from `●` (state) and `◆` (shadow).

**Placement: leftmost, before the state dot** — the mark is a durable user
annotation, not part of the live-state cluster, and leftmost content survives
truncation first.

- `minimonitor_app.py:679` → `f"{mark} {dot}{shadow_part} {glyph} {name}  {status}"`
- `monitor_app.py:1355-1358` → `f" {mark} {dot}{shadow_part} {glyph} {window_index}:{window_name} …"`

**Width budget (minimonitor only).** `#mini-pane-list` renders at ~38 usable
columns and the worst-case row (`● ◆! ≈ <22-char name>  PROMPT 123s`) already
reaches ~42. The mark adds 2 more. Pay for it by lowering `max_name` from 22 to
**20** (`minimonitor_app.py:674`) — shed context before signal. The
"truncated to 22 characters" line in the minimonitor how-to must change with it.
The full monitor is full-width and needs no budget change.

### 5. TUI integration

Identical shape in both apps.

**Binding** — `Binding("space", "toggle_mark", "Mark", show=False)` in
`minimonitor_app.py:193-211` and `monitor_app.py:458-477`. `space` is free in
both, and free in Textual's `VerticalScroll`/`ScrollView` bindings (verified).
`register_app_bindings` (`shortcuts_mixin.py:90`) picks it up automatically — no
keybinding-registry edit. In the full monitor, `check_action`
(`monitor_app.py:2061-2065`) already disables every pane-list binding outside
`Zone.PANE_LIST`, so `space` keeps being forwarded to the tmux pane in the
preview/shadow zones exactly as today.

**Action** — `async def action_toggle_mark`, following the
`action_cycle_compare_mode` idiom (`minimonitor_app.py:1682-1694`):

1. Resolve the selected card with **`_get_focused_pane_id()`** (live focus), not
   the cached `_focused_pane_id` — and return **silently** when it is `None`.
   This is load-bearing: Textual keeps App-level bindings in the chain while a
   `ModalScreen` is pushed (which is exactly why `_ConcernRow.on_key` calls
   `event.stop()`), so a bare `space` pressed inside any modal *without* a space
   handler would otherwise toggle a mark invisibly behind the dialog. Live focus
   is inside the modal, so `_get_focused_pane_id()` returns `None` and the action
   no-ops. Note this deliberately diverges from `_current_shadow_pane_id`
   (`monitor_app.py:1787-1797`), which documents preferring the *cached* field —
   record why in a docstring so the divergence reads as a choice.
2. Resolve the root **strictly**: require `snap.pane.session_name` to be present
   in `get_session_to_project_mapping()`. Do **not** use `_root_for_snap`'s
   silent fallback to `self._project_root` here — that fallback would attribute a
   foreign repo's agent to *this* repo and write a mark under the wrong root.
   Unresolvable → `notify("Cannot resolve this agent's project", severity="warning")`
   and return.
3. Run `aitask_agent_marks.sh toggle` through a new app-level seam
   `async def _run_marks_cmd(self, args) -> tuple[int, str]`, implemented with
   `asyncio.create_subprocess_exec`. Tests override this one method.
   **Not** `TmuxMonitor._run_offloaded`: its docstring
   (`monitor_core.py:1246-1254`) states *"`fn` MUST be pure compute over plain
   data (invariant A)"* — spawning a subprocess through it would violate the
   seam's contract.
4. On `MARKED:`/`UNMARKED:` → invalidate the `MarksView` cache, `notify` the new
   state, `call_later(self._refresh_data)`.
   On `LOCK_BUSY` → warn "Marks file busy — try again"; change nothing.
   On `ERROR:` → warn with the message; change nothing.

No optimistic local toggle: a silently-diverging UI on `LOCK_BUSY` is worse than
a 2s worst-case wait that only occurs under contention.

**Read** — one `MarksView` per app, refreshed in `_refresh_data`
(`minimonitor_app.py:445`, `monitor_app.py:896`) right beside the existing
`update_session_mapping` call. A mark set in another repo appears within one
refresh tick (~3s) at the cost of one `os.stat` when unchanged.

The full monitor's fast path already recomputes card text every tick
(`monitor_app.py:1427-1430`), and the minimonitor rebuilds the whole list, so
both repaint marks for free.

### 6. Purge policy

Two filters, both **pure** and both applied on read every tick; materialized to
disk only periodically.

**(a) Age expiry** — drop entries older than `ttl_days` (default 2.0,
`AITASKS_AGENT_MARK_TTL_DAYS`). Needs no tmux visibility; it is the safe general
reaper.

**(b) Liveness — fail-closed, keyed on *successful enumeration*.**

The requirement is that a mark disappears when its agent window is gone — which
must happen promptly, not only after the 2-day TTL. So a session that was
enumerated successfully and simply has **no agent windows left** must count as
*observed-empty* and be swept. That is different from a session we could not see
at all, which must never be swept.

Distinguishing those two needs a fact the monitor does not currently expose.
`_discover_panes_multi{,_async}` (`monitor_core.py:1478-1513`) does
`if rc != 0: continue` — a session whose `list-panes` **failed** is silently
dropped and is therefore indistinguishable from a session with zero agents. And
in single-session mode `discover_panes` (`monitor_core.py:1515-1526`) lists only
`self.session`, while `get_session_to_project_mapping()` returns **every**
discovered aitasks session. Treating "discovered" as "observed" would, in
single-session mode, purge every other repo's marks on the first tick.

**Small addition to `monitor_core.py`:** record the sessions whose `list-panes`
returned `rc == 0` during the last discovery, and expose them:

```python
def last_enumerated_sessions(self) -> set[str]:
    """Sessions whose panes were successfully listed in the last discovery.

    NOT the same as the discovered-session set: a session whose `list-panes`
    failed is skipped by _discover_panes_multi, and single-session mode only
    ever lists `self.session`. Liveness purging must key on *successful
    enumeration*, because only that distinguishes "this session has no agents
    left" from "we could not see this session".
    """
```

Populated in all four discovery branches (multi sync/async, single sync/async);
empty on failure.

**It must NOT be ambient monitor-wide state.** `capture_all_classified_async`
reserves `gen = self._next_generation()` **before** awaiting
`discover_panes_with_shadows_async()` (`monitor_core.py:1986-1987`), refreshes
overlap, and only the commit is generation-guarded (`commit_snapshot` :1835,
`commit_snapshots` :2031 — both return `None` when superseded). A plain
`self._last_enumerated_sessions` assignment inside discovery would be unguarded:
a superseded older capture can finish discovery *after* a newer generation has
committed and overwrite the enumeration set. The newer tick's snapshots would
then be paired with the older tick's enumeration — and since the sweep decides
deletions from exactly that pairing, the mismatch purges live marks. This is
invariant B (loop-side, generation-guarded) from t1111_4.

**Carry it with the generation instead:**

- Discovery *returns* the successfully-enumerated session set rather than
  assigning it; `capture_all_classified_async` carries it alongside `gen` and
  `classified` (extend the returned tuple, or bundle the three into a small
  frozen dataclass — the latter reads better and stops the next field from
  growing another positional).
- `commit_snapshots` publishes `self._last_enumerated_sessions` **only on the
  branch where `gen == self._capture_generation`**, in the same commit that
  publishes the snapshots. Snapshots and enumeration then always originate from
  one generation, atomically.
- `tests/test_monitor_finalize_offload.py` pins this two-phase protocol and must
  be updated with the signature.

**Belt-and-braces (fail-closed):** at sweep time, if any captured snapshot's
`session_name` is absent from the published enumerated set, skip the sweep for
that tick. Any residual pairing mismatch is then inert — it can only cause a
*missed* purge, never a wrong deletion.

**The rule:**

```
sweepable = { realpath(mapping[s]) for s in last_enumerated_sessions() if s in mapping }
observed[root] = { window names of agent panes strictly resolved to root }   # may be empty

drop mark iff  mark.root ∈ sweepable  and  mark.window ∉ observed.get(mark.root, ∅)
```

plus one guard: **if any captured agent pane fails strict root resolution, skip
the sweep entirely for that tick.** `_root_for_snap` falls back to
`self._project_root` when a session is missing from the mapping; without this
guard a repo-A agent that failed to resolve would be absent from
`observed[rootA]` while `rootA` is still sweepable, and its live mark would be
deleted. A visibility gap must never be able to cause a deletion.

Fail-closed properties this preserves: a root whose session was not enumerated
(not running, enumeration failed, or on another tmux socket —
`AITASKS_TMUX_SOCKET`, default `-L ait`) is never in `sweepable`; and in
single-session mode `last_enumerated_sessions()` is at most `{self.session}`, so
other repos' marks remain structurally unpurgeable.

### Accepted limitations

- **Duplicate window names within one repo.** tmux permits two windows in a
  session to share a name, and the task specifies the window name as the
  identifier — so marking one marks both. Stated, not solved.
- **Clock skew.** `marked_at` is wall-clock epoch. A `~/.config` shared across
  machines with skewed clocks can expire a mark early or late by the skew.
  Bounded by the 2-day window; not worth a monotonic scheme.
- **TTL env hygiene.** A malformed or non-positive `AITASKS_AGENT_MARK_TTL_DAYS`
  falls back to the default rather than being honoured — a typo must not silently
  wipe every mark.

**Materialization.** Applying (a)+(b) only on read would let the file grow
forever; running the locked writer every 3s tick would spawn a subprocess per
tick. So: filter on every read (instant UX), and materialize via
`aitask_agent_marks.sh purge` once at mount and at most once every 10 minutes
thereafter.

That materialization runs through **`_run_marks_cmd`** — the same async
subprocess seam as the toggle, *not* `_run_offloaded`. (An earlier draft of this
plan said `_run_offloaded` here while simultaneously forbidding it for the
toggle; that was self-contradictory and would have either blocked the event loop
or violated the seam's pure-compute invariant.)

Scheduling is explicit per app, not implicit:

- `self._marks_purge_due_at: float` (monotonic), initialized to `0.0` so the
  first tick after mount purges; reset to `now + 600` after each completed run.
- `self._marks_purge_inflight: bool` — a tick that finds a run already in flight
  skips rather than stacking a second subprocess. Cleared in a `finally`, so a
  wrapper crash or timeout cannot wedge the scheduler permanently.
- The `observed` map is snapshotted **before** the await and passed to the
  wrapper explicitly (a temp file listing `root<TAB>window` lines), never read
  from ambient app state inside the callback — the snapshot the purge acts on
  must be the one it was scheduled with.

### 7. Docs

- `website/content/docs/tuis/minimonitor/how-to.md` — new "How to Mark an Agent
  as Prioritized" section; add `space` to the Key Bindings table (line ~216);
  extend "How to Read the Agent List" with the `★`/`☆` glyph; **fix the
  "truncated to 22 characters" line to 20**.
- `website/content/docs/tuis/monitor/how-to.md` — the matching how-to section.
- `website/content/docs/tuis/monitor/reference.md` — add `space` to the **Pane
  Interaction** table (line ~24), context "Pane list zone". Note the monitor's
  key table lives in `reference.md`, not `how-to.md`.

Document the store path, the env overrides, and the purge policy (both the age
window and the fail-closed liveness rule) in user-facing terms.

## What is deliberately NOT generalized for t1343

`t1343_parallel_agent_file_conflict_advisory` adds a second, independent mark to
the same rows. It is *derived, repo-local, ephemeral*; this one is *user intent,
per-user, cross-repo, durable*. They do not belong in the same file, so the JSON
schema is **not** generalized into a multi-kind container.

What t1343 does reuse, unchanged: the `format_*_glyph(...) -> str` helper shape
and its placement in `monitor_shared.py`; the leftmost-glyph row layout and its
width budget; the `(realpath(root), window_name)` identity; and the
guarded-action + `_run_offloaded` + `call_later(_refresh_data)` toggle idiom.
Whichever glyph and key t1343 picks must stay distinguishable — `x`, `f`, `g`,
`b`, `v`, `w`, `y` remain free in both TUIs after this task takes `space`.

**Bookkeeping:** t1326 points at t1343, but the reverse pointer is not confirmed.
Check `t1343_parallel_agent_file_conflict_advisory` and, if it does not already
reference t1326, add a short note recording the glyph/key/plumbing this task
settled — coordination links should be bidirectional.

## Tests

| File | Kind | Covers |
|---|---|---|
| `tests/test_agent_marks.py` *(new)* | Python `unittest` | schema round-trip; unknown `version` → unreadable + never overwritten; realpath canonicalization via a symlinked root; toggle on/off + `marked_at`; TTL boundary (under / at / over); corruption matrix (malformed, truncated, path-is-dir, unreadable) proving `load_safe` empty-and-silent vs `load` raising; `(st_mtime_ns, st_size)` gate does not re-read when unchanged |
| `tests/test_agent_marks_liveness.py` *(new)* | Python `unittest` | the sweep rule and, critically, the **three-way distinction**: (i) session enumerated with the window present → survives; (ii) session enumerated, window gone → **purged** (this is the requirement the old rule failed); (iii) session **not** enumerated → survives regardless. Plus the unresolved-pane guard: one unresolvable pane suppresses the whole sweep |
| `tests/test_agent_marks_concurrency.sh` *(new)* | bash | modelled on `tests/test_gate_lock_characterization.sh`: 6 background `toggle` writers on distinct windows + `wait`; assert all 6 present **exactly once** (no lost update, no duplication); per-contender stderr dumped on anomaly; lock dir released. Plus a held-lock case asserting `LOCK_BUSY`, exit 3, and **zero** file mutation |
| `tests/test_monitor_agent_marks.py` *(new)* | Python `unittest` + `run_test()` | **Render:** `format_mark_glyph` markup for both states; both card builders; mounted `PaneCard.render().plain` contains `★`. **Surface:** `("space","toggle_mark")` in both `BINDINGS`; `#mini-key-hints` still ≤ `_HINT_WIDTH_BUDGET` (38) and mentions the key; `check_action` disables the binding outside `Zone.PANE_LIST` |
| `tests/test_monitor_agent_marks_action.py` *(new)* | Python `unittest` | **Seam-level action contract, for BOTH apps.** Override `_run_marks_cmd` with a recording double and assert: (a) a card belonging to a *different* session resolves its own strict root — not `self._project_root` — and the wrapper is invoked with **exactly** `[<script>, "toggle", <that root>, <that window>]`, asserted token-by-token, not by substring; (b) a card whose session is absent from the mapping produces **no** invocation and a warning; (c) each of `MARKED:` / `UNMARKED:` / `LOCK_BUSY` / `ERROR:` produces its correct notification and cache/repaint behaviour, and the three non-success outcomes mutate nothing. Without this, a wrong-root write or a dead notification path passes the whole suite |
| `tests/test_monitor_modal_space_dispatch.py` *(new)* | Python `unittest` + `run_test()` | **Real event dispatch, both TUIs.** Push an actual `ModalScreen`, then `await pilot.press("space")`, and assert `_run_marks_cmd` was never invoked. Calling `action_toggle_mark()` directly proves nothing about how Textual *routes* the key — this must go through the real entry point. Also the positive control: with a `PaneCard` focused and no modal, `pilot.press("space")` **does** invoke the seam, so the test is shown to discriminate |
| `tests/test_agent_marks_generation.py` *(new)* | Python `unittest` | **Interleaving.** Drive two overlapping captures where the **older** generation's discovery resolves *after* the newer one has committed — gated with `asyncio.Event`, never sleeps, per `aidocs/framework/testing_conventions.md`. Assert (a) the published enumerated set is the **newer** generation's, (b) the superseded commit publishes nothing, and (c) no mark is purged on the basis of the stale set. Negative control: publish enumeration unguarded (ambient assignment) and confirm the test FAILS |
| `tests/test_monitor_finalize_offload.py` | update | pins the two-phase `capture_all_classified_async` / `commit_snapshots` generation protocol; the carried enumeration set changes that signature |
| `tests/test_monitor_shadow_status.py`, `tests/test_monitor_completed_status.py` | update | both assert on exact agent-row strings and on `plain.index()` ordering; the new leading glyph shifts them |
| `tests/test_multi_session_minimonitor.sh` **and** `tests/test_multi_session_monitor.sh` | update | the cross-root collision case in **both**, as the acceptance criteria require: two fake roots whose sessions both fall back to the name `"aitasks"` — a mark in one must not render in the other. The two apps have independent refresh and root-resolution paths (sync `get_session_to_project_mapping` in the minimonitor, async in the monitor), so covering one does not cover the other |

## Verification

1. `bash tests/test_agent_marks_concurrency.sh` — expect its own `Results:` line.
2. `shellcheck .aitask-scripts/aitask_agent_marks.sh`
3. `bash tests/run_all_python_tests.sh` — **read only the last line**
   (`PYTHON SUITE: PASSED|FAILED`); it goes to stderr, and piping discards the
   exit status.
4. **Negative controls (two, because the rule now has two failure directions).**
   Each must be shown to make the suite exit 1, then restored by undoing the
   mutation only — never `git checkout`, which would also revert unrelated
   in-flight edits.
   - Replace `last_enumerated_sessions()` with the full discovered-session set.
     The "session not enumerated → mark survives" case must FAIL (this is the
     over-deletion direction, the dangerous one).
   - Restore the old "root needs ≥1 observed pane" gate. The "session enumerated
     with zero agents → mark purged" case must FAIL (the under-deletion
     direction, i.e. the requirement concern 2 identified as unmet).
5. **Live cross-repo check (real terminal, not a claim):** two tmux sessions in
   two different repos on the `ait` socket; mark an agent in repo A's
   minimonitor; capture repo B's minimonitor pane with tmux and confirm the `★`
   appears within one refresh tick. Also capture at 40 columns to confirm the row
   still reads after the width change.
6. Restart a TUI and confirm the mark survives; check the file is mode 0600.

## Risk

### Code-health risk: medium

- This is the **first persisted state for the monitor TUIs** and the first
  per-user cross-repo file *written* from a Python TUI. Blast radius: 2 new
  files, 3 modified source files (`monitor_shared.py`, `minimonitor_app.py`,
  `monitor_app.py`), 3 doc files, 2 existing test files updated. · severity: medium · → mitigation: none needed (covered by this task's own tests)
- A bare `space` App binding stays in Textual's binding chain while a
  `ModalScreen` is pushed, so any modal lacking its own space handler could
  toggle a mark invisibly behind the dialog. The live-focus guard addresses it,
  and a real-event-dispatch test now pins it **in this task**; the follow-up
  generalizes the audit to the other bare single-key bindings, which this task
  does not touch. · severity: medium · → mitigation: monitor_modal_binding_guard_audit
- The minimonitor row already reaches ~42 columns in its worst case against ~38
  usable; adding 2 columns and shrinking the name budget 22→20 is a visible,
  bounded UX regression that only a real narrow-terminal capture can falsify. · severity: low · → mitigation: minimonitor_row_width_audit
- The liveness rule forces a change to `monitor_core.py`'s **two-phase capture
  generation protocol** (threading the enumerated-session set through to the
  guarded commit) — the concurrency core of both TUIs, and the widest-reaching
  edit in this task. Bounded by the fail-closed mismatch check, which makes any
  residual pairing error cause a *missed* purge rather than a wrong deletion,
  and pinned by an interleaving test with a negative control. · severity: medium · → mitigation: none needed (covered in-task)
- File-level concurrency is delegated to the proven `registry_lock.sh` rather
  than reimplemented, which is what keeps this from being high. · severity: low · → mitigation: none needed

### Goal-achievement risk: medium

- The fail-closed liveness rule is the requirement most likely to be delivered
  subtly wrong: it interacts with single- vs multi-session mode, the
  `_root_for_snap` fallback, and socket scoping. The design tightens it, but its
  real behaviour is only observable with several genuine repos and tmux sessions —
  which no existing test harness sets up. · severity: medium · → mitigation: agent_marks_multirepo_tmux_test
- Cross-repo visibility itself is low-risk: it follows by construction from a
  per-user path plus an mtime-gated per-tick re-read. · severity: low · → mitigation: none needed

### Planned mitigations
- timing: after | name: agent_marks_multirepo_tmux_test | type: test | priority: medium | effort: medium | addresses: goal-achievement — fail-closed liveness rule | desc: Tier-2 real-tmux harness with two fake repos and two sessions on an isolated socket, asserting cross-repo mark visibility and that killing a session never drops its marks
- timing: after | name: monitor_modal_binding_guard_audit | type: test | priority: medium | effort: low | addresses: code-health — bare single-key App bindings fire under a pushed modal | desc: Generalize the guard beyond `space` — audit every bare single-key App binding in both monitor TUIs for modal leakage and pin the ones that are unguarded
- timing: after | name: minimonitor_row_width_audit | type: chore | priority: low | effort: low | addresses: code-health — minimonitor row width regression | desc: Audit the minimonitor agent row at 40 columns across every glyph combination and shed context until it reads

## Post-Review Changes

### Change Request 1 (2026-07-30)

- **Requested by user:** use white, not yellow, for the filled `★` when an agent
  is marked.
- **Changes made:** `format_mark_glyph` now returns `[bold white]★[/]`. This is a
  deliberate departure from the repo-wide marked=bold-yellow convention
  (`brainstorm/widgets.py`, `_ConcernRow.render`), and the better call: those
  marks live in pickers where nothing else on the row is state-coloured, whereas
  this one sits two columns from the agent's `●`, which `_state_color` paints
  **yellow for IDLE**. A yellow ★ beside a yellow ● read as one state cluster
  and invited "is that agent idle, or flagged?". White belongs to no rung of the
  state ladder (magenta / dodger_blue1 / yellow / green), which is what makes it
  legible as *user intent* rather than status. The docstring now records that
  reasoning so the divergence does not look accidental.
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`,
  `tests/test_monitor_agent_marks.py` (assertion + test renamed
  `test_marked_is_bold_white_star`).

### Change Request 2 (2026-07-30) — review concerns

All six verified against the source; all six valid; all six fixed (the two
"follow-up" dispositions were cheap enough to land here rather than defer).

1. **[high, CONFIRMED] Liveness derived from `_snapshots` could delete a live
   mark.** `commit_snapshots` drops any pane whose *content capture* failed
   (`monitor_core.py:2101`, `if result is None: continue`), so `_snapshots` is
   "panes we successfully read", not "panes that exist". A transient capture
   failure on one agent, while a sibling kept its root sweepable, would purge
   the failed agent's live mark. My earlier reasoning ("a tmux session always
   has ≥1 pane") conflated *discovery* with *capture* — the plan's original
   design was right and I was wrong to drop it.
   **Fix:** `TmuxMonitor` now records `(enumerated_sessions, discovered_agents)`
   at **discovery** time, keyed by capture generation
   (`_record_discovery_facts`), and `commit_snapshots` promotes them
   (`_publish_discovery_facts`) only past its generation guard — atomically with
   the snapshots. Keying by `gen` rather than assigning a bare attribute is what
   makes a superseded older discovery inert. Exposed as
   `last_enumerated_sessions()` / `last_discovered_agents()`;
   `_collect_marks_observation` reads those and never `_snapshots`. A monitor
   that cannot report them fails closed (nothing sweepable).
   Pinned by `tests/test_agent_marks_generation.py` (8 tests, incl. an
   older-finishes-after-newer interleaving case) and
   `test_agent_whose_capture_failed_is_still_observed`.

2. **[medium, CONFIRMED] `MarksView` staleness.** Reproduced: an equal-length
   `os.replace` within one coarse timestamp left `(st_mtime_ns, st_size)`
   unchanged, so another repo's final state stayed invisible indefinitely.
   **Fix:** the stamp is now `(st_mtime_ns, st_size, st_ino)`. Every
   `os.replace` yields a new inode, making the stamp replacement-sensitive by
   construction. `GateSummaryCache`'s pair is fine for in-place rewrites; this
   store is only ever atomically replaced, which is the difference.

3. **[medium, CONFIRMED] Seam had no timeout and no normalised failure.** A
   missing wrapper raised `OSError` out of `action_toggle_mark` on a keypress,
   and a child that never exits would hang `communicate()` so
   `_maybe_purge_marks`'s `finally` never cleared `_marks_purge_inflight` —
   directly contradicting that method's documented guarantee.
   **Fix:** `_run_marks_cmd` is now total — `asyncio.wait_for` with
   `_MARKS_CMD_TIMEOUT = 20s` (above the wrapper's own 2s/10s lock timeouts so a
   contended-but-healthy writer reports `LOCK_BUSY` itself), kill-and-reap on
   timeout, and `OSError` normalised to `ERROR:…`.

4. **[low, CONFIRMED] Version 0 was accepted and silently upgraded.** The guard
   was `version > SCHEMA_VERSION`. **Fix:** exact equality — rewriting an older
   version *is* a migration and none exists.

5. **[low, CONFIRMED] `md5sum` is absent on stock macOS.** **Fix:** the
   concurrency test now uses `cmp -s` against a saved copy.

6. **[low, CONFIRMED] `AITASKS_AGENT_MARKS_FILE` undocumented.** **Fix:** both
   how-to pages now name it beside the default path.

Negative controls for the two blocking fixes, both shown to fail on exactly the
intended tests: reverting the stamp to `(mtime, size)` breaks the staleness
test; deriving the agent set from `_snapshots` breaks
`test_agent_whose_capture_failed_is_still_observed`.

### Change Request 3 (2026-07-30) — enumeration must not be pane-derived

**[medium, CONFIRMED, blocking]** After Change Request 2, `enumerated_sessions`
was still *inferred* from the post-filter `panes + shadows`. `_parse_list_panes`
drops a companion pane sitting in an agent-named window (`category == AGENT and
_is_companion_process(pid)`), so the moment an agent exits and only its
minimonitor split remains, that session parses to **zero panes** — and was
therefore published as *unenumerated*, leaving it un-sweepable and stranding the
departed agent's mark until TTL expiry. That is precisely the case the prompt
purge exists for.

I had spotted this residue during Change Request 2 and waved it through as
"benign fail-closed". That was the wrong call: it is fail-closed against
*deleting* a mark, but it silently defeats the feature's main purpose.

**Fix:** the successful `rc == 0` session set is now tracked inside discovery
itself — `_discover_panes_multi{,_async}` return
`(panes, shadows, enumerated_sessions)`, and the single-session branch reports
`{self.session}` on `rc == 0` — entirely independently of what survives parsing
and filtering. It reaches the caller through a **caller-owned sink**
(`discover_panes_with_shadows_async(*, enum_sink=...)`) rather than the return
value or an instance attribute:

- the 2-tuple return is a widely-stubbed seam (13 test doubles patch it), so its
  shape stays untouched;
- binding the value to *this* call is what stops an overlapping discovery from
  handing its answer to the wrong capture generation — an instance attribute
  would reintroduce exactly the pairing hazard Change Request 2 closed.

`_record_discovery_facts` takes the set explicitly and falls back to the
pane-derived approximation only when a caller cannot supply it (stubbed
discovery in tests).

Tested through the **real** discovery path, as the concern asked:
`RealDiscoveryEnumerationTests` drives `_parse_list_panes` with a list-panes
payload containing only an excluded companion pane and asserts the session is
still enumerated — plus the end-to-end case through the generation-guarded
commit. Negative control: forcing the pane-derived inference makes
`test_companion_only_session_reaches_the_published_facts` fail.

### Change Request 4 (2026-07-30) — seam doubles broken by the sink

**[medium, CONFIRMED, blocking]** Change Request 3 preserved the discovery
seam's 2-tuple *return* but changed its *invocation*:
`capture_all_classified_async` now always passes `enum_sink=`, while ten test
doubles across five files replaced it with zero-argument coroutines. Those
raised `TypeError: unexpected keyword argument 'enum_sink'` inside the capture
task — and because several of the affected suites are event-driven, the crash
did not surface as a clean failure but **hung** them
(`test_monitor_finalize_offload` had to be killed at a 2-minute timeout).

Two process failures of mine, worth recording:
1. I identified this exact risk when choosing the sink design ("doubles would
   break on the unexpected kwarg") and then did not update them.
2. I had launched the affected suites in the background and reported progress
   without noticing the log was empty **because the run was hung**. An empty log
   is a signal, not a neutral "still running".

**Fix:** every double now takes `*, enum_sink=None` and populates it from the
panes it returns, mirroring the real seam. Explicit keyword rather than
`**kwargs` on purpose — `**kwargs` would silently swallow a future rename of the
parameter, recreating this failure in a form no test would catch.

Doubles updated: `test_monitor_shadow_status.py` (2),
`test_monitor_shadow_zone.py` (1 + three `_no_shadows`),
`test_monitor_finalize_offload.py` (1), `test_shadow_seam.py` (1 +
`slow_discovery` + the `_discovery` factory), `test_monitor_concern_action.py`
(1). A grep for zero-argument discovery doubles now returns none.

**Lesson applied to verification:** a targeted suite selection is what let this
through, so the full Python suite — not a curated subset — is the gate before
this task is reported as verified.

## Final Implementation Notes

- **Actual work done:** New `.aitask-scripts/lib/agent_marks.py` (lock-free store
  + policy + CLI) and `.aitask-scripts/aitask_agent_marks.sh` (the only writer,
  holding `registry_lock.sh`). `format_mark_glyph` plus a shared
  `AgentMarksMixin` in `monitor_shared.py`, mixed into both apps; `space`
  binding, async `action_toggle_mark`, per-tick read and a scheduled purge.
  Six new test files, four existing suites updated, three doc files.

- **Deviations from plan:**
  1. **[SUPERSEDED by Change Request 2 — this reasoning was wrong.]**
     **No `monitor_core.py` change; `last_enumerated_sessions()` never built.**
     The plan threaded a new enumerated-session set through the two-phase
     capture protocol to avoid a generation-pairing hazard. That turned out to
     be unnecessary: `_parse_list_panes` returns panes of *every* category and a
     tmux session always has ≥1 pane, so
     `{snap.pane.session_name for snap in _snapshots.values()}` **is** the
     successfully-enumerated set — a failed `list-panes` contributes nothing.
     Since `_snapshots` is what `commit_snapshots` publishes under the
     generation guard, enumeration and snapshots are the same object and cannot
     be mismatched. **This was wrong**: `_snapshots` omits panes whose content
     capture failed, so it is not the discovered-pane set. Review concern 1
     caught it; the plan's original design was reinstated, and
     `tests/test_agent_marks_generation.py` now exists after all. Recorded here
     rather than deleted so the mistake is visible: "a tmux session always has
     ≥1 pane" was a fact about tmux, not about the capture pipeline.
  2. **`AgentMarksMixin` instead of parallel edits.** ~180 lines shared by both
     apps rather than duplicated.
  3. **No allow-list entries and no `ait` dispatcher case.** Per
     `aidocs/framework/aitasks_extension_points.md`, the 7-touchpoint whitelist
     applies only to helpers invoked from a SKILL.md; this one is called solely
     by the Python TUIs (the `aitask_skill_invalidate.sh` precedent).
  4. **Modal-safety rationale corrected.** The plan (and my first
     implementation comment) claimed the live-focus guard is what stops `space`
     leaking through a pushed modal. A negative control disproved it: Textual
     does not dispatch App-level `BINDINGS` while a `ModalScreen` is active, so
     the modal tests stay green with the guard removed. The comment and test
     docstring now attribute the protection correctly, the modal tests are
     documented as a regression pin on Textual's behaviour, and
     `test_space_with_focus_off_the_card_does_not_toggle` was added — that one
     *does* fail under the mutation and is the guard's real justification.
  5. **Negative-control target corrected.** The plan named the single-root
     "session not enumerated" case as the over-deletion control. It does not
     discriminate: with an empty `sweepable_roots` the early return fires first,
     so it passes under the broken implementation too. The mixed-root tests are
     the real control; the module docstring says so explicitly.
  6. **Width is column-neutral, not a net cost.** Verified by real tmux capture
     at 40 columns: the mark adds 2 columns and the name cap 22→20 removes 2, so
     the worst-case row wraps exactly as much as it did before.

- **Issues encountered:**
  - **A real defect the tests caught:** `_strict_root_for_snap` originally
    called the **sync** `get_session_to_project_mapping()` — once per row, per
    tick — putting a potential blocking tmux round-trip on the full monitor's
    refresh path. `tests/test_monitor_refresh_no_sync_tmux.py` exists precisely
    to trip that and did. Fixed by publishing the mapping once per tick via
    `_set_session_root_map`, fed from the value each app already fetches (the
    **async** variant in the full monitor). This also removed an O(rows) lookup.
  - A test bug that a positive control caught: `calls.extend(inner_list)` copied
    an empty list, so the modal dispatch test was passing vacuously. Fixed by
    passing the recording list by identity.

- **Upstream defects identified:**
  - `tests/test_multi_session_minimonitor.sh:188,272,332 — three `__new__`-built
    app stubs omit `_completed_pane_ids`, which `_agent_card_text` /
    `_rebuild_session_bar` have read since t1322; every `_rebuild_pane_list`
    case in the file raised AttributeError before its assertions ran. The suite
    was already red at HEAD (verified against `git show HEAD:` — the stub cannot
    satisfy HEAD's code either). Repaired here since the file had to be touched
    anyway; not a separate task.
  - `website/content/docs/tuis/monitor/reference.md:45 — documents `a` for
    auto-switch while `monitor_app.py` binds `A` (uppercase). Pre-existing doc
    drift, untouched.
  - `tests/test_board_work_report.py:483 — `test_hidden_cards_still_listed`
    fails deterministically (`147 != 148`): `WorkReportTaskSelectScreen`'s
    SelectionList shows one fewer option than `get_column_tasks()` returns for
    the same column, so exactly one task in a 148-task column is silently
    unselectable in the work report. Not caused by t1326 — the board imports
    nothing this task touched (verified by grep) and the assertion is a pure
    task-data count. Reproduced twice with identical numbers, so it is a stable
    defect rather than a flake. Worth its own bug task.

- **Key decisions:** identity is `(realpath(project_root), window_name)` — never
  the session name, which is not unique across repos; the store is JSON so the
  reader needs no PyYAML; read fails safe / write fails loud; the liveness sweep
  is gated on *successful enumeration* so an enumerated-but-empty session purges
  promptly while an unobservable one never does.

## Post-implementation

Step 9 of the shared workflow handles cleanup, merge, and archival.

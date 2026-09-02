---
Task: t1686_companion_pane_filter_misses_shell_hosted_monitor.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1686 — Companion pane filter misses a shell-hosted monitor

## Context

`ait minimonitor` / `ait monitor` render an agent window **twice**: the real
agent card plus a second AGENT card carrying the same window name. Observed live
on `agent-pick-1677` and `agent-pick-1683`.

`monitor_core._is_companion_process(pid)` decides "is this pane a
minimonitor/monitor companion?" by matching `/proc/<pid>/cmdline` against
`_COMPANION_KEYWORDS`. The pid it gets is tmux's `#{pane_pid}` — the pane's
**top-level** process. When a companion is launched as the pane's start command
that *is* the Python process and the match works; when a user restarts the
companion **from an interactive shell inside the pane**, `#{pane_pid}` is
`-bash` and `minimonitor_app.py` is a child. The match fails, the pane survives
discovery, `classify_pane(window_name)` matches the `agent-` prefix, and the
companion is rendered as a full agent card indistinguishable from its agent.

Every companion already stamps `@aitask_monitor_kind = "<kind>:<pid>"` on its own
pane, and that pid is the **app's own** — exactly the one the cmdline heuristic
cannot reach. `.aitask-scripts/lib/monitor_marker.py` (t1451) is the canonical,
single implementation of the marker's parse + liveness rule, already consumed by
`aitask_companion_cleanup.sh` and `agent_launch_utils.maybe_spawn_minimonitor`.
Monitor **discovery** is the one place that never consults it.

Outcome: make the marker the **primary** companion signal at all three blind call
sites, keep the cmdline heuristic as a live fallback rung, and reuse
`monitor_marker.py`'s verdicts rather than re-deriving them.

## Scope — three call sites

| site (`.aitask-scripts/monitor/monitor_core.py`) | consequence today |
|---|---|
| `_parse_list_panes` (~2003) via `_is_companion_pane` (~1951) | the duplicate agent card — the reported symptom |
| `find_companion_pane_id` (~2984) | returns `None`, so `switch_to_pane(prefer_companion=True)` cannot locate a shell-hosted companion |
| `kill_agent_pane_smart` (~3029) | `is_helper` False ⇒ `count_other_real_agents` sees a phantom agent ⇒ kill downgraded from kill-**window** to kill-**pane**, orphaning the window. **Plus a pre-existing latent defect in the same loop** — see step 5 |

**Naming note:** the task's acceptance criteria name
`_find_companion_pane_in_window`; the function in the tree is
`find_companion_pane_id` (`monitor_core.py:2984`). Same function, same defect —
the AC is satisfied by fixing it.

Deliberately **out of scope**: `_WINDOW_PANES_FORMAT` / `_parse_window_panes`
(the 8-field `discover_window_panes` path). Its only consumer,
minimonitor's `_check_auto_close`, asks "is any *other* pane left in my window?"
— agent-ness never enters, so the marker would change nothing there.

---

## Implementation

### Pre-phase (risk mitigations)

1. `[assert_fixture_rows_parsed]` **Before touching any stub arity**, add a
   positive-presence assertion to every test that hand-builds `list-panes` rows
   (`tests/test_agent_marks_generation.py`,
   `tests/test_monitor_refresh_no_sync_tmux.py`,
   `tests/test_monitor_shadow_status.py`, `tests/test_multi_session_monitor.sh`,
   `tests/test_multi_agent_window_substrate.sh`): each fixture must assert that
   its rows actually **produced** panes (or the exact expected non-empty pane-id
   set), not merely an expectation an empty parse would also satisfy. Run them
   green at the OLD arity first, so the assertions are known-live before the
   format widens — that is what makes step 7's sweep verifiable rather than
   hopeful.

### 1. `monitor_core.py` — import the canonical rule

`lib/` is already on `sys.path` (module header). Import the marker seam
**directly from `monitor_marker`**, not via `agent_launch_utils`' re-export —
`monitor_marker` is stdlib-only and is the module that owns the rule:

```python
from monitor_marker import MONITOR_KIND_OPTION, monitor_marker_alive  # noqa: E402
```

### 2. `monitor_core.py` — one pure predicate, mirroring `is_shadow_target`

Add next to `is_shadow_target` (~353), in the companion block near
`_COMPANION_KEYWORDS`:

```python
def is_live_companion_marker(monitor_kind: str) -> bool:
    """True when a pane's ``@aitask_monitor_kind`` proves a LIVE companion.

    Pure, like :func:`is_shadow_target`: takes the already-read option value so
    the tmux read stays at the call site. The parse + liveness rule is NOT
    re-derived here — it is `monitor_marker.monitor_marker_alive`, the single
    implementation the guards and `aitask_companion_cleanup.sh` already use
    (t1451). A *stale* marker (recorded pid provably gone) is deliberately not a
    companion; a non-empty value that does not parse is `present` per that
    module's "unverifiable is not absence" rule.
    """
    return monitor_marker_alive(monitor_kind.strip())
```

`.strip()` first so a whitespace-only value reads as *absent* rather than as the
unparseable-⇒-present case (tmux emits `""` for an unset option;
`monitor_marker_alive("")` is already `False`).

Also update `_COMPANION_KEYWORDS` / `_is_companion_process`' docstring to say it
is now the **fallback** rung, reached only when the marker is absent or stale.

### 3. `_LIST_PANES_FORMAT` — append the marker field (index-stable)

```python
_LIST_PANES_FORMAT = "\t".join([
    ...,
    "#{@aitask_shadow_target}",   # shadow helper marker (t986); "" when unset
    "#{history_size}",            # scrollback-growth work signal (t1159_2)
    f"#{{{MONITOR_KIND_OPTION}}}",  # companion marker (t1686); "" when unset
])
```

**Appended, not inserted next to `@aitask_shadow_target`.** Inserting would shift
`history_size` and make every existing 10-field stub parse its history value as a
marker — a silent reinterpretation. Appending keeps `parts[0..9]` stable.

Replace the inline arity literal with a named constant carrying the era map:

```python
#: Accepted `list-panes` record arities. 11 = current (t1686 marker); 10 =
#: pre-marker; 9 = pre-`history_size` (t1159_2). The set is CLOSED on purpose:
#: an unexpected arity is dropped, so a stub that drifts out of the set fails
#: loudly-by-absence rather than being reinterpreted field-by-field.
_LIST_PANES_ARITIES = (9, 10, 11)
```

and in `_parse_list_panes`:

```python
if len(parts) not in _LIST_PANES_ARITIES:
    continue
...
monitor_kind = parts[10] if len(parts) > 10 else ""
```

### 4. `_is_companion_pane` — marker primary, memo guards only the fallback

```python
def _is_companion_pane(
    self, pane_id: str, pane_pid: int, session: str, monitor_kind: str = "",
) -> bool:
    # Primary signal: the pane's own marker (t1686). Evaluated fresh on every
    # tick and DELIBERATELY NOT memoized — the memo exists to bound the cost of
    # `_is_companion_process`' /proc (or `ps`) read, and `monitor_marker_alive`
    # is a single `os.kill(pid, 0)`. Caching it would re-introduce a window in
    # which a companion that has exited (marker now stale, shell pane still
    # alive) stays hidden for the rest of the TTL — exactly the staleness the
    # marker exists to resolve.
    if is_live_companion_marker(monitor_kind):
        return True
    # Fallback rung: cmdline identity, memoized POSITIVE-ONLY as before.
    ...unchanged body...
```

The positive-only asymmetry (a launcher pane `exec`s into the app under an
unchanged pid) is preserved verbatim — only the fallback path touches the memo.
Call site in `_parse_list_panes` passes `monitor_kind`.

### 5. Both single-window readers: stop stripping the record's last field

**Blocking prerequisite for steps 6 and 7.** `find_companion_pane_id`
(`monitor_core.py:2996`) and `kill_agent_pane_smart` (`:3053`) iterate
`stdout.strip().splitlines()`. `str.strip()` acts on the **whole** buffer, so it
eats the trailing tab of the **last** record when that record's final field is
empty — the interior lines keep theirs only because a `\n` follows. Measured:

```
"%1\t111\t\n%2\t222\t\n%3\t333\t\n"
  .strip().splitlines() -> 3, 3, 2 fields    # last record loses a field
       .splitlines()    -> 3, 3, 3 fields
```

A record short of the expected arity hits the `continue` and vanishes.

- **`find_companion_pane_id` is safe only by accident today** — its last field is
  `#{pane_pid}`, never empty. Appending `@aitask_monitor_kind` breaks it: an
  **unmarked** companion listed last would no longer reach the cmdline fallback,
  silently defeating step 7's whole fallback rung for the last pane in a window.
- **`kill_agent_pane_smart` is ALREADY BROKEN** — its format already ends in
  `#{@aitask_shadow_target}`, which is empty for every non-shadow pane, so the
  last-listed pane is dropped from `records` whenever it is unmarked. If that
  pane was the only other real agent, `count_other_real_agents` returns 0 and the
  **whole window is killed with a live agent still in it.** This is a
  pre-existing latent defect, not one this task introduces; it is fixed here
  because it sits inside AC 2's call site and step 8 would otherwise entrench it.
  `tests/test_kill_agent_pane_smart.sh` misses it because its fixture creates the
  companion **last**, and dropping a *helper* changes no count — a vacuous pass.

Fix both, identically, and mirror `_parse_list_panes`' existing comment:

```python
for line in stdout.splitlines():
    if not line.strip():
        continue          # blank lines are not records
    parts = line.split("\t")
```

`_parse_list_panes` (`:2025`) already iterates bare `splitlines()` for exactly
this reason. `_parse_window_panes` (`:2231`) still strips, but its last field is
`#{pane_height}` — never empty — so it is deliberately left alone; a future
appended optional field there must revisit it.

### 6. `find_companion_pane_id` — read the marker in the same round trip

```python
fmt = f"#{{pane_id}}\t#{{pane_pid}}\t#{{{MONITOR_KIND_OPTION}}}"
...
if len(parts) != 3:
    continue
pane_id_str, pid_str, monitor_kind = parts
...
if is_live_companion_marker(monitor_kind) or _is_companion_process(pid):
    return pane_id_str
```

Keep the `int(pid_str)` `ValueError` guard, but evaluate the **marker before**
it so a malformed pid cannot suppress a valid marker verdict.

### 7. `kill_agent_pane_smart` — the behavioural half of the defect

```python
"-F", f"#{{pane_id}}\t#{{pane_pid}}\t#{{@aitask_shadow_target}}\t#{{{MONITOR_KIND_OPTION}}}",
...
if len(parts) != 4:
    continue
other_id, pid_str, shadow_target, monitor_kind = parts
...
is_helper = (
    is_shadow_target(shadow_target)
    or is_live_companion_marker(monitor_kind)
    or _is_companion_process(pid)
)
```

`count_other_real_agents` is unchanged — helper classification stays at the
caller, as its docstring requires.

### 8. Test-stub arity sweep (every hand-built `list-panes` line)

Any stub left at an arity outside the closed set is silently `continue`d, i.e.
its test passes **vacuously**. Sweep all of them, in the same commit:

| file | site |
|---|---|
| `tests/test_monitor_companion_filter.py` | `_row()` |
| `tests/test_agent_marks_generation.py` | `_row()` + the stale `_FIELDS = 9` constant and its comment (already wrong: the format is 10 fields) |
| `tests/test_monitor_refresh_no_sync_tmux.py` | the inline `"0\tagent-1\t0\t%1\t12345\tbash\t80\t24\t"` literal |
| `tests/test_monitor_shadow_status.py` | `_list_panes_line()` |
| `tests/test_multi_session_monitor.sh` | three `make_row()` bodies (lines ~72, ~288, ~330) |
| `tests/test_multi_agent_window_substrate.sh` | the `FMT_LINE([...])` fixture rows + the `FMT_LINE` comment |

Each builder gains a `monitor_kind: str = ""` keyword and emits 11 fields.

**Keep the deliberate legacy rows.** `test_multi_agent_window_substrate.sh`
asserts a 9-field row parses with `history_size None` — that assertion stays, and
a 10-field row is added alongside it so both legacy rungs remain executable.

`tests/test_minimonitor_auto_close_guard.py` builds 8-field
`_WINDOW_PANES_FORMAT` rows — **not** touched (different format, out of scope).

### 9. New coverage — `tests/test_monitor_companion_filter.py`

Real pids drive the marker so the canonical rule is genuinely exercised (no
patching of `monitor_marker_alive` — the AC requires it be *called*):

- `_LIVE_PID = os.getpid()`.
- `_DEAD_PID`: spawn `subprocess.Popen([sys.executable, "-c", ""])`, `wait()`,
  reuse its pid. **Fixture guard:** assert
  `monitor_marker_state(f"minimonitor:{_DEAD_PID}") == "stale"` at setup, so a
  recycled pid fails the fixture instead of silently softening the test.

New tests:

1. **`test_shell_hosted_companion_is_filtered_by_marker`** — marker
   `minimonitor:<live>`, `_is_companion_process` returns **False** for the pane
   pid (the `-bash` case). Pane must be absent from `panes` and from
   `_pane_cache`. *This is the reported defect; it fails against today's code.*
2. **`test_marker_is_primary_cmdline_not_consulted`** — with a live marker the
   `_CompanionSpy` records **zero** calls for that pid.
3. **`test_unmarked_companion_still_filtered_by_cmdline`** — marker `""`,
   `_is_companion_process` True ⇒ filtered. The negative control proving the
   fallback rung is reachable, not dead code (`App.run_test()` mounts pass
   `mark_pane=False`).
4. **`test_stale_marker_is_not_a_companion`** — marker
   `minimonitor:<dead>`, cmdline non-companion ⇒ pane **survives** as an agent.
5. **`test_marker_verdict_is_not_memoized`** — tick 1 live marker (filtered);
   tick 2 same pane/pid, marker now `""` and cmdline non-companion ⇒ pane
   reappears **immediately**, with no clock advance. Discriminates decision 4.
6. **`test_wrong_arity_row_is_rejected`** — a 12-field row and an 8-field row are
   both dropped, while an 11-field row parses. Pins the closed arity set so a
   drifted stub cannot be swallowed.
7. **`test_find_companion_pane_id_resolves_shell_hosted_companion`** — stub
   `tmux_run` to return `%1\t<agent pid>\t` + `%2\t<bash pid>\tminimonitor:<live>`
   with `_is_companion_process` False ⇒ returns `%2`. (AC 3.)
8. **`test_kill_smart_collapses_window_for_shell_hosted_companion`** — seed
   `_pane_cache`, stub `tmux_run` to list one agent + one marker-carrying
   companion, stub `kill_window` / `kill_pane` to record. Killing the last real
   agent must call **`kill_window`**. Paired negative control: with the marker
   removed and `_is_companion_process` False, the same fixture downgrades to
   `kill_pane` — i.e. the assertion tracks the marker, not the fixture shape.
   (AC 2.)

Last-record coverage for step 5 — **both** readers, with the record that would
be dropped placed **last** and carrying an empty final field (the ordering the
existing live test accidentally avoids):

9. **`test_find_companion_pane_id_reads_an_unmarked_last_record`** — stdout
   `"%1\t<agent>\t\n%2\t<companion>\t\n"` (trailing newline, empty marker on
   both), `_is_companion_process` True only for the companion pid ⇒ returns
   `%2`. Fails against `stdout.strip().splitlines()`.
10. **`test_kill_smart_counts_an_unmarked_last_real_agent`** — a window whose
    **last** listed pane is an unmarked real agent sibling; killing the target
    must call **`kill_pane`**, not `kill_window`. This is the pre-existing
    defect named in step 5 and it fails against today's code. Paired negative
    control: with that sibling removed the same fixture calls `kill_window`, so
    the assertion tracks the surviving sibling rather than the stub shape.

`tests/test_kill_agent_pane_smart.sh` (live tmux, sentinel argv, no markers on
its fixture panes) is left as-is and doubles as the fallback-rung control for
site 3.

### 10. Docs — `aidocs/framework/tui_conventions.md`

The `@aitask_monitor_kind` section states *"Two consumers read it: the
single-instance guards … and `aitask_companion_cleanup.sh`'s companion
discovery."* That claim becomes false. Update it to name the third consumer —
**monitor / minimonitor discovery** (`_is_companion_pane`,
`find_companion_pane_id`, `kill_agent_pane_smart`) — and record the rule:
marker primary, `#{pane_pid}` cmdline as fallback, and a **stale** marker is not
a companion. Add the *why*: `#{pane_pid}` is the pane's top-level process, so a
companion restarted inside an interactive shell is invisible to cmdline matching.

No `website/content/` page documents this internal, so no site change (and the
task declares no `docs_updated` gate).

### Post-phase (risk mitigations)

1. `[live_shell_hosted_repro]` Run the task's real reproduction in a **scratch**
   tmux session (never the working session): create a window, split a plain
   shell pane into it, run `ait minimonitor` from that shell, and confirm from a
   second `ait monitor` / `ait minimonitor` that the window is listed **once**.
   Then kill the last real agent pane in that window through the TUI and confirm
   the **window** is killed, not just the pane. Finally, in a window holding
   **two** real agent panes with the unmarked one listed last, kill one and
   confirm only the **pane** dies — the step-5 regression direction, and the one
   whose failure mode is destructive. Record every observed outcome in the Final
   Implementation Notes. This is the only check that exercises a real
   shell-hosted companion end to end; every other AC is proven at the parse seam.

---

## Verification

Deterministic (all offline; run from repo root):

```bash
python3 tests/test_monitor_companion_filter.py
python3 tests/test_agent_marks_generation.py
python3 tests/test_monitor_refresh_no_sync_tmux.py
python3 tests/test_monitor_shadow_status.py
python3 tests/test_monitor_shadow_zone.py
python3 tests/test_minimonitor_auto_close_guard.py
bash tests/test_multi_agent_window_substrate.sh
bash tests/test_multi_session_monitor.sh
bash tests/test_kill_agent_pane_smart.sh
```

Then the full Python suite (read **only** the last line for the verdict;
`set -o pipefail` if piping):

```bash
bash tests/run_all_python_tests.sh
```

Live end-to-end repro of the reported symptom, in a scratch tmux session (not the
working session):

```bash
tmux -L ait split-window -t <agent-window>   # a plain shell pane
# inside it:  ait minimonitor
```
Any *other* minimonitor must list the window **once**, not twice.

**Per-half pre-fix controls** — this change has two independent halves, so one
mutant is not enough. Each must be shown to fail on its own (do **not** stash;
snapshot to the scratchpad if a comparison copy is needed):

- revert only step 4's marker branch ⇒ new tests 1, 2, 5 fail;
- revert only step 5's iteration change ⇒ new tests 9, 10 fail.

## Step 9 (Post-Implementation)

Cleanup, archival and merge follow `task-workflow` Step 9. Current-branch mode:
nothing to merge, `main` is both base and output.

## Risk

*(Reassessed after the two inline mitigations were folded into the plan body.)*

### Code-health risk: medium
- Widening the `list-panes` arity set touches ~6 test files' hand-built stubs; a
  stub left at a stale arity is silently `continue`d, so its assertions pass
  **vacuously** rather than failing · severity: medium ·
  → mitigation: inline pre-phase assert_fixture_rows_parsed
- The discovery hot path runs every ~3 s in both TUIs; a marker verdict that
  returned True for a real agent pane would *hide* an agent. Bounded — only our
  own writer stamps `@aitask_monitor_kind`, and the value is validated by
  `monitor_marker.py` · severity: low ·
  → mitigation: inline post-phase live_shell_hosted_repro
- The arity tolerance list grows again (9 → 9,10,11). Contained for now (named
  constant + era map), but it is an accumulating seam · severity: low ·
  → mitigation: none (accepted)
- Step 5 changes the record-iteration contract of two live-tmux code paths and
  fixes a pre-existing `kill_window` defect. Killing the wrong thing is
  destructive, and the existing live test's fixture ordering cannot see it ·
  severity: medium · → mitigation: new tests 9–10 (last-record placement, each
  with a paired negative control) plus inline post-phase
  live_shell_hosted_repro, which exercises the kill path for real

### Goal-achievement risk: low
- Every AC maps to a named change and a named test; the root cause was verified
  live with an exact correlation between the two shell-hosted companions and the
  two duplicated windows. Residual: the ACs are proven at the parse seam, not
  through a real tmux session with a real shell-hosted minimonitor ·
  severity: low ·
  → mitigation: inline post-phase live_shell_hosted_repro

### Planned mitigations
- timing: pre-phase | name: assert_fixture_rows_parsed | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — stub arity drift passing vacuously | desc: assert every hand-built list-panes fixture actually produced panes, green at the old arity first
- timing: post-phase | name: live_shell_hosted_repro | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — ACs proven only at the parse seam | desc: run the real shell-hosted-minimonitor repro in a scratch tmux session and confirm single listing plus kill-window

---
Task: t1327_fix_pane_discovery_shadow_companion_filtering.md
Worktree: (current branch — profile 'fast' works in place)
Branch: main
Base branch: main
Output branch: main
---

# p1327 — Fix pane-discovery shadow/companion filtering test

## Context

`bash tests/test_multi_agent_window_substrate.sh` fails at its Tier-1
pane-discovery block:

```
  FAIL: discovery keeps exactly one real agent
  FAIL: discovery kept the agent pane (%1)
AttributeError: 'list' object has no attribute 'pane_id'
```

t1327 asks to determine whether the defect is in `_parse_list_panes`' filtering
or in the test fixture drifting from `_LIST_PANES_FORMAT`, and to make the
assertion fail cleanly.

**Root cause established (fixture drift, not a filtering regression):**

- The test was written by t986_1 (`4dcad92e4`), when
  `TmuxMonitor._parse_list_panes` returned a **single list** of panes.
- t1133 (`6998efc7f`) changed the signature to return a **tuple**
  `(agent_facing_panes, shadow_panes)` — see
  `.aitask-scripts/monitor/monitor_core.py:1876-1964`. Every Python caller
  (`tests/test_monitor_companion_filter.py:118`,
  `tests/test_monitor_shadow_status.py:146`, `_discover_panes_multi`) was
  updated; this shell test was not.
- So `panes` is a 2-tuple → `len(panes) == 1` is False, and `panes[0]` is a
  `list`, which is exactly the `AttributeError`.

The production filtering is correct: shadows are diverted at
`monitor_core.py:1919` and companions at `:1946`. Verified live against the
current module — the intended fixture yields panes `['%1','%4']`, shadows
`['%2']`, cache `['%1','%4']`. **No production code changes.**

Two secondary defects in the same block:

- The `%2`/`%3` exclusion checks and the whole rest of Tier 1 never execute —
  the `AttributeError` aborts the interpreter first. Tier 1 has therefore had
  **zero** coverage of `_parse_list_panes` and of `TaskInfoCache` since t1133.
- `TmuxMonitor(session="testsess")` leaves `exclude_pane` defaulting to
  `os.environ.get("TMUX_PANE")` (`monitor_core.py:__init__`). Running the suite
  from inside a tmux pane leaks an ambient pane id into the fixture. The
  Python sibling avoids this by passing `exclude_pane=""` explicitly
  (`tests/test_monitor_companion_filter.py:60-64`).

**Intended outcome:** Tier 1 runs to completion, genuinely asserts the
shadow/companion filtering contract as it exists today, is hermetic, and
reports a comparison rather than a traceback when it next breaks.

## Scope

Single file: `tests/test_multi_agent_window_substrate.sh`, Tier-1 block only
(lines 34-121). No production code changes, in the implementation or in the
negative control.

**What this block claims to cover** (stated in the refreshed header comment, so
the claim stays honest): `_parse_list_panes` returns `(agents, shadows)`; the
shadow marker diverts a pane to the second list; the companion predicate is
consulted **regardless of window classification**; neither helper enters
`_pane_cache`; both the 10-field and legacy 9-field row shapes parse. The
exhaustive companion-filter contract (memoization, TTL, per-session eviction,
call counting) stays owned by `tests/test_monitor_companion_filter.py` — this
block does not duplicate it.

## Implementation

### 1. Add a comparison-reporting check helper (Tier 1 preamble, ~line 47)

Keep the existing `check(label, cond)` and add a sibling so a failure prints
the mismatch instead of just the label:

```python
def check_eq(label, actual, expected):
    if actual == expected:
        print(f"  ok: {label}")
    else:
        print(f"  FAIL: {label} — got {actual!r}, expected {expected!r}")
        failures.append(label)
```

### 2. Pin the fixture to the current `_LIST_PANES_FORMAT` (lines 76-88)

- Construct the monitor hermetically: `TmuxMonitor(session="testsess", exclude_pane="")`.
- Fix the stale `FMT_LINE` comment — `_LIST_PANES_FORMAT` is now **10** fields
  (`…, #{@aitask_shadow_target}, #{history_size}`), not 9.
- Emit the scenario rows in the **current 10-field** shape, plus one row in the
  legacy **9-field** shape to pin the back-compat path `_parse_list_panes`
  explicitly documents (`monitor_core.py:1898-1900`, "9 = pre-history_size
  lines (test stubs)").

| pane | window | pid | shadow target | history | expectation |
|---|---|---|---|---|---|
| `%1` | `agent-pick-100` | 1234 | `""` | 500 | kept as agent |
| `%2` | `agent-pick-100` | 1235 | `"%1"` | 12 | shadow list |
| `%3` | `agent-pick-100` | 9999 | `""` | 40 | companion — filtered from both |
| `%4` | `agent-pick-100` | 1236 | `""` | *(9-field row)* | kept, `history_size is None` |
| `%5` | `noam_bugs` | 9999 | `""` | 7 | companion in a **non-agent** window — filtered |

Row `%5` is the one that discriminates: `classify_pane("noam_bugs")` returns
`OTHER`, so a regression to the pre-t1382 `category == AGENT and …` conjunct
would short-circuit and leak it into `panes`. Every `agent-pick-100` row is
classified `AGENT` and would be filtered under either form, so without `%5`
this block cannot catch that regression at all. Verified: `%5` is filtered by
the current code.

### 3. Guard the return shape, then assert (lines 89-95)

Unpacking first would raise before any helper runs if a future change returns
the old single list (or any other shape) — recreating exactly the traceback
this task exists to eliminate. So describe the shape *without indexing into
it*, and only inspect pane attributes once both collections are safe to
iterate:

```python
MISSING = "<attr missing>"


def shape_of(obj):
    """Describe the return shape without indexing into it."""
    if (isinstance(obj, tuple) and len(obj) == 2
            and all(isinstance(x, list) for x in obj)):
        return "tuple[list, list]"
    if isinstance(obj, (tuple, list)):
        return f"{type(obj).__name__}[{len(obj)}]"
    return type(obj).__name__


def attr(obj, name):
    """Project a field without raising when the element shape drifts."""
    return getattr(obj, name, MISSING)


result = monitor._parse_list_panes(stdout, "testsess")
check_eq("_parse_list_panes returns (agents, shadows)",
         shape_of(result), "tuple[list, list]")

if shape_of(result) != "tuple[list, list]":
    # Do NOT unpack or touch attributes — the shape check above already
    # registered the failure with a got/expected comparison.
    print("  BLOCKED: discovery assertions (return shape changed)")
    failures.append("discovery assertions blocked by return-shape change")
else:
    panes, shadows = result
    check_eq("discovery keeps the real agent panes only",
             [attr(p, "pane_id") for p in panes], ["%1", "%4"])
    check_eq("shadow pane returned in the shadow list",
             [attr(p, "pane_id") for p in shadows], ["%2"])
    check_eq("shadow carries its followed-agent target",
             [attr(s, "shadow_target") for s in shadows], ["%1"])
    check_eq("companion panes excluded from both lists",
             sorted(map(str, {"%3", "%5"} & {attr(p, "pane_id")
                                             for p in panes + shadows})), [])
    check_eq("10-field row parses history_size",
             [attr(p, "history_size") for p in panes
              if attr(p, "pane_id") == "%1"], [500])
    check_eq("legacy 9-field row parses with history_size None",
             [attr(p, "history_size") for p in panes
              if attr(p, "pane_id") == "%4"], [None])
    # Cache-boundary invariant (monitor_core.py:1886-1890): only agent-facing
    # panes enter _pane_cache.
    check_eq("shadow + companions stay out of _pane_cache",
             sorted(map(str, monitor._pane_cache)), ["%1", "%4"])
```

**What this does and does not claim.** `shape_of` covers the return-shape class
of regression — the one that actually bit here — and the blocked branch appends
its own named failure rather than falling through, so a shape change can never
leave the remaining assertions silently vacuous. Inside the guarded branch,
`tuple[list, list]` says nothing about what the elements are, so every field
projection goes through `attr()`: a renamed or removed field surfaces as
`'<attr missing>'` inside the got/expected comparison instead of an
`AttributeError`, and `sorted(map(str, …))` keeps the two ordering assertions
total against non-string ids. The precise claim is therefore: **no
`AttributeError` and no ordering `TypeError` on a shape or field drift** — a
drift is reported as a comparison. It is not a claim that arbitrary malformed
contents are impossible to trip over.

### 4. Refresh the header comment (line 9)

Replace `_parse_list_panes filters shadow helper panes` with the coverage claim
spelled out in **Scope** above, including the explicit hand-off of the full
companion-filter contract to `tests/test_monitor_companion_filter.py`.

## Verification

1. `bash tests/test_multi_agent_window_substrate.sh` — Tier 1 must run to
   completion and print `Tier 1 OK`; Tier 2 (live tmux) must stay green.
2. Confirm the previously-unreachable tail actually executes: the four
   `TaskInfoCache` checks (current lines 97-116) print `ok:` lines.
3. Bounded regression sweep of the Python modules that read the same seam.
   `run_all_python_tests.sh` takes `--test-dir <dir>` (one directory, consumed
   as `$1`) and has no module-list selector, and a positional path disables the
   parallel lane — so drive `unittest` directly under the framework
   interpreter, exactly as the runner resolves it:

   ```bash
   (
     cd /home/ddt/Work/aitasks
     source .aitask-scripts/lib/python_resolve.sh
     PY="$(require_ait_python)"; unset PYTHONPATH
     rc=0
     for m in test_monitor_companion_filter test_monitor_shadow_status \
              test_monitor_shadow_zone test_agent_marks_generation; do
         "$PY" -m unittest discover -s tests -p "$m.py" || { echo "FAILED: $m"; rc=1; }
     done
     [ "$rc" -eq 0 ] && echo "SWEEP: PASSED" || echo "SWEEP: FAILED"
     exit "$rc"
   )
   ```

   The `|| { …; rc=1; }` form records the failure **and** keeps it in the exit
   status; a bare `|| echo "FAILED: $m"` would make every failing module a
   successful command and let the loop finish 0 while printing failures. The
   subshell wrapper is what makes `exit "$rc"` the sweep's status without
   killing the calling shell — **read the exit status, not just the banner**.
   (Verified working: `test_monitor_companion_filter` → `Ran 10 tests … OK`.)
4. Negative control (post-phase `negctrl_discovery_filter` below).

## Step 9 (Post-Implementation)

Standard: merge to `main`, archive `t1327` and this plan.

## Risk

### Code-health risk: low
- The restored assertions could be vacuous — a test that passes without
  actually exercising the shadow/companion filter is worse than the current
  loud failure, and there is no way to tell from a green run alone.
  · severity: medium · → mitigation: inline post-phase negctrl_discovery_filter

### Goal-achievement risk: low
- None identified beyond the above. The root cause was established by git
  archaeology (`4dcad92e4` wrote the block against a single-list return;
  `6998efc7f` changed it to a tuple) and by reading the current
  `_parse_list_panes`, not inferred from the symptom. A grep for
  `_parse_list_panes` across `tests/` and `.aitask-scripts/` confirms this is
  the only stale caller.

### Planned mitigations
- timing: post-phase | name: negctrl_discovery_filter | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — restored assertions could be vacuous | desc: after the fix is green, inject a shadow-filter fault through the test's own module-monkeypatch seam and confirm the four dependent assertions fail by name with got/expected comparisons; revert the one-line injection and confirm green again.

### Post-phase (risk mitigations)

**negctrl_discovery_filter** — run after step 3 above is green.

**No production file is edited and no `git checkout` is run.** The tree is
shared and already carries another session's uncommitted work, so reverting a
tracked file by checkout could discard it. Instead the fault goes in through
the seam the test already uses for `_is_companion_process`: `_parse_list_panes`
resolves `is_shadow_target` from the module globals at call time
(`monitor_core.py:1919`), so rebinding it in the test's own heredoc disables
the exact predicate under test. Reverting is deleting the one line just added
to a file this task already owns.

1. In the Tier-1 heredoc, immediately below the existing
   `mc._is_companion_process = …` patch, add `mc.is_shadow_target = lambda t: False`.
2. Re-run `bash tests/test_multi_agent_window_substrate.sh`. Tier 1 MUST report
   **exactly these four** failures, each with a got/expected comparison and no
   traceback (levels confirmed empirically against the real module):

   | assertion | got | expected |
   |---|---|---|
   | `discovery keeps the real agent panes only` | `['%1', '%2', '%4']` | `['%1', '%4']` |
   | `shadow pane returned in the shadow list` | `[]` | `['%2']` |
   | `shadow carries its followed-agent target` | `[]` | `['%1']` |
   | `shadow + companions stay out of _pane_cache` | `['%1', '%2', '%4']` | `['%1', '%4']` |

   The companion assertions MUST stay green — `%3`/`%5` are filtered by a
   different predicate, and their surviving is what shows the injection was
   narrow rather than blanket. If the run produces a different failure set, the
   fixture or the assertions are wrong; stop and re-diagnose before committing.
3. Delete the injected line and re-run to confirm `Tier 1 OK`. Confirm the file
   is back to its intended state with `git diff --stat -- tests/test_multi_agent_window_substrate.sh`
   (only the t1327 changes remain). Nothing from this phase is committed.

---
Task: t2088_kill_bound_helpers_on_direct_kill.md
Base branch: main
Output branch: main
---

# t2088 — kill bound helpers on the direct kill-pane paths

## Context

A bound helper (shadow `@aitask_shadow_target`, scratchpad `@aitask_scratchpad_target`)
is killed with its agent only by `aitask_companion_cleanup.sh` job 1, which runs from the
agent pane's `pane-died` hook. Two framework paths kill an agent with a plain
`kill-pane` / `kill-window`, and that fires no `pane-died`, so the helpers are left behind
bound to a pane id that no longer exists:

- `monitor_core.TmuxMonitor.kill_agent_pane_smart` (`.aitask-scripts/monitor/monitor_core.py:3786`)
  — the pane branch when other real agents stay in the window. The window branch leaks
  too, for a helper placed in **another** window (the shadow's configurable placement), which
  job 1 handles because it is session-scoped.
- `lib/agent_freeze.drop_record` (`.aitask-scripts/lib/agent_freeze.py:1482`) →
  `frozen_ops.kill_if_stamped` when a real sibling keeps the window (and, the same way, a
  separate-window helper on the window branch).

`tests/test_scratchpad_spawn_live.sh` case D currently asserts the pad is left behind
(known gap). Result after this task: both paths kill every helper bound to the pane they
just killed, never a frozen stand-in, never a helper bound to a pane that is still alive;
the rule lives in `lib/helper_panes.py`.

## Design

**One shared sweep in `lib/helper_panes.py`** (stays stdlib-only and tmux-free: it takes
the caller's gateway-backed `run` callable, so `tests/test_no_raw_tmux.sh` is unaffected and
there is no third hard-coded marker list):

- `bound_helper_sweep_format(frozen_option)` → `#{pane_id}`, `#{pane_pid}`, `#{pid}`,
  `#{<frozen>}`, then one field per option in `BOUND_HELPER_TARGET_OPTIONS`, in tuple order,
  tab-joined. The frozen option is a parameter (`monitor_core.FROZEN_OPTION`), not a
  duplicated literal.
- `helpers_bound_to(stdout, target_pane_id)` → pure parse of that listing, returning
  candidates `(pane_id, pane_pid, server_pid, matched_option)`. These are candidates only;
  the guarded dispatch below decides:
  - per-line `split("\t")`, never a whole-buffer `strip()` (t1686 trailing-empty-field trap);
    rows with the wrong arity are skipped;
  - **frozen first**: a row with a non-empty frozen field is never a helper;
  - a row is a victim when any target field `.strip() == target_pane_id` and it is not the
    target itself;
  - **target-alive guard**: if `target_pane_id` itself appears in the listing, return `[]` —
    the kill did not take, or a server restart recycled the `%N`; either way the helpers
    serve a live pane and must not be touched ("never kill on unknown" — `rc != 0` listing
    also yields nothing).
- `kill_bound_helpers(run, target_pane_id, *, frozen_option)` → `run(["list-panes", "-a",
  "-F", fmt])`; on `rc != 0` return `[]`; otherwise, for each victim, **one guarded dispatch —
  never a bare `kill-pane`** (review finding, t1773/t1783 shape):

  ```
  if-shell -F -t <helper> "<cond>" "kill-pane -t <helper>"
  cond = #{&&: frozen-empty ,
          #{&&: #{==:#{<matched option>},<target>} ,
           #{&&: #{==:#{pane_pid},<listed pane_pid>} , #{==:#{pid},<listed server pid>} }}}
  ```

  The listing and the dispatch can be split by a tmux restart (recycling the helper's `%N`
  into an unrelated pane), by a freeze stamping the candidate, or by a rebind. The condition is
  evaluated by the server at dispatch time, so the deletion happens only if, **at that
  instant**, the pane is still unfrozen, still carries the expected binding to the killed
  target, still runs the process that was listed (`pane_pid`), and is on the same server
  generation (`#{pid}`, server-scoped). The server-pid half also makes the target-alive
  guard sound: it ran against the same server generation the kill runs in, and pane ids are
  never reused within one generation. `<matched option>` is the option whose value matched
  (the first, if both did).

  Then one read-back per dispatched helper (`display-message -p -t <helper>
  "#{pane_id}\t#{pid}"`): `if-shell` answers 0 whether or not the branch fired, so only an
  empty pane id on the same server pid counts as killed (`kill_if_stamped`'s after-read
  rule; tmux unreachable counts as "not killed", never as gone). Returns the verified-gone ids.
  Best-effort, like job 1's `|| true`: it never changes the caller's verdict.

  Values going into the condition are validated before any dispatch: target and helper ids
  must match `^%[0-9]+$`, `pane_pid` and the server pid `^[0-9]+$`. A row that fails is
  skipped. Listing rows therefore also carry `#{pane_pid}` and `#{pid}`:
  the sweep format is `pane_id, pane_pid, pid, <frozen>, <targets in tuple order>`.

  **Measure the grammar first (implementation step 0):** on a private `-L` server under the
  scratchpad `TMUX_TMPDIR`, check that the frozen-empty half (`#{==:#{@opt},}`; else
  `#{?#{@opt},0,1}`) and the nested binary `#{&&:…}` evaluate as intended on the installed
  tmux, for both a stamped and an unstamped pane. Use whichever form is measured to work.

Scope is `list-panes -a` (whole server) rather than job 1's session scope: pane ids are
server-unique, so matching server-wide reaches the same helpers plus any in another session,
and needs no session resolved before the kill. Documented in the docstring.

Helpers bound to a still-alive sibling are untouched by construction: only rows whose target
equals the killed pane match.

## Implementation steps

0. **Grammar probe** (see Design): measure the frozen-empty and nested `&&` forms on a
   private tmux server; record the measured table in the plan's Final Implementation Notes.

1. **`.aitask-scripts/lib/helper_panes.py`** — add the three functions above, plus a private
   `_guard_condition(...)` builder (pure, unit-tested on its own); extend the
   module docstring's rule list ("it is killed when its target pane dies (cleanup job 1) **or
   is killed directly** (`kill_bound_helpers`)") and name the two direct-kill call sites.

2. **`.aitask-scripts/monitor/monitor_core.py`**
   - re-export `bound_helper_sweep_format`, `helpers_bound_to`, `kill_bound_helpers` from the
     existing `from helper_panes import (...)` block.
   - add `TmuxMonitor._kill_bound_helpers(pane_id)`: calls
     `kill_bound_helpers(self.tmux_run, pane_id, frozen_option=FROZEN_OPTION)` and pops each
     killed id from `_pane_cache` / `_last_content` / `_last_change_time` (as `kill_pane` does).
   - `kill_agent_pane_smart`: run `self._kill_bound_helpers(pane_id)` after **every successful
     kill** — the two early `kill_pane` fallbacks (cache miss, listing failed) and both
     window/pane branches — and after the existing record drop. Restructure the early returns
     to bind `ok, killed_window` and fall through to one exit, so no route can skip it. Return
     value unchanged. Docstring: say why (`kill-pane` fires no `pane-died`).

3. **`.aitask-scripts/lib/agent_freeze.py`** — in `drop_record`'s `must_kill` branch, after
   `verdict == "gone"` is verified (before the store write), call
   `kill_bound_helpers(frozen_ops.run, pane_id, frozen_option=FROZEN_OPTION)`
   (`frozen_ops.run` through the module, per the seam rule). Not run when the kill was not
   verified gone (fails closed) or when there was nothing to kill (`must_kill` false — a
   recycled `%N` or no pane). Wire lines (`DROPPED:` etc.) unchanged. Add a docstring step
   "2b. **helpers**" to the ORDER list.

4. **Mocked tests — `tests/test_helper_panes.py`**
   - format tripwire: `bound_helper_sweep_format` carries the frozen option and every option
     in the tuple, in order; identity test for the three new re-exports on `monitor_core`.
   - `helpers_bound_to`: shadow-bound and pad-bound rows returned; frozen row carrying a
     target retained → excluded (negative control: same row unstamped → included); row bound
     to a sibling → excluded; target present in listing → `[]`; wrong-arity row skipped; a
     final row with empty trailing fields still parsed.
   - `kill_bound_helpers`, against a self-contained server-model stub that evaluates
     `if-shell -F` conditions (the `==` / binary `&&` / `#{pid}` subset) and runs the branch:
     listing `rc != 0` → nothing dispatched; **no bare `kill-pane` is ever issued** (every
     kill is inside an `if-shell` branch); only verified-gone ids are reported.
   - **deterministic race tests**, all with a stub that mutates the model *between* the
     listing and the dispatch, each asserting the candidate **survives** and is not
     reported: (a) server restart recycles the candidate's `%N` into an unrelated pane
     (new server pid, new `pane_pid`, no binding); (b) restart recycles it into a pane that
     *is* bound to the same target id (new server pid only — proves the `#{pid}` half alone
     rejects it); (c) the candidate gets `@aitask_frozen` stamped; (d) the candidate is
     rebound to another agent; (e) the candidate's process is replaced (`pane_pid` changes,
     same server). Control: the same stub with no mutation kills the candidate.
   - unsafe values (a target or helper id not `%N`, a non-numeric pid) → row skipped, nothing
     dispatched.

5. **Mocked tests — `kill_agent_pane_smart`** (new class in
   `tests/test_monitor_companion_filter.py`, beside `KillAgentPaneSmartTests`): a tmux stub
   that answers the `FROZEN_AWARE_PANE_FORMAT` window listing and the `-a` sweep listing from
   one pane model (and removes panes on kill). Cases: pane branch kills the shadow and the pad
   bound to the killed agent, leaves a pad bound to the surviving sibling and a frozen
   stand-in retaining a target; window branch kills a separate-window shadow; cache-miss
   fallback also sweeps; a failed kill issues no sweep.

6. **Mocked tests — `drop_record`** (in `tests/test_agent_freeze.py` `DropVerbTests`, reusing
   `_FakeTmux`): with a real sibling in the window (kill-pane branch) a shadow and a pad bound
   to `AGENT_PANE` are killed after the guarded `if-shell` dispatch, a pad bound to the
   sibling survives, a frozen pane with a retained target survives; a declined kill
   (`kill_ok = False`) → `DROP_FAILED` and no helper killed; a racing `run` (the existing
   `racing_run` pattern) that restarts the server between the sweep listing and the helper
   dispatch → the helper survives. Every helper `kill-pane` in `calls` must sit inside an
   `if-shell` branch. `_FakeTmux._cond_holds` learns to answer `#{pid}` from `server_pid`
   (today it reads it from the pane dict, where it is absent). Existing assertions (first
   destructive call is `if-shell`, no kill when no pane) must still pass.

6b. **Live, runnable here — `tests/test_kill_agent_pane_smart.sh`** (needs only
   `require_isolated_tmux`, so unlike the scratchpad file it runs inside this session): in
   each pass (control-client backend AND subprocess fallback) add a pane bound to A1 via
   `@aitask_shadow_target` and a pane bound to A2 via `@aitask_scratchpad_target`; after
   killing A1, assert A1's helper is gone and A2's survives. This proves the guarded
   `if-shell` condition really fires on a real server, through both `tmux_run` routes
   (including `_quote_arg`), and the negative case rules out a condition that matches
   everything.

7. **Live — `tests/test_scratchpad_spawn_live.sh`**
   - flip case D: retitle; after `DROPPED`, `wait_until 20 pane_gone "$PAD"`; add a fake
     shadow (a `sleep` split with `@aitask_shadow_target=$AGENT`) and assert it is gone too;
     add a control pad bound to `$SIBLING` (spawned through `spawn`) and assert it survives
     and stays bound.
   - add case G — `kill_agent_pane_smart` pane branch live: a driver `kill <pane>` mode
     (`discover_panes()` then `kill_agent_pane_smart`); agent + real sibling + pad + fake shadow
     bound to the agent + control pad bound to the sibling → pad and shadow gone, sibling and
     control alive.
   - update the header comment (D no longer a known gap, G described).

8. **Step 9 (Post-Implementation)** — commit, archival, merge per the workflow.

### Post-phase (risk mitigations)

1. [prove_sweep_guards_with_mutants] Copy the changed modules and tests into a scratchpad
   directory (never edit or `git restore` the shared worktree). Apply each mutant alone and run
   the mocked tests against it, recording which named test fails:
   (a) drop the frozen-first check in `helpers_bound_to`;
   (b) drop the target-alive guard;
   (c) remove the `_kill_bound_helpers` call from `kill_agent_pane_smart`;
   (d) remove the `kill_bound_helpers` call from `drop_record`;
   (e) replace the guarded dispatch with a bare `kill-pane -t <helper>`;
   (f) drop the `#{pid}` half of the condition;
   (g) drop the `pane_pid` half of the condition.
   Each mutant must turn at least one test red, and that test must be the one about that
   guard. A mutant that stays green means a missing test: add it and re-run. Record the
   mutant → failing-test table in the plan's Final Implementation Notes.

## Verification

- `python3 tests/test_helper_panes.py`
- `python3 -m pytest tests/test_monitor_companion_filter.py tests/test_agent_freeze.py -q`
  (or unittest)
- `bash tests/test_kill_agent_pane_smart.sh` (live guarded dispatch, both backends),
  `bash tests/test_cleanup_rule_parity.sh`,
  `bash tests/test_no_raw_tmux.sh`, `bash tests/test_no_lib_to_tui_import.sh`
- `bash tests/test_scratchpad_spawn_live.sh` from a terminal outside tmux (it refuses inside
  tmux / with `-L ait` alive) — if it cannot run here, say so instead of claiming it.
- `bash tests/run_all_python_tests.sh` — read only the last line for the verdict.

## Risk

### Code-health risk: medium
- Helper deletion based on an earlier listing could kill a recycled `%N` (tmux restart), or a candidate that was frozen or rebound after the listing. Addressed in the design: every deletion is a single `if-shell -F` dispatch that rechecks frozen, binding, `pane_pid` and server pid at kill time, plus deterministic race tests (review finding) · severity: low (residual — guarded dispatch + race tests; mutants e–g pin it) · → mitigation: inline post-phase prove_sweep_guards_with_mutants
- New destructive `kill-pane` calls on two load-bearing kill paths: a parse or guard slip could kill a pane that is not a helper of the killed agent (a frozen stand-in, a sibling's helper, a recycled `%N`). Bounded by frozen-first, exact target match, and the target-alive guard, all unit-pinned, but the tests only prove anything if they fail without those guards · severity: low (residual — addressed by inline post-phase prove_sweep_guards_with_mutants) · → mitigation: inline post-phase prove_sweep_guards_with_mutants
- `kill_agent_pane_smart` runs in sync UI handlers; one extra `list-panes -a` per kill adds a little latency. Existing tests that pin exact tmux call sequences (`DropVerbTests`, `KillAgentPaneSmartTests`) may need adjusting · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The live flip (case D) and the new live case G cannot run in this session: it is inside tmux with the `-L ait` server alive, and `require_clean_ait_server` refuses. So the end-to-end proof that no `pane-died` is needed would land unrun · severity: medium · → mitigation: t2093

### Planned mitigations
- timing: post-phase | name: prove_sweep_guards_with_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — new helper kills on load-bearing paths; guard tests must have signal | desc: Mutant-check the frozen-first, target-alive, both call-site sweeps and the guarded-dispatch halves against the mocked tests in an isolated copy
- timing: after | name: run_helper_sweep_live_outside_tmux | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — live case D flip and case G cannot run inside this tmux session | desc: Run tests/test_scratchpad_spawn_live.sh from a terminal outside tmux (no -L ait server) and confirm cases D and G pass | created: t2093

## Final Implementation Notes
- **Actual work done:** `lib/helper_panes.py` gained the shared direct-kill sweep — `bound_helper_sweep_format`, `helpers_bound_to` (pure candidate parse: frozen first, exact target, target-alive ⇒ nothing, malformed ids/pids skipped), `_guard_condition`, `kill_bound_helpers` (whole-server listing, then per helper ONE guarded `if-shell -F` dispatch re-checking frozen-empty, binding, `pane_pid` and server `#{pid}`, then a read-back). `monitor_core` re-exports them; `kill_agent_pane_smart` became a thin wrapper over `_kill_agent_pane` that sweeps after any successful kill (both fallbacks, pane and window branch). `agent_freeze.drop_record` sweeps after the stand-in is verified gone, before the store write. Tests: `tests/lib/tmux_server_model.py` (in-memory server evaluating guarded dispatches), new sweep/race classes in `tests/test_helper_panes.py`, new `tests/test_kill_bound_helpers.py`, `DropHelperSweepTests` in `tests/test_agent_freeze.py`, live helper checks in `tests/test_kill_agent_pane_smart.sh` (both tmux_run routes), case D flipped + case G added in `tests/test_scratchpad_spawn_live.sh`.
- **Deviations from plan:** the `kill_agent_pane_smart` mocked tests live in a new `tests/test_kill_bound_helpers.py` instead of `test_monitor_companion_filter.py` (that file is about companion filtering). The shared server-model stub lives in `tests/lib/`. `_FakeTmux` in `test_agent_freeze.py` now expands `#{pid}` from `server_pid` in listings and conditions (previously only `display-message`). The existing `test_a_moved_pane_counts_siblings_in_its_OWN_window` was updated: its `%8` is a shadow bound to the dropped stand-in in another window, which the sweep now retires — the intended new behaviour; the stand-in's own kill is still exactly one `kill-pane`.
- **Issues encountered:** the live fixture's default 80x24 session refused extra splits ("no space for a new pane") — the session is now created at 240x80. A splice while editing the scratchpad live file briefly deleted Case C's body; restored verbatim from HEAD and re-diffed.
- **Key decisions:** Review finding (blocking) adopted — no bare `kill-pane` of a listed id; each helper kill is a single server-evaluated `if-shell -F` (the `kill_if_stamped` shape), and the server-pid half makes the listing's target-alive reading apply to the generation the kill runs in. Whole-server `list-panes -a` rather than job 1's session scope (pane ids are server-unique). Sweep is best-effort and never changes either caller's verdict or wire line.
- **Grammar probe (tmux 3.8, private `-S` server):** `#{==:#{@opt},}` → 1 unstamped / 0 stamped; `#{?#{@opt},0,1}` same; nested binary `#{&&:…}` → 1 only when all halves hold; wrong `pane_pid` → 0; wrong `#{pid}` → 0; `if-shell` answers 0 whether or not the branch fired, 1 on a gone target; `display-message -p` on a gone pane → rc 0, empty `#{pane_id}`, `#{pid}` still expanded.
- **Mutants (prove_sweep_guards_with_mutants), isolated scratchpad copies, all red:** (a) no frozen-first → `test_a_frozen_pane_with_a_retained_target_is_never_a_candidate`; (b) no target-alive → `test_the_target_still_listed_means_nothing`, `test_the_target_still_alive_kills_nothing`; (c) no monitor sweep → 5 `KillAgentPaneSmartSweepTests` (and the live `test_kill_agent_pane_smart.sh` — A1's shadow survives); (d) no drop sweep → 3 `DropHelperSweepTests` + the moved-pane test; (e) bare kill → `test_no_bare_kill_pane_is_ever_issued`, `test_every_helper_kill_sits_inside_a_guarded_branch`, all `SweepRaceTests`; (f) no `#{pid}` half → `test_restart_recycles_the_id_into_a_pane_bound_to_the_same_id`, drop restart test; (g) no `pane_pid` half → `test_the_candidate_s_process_is_replaced`; (h) no frozen half → `test_the_candidate_is_frozen_after_the_listing`; (i) no binding half → `test_the_candidate_is_rebound_to_another_agent`.
- **Not run here:** `tests/test_scratchpad_spawn_live.sh` (cases D, G) and `tests/test_cleanup_rule_parity.sh` refuse inside tmux / with `-L ait` alive — covered by the `run_helper_sweep_live_outside_tmux` after-mitigation.
- **Upstream defects identified:** None

---
Task: t2096_resolve_claude_version_titled_panes.md
Base branch: main
Output branch: main
---

# t2096 — Resolve Claude panes whose tmux command is a version string

## Context

Pressing `L` in minimonitor while following a Claude agent refuses with
"Auto-recheck unavailable for '2.1.306' — the recheck loop supports claude, codex,
opencode". `lib/agent_keys.py:agent_key_from_pane` returns `""` for every Claude
pane on this machine, so prompt scoping (t1467), workflow-phase live tiers, shadow
key resolution and `pane_state_probe` all quietly fall back as well.

**Measured root cause (re-probed during planning, 2026-10-21).** The cause is not
a process title. The native installer makes `~/.local/bin/claude` a **symlink** to
`~/.local/share/claude/versions/2.1.306`:

| pane | `pane_current_command` | `ps -o comm= -p <pane_pid>` | children |
|------|------------------------|-----------------------------|----------|
| %4   | `2.1.306` | `claude` | none |
| %10  | `2.1.306` | `claude` | `caffeinate`, `/bin/zsh` |
| %15  | `2.1.306` | `claude` | `caffeinate` |
| %12  | `codex`   | `codex`  | `…/codex-code-mode-host` |

tmux names the *resolved* executable (basename `2.1.306`), and `ps -o comm=` names
the *invoked* path (`claude`). `tests/lib/fake_agent_binary.py` already documents
this same split between the two readers for symlinks. The resolver never asks for
the pane process's **own** comm: rung 1 reads the tmux command and rung 2 reads
only children.

## Implementation

### Pre-phase (risk mitigations)

1. [baseline_suite_before_rung] Before any edit, run
   `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tee <scratchpad>/baseline_t2096.log`
   on the unfixed tree. Record the last verdict line and the list of failing
   modules. Every post-change failure is then classified against this baseline as
   either pre-existing or introduced. The live-tmux carve-out modules count as not
   run while `$TMUX` is set, never as passed.

### 1. `.aitask-scripts/lib/agent_keys.py`

- Add a module-level `_own_command(pane_pid: int) -> str`, a sibling of
  `_child_commands` that tests can substitute in the same way: guard
  `not pane_pid or pane_pid <= 0` → `""`; `shutil.which("ps")` missing → `""`; run
  `[ps, "-o", "comm=", "-p", str(pane_pid)]` with `timeout=_LOOKUP_TIMEOUT`. Any
  `OSError`/`SubprocessError` or non-zero exit returns `""`. Otherwise return the
  first non-empty stripped line, or `""`.
- In `agent_key_from_pane`, inside the cached section (after the miss-backoff
  gate, before the children lookup):
  ```python
  resolved = agent_key_from_command(_own_command(int(pane_pid)))
  if not resolved:
      resolved_set = {...children...}          # unchanged
      resolved = resolved_set.pop() if len(resolved_set) == 1 else ""
  ```
  Once the own comm resolves, children are not consulted, because the pane process
  *is* that agent. Ambiguity suppression and the one-level depth bound apply to the
  children rung exactly as before. The positive and negative caches wrap both
  lookups unchanged, so a resolved pane still costs one lookup for its lifetime and
  a miss is still retried on the backoff schedule.
- Rewrite the docstrings so they describe a three-rung ladder (tmux command → the
  pane process's own comm → one level of children). Replace the stale 2026-08-13
  table (`claude → native ELF → pane reports claude ✓`) with the measurement above,
  and state the symlink cause: tmux reports the resolved executable, while `ps`
  reports the invoked path. Update `agent_key_from_pane`'s docstring to say why
  rung 2 (own comm) exists and why it outranks children. Note the accepted
  residual: a binary invoked by its versioned path still reads `2.1.306` through
  `ps`, so it stays unresolved (`""`, which means "could not resolve" and is
  degraded on, never concluded from).

### 2. `.aitask-scripts/monitor/minimonitor_app.py` — `action_toggle_review_loop` (~4578)

Before the `review_loop_agent_supported` check, split the resolution miss out:
```python
if not followed_key:
    self.notify(
        f"Auto-recheck unavailable: could not identify the followed agent "
        f"from pane command '{snap.pane.current_command or 'unknown'}' — "
        f"try again in a moment",
        severity="warning", markup=False)  # pane command (t2017)
    return
```
The existing unsupported branch then interpolates `followed_key` (the resolved but
unsupported key) in place of the pane command:
`f"Auto-recheck unavailable for '{followed_key}' — the recheck loop supports {supported}"`.
Keep the comment block and `markup=False`. Existing tests remain valid as written:
`test_refuses_unresolvable_followed_pane` asserts `"node"` is in the message (it
reaches the new branch). `_UNDETECTED_KEY` tests use command == key. The
markup-sink driver in `test_monitor_markup_literal_sinks.py` uses `PaneSnapshot`
with the default `agent_key=""`, so it reaches the new branch, which still
interpolates the pane command with `markup=False`.

### 3. Tests

**`tests/test_agent_keys.py`**
- New class `OwnCommandRungTest`:
  - `test_version_string_command_with_claude_comm_resolves`: substitute
    `ak._own_command = lambda pid: "claude"` and `ak._child_commands = lambda pid: []`,
    then assert `agent_key_from_pane("2.1.306", 4242, "%4") == "claude"`. This is
    the regression test.
  - `test_own_comm_outranks_children`: own `"claude"`, children
    `["codex", "opencode"]` → `"claude"`. Children are not consulted (substitute a
    child stub that raises).
  - `test_full_path_comm_resolves`: own `"/Users/x/.local/bin/claude"` → `"claude"`.
  - `test_unresolved_own_comm_falls_through_to_children`: own `"node"`, children
    `["codex"]` → `"codex"`. Also: own `"node"` with children `["codex", "claude"]`
    → `""` (ambiguity still suppresses).
  - `test_real_process_own_comm`: against a real process. Use
    `_fake_agent_binary(tmp, "claude")` and launch it **directly**
    (`subprocess.Popen([claude, "30"])`, not under `sh`) so its own pid is the pane
    pid. Assert `agent_key_from_pane("2.1.306", proc.pid) == "claude"`. This
    exercises the real `_own_command` → `ps` path. It does **not** claim to test the
    symlink: `fake_agent_binary` tries a copied binary and a compiled binary before
    its opt-in symlink fallback, so on a host with a compiler the result is a real
    file.
  - `test_real_symlink_invoked_name_resolves`: a dedicated case for the invoked-name
    behavior this fix relies on, built in the production shape. The **target** is a
    runnable binary named like the version file,
    `target = fake_agent_binary(tmp, "2.1.306")` (default `allow_symlink=False`, so
    the target is a real file and not a symlink to `sleep`). Then create
    `link = os.path.join(tmp, "bin", "claude")` with `os.symlink(target, link)`,
    assert `os.path.islink(link)` (premise), and launch through the link:
    `subprocess.Popen([link, "30"])`. Assert `os.path.basename(ak._own_command(pid))
    == "claude"` (the invoked name, not `2.1.306`) and
    `agent_key_from_pane("2.1.306", pid, "%t") == "claude"`. Skip with a reason on
    `FakeAgentBinaryUnavailable`.
  - `test_own_comm_missing_ps_returns_empty`: empty `PATH` → `_own_command(pid) == ""`.
- **Isolate the existing stubbed classes from the host.** `CacheTest` and
  `NegativeCacheRetryTest` stub only `_child_commands`, with fake pids
  (4242/5150/777…). The new rung would run a real `ps` on those pids, and on a box
  running many Claude processes a fake pid can be a real `claude`, which makes the
  results host-dependent. In both `setUp`s, also save and stub `ak._own_command`
  with a **counting** stub (`self.own_calls += 1`, then return the scripted
  `self.own` value, default `""`), and restore it in `tearDown`.
- **Pin that the own-comm lookup sits behind the caches.** Counting only
  `_child_commands` would let an `_own_command` placed before the positive-cache or
  miss-backoff checks pass while adding a subprocess on every refresh tick. Add:
  - `CacheTest.test_own_comm_positive_hit_is_looked_up_once`: `self.own = "claude"`,
    then call `agent_key_from_pane("2.1.306", 4243, "%3")` 10 times. All return
    `"claude"`, `self.own_calls == 1`, and `self.calls == 0` (children never
    consulted once own comm answers).
  - `CacheTest.test_repeated_calls_hit_the_cache` (existing): also assert
    `self.own_calls == 1`.
  - `NegativeCacheRetryTest.test_backoff_bounds_the_lookup_rate` (existing): also
    assert `self.own_calls == self.calls` and `self.own_calls <= 3`, so the miss
    backoff gates both rungs equally.
  - `NegativeCacheRetryTest.test_own_comm_miss_inside_retry_interval_is_not_re_looked_up`:
    one miss, then 5 calls with the clock advanced by less than
    `_MISS_RETRY_SCHEDULE[0]`. `self.own_calls == 1`. Then set `self.own = "claude"`
    and advance past the step: the call resolves `"claude"` and
    `self.own_calls == 2`.
  - `NegativeCacheRetryTest.test_a_resolved_pane_is_never_re_looked_up` (existing):
    also assert that `own_calls` does not grow after the first resolution.
  Pre-fix control for this block: temporarily move the `_own_command` call above the
  cache lookup, confirm that the counting assertions fail, then restore it. Record
  the result. Do the same in
  `RungOneTest.test_rung_two_is_not_reached_when_rung_one_answers` (make it raise,
  like the child stub). `RungTwoTest` uses real `sh` trees whose own comm is `sh`,
  so it needs no stub.
- Update the module docstring's numbered list to cover the new rung.

**`tests/test_prompt_detection.py` `_check_fixture_is_isolated_from_host_process_table`**
(t1763): stub `agent_keys._own_command = lambda pid: "claude"` alongside the
existing `_child_commands` stub, and restore both. That keeps the host-isolation
check covering **both** pid-driven rungs, rather than passing only because the new
rung was never tested.

**`tests/test_minimonitor_concern_action.py`**
- `test_refuses_unresolvable_followed_pane`: also assert `"could not identify"` is
  in the message, and that `"supports"` is **not**. This pins the new distinction.
- `test_refuses_unsupported_followed_agent` (the `_UNDETECTED_KEY` one): also
  assert that `"could not identify"` is not in the message.

### 4. Pre-fix control

Before applying step 1, run the new `OwnCommandRungTest` (written first) against
the unfixed `agent_keys.py`. With `_own_command` absent, the substitution creates a
new attribute that the code never reads, so `test_version_string_command_…` and
`test_real_process_own_comm` must **fail** (they return `""`). Likewise, the
strengthened minimonitor assertion must fail before step 2. Record both failures.

### Post-phase (risk mitigations)

1. [sweep_fake_pid_fixtures] Run
   `grep -rnE "pane_pid=[1-9][0-9]*" tests/` and inspect each hit whose
   `current_command` is **not** an agent name (`claude`/`codex`/`opencode`) and whose
   path reaches `agent_key_from_pane` (monitor `_classify_batch` and the call sites
   ~3046/3141/3233/3320, `pane_state_probe`, minimonitor `_resolve_shadow_agent_key`).
   For each one that asserts on `agent_key`, `scoped` or scoped prompt matching,
   either switch it to `pane_pid=0` (the documented "no pid" value, as t1763 did) or
   stub `agent_keys._own_command`. Leave fixtures alone where the command already
   resolves at rung 1, or where the assertion does not depend on the key. List
   every hit with its verdict (changed / not affected and why) in the Final
   Implementation Notes. Then re-run the full suite and compare it against the
   `baseline_suite_before_rung` log.

## Verification

- `python3 tests/test_agent_keys.py`
- `python3 tests/test_prompt_detection.py`
- `python3 -m pytest tests/test_minimonitor_concern_action.py tests/test_monitor_markup_literal_sinks.py -q`
  (or `--test-dir` through the runner)
- Full Python suite: `bash tests/run_all_python_tests.sh`, reading only the last
  verdict line. Because `$TMUX` is set in this session, the live-tmux carve-out
  modules may need to be reported as not run, never as passed (see memory note).
- Live check (task item 5): from a Python one-liner, run
  `agent_key_from_pane("2.1.306", <pid of %4>, "%4")` and expect `claude`. Then, in
  a real minimonitor following a Claude pane with a shadow, press `L` and confirm
  the loop arms. That step is manual if no shadow is open, so report it as run or
  not run.
- Step 9 (Post-Implementation): commit, archive the task, and carry the
  `risk_evaluated` gate.

## Risk

### Code-health risk: low
- The new rung runs a real `ps` on the pane pid. Fixtures that stub only `_child_commands` with fake pids (4242, 5150, 777…) can then resolve whatever real process holds that pid on the host, which makes them flaky on a box with many Claude processes · severity: low (residual: addressed by the step-3 stubs, with a baseline to attribute any failure, via inline pre-phase baseline_suite_before_rung) · → mitigation: inline pre-phase baseline_suite_before_rung
- One extra `ps` call per pid-driven lookup on the per-tick refresh path. This is bounded by the existing positive cache (once per pane) and the miss backoff · severity: low · → mitigation: none
- Other test modules build monitor fixtures with non-agent commands and literal fake pids (`test_agent_sessions_*`, `test_monitor_*`), and these now also hit the own-comm rung. The children rung already gave them the same class of exposure, but own comm is a more direct hit · severity: low (residual: addressed by inline post-phase sweep_fake_pid_fixtures) · → mitigation: inline post-phase sweep_fake_pid_fixtures

### Goal-achievement risk: low
- Depends on `ps -o comm=` reporting the invoked name. Measured true for every live Claude pane here, but a Claude launched by its versioned path would still read `2.1.306` and stay unresolved (documented residual, and the new message says "could not identify" rather than "unsupported") · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: baseline_suite_before_rung | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — host-dependent stubbed fixtures | desc: Run the full Python suite on the unfixed tree and record failing modules as the attribution baseline
- timing: post-phase | name: sweep_fake_pid_fixtures | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — fake-pid monitor fixtures reaching the own-comm rung | desc: Audit literal fake pane_pid fixtures with non-agent commands; pin them to pane_pid=0 or stub _own_command where they assert on the key

## Final Implementation Notes
- **Actual work done:** Added `agent_keys._own_command` and made `agent_key_from_pane` a three-rung ladder (tmux command → pane process's own comm → one level of children), with both pid-driven rungs behind the existing positive/negative caches. Rewrote the module and function docstrings with the re-measured table. Split minimonitor's `L` refusal into "could not identify the followed agent from pane command '…'" (`agent_key == ""`) versus "unavailable for '<key>' — supports …" (resolved but unsupported). Tests: `OwnCommandRungTest` (8 cases, including a real agent-named symlink to a version-named binary), counting `_own_command` stubs in `CacheTest`/`NegativeCacheRetryTest` with new cache-placement assertions, an own-comm-must-not-run assertion in `RungOneTest`, the t1763 isolation check extended to both pid rungs, and the minimonitor refusal distinction pinned.
- **Deviations from plan:** (1) `tests/test_monitor_markup_literal_sinks.py`: the "recheck unavailable (shadow command)" site's driver used `agent_key=""` and so silently started hitting the new followed-side early return. It now passes while proving the wrong toast. The driver now sets `agent_key="claude"` when the followed side is supported, and the site verifiably reaches the shadow-side toast again. (2) `tests/test_prompt_scoping_live.py`: assertion message "rung 2" → "the child rung" (wording only).
- **Issues encountered:** The task body's root cause ("process title set to the version") was wrong. Measured during planning: `~/.local/bin/claude` is a symlink to `~/.local/share/claude/versions/2.1.306`; tmux reports the resolved file, `ps` the invoked path.
- **Key decisions:** Own comm outranks children (it is what the pane *is*). Children are not consulted once it resolves. A Claude launched by its versioned path stays unresolved (accepted, documented residual).
- **Verification as run:** Pre-fix controls: 11 `test_agent_keys` failures against unfixed code; the strengthened `test_refuses_unresolvable_followed_pane` failed before the message change; with the `_own_command` call deliberately misplaced above the caches, 5 counting tests failed (then restored). Baseline full suite (unfixed, runner=unittest because pytest is not installed): `PYTHON SUITE: FAILED (runner=unittest, exit=1)` with 10 failures (9 `test_sync_action_runner.TimeoutContainmentTests`, 1 `test_model_supersession.RobustnessTests.test_recovery_command_quotes_the_repository_path`). After the fix: the identical 10 failures, none new. Live: every real `2.1.306` pane on `-L ait` resolves to `claude`, and codex still resolves. **Not run:** the manual `L` arm against a real Claude pane with a shadow open.
- **Post-phase sweep_fake_pid_fixtures:** Done empirically rather than by grep alone. The whole unittest suite was run with `agent_keys._own_command` forced to `"claude"` (worst-case host), and the result was diffed against the baseline. Verdicts for the 10 extra failures: the 8 `test_agent_keys` RungTwo/own-comm cases are not affected in reality (they drive real rungs or `_own_command` itself on test-spawned `sh` processes, so only the stub breaks them). `test_prompt_scoping_live.test_wrapper_pane_resolves_through_its_child` is not affected (its pane is a test-spawned process on a private tmux socket). `test_monitor_finalize_offload.test_unresolvable_pane_falls_open_and_says_so` was **changed**: `_pane()` uses the literal fake pid 1009 with command `node`, so it is host-dependent through both pid rungs. It now stubs `_own_command`/`_child_commands` empty and passes under a hostile run of both rungs. Every other fixture with a literal `pane_pid` (`test_agent_sessions_*`, `test_monitor_*`, `test_agent_freeze`, …) passed under the hostile run: either rung 1 answers or the assertion does not depend on the key. Bash suites were not part of this sweep.
- **Upstream defects identified:** None

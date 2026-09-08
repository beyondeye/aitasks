---
Task: t1705_5_restore_and_repick_flows.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_1_*.md … aitasks/t1705/t1705_4_*.md, aitasks/t1705/t1705_6_*.md … aitasks/t1705/t1705_10_*.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-08 10:18
---

# t1705_5 — Restore and re-pick flows

## Step 0 — tmux preflight (run BEFORE anything else; blocking)

This task destructively manipulates tmux (`respawn-pane -k`, real `pane-died`
cleanup hooks, `kill-window`/`kill-server` on an isolated server). Its live
tests call `tests/lib/tmux_isolation.sh::require_clean_ait_server`, which
refuses to run from inside tmux or while the dedicated `-L ait` server has any
pane. Check this **first**, before planning or editing a file:

```bash
[ -z "${TMUX:-}" ] && echo "PREFLIGHT_OK: not inside tmux" || { echo "PREFLIGHT_BLOCKED: this session runs inside tmux ($TMUX)"; }
tmux -L ait list-panes -a -F '#{pane_id} #{window_name}' 2>/dev/null && echo "NOTE: the -L ait server has panes — stop 'ait ide' / close them before running the live suites" || echo "PREFLIGHT_OK: -L ait server idle"
```

- `PREFLIGHT_BLOCKED` → **do not implement.** Execute the workflow's **Task
  Abort Procedure** (`task-abort.md`) so the task reverts to `Ready` with its
  plan kept, and tell the user to re-pick from a terminal that is NOT inside
  tmux. Do not set `AIT_LIVE_TMUX_TEST_FORCE=1` — it is for a dedicated CI
  box only.
- `-L ait` server has panes → implementation may proceed, but the live suites
  will refuse until that server is stopped; say so in the Final
  Implementation Notes if verification had to wait.

> **Preflight history.** The 2026-09-07 planning session ran this check and got
> `PREFLIGHT_BLOCKED` (inside the `-L ait` server itself, 5 panes). Planning
> proceeded — it writes no code and runs no tmux — and stopped at plan approval.
> Implementation still requires a clean, non-tmux shell.

## Context

The acknowledged two-phase restore (PINNED §D), re-pick, Restore-All, the
`--resume-session` seam in `aitask_codeagent.sh`, and the `restoring` /
`aborting` rows of reconcile. Lands **before** the viewer (t1705_6): the
viewer only calls `aitask_frozen.sh restore <id>` through `run-shell -b`, and
this child's rollback path is exercised with `AITASKS_FROZEN_STANDIN_CMD`.
The fake agent from t1705_1 (`tests/lib/fake_agent.sh`) is the replacement
process in every automated case; it must exec the **shipped** hook so the
acknowledgement path is the real one.

**Tmux-stress** — implement and verify from a shell outside the `-L ait` server.

## Verification findings (re-verified 2026-09-07, against `954f6738a`)

This plan was written at parent-decomposition time, **before** t1705_2 (store),
t1705_3 (hooks), t1705_4 (freeze engine + reconcile) and t1716 (env-passing
evidence) landed. Every anchor and assumption below was re-checked against the
tree. Anchors that verified clean are not re-listed; these are the deltas that
change the work.

**V1 — Deliverable 4 is already implemented; it becomes test-only.**
`_reconcile_restoring` (`lib/agent_freeze.py:833`) and `_reconcile_aborting`
(`:918`) already implement **every** `restoring` / `aborting` row of the §C
table: pane-gone, mismatch-by-`last_error`, pane-dead, viewer-here by
`standin_pid`, replacement-here by `launch_pid` + ack grace, and the
`launch_pid==0` indeterminate → `2 × stale_op_grace` → abort path. t1705_4's own
docstring says so: *"The restore COORDINATOR is t1705_5; this is only the repair
side."* → **Implementation step 5 changes from "implement" to "verify by test."**
The only production edit left in `agent_freeze.py` is the grace accessor in V2.

**V2 — The plan's test grace knobs do not exist. This is the load-bearing fix.**
The old test spec said "`restore_ack_grace=5`, `stale_op_grace=2` via a scratch
`project_config.yaml`". Neither half is real:

- `stale_op_grace` is overridden by the **env** seam `AITASKS_STALE_OP_GRACE`,
  honoured only under `AITASKS_TEST_MODE=1` (`lib/agent_sessions.py:605-628`).
  `tests/test_freeze_engine_live.sh:102` uses `AITASKS_STALE_OP_GRACE=1`.
- `RESTORE_ACK_GRACE = 20.0` is a **hardcoded module constant**
  (`lib/agent_freeze.py:94`, read at `:899`). There is **no** override — not
  config, not env.

A test written to the old spec would silently run at 20 s / 60 s: the
`test_freeze_engine_live.sh`-style timings would blow out, and the
`session_mismatch` case's "**the liveness fallback must not fire** (assert
elapsed < grace)" assertion would pass **vacuously** — it would be asserting
against a grace it never shortened. Fix in step 0 below, before any test is
written.

**V3 — `restore-begin` and `lease-take` both require `--owner-pid`.** The
shipped surface is `restore-begin <id> --owner-pid <pid> --mode resume|repick`
and `lease-take <id> --owner-pid <pid>`. Amendment A7 records this for
`restore-begin`, but the plan body and PINNED §A/§D still show both verbs
without it. A defaulted or omitted pid is a usage error (exit 2); a *wrong* one
degrades the lease to a bare 60 s timer and lets reconcile abort a restore
that is still polling.

**V4 — Env passing: `respawn-pane -e` is now preferred over the `env` prefix.**
PINNED §D step 3 specifies the `env VAR=… <argv>` prefix. t1716 measured the
native flag (spike Case 3b) and the parent's PINNED spike findings now read
*"Prefer `-e`"*, with the prefix kept as the fallback for a build without it.
Both preserve `#{pane_pid} == agent pid`, which is the assertion that actually
matters (the `pid_anchor` lock-liveness contract, t1465). Exact measured shape:

```
respawn-pane -k -e "VAR=value" -t <pane> "<command>"
```

**V5 — Only two of the four `AITASK_RESTORE_*` variables are consumed.** The
shipped hook (`aitask_session_hook.sh:144-146`) forwards **only**
`--restore-of "$AITASK_RESTORE_RECORD"` and `--nonce "$AITASK_RESTORE_NONCE"`.
The store reads the mode and the expected session **off the record**, not off
the environment (`lib/agent_sessions.py:781`:
`rec.restore_mode == "resume" and session_id != rec.codeagent_session_id`).
`AITASK_RESTORE_MODE` and `AITASK_RESTORE_EXPECT_SESSION` are inert today.
**Decision: export all four anyway**, but as *diagnostics* — they cost two extra
`-e` flags, they make a frozen pane's environment self-describing when a restore
has to be debugged by hand, and t1705_6's viewer may surface them. The plan no
longer implies the hook reads them.

**V6 — `setsid` contradiction, resolved in favour of the plan.** The task body's
deliverable 3 says the coordinator "`setsid`s itself"; this plan's step 4 says it
does not. The plan is right: spike finding #3 measured that **`run-shell -b`
outlives the pane that started it**, and the shipped `aitask_frozen.sh` header
already documents `run-shell -b` as the mechanism "how a coordinator that must
OUTLIVE the pane it respawns gets started". No `setsid`.

**V7 — `fake_agent.sh` is further along than the plan assumed, and further
behind in one place.** Already shipped: `--resume <id>`, bare `resume <id>`,
`FAKE_AGENT_EXIT=1`, `--report-env <file>`. Genuinely new:
`FAKE_AGENT_SESSION=<other>`, `FAKE_AGENT_NO_HOOK=1`, and — the substantial
one — **it never invokes the hook at all today**. Making it exec the shipped
`aitask_session_hook.sh` with a synthetic payload is the largest single test-
fixture item in this task, and it is what makes the ack path *real* rather than
simulated.

**V8 — `aitask_frozen.sh` dispatch needs a decision the plan never made.** The
script currently ends in `exec "$(require_ait_python)" "$FREEZE_PY" "$@"` —
unconditional. Adding `restore` requires routing that verb to a different
module. **Decision: dispatch in the shell** — `restore` execs `agent_restore.py`,
`freeze`/`reconcile` keep execing `agent_freeze.py`. That keeps each module's
`main()` owning exactly its own verbs and avoids `agent_freeze` importing
`agent_restore` (which would make the repair side depend on the coordinator it
was deliberately written to work without). Its documented exit codes (0 all-ok /
1 some-failed / 2 usage) extend to restore unchanged.

**V9 — `pick_launch_argv` is thinner than described, and carries a silent
behaviour-change risk.** Both cited call sites
(`monitor/minimonitor_app.py:3013`, `monitor/monitor_app.py:3598` — the plan's
`:3021` / `:3612` point inside the same blocks) reduce to:

```python
full_cmd = resolve_dry_run_command(target_root, "pick", target_id)   # NO agent_string
window_name = f"agent-pick-{target_id}"
agent_string = resolve_agent_string(target_root, "pick")
```

Note they **do not** pass `agent_string` into `resolve_dry_run_command`. A shared
helper whose signature is `(root, task_id, agent_string=None)` must therefore
default to `None` at those two sites, or the TUIs would silently start launching
a different agent/model than they do today. The extraction is still worth doing
(t1705_7 consumes it for its restore keys), but it is a *three-line* helper, not
a shape — scope it honestly and pin behaviour-preservation with the existing
pick tests.

**V10 — `resolve_dry_run_command` genuinely needs the new parameter.** Its
signature is `(project_root, operation, *args, agent_string=None)` and it builds
`[wrapper] + [--agent-string s] + [--dry-run, invoke, operation] + args`
(`:234-264`). `*args` land **after** `invoke <operation>`, so they are operation
arguments; `--resume-session` is a **global** flag and must precede `--dry-run`.
The plan's `extra_global_flags` extension is correct and required.

**V11 — repeated `-e` is unmeasured.** Spike Case 3b passed exactly **one**
`-e`. tmux documents the flag as repeatable, but this task will pass four, so
the new live test must assert that **all** of them arrive — otherwise a
silently-dropped `AITASK_RESTORE_NONCE` would turn every hook ack into a
`NONCE_MISMATCH` and route every restore down the liveness fallback.

**V12 — The hook can beat `restore-launched`, and the naive handling kills a
restored agent.** `restore_launched` is state-guarded to `restoring`
(`lib/agent_sessions.py:1011`), and so is `restore_abort` (`:1055`). The
replacement agent's SessionStart hook acks by moving the record
`restoring → live` with `ack=hook`, and it can do so before the coordinator
completes its `display-message` round-trip plus a wrapper subprocess spawn — in
the live fixture, where the fake agent execs the hook immediately, it will do so
most of the time. `restore-launched` is then refused with
`TRANSITION_REFUSED:<id>|live|restore-launched`. A coordinator that reads that
refusal as failure takes the abort branch and `respawn-pane -k`s the pane back
to the stand-in — **killing an agent that was successfully restored**, which is
strictly worse than never restoring. The fix is a re-read rule binding every
store verb in the sequence (step 3), plus a test that forces the ordering
instead of hoping for it. The original plan specified neither.

## Files

- **New** `.aitask-scripts/lib/agent_restore.py` — imports the SHARED
  `.aitask-scripts/lib/agent_frozen_ops.py` (shipped by t1738) for the store
  wire protocol and tmux plumbing: `store` / `store_show` / `nonce_from` /
  `run` / `pane_facts` / `pane_location` / `set_option` / `unset_option` /
  `respawn` / `int_or_zero` / `test_mode` / `make_fail_at` / `pause_at` /
  `StageFailure` / `SESSIONS_SH` / the four `EXIT_*` codes. Do **not** copy them
  and do **not** import `agent_freeze`'s privates — that was the risk this
  task's mitigation removed
- **Edit** `.aitask-scripts/aitask_frozen.sh` — `restore <id> [--repick]`, `restore --all`; shell-level verb dispatch (V8)
- **Edit** `.aitask-scripts/aitask_codeagent.sh` — `--resume-session <sid>` (global flag, `build_invoke_command`, `show_help`)
- **Edit** `.aitask-scripts/lib/agent_freeze.py` — **grace accessor only** (V1/V2): add `restore_ack_grace()`, switch the `RESTORE_ACK_GRACE` read in `_reconcile_restoring` to it (t1738 moved code above it, so re-locate by name rather than by the old `:899`). **Reconsider the placement:** putting the accessor here makes `agent_restore` import the repair module for one function — the exact coupling t1738's mitigation removed. `lib/agent_frozen_ops.py` is the natural home; t1738 deliberately left `RESTORE_ACK_GRACE` / `_epoch` / `_stale_grace` in `agent_freeze.py` because the call is this task's to make
- **Edit** `.aitask-scripts/lib/agent_launch_utils.py` — `resolve_dry_run_command(..., extra_global_flags=None)` (V10) and `pick_launch_argv(root, task_id, agent_string=None)` (V9)
- **Edit** `monitor/minimonitor_app.py`, `monitor/monitor_app.py` — switch to `pick_launch_argv`, behaviour-identical (V9)
- **Edit** `tests/lib/fake_agent.sh` — `FAKE_AGENT_SESSION`, `FAKE_AGENT_NO_HOOK`, `FAKE_AGENT_HOOK_DELAY` (V12 race forcing), **exec the shipped hook** (V7)
- **New tests** `tests/test_codeagent_resume_session.sh`, `tests/test_restore_flows_live.sh`, `tests/test_agent_restore.py` (unit, fake `TmuxClient` + fake wrapper)

## Implementation steps

### Step A — Propagate the amended contract to the parent and sibling plans (FIRST; before any code)

**Why this is step A and not a footnote.** Amendments B1–B4 deviate from the
PINNED §D text, and the PINNED rule is explicit: *"if a child must deviate,
update the parent plan and every sibling plan in the same commit."* Until that
happens, the durable files carry the obsolete contract while this approval rests
on the amended one. Measured blast radius (`grep -rln "env AITASK_RESTORE_RECORD"
aiplans/`):

| file | why it matters |
|---|---|
| `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` | the parent; **internally inconsistent today** — §D says `env` prefix, its own PINNED spike findings say *"Prefer `-e`"* |
| `aiplans/p1705/p1705_6_frozenagent_viewer_tui.md` | the viewer shells out to `restore`; reads §D for the contract |
| `aiplans/p1705/p1705_7_monitor_minimonitor_frozen_rows.md` | wires the restore keys; also consumes `pick_launch_argv` |
| `aiplans/p1705/p1705_8_frozen_agents_acceptance_test.md` | **the acceptance test** — would assert the obsolete contract |
| `aiplans/p1705/p1705_9_frozenagent_tui_docs.md`, `p1705_10_freeze_restore_workflow_docs.md` | **the docs** — would publish the obsolete contract |

Actions:

1. Add the `## Amendments from re-verification` block (B1–B4) to the parent
   plan, and resolve its internal §D-vs-spike-findings contradiction in favour
   of `-e`.
2. Add the same supersession banner to the PINNED block of each of the five
   pending sibling plans above.
3. **Do not touch `aiplans/archived/p1705/p1705_1..4`** or the archived task
   file. Those are historical records of what was true at implementation time;
   rewriting them would falsify the record. B1/B4 are not deviations anyway —
   they are the shipped reality that t1705_2 / t1705_4 established, and the
   archived plans correctly describe their own moment.
4. Commit the parent + five siblings together (`./ait git`), per the
   same-commit rule.

> **This plan file itself is fixed by approval, not by step A.** `aiplans/p1705/
> p1705_5_restore_and_repick_flows.md` on disk is still the pre-verification
> draft; the verify path writes it only when `ExitPlanMode` externalizes, which
> is why a reviewer reading the checked-in file sees none of V1–V12. Step A
> covers the *other* eight files, which no externalization will touch.

### The rest of the implementation

> **One blocking "before" task precedes all of this.**
> `extract_freeze_store_helpers` (see `### Planned mitigations`) is confirmed as
> a spawned *before* mitigation: workflow Step 7 creates it, wires it into this
> task's `depends:`, and stops this task until it lands. Step 3 then imports the
> shared helpers instead of copying them. Expect the first post-approval session
> to create that task and stop — that is the confirmed design, not a failure.

### Pre-phase (risk mitigations)

These run **before** step 0. Each is a confirmed inline mitigation from the
`### Planned mitigations` block below; each is test-first, so it fails against
the current tree and passes once the step it guards has landed.

1. `[measure_repeated_respawn_e]` Add **Case 3c** to
   `tests/test_frozen_standin_spike.sh`, alongside Case 3b (`:504-560`): respawn
   a pane with **four** `-e` flags —
   `respawn-pane -k -e A=1 -e B=2 -e C=3 -e D=4 -t <pane> "'$FAKE_AGENT' --report-env '$report'"` —
   and assert via the self-report that **all four** arrive and that
   `#{pane_pid}` still equals the reported pid. Extend `fake_agent.sh
   --report-env` to echo the extra names. Record a `finding` line in the spike's
   own format. Gate: this must pass before step 3 commits to `-e` delivery; if a
   build accepts only the last `-e`, step 3 falls back to the `env` prefix
   wholesale rather than per-variable.

2. `[assert_grace_seam_effective]` Write the grace-seam contract test **before**
   step 0 implements it, so the bar is set by a test that is currently red:
   - unit (`tests/test_agent_restore.py`): `restore_ack_grace()` precedence —
     `AITASKS_RESTORE_ACK_GRACE` wins **only** under `AITASKS_TEST_MODE=1`; else
     `frozen.restore_ack_grace` from `project_config.yaml`; else `20.0`;
     non-positive and unparseable values fall back to the default;
   - fixture guard in `tests/test_restore_flows_live.sh`: assert the **effective**
     grace is `< 10` before running any timing case, and abort the file with a
     named failure if it is not. This is the guard that would have caught V2:
     without it, the `session_mismatch` case's "liveness fallback must not fire"
     assertion passes while testing nothing.

3. `[pin_pick_argv_behaviour]` Before the step-2 extraction, capture the exact
   command string both TUIs produce today. Add a characterization test that
   calls the current `resolve_dry_run_command(root, "pick", task_id)` path and
   pins the result, plus the `agent-pick-<id>` window-name convention. The
   extraction in step 2 must leave this test green **unchanged** — that is what
   proves the two call sites did not silently start resolving a different
   agent/model (V9).

**0. Grace accessor first (V2) — nothing else is testable until this lands.**
In `lib/agent_freeze.py`, add beside `capture_max_lines` (`:281`, the existing
`frozen.*` precedent, read with `config_utils.load_yaml_config` — never
hand-parsed):

```python
RESTORE_ACK_GRACE = 20.0          # keep as the default

def restore_ack_grace(root=None) -> float:
    """`frozen.restore_ack_grace`, with the test-mode env seam."""
    # 1. AITASKS_RESTORE_ACK_GRACE, honoured ONLY under AITASKS_TEST_MODE=1
    #    (mirrors agent_sessions._stale_op_grace, :605-628)
    # 2. else frozen.restore_ack_grace from project_config.yaml
    # 3. else RESTORE_ACK_GRACE; non-positive / unparseable -> the default
```

Then **switch `agent_freeze.py:899` from the constant to this accessor**, and
have `agent_restore` read the same function. Coordinator and reconcile must not
be able to disagree about the grace — if they do, reconcile can liveness-confirm
a restore the coordinator is still waiting on.

1. **`--resume-session`** in `aitask_codeagent.sh`: `OPT_RESUME_SESSION=""`
   beside `OPT_HEADLESS` (`:36`); parse in `main` beside `--headless` (`:688`)
   as `--resume-session) OPT_RESUME_SESSION="$2"; shift 2 ;;`; validate
   `^[A-Za-z0-9._-]+$` (`die` otherwise — the value reaches an argv);
   `cmd_invoke` (`:586`) refuses it for any operation but `raw`
   (`die "--resume-session requires 'invoke raw'"`). In `build_invoke_command`,
   which pre-seeds `CMD=("$binary" "$model_flag" "$cli_id")` at `:443`:
   - `claudecode` → **append**: `CMD+=(--resume "$OPT_RESUME_SESSION")` — after
     the model flag, before any prompt positional (the `explore-relay` ordering
     hazard, `:510-513`);
   - `codex` → **rebuild** (the pre-seed puts the model flag first, but `resume`
     must be the leading positional):
     `CMD=("$binary" resume "$OPT_RESUME_SESSION" "$model_flag" "$cli_id")`;
   - `opencode` → `die "RESUME_UNSUPPORTED:opencode"` (exit 2).

   `show_help` documents it in the Options block (`:633-641`). `--dry-run`
   prints `DRY_RUN:` + `%q` args as today.

   > **Codex reality check (t1705_1 PINNED).** Codex's SessionStart hook fires
   > under `codex exec` and **never in the interactive TUI**, which is the
   > framework's launch path — so a codex record's `codeagent_session_id` is
   > empty in practice and `codex = re-pick only` stands. The `--resume-session`
   > codex branch is therefore an argv-completeness/dry-run surface, not a live
   > path. Build it, pin it with a dry-run test, and do not write a live codex
   > resume case.

2. **`pick_launch_argv`** (V9) — pure refactor, own commit, both TUIs green.
   `pick_launch_argv(root, task_id, agent_string=None) -> tuple[str | None, str]`
   returning `(full_cmd, window_name)` where `window_name = f"agent-pick-{task_id}"`.
   The two TUI sites call it **without** `agent_string` so their behaviour is
   byte-identical; `agent_restore` calls it **with** the record's agent string.

3. **`lib/agent_restore.py`.**
   ```python
   @dataclass class RestoreResult: record_id: str; ok: bool; outcome: str; line: str
   # outcome ∈ hook|liveness|session_mismatch|agent_exited|no_session|binary|nonce_mismatch
   def build_resume_argv(rec) -> str | None   # resolve_dry_run_command(rec.root, "raw",
                                              #   agent_string=rec.agent_string,
                                              #   extra_global_flags=["--resume-session", rec.codeagent_session_id])
   def build_repick_argv(rec) -> str | None   # pick_launch_argv(rec.root, rec.task_id, rec.agent_string)
   def restore(record_id, *, repick=False, grace=None) -> RestoreResult
   def restore_all() -> list[RestoreResult]
   ```

   `restore` follows §D 1–5 literally, with the V3/V4/V5 corrections applied:

   - **Preflight, before any store write.** Empty `codeagent_session_id` and no
     `--repick` → `RESTORE_FAILED:<id>|no_session` (nothing changes). Agent
     binary missing → `RESTORE_FAILED:<id>|binary`. Both are detected by the
     `aitask_codeagent.sh --dry-run` probe returning `None` — a failed probe is
     the binary check, so there is no second `shutil.which` path to keep in sync.
     Transcript missing → **warn and continue** (it is not needed to resume).
   - `restore-begin <id> --owner-pid <os.getpid()> --mode <m>` **(V3)** → nonce.

     `os.getpid()` **is** the detached coordinator's pid, and only because of the
     `exec` chain: `run-shell -b` → `aitask_frozen.sh` → `exec python
     agent_restore.py`. The shell replaces itself, so the Python process is the
     one tmux detached and the one that outlives the respawn. Do not pass a
     parent pid, and do not let the value default: the store uses it to answer
     "is the coordinator still working?", and a pid that is already dead
     degrades the lease to a bare `stale_op_grace` timer — after which
     `reconcile` will abort this restore **while it is still polling for the
     ack**, and the coordinator's next verb fails `NONCE_MISMATCH`. The user's
     restore is then lost silently. If the `exec` chain in step 4 is ever
     changed to a fork, this line must change with it.
   - Build the argv, then deliver the restore identity by **`respawn-pane -e`
     (V4)**, one `-e` per variable, all four **(V5)**:
     `-e AITASK_RESTORE_RECORD=<id> -e AITASK_RESTORE_NONCE=<n>
      -e AITASK_RESTORE_MODE=<m> -e AITASK_RESTORE_EXPECT_SESSION=<sid>`.
     Keep the `env`-prefix builder as a documented fallback for a tmux without
     `-e`, selected once at module import, not per call.
   - `set-option -pu @aitask_standin_ready` → `respawn-pane -k -e … -t <pane>
     '<argv>'` — or, when `rec.pane_id == ""`, `launch_in_tmux` into
     `unique_window_name(existing, rec.window)` in the session hosting `rec.root`
     (first match of `discover_aitasks_sessions`; none →
     `RESTORE_FAILED:<id>|no_session_for_root`, then `restore-abort` +
     `standin-respawned --nonce --pane "" --pane-pid 0`).
   - Read `#{pane_id}\t#{pane_pid}` → `restore-launched --nonce --pane --pane-pid`.

     **⚠ The hook can win this race (V12). Handle it explicitly.**
     `restore_launched` is guarded by `_require_state(rec, "restore-launched",
     STATE_RESTORING)` (`lib/agent_sessions.py:1011`). The replacement agent's
     SessionStart hook can fire and ack (`restoring → live`, `ack=hook`) before
     the coordinator finishes its `display-message` round-trip and its wrapper
     subprocess — and in the live tests, where the fake agent execs the hook
     immediately, it routinely will. `restore-launched` is then refused with
     `TRANSITION_REFUSED:<id>|live|restore-launched` (exit 5).

     **A refused verb is never, by itself, a failure signal.** On any non-zero
     exit from `restore-launched`, **re-read the record** (`show <id>`) before
     deciding anything:
     - `state == live` and `ack == hook` → the hook already acknowledged: this
       is **success**. Clear `@aitask_frozen`, print `RESTORED:<id>|hook`, and
       return. `launch_pid` legitimately stays `0` — nothing needs it, because
       the liveness path (which is what requires it) is not taken.
     - `state == restoring` and `last_error` carries this nonce → the mismatch
       branch, as below.
     - anything else → a real failure; take the abort branch.

     **This rule binds every verb in the sequence, not just this one.** The
     abort branch itself calls `restore-abort`, which is guarded identically
     (`:1055`), and the branch's *next* action is `respawn-pane -k` back to the
     stand-in. Rolling back without checking `restore-abort`'s exit status would
     **kill a successfully restored agent** — the single worst outcome this task
     can produce, and strictly worse than never restoring at all. So: check the
     exit status of every store verb, and enter the rollback only once the store
     has confirmed the record actually moved to `aborting`.

   - Poll loop (0.5 s) against `show <id>` until one of the four §D outcomes:
     `state==live and ack==hook` → clear `@aitask_frozen` → `RESTORED:<id>|hook`;
     `last_error` starts with this nonce → abort branch `session_mismatch`;
     `pane_dead == 1` → abort branch `agent_exited`;
     elapsed ≥ `restore_ack_grace()` and `pane_pid == launch_pid` →
     `restore-confirm --nonce --pane --pane-pid` → clear stamp →
     `RESTORED:<id>|liveness`.
   - Abort branch = `restore-abort --nonce` → `set-option -pu
     @aitask_standin_ready` → `respawn-pane -k <standin_command(id)>` →
     `standin-respawned --nonce --pane --pane-pid`.
   - Any `NONCE_MISMATCH` → return `outcome="nonce_mismatch"` and issue **no
     further tmux calls**; reconcile already settled it.
   - **Codex result-line honesty (task edge case).** When
     `rec.agent_kind == "codex"`, a hook ack cannot arrive on the interactive
     path, so the only reachable success is `liveness` (captures kept). Say so
     in the printed line rather than letting it read like an unexplained
     downgrade.
   - Seams: `AITASKS_RESTORE_FAIL_AT=begin|respawn|ack` and
     `AITASKS_FROZEN_PAUSE_AT=respawn|aborting`, both under `AITASKS_TEST_MODE=1`,
     from the SHARED module `lib/agent_frozen_ops` (t1738), not from
     `agent_freeze`: bind `_fail_at = frozen_ops.make_fail_at("AITASKS_RESTORE_FAIL_AT")`
     — the factory exists so this engine's injected failures cannot fire in the
     freeze engine — and call `frozen_ops.pause_at` / `frozen_ops.test_mode`
     directly. **Call every shared function through the module**, never
     `from agent_frozen_ops import store as _store`: `store` and `_TMUX` are
     swapped in place by the tests, and an import-time alias binds the original
     object and bypasses the swap. `tests/test_agent_frozen_ops.py` fails on any
     engine module that holds such an alias, and it already looks up
     `agent_restore` dynamically.

4. **Detached entry** — `aitask_frozen.sh restore <id> [--repick] | --all`.
   Dispatch in the shell (V8): `restore` execs `lib/agent_restore.py`, the
   existing verbs keep execing `lib/agent_freeze.py`. **No `setsid` (V6)** — the
   caller detaches via `run-shell -b`, which is measured to outlive the pane;
   running in the foreground means a shell user also sees the result line.
   Document in the header that TUIs must use `run-shell -b`, and update the
   header's "`restore` arrives in t1705_5" note and the `usage()` block.

5. **Reconcile rows — verify, do not implement (V1).** `_reconcile_restoring`
   and `_reconcile_aborting` already cover the §C table. This step's only
   production change is step 0's grace accessor at `:899`. The obligation is a
   **test** one: the two coordinator-death cases below must prove the shipped
   repair side actually settles a record this task's coordinator abandoned.

6. **Restore-All** — every `frozen` record, sequential, results collected; one
   failure never stops the batch; summary line `RESTORE_ALL:<ok>/<total>`.

## Tests

**`tests/test_codeagent_resume_session.sh`** — dry-run argv for the three
agents (ordering vs the model flag: `--resume` *after* it for claudecode,
`resume` *first* for codex), refusal with `invoke pick`, invalid session id
rejected, `RESUME_UNSUPPORTED:opencode` exit 2.

**`tests/test_agent_restore.py`** — unit, fake `TmuxClient` + fake wrapper:
`build_resume_argv` / `build_repick_argv`; the `no_session` and `binary`
preflights write **nothing** to the store; `NONCE_MISMATCH` issues no tmux call;
`restore_ack_grace()` precedence (env seam under test mode > config > default,
non-positive → default).

**`tests/test_restore_flows_live.sh`** — isolated server. Fixture, mirroring
`tests/test_freeze_engine_live.sh:58-102`:

```bash
require_clean_ait_server     # FIRST — ordering is load-bearing
require_isolated_tmux        # SECOND
export AITASKS_TEST_MODE=1
export AITASKS_STALE_OP_GRACE=1          # env seam, NOT project_config (V2)
export AITASKS_RESTORE_ACK_GRACE=3       # env seam added in step 0 (V2)
export AITASKS_FROZEN_STANDIN_CMD="$PROJECT_DIR/tests/lib/fake_standin.sh"
```

fake agent on `PATH` as `claude`, real hook, real store. Cases:

- **happy resume** — `ack=hook`, captures deleted, `@aitask_frozen` cleared,
  `@aitask_record` on the pane, `pane_pid` updated;
- **happy repick** — new session id adopted;
- **all four `-e` variables arrive (V11)** — via `fake_agent.sh --report-env`;
  a dropped `AITASK_RESTORE_NONCE` would silently demote every ack to liveness;
- **`FAKE_AGENT_EXIT=1`** → `agent_exited`, back to `frozen`, capture intact,
  stand-in back and stamped, `restore_attempts=1`;
- **`FAKE_AGENT_SESSION=other`** → `last_error` persisted, `session_mismatch`,
  **assert elapsed < `AITASKS_RESTORE_ACK_GRACE`** (the liveness fallback must
  not fire) — this assertion is only meaningful because step 0 made the grace
  shortenable (V2);
- **`FAKE_AGENT_NO_HOOK=1`** → `liveness` after the grace, captures **kept**,
  `ack=liveness`;
- **gone-pane restore** → new window, same record id, no second record;
- **hook wins the launch race (V12)** — the fake agent execs the hook
  immediately, so `restore-launched` is refused with
  `TRANSITION_REFUSED:<id>|live|restore-launched`. Assert the coordinator
  re-reads, reports `RESTORED:<id>|hook`, deletes the captures, clears
  `@aitask_frozen`, and issues **no** rollback command (verify via the logging
  `tmux` wrapper on `PATH` — no `respawn-pane` back to the stand-in). Force the
  ordering rather than hoping for it: a `FAKE_AGENT_HOOK_DELAY=0` fixture that
  acks before the coordinator's `display-message` round-trip can complete.
  `launch_pid` is asserted to remain `0` — the liveness path is not taken, so
  nothing needs it;
- **an active restore is NOT taken over (concern 1 regression)** — mirroring
  `tests/test_freeze_engine_live.sh:335-351`: background a coordinator with
  `AITASKS_FROZEN_PAUSE_AT=respawn` so it `SIGSTOP`s itself holding the lease,
  then run `reconcile` **twice** — inside the grace and again **past** it — and
  assert `LEASE_HELD:<rid>` **both** times. A `SIGSTOP`ped process is alive, so
  the live-owner check must refuse takeover no matter how much grace elapsed.
  Then `SIGCONT` and assert the coordinator completes normally. This is the
  assertion that fails if `--owner-pid` is ever dropped or defaulted;
- **failure injection, one case per seam (concern 3)** — loop
  `AITASKS_RESTORE_FAIL_AT` over `begin|respawn|ack` the way
  `tests/test_freeze_engine_live.sh:273` loops the freeze seams. Each case
  asserts the **state and the recovery**, not just the exit code:
  - `begin` → the store was never written: record still `frozen`, no lease, no
    `restore_attempts` bump, capture intact, `@aitask_standin_ready` still set;
  - `respawn` → record `restoring` with a lease and the ready mark **cleared**;
    reconcile past the grace must put the stand-in back and return the record to
    `frozen` with the capture intact and the ready mark re-stamped (this is the
    stranded-lease / uncleared-ready-mark case, and it is the one that leaves a
    user staring at a dead pane if it regresses);
  - `ack` → the replacement is running but the coordinator died before
    resolving; reconcile liveness-confirms it via `launch_pid` past the grace,
    `ack=liveness`, captures **kept**;
- **coordinator killed after clearing ready, before respawn**
  (`AITASKS_FROZEN_PAUSE_AT=respawn` + `SIGKILL`) → reconcile aborts by
  `standin_pid`, never confirms;
- **coordinator `SIGSTOP`ped in `aborting`** → a second `restore` is
  `TRANSITION_REFUSED`; reconcile past the grace finishes; the resumed
  coordinator gets `NONCE_MISMATCH` and issues **no** tmux command (assert via a
  logging `tmux` wrapper on `PATH`);
- **Restore-All** with one failing record → `RESTORE_ALL:1/2`.

## Verification

```bash
bash tests/test_codeagent_resume_session.sh
bash tests/run_all_python_tests.sh                       # agent_restore unit + pick argv pins
bash tests/test_restore_flows_live.sh                    # outside -L ait
bash tests/test_freeze_engine_live.sh                    # still green (grace accessor touched :899)
bash tests/test_frozen_standin_spike.sh                  # the -e evidence this plan rests on
bash tests/test_no_raw_tmux.sh
shellcheck .aitask-scripts/aitask_codeagent.sh .aitask-scripts/aitask_frozen.sh
```

## Risk

### Code-health risk: high

- Editing `lib/agent_freeze.py:899` to read a configurable grace changes the
  behaviour of the **already-shipped, already-green** reconcile path (t1705_4).
  A wrong default or a mis-scoped env seam would alter reconcile timing for
  every frozen record, not just this task's · severity: medium · → mitigation: none (covered by re-running `tests/test_freeze_engine_live.sh` in Verification)
- The `pick_launch_argv` extraction touches two live TUIs
  (`minimonitor_app.py`, `monitor_app.py`) for a three-line helper. The specific
  hazard is measured, not hypothetical: the call sites do **not** pass
  `agent_string` today, so a helper that defaults it wrongly silently changes
  which agent/model every `pick` launch starts · severity: low (residual — the
  pre-extraction characterization test makes any behaviour change a test
  failure) · → mitigation: inline pre-phase pin_pick_argv_behaviour
- `agent_restore.py` is a new ~400-line coordinator that duplicates several
  private helpers from `agent_freeze.py` (`_store`, `_pane_facts`, `_respawn`,
  `_set_option`, the test seams). Copying them forks two engines that must stay
  in agreement about the store wire protocol; importing them couples the
  coordinator to a module deliberately written to work without it · severity: medium (residual — deferred to a blocking "before" task, so this plan does not land the duplication) · → mitigation: t1738
- The store's transitional verbs are state-guarded, so a lost race returns a
  refusal rather than an error — and a coordinator that reads a refusal as
  failure rolls back, `respawn-pane -k`ing a **successfully restored agent**
  back to the stand-in and destroying the session the user was trying to
  recover (V12). This was found on review, not during planning, which is the
  real signal here: the acknowledgement protocol's failure modes are not fully
  enumerated by the §D prose, and a second unenumerated one is plausible
  · severity: medium (residual — the step-3 re-read rule binds every verb in
  the sequence and the immediate-hook test forces the ordering) · → mitigation: none (addressed in-plan; no separate mitigation confirmed)
- The amended contract (B1–B4) initially existed only in this child's plan while
  the parent and five pending sibling plans — including the acceptance test and
  both docs tasks — still carried the obsolete §D. A sibling picked before this
  task lands would implement, test, or *document* the superseded protocol
  · severity: low (residual — implementation step A propagates and commits all
  six live files before any code is written) · → mitigation: none (addressed in-plan; no separate mitigation confirmed)
- Implementation cannot be verified from this machine's current shell (Step 0
  preflight blocked), so the live suite — the only thing that exercises the real
  tmux/hook/store path — is the easiest step to skip under time pressure · severity: high · → mitigation: none (procedural; the aggregate manual-verification sibling t1705_11 already carries the end-to-end check)

### Goal-achievement risk: medium

- The four-outcome acknowledgement protocol is the whole point of the task, and
  its most important negative assertion ("the liveness fallback must not fire on
  a session mismatch") was **unreachable as originally specified** (V2). The
  same class of defect — an assertion that passes without testing anything —
  could recur in the coordinator-death cases, which depend on `SIGSTOP`/`SIGKILL`
  timing against a shortened lease · severity: medium (residual — the inline
  guard closes the grace case specifically and fails the file loudly; the
  coordinator-death cases remain unguarded by it) · → mitigation: inline pre-phase assert_grace_seam_effective
- Codex cannot capture a session id on the interactive launch path (t1705_1
  PINNED), so the codex half of `--resume-session` is unexercisable end-to-end
  and is pinned only by dry-run argv. If codex's hook later becomes viable, the
  live behaviour is unproven · severity: low · → mitigation: none (accepted; no live path exists to test)
- Repeated `respawn-pane -e` is unmeasured (V11): the spike proved one variable,
  this task passes four. A tmux build that accepted only the last `-e` would
  drop the nonce and route every restore to the liveness fallback — a silent
  degradation that still *looks* like success · severity: low (residual —
  measured by the pre-phase spike case before step 3 relies on it) · → mitigation: inline pre-phase measure_repeated_respawn_e

### Planned mitigations
- timing: pre-phase | name: measure_repeated_respawn_e | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — repeated `-e` unmeasured | desc: Spike Case 3c asserting four `-e` variables all arrive and `#{pane_pid}` still equals the agent pid
- timing: pre-phase | name: assert_grace_seam_effective | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the "liveness fallback must not fire" assertion was unreachable | desc: Red-first unit test for `restore_ack_grace()` precedence plus a live-fixture guard aborting if the effective grace is not < 10s
- timing: pre-phase | name: pin_pick_argv_behaviour | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — `pick_launch_argv` extraction touches two live TUIs | desc: Characterization test pinning the pick command and window-name convention before the extraction, which must stay green unchanged after it
- timing: before | name: extract_freeze_store_helpers | type: refactor | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: code-health — new coordinator duplicates private helpers from agent_freeze.py | desc: Extract `_store` / `_pane_facts` / `_respawn` / `_set_option` / the test seams into a module both engines import, so `agent_restore.py` shares rather than forks the store wire protocol | created: t1738

**Post-inline reassessment (single pass, 2026-09-07).** Levels re-assessed
against the augmented plan (pre-phase block + main body). Three bullets drop to
residual `low`/`medium`, but neither dimension clears: code-health still carries
the unguarded `:899` edit and the procedural high-severity verification gap, and
goal-achievement still carries the unguarded coordinator-death timing cases.
Goal-achievement stays **medium**. No new risks were introduced by the inline
phases, and no mitigation selection was reopened.

**Post-review revision (2026-09-08).** Code-health is raised **medium → high**.
Not because the new race is unaddressed — step 3 handles it and a test forces it
— but because it was found by review rather than by planning. The plan now
carries two high-severity code-health concerns at once: a failure mode whose
naive handling destroys the user's session, and a live suite that cannot be run
from the machine this was planned on. Those compound: the test that would catch a
regression here is exactly the test that is easiest to skip. Mitigation selection
was **not** reopened (the review's own dispositions were blocking-fix-in-plan,
not new mitigations).

## Amendments from t1705_2 (store implementation, 2026-09-06)

**A7 — `restore-begin` REQUIRES `--owner-pid <pid>`.** Pass the **coordinator's**
pid — the detached `run-shell -b` process that outlives the respawn — never the
wrapper's own. The store uses it to answer "is the coordinator still working?",
and reconcile skips a record whose lease has a live owner. A defaulted pid is
dead the instant the verb returns, so the lease degrades to a bare 60 s timer and
reconcile can abort this restore mid-flight while it is still polling for the
ack; the coordinator's next verb then fails `NONCE_MISMATCH` and the user's
restore is silently lost. The wrapper rejects a missing value with exit 2.

**A4 — refusal wire lines.** The unacknowledged-restore refusal is unchanged
(`UPSERT_REFUSED:<id>|restoring_unacknowledged`); the sibling transitional states
now use the same `<state>_unacknowledged` shape.

## Amendments from re-verification (2026-09-07)

These supersede the verbatim PINNED text below where they conflict. Per the
PINNED rule, the parent plan wins on discrepancy — and in each case the parent's
own later evidence (the t1705_1/t1716 spike findings) is what supersedes the
earlier §D prose.

**B1 — §D step 2/§A `lease-take`: add `--owner-pid`** (see V3). Both
`restore-begin` and `lease-take` require it in the shipped wrapper.

**B2 — §D step 3: `respawn-pane -e` replaces the `env` prefix** (see V4). The
prefix remains the documented fallback for a tmux build without `-e`.

**B3 — §D step 3: the hook consumes only `RECORD` and `NONCE`** (see V5). All
four variables are still exported, as diagnostics.

**B4 — §C `restoring`/`aborting` rows are implemented** (see V1). The table
below is now a specification of *shipped* behaviour, and this task's obligation
against it is a testing one.

**B5 — B1–B4 are not self-executing: they must be propagated.** The PINNED rule
requires a deviating child to update the parent and every sibling plan *in the
same commit*. Eight files currently carry the obsolete §D contract; five of them
are pending sibling plans, including the acceptance test (t1705_8) and both docs
tasks (t1705_9/10). **Implementation step A** discharges this and must run before
any code. Archived plans are deliberately excluded.
## PINNED contracts (from p1705 — do not re-decide)

Copied verbatim from `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` §A–§D. On any discrepancy the parent plan wins; if a child must deviate, update the parent plan and every sibling plan in the same commit.

> **Partly superseded — read `## Amendments from re-verification (2026-09-07)`
> first (B1–B4).** In particular §D step 3's `env VAR=…` prefix is superseded by
> `respawn-pane -e` (B2): the prefix is now the documented **fallback** for a tmux
> build without `-e`, not the primary mechanism. Implement from the amendments;
> the text below is retained as the unedited parent contract.


#### A. Session store — `lib/agent_sessions.py` + `aitask_agent_sessions.sh`

- Path `~/.config/aitasks/agent_sessions.json`, env override
  `AITASKS_AGENT_SESSIONS_FILE`, lock dir derived from the resolved path
  (`<file>.lockd`), 0600 with `_target_mode` preservation, write via
  `lib/atomic_write.py`. Captures under `~/.config/aitasks/frozen/<id>/`
  (0700 dir; `capture.ansi`, `capture.txt`), env `AITASKS_FROZEN_DIR`.
- Schema v1:
  ```json
  {"version": 1, "sessions": [{
    "id": "7f3a2c1d",                 // record id (8 hex, os.urandom) — PRIMARY KEY
    "root": "/real/path/project",     // realpath, both sides         ┐ DURABLE IDENTITY
    "window": "agent-pick-1705",      //                               │ (root, window, window_slot)
    "window_slot": 0,                 // assigned once; >0 only for a 2nd agent in the same window ┘
    "pane_id": "%104", "pane_pid": 41233,   // LOCATION / GENERATION data — replaceable, never identity
    "session": "aitasks",             // tmux session name — display only
    "operation": "pick", "task_id": "1705",          // task_id "" when unbound
    "agent_string": "claudecode/opus5", "agent_kind": "claudecode",
    "codeagent_session_id": "", "transcript_path": "",  // "" = unknown → re-pick only
    "started_at": "2026-09-04T09:12:03Z",
    "state": "live",                  // live | freezing | frozen | restoring | aborting
    "state_at": "2026-09-04T09:12:03Z",
    "op_nonce": "", "op_owner_pid": 0, "op_started_at": "",   // LEASE of the in-flight freeze/restore (see below)
    "frozen_at": "", "capture_ansi": "", "capture_txt": "",
    "capture_lines": 0, "last_phase": "",
    "standin_pid": 0,                 // #{pane_pid} of the stand-in viewer, written at freeze-commit and every stand-in respawn
    "launch_pid": 0,                  // #{pane_pid} of the replacement agent, written by restore-launched (nonce-bound)
    "restore_attempts": 0, "restore_mode": "",   // "" | resume | repick (current attempt)
    "ack": "",                        // "" | hook | liveness — how the last restore was confirmed
    "last_error": ""                  // "" | "<nonce>:session_mismatch" | "<nonce>:<reason>" — coordinator-readable outcome channel
  }]}
  ```
  `pane_id` / `pane_pid` are **location and generation data**: a tmux server
  restart, a reattach or a respawn replaces them on the same record. They
  are never part of the identity key and a recycled `%N` can attach to
  nothing on its own — attachment needs either `@aitask_record` on the pane
  (options die with the pane, so a recycled pane never carries a stale one)
  or a `(root, window)` match under the conflict policy below.
  Unknown `state` = corruption (not a default). `load()` raises
  `MalformedSessionsError`; `load_safe()` returns empty. Generation normalised
  to `SCHEMA_VERSION` on read.
- **Record ownership (one allocator) and the `(root, window)` conflict
  policy.** The `upsert` verb is the *only* creator of records. Resolution
  order for a caller without `--restore-of`:
  1. `--id <rid>` (from `@aitask_record` on the caller's pane) → that record,
     whatever its `(root, window)` (a renamed window keeps its record).
  2. Else, **among `live` records only** with the caller's `(root, window)`,
     the relocation candidates are: the one whose `pane_id` equals the
     caller's pane, else those whose `pane_pid` is dead or whose pane no
     longer exists. **Exactly one candidate** → it is the same agent slot:
     replace `pane_id`/`pane_pid`, update session id / transcript / agent
     string, print `UPSERTED:<id>|updated` (the tmux-restart and reattach
     case — no second record). **More than one candidate** (two agents shared
     the window before a server restart; nothing on the caller's side can
     tell them apart) → **fail closed on relocation**: fall through to rule 3
     and print `UPSERTED:<id>|created_slot<N>|ambiguous_relocation`; the stale
     records are left for purge (rule: a `live` record whose `pane_pid` is
     dead and whose `pane_id` is absent from an enumerated window →
     `DROPPED:…|dead_pane`), never guessed.
     Transitional records (`freezing`/`restoring`/`aborting`) are **never**
     relocated or updated by an unstamped caller: they are touched only by
     `--restore-of` + the current nonce, or by `reconcile`. If the caller's
     pane *is* a transitional record's pane → refuse
     (`UPSERT_REFUSED:<id>|<state>_unacknowledged`, a stray session in a
     transacting pane); otherwise they are simply not candidates.
  3. Else every `(root, window)` record is `live` in **another** pane (a
     second agent split into the same window), transitional, or `frozen`
     (retained state whose window name is being reused, e.g. the same task
     re-picked after a tmux restart) → **create beside it**: new record,
     `window_slot` = lowest unused slot for that `(root, window)`, print
     `UPSERTED:<id>|created_slot<N>`. A retained frozen record never blocks a
     live launch and is never attached to; it stays restorable into a fresh
     window (`unique_window_name` disambiguates) and is listed distinctly by
     its `frozen_at`.
  4. Else → create (`state=live`, `window_slot=0`), print `UPSERTED:<id>|created`.
  In every create/update branch the caller's pane is stamped
  `@aitask_record=<id>`.
  Other branches:
  - record exists in `restoring` **and** the caller passes
    `--restore-of <id> --nonce <n>` (the hook forwards them from the
    replacement agent's environment, §D) → the **restore acknowledgement**:
    nonce must equal `op_nonce`; in `resume` mode `--session-id` must equal
    `codeagent_session_id` — else the store **persists**
    `last_error="<nonce>:session_mismatch"` (state unchanged) and prints
    `RESTORE_SESSION_MISMATCH:<id>` exit 7. The hook has no return channel to
    the detached coordinator, so the record *is* the channel: the coordinator
    and `reconcile` both read `last_error` for the current nonce and take the
    abort branch, never the liveness fallback. In `repick` mode the new
    session id is adopted. On success: `pane_id`/`pane_pid` updated from the
    caller's pane, `@aitask_record` stamped on it, state `live`, `ack=hook`,
    capture files deleted, print `UPSERTED:<id>|restored`;
  - record exists in `restoring` without `--restore-of`/`--nonce` → refuse,
    print `UPSERT_REFUSED:<id>|restoring_unacknowledged` (a stray session in
    a restoring pane is never an ack);
  - record exists in `freezing` / `frozen` → refuse, print
    `UPSERT_REFUSED:<id>|<state>` (a hook firing in a stand-in pane is a bug).
  Two callers: the SessionStart hook (child 3, normal path) and the freeze
  engine (child 4, fallback when the hook never fired). Both read
  `@aitask_record` off the pane first and pass `--id` when present, so a pane
  that was already recorded is never duplicated even after a `pane_id`
  recycle. A restore into a **new** pane (window gone) carries the record id
  in the environment, never on the pane, so it selects the old record instead
  of creating a second one.
- **Operation lease.** `freeze-begin`, `restore-begin` and `lease-take` mint
  `op_nonce` (8 hex), record `op_owner_pid` (the coordinator) and
  `op_started_at`, and print the nonce. **Every verb that mutates a record
  holding a lease** (`freeze-commit`, `freeze-abort`, `restore-launched`,
  `restore-confirm`, `restore-abort`, `standin-respawned`, the ack form of
  `upsert`) requires `--nonce <n>`; a mismatch prints `NONCE_MISMATCH:<id>`
  exit 6 and writes nothing — a coordinator that lost the race to
  `reconcile` fails closed instead of double-acting. `lease-take <id>` →
  `LEASED:<id>|<nonce>` is how `reconcile` (or a stand-in relaunch on a
  `frozen` record) acquires ownership: it is refused (`LEASE_HELD:<id>`)
  while a lease exists whose `op_started_at` is younger than
  `stale_op_grace` (default 60 s) **or** whose `op_owner_pid` is alive; a
  stale lease with a dead/unverifiable owner is taken over. Within the grace,
  or with a live owner, reconcile leaves the record alone. Lease-clearing
  transitions (`freeze-commit`, `freeze-abort`, `restore-confirm`, hook ack,
  `standin-respawned` out of `aborting`) clear the lease.
- **State machine** (every transition is one locked verb; illegal transitions
  print `TRANSITION_REFUSED:<id>|<from>|<verb>` exit 5 and write nothing):
  ```
  live ──freeze-begin──▶ freezing ──freeze-commit──▶ frozen ◀────────────────┐
   ▲                        │                          │                      │
   └────freeze-abort────────┘                          │ restore-begin        │ standin-respawned
   ▲                                                   ▼                      │ (same nonce)
   └──upsert (hook ack) / restore-confirm── restoring ──restore-abort──▶ aborting
  drop: any state → record removed + capture files removed
  ```
  `aborting` is **nonce-owned**: the record stays leased by the aborting
  attempt until its stand-in is back (`standin-respawned --nonce` → `frozen`,
  lease cleared). `restore-begin` on `aborting` → `TRANSITION_REFUSED`, so a
  user or a second controller cannot start another restore in the gap and
  an old coordinator cannot respawn over a newer attempt: its `standin-respawned`
  carries a stale nonce and is refused.
  **Captures are deleted only on a verified ack** (`ack=hook`). A
  liveness-only `restore-confirm` transitions to `live` but **keeps** the
  capture files (`ack=liveness`); they are removed on `drop` or liveness
  purge. This is what stops a malformed resume that starts a fresh session
  from destroying the only copy.
- Wrapper verbs (sole writer; `list`/`show` take no lock; exit 0/2/3
  `LOCK_BUSY`/4 `ERROR`/5 `TRANSITION_REFUSED`/6 `NONCE_MISMATCH`/7
  `RESTORE_SESSION_MISMATCH`/8 `LEASE_HELD`):
  `upsert --root <r> --window <w> --pane <id> --pane-pid <pid> [--id <rid>] [--session-id <sid>] [--transcript <p>] [--agent-string <s>] [--operation <op>] [--task-id <t>] [--restore-of <rid> --nonce <n>]`;
  `freeze-begin <id> --capture-ansi <p> --capture-txt <p> --lines <n> [--phase <t>]` → `FREEZING:<id>|<nonce>`;
  `freeze-commit <id> --nonce <n> --pane <pane_id|""> --pane-pid <pid|0>` → `FROZEN:<id>` (writes the stand-in's location: `pane_id`/`standin_pid` from the arguments; `--pane "" --pane-pid 0` is the gone-pane commit used by reconcile; `--pane` without `--pane-pid` or vice versa → usage error exit 2);
  `freeze-abort <id> --nonce <n>` → `LIVE:<id>` (captures deleted);
  `restore-begin <id> --mode resume|repick` → `RESTORING:<id>|<nonce>` (captures **retained**, `restore_attempts`+1, `launch_pid=0`, `last_error=""`);
  `restore-launched <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LAUNCHED:<id>` (records the replacement's `launch_pid` + location; written by the coordinator right after `respawn-pane`/`launch_in_tmux` returns — the nonce-bound evidence that the respawn happened);
  `restore-confirm <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LIVE:<id>|liveness` (captures **kept**; refused with `TRANSITION_REFUSED` unless `launch_pid != 0` and equals `--pane-pid`);
  `standin-respawned <id> --nonce <n> --pane <id> --pane-pid <pid>` → `STANDIN:<id>` (records the stand-in's `standin_pid` + location; from `aborting` it also transitions to `frozen` and clears the lease; from `frozen` (a `lease-take`n relaunch of a dead stand-in) it just updates and clears the lease; `freeze-commit` folds the same write in);
  `restore-abort <id> --nonce <n>` → `ABORTING:<id>` (captures retained; lease kept by the same nonce);
  `lease-take <id>` → `LEASED:<id>|<nonce>` / `LEASE_HELD:<id>` exit 8;
  `drop <id>` → `DROPPED:<id>`;
  `list [--state <s>] [--root <r>]` → `SESSION:<id>|<state>|<root>|<window>|<pane_id>|<task_id>|<agent_string>|<state_at>`;
  `show <id>` → `KEY:value` lines;
  `purge --observed <file>` → `DROPPED:<id>|<reason>` + `PURGED:<n>`.
  **Observation protocol (superset of the marks one, backward-compatible):**
  ```
  ROOT<TAB><root>                                   -- successfully enumerated root
  WINDOW<TAB><root><TAB><window>                    -- observed agent window
  PANE<TAB><root><TAB><window><TAB><pane_id><TAB><pane_pid><TAB><pane_dead>   -- every pane of that window
  INCOMPLETE                                        -- suppress every sweep
  ```
  `monitor_shared._write_observation_file()` gains a `panes=` argument and
  writes the `PANE` rows from `TmuxMonitor.last_discovered_panes()` (the
  `_LIST_PANES_FORMAT` already carries `pane_id` and `pane_pid`; `pane_dead`
  is appended to the format — see §B arity rule). The marks reader
  (`agent_marks._read_observed`) is extended to **skip** `PANE` rows so one
  file serves both purges; `agent_sessions` requires them. A file with
  `ROOT`/`WINDOW` but no `PANE` rows for an enumerated root is treated as
  pane-incomplete for that root: `dead_window` still applies, `dead_pane`
  does not (fail closed).
- **Purge policy** (fail-closed on `INCOMPLETE`, mirrors `sweep_liveness`):
  a `live` record whose `(root, window)` is absent from a successfully
  enumerated root → `DROPPED:…|dead_window`; a `live` record whose window has
  a `WINDOW` row **and** `PANE` rows, but whose `pane_id` appears in none of
  them (or appears with `pane_dead=1`) and whose `pane_pid` is dead
  (`os.kill(pid, 0)` → `ESRCH`; an `EPERM`/unverifiable pid is treated as
  alive) → `DROPPED:…|dead_pane` — this is what retires the stale candidates
  left behind by an ambiguous relocation. Two producers feed `purge`: the
  monitor maintenance tick (observation file above) and `aitask_frozen.sh
  reconcile`, which builds the same file from its own `list-panes` pass so
  retirement does not depend on a TUI being open. `freezing` / `frozen` / `restoring` /
  `aborting` records are never purged by liveness — they are reconciled by
  `aitask_frozen.sh reconcile` (§C/§D). A frozen record whose capture file is
  missing → `DROPPED:…|capture_missing`.
- `SessionsView` (mtime+size+inode gated) for the TUIs; `invalidate()` after
  every write. `standin_command(record_id) -> str` returns
  `ait frozenagent --record <id>` unless `AITASKS_FROZEN_STANDIN_CMD` is set
  (documented **test seam**; production never sets it).

#### B. Pane options (tmux user options, pane-scoped)

| Option | Set by | Cleared by | Read by | Meaning |
|---|---|---|---|---|
| `@aitask_record=<id>` | `upsert` (hook or freeze engine) | `drop`; pane death | freeze engine, restore coordinator, hook (`--id`) | the pane-visible join to its store record |
| `@aitask_frozen=<id>` | freeze engine, immediately before `respawn-pane` | `restore-confirm` path (coordinator), `drop` | `_LIST_PANES_FORMAT` (appended), `kill_agent_pane_smart` format, `aitask_companion_cleanup.sh`, `maybe_spawn_minimonitor` occupancy | this pane is a frozen stand-in — **authoritative** classifier |
| `@aitask_standin_ready=<id>` | **the viewer itself**, after mount (only the app stamps its own pane — `mark_monitor_pane` rule) | freeze engine + restore coordinator (`set-option -pu`) immediately **before** every `respawn-pane`; `drop` | `reconcile` | positive proof that the stand-in is up — the only signal that distinguishes "stamped, viewer running" from "stamped, agent still running" |
| `@aitask_agent_session=<sid>` | SessionStart hook on `$TMUX_PANE` | pane death | freeze engine fallback when the store has no session id | codeagent session id |

**Pane user options survive `respawn-pane`** (they are pane-scoped, not
process-scoped), which is why `@aitask_standin_ready` must be explicitly unset
before each respawn and why `@aitask_record` stays valid across freeze/restore
on the same pane. `#{pane_current_command}` is a process basename and is
**never** used as identity; `#{pane_pid}` (stored as `pane_pid`) and the
options above are the only server-observable identities reconcile reads.

Constants live in `monitor/monitor_core.py` beside `SHADOW_TARGET_OPTION`
(`RECORD_OPTION`, `FROZEN_OPTION`, `STANDIN_READY_OPTION`,
`AGENT_SESSION_OPTION`) and are mirrored in `lib/agent_sessions.sh` for shell
callers.

#### C. Freeze — `lib/agent_freeze.py` + `aitask_frozen.sh freeze <pane>|--all`

Runs **out of the agent pane** (from a TUI, a shell, or `run-shell -b`).
Every step is persisted before the next irreversible one:

1. Resolve the record: `@aitask_record` → `show`; else `upsert` (fallback).
   Read `codeagent_session_id`; if empty, try `@aitask_agent_session`.
2. `capture-pane -p -e -J -t <pane> -S -<cap>` via `TmuxClient.run` →
   `capture.ansi`; strip via `monitor/ansi_utils` → `capture.txt`.
3. `freeze-begin` → state `freezing`, capture paths persisted, **lease
   minted** (`op_nonce`, `op_owner_pid`=this coordinator).
4. `set-option -p -t <pane> @aitask_frozen <id>`; `set-option -pu -t <pane>
   @aitask_standin_ready` (clear any stale ready mark from a previous cycle).
5. `respawn-pane -k -t <pane> '<standin_command(id)>'` via the gateway.
   Window name unchanged, so `classify_pane` / `task_id_from_window_name`
   keep working. The viewer stamps `@aitask_standin_ready=<id>` on mount.
6. `freeze-commit --nonce <n> --pane <pane> --pane-pid <stand-in pid>` →
   state `frozen`, `standin_pid` + location recorded (read via
   `display-message -p -t <pane> '#{pane_id}\t#{pane_pid}'` after the
   respawn), lease cleared.

Failure at 1–3 → nothing to undo beyond temp files (`FREEZE_FAILED:<stage>`).
Failure at 4 → `freeze-abort --nonce`. Failure at 5 (tmux refused) → unstamp +
`freeze-abort --nonce`; the agent is still running. Failure at 6 (store busy)
→ the record stays `freezing`; **reconcile** completes it once the lease is
stale. A `NONCE_MISMATCH` at 6 means reconcile already resolved the record;
the coordinator reports it and exits without touching the pane.

**`aitask_frozen.sh reconcile`** (idempotent; run by the coordinator after
every freeze/restore, by the monitor maintenance tick beside
`_maybe_purge_marks`, and manually) resolves every non-`live` record **whose
lease is stale** (`op_started_at` + `stale_op_grace` elapsed **and**
`op_owner_pid` dead/unverifiable — otherwise the record is skipped as
in-flight) from server-observable facts only
(`list-panes -F '#{pane_id}\t#{pane_pid}\t#{pane_dead}\t#{@aitask_frozen}\t#{@aitask_standin_ready}\t#{@aitask_record}'`;
"agent alive" = `pane_pid == record.pane_pid`; "viewer here" =
`pane_pid == record.standin_pid`; "replacement here" =
`pane_pid == record.launch_pid`; "stand-in up" = `@aitask_standin_ready == id`;
"mismatch" = `last_error` begins with the current `op_nonce`):

| record state | pane observation | action |
|---|---|---|
| `freezing` | `@aitask_frozen==id` **and** stand-in up | `freeze-commit --pane <pane> --pane-pid <observed pid>` |
| `freezing` | agent alive, stand-in not up | unstamp both options, `freeze-abort` (captures deleted) |
| `freezing` | `@aitask_frozen==id`, stand-in not up, neither agent nor viewer pid, pane not dead | **indeterminate — no transition** (viewer may still be booting); re-checked next pass |
| `freezing` | `@aitask_frozen==id`, pane dead | respawn the stand-in (clear ready first), `standin-respawned`, then re-check |
| `freezing` | pane gone | `freeze-commit --pane "" --pane-pid 0` |
| `frozen` | pane gone | keep (restorable into a new window) |
| `frozen` | `@aitask_frozen==id`, pane dead | `lease-take`, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | mismatch recorded for this nonce | `restore-abort` (→ `aborting`), kill the wrong agent via `respawn-pane -k` back to the stand-in, `standin-respawned --nonce` (→ `frozen`) — **never** liveness-confirm |
| `restoring` | viewer here (`pane_pid==standin_pid`) — the coordinator died before or during the respawn, whether or not the ready mark survived | `restore-abort`; respawn the stand-in so it re-stamps ready; `standin-respawned --nonce` |
| `restoring` | `launch_pid==0` and pane pid is neither the viewer's nor the agent's | **indeterminate — no transition** (respawn may be mid-flight); after `stale_op_grace` ×2 → `restore-abort` + respawn stand-in + `standin-respawned --nonce` |
| `restoring` | replacement here (`pane_pid==launch_pid`), pane not dead, no mismatch, `state_at` + `restore_ack_grace` (default 20 s) elapsed | `restore-confirm --pane --pane-pid` (`ack=liveness`, captures kept) |
| `restoring` | pane dead | `restore-abort`, clear ready, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | pane gone | `restore-abort` with `pane_id=""`, then `standin-respawned --nonce --pane "" --pane-pid 0` (→ `frozen`, restorable into a new window) |
| `aborting` (stale lease taken over) | stand-in up (`@aitask_standin_ready==id`) | `standin-respawned --nonce` (→ `frozen`) |
| `aborting` (stale lease taken over) | anything else | clear ready, respawn the stand-in, `standin-respawned --nonce` (→ `frozen`) |

Every reconcile action on a leased record is preceded by `lease-take`; a
`LEASE_HELD` answer means a live coordinator owns it and reconcile skips.

A liveness confirm therefore requires **positive evidence** that the
process in the pane is the one the coordinator launched (`launch_pid`), and
a viewer whose ready mark was cleared is still recognised by `standin_pid`.

Failure injection: `AITASKS_FREEZE_FAIL_AT=capture|begin|stamp|respawn|commit`,
`AITASKS_RESTORE_FAIL_AT=begin|respawn|ack`, and `AITASKS_FROZEN_PAUSE_AT=<stage>`
(the coordinator `SIGSTOP`s itself so a test can run a concurrent
`reconcile` and then `SIGCONT`) — documented test seams, honoured only under
`AITASKS_TEST_MODE=1`.

**Cleanup contract** (`aitask_companion_cleanup.sh` + `count_other_real_agents`
must agree — pinned by the parity test):
- a `@aitask_frozen`-stamped pane **counts as a real agent sibling** (the
  window exists to hold it; killing agent B must not destroy frozen A's viewer);
- when the *dying* pane is the stamped one, the cleanup script **abstains
  entirely** (it is being respawned, not departing);
- `kill_agent_pane_smart` on a frozen pane = `drop` + kill by the same rule.

#### D. Restore — `lib/agent_restore.py` + `aitask_frozen.sh restore <id> [--repick] | --all`

**Never runs inside the pane it replaces.** The viewer's `R`/`p` keys and the
minimonitor keys invoke `run-shell -b "<repo>/.aitask-scripts/aitask_frozen.sh restore <id>"`
through the gateway; the coordinator is a detached process that outlives the
respawn. Two-phase, acknowledged:

1. Build the argv: `aitask_codeagent.sh --agent-string <s> --resume-session <sid> --dry-run invoke raw`
   (resume) or the existing pick launch argv (`--repick`, task id required).
   Empty session id and no `--repick` → `RESTORE_FAILED:no_session` (nothing changes).
2. `restore-begin --mode <m>` → state `restoring`, lease minted (nonce `n`);
   captures and `@aitask_frozen` retained.
3. Prefix the argv with the **restore identity environment** (the
   `explore-relay` `env` precedent — `env` execs into the agent, so the pane
   pid is still the agent's):
   `env AITASK_RESTORE_RECORD=<id> AITASK_RESTORE_NONCE=<n> AITASK_RESTORE_MODE=<m> AITASK_RESTORE_EXPECT_SESSION=<sid> <argv>`.
   Then `set-option -pu @aitask_standin_ready` and
   `respawn-pane -k -t <stand-in> '<env argv>'` — or, when `pane_id=""`,
   `launch_in_tmux` into a new window with the recorded name. Immediately
   after tmux returns, read the new `#{pane_pid}` and write
   `restore-launched --nonce --pane --pane-pid` — the nonce-bound evidence
   that a replacement was actually started. The replacement agent's
   SessionStart hook forwards the four variables as `upsert --restore-of
   --nonce --session-id` (§A ack rules), which is what selects the **old**
   record from a brand-new pane, verifies the resumed session id, and stamps
   `@aitask_record` there.
4. Wait for the ack: poll `show <id>` until `state=live`, `last_error`
   carries this nonce, **or** `restore_ack_grace` elapses.
   - `live` with `ack=hook` → clear `@aitask_frozen`, print `RESTORED:<id>|hook`
     (captures already deleted by the ack).
   - `last_error="<nonce>:session_mismatch"` (the hook reported a different
     session in `resume` mode; persisted by the store because the hook has
     no channel to this process) → `restore-abort --nonce` (→ `aborting`,
     still owned by this nonce), `set-option -pu @aitask_standin_ready`,
     `respawn-pane -k` back to the stand-in, then `standin-respawned --nonce
     --pane --pane-pid` (→ `frozen`), print `RESTORE_FAILED:<id>|session_mismatch`;
     **capture intact**. The same abort → respawn → `standin-respawned --nonce`
     sequence is used by every failure branch below; a `NONCE_MISMATCH` at
     any step means reconcile already finished the abort.
   - grace elapsed, pane alive, `pane_pid == launch_pid`, no hook ack and no
     error → `restore-confirm --nonce --pane --pane-pid` → `live` with
     `ack=liveness`, **captures kept**, clear the stamp, print
     `RESTORED:<id>|liveness` (the viewer/minimonitor show "restored,
     unverified — capture kept").
   - pane dead at any poll (invalid session, binary missing, immediate exit)
     → `restore-abort --nonce`, clear ready, respawn the stand-in,
     `standin-respawned --nonce`, print `RESTORE_FAILED:<id>|agent_exited` —
     **the capture is intact and the viewer is back**.
   - `NONCE_MISMATCH` on any verb → reconcile already settled it; exit
     without touching the pane.
5. Coordinator crash between 2 and 4 → `reconcile` (§C table) settles it
   once the lease is stale.

`aitask_codeagent.sh` gains a global `--resume-session <sid>` (template
`OPT_HEADLESS`): `claude --model <id> --resume <sid>`, `codex resume <sid>`
(model flag per codex CLI), opencode → `RESUME_UNSUPPORTED:opencode` exit 2.
Resolution stays single-sourced in `lib/agent_string.sh`. Restore-All iterates
`frozen` records; per-record failures are reported, never abort the batch.


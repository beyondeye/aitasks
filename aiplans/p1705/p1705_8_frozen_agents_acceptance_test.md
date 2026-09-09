---
Task: t1705_8_frozen_agents_acceptance_test.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_1_*.md … aitasks/t1705/t1705_7_*.md, aitasks/t1705/t1705_9_*.md, aitasks/t1705/t1705_10_*.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-09 19:30
---

# t1705_8 — Frozen agents acceptance test (composed, shipped wrappers only)

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

## Context

End-to-end proof that children 2–7 agree on the joins (hook → store →
freeze → viewer → restore → cleanup), on an isolated tmux server, through
the shipped wrappers only, with a fake agent binary so it runs unattended.
The parent's mitigation for cross-child drift. Real agents are the
manual-verification sibling's job. **Tmux-stress** — run outside the `-L ait`
server.

## Amendments from re-verification (2026-09-09) — READ FIRST

This plan was written 2026-09-08. t1705_7 landed on 2026-09-09 and the
re-verification below checked every environment knob and CLI contract the plan
depends on against the shipped tree. **Eleven assumptions were wrong.** Each is
recorded with the evidence, because nine of them are not cosmetic — they make
planned assertions unreachable or blow the timing budget.

**V1 — `stale_op_grace` is env-only; the `project_config.yaml` setting is a
no-op.** `agent_sessions._stale_op_grace()`
(`.aitask-scripts/lib/agent_sessions.py:604`) reads **only**
`AITASKS_STALE_OP_GRACE`, and only under `AITASKS_TEST_MODE=1`. It never opens
`project_config.yaml`. The old step 1 set `stale_op_grace: 2` in the scratch
project's `frozen:` block, which leaves the real value at
`STALE_OP_GRACE_DEFAULT` (60 s). Cases 7 and 8 each wait past it, so that
setting alone contributes ~120 s of pure sleeping and breaks the `< 3 min`
budget the plan asserts. **Use the env seam.** (`restore_ack_grace` and
`capture_max_lines` *do* read the project config — only this one does not,
which is exactly why it was easy to get wrong.)

**V2 — Case 10 asserted something its chosen CLI cannot do.**
`lib/agent_sessions.py` opens with "THIS MODULE NEVER TOUCHES TMUX. It imports
no tmux and spawns no process." So `aitask_agent_sessions.sh drop <id>` removes
the record and capture files and **leaves the stand-in pane running with all
three stamps intact**. The pane-option half of case 10 is unreachable through
it. The verb that retires the pane is `aitask_frozen.sh drop <id>` →
`agent_freeze.drop_record()` (`:946`), and even there the options are never
unset: the docstring is explicit — *"Pane options are pane-scoped and die with
the pane, so this retires all three stamps with no unstamp step to fail."*
Case 10 must therefore split in two and assert the mechanism, not a
coincidence (see the rewritten case list).

**V3 — the old step-1 recipe runs `ait setup`, which builds venvs into the
developer's real `$HOME`.** `aitask_setup.sh` creates `$HOME/.aitask/venv` and
pip-installs into it (`:8`, and the two pip-install sites). The old plan
deliberately left `HOME` unredirected "(setup writes there)" — so the test
would mutate the real venv and cost minutes it does not have. `install.sh`
does **not** build a venv; it only stores the hook *seed* at
`aitasks/metadata/claude_settings.hooks.json` (`install.sh:814`). The shipped
code path that actually writes `.claude/settings.json` is
`setup_claude_hooks()` (`aitask_setup.sh:2622`), reachable via the sanctioned
`--source-only` seam (`aitask_setup.sh:4488`) — which is exactly how t1705_3's
own `tests/test_session_hook_install.sh:112` drives it. Use that: it is *more*
faithful to "shipped wrappers" than a full `ait setup`, and it is free.

**V4 — `fake_agent.sh` does not produce the output case 2 measures.** The
fixture prints at most two status lines (`tests/lib/fake_agent.sh:48,81`), not
"50 numbered lines with ANSI colour". Case 2's `line count = fake output`
assertion has no source today. The task file already licenses the fix ("edit
`tests/lib/fake_agent.sh` if a knob is missing") — add one, **default-off**
(see M1).

**V5 — the isolation helpers were listed in the wrong order.**
`tests/lib/tmux_isolation.sh:115` states "ORDERING IS LOAD-BEARING: call this
BEFORE `require_isolated_tmux`", and both existing live suites obey it
(`test_restore_flows_live.sh:64-65`, with the comment `# FIRST` / `# SECOND`).
The old step 1 listed them reversed.

**V6 — `AITASKS_FROZEN_PAUSE_AT=respawn` is ambiguous.** The stage name
`respawn` is used by **both** `agent_freeze.py:392` and
`agent_restore.py:407`. Case 8 freezes and *then* restores, so exporting the
variable process-wide would `SIGSTOP` the freeze at its own respawn stage
before the restore is ever reached. It must be set on the restore invocation
only, never exported. (`aborting` is unambiguous — `agent_restore.py:238`.)

**V7 — a symlink to a shell script is not named `claude`.** t1729 added
`tests/lib/fake_agent_binary.py` precisely because "a script's `comm` is its
interpreter's, so a `sh` wrapper named `codex` reports `sh`". The old step 1
proposed `bin/claude` → symlink to `fake_agent.sh`. That is fine **only**
because nothing on the freeze path keys on `#{pane_current_command}` — §B pins
that it "is a process basename and is **never** used as identity". **V8
supersedes the symlink anyway** — `bin/claude` becomes a control-file wrapper —
and the same caveat carries over to it: if any assertion ever needs the pane's
command to *read* as `claude`, use `fake_agent_binary.py`, not a rename or a
wrapper filename.

**V8 — per-case agent behaviour cannot be delivered by the test shell's
environment.** This is the sharpest consequence of constraint (a) below, and
the old plan missed it. `respawn-pane` runs its command in the **tmux server's**
environment, captured at server start, so a per-case
`FAKE_AGENT_EXIT=1 ./aitask_frozen.sh restore …` in the test shell **never
reaches the replacement agent**. Cases 3 (`FAKE_AGENT_EXIT=1`), 4
(`FAKE_AGENT_SESSION=other`) and 5 (happy resume) all need to change the
replacement's behaviour *after* the server is running, so with the old plan's
plain `bin/claude` → `fake_agent.sh` symlink they are untestable as specified.
`test_restore_flows_live.sh:101-112` already solved this: `bin/claude` is a
generated **wrapper** that sources a per-case control file before `exec`ing the
fixture (`exec` keeps the pid, so `#{pane_pid}` still names the agent — t1465).
Adopt that mechanism; the symlink is not sufficient.

**V9 — the coordinator's environment depends on how it was dispatched.** Two
different answers, and cases 4, 7 and 8 straddle them:

- a coordinator the test invokes **directly**
  (`AITASKS_FROZEN_PAUSE_AT=aborting "$FROZEN_SH" restore <id>`) is a child of
  the test shell and inherits its environment — this is what cases 7/8 use, and
  it works;
- a coordinator dispatched through **`run-shell -b`** (the viewer's `R` key,
  the minimonitor keys — case 4's "real detached coordinator") runs in the
  **server's** environment, so its seams must be exported before server start
  or delivered by a control file, exactly as V8 requires for the agent.

State this at every seam-setting site; it is the difference between a case that
measures the shipped path and one that measures the test shell.

**V10 — a sourced control file must carry `export`, or the knobs never reach
the fixture.** The wrapper of V8 sources `$AGENT_ENV_FILE` and then `exec`s
`fake_agent.sh` — a *separate program* that reads `${FAKE_AGENT_EXIT:-0}` and
friends from its **environment**. A bare `NAME=value` line becomes a shell
variable of the wrapper, and `exec` does not pass those on, so every
"controlled" case would silently take the happy path. This failure is quiet
where it matters least and loud where it matters most: cases 3 and 4 assert a
`RESTORE_FAILED:` line and would fail visibly, but the ack-grace probe's
`FAKE_AGENT_NO_HOOK=1` would simply let the hook ack arrive and the probe would
measure the wrong path. The shipped suite already solved it —
`test_restore_flows_live.sh:185` writes `printf 'export %s\n'`. Reuse that
helper verbatim; do not hand-write the file. As belt-and-braces, one case
should assert the knob actually arrived via `fake_agent.sh --report-env`,
which self-reports its environment for exactly this reason.

**V11 — the scratch `frozen:` config was never written, and setting a knob
both ways proves nothing.** Two compounding gaps. First, the recipe asserted
that `capture_max_lines` "stays in" the scratch `project_config.yaml`, but
nothing ever wrote a `frozen:` block: `install.sh:567-575` seeds the file from
`seed/project_config.yaml`, which has no such block, so every config-read path
silently took its default. Second — and worse — `restore_ack_grace` was set in
*both* the environment and the config with the same value, described as
"exercising the config path". It does the opposite: under `test_mode()` a
positive `AITASKS_RESTORE_ACK_GRACE` returns at
`agent_frozen_ops.py:144-151`, **before the config is opened**, so a missing or
malformed `frozen:` block behaves exactly like a correct one. A knob set two
ways at the same value is not covered twice; it is covered once and untested at
the lower-precedence layer. Fixed by writing the block explicitly with
three-way-distinct values, and by probes C1/C2 that run with the higher-
precedence layer removed so the configured value is the only thing that can
explain the result.

**Also noted (not defects):** the store has shipped a `lease-release` verb
(`aitask_agent_sessions.sh:315`) that §A's pinned verb list predates; and
`drop` now has three additional result lines — `DROP_REFUSED:<id>|in_flight`,
`DROP_FAILED:<id>|<stage>`, `DROP_ABORTED:<id>|raced`. Assert the shipped
surface, not §A's list, where they differ.

**Still true, re-confirmed:** capture files are `0o600`
(`agent_freeze.py:213,220`); `AITASKS_FROZEN_STANDIN_CMD` is a real seam and
leaving it unset is what makes this suite distinct from t1705_5's
(`test_restore_flows_live.sh:83` *sets* it to `fake_standin.sh`; we must not);
`freeze --all --dry-run` prints `WOULD_FREEZE:…` then
`FREEZE_ELIGIBLE:<n>` (`agent_freeze.py:1188-1190`); `restore_verdict` /
`drop_verdict` / `restore_settle_timeout` all exist as t1705_7's note claimed.

## Composed environment (corrected recipe)

Replaces the old step 1. Two constraints dominate and both are load-bearing:

**(a) Every env seam must be exported BEFORE the isolated server starts.**
`respawn-pane` and `run-shell -b` run their commands in the **tmux server's**
environment, captured at server start — not the calling shell's at call time.
`test_restore_flows_live.sh:95-97` records this in so many words. Since the
restore coordinator is a detached `run-shell -b` job, `AITASKS_TEST_MODE`,
`AITASKS_STALE_OP_GRACE` and `AITASKS_RESTORE_ACK_GRACE` reach it **only** via
the server environment.

**(b) The scratch project supplies the hook; the real `$HOME` is never
written.**

```bash
. tests/lib/asserts.sh;  assert_counters_init          # subshell-safe (t1207)
. tests/lib/tmux_isolation.sh
require_clean_ait_server        # FIRST  (V5)
require_isolated_tmux           # SECOND

SCRATCH="$(mktemp -d)"
bash install.sh --dir "$SCRATCH"                       # tree + hook seed; no venv (V3)

# --- the setup entry point, at two levels (see "Setup coverage" below) -------
"$SCRATCH/ait" setup --help >/dev/null                 # real CLI dispatch, zero side effects
( . "$SCRATCH/.aitask-scripts/aitask_setup.sh" --source-only
  setup_claude_hooks </dev/null )                      # the REAL hook installer (V3)

export AITASKS_AGENT_SESSIONS_FILE="$SCRATCH/.sessions.json"
export AITASKS_FROZEN_DIR="$SCRATCH/.frozen"
export AITASKS_TEST_MODE=1
export AITASKS_STALE_OP_GRACE=2                        # env-only (V1)
export AITASKS_RESTORE_ACK_GRACE=5          # config says 8, default 20 (V11)
export AITASKS_FAKE_AGENT_HOOK="$SCRATCH/.aitask-scripts/aitask_session_hook.sh"
unset AITASKS_FROZEN_STANDIN_CMD                       # the REAL viewer must boot
export TMUX_TMPDIR="$SCRATCH/tmux"

# --- per-case control wrapper, NOT a symlink (V8) ----------------------------
AGENT_ENV_FILE="$SCRATCH/agent_env"                    # rewritten per case
mkdir -p "$SCRATCH/bin"
for n in claude codex; do
  cat > "$SCRATCH/bin/$n" <<WRAPPER
#!/usr/bin/env bash
# Sources a per-case control file before exec'ing the fixture: respawn-pane runs
# in the SERVER's environment (captured at server start), so per-case knobs set
# in the test shell never reach the replacement agent (V8). \`exec\` keeps the
# pid, so \`#{pane_pid}\` still names the agent (t1465).
[ -f "$AGENT_ENV_FILE" ] && . "$AGENT_ENV_FILE"
exec "$PROJECT_DIR/tests/lib/fake_agent.sh" "\$@"
WRAPPER
  chmod +x "$SCRATCH/bin/$n"
done
export PATH="$SCRATCH/bin:$PATH"
: > "$AGENT_ENV_FILE"                                  # default: plain happy agent
# ...only now start the isolated server (a)
```

Per case, set the knobs through the two helpers the existing suite already
ships (`test_restore_flows_live.sh:185-186`), and truncate in teardown so a
leaked knob cannot silently alter a later case:

```bash
agent_env()       { printf 'export %s\n' "$@" > "$AGENT_ENV_FILE"; }
agent_env_clear() { : > "$AGENT_ENV_FILE"; }

agent_env FAKE_AGENT_EXIT=1          # case 3
agent_env FAKE_AGENT_SESSION=other   # case 4
agent_env FAKE_AGENT_NO_HOOK=1       # ack-grace probe
```

**The `export` is load-bearing, not style (V10).** The wrapper *sources* this
file and then `exec`s `fake_agent.sh`, which is a separate program reading its
**environment**. A bare `FAKE_AGENT_EXIT=1` line creates a shell variable that
`exec` does not pass on, so the fixture would evaluate `${FAKE_AGENT_EXIT:-0}`
as unset and take the happy path. Use `agent_env`; never hand-write the file.
(The equivalent fix, if a future wrapper prefers it, is `set -a` around the
source — but match the shipped helper rather than inventing a second form.)

### The scratch `frozen:` config — written explicitly, and made observable

`install.sh:567-575` seeds `aitasks/metadata/project_config.yaml` from
`seed/project_config.yaml`, so the file exists — but with **no `frozen:`
block**. It must be written explicitly, or every config-read path silently
takes its default and a malformed block is indistinguishable from a correct
one (V11):

```bash
cat >> "$SCRATCH/aitasks/metadata/project_config.yaml" <<'YAML'
frozen:
  capture_max_lines: 120     # env-free knob — the config-read proof (probe C1)
  restore_ack_grace: 8       # distinct from env 5 AND default 20 (probe C2)
  # stale_op_grace is NOT settable here: env-only under AITASKS_TEST_MODE (V1).
YAML
```

The values are deliberately **three-way distinct** so each probe can attribute
the result to the config rather than to a coincidence: `restore_ack_grace` is
`8` in the config, `5` in the environment, `20` by default.

### Setup coverage — why three levels, not one

Sourcing `setup_claude_hooks` exercises the real hook-writing function but
bypasses the shipped `ait setup` entry point, so on its own a broken CLI
dispatch could pass this suite while users cannot install the hook. A full
`ait setup` is not an option inside the timed run: `setup_python_venv` runs at
`aitask_setup.sh:4421`, **before** `setup_code_agents` → `setup_claude_hooks`
at `:4451`, so reaching the hook requires building a venv first — minutes of
pip, and a hard failure on an offline box. Three levels, chosen accordingly:

1. **`"$SCRATCH/ait" setup --help`** (always, free). `ait:229` is
   `setup) shift; exec "$SCRIPTS_DIR/aitask_setup.sh" "$@"`, and `--help` is
   handled at `aitask_setup.sh:4338` with the comment *"Must exit before any
   setup step runs"*. So this proves routing, `exec`, and argv forwarding
   end-to-end with zero side effects — precisely the "broken CLI dispatch"
   failure mode, and it costs nothing.
2. **`setup_claude_hooks` via `--source-only`** (always) — the real hook
   installer, as above.
3. **`AIT_ACCEPTANCE_FULL_SETUP=1`** (opt-in, **outside** the timed region):
   run `HOME="$SCRATCH/home" "$SCRATCH/ait" setup </dev/null` and assert
   `$SCRATCH/.claude/settings.json` holds exactly one aitasks SessionStart
   group. `VENV_DIR="$HOME/.aitask/venv"` (`aitask_setup.sh:8`) is
   `$HOME`-derived, so the redirect keeps the real `$HOME` untouched — the
   guarantee the task depends on. This is the genuine end-to-end backstop; it
   is opt-in only because of the venv cost, and a CI box should set it.

## Implementation steps

### Pre-phase (risk mitigations)

Both run to green **before any acceptance case is written**. They are inline
phases of this task, not spawned tasks.

- **`fixtures_extraction_control`** — `test_freeze_engine_live.sh` and
  `test_restore_flows_live.sh` duplicate **13** helpers (measured:
  `cleanup`, `make_agent_window`, `pane_exists`, `pane_fmt`, `record_field`,
  `record_of_pane`, `section`, `store`, `tm`, `wait_for_ready`,
  `wait_for_record_state`, `wait_stopped`, `window_exists`), so the extraction
  the old plan made conditional is warranted. Carry `agent_env` /
  `agent_env_clear` (`test_restore_flows_live.sh:185-186`) into the shared lib
  too: they live only in the restore suite today, and V10 shows that
  re-implementing them by hand is a silent-failure trap. Do it as a **pure,
  behaviour-preserving refactor**, on its own, first: run both suites to green,
  extract `tests/lib/frozen_fixtures.sh`, re-point both to source it, run both
  to green again. Any `fake_agent.sh` knob added for V4 is **default-off** and
  both suites are re-run after it. Rationale: both suites currently pass and
  can only be verified in this same rare environment — a regression introduced
  here and discovered later is very expensive to attribute.
- **`env_seam_probe`** — before writing cases 3–11, prove each seam *actually
  takes effect*. A timing assertion alone is not enough: a normal hook ack
  finishes well inside either grace, so it would pass without the override ever
  being seen. Each probe therefore needs a **controlled stimulus that forbids
  the fast path**, a **terminal verdict**, and a **bound that excludes the
  default**. Configured values 5 s / 2 s vs. defaults
  `RESTORE_ACK_GRACE = 20.0` (`agent_frozen_ops.py:117`) and
  `STALE_OP_GRACE_DEFAULT = 60.0` (`agent_sessions.py:73`) give wide margins:

  - **Ack grace.** Stimulus: `FAKE_AGENT_NO_HOOK=1` in `$AGENT_ENV_FILE`, so no
    hook ack can ever arrive and the coordinator is forced onto the liveness
    path. Verdict: `RESTORED:<id>|liveness`, record `ack=liveness`, **captures
    kept** (the ack-less contract). Bound: `5 <= elapsed < 15` — unreachable
    under the 20 s default, so the assertion fails loudly if the seam is
    ignored, instead of merely running slow.
  - **Stale-op grace.** Stimulus: strand a lease with a dead owner — start a
    restore under `AITASKS_FROZEN_PAUSE_AT=aborting`, `SIGKILL` the
    coordinator. Verdict: `reconcile` settles the record to `frozen` with the
    stand-in back. Bound: settles within `< 15 s`. Under the 60 s default
    reconcile skips the record as in-flight and it stays unsettled, so this
    positively discriminates rather than merely timing a fast path.
  - **Coordinator visibility (V9).** Run the ack-grace probe once through the
    **`run-shell -b`** path (the viewer's `R` key via `send-keys`), not only as
    a direct subprocess, since that is the only dispatch whose environment
    comes from the server rather than the test shell. This is what actually
    proves the override reaches the shipped coordinator.
  - **C1 — config read, env-free (`capture_max_lines`).** This is the one
    `frozen:` knob with **no environment override at all**
    (`agent_freeze.py:157`), so it proves, on its own, both that the scratch
    config was found and that `_walk_up_to_project` (`:228`) resolved the root
    to `$SCRATCH`. Stimulus: the new V4 output knob emits **300** lines.
    Verdict: `capture.txt` is exactly **120** lines. Under a missing, malformed
    or unfound config the default is `DEFAULT_CAPTURE_MAX_LINES = 50000`
    (`:118`) and all 300 survive — so the two outcomes are unmistakable.
  - **C2 — the configured `restore_ack_grace` is observably responsible.**
    Under `test_mode()`, a positive `AITASKS_RESTORE_ACK_GRACE` returns
    **before the config is ever opened** (`agent_frozen_ops.py:144-151`), so
    the normal cases never exercise the config path for this setting. Run one
    probe with the override **absent** — `env -u AITASKS_RESTORE_ACK_GRACE
    "$FROZEN_SH" restore <id>`, invoked **directly** so it inherits the test
    shell rather than the server (V9), which is what makes `env -u` effective
    at all. Stimulus: `FAKE_AGENT_NO_HOOK=1` as above. Bound:
    `7 <= elapsed < 15`, which implicates the configured `8` and excludes both
    the env `5` and the default `20`.

  V1 is exactly this class of defect, and it does not fail loudly on its own:
  a missed seam silently restores the default, and only the end-of-run budget
  assertion would notice, after the fact.

- **`setup_entrypoint_coverage`** — implement the three-level "Setup coverage"
  design above before the cases: level 1 (`ait setup --help`) and level 2
  (`setup_claude_hooks`) run always, level 3 (`AIT_ACCEPTANCE_FULL_SETUP=1`,
  `HOME`-redirected, untimed) is opt-in. Without level 1 this suite can go
  green while `ait setup` is broken for every user; without the `HOME`
  redirect, level 3 would write the developer's real venv.

### Main steps

1. **Environment.** As "Composed environment" above.
2. **Launch helper.** `launch_agent <window>`: `python3 -c` using the scratch
   tree's `agent_launch_utils.launch_in_tmux`
   (`.aitask-scripts/lib/agent_launch_utils.py:1369`) with the argv from
   `$SCRATCH/.aitask-scripts/aitask_codeagent.sh --agent-string
   claudecode/opus5 --dry-run invoke raw`, so the wrapper, the
   `AITASK_AGENT_STRING` export path and the fake binary are all real. Then
   `attach_companion_cleanup_hook` and a stub companion pane stamped
   `@aitask_monitor_kind`. (`--resume-session` requires `invoke raw` —
   `aitask_codeagent.sh:630` — which the restore path already satisfies.)
3. **Cases 1–9 and 10a/10b** as enumerated in the task file, each a `( … )`
   subshell, with these corrections:
   - ground truth from tmux (`display-message` / `list-panes` through
     `ait_tmux`) and the filesystem, never the store alone;
   - **case 2** asserts capture mode `0600` and the line count. Note this is
     now the **capped** count, not the emitted one: with the V4 knob emitting
     300 lines and `capture_max_lines: 120`, `capture.txt` is 120 lines. That
     is the same measurement probe C1 makes, so keep the two consistent — if
     the cap is ever changed, both move together;
   - **case 4** uses a logging `tmux` shim in front of the real one only to
     prove the coordinator ran detached, driven with `send-keys R` into the
     stand-in pane — the one place the viewer's key path is exercised live.
     Note the viewer still carries the hardcoded 40 s deadline
     (`frozenagent_app.py:877`, filed as **t1766**); with `restore_ack_grace=5`
     that is not reached, so this suite does not depend on the fix;
   - **cases 3, 4 and 5** deliver their agent knobs (`FAKE_AGENT_EXIT=1`,
     `FAKE_AGENT_SESSION=other`, the happy resume) by writing
     `$AGENT_ENV_FILE`, **never** by exporting into the test shell (V8), and
     truncate it in teardown;
   - **cases 7/8** invoke the coordinator **directly** so it inherits the test
     shell, and set `AITASKS_FROZEN_PAUSE_AT` **on that one invocation only**,
     never exported (V6/V9); they find it via
     `pgrep -f "aitask_frozen.sh restore $id"`;
   - **case 9** kills and recreates the *isolated* server via the
     `tmux_isolation.sh` helpers — never the user's;
   - **case 10 splits into two INDEPENDENT cycles** (V2). They must not share a
     record: 10a deletes it, so a 10b reusing the same id would have nothing to
     drop, and 10a's surviving stamped pane would linger into 10b and
     contaminate `_other_real_agents()`' kill-window-vs-kill-pane decision.
     Each subcase therefore does its own `launch_agent` → `freeze` → assert →
     teardown, and each verifies its own teardown before the next begins:
     - **10a** — `aitask_agent_sessions.sh drop <id>` (the tmux-free store):
       record gone, capture dir gone, and the **stand-in pane still alive with
       all three stamps intact**. That is the store's real contract, and 10a
       exists to pin it. Teardown: explicitly kill the orphaned stand-in window
       and assert it is gone, so nothing leaks into 10b.
     - **10b** — fresh cycle, then `aitask_frozen.sh drop <id>` →
       `DROPPED:<id>`, record and capture gone, and the pane verified **gone**
       (`kill-window` when it was the last real agent, else `kill-pane`).
       Assert the pane is gone — *not* that options were unset, which never
       happens: they die with the pane (`agent_freeze.py:946` docstring).
   - **case 11 is dropped.** `tests/test_session_hook_install.sh` Group C
     already asserts "still exactly ONE SessionStart group" across repeated
     `setup_claude_hooks`, against the same shipped function this suite calls.
     Re-running it here buys a second copy of an existing assertion at the cost
     of a second full setup in the timed budget. If a composed re-check is
     wanted, fold it into case 1 as a one-line count of the scratch project's
     `.claude/settings.json` SessionStart groups.
4. **Timing.** Print `ACCEPTANCE_ELAPSED:<s>`; assert `< 180`. With V1 fixed
   this is achievable; with V1 unfixed it is not.
5. **Docs.** Add the "Composed acceptance through shipped wrappers" paragraph
   to `aidocs/framework/testing_conventions.md`, pointing at this file as the
   pattern, and naming the two constraints from "Composed environment" (a) and
   (b) — they are the reusable part.

## Verification

```bash
bash tests/test_frozen_agents_acceptance.sh    # outside -L ait; per-case PASS/FAIL + timing
bash tests/test_freeze_engine_live.sh          # still green after the extraction
bash tests/test_restore_flows_live.sh          # still green after the extraction
bash tests/test_no_raw_tmux.sh
bash tests/test_session_hook_install.sh        # unaffected by the setup_claude_hooks reuse
```

`tests/test_cleanup_rule_parity.sh` is also still unrun (t1705_7's note); it
refuses while the `-L ait` server has panes. It is t1705_11's, not this task's,
but this is the environment in which it can finally run — do it while here.

## Risk

### Code-health risk: medium

- Extracting 13 duplicated helpers out of two large, currently-passing live
  suites (`test_freeze_engine_live.sh`, `test_restore_flows_live.sh`) can break
  them, and both are verifiable only in this same rare environment ·
  severity: medium · → mitigation: inline pre-phase `fixtures_extraction_control`
- `tests/lib/fake_agent.sh` is shared by several live suites; a new output knob
  that is not default-off changes their capture assertions · severity: medium ·
  → mitigation: inline pre-phase `fixtures_extraction_control`
- No production code is touched — the change is confined to `tests/` plus one
  `aidocs/` paragraph, which bounds the blast radius to the test tree ·
  severity: low · → mitigation: none needed

### Goal-achievement risk: high

- Re-verification found **eleven** assertions/knobs in this plan that were
  unreachable or ineffective against the shipped tree (V1–V11), six of them
  found only on later review passes. The same class
  of drift may remain in the parts that cannot be checked without running the
  suite · severity: high · → mitigation: inline pre-phase `env_seam_probe`
- The suite cannot be run at all from this session (blocked preflight), so
  nothing here is evidence yet; first-run success across 11 live cases, a real
  Textual viewer boot, a detached coordinator and a server kill/recreate is
  unlikely without iteration · severity: high · → mitigation: none — this is
  why the task stops on an approved plan and is re-picked outside tmux
- The real `ait frozenagent` viewer must boot in a pane under a wall-clock
  budget; CLAUDE.md records that live-TUI boot budgets become flakes under a
  loaded machine · severity: medium · → mitigation: none — run the suite on an
  otherwise idle box, as the preflight already demands
- The timed run reaches the hook installer via `--source-only` rather than the
  `ait setup` CLI, so a setup **precondition or integration** defect between
  the entry point and `setup_claude_hooks` is not covered by the default run —
  only dispatch (level 1) and the function itself (level 2) are · severity:
  medium · → mitigation: the three-level "Setup coverage" design; level 3
  (`AIT_ACCEPTANCE_FULL_SETUP=1`) closes it end-to-end and CI should set it
- Per-case behaviour now flows through a shared control file, so a case that
  forgets to truncate it silently changes a later case's agent · severity:
  medium · → mitigation: none needed — every case writes it on entry and
  truncates on teardown, and the probes assert terminal state, not just timing
- Layered configuration hides its own gaps: a knob set at two precedence levels
  is exercised only at the higher one, so the lower layer can be missing or
  malformed and nothing fails (V11). The suite sets three such knobs ·
  severity: medium · → mitigation: inline pre-phase `env_seam_probe`, probes
  C1/C2, which remove the higher layer so the lower one is observably
  responsible

### Planned mitigations
- timing: pre-phase | name: fixtures_extraction_control | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health blast radius into two working live suites + shared fake_agent.sh | desc: extract frozen_fixtures.sh and re-point both existing live suites first, proving both green before and after, with any new fake_agent.sh knob default-off
- timing: pre-phase | name: env_seam_probe | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: medium | addresses: V1/V11-class silent seam-and-config ineffectiveness | desc: prove each seam AND the scratch frozen config take effect, using stimuli that forbid the fast path (FAKE_AGENT_NO_HOOK for ack grace, a SIGKILLed leaseholder for stale-op grace), terminal verdicts, and bounds excluding the 20s/60s defaults; plus C1 (env-free capture_max_lines proves the config is read and the root resolved) and C2 (ack grace with the env override removed via env -u, proving the configured value is responsible); one run through the detached run-shell -b path
- timing: pre-phase | name: setup_entrypoint_coverage | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: bypassing the ait setup CLI while keeping the no-real-HOME guarantee | desc: assert `ait setup --help` routes through the real dispatch with zero side effects, and gate a full HOME-redirected `ait setup` end-to-end check behind AIT_ACCEPTANCE_FULL_SETUP=1 outside the timed region

## PINNED contracts (from p1705 — do not re-decide)

Copied verbatim from `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` §A–§D. On any discrepancy the parent plan wins; if a child must deviate, update the parent plan and every sibling plan in the same commit.

> **⚠ PARTLY SUPERSEDED — read the parent plan's `## Amendments from
> re-verification (t1705_5, 2026-09-07 / 2026-09-08)` block (B1–B7) BEFORE
> implementing anything from §A–§D below.** t1705_5 re-verified the §D restore
> contract against the shipped tree and amended it; the parent plan carries the
> authoritative list. The text below is retained as the unedited parent contract.
>
> The four that change §D's wire protocol:
>
> - **B1** — `restore-begin` and `lease-take` both REQUIRE `--owner-pid <pid>`.
> - **B2** — §D step 3's `env VAR=…` prefix is superseded by **`respawn-pane -e`**
>   (one `-e` per variable). The prefix is now the documented *fallback* for a
>   tmux build without `-e`, not the primary mechanism.
> - **B3** — the hook consumes only `AITASK_RESTORE_RECORD` and
>   `AITASK_RESTORE_NONCE`; the other two are exported as diagnostics only.
> - **B4** — §C's `restoring`/`aborting` reconcile rows are already SHIPPED
>   (t1705_4), so §C is a specification of existing behaviour.
>
> **Why this matters for this task specifically.** This is the ACCEPTANCE TEST.
> Asserting §D's original `env`-prefix wire format, or a `restore-begin` without
> `--owner-pid`, would pin the superseded protocol and fail against the shipped
> implementation. Assert B1–B4, not the text below.



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


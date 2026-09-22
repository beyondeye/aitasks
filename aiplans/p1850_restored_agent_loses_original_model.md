---
Task: t1850_restored_agent_loses_original_model.md
Base branch: main
Output branch: main
---

# t1850 — A restored agent loses its original model

## Context

A frozen agent restored with `R` comes back on the project's default model.
`agent_restore.build_resume_argv` / `build_repick_argv` pass the record's
`agent_string`, and that string is `''` in **every** record in
`~/.config/aitasks/agent_sessions.json`.

### Root cause (confirmed during planning)

TUI launches never go through the wrapper's `exec` path. Every TUI launch site
(board, monitor, minimonitor, codebrowser, brainstorm, syncer, tui_switcher,
the shadow spawners, `AgentCommandScreen`, and `pick_launch_argv`) calls
`agent_launch_utils.resolve_dry_run_command()`. That runs
`aitask_codeagent.sh --dry-run invoke …`, takes the printed `DRY_RUN:` command
and hands it to `launch_in_tmux`. `cmd_invoke` returns from the dry-run branch
**before** `export AITASK_AGENT_STRING=…` (`aitask_codeagent.sh:657-667`). The
agent therefore starts without the variable, and the SessionStart hook upserts
`--agent-string ""`, which the store treats as "not supplied" (t1802).

What I observed on this machine: this session's own `claude` process (the pane's
direct child of the tmux server, argv
`claude --model claude-opus-5 /aitask-pick 1850`) has **no**
`AITASK_AGENT_STRING` in `/proc/<pid>/environ`.

The other two candidates in the task are ruled out:
- **Hooks do inherit the agent's environment.** Restore acknowledgements
  depend on `AITASK_RESTORE_RECORD` reaching the hook, and record
  `7b9ad914` shows `ack: hook`.
- **The store keeps any non-blank value** (`agent_sessions.py:757`).

`agent_restore` already knows about the gap. It re-delivers the variable to its
replacements through `_restore_env` (see the comment at
`agent_restore.py:135-141`). Nothing delivers it on a normal launch.

## Implementation

### 1. Wrapper: `--dry-run` can emit the export it would perform
`.aitask-scripts/aitask_codeagent.sh`
- Add a global flag `--with-agent-env` (parsed next to `--dry-run`, variable
  `OPT_WITH_AGENT_ENV=false`). Document it in `show_help`.
- In `cmd_invoke`, resolve `agent_string` **before** the dry-run branch. Both
  paths then use one resolution, and the real-launch `export` stays
  byte-identical. When dry-running with the flag set:
  ```bash
  printf 'DRY_RUN:'
  [[ "$OPT_WITH_AGENT_ENV" == true ]] && printf ' %q' env "AITASK_AGENT_STRING=$agent_string"
  printf ' %q' "${CMD[@]}"
  ```
  Without the flag the output is unchanged. The ~86 bash assertions and the
  non-launch consumers (skillrun, chatlink preflight, crew runner) all parse
  plain `DRY_RUN:`, so they are unaffected.
- Why `env` rather than a bare `VAR=… cmd`: `env` **execs into** the agent, so
  `#{pane_pid}` remains the agent's pid. The task-lock liveness anchor (t1465)
  depends on that. The spike behind `agent_restore._env_prefixed` already
  measured it (Case 3).

### 2. Launch choke point passes the flag
`.aitask-scripts/lib/agent_launch_utils.py::resolve_dry_run_command`
- Always add `--with-agent-env` before `--dry-run`. Every TUI launch then
  carries `env AITASK_AGENT_STRING=<resolved> <agent argv>`. That covers all ~20
  call sites without touching them, including `pick_launch_argv` and the
  restore coordinator. For the coordinator, the outer `_env_prefixed`/`-e`
  delivery of the same value is now redundant but harmless.
- Update the docstring: why the prefix exists, and that it must stay `env`
  (exec) for the pane-pid anchor.
- Update the stale comment on `ENV_AGENT_STRING` in `lib/agent_restore.py`. It
  now says the dry-run carries the export too, and the `-e` delivery stays as a
  second line of defence. Keep that delivery, since removing it would be an
  unrelated change.
- Known limitation, recorded in the docstring: if a user hand-edits `--model`
  in `AgentCommandScreen`'s editable command, the env prefix still names the
  resolved model. The agent picker in that dialog regenerates both.

### 3. Freeze-time recovery for agents that have no string
This covers every agent already running now, which was launched before the fix
and has a blank record. Once an agent is frozen, the string cannot be recovered.

`.aitask-scripts/lib/agent_sessions.py`
- Generalize the cmdline reader: add `process_cmdline_argv(pid, *, proc_root)`
  as the public name and keep `_codex_cmdline_argv` as an alias or caller.
- Add `process_environ_value(pid, name, *, proc_root) -> str | None`, which
  reads `/proc/<pid>/environ`. It returns None when the file can't be read and
  never raises.
- Add `process_model_evidence(pid, *, proc_root) -> tuple[str, str]`, returning
  `(agent_kind, cli_id)`. It maps argv0's basename (`claude` → `claudecode`,
  `codex`, `opencode`) and reads `-m`/`--model`/`--model=` anywhere in argv,
  using the same parse as `codex_process_model`. Make `codex_process_model`
  delegate to it so there is one argv parser.

`.aitask-scripts/lib/agent_freeze.py`
- Generalize `_codex_agent_string(cli_id, root)` into
  `_resolve_cli_model(agent, cli_id, root)`: exact `AGENT_STRING:` match only,
  and the kind must equal `agent`. `_codex_agent_string` becomes a thin
  wrapper.
- New `_recover_agent_string(pane_pid, root) -> str`, in this order:
  1. `AITASK_AGENT_STRING` from the live process's environ, when
     `agent_kind_of()` accepts it and its kind agrees with argv0's kind (an
     unknown argv0 kind is accepted);
  2. otherwise argv0 kind + `--model`, resolved through `_resolve_cli_model`;
  3. otherwise `""`, meaning no evidence (for example `claude` launched with no
     `--model`).
- `_resolve_record`:
  - **stamped path:** after `_capture_codex_session`, add a new
    `_backfill_agent_string(record_id, facts, root)`. **Model recovery is kept
    separate from conversation capture, and it covers codex too.**
    `_observe_codex_session` returns before it ever reads the model whenever
    `codex_session_for_pid` misses. `MISS_NO_MATCH` (no rollout before the first
    turn) is one concrete trigger. Excluding codex here would leave a stamped
    blank codex record blank despite readable `--model` or environ evidence,
    and a re-pick would use the project default.
    - Re-read the record with `frozen_ops.store_show`, because the codex capture
      may have just written the string (or cleared the session id). Proceed only
      if the `agent_string` is **still blank**.
    - `v = _recover_agent_string(pane_pid, root)`; stop on `""`.
    - **Never pair a codex model with an unproven session.** If the re-read
      record holds a `codeagent_session_id` and `agent_kind_of(v) == "codex"`,
      skip. A blank-kind record with an id got that id from the SessionStart hook,
      and interactive codex fires no hook, so the id cannot be proven to be this
      codex's. Filling in the kind would turn the restore into
      `codex resume <foreign id>`.
    - Upsert **only** the model: `--id <rid> --root … --window … --pane …
      --pane-pid … --agent-string <v>`. Never pass `--session-id` or
      `--transcript`, so a cleared or unverified id is never restored.
    - Success is detected from the `UPSERTED:` line, not from `rc`, the same
      pattern `_capture_codex_session` uses. It never raises and warns on
      stderr.
  - **unstamped path:** the creating upsert stays **unchanged**. Its
    `--agent-string` remains the codex observation's verified value or `""`,
    and a recovered model is **not** folded into it. That upsert can select an
    **existing** record by pane identity or relocation, and
    `_apply_upsert_fields` keeps that record's `codeagent_session_id` when the
    field is omitted. That preservation is the guarantee that omission never
    erases a valid id, and it is kept. As a consequence, "no session id is being
    sent" proves nothing about the record that results. So, **after** the
    upsert has returned the selected `record_id` (and the pane is stamped),
    call the same `_backfill_agent_string(record_id, facts, root)`. The
    no-unproven-session guard then runs against the **actual selected record**
    as re-read from the store. Both paths share one guarded fill.
- The backfill never overwrites a non-blank stored value. Refreshing a
  disagreeing live model on a non-blank record stays with codex's own
  `_capture_codex_session`; for other agents it is out of scope.

### 4. Say so when restoring a record whose model is unknown
- `agent_sessions.py`: add a helper, `unknown_model_note(agent_string) -> str`.
  It returns `"original model unknown — restoring with the default model"` when
  `agent_kind_of(agent_string)` is empty, else `""`.
- `frozenagent/frozenagent_app.py::_start_restore` and
  `monitor/monitor_shared.py::_start_frozen_restore`: when the note is
  non-empty, append it to the dispatch notification with severity `warning`.
  This has to happen **at dispatch**: on success the viewer is replaced by the
  agent, so a message shown after the restore has nowhere to go.
- `lib/agent_restore.py::restore`: after the command resolves, print
  `WARNING:<rid>|original model unknown — restoring with the default model` to
  stderr, alongside the existing `transcript missing` warning. Leave the
  `RESTORED:` wire line format untouched.

### Post-phase (risk mitigations)
1. [pane_pid_anchor_live_check] In `tests/test_launch_agent_string_env.py`,
   add a live case that skips when tmux is missing. It uses a private tmux
   socket session (through the `lib/tmux_exec.py` gateway or a test-scoped
   `TMUX_TMPDIR`, with no raw tmux in framework code), then:
   - takes the prefix `resolve_dry_run_command` produced, applies it to
     `sleep 30`, and launches the result with `launch_in_tmux`;
   - asserts that the returned pane pid's `/proc/<pid>/cmdline` argv0 is
     `sleep`. That proves `env` exec'd, so the pane pid is the command itself
     and not a wrapper that would outlive it;
   - asserts that `/proc/<pid>/environ` contains
     `AITASK_AGENT_STRING=<value>`;
   - kills the session at the end.

## Tests
- `tests/test_codeagent.sh`: add one case after Test 11. `--with-agent-env
  --dry-run invoke pick 42` prints `DRY_RUN: env AITASK_AGENT_STRING=<default>`
  followed by the claude argv. Without the flag, the output does not contain
  `AITASK_AGENT_STRING`.
- New `tests/test_launch_agent_string_env.py` (real wrapper, like
  `test_pick_launch_argv.py`):
  - `resolve_dry_run_command(REPO_ROOT, "pick", "1")` starts with
    `env AITASK_AGENT_STRING=`, and the value equals `resolve_agent_string(...)`;
  - `agent_string="claudecode/sonnet5"` yields that value in the prefix;
  - `pick_launch_argv` carries the prefix;
  - the live pane-pid check (Post-phase `pane_pid_anchor_live_check`).
- `tests/test_agent_freeze.py` (extend) or a new
  `tests/test_agent_string_recovery.py`, using a fake `proc_root` with
  `cmdline`/`environ` files:
  - environ value wins; an environ value whose kind disagrees with argv0 is
    ignored;
  - argv0 `claude` plus `--model claude-opus-5` resolves to the models-JSON
    name (resolver patched);
  - no model → `""`; unreadable proc → `""`;
  - backfill: stored blank → upsert called with `--agent-string` only (no
    `--session-id`/`--transcript`); stored non-blank → no call;
  - **stamped blank codex record, `MISS_NO_MATCH`** (patch
    `codex_session_for_pid` to return the miss), with readable model evidence
    (`codex -m gpt-5.4` in cmdline, resolver patched to `codex/gpt5_4`):
    `_resolve_record` leaves the record with `agent_string == "codex/gpt5_4"`
    and no session id. Then `agent_restore.build_repick_argv(rec)` passes
    `agent_string="codex/gpt5_4"` to `pick_launch_argv` (patched), so the
    re-pick keeps the model;
  - same record, with a stored session id and a blank kind → no model fill
    (the no-unproven-session rule); a claudecode recovery on that record → it
    is filled;
  - **unstamped regression:** a store (in a temp `AITASK_SESSIONS` file) that
    holds an existing blank-model record with a `codeagent_session_id`,
    matched by pane identity. The pane has no `@aitask_record` or
    `@aitask_agent_session` stamp. A live codex process whose capture misses
    (`MISS_NO_MATCH`) has readable `-m` evidence. `_resolve_record` selects that
    record, which then **keeps its session id** (omission did not erase it) and
    **keeps a blank `agent_string`** (no codex model was paired with the
    unproven id). The same setup with argv0 `claude` fills `claudecode/<m>`.
- `unknown_model_note`: blank or malformed → note; well-formed → `""`.
- Re-run existing suites: `test_pick_launch_argv.py`, `test_agent_restore.py`,
  `test_agent_freeze.py`, `test_codeagent.sh`, `test_codeagent_op_wiring.sh`,
  `test_frozenagent_app.py`, and the full Python runner
  (`bash tests/run_all_python_tests.sh`, last line only). Run `shellcheck` on
  the wrapper.

## Verification (end-to-end)
1. After the change, launch a pick from `ait monitor`/board for any task. Check
   `tr '\0' '\n' </proc/<pane_pid>/environ | grep AITASK_AGENT_STRING`, then
   check the record's `agent_string` with
   `aitask_agent_sessions.sh show <id>`.
2. For an agent launched before the fix, freeze it. The record's `agent_string`
   is backfilled from `--model`.
3. Restore it. It comes back on the same model.

## Risk

### Code-health risk: low
- Every TUI launch command gains an `env AITASK_AGENT_STRING=…` prefix, which
  touches about 20 call sites through one choke point. A prefix that did not
  exec would break the pane-pid lock-liveness anchor (t1465). · severity: low
  (residual: `env` execs, and inline post-phase
  pane_pid_anchor_live_check verifies it) · → mitigation: inline post-phase
  pane_pid_anchor_live_check

### Goal-achievement risk: medium
- Freeze-time recovery depends on the agent's argv naming `--model` and on that
  id mapping exactly into `models_<agent>.json`. An unmapped id or a model-less
  launch yields no recovery, and the restore then warns instead of fixing.
  Codex model recovery is deliberately independent of the conversation
  capture, so a codex agent with no rollout yet still gets its model. It is
  withheld only where it would pair with an unproven session id.
  Records that are already frozen with a blank string cannot be recovered.
  · severity: medium · → mitigation: none

### Planned mitigations
- timing: post-phase | name: pane_pid_anchor_live_check | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health: env prefix must keep pane pid == agent pid | desc: live tmux test that a launch_in_tmux'd env-prefixed command execs (argv0 = command) and carries AITASK_AGENT_STRING

## Step 9
Post-implementation: commit the code, archive the task, and handle the plan file
per the task-workflow Step 9.

## Final Implementation Notes

- **Actual work done:** all four plan steps and the post-phase were implemented as planned.
  - The wrapper has a `--with-agent-env` flag. `resolve_dry_run_command` always
    passes it, so every TUI launch is `env AITASK_AGENT_STRING=<v> <agent argv>`.
  - Freeze-time recovery: `process_model_evidence` and `process_environ_value`
    in `agent_sessions.py`, plus `_resolve_cli_model`, `_recover_agent_string`
    and `_backfill_agent_string` in `agent_freeze.py`. Both `_resolve_record`
    paths call the backfill after the record is resolved.
  - `unknown_model_note` / `UNKNOWN_MODEL_NOTE` are shown at dispatch time in
    the frozenagent viewer and the monitor, and as a coordinator stderr
    `WARNING:`.
- **Deviations from plan:**
  - `_codex_cmdline_argv` kept its name. The new `process_model_evidence`
    reuses it rather than a renamed public alias.
  - `codex_process_model` shares `_argv_model` for the model parse.
- **Issues encountered:**
  - The shared freeze fixture uses `AGENT_PID=4242`, which can be a real
    process. The new `/proc` readers are therefore stubbed for every
    `_FreezeTestCase` test, not only the recovery ones, the same way the codex
    observers already were.
  - The live tmux test left stale socket files; its cleanup now unlinks them.
- **Key decisions:**
  - Review found two guard gaps, both fixed. Model recovery is separate from
    the codex conversation capture, and the no-unproven-session guard reads the
    record the upsert actually selected.
  - Negative controls:
    - a non-exec `sh -c` launch fails the live pane-pid test;
    - removing the codex/session guard fails 2 tests;
    - dropping the unstamped backfill fails 1 test.
- **Upstream defects identified:** None
- **Tests:**
  - `tests/test_codeagent.sh` 193/193.
  - Full Python suite passed (`runner=pytest, exit=0`).
  - `test_shadow_spawn_learner.sh`, `test_frozen_dry_run_wrapper.sh`,
    `test_no_raw_tmux.sh` and `test_restore_session_bootstrap_live.sh` pass.
  - Not run: `test_monitor_shadow_spawn_live.sh`, `test_restore_flows_live.sh`,
    `test_freeze_engine_live.sh` and `test_frozen_agents_acceptance.sh`. They
    refuse to run inside tmux, and this session is inside tmux.

## Post-Review Changes

### Change Request 1 (2026-09-22 09:40)
- **Requested by user:** two review findings.
  - (a) `cmd_invoke` resolved the agent string a second time for the env
    prefix, separately from the resolution `build_invoke_command` used for
    `CMD`. A config change between the two reads exported a different model
    than the one launched. The reviewer reproduced
    `AITASK_AGENT_STRING=claudecode/sonnet5 claude --model claude-opus-5`.
  - (b) `test_launch_agent_string_env.py` skipped whenever the resolver
    returned None, so a broken wrapper flag or output parse passed as
    "skipped".
- **Changes made:**
  - (a) `build_invoke_command` publishes the one value it built `CMD` from as
    `INVOKE_AGENT_STRING` (declared `local` in `cmd_invoke`, like `CMD`). Both
    the dry-run prefix and the real export read it, and nothing resolves a
    second time. New regression test 11a-2 in `tests/test_codeagent.sh` uses a
    `jq` shim that answers opus5 first and sonnet5 on every later read, with a
    control proving the shim switches. Negative control: a double-resolve
    mutant of the wrapper fails 2 of that test's assertions with exactly the
    reviewer's output.
  - (b) The dry-run needs only `jq` and the repo metadata (verified: it never
    looks for the agent binary). The tests now skip only on missing `jq`
    (plus tmux or `/proc` for the live case), or when `claudecode/sonnet5` is
    absent from the models JSON. A None from the resolver fails with an
    explicit message. Negative control: an always-None resolver gives
    4 failures, 0 skips.
- **Files affected:** `.aitask-scripts/aitask_codeagent.sh`,
  `tests/test_codeagent.sh`, `tests/test_launch_agent_string_env.py`

---
Task: t1736_manual_verification_fix_macos_only_suite_failures_followup.md
Base branch: main
Output branch: main
---

# t1736 — Manual verification of t1729 (BSD mktemp suffix fix): auto-execution record

Strategy: autonomous. All call sites were run in throwaway scratch projects
(copied `.aitask-scripts/`, `ait`, `aitasks/metadata/`, and the two needed
`seed/` files, plus scratch tasks) under the session scratchpad, against the real
`$TMPDIR` (`/var/folders/.../T/`), so the real task data, config and seed
files were never touched.

## Execution Log

### Item 1
- Item text: `ait brainstorm init --proposal-file <f>` twice in a row
- Approach: CLI invocation (scratch project)
- Action run: `./ait brainstorm init {1,2,3} --proposal-file proposal.md`. In the scratch copy only, `brainstorm_cli.py`'s `start_runner` branch was stubbed out, because it would launch a real interactive agent. The spec tmpfile is created earlier, in bash, so the path under test is unaffected.
- Output (trimmed): `INITIALIZED:1`, `INITIALIZED:2`, t3 `rc=0`; the task text reached `crew-brainstorm-2/br_session.yaml`; no `brainstorm_spec_*` leftovers
- Verdict: pass

### Item 2
- Item text: `ait update <id>` interactive description edit twice; `.md` suffix kept
- Approach: TUI interaction (fzf driven over a private tmux socket `-L av1736`)
- Action run: `ait update 1` → description → Open in editor → Done (no commit), done twice. `$EDITOR` was a logging script that recorded the path, asked vim for the detected filetype, and appended a marker line.
- Output (trimmed): paths `aitask_sYxBZK.md`, `aitask_goK0ym.md`; vim `filetype=markdown` (run 1's probe was misconfigured, not a product issue); task body ended with `EDIT_RUN_1` and `EDIT_RUN_2`
- Verdict: pass

### Item 3
- Item text: `ait crew command` x2 and `ait crew setmode` x2
- Approach: CLI invocation against the scratch crew `brainstorm-1`
- Action run: `ait crew command send --crew brainstorm-1 --agent initializer_bootstrap --command pause` x2; `ait crew setmode ... --mode headless` then `--mode interactive`
- Output (trimmed): `COMMAND_SENT:pause` x2, with both entries in the commands yaml; `UPDATED:...:headless`, `UPDATED:...:interactive` (push warning expected, since scratch has no remote)
- Verdict: pass

### Item 4
- Item text: `ait add-model` twice (six tmpfiles)
- Approach: CLI invocation. There is no `ait add-model` dispatcher verb; the helper is `.aitask-scripts/aitask_add_model.sh`, which the add-model skill calls.
- Action run: `add-json`, `promote-config --ops pick`, `promote-default-agent-string` for `avtest_a`, then again for `avtest_b`
- Output (trimmed): all six `rc=0`; both models present in metadata and seed `models_claudecode.json`; `defaults.pick` = `claudecode/avtest_b` in both configs; `DEFAULT_AGENT_STRING` and the resolution-chain note updated
- Verdict: pass

### Item 5
- Item text: `ait archive` verify-defer path twice
- Approach: CLI invocation on two scratch manual_verification tasks, each with one deferred item
- Action run: `aitask_archive.sh --with-deferred-carryover 10`, then `11`
- Output (trimmed): `CARRYOVER_CREATED:12`, `CARRYOVER_CREATED:13`, both `COMMITTED`; deferred items seeded into the carry-overs; no `ait_verify_defer_*` leftovers
- Verdict: pass
- Side observation (not t1729 scope): the seeded carry-over item text keeps the source's `— DEFER <timestamp>` annotation verbatim.

### Item 6
- Item text: `resource_admission_command` hook runs twice consecutively
- Approach: CLI invocation plus a pre-fix control
- Action run: scratch `project_config.yaml` with `resource_admission_command: "echo probing; exit 0"`; `aitask_resource_admission.sh` x3. Control: the same script reverted to plain `mktemp "..._XXXXXX.log"` with a private TMPDIR, run x2.
- Output (trimmed): fixed: 3x `VERDICT:admit` with unique log names. Pre-fix control: run 1 wrote a literal `aitask_resource_admission_XXXXXX.log`; run 2 printed `mkstemp failed ... File exists` / `DIAG:could not create a temporary log file`, rc=3
- Verdict: pass

### Item 7
- Item text: `ls "$TMPDIR"/*XXXXXX*` returns nothing
- Approach: file inspection plus repo grep
- Action run: count `XXXXXX` names in `$TMPDIR` and `/tmp`; grep `.aitask-scripts`, `.claude/skills`, `seed`, `ait` for suffixed templates outside `mktemp_suffixed`
- Output (trimmed): 0 and 0; remaining grep hits are comments and docs only
- Verdict: pass

## Cleanup
- Killed the tmux server `-L av1736`
- Removed scratchpad dirs `av1736_proj`, `av1736_6` (control TMPDIR inside), the editor script/log, and the proposal file
- Removed the 3 `aitask_resource_admission_*.log` files created in the real `$TMPDIR`

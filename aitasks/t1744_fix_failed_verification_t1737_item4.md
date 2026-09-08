---
priority: medium
effort: medium
depends: [1729]
issue_type: bug
status: Implementing
labels: [verification, bug]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: verification_failure
created_at: 2026-09-08 17:16
updated_at: 2026-09-08 17:27
---

## Failed verification item from t1729

> The fixture ladder: confirm `tests/lib/fake_agent_binary.py` takes rung 1 on Linux (copies the system `sleep`, which carries no restricted flag), never the compiled or symlink rungs.

### Source

- **Manual-verification task:** `aitasks/t1737_verify_macos_fixes_on_linux.md` (item #4)
- **Origin feature task:** t1729
- **Origin archived plan:** `aiplans/archived/p1729_fix_macos_only_suite_failures.md`

### Commits that introduced the failing behavior

- ce3a10af3 bug: Fix the macOS-only suite failures, and the mktemp idiom behind one (t1729)

### Files touched by those commits

- .agents/skills/task-workflow-remote-codex-/manual-verification.md
- aidocs/framework/sed_macos_issues.md
- .aitask-scripts/aitask_add_model.sh
- .aitask-scripts/aitask_archive.sh
- .aitask-scripts/aitask_brainstorm_init.sh
- .aitask-scripts/aitask_create_manual_verification.sh
- .aitask-scripts/aitask_crew_command.sh
- .aitask-scripts/aitask_crew_setmode.sh
- .aitask-scripts/aitask_resource_admission.sh
- .aitask-scripts/aitask_run_project_command.sh
- .aitask-scripts/aitask_update.sh
- .aitask-scripts/aitask_verification_followup.sh
- .aitask-scripts/lib/terminal_compat.sh
- .claude/skills/task-workflow/manual-verification.md
- .claude/skills/task-workflow-remote-/manual-verification.md
- .opencode/skills/task-workflow-remote-/manual-verification.md
- tests/golden/procs/task-workflow/manual-verification-default.md
- tests/golden/procs/task-workflow/manual-verification-fast.md
- tests/golden/procs/task-workflow/manual-verification-remote.md
- tests/lib/fake_agent_binary.py
- tests/test_agent_keys.py
- tests/test_board_startup_focus_live.py
- tests/test_brainstorm_init_proposal_file.sh
- tests/test_codebrowser_startup_focus_live.py
- tests/test_contribution_review.sh
- tests/test_merge_issues.sh
- tests/test_prompt_scoping_live.py
- tests/test_sed_compat.sh
- tests/test_skill_render_task_workflow.sh
- tests/test_stats_data.sh
- tests/test_tmux_exec.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1737 item #4.

## Measured evidence (t1737, Linux)

The item is **partially** falsified, and the distinction matters:

- **What holds:** the binary `fake_agent_binary()` *returns* on Linux is rung 1 —
  a byte-identical `shutil.copy` of `/usr/bin/sleep`, a regular file (not a
  symlink), mode `-rwxr-xr-x`. Linux has no `chflags`/SIP, so `os.stat` exposes
  no `st_flags` and the copy runs. The symlink rung is never reached.
- **What is falsified:** rung 2 is evaluated *unconditionally*, on every
  platform, including when rung 1 succeeds.

`tests/lib/fake_agent_binary.py:134`:

```python
for source in (_sleep_binary(), _compiled_sleeper_path()):
```

The tuple is built **eagerly**, so `_compiled_sleeper_path()` is called before
the loop body ever runs. It `mkdtemp`s a build dir, writes `sleeper.c`, invokes
`cc`/`clang`/`gcc`, and `_runs` the result — then the loop returns on its first
iteration and throws that work away.

Measured in a fresh process with `_compiled_sleeper_path` wrapped in a spy:

```
returned path is a copy of /usr/bin/sleep : True
returned path is a symlink                : False
rung-2 (_compiled_sleeper_path) CALL COUNT: 1
rung-2 actually produced a compiled binary: /tmp/ait-fake-agent-build-sfp9spfl/sleeper
```

This contradicts the module's own docstring, which describes a ladder that
"tries a ladder and **verifies each rung by running it**" — a ladder implies
rung 2 is consulted only when rung 1 fails.

**Impact:** correctness is unaffected (the right binary is returned). The cost is
one wasted C compilation per test *process* that touches this fixture — it is
memoised in the `_compiled_sleeper` module global, so it is once per process,
not once per call. It also means a box with no C toolchain does strictly more
work and logs more failure noise than it needs to.

**Suggested fix:** make the ladder lazy, e.g. iterate over thunks and call each
only when the previous rung has failed:

```python
for get_source in (_sleep_binary, _compiled_sleeper_path):
    source = get_source()
    ...
```

**Negative control:** forcing rung 1's copy to be unrunnable (patching `_runs` to
return `False` for the first dest) does fall through to rung 2 and returns the
compiled sleeper — so the fallback path itself is sound.

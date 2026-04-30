---
Task: t718_2_wire_long_running_tuis_to_fast_path.md
Parent Task: aitasks/t718_pypy_optional_runtime_for_tui_perf.md
Sibling Tasks: aitasks/t718/t718_3_documentation_pypy_runtime.md, aitasks/t718/t718_4_manual_verification_pypy_optional_runtime_for_tui_perf.md
Archived Sibling Plans: aiplans/archived/p718/p718_1_pypy_infrastructure_setup_resolver.md
Worktree: (none — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 14:28
---

# Plan: t718_2 — Wire long-running TUIs to require_ait_python_fast

## Context

Second of three children of parent t718. **Sibling t718_1 has landed** —
`require_ait_python_fast` is defined in `.aitask-scripts/lib/python_resolve.sh:130`
alongside `require_ait_python` (line 93) and `require_ait_pypy` (line 123).
This task is a focused single-line edit: each long-running Textual TUI
launcher swaps its `require_ait_python` call for `require_ait_python_fast`.
After this lands, once a user has run `ait setup --with-pypy`, the named TUIs
auto-route through PyPy.

## Verification finding (this re-pick, 2026-04-30)

The original plan listed **5 launchers**. A re-grep of
`require_ait_python\b` callers found a 6th launcher matching the same pattern:
`.aitask-scripts/aitask_syncer.sh` (added by t713_2 after t718 was planned).
It is a long-running Textual TUI (`syncer TUI entrypoint and Textual app
shell`) with `PYTHON="$(require_ait_python)"` at line 12 — identical shape to
the other 5. Per user direction during verify, **scope is expanded to include
`aitask_syncer.sh` (6 launchers total)**.

All other `require_ait_python` callers were re-confirmed as out-of-scope:
brainstorm helpers (non-TUI), crew helpers (short-lived), `aitask_stats.sh`
(one-shot CLI), `aitask_diffviewer.sh` (transitional per CLAUDE.md),
`aitask_explain_context.sh`, `aitask_monitor.sh`, `aitask_minimonitor.sh`.

## Files modified (exactly 6)

1. `.aitask-scripts/aitask_board.sh` — line 12
2. `.aitask-scripts/aitask_codebrowser.sh` — line 12
3. `.aitask-scripts/aitask_settings.sh` — line 12
4. `.aitask-scripts/aitask_stats_tui.sh` — line 12
5. `.aitask-scripts/aitask_brainstorm_tui.sh` — line 12
6. `.aitask-scripts/aitask_syncer.sh` — line 12

Each edit:

```diff
-PYTHON="$(require_ait_python)"
+PYTHON="$(require_ait_python_fast)"
```

All 6 files have the identical literal at line 12 (verified during this
re-pick via `awk 'NR==12'`).

## Files explicitly NOT modified in this task (verify in git diff)

- `.aitask-scripts/aitask_monitor.sh` — bottleneck is `fork+exec(tmux)`. **Sibling t718_5 (created by this task — see below) will empirically verify whether PyPy helps here despite the assumed dominance of fork/exec.**
- `.aitask-scripts/aitask_minimonitor.sh` — same as monitor; covered by t718_5.
- `.aitask-scripts/aitask_stats.sh` — one-shot CLI, PyPy warmup hurts
- `.aitask-scripts/aitask_diffviewer.sh` — transitional per CLAUDE.md, will fold into brainstorm
- `.aitask-scripts/aitask_brainstorm_*.sh` siblings other than `_tui` — short-lived helpers
- `.aitask-scripts/aitask_crew_*.sh` — short-lived helpers
- `.aitask-scripts/aitask_explain_context.sh` — short-lived helper
- `.aitask-scripts/lib/python_resolve.sh` — defines the resolvers; not a launcher

If `git diff --stat` after the edits shows any file outside the 6-element list
above, that is a scope violation — revert the extra change.

## Implementation steps

### 1. Pre-flight: confirm t718_1 has landed

Already confirmed during this re-pick:
- `lib/python_resolve.sh:130` defines `require_ait_python_fast`
- `lib/python_resolve.sh:123` defines `require_ait_pypy`
- Archived plan at `aiplans/archived/p718/p718_1_pypy_infrastructure_setup_resolver.md`

### 2. Edit each launcher

Use the `Edit` tool per file with this exact replacement:
- old_string: `PYTHON="$(require_ait_python)"`
- new_string: `PYTHON="$(require_ait_python_fast)"`

All 6 launchers use the identical literal at line 12 (re-confirmed).

### 3. Lint

```bash
shellcheck .aitask-scripts/aitask_board.sh \
           .aitask-scripts/aitask_codebrowser.sh \
           .aitask-scripts/aitask_settings.sh \
           .aitask-scripts/aitask_stats_tui.sh \
           .aitask-scripts/aitask_brainstorm_tui.sh \
           .aitask-scripts/aitask_syncer.sh
```

### 4. Verify scope

```bash
git diff --stat
# Should show exactly the 6 files above. No others.

git diff -- .aitask-scripts/aitask_monitor.sh .aitask-scripts/aitask_minimonitor.sh
# Should be empty.
```

### 5. Create follow-up sibling task t718_5 (monitor/minimonitor fast-path verification)

Per user direction, create a new sibling task whose purpose is to *empirically
verify* whether PyPy helps `monitor` / `minimonitor` despite the
`fork+exec(tmux)` bottleneck assumption documented in t718's parent
description. The parent currently lists `children_to_implement:
[t718_2, t718_3, t718_4]`; the create command with `--parent 718` will append
t718_5 to that list automatically.

Use the **Batch Task Creation Procedure** (see
`.claude/skills/task-workflow/task-creation-batch.md`):

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --parent 718 \
  --name verify_pypy_for_monitor_minimonitor \
  --priority low \
  --effort low \
  --issue-type performance \
  --labels performance,tui \
  --depends t718_2 \
  --desc-file <<TASKDESC
## Context

Sibling of t718_2. Parent t718 deliberately excluded \`aitask_monitor.sh\`
and \`aitask_minimonitor.sh\` from the PyPy fast path under the assumption
that their dominant cost is \`fork+exec(tmux)\` (which PyPy cannot
accelerate). t719 is the planned tmux control-mode refactor for the
fork/exec cost.

This task empirically tests that assumption: temporarily wire monitor and
minimonitor to \`require_ait_python_fast\` and measure whether PyPy yields
any meaningful improvement under CPython baseline vs PyPy. If yes (>10-15%
on a representative workload), keep the fast-path migration. If no, revert
the change and document the negative result so the assumption is
empirically anchored.

This is exploratory/verification work, not a feature. The deliverable is
either:
(a) the 2-line edit landing in main with measurement evidence, or
(b) the negative-result note in the parent's plan plus a CLAUDE.md
    Project-Specific note that PyPy is *not* worth wiring for these two
    TUIs.

## Key Files to Modify (transient)

- \`.aitask-scripts/aitask_monitor.sh\` — line 12
- \`.aitask-scripts/aitask_minimonitor.sh\` — line 12

Both currently have \`PYTHON="\$(require_ait_python)"\`. Swap to
\`require_ait_python_fast\`. Whether this edit becomes permanent depends
on the measurement.

## Reference Files for Patterns

- Sibling t718_2's plan (\`aiplans/archived/p718/p718_2_*.md\` after archival)
  — same edit pattern.
- \`aidocs/python_tui_performance.md\` — PyPy speedup analysis. Update
  with measurement results from this task.

## Implementation Plan

1. **Baseline measurement (CPython):** Time a representative monitor /
   minimonitor workload under CPython. Suggested: launch monitor, page
   through 50 sessions, measure total elapsed time and tmux IPC count
   (use \`strace -c -e fork,execve\` or similar to confirm
   fork+exec dominates).
2. **Apply the edit:** Swap to \`require_ait_python_fast\` in both
   launchers.
3. **PyPy measurement:** Same workload, with \`AIT_USE_PYPY=1\`
   (PyPy installed via \`./ait setup --with-pypy\`).
4. **Decision:**
   - If PyPy improves wall-clock by >10-15% on representative workload:
     keep the edit, file under "performance feature" — task lands as
     implemented.
   - Otherwise: revert the edit, write a "Negative result" note in the
     parent t718 plan and \`aidocs/python_tui_performance.md\` confirming
     fork/exec dominance, leave a CLAUDE.md Project-Specific note that
     monitor/minimonitor stay on CPython for the foreseeable future
     (until t719's tmux control-mode refactor lands and the picture
     changes).

## Verification Steps

- Document baseline + PyPy timings in plan's Final Implementation Notes.
- If kept: \`shellcheck\` clean on both modified files; smoke test that
  \`./ait monitor\` still launches and renders normally with and without
  PyPy installed.
- If reverted: \`git diff\` against base shows no change to the 2 files
  after revert; the negative-result note is added to the parent plan and
  to \`aidocs/python_tui_performance.md\`.

## Notes

- This task is intentionally low priority — it is exploratory. It can be
  picked anytime after t718_2 archives. It does not block t718_3 (docs)
  or t718_4 (manual verification) of the originally-planned fast-path TUIs.
- Do not let this task expand into the t719 tmux control-mode refactor
  — that is a separate, much larger piece of work. This task is purely
  the 2-line swap + measurement.
TASKDESC
```

After the create script returns, parse `CREATED:t718_5_*.md` and confirm the
parent's `children_to_implement` was updated to include `t718_5`.

The task above explicitly does not need a sibling plan file written upfront —
it's exploratory and the planning will happen when it's picked.

## Verification (this task)

1. **Without PyPy installed:** `./ait board` launches via CPython exactly as
   before. (`require_ait_python_fast` falls through to `require_ait_python`.)
   Visual smoke: TUI renders normally. Repeat for codebrowser, settings,
   stats_tui, brainstorm_tui, syncer.
2. **With PyPy installed (`./ait setup --with-pypy` already run):** `./ait
   board` auto-launches under PyPy. Verify by adding a temporary
   `print(sys.implementation.name)` to a startup hook, OR by running:
   ```bash
   AIT_USE_PYPY=1 ~/.aitask/pypy_venv/bin/python -c "import sys; print(sys.implementation.name)"
   ```
   …and trusting the resolver. Repeat for the other 5 fast-path TUIs.
3. **`AIT_USE_PYPY=0 ./ait board`** (with PyPy installed) launches under CPython.
4. **`AIT_USE_PYPY=1 ./ait board`** (without PyPy installed) errors with the
   message from `require_ait_pypy`.
5. **`AIT_USE_PYPY=1 ./ait monitor`** (with PyPy installed) **still uses
   CPython** in this task — t718_5 will revisit empirically.
6. `shellcheck` clean on all 6 modified files.
7. After Step 5 of implementation: `./.aitask-scripts/aitask_ls.sh -v
   --children 718 99` shows t718_5 as a pending child of t718.

## Notes for sibling tasks

- t718_3 (documentation) lands after this. Update its draft to mention 6
  fast-path TUIs (add `syncer` to the user-visible list alongside board,
  codebrowser, settings, stats, brainstorm). Also mention the existence of
  t718_5 as a follow-up exploration for monitor/minimonitor.
- t718_4 (manual verification) — its checklist already enumerates the
  fast-path TUIs; add a syncer verification line if not present.
- t718_5 (created here) — exploratory, low priority, no plan file required
  upfront.
- Future newly-introduced long-running TUIs should call `require_ait_python_fast`
  from the start; CLAUDE.md may want a one-line rule documenting this.

## Step 9 (Post-Implementation)

Standard child-task archival per `task-workflow/SKILL.md` Step 9.

## Final Implementation Notes

- **Actual work done:** Implemented the 6-launcher fast-path swap exactly as planned. Each of `aitask_board.sh`, `aitask_codebrowser.sh`, `aitask_settings.sh`, `aitask_stats_tui.sh`, `aitask_brainstorm_tui.sh`, and `aitask_syncer.sh` had its line-12 `PYTHON="$(require_ait_python)"` swapped to `PYTHON="$(require_ait_python_fast)"`. `git diff --stat` shows exactly 6 files, 1 insertion + 1 deletion each. `monitor` / `minimonitor` confirmed untouched. Step 5 (follow-up sibling) created `aitasks/t718/t718_5_verify_pypy_for_monitor_minimonitor.md` with priority/effort low; auto-sibling-dep was overridden to make t718_5 depend on t718_2 only (not on t718_4) so it can be picked independently of the docs+manual-verification chain.
- **Deviations from plan:** Two minor:
  1. The plan's `aitask_create.sh` snippet used `--depends t718_2` and `--issue-type performance`; the actual flags are `--deps` and `--type` respectively. Used the correct flag names.
  2. The default sibling-dep chain made t718_5 depend on t718_4. Per the plan's "does not block t718_3 / t718_4" intent, the dep was rewritten to `t718_2` only via `aitask_update.sh --batch 718_5 --deps t718_2` and committed.
- **Issues encountered:** None. shellcheck reported only pre-existing SC1091 (info-level) noise on `source` lines for all 6 launchers — already documented as upstream noise in t718_1's Final Implementation Notes; not introduced by this task.
- **Key decisions:**
  1. **Scope expansion to include `aitask_syncer.sh`** — the original plan listed 5 launchers; verify-mode grep surfaced a 6th matching the same pattern (added by t713_2 after t718 was planned). User confirmed expansion via the verify AskUserQuestion. This is the documented mechanism for keeping the fast-path list current as new long-running TUIs are introduced.
  2. **t718_5 created as exploratory follow-up** — User explicitly requested a follow-up sibling to empirically verify the parent's "monitor/minimonitor stay on CPython" assumption rather than treat it as immutable. Task is intentionally low-priority and stays out of the docs/manual-verification critical path.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - t718_3 (documentation) — when written, mention **6 fast-path TUIs** (board, codebrowser, settings, stats, brainstorm, **syncer**) plus the existence of t718_5 as the deferred monitor/minimonitor evaluation. The parent task description's "(board, codebrowser, settings, stats)" enumeration in `aidocs/python_tui_performance.md` may need a similar update.
  - t718_4 (manual verification) — when picked, the Manual Verification Procedure should add a `syncer` smoke-test line to its checklist alongside the other 5 TUIs.
  - t718_5 — exploratory, blocked-on=t718_2 only. Plan file is intentionally not pre-written; the picker will plan when picked.
  - Future long-running TUIs introduced after this point should call `require_ait_python_fast` (not `require_ait_python`) from the start. A one-line rule in CLAUDE.md's "Shell Conventions" section would prevent the next drift; this is *not* in scope for this task but is a candidate for the t718_3 docs work or a separate small chore task.
  - The `require_ait_python_fast` resolver contract from t718_1 held perfectly: drop-in replacement, fall-through to CPython when PyPy is absent, no functional change for non-PyPy users.

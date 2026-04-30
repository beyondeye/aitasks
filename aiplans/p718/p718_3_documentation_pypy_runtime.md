---
Task: t718_3_documentation_pypy_runtime.md
Parent Task: aitasks/t718_pypy_optional_runtime_for_tui_perf.md
Sibling Tasks: aitasks/t718/t718_1_pypy_infrastructure_setup_resolver.md (archived), aitasks/t718/t718_2_wire_long_running_tuis_to_fast_path.md (archived), aitasks/t718/t718_4_manual_verification_pypy_optional_runtime_for_tui_perf.md, aitasks/t718/t718_5_verify_pypy_for_monitor_minimonitor.md
Archived Sibling Plans: aiplans/archived/p718/p718_1_pypy_infrastructure_setup_resolver.md, aiplans/archived/p718/p718_2_wire_long_running_tuis_to_fast_path.md
Worktree: (none — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 15:12
---

# Plan: t718_3 — Documentation for PyPy runtime

## Context

Final implementation child of parent t718 (manual-verification sibling t718_4
and exploratory sibling t718_5 are scoped separately). Siblings t718_1
(infrastructure) and t718_2 (TUI wiring) are archived; the user-visible
surface is final:

- `ait setup --with-pypy` installs PyPy 3.11 into `~/.aitask/pypy_venv/`
  (~100-150 MB).
- Six long-running Textual TUIs auto-route through PyPy when installed:
  **board, codebrowser, settings, stats-tui, brainstorm, syncer**.
- `AIT_USE_PYPY=0/1` env var overrides per invocation; precedence is
  defined by `require_ait_python_fast` in `lib/python_resolve.sh`.
- Monitor / minimonitor remain on CPython (their bottleneck is
  `fork+exec(tmux)`, not Python execution). Sibling t718_5 will
  empirically verify this assumption.

This task documents that surface in the framework-internal CLAUDE.md and the
user-facing website. README.md is unchanged because it does not currently
enumerate setup flags.

## Verification status (this re-pick, 2026-04-30)

Re-verified the existing plan at `aiplans/p718/p718_3_documentation_pypy_runtime.md`
against the current codebase. Findings that changed the plan:

1. **CLAUDE.md insertion point.** Original plan said "add a subsection
   under 'Shell Conventions'". Since the original plan was written, commit
   `94e7b540` added a `require_ait_python_fast` contributor rule to **TUI
   (Textual) Conventions** (line 162-168), not Shell Conventions. The new
   `AIT_USE_PYPY` env-var precedence table belongs alongside that existing
   bullet — **TUI Conventions, not Shell Conventions**.

2. **TUI count.** Original plan listed 5 fast-path TUIs (board, codebrowser,
   settings, stats-tui, brainstorm). t718_2 expanded scope to **6** by
   including `aitask_syncer.sh` (added by t713_2 after t718 was planned).
   Verified via grep: `aitask_syncer.sh:12` calls `require_ait_python_fast`.
   All user-visible enumerations must list 6.

3. **Cross-task reference.** t718_5 was created during t718_2 implementation
   as the empirical follow-up for monitor / minimonitor. User-facing docs
   should mention that the exclusion is a current default, with a follow-up
   evaluation in flight.

4. **Aidoc drift.** `aidocs/python_tui_performance.md:109` enumerates only
   `aitask_board.sh, aitask_codebrowser.sh, aitask_settings.sh,
   aitask_stats.sh` for the fast path. This was the planned scope at
   t718's writing; current scope is 6 launchers. Minor correctness fix
   in scope for this task because that aidoc is the canonical reference
   cross-linked from CLAUDE.md.

5. **README.md.** Inspected — README mentions `ait setup` only as a basic
   bootstrap command and does not enumerate setup flags. Per the original
   plan's conditional ("only if README mentions setup flags"), **skip
   README.md**.

6. **Website setup page.** `website/content/docs/commands/setup-install.md`
   is the natural setup-flags reference; step 7 covers the Python venv.
   `website/content/docs/installation/_index.md` lists global dependencies.
   The dedicated page approach (a new `installation/pypy.md`) is preferred
   over inlining everything into setup-install.md — keeps the optional
   nature of PyPy obvious and gives room for the precedence table and
   diagnostics without bloating a step-by-step setup guide. Cross-link
   from both setup-install.md (step 7) and installation/_index.md
   (Global dependencies).

## Files to modify

1. `CLAUDE.md` — add a new bullet in "TUI (Textual) Conventions" section
   (right after the existing `require_ait_python_fast` rule) documenting
   the `AIT_USE_PYPY` env-var precedence table.
2. `website/content/docs/installation/pypy.md` — new file: dedicated PyPy
   page covering install, opt-out, diagnostics, and the env-var precedence.
3. `website/content/docs/commands/setup-install.md` — extend step 7 with a
   one-line cross-link to the new PyPy page.
4. `website/content/docs/installation/_index.md` — extend "Global
   dependencies" with a one-line cross-link to the new PyPy page.
5. `aidocs/python_tui_performance.md` — update the "Option A" launchers
   row (line 109) from 4 to 6 fast-path TUIs (correctness fix).

**Out of scope:** any `.aitask-scripts/*.sh` change, any change to
`lib/python_resolve.sh`, `aitask_setup.sh`, or test files. `git diff --stat`
must show only `.md` files (CLAUDE.md, the website docs, and the aidoc).
Any `.sh`/`.py` change is a scope violation.

## Implementation steps

### 1. CLAUDE.md addition

Insert after the existing `require_ait_python_fast` bullet in "TUI (Textual)
Conventions" (between current line ~168 and the `n` is the create-task key
bullet at line ~170). New bullet content:

```markdown
- **`AIT_USE_PYPY` precedence (runtime override).** When PyPy has been
  installed via `ait setup --with-pypy`, the six fast-path TUIs (board,
  codebrowser, settings, stats-tui, brainstorm, syncer) auto-route through
  `~/.aitask/pypy_venv`. The `AIT_USE_PYPY` env var overrides per
  invocation:

  | `AIT_USE_PYPY` | PyPy installed? | Result |
  |----------------|-----------------|--------|
  | `1`            | Yes             | PyPy (forced) |
  | `1`            | No              | error: install with `ait setup --with-pypy` |
  | `0`            | (any)           | CPython (override) |
  | unset          | Yes             | PyPy (default once installed) |
  | unset          | No              | CPython (current behavior preserved) |

  Monitor / minimonitor stay on CPython regardless of `AIT_USE_PYPY` — their
  bottleneck is `fork+exec(tmux)`, not Python execution. Sibling task t718_5
  will empirically re-evaluate. Full analysis:
  `aidocs/python_tui_performance.md`.
```

Format-match neighbors: bullet starts with bold rule-statement, followed by
elaboration. Do not narrate rollout history per CLAUDE.md "Documentation
Writing" rules.

### 2. New website page — `website/content/docs/installation/pypy.md`

Hugo/Docsy frontmatter following the pattern of neighboring installation
pages (e.g., `windows-wsl.md`, `macos.md`). Page outline:

```markdown
---
title: "PyPy Runtime (Optional)"
linkTitle: "PyPy Runtime"
weight: 60
description: "Optional PyPy 3.11 sibling interpreter for faster long-running TUIs"
---

## What it is

aitasks supports an opt-in **PyPy 3.11** sibling interpreter for the
long-running Textual TUIs. PyPy's tracing JIT typically yields **2-5×**
speedups on Textual + Rich workloads, helping board / codebrowser /
settings / stats-tui / brainstorm / syncer TUIs feel snappier under
heavy use.

CPython remains the default. PyPy is sibling, not replacement —
short-lived CLI scripts (`ait pick`, `ait create`, etc.) and the
monitor / minimonitor TUIs continue to use CPython, where PyPy's ~150-300
ms warmup would hurt or where the bottleneck is OS-level (fork/exec) and
PyPy cannot help.

## Install

```bash
ait setup --with-pypy
```

This installs PyPy 3.11 into `~/.aitask/pypy_venv/` (~100-150 MB) with the
same dependency set as the regular CPython venv. `ait setup` (without the
flag) also offers an interactive prompt on TTYs.

Once installed, the six fast-path TUIs auto-route through PyPy:

| TUI            | Command           |
|----------------|-------------------|
| Board          | `ait board`       |
| Code Browser   | `ait codebrowser` |
| Settings       | `ait settings`    |
| Stats          | `ait stats-tui`   |
| Brainstorm     | `ait brainstorm`  |
| Syncer         | `ait sync`        |

No further action required — the resolver in `lib/python_resolve.sh` picks
PyPy automatically when the venv exists.

## Override per invocation

The `AIT_USE_PYPY` env var lets you force CPython (or force PyPy) for a
single command:

| `AIT_USE_PYPY` | PyPy installed? | Result |
|----------------|-----------------|--------|
| `1`            | Yes             | PyPy (forced) |
| `1`            | No              | error: install with `ait setup --with-pypy` |
| `0`            | (any)           | CPython (override) |
| unset          | Yes             | PyPy (default once installed) |
| unset          | No              | CPython |

Examples:

```bash
AIT_USE_PYPY=0 ait board     # one-off CPython run with PyPy installed
AIT_USE_PYPY=1 ait codebrowser  # error if PyPy not installed
```

## TUIs that don't use PyPy

`ait monitor` and `ait minimonitor` stay on CPython. Their bottleneck is
`fork+exec(tmux)` per refresh tick — an OS-level cost that PyPy cannot
accelerate. A separate task (t718_5) will empirically verify whether PyPy
yields any meaningful improvement under representative workloads; until
that lands, monitor / minimonitor stay on CPython.

`ait stats` (the one-shot CLI variant) and other short-lived CLIs also
stay on CPython — the ~150-300 ms PyPy warmup would dominate their total
runtime.

## Diagnostics

Confirm the PyPy venv is healthy:

```bash
~/.aitask/pypy_venv/bin/python -c "import sys; print(sys.implementation.name, sys.implementation.version)"
# Expected output: pypy sys.version_info(major=3, minor=11, ...)
```

Confirm `textual` is importable:

```bash
~/.aitask/pypy_venv/bin/python -c "import textual; print(textual.__version__)"
```

## Disable / remove

- **One-off:** `AIT_USE_PYPY=0 ait board`
- **Persistent:** `rm -rf ~/.aitask/pypy_venv` — the resolver falls
  through to CPython silently. Re-run `ait setup --with-pypy` to reinstall.

## Background

For the per-TUI bottleneck analysis and PyPy compatibility audit that
motivated this design, see
[`aidocs/python_tui_performance.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/python_tui_performance.md)
in the repo.

---

**Next:** [Known Issues]({{< relref "known-issues" >}})
```

### 3. `website/content/docs/commands/setup-install.md` — cross-link

In step 7 (Python venv) of the "Guided setup flow" list, append a sentence
after the existing plotext mention:

> For an opt-in PyPy 3.11 venv that speeds up long-running TUIs, see
> [PyPy Runtime]({{< relref "/docs/installation/pypy" >}}).

### 4. `website/content/docs/installation/_index.md` — cross-link

In the "**Global dependencies**" section near line 131, after the line about
`Python venv at ~/.aitask/venv/...`, add a sub-bullet:

> - Optional: PyPy 3.11 venv at `~/.aitask/pypy_venv/` for faster TUIs — see
>   [PyPy Runtime]({{< relref "pypy" >}})

### 5. `aidocs/python_tui_performance.md` — correctness fix

Update line 109 (Option A row "TUI launchers"):

```diff
-`aitask_board.sh`, `aitask_codebrowser.sh`, `aitask_settings.sh`, `aitask_stats.sh` use new `require_ait_python_fast`
+`aitask_board.sh`, `aitask_codebrowser.sh`, `aitask_settings.sh`, `aitask_stats_tui.sh`, `aitask_brainstorm_tui.sh`, `aitask_syncer.sh` use new `require_ait_python_fast`
```

Note `aitask_stats.sh` → `aitask_stats_tui.sh` (the actual fast-path
launcher; `stats.sh` is the short-lived CLI). Add `aitask_brainstorm_tui.sh`
and `aitask_syncer.sh` per t718_2's expanded scope.

This is a localized correctness fix to a single table cell — no narrative
rewrite of the analysis. The rest of the aidoc remains as the canonical
historical reference.

## Verification

1. `cd website && hugo build --gc --minify` succeeds with no broken
   cross-link warnings involving the new `pypy.md` page.
2. `grep -n "AIT_USE_PYPY\|--with-pypy" CLAUDE.md website/content/docs/ -r`
   shows both surfaces (env var and flag) documented in CLAUDE.md and the
   new website page.
3. `grep -n "syncer" website/content/docs/installation/pypy.md
   aidocs/python_tui_performance.md` shows the 6-launcher list in both.
4. `git diff --stat` shows changes only to:
   - `CLAUDE.md`
   - `website/content/docs/installation/pypy.md` (new)
   - `website/content/docs/commands/setup-install.md`
   - `website/content/docs/installation/_index.md`
   - `aidocs/python_tui_performance.md`
   No `.aitask-scripts/`, `.py`, `.sh`, or test file edits.
5. Spot-check the rendered website locally (`cd website && ./serve.sh`) —
   verify the new page renders, the env-var table formats, code blocks
   highlight, and cross-links from setup-install.md and installation/_index.md
   resolve.

## Step 9 (Post-Implementation)

Standard child-task archival per `task-workflow/SKILL.md` Step 9. After this
task archives, the parent t718's `children_to_implement` will lose t718_3.
Manual-verification sibling t718_4 and exploratory sibling t718_5 still
remain on the parent's pending list — t718 does NOT auto-archive yet.

## Notes for sibling tasks

- t718_4 (manual verification) — when picked, the verification checklist
  should include a smoke test of the new website page (e.g., does the
  PyPy-runtime page render, do its links resolve, does the env-var table
  format correctly under the active Hugo theme). Add this to the checklist
  if the seeder did not already include it.
- t718_5 (exploratory monitor/minimonitor evaluation) — independent of
  this task. After t718_5 lands either way, the exclusion paragraph in
  the new `pypy.md` page should be amended to reflect the empirical
  result (either "PyPy is now wired in too" or "negative result:
  fork+exec dominance confirmed; CPython is the long-term answer").
  Either way, the amendment is t718_5's responsibility, not this task's.
- The CLAUDE.md TUI-Conventions section is now the canonical contributor
  reference for both the function-choice rule and the env-var precedence.
  Future PyPy-related contributor rules belong there.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned across five `.md` files:
  (1) New bullet in `CLAUDE.md` "TUI (Textual) Conventions" section (line ~170) with the `AIT_USE_PYPY` precedence table and the 6-TUI fast-path enumeration.
  (2) New page `website/content/docs/installation/pypy.md` (~99 lines) with frontmatter `weight: 60`, sections What it is / Install (with TUI table) / Override per invocation / TUIs that don't use PyPy / Diagnostics / Disable-remove / Background.
  (3) `website/content/docs/commands/setup-install.md` step 7 extended with one-sentence cross-link to the new page.
  (4) `website/content/docs/installation/_index.md` Global dependencies extended with one-bullet cross-link.
  (5) `aidocs/python_tui_performance.md` line 109 (Option A "TUI launchers" cell) updated to enumerate the actual 6 fast-path launchers (was 4) and corrected `aitask_stats.sh` → `aitask_stats_tui.sh` (the actual fast-path launcher; `stats.sh` is the short-lived CLI). Hugo build verified: 181 pages, no broken cross-link warnings, the only WARN is a pre-existing `.Site.AllPages` deprecation unrelated to this change.
- **Deviations from plan:** None of substance. The new `pypy.md` page and the CLAUDE.md addition match the plan drafts byte-for-byte modulo whitespace. The `aidoc` correction also lifted `aitask_stats.sh` into the short-lived CLI list (it was previously only implied by exclusion) — minor clarification beyond the strict diff in the plan, kept the table internally consistent.
- **Issues encountered:** None. The plan's verify-mode pass (with the 4 findings logged in "Verification status (this re-pick)") had already correctly anchored the insertion points (CLAUDE.md TUI Conventions, not Shell Conventions), the 6-launcher count, and the README.md skip decision before any edit was made.
- **Key decisions:**
  1. **CLAUDE.md placement** — adjacent to the existing `require_ait_python_fast` contributor-rule bullet (TUI Conventions), not in Shell Conventions as the original plan had said. Same audience, same conceptual neighborhood; the env-var precedence table reads as a continuation of the contributor rule.
  2. **Dedicated `pypy.md` page over inlining** — kept the optional/opt-in nature of PyPy obvious and gave room for the precedence table + diagnostics without bloating the step-by-step setup-install.md guide.
  3. **README.md skip** — README does not currently enumerate setup flags individually (only mentions `ait setup` as a basic bootstrap command). Per the plan's conditional, no README change.
  4. **Aidoc small fix in scope** — the aidoc is the canonical reference cross-linked from CLAUDE.md, and its enumeration was concretely wrong (4 launchers vs 6 actual). One-cell correctness fix; not a narrative rewrite.
- **Upstream defects identified:** None. (Note: there are pre-existing uncommitted changes in `.aitask-scripts/aitask_ide.sh`, `.aitask-scripts/lib/tui_switcher.py`, `.aitask-scripts/monitor/minimonitor_app.py`, `.aitask-scripts/monitor/monitor_app.py`, etc., visible at task pick time — but these are unrelated work-in-progress on the user's working tree, not defects diagnosed during this docs task. Left untouched.)
- **Notes for sibling tasks:**
  - t718_4 (manual verification) — when its checklist is built, include: "Open `https://aitasks.io/docs/installation/pypy/` (or the local `hugo serve` equivalent) and confirm the page renders, the env-var table formats, code blocks highlight, and the `Background` link to the GitHub-hosted aidoc resolves."
  - t718_5 (exploratory monitor/minimonitor evaluation) — when this completes, the "TUIs that don't use PyPy" section in `installation/pypy.md` MUST be amended to reflect the empirical result. The wording was deliberately scoped narrowly so this update is a one-paragraph swap, not a structural rewrite. Same for the CLAUDE.md "Monitor / minimonitor stay on CPython" sentence — update both in lockstep.
  - Future fast-path TUI additions (a 7th, 8th, …) MUST update three places in lockstep: CLAUDE.md TUI-Conventions bullet (the "six fast-path TUIs (…)" enumeration), the `pypy.md` Install section table, and the `aidocs/python_tui_performance.md` Option A row. The CLAUDE.md "Why" trailer (TUI Conventions, the existing rule) does not enumerate; only the env-var bullet does.
  - The cross-link from `installation/_index.md` to `pypy.md` uses `{{< relref "pypy" >}}` (relative to the same directory), while the cross-link from `commands/setup-install.md` uses `{{< relref "/docs/installation/pypy" >}}` (absolute path). Both are correct under Hugo/Docsy and both resolve in the verified `hugo build`.

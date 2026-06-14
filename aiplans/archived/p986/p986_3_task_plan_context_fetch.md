---
Task: t986_3_task_plan_context_fetch.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_1_*.md, aitasks/t986/t986_2_*.md, aitasks/t986/t986_4_*.md, aitasks/t986/t986_5_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: (none — implemented on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-14 18:46
---

# Plan: t986_3 — Task/plan context-fetch utility

## Context

Child of **t986 (shadow agent)**. For shadow use-case 2 — an `AskUserQuestion`
shown in the terminal **without** the source task/plan visible (observed example:
a session working `t635_3`) — the shadow must auto-fetch the relevant **task file
+ most-recent plan file** (and optionally sibling context) for the task the
followed agent is on. This child delivers a single thin helper that wraps the
existing canonical scanners (`aitask_query_files.sh`); it does **not** fork their
scan logic or build a parallel cache.

**Why now / dependency note:** the formal `depends: [t986_2]` is a *sibling
ordering* dependency only — t986_2 (phase-autodetection) is **Postponed** and the
parent design note + this task body both state t986_3 has **no true deps**. It is
implemented directly here. (See "Dependency cleanup" below.)

## Verification findings (verify-path re-check, 2026-06-14)

Re-checked the existing plan against the current codebase. One concrete bug and
two scope clarifications:

1. **BUG — child IDs break `task-file`.** `aitask_query_files.sh task-file <id>`
   (`.aitask-scripts/aitask_query_files.sh:129`) globs only **active parent**
   files (`$TASK_DIR/t<num>_*.md`) and `validate_num` rejects non-numeric IDs, so
   `task-file 635_3` would `die`. But the documented use-case-2 example is a
   **child** (`t635_3`). The helper MUST branch parent vs child:
   - child `N_M` → `child-file N M` (`:219`, emits `CHILD_FILE:`/`NOT_FOUND`)
   - parent `N`  → `task-file N` (`:129`, emits `TASK_FILE:`/`NOT_FOUND`)
   - either, on miss → `archived-task <id>` (`:144`, handles both `N` and `N_M`,
     emits `ARCHIVED_TASK:` / `ARCHIVED_TASK_ARCHIVE:` / `NOT_FOUND`).

2. **Plan resolution.** `plan-file <id>` (`:336`) already handles both parent
   (`p<N>_*.md`) and child (`p<N>/p<N>_<M>_*.md`) **active** plans. "Most recent
   when multiple" = take the lexicographically-last path (`ls`-sorted; `tail -1`).

3. **Archived plans are out of scope (deliberate).** `query_files` has **no**
   archived-plan subcommand. The primary use case is an *active* task (the
   followed agent is working it ⇒ its plan is in `aiplans/`). Archived/historical
   plan retrieval is the documented job of `aitask_explain_context.sh` (on-demand,
   deeper context) — this helper stays thin and emits `PLAN_FILE:NOT_FOUND` when
   no active plan exists. (Asymmetry with archived-task resolution is intentional
   and noted in the script header.)

## Deliverables

- **Create** `.aitask-scripts/aitask_shadow_context.sh` (executable, whitelisted).
- **Create** `tests/test_shadow_context.sh`.
- **Register** the helper in the helper-script whitelist (touchpoints 1/3/4/6/7)
  via `aitask_audit_wrappers.sh apply-helper-whitelist`.

## Interface (the stable contract)

```
aitask_shadow_context.sh [--siblings] <task_id>
```
- `<task_id>`: `N`, `tN`, `N_M`, or `tN_M` (optional `t` prefix stripped).
- `--siblings`: also emit sibling context (default **off**, to stay cheap).
- Malformed id → `die` with usage (non-zero). All resolution outcomes otherwise
  exit 0; consumers read the output lines, not the exit code (mirrors
  `query_files`).

**Output lines (stdout):**
```
TASK_FILE:<path>      # or TASK_FILE:NOT_FOUND
PLAN_FILE:<path>      # or PLAN_FILE:NOT_FOUND   (active; most-recent if multiple)
SIBLING:<path>        # zero or more; only with --siblings
```
Per-key `NOT_FOUND` (rather than a bare `NOT_FOUND`) so the shadow can tell which
artifact is missing.

## Implementation steps

1. **Header / conventions** — `#!/usr/bin/env bash`, `set -euo pipefail`; source
   `lib/terminal_compat.sh` then `lib/task_utils.sh` (for `die` + `TASK_DIR`
   defaults), mirroring `aitask_query_files.sh:30-38`. Do **not** `cd` to repo
   root (so the test can drive it with absolute `TASK_DIR`/`PLAN_DIR` overrides,
   exactly as `query_files` is driven). Resolve `QUERY="$SCRIPT_DIR/aitask_query_files.sh"`.

2. **Arg parse** — accept optional `--siblings` flag (any position) + one
   positional `<task_id>`. Strip optional `t` prefix; classify as child (`^[0-9]+_[0-9]+$`)
   or parent (`^[0-9]+$`); else `die`. For a child, `parent="${id%_*}"`.

3. **Resolve task file** (delegate to `query_files`; env vars inherited by the
   subprocess):
   - child → `child-file <parent> <child>`; if `CHILD_FILE:` use it, else
     `archived-task <parent>_<child>`.
   - parent → `task-file <num>`; if `TASK_FILE:` use it, else `archived-task <num>`.
   - From the chosen line, strip the `*:` prefix to the raw path. Emit
     `TASK_FILE:<path>` or `TASK_FILE:NOT_FOUND`.

4. **Resolve most-recent plan** — `plan-file <id>`. If output starts with
   `PLAN_FILE:`, strip the prefix and take the last line
   (`printf '%s\n' "$rest" | tail -n1`) as the most-recent path; emit
   `PLAN_FILE:<path>`. Otherwise emit `PLAN_FILE:NOT_FOUND`.

5. **Optional siblings** (only when `--siblings`) — `sibling-context <parent>`
   (for a parent id, `<parent>` is the id itself). For each output line that
   isn't `NO_CONTEXT`, strip the `query_files` sub-type prefix
   (`ARCHIVED_PLAN:`/`ARCHIVED_TASK:`/`PENDING_SIBLING:`/`PENDING_PLAN:`) and emit
   `SIBLING:<path>`.

6. **Thin-orchestrator guard** — no parallel cache, no archived-plan globbing, no
   `aitask_explain_context.sh` invocation (that is the shadow skill's on-demand
   deeper path, per the parent task design). `chmod +x` the script.

7. **Register in whitelist** — run
   `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_shadow_context.sh`,
   then confirm with `audit-helper-whitelist aitask_shadow_context.sh` (expect no
   `MISSING:` lines). This writes touchpoints 1 (`.claude/settings.local.json`,
   gitignored), 3 (`.codex/rules/default.rules`), 4
   (`seed/claude_settings.local.json`), 6 (`seed/codex_rules.default.rules`), 7
   (`seed/opencode_config.seed.json`). No test currently runs the audit, so this
   is pre-wiring so the t986_4 shadow skill can call the helper without a
   permission prompt.

8. **Test** `tests/test_shadow_context.sh` — mirror `tests/test_query.sh`
   structure: `mktemp -d` mock repo, `source tests/lib/asserts.sh`, export
   `TASK_DIR/PLAN_DIR/ARCHIVED_DIR/ARCHIVED_PLAN_DIR` at mock paths, invoke
   `$PROJECT_DIR/.aitask-scripts/aitask_shadow_context.sh`. Cases:
   - **active child** (`986_3`): `TASK_FILE:` resolves the child file; `PLAN_FILE:`
     resolves the child plan. (Guards the bug in finding #1.)
   - **active parent** (`16`): correct `TASK_FILE:`/`PLAN_FILE:`.
   - **most-recent plan**: ≥2 plans matching a child glob → last (lex) is chosen.
   - **archived task fallback**: active miss → `ARCHIVED_TASK:` path returned as
     `TASK_FILE:`.
   - **missing**: unknown id → `TASK_FILE:NOT_FOUND` and `PLAN_FILE:NOT_FOUND`.
   - **--siblings**: emits ≥1 `SIBLING:` line; absent without the flag.
   - **`t`-prefix** accepted (`t986_3` == `986_3`).

## Dependency cleanup (post-approval, Step 7 of workflow)

t986_2 is `Postponed` and t986_3 has no true dependency on it. Leaving
`depends: [t986_2]` would mark t986_3 **Blocked** in `ait ls`. As a small
frontmatter cleanup, clear the stale dep at implementation time:
`./.aitask-scripts/aitask_update.sh --batch 986_3 --deps ""` (committed via
`./ait git`). This is recorded here so it is visible/approvable, not done
silently.

## Verification

- `bash tests/test_shadow_context.sh` — all cases above PASS.
- `shellcheck .aitask-scripts/aitask_shadow_context.sh` — clean.
- `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_shadow_context.sh`
  emits **no** `MISSING:` lines.
- Smoke test against the live repo: `aitask_shadow_context.sh 986_3` →
  `TASK_FILE:aitasks/t986/t986_3_…` + `PLAN_FILE:aiplans/p986/p986_3_…`.

## Risk

### Code-health risk: low
- New isolated script + test; the only edits to existing files are
  **additive, tool-generated** whitelist lines (touchpoints 1/3/4/6/7) inserted
  by `aitask_audit_wrappers.sh`. No existing code path is modified. · severity: low · → mitigation: None
- Blast radius is one new helper consumed by a not-yet-built skill (t986_4); no
  current caller can regress. · severity: low · → mitigation: None

### Goal-achievement risk: low
- Core risk (child-id resolution) was found and designed out in finding #1; the
  approach reuses verified `query_files` subcommands. · severity: low · → mitigation: None
- Archived-plan retrieval is intentionally out of scope (deferred to
  `aitask_explain_context.sh`); acceptable because the driving use case is an
  active task. · severity: low · → mitigation: None

No mitigations needed (`risk_mitigations_planned = false`).

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9. Implemented on the
current branch (no worktree), so the merge sub-step is a no-op; archive via
`./.aitask-scripts/aitask_archive.sh 986_3`.

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/aitask_shadow_context.sh`
  (`[--siblings] <task_id>` → `TASK_FILE:` / `PLAN_FILE:` / `SIBLING:` lines), a
  thin orchestrator over `aitask_query_files.sh`. Created
  `tests/test_shadow_context.sh` (28 assertions, all pass). Registered the helper
  in all 5 whitelist touchpoints via `aitask_audit_wrappers.sh
  apply-helper-whitelist`. Cleared the stale `depends: [t986_2]`.
- **Deviations from plan:** None of substance — implemented exactly as the
  verified plan. The plan was authored on the **verify path** specifically to fix
  the child-ID resolution bug (the original task-body plan step 1 said
  `task-file <id>`, which `die`s on child IDs); the helper branches
  `child-file`/`task-file`/`archived-task` accordingly.
- **Issues encountered:** `shellcheck` emits SC1091 ("not following sourced file")
  for the two `source` lines — this is **info-level** and identical to the
  baseline on `aitask_query_files.sh`; clean at `--severity=warning`. Accepted as
  the project norm (no `.shellcheckrc`).
- **Key decisions:**
  - **Most-recent plan via `tail -1`:** `plan-file` emits `PLAN_FILE:$files` once
    even when its `ls` glob matches multiple files (only the first line carries
    the prefix). The helper strips the prefix and takes the last line
    (lexicographically newest). Single-plan-per-task is the norm, so this is just
    defensive; not treated as a `query_files` defect (multi-match is outside that
    subcommand's documented one-path contract).
  - **Archived plans deliberately out of scope:** `query_files` has no
    archived-plan subcommand; the helper resolves the active plan only and emits
    `PLAN_FILE:NOT_FOUND` for archived tasks. Deeper/historical plan retrieval is
    the documented job of `aitask_explain_context.sh` (on-demand), per the parent
    t986 design. Archived **task** files ARE resolved (fallback), so an archived
    task can yield `TASK_FILE:<path>` + `PLAN_FILE:NOT_FOUND`.
  - **Per-key `NOT_FOUND`** (`TASK_FILE:NOT_FOUND` / `PLAN_FILE:NOT_FOUND`) rather
    than a bare `NOT_FOUND`, so the shadow can tell which artifact is missing.
  - **Sibling lines** strip the `query_files` sub-type prefix
    (`ARCHIVED_PLAN:`/`PENDING_SIBLING:`/…) to a uniform `SIBLING:<path>`.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t986_4 (shadow skill)** is the consumer: call
    `./.aitask-scripts/aitask_shadow_context.sh <id>` (the followed agent's task
    id, parent or child) to fetch task + most-recent active plan; add `--siblings`
    for sibling context. The helper is already whitelisted, so no permission
    prompt. For deeper/historical context the skill should call
    `aitask_explain_context.sh` itself (the helper intentionally does not).
  - The shadow skill dir (e.g. `.claude/skills/shadow/`) is **not** scanned by
    `aitask_audit_wrappers.sh cmd_discover_helpers` (it scans `aitask-*`,
    `task-workflow`, `user-file-select`, `ait-git`). Registration here was done by
    explicit helper name, so it is covered; but if a future audit-driven check is
    added, t986_4/t986_5 may need to extend `cmd_discover_helpers` to include the
    shadow skill tree.
  - Cross-agent: helper is agent-agnostic; the Codex/OpenCode whitelist
    touchpoints (3/6/7) are already populated by this task.

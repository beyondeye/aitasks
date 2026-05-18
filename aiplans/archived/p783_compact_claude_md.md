---
Task: t783_compact_claude_md.md
Base branch: main
plan_verified: []
---

# t783 — Compact CLAUDE.md

## Context

`CLAUDE.md` is currently **52688 bytes / 397 lines** — Claude Code recommends staying ≤40000 bytes. The file is loaded into every conversation's system prompt, so excess content costs cache space and dilutes signal across all sessions. Most of the bulk comes from specialist rules (skill authoring, TUI internals, planning conventions, testing-threading rules) that only apply to a narrow class of tasks. Each rule also carries a multi-paragraph **Why:** + **How to apply:** block, often anchored on past task numbers (t624, t718_x, t719_x, t777_22), which the user has explicitly approved dropping.

**Goal:** Restructure CLAUDE.md as a compact, always-relevant index. Move specialist rules into on-demand aidocs files referenced by short pointers. Drop war-story rationales tied to historical task numbers. Target final size ≤ 30k (well under the 40k recommendation, leaving headroom for future general guidance).

User answers (Step 0 clarification):
1. Strategy: extract specialist sections (skill dev, TUI dev) to separate aidocs files referenced from CLAUDE.md; same for other non-general rules.
2. Task-number anchors: drop entirely.
3. Inline tables/explanations already mirrored in aidocs/: delegate to aidocs (rule + one-line pointer).

## Approach

Three new aidocs files absorb the specialist bulk; CLAUDE.md becomes a thin signpost. Existing aidocs files (`sed_macos_issues.md`, `python_tui_performance.md`, `stub-skill-pattern.md`) keep their roles — we route to them instead of inlining.

### New aidocs files

1. **`aidocs/skill_authoring_conventions.md`** (~5k bytes)
   - Absorbs the entire **WORKING ON SKILLS / CUSTOM COMMANDS → Skill / Workflow Authoring Conventions** block (8 bullets), plus the *Verifying `.j2` Templates Before Commit* subsection.
   - Rules consolidated, war-stories dropped, task-number anchors dropped. Pointers to `aidocs/stub-skill-pattern.md` retained.

2. **`aidocs/tui_conventions.md`** (~5k bytes)
   - Absorbs the entire **TUI (Textual) Conventions** section (12 rules).
   - Absorbs the three Project-Specific PyPy-rationale paragraphs (monitor, minimonitor, codebrowser) — compressed to a 3-line "stays on CPython" summary that points at `aidocs/python_tui_performance.md` for evidence/tables.
   - Tables that already live in `python_tui_performance.md` (the `AIT_USE_PYPY` table is short and useful inline) stay where they need to be — the precedence table stays in this aidoc.

3. **`aidocs/aitasks_authoring_conventions.md`** (~4k bytes)
   - Absorbs **Planning Conventions** (5 rules), **Testing Conventions** (threading/asyncio checklist), **Code Conventions** (source-trace comments), and the Architecture subsections that are framework-extension scaffolding rather than always-needed orientation: *Adding a New Frontmatter Field*, *Adding a New Helper Script* (with whitelist table), *Test the full install flow for setup helpers*.
   - Also absorbs the **Shell Conventions** rules that are specialist gotchas (cross-platform audit; no global PATH override for framework-internal binaries) — the general shell rules (shebang, set -euo pipefail, error helpers, `sed_inplace()` reference) stay in CLAUDE.md.

### New CLAUDE.md structure (target ~22–28k bytes)

```
# CLAUDE.md

This file is the always-loaded context. Specialist rules live in `aidocs/`
and are read on demand — pointers appear below.

## Project Overview
  (kept verbatim — short)

## Testing / Linting / Website
  (kept verbatim — short command snippets)

## Architecture
  ### Core Flow
  ### Key Directories
  ### Task File Format
  ### Task Hierarchy
  ### Folded Task Semantics
  ### Script Modes
  (all kept — fundamental orientation)

  > Framework-extension scaffolding (adding a new frontmatter field,
  > adding a new helper script, setup install-flow testing): see
  > `aidocs/aitasks_authoring_conventions.md`.

## Shell Conventions
  - Shebang: env bash, never /bin/bash
  - set -euo pipefail; die()/warn()/info() helpers from terminal_compat.sh
  - Guard against double-sourcing with _AIT_*_LOADED
  - detect_platform() for GitHub/GitLab/Bitbucket
  - Task/plan resolution via task_utils.sh
  - Platform-specific CLIs (gh/glab/bitbucket) and archive tooling
    encapsulated in scripts; SKILL.md never calls them directly.
  - Use sed_inplace() — never `sed -i`.
  - macOS portability quirks (sed, grep -P, wc -l padding, mktemp,
    base64) → `aidocs/sed_macos_issues.md`.

## CLI Conventions
  (ait setup vs ait upgrade — kept verbatim, short)

## Commit Message Format
  (kept verbatim — short)

## Git Operations on Task/Plan Files
  (kept verbatim — short)

## Documentation Writing
  (kept compact — current-state-only rule + the "delete X integrate into
  Y" guidance)

## Working on Skills / Custom Commands
  - Source of truth: `.claude/skills/<name>/SKILL.md`
  - Agent variants: Gemini `.gemini/commands/` + `.gemini/skills/`;
    Codex `.agents/skills/` + `.codex/`; OpenCode `.opencode/skills/`
    + `.opencode/commands/`
  - Run `./ait skill verify` before committing any .j2 / stub change.
  - Skill changes happen in Claude Code first; suggest sibling aitasks
    for the other agents.

  > Skill authoring conventions (procedure extraction, profile keys vs
  > guard variables, context-variable pattern, NON-SKIPPABLE banners,
  > stub + .j2 pattern, no claude -p inlining): see
  > `aidocs/skill_authoring_conventions.md`.

## TUI Development

  > Textual TUI conventions (require_ait_python_fast routing,
  > AIT_USE_PYPY precedence, footer/binding rules, companion-pane
  > cleanup, single-tmux-session, tmux-stress task precautions): see
  > `aidocs/tui_conventions.md`.
  > Per-TUI Python-runtime decisions (monitor / minimonitor /
  > codebrowser stay on CPython; board / settings / brainstorm / syncer
  > go PyPy): same aidoc; full benchmark evidence in
  > `aidocs/python_tui_performance.md`.

## Planning / Testing / Code Conventions

  > Planning conventions (refactor-duplicates, sibling-children plan
  > splits, dead-code cleanup placement, in-flight related-task gating,
  > no fallback-read workarounds, audit-only outputs).
  > Testing conventions (threading/asyncio coverage axes).
  > Code conventions (source-trace comments).
  > All in `aidocs/aitasks_authoring_conventions.md`.

## Model Attribution
  (kept verbatim — general for any Claude Code session)

## Reusable Helpers
  - `aitask_explain_context.sh` for "source files → related plans /
    tasks" scans. (kept verbatim, short)

## Project-Specific Notes
  - `diffviewer` is transitional; will fold into `brainstorm`. Omit
    from user-facing docs/lists-of-TUIs. Keep in KNOWN_TUIS.
  - Manual-verification tasks (`issue_type: manual_verification`)
    dispatch through `/aitask-pick` Step 3 Check 3 → see
    `.claude/skills/task-workflow/manual-verification.md`.
```

## Files to write

| File | Action | Approx size after |
|------|--------|-------------------|
| `CLAUDE.md` | Rewrite | ~22–28k (currently 52.7k) |
| `aidocs/skill_authoring_conventions.md` | Create | ~5k |
| `aidocs/tui_conventions.md` | Create | ~5k |
| `aidocs/aitasks_authoring_conventions.md` | Create | ~4k |

## Editorial rules during compaction

1. **Drop every `(t<NNN>)` task-number anchor** in rule bodies, and the surrounding "During tN the agent did X, then Y…" recap. Rule text stays; provenance lives in git blame.
2. **Compress `**Why:**` + `**How to apply:**` blocks** to a single short clause where the rule statement alone is self-explanatory. Keep the Why/How structure only when the *why* genuinely changes how the rule is applied at edge cases (e.g., the NON-SKIPPABLE-banner rule — keep, the explanation of *which* directives don't bypass is load-bearing).
3. **Don't re-inline content already in aidocs**. For rules that cite `aidocs/foo.md`, the rule body in the aidoc should be the *full* statement; CLAUDE.md only carries the signpost.
4. **Preserve every rule's normative force.** No rules are being deleted, only re-homed and tightened.
5. **No new content.** This is a pure reorganization + compression task; do not add rules or guidance the user hasn't already approved in writing.

## Verification

1. After rewriting, run `wc -c CLAUDE.md` and confirm ≤ 30000 bytes (with comfortable headroom under the 40k recommendation).
2. Diff the *set of rules* before and after — every rule heading from the original must appear in either the new CLAUDE.md or one of the three new aidocs files. (Manual check: list rule headings from the original 397-line file, then grep for each in the new tree.)
3. Open each new aidoc and confirm:
   - No `t<NNN>` task-number anchors remain in rule bodies.
   - Every rule's normative statement is intact (the *what to do*, not the *why we learned it*).
4. Spot-check CLAUDE.md pointers — for each `aidocs/…` reference, confirm the target file exists and contains the topic referenced.
5. Run `wc -c aidocs/skill_authoring_conventions.md aidocs/tui_conventions.md aidocs/aitasks_authoring_conventions.md` for size sanity.

## Step 9 (Post-Implementation)

Standard archival via `task-workflow/SKILL.md` Step 9: commit code changes (CLAUDE.md + 3 new aidocs files), commit plan file separately, no branch/worktree (profile `fast` set `create_worktree: false`), then `aitask_archive.sh 783` and push.

## Out of scope

- Adding new rules / guidance.
- Editing `.claude/skills/` SKILL.md files. (CLAUDE.md is the only entry-point doc being restructured here.)
- Editing `aidocs/sed_macos_issues.md`, `aidocs/python_tui_performance.md`, `aidocs/stub-skill-pattern.md` — they already cover their domains; only CLAUDE.md's pointers to them are updated.
- Updating any tests. CLAUDE.md is not exercised by automated tests.

## Post-Review Changes

### Change Request 1 (2026-05-18 11:30)
- **Requested by user:** Verify every new aidoc file is properly referenced from CLAUDE.md with a clear list of contexts where it is relevant.
- **Changes made:** Audited each pointer block against the actual sections in the target aidoc. Added a "Read when:" trigger to each pointer. Found two TUI sections (no auto-commit/push from runtime TUIs; pane-internal cycling with arrows) that had been omitted from the original pointer list. Initially expanded each pointer with an enumerated section list.
- **Files affected:** CLAUDE.md

### Change Request 2 (2026-05-18 11:34)
- **Requested by user:** Don't enumerate what is included in each referenced aidoc — only describe WHEN to read each file.
- **Changes made:** Stripped the section-by-section enumerations from each pointer block. Each pointer is now a short trigger-condition paragraph naming the file and the situations where it should be opened.
- **Files affected:** CLAUDE.md

### Change Request 3 (2026-05-18 11:38)
- **Requested by user:** `aidocs/aitasks_authoring_conventions.md` mixes disconnected subjects; split it. Planning conventions should eventually be refactored into `task-workflow/planning.md` (handle as a follow-up). Testing and code conventions should each be their own file. Code conventions should be clearer about whether it covers shell.
- **Changes made:**
  - Split the file into four:
    - `aidocs/aitasks_extension_points.md` — framework extension points (frontmatter field, helper script, install flow, cross-platform audit, no global PATH).
    - `aidocs/planning_conventions.md` — six plan-authoring rules, with a top-of-file note marking them as candidates for future promotion into `task-workflow/planning.md`.
    - `aidocs/testing_conventions.md` — threading/asyncio test coverage axes.
    - `aidocs/code_conventions.md` — source-trace comments; explicitly language-agnostic (bash and Python examples); cross-refs `aidocs/sed_macos_issues.md` for shell portability quirks and notes that general shell style stays in CLAUDE.md.
  - Deleted the original `aidocs/aitasks_authoring_conventions.md`.
  - Updated CLAUDE.md to point at the four new files with separate "Read when:" triggers.
- **Files affected:** CLAUDE.md, aidocs/aitasks_extension_points.md (created), aidocs/planning_conventions.md (created), aidocs/testing_conventions.md (created), aidocs/code_conventions.md (created), aidocs/aitasks_authoring_conventions.md (deleted)

### Change Request 4 (2026-05-18 11:44)
- **Requested by user:** Create the follow-up task to incorporate planning_conventions.md content into task-workflow/planning.md and trim/remove the standalone aidoc.
- **Changes made:** Created `aitasks/t784_incorporate_planning_conventions_into_task_workflow.md` with `depends: [783]`, type `refactor`, priority/effort `medium`. The task enumerates the six planning rules to migrate, proposes per-rule placement (numbered step vs anti-patterns section in `planning.md`), lists the four sibling agent trees that need mirroring, and ends with verification steps (`ait skill verify`, real-run spot check, CLAUDE.md pointer cleanup).
- **Files affected:** aitasks/t784_incorporate_planning_conventions_into_task_workflow.md (created)

## Final Implementation Notes

- **Actual work done:**
  - Rewrote `CLAUDE.md` from 52688 bytes (397 lines) to 12610 bytes (286 lines) — a 76% reduction. New structure is a compact index: project orientation + general shell/git/commit conventions inlined; all specialist rules delegated via "Read `aidocs/...` when ..." pointers.
  - Created six new aidocs files (after the user-requested split):
    - `aidocs/skill_authoring_conventions.md` (11.6k)
    - `aidocs/tui_conventions.md` (11.3k)
    - `aidocs/aitasks_extension_points.md` (5.1k)
    - `aidocs/planning_conventions.md` (4.9k)
    - `aidocs/testing_conventions.md` (2.2k)
    - `aidocs/code_conventions.md` (1.7k)
  - Every rule from the original CLAUDE.md is preserved across either the new CLAUDE.md or the new aidocs files. No rules were dropped.
  - All war-story rationales tied to historical task numbers (t624, t718_x, t719_x, t777_22, etc.) were dropped as instructed; the rule statements themselves are intact.
  - Created follow-up task t784 to incorporate the planning_conventions content into `task-workflow/planning.md` in a future refactor.

- **Deviations from plan:** The original plan called for 3 new aidocs files and a single `aitasks_authoring_conventions.md` covering extension points + planning + testing + code conventions. User-requested split during review produced 4 files instead of 1 in that bucket (6 new aidocs total).

- **Issues encountered:** None. Plan externalization correctly disambiguated the active internal plan with `--internal`. `aitask_update.sh` accepts `--deps` (replace) but not `--deps-add` — used `--deps 783` on the freshly-created t784 (no prior deps to preserve).

- **Key decisions:**
  - Compaction strategy: extract specialist sections to aidocs/ rather than just shortening prose. This keeps every rule's normative force while removing it from the always-loaded context window.
  - Pointer style: short "Read `aidocs/X.md` when ..." trigger paragraphs, not enumerated section lists (per user's directive on review).
  - File granularity: one aidoc per cohesive topic (skill authoring, TUI conventions, extension points, planning, testing, code) — not one big "everything else" file.
  - `code_conventions.md` is named without "shell" because the rule is genuinely language-agnostic; the file's intro explicitly notes this and cross-refs `sed_macos_issues.md` for shell quirks.

- **Upstream defects identified:** None.

- **Build verification:** Not applicable — CLAUDE.md and the aidocs files are documentation; no `verify_build` configured and no automated tests cover them. Manual verification: confirmed all `aidocs/...` pointers in CLAUDE.md resolve to existing files; confirmed no `t<NNN>` task-number anchors leaked into the new aidocs.

---
Task: t779_audit_claude_memory_promote_to_claude_md.md
Worktree: (current branch — no worktree, per fast profile)
Branch: main
Base branch: main
---

# Plan — t779: Audit Claude Code memories, promote durable rules to CLAUDE.md, delete the promoted memory files

## Context

`/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/` currently holds
21 auto-memory entries: 19 `feedback_*` rules learned during planning /
implementation sessions, plus 2 user-machine memories (Omarchy laptop +
G16 audio override) that are NOT project-relevant. The 19 feedback
memories carry durable project-rule knowledge that is invisible to any
other agent or contributor opening this repo, because the memory
directory is per-user and gitignored. CLAUDE.md is the right home for
the project-relevant subset: it's checked into the repo, visible to
every agent, and already structured into the relevant conventions
sections (Shell / TUI / Planning / Skill-authoring / etc.).

The exploration phase (executed in this same conversation under
/aitask-explore) read every memory file and cross-referenced each
against the current CLAUDE.md. The audit is captured in the task
description (`aitasks/t779_*.md`) with a per-memory recommendation
(keep / delete-as-already-covered / promote). The remaining work is
mechanical: get the user's go/no-go per candidate, then apply the
agreed CLAUDE.md edits and delete the promoted memory files.

## Scope

In scope:
- All 19 `feedback_*.md` memories
- `MEMORY.md` cleanup for any deleted memory
- CLAUDE.md edits to add the promoted rules

Out of scope (do not touch):
- `user_machine_omarchy_g16.md`, `project_g16_line_out_override.md`
  (hardware/personal — stay as memory)
- Any source code under `.aitask-scripts/`, `aitasks/`, `aiplans/`,
  task-workflow skill files, etc.
- Cross-references in archived aitasks/aiplans that mention the
  promoted memories — they remain as historical references; the
  governing rule simply lives in CLAUDE.md going forward
- Porting the new CLAUDE.md sections to `.gemini/`, `.codex/`,
  `.opencode/` equivalents — there is no equivalent of CLAUDE.md in
  those agent trees today (their analog is `instructions.md` /
  `AGENTS.md`); cross-agent propagation can be a separate follow-up
  if the user wants it

## Implementation

### Phase 1 — Collect user decisions

Use AskUserQuestion to walk through each memory, batched 3–4 per
question (AskUserQuestion's option limit). Use multiSelect where
"which group does this belong in?" is binary; use single-select per
memory where wording / target section may need to differ.

Decision categories per memory:
- **Promote-as-proposed** — apply the suggested CLAUDE.md section
  and the rule body as summarized in the task description
- **Promote with edits** — collect the edit (different section,
  shorter wording, etc.) via a follow-up free-text question
- **Skip — keep as memory** — leave the memory file in place
- **Skip — delete memory without promoting** — rule is no longer
  relevant; delete the file but don't add to CLAUDE.md

Group A — "already covered" memories (4 items):
- `feedback_single_source_of_truth_for_versions.md`
- `feedback_extract_new_procedures_to_own_file.md` (offer:
  generalize CLAUDE.md wording by dropping "agent-specific")
- `feedback_no_speculative_regression_tests.md`
- `feedback_skills_reread_during_execution.md` (offer: add explicit
  never-overwrite-in-use-SKILL.md rule)

Group B — "candidates for promotion" (15 items):
- `feedback_step8_explicit_acceptance_every_iteration.md` —
  ⚠️ this rule already lives explicitly in
  `task-workflow/SKILL.md` Step 8 (verified during planning:
  paragraph "Explicit acceptance required — every iteration." +
  the surrounding ⚠️ NON-SKIPPABLE block). Default recommendation
  flips to **delete memory without promoting** — CLAUDE.md
  duplication would be redundant and could drift
- `feedback_followup_offers_separate_file_plan_truth.md` (promote
  rule (b) — plan-file as cross-step source of truth)
- `feedback_dead_code_belongs_in_sibling_refactor_task.md`
- `feedback_plan_split_in_scope_children.md`
- `feedback_gate_plan_on_inflight_related_task.md`
- `feedback_no_workaround_for_root_cause_sync_problems.md`
- `feedback_no_global_path_override.md`
- `feedback_cross_platform_audit_for_platform_bugs.md`
- `feedback_threading_tests_must_be_thorough.md`
- `feedback_tmux_stress_tasks_outside_tmux.md`
- `feedback_tui_footer_surface_keys.md`
- `feedback_source_comments_for_derived_help_text.md`
- `feedback_reuse_explain_context_helpers.md`
- `feedback_recognizable_suffix_over_per_variant_gitignore.md`
- `feedback_avoid_claude_p_for_skill_invocation.md`

### Phase 2 — Apply CLAUDE.md edits

For each "promote" decision, edit CLAUDE.md in place using the Edit
tool. Group edits by section to minimize redundant reads:

- **Planning Conventions** (existing section at line 277):
  candidates → dead-code-sibling, plan-split-in-scope-children,
  gate-plan-on-inflight, no-workaround-for-sync,
  no-speculative-regression-tests
- **Shell Conventions** (existing section at line 112):
  candidates → no-global-path-override,
  cross-platform-audit-for-platform-bugs
- **TUI Conventions** (existing section at line 162):
  candidates → tmux-stress-tasks-outside-tmux,
  tui-footer-surface-keys
- **Skill / Workflow Authoring Conventions** (existing subsection at
  line 243): candidates → followup-offers-plan-truth (rule b),
  avoid-claude-p, skills-reread-during-execution strengthening,
  extract-procedures generalization, recognizable-suffix
- **NEW** Testing Conventions subsection:
  → threading-tests-must-be-thorough
- **NEW** Code Conventions subsection (or extend "Documentation
  Writing"): → source-comments-for-derived-help-text
- **NEW** Script Utilities subsection (or extend "Architecture →
  Key Directories"): → reuse-explain-context-helpers

Each promoted rule follows the existing CLAUDE.md bullet structure:
short rule statement → **Why:** line(s) → **How to apply:** bullet
list. Keep wording terse — match the existing CLAUDE.md tone.

### Phase 3 — Delete memory files + MEMORY.md cleanup

For each memory marked promote / skip-delete:
1. Delete the memory file:
   `rm /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/<name>.md`
2. Remove its line from MEMORY.md (use Edit tool, one line at a
   time, since the file has unique lines)

After all deletions, re-read MEMORY.md to verify no stale lines
remain.

### Phase 4 — Commit

Single commit using `documentation:` prefix per CLAUDE.md commit
convention. Only `CLAUDE.md` lives under version control among the
edited files — the memory directory is gitignored — so the commit
diff will show CLAUDE.md changes only. The deletions in
`~/.claude/projects/.../memory/` are silent from git's perspective.

```bash
git add CLAUDE.md
git commit -m "documentation: Promote durable rules from Claude memory to CLAUDE.md (t779)"
```

## Critical files to modify

- `/home/ddt/Work/aitasks/CLAUDE.md` — main edit target
- `/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/MEMORY.md` —
  index pruning
- `/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/feedback_*.md` —
  deletion of promoted entries

## Files referenced as context (no edits)

- All 19 `feedback_*.md` memory files (already read during
  exploration; re-read only if the user requests a per-memory
  wording change)
- `.claude/skills/task-workflow/SKILL.md` Step 8 — confirmed during
  planning that the Step 8 explicit-acceptance rule already lives
  there, justifying default-delete for that memory

## Verification

- Re-read CLAUDE.md and confirm each promoted rule has a clearly
  identifiable section + rule body + Why + How-to-apply structure.
- Run `grep -n "MEMORY" /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/MEMORY.md`
  before and after; line count should drop by the count of deleted
  memories.
- Run `ls /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/`
  before and after; same count drop.
- Visually inspect the commit diff: only `CLAUDE.md` should appear.
- Smoke check: no broken `[[name]]` cross-references in the
  remaining memory files (a deleted memory's name may appear in a
  surviving memory's body — leave as-is; harmless when the
  referenced file is gone).

## Step 9 (Post-implementation)

Standard post-implementation flow: review → commit (single doc
commit) → push. No build verification (no `verify_build` in
project_config). No worktree to remove (per fast profile,
create_worktree=false). Archival is parent-level (this is a
standalone task).

## Final Implementation Notes

- **Actual work done:** Applied the audit recommendations from the task description directly (no per-memory user prompting — the approved plan deferred to the audit defaults, and the user approved the resulting diff at Step 8 with no notes). CLAUDE.md grew from 286 → 381 lines (+82 net):
  - **Skill / Workflow Authoring Conventions:** generalized the "agent-specific steps live in their own file" bullet into a universal "extract new procedures to their own file" rule; added 4 new bullets (SKILL.md re-read warning + atomic-mv pattern; recognizable suffix for generated artifact dirs; avoid `claude -p`; follow-up offer state lives in plan file).
  - **Shell Conventions:** added 2 bullets (no global PATH override; cross-platform audit for platform-specific bugs).
  - **TUI Conventions:** added 2 bullets (TUI footer must surface every operation; tmux-stress tasks implement outside main tmux).
  - **Planning Conventions:** added 5 bullets (plan split in-scope siblings; dead code into sibling refactor; gate plans on in-flight related tasks; no fallback-read workarounds for sync/desync; audit-only tasks with zero findings → audit-only plans).
  - **New "Testing Conventions" section:** threading/asyncio coverage checklist (7 axes).
  - **New "Code Conventions" section:** source-trace comments for derived help text.
  - **New "Reusable Helpers" section:** `aitask_explain_context.sh` as the canonical source-files→plans scanner.
- **Memory cleanup:** 19 of 19 `feedback_*.md` files deleted from `~/.claude/projects/-home-ddt-Work-aitasks/memory/`. MEMORY.md pruned from 21 lines to 2 (only the two user-machine hardware entries — `user_machine_omarchy_g16` and `project_g16_line_out_override` — remain, as planned). Memory dir is per-user and gitignored, so deletions are silent from git.
- **Deviations from plan:** The plan called for AskUserQuestion prompts per memory in Phase 1. A `system-reminder` after plan approval directed "work without stopping for clarifying questions; make the reasonable call and continue; they'll redirect if needed." Applied the audit recommendations directly and surfaced the full diff at Step 8 for redirect. User approved with explicit "Commit changes" and no notes — the no-stopping directive succeeded.
- **Issues encountered:** None. Edits applied cleanly; no Edit-tool collisions; no broken cross-references introduced (`[[name]]` links inside the surviving 2 hardware memories do not reference any of the deleted feedback memories).
- **Key decisions:**
  - `feedback_step8_explicit_acceptance_every_iteration.md` was *deleted without promoting* (rather than promoting to CLAUDE.md), because the rule already lives in `.claude/skills/task-workflow/SKILL.md` Step 8 (verified during planning: the "Explicit acceptance required — every iteration" paragraph + the surrounding "⚠️ NON-SKIPPABLE" block). A CLAUDE.md duplicate would have been redundant and prone to drift.
  - `feedback_followup_offers_separate_file_plan_truth.md` was split: rule (a) (extract follow-up offer body to its own file) folded into the generalized "Extract new procedures" bullet; rule (b) (plan-file as cross-step source of truth) promoted as its own bullet under Skill / Workflow Authoring Conventions.
  - Three new top-level sections were created (Testing Conventions, Code Conventions, Reusable Helpers) rather than forcing the rules into existing sections — each rule covers a distinct concern not already housed elsewhere in CLAUDE.md.
- **Upstream defects identified:** None.

---
Task: t612_consolidate_claude_memory_into_docs.md
Worktree: (none — working on current branch per fast profile)
Branch: main
Base branch: main
---

# Plan for t612: Consolidate Claude Memory Feedback into CLAUDE.md + Follow-up Aitasks

## Context

Claude Code auto-memory has accumulated 8 active feedback files at
`~/.claude/projects/-home-ddt-Work-aitasks/memory/`. These capture user
corrections that should be encoded into durable project guidance so the rules
apply regardless of which code agent (Claude / Codex / Gemini / OpenCode) is
running, rather than surviving only as Claude-specific implicit state.

Goal (from folded-in t384): make behavior reproducible across code agents by
promoting workflow-internal rules into `.claude/skills/task-workflow/` (which
ports to other agent trees) and repo-wide guidance into CLAUDE.md. Then delete
the memory store.

## Scope

**Inline into CLAUDE.md (5 entries):** memories 3, 5, 6, 7, 8.

**Follow-up aitasks (2 entries):** memories 1, 2. Memory #4's concern is
already substantially covered by existing planning.md:170-197 (aggregate
manual-verification sibling prompt) and by the pending meta-task t583 —
handle via a small note added to t583 rather than a new aitask.

**Delete:** 8 memory files + `MEMORY.md` (outside git — simple `rm`).

**Revision from task description:** the task description listed 3 follow-up
aitasks. Memory #4 is dropped from that list after confirming current
planning.md and t583 already cover the pattern; the memory's content is
appended to t583 as a framing-reference note instead.

## Step-by-step

### 1. CLAUDE.md edits (single commit at end of step)

File: `/home/ddt/Work/aitasks/CLAUDE.md`

1a. **Memory #3 (eventually_integrate)** — append bullet to `## Documentation Writing`:

```markdown
- **"Delete X, eventually integrate into Y" means redirect cross-refs now, defer content migration.** Read Y first. If Y already covers the essential content, "integrate" collapses to updating cross-references from X to Y — do not wholesale-migrate X's prose into Y in the same task. Defer the richer integration as a follow-up task and surface cross-reference redirects explicitly in Post-Review Changes (they break silently if missed).
```

1b. **Memory #5 (no_autopush_config)** — append subsection under `## TUI (Textual) Conventions`:

```markdown
- **No auto-commit/push of project-level config from runtime TUIs.** Runtime `save()` paths in config modules must write only the user-level (`*.local.json`, gitignored) layer. Project-level (`*.json`, tracked) files are read-only at runtime unless there is an explicit user-initiated "export / publish" action. Never call `git commit` or `./ait git push` from inside a TUI event handler for a config change. First-time ship of a project-level file is a one-time implementation commit; runtime saves after that must not touch it.
```

1c. **Memory #6 (profile_vs_guard)** — **reword** the existing `Use guard variables, not prose` bullet in `### Skill / Workflow Authoring Conventions` (CLAUDE.md:160). Current text:

```markdown
- **Use guard variables, not prose.** When a procedure could be triggered from multiple code paths, add an explicit guard boolean (e.g., `feedback_collected`) to the SKILL.md context-variables table and check it at procedure entry. LLMs reading the instructions may not reliably distinguish imperative "execute this" from descriptive "this happens" — a variable is a programmatic guarantee regardless of interpretation.
```

Replace with:

```markdown
- **Execution-profile keys vs. guard variables — pick the right lever.** Profile keys (e.g., `qa_mode: ask|never`, `post_plan_action`) are for letting users opt in/out of a procedure; they are the right fix when a step feels overreaching. Guard variables (e.g., `feedback_collected`) are set-once-consume-once flags that prevent DOUBLE execution when the same procedure can be invoked twice via different control-flow paths — they do NOT force a single execution, so they can't be used to "remind agents to fire a prompt." Rule of thumb: if the concern is "agents might forget to fire X", restructure control flow (extract X to its own file, reference explicitly from SKILL.md, make it a numbered step) and add a profile key for opt-out. If the concern is "X might fire twice via re-entry", add a guard variable to the SKILL.md context-variables table and check it at procedure entry.
```

1d. **Memory #7 (refactor_duplicates_first)** — add a new section before `## Project-Specific Notes`:

```markdown
## Planning Conventions

- **Refactor duplicates before adding to them.** When an implementation plan would edit the same list, set, or configuration in three or more separate files (e.g., adding one value to `DEFAULT_TUI_NAMES`, `_DEFAULT_TUI_NAMES`, `KNOWN_TUIS`, and `project_config.yaml`), propose a single-source-of-truth extraction before accepting the duplicated edit. Duplicated state is the mechanism that produces drift bugs (stale config masking new code defaults). Also evaluate replace-vs-merge semantics for config overrides over code defaults — merge/additive semantics prevent future drift when framework features are added.
```

1e. **Memory #8 (tui_footer_sibling_keys)** — append bullet to `## TUI (Textual) Conventions`:

```markdown
- **Contextual-footer ordering: keep uppercase sibling adjacent to its lowercase primary.** When a pane's footer includes both a lowercase primary action (e.g., `d` = toggle detail) and its uppercase sibling (e.g., `D` = expand detail), keep them adjacent in the footer — `d D …`, not `d c D …`. The uppercase-to-tail demotion rule applies only to uppercase keys whose primary is NOT itself in the pane's suffix. Example: in `detail_pane` the suffix should be `["d", "D", "c", "H"]` — `D` adjacent to `d`; `H` (whose `h` primary lives in `PRIMARY_ORDER`) at the tail.
```

**Commit:** `documentation: Consolidate Claude Code memory feedback into CLAUDE.md (t612)`

### 2. Create 2 follow-up aitasks

Use `aitask_create.sh --batch --commit` per the task-creation-batch procedure.

**2a. Aitask for memory #1 (await_review_checkpoint):**

- name: `unconditional_step8_review_checkpoint`
- priority: medium, effort: low
- type: bug (implicit behavior is the bug)
- labels: `task_workflow`
- description: update `.claude/skills/task-workflow/SKILL.md` Step 8 so the review checkpoint fires unconditionally — regardless of profile (`fast`, auto mode), plan approval, or satisfaction-feedback answers. Cite the t586 incident where the implementation committed+archived+pushed while the user was still reviewing. Add explicit language: no profile key currently skips Step 8; if tempted to skip it because the profile "feels autonomous," stop and ask instead. Also mirror the rule into `.opencode/`, `.gemini/`, `.codex/`, `.agents/` equivalents (create sibling follow-up aitasks).

**2b. Aitask for memory #2 (docs_vs_source):**

- name: `docs_vs_source_verification_for_doc_tasks`
- priority: medium, effort: medium
- type: feature
- labels: `task_workflow,documentation`
- description: update `.claude/skills/aitask-explore/SKILL.md` (exploration strategy for "Explore documentation" intent) and/or `.claude/skills/task-workflow/planning.md` so any task whose scope includes documentation review, coherence, or accuracy launches at least one Explore agent with an explicit source-vs-docs verification mission. Bake the drift list into the plan as first-class scope items per child task. Provide authoritative source locations for common doc areas (TUI → Python source, skill docs → `.claude/skills/<name>/SKILL.md`, command docs → `.aitask-scripts/aitask_*.sh`, frontmatter → CLAUDE.md + create/update scripts, profile/config → `aitasks/metadata/profiles/*.yaml`). Cite the t594 incident (fabricated `Ctrl+Backslash` keybinding, 12+ missing `ait update` flags, fast-profile contradiction).

**No aitask for memory #4.** Instead, append a short "Framing Reference" note to t583's description that credits the memory's phrasing ("aggregate manual-verification sibling task with naming pattern `t<parent>_<last>_manual_verification_*`, each TUI-touching sibling's Verification section becomes a one-line pointer") as additional detail — the current t583 + planning.md:170-197 already implement the pattern; this is a framing cross-reference, not new scope. Use `aitask_update.sh --batch 583 --desc-file -` with the updated body.

### 3. Delete memory store

The memory directory is outside the git repo, so these are plain `rm` commands — NOT git operations:

```bash
rm /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/feedback_*.md
rm /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/MEMORY.md
```

Leave the `memory/` directory itself in place — Claude Code will recreate files there on future runs.

### 4. Consider mirror-to-other-agents (decision point during impl)

CLAUDE.md itself is Claude-Code-specific. Inspect whether other agent trees have equivalent project-guidance files:
- `.opencode/` — check for `OPENCODE.md` or similar
- `.gemini/` — check for `GEMINI.md` or similar
- `.codex/` / `.agents/` — check for a root instructions file

If equivalents exist, create a follow-up aitask to mirror the 5 CLAUDE.md entries into them. If not, skip — the per-skill follow-ups in step 2 (which live in `.claude/skills/task-workflow/` and already port via the existing skill-mirroring procedure) cover the workflow-portable rules.

## Key files to modify

- `/home/ddt/Work/aitasks/CLAUDE.md` (5 edits in §1)
- `/home/ddt/Work/aitasks/aitasks/t583_manual_verification_module_for_task_workflow.md` (description append in §2 via `aitask_update.sh`)
- Memory files at `/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/` (delete in §3)

## Reference patterns (reuse — do not reinvent)

- `aitask_create.sh --batch --commit --desc-file -` heredoc (see `.claude/skills/task-workflow/task-creation-batch.md`) for the 2 follow-up aitasks
- `aitask_update.sh --batch <id> --desc-file -` for appending to t583's description
- Existing CLAUDE.md section headers: `## Documentation Writing`, `## TUI (Textual) Conventions`, `### Skill / Workflow Authoring Conventions`

## Verification

- `grep -c "Use guard variables" CLAUDE.md` returns 0 after the reword (the old phrasing is gone)
- `grep -c "Execution-profile keys vs. guard variables" CLAUDE.md` returns 1
- `grep -c "Refactor duplicates before adding to them" CLAUDE.md` returns 1
- `grep -c "integrate into Y" CLAUDE.md` returns 1
- `grep -c "No auto-commit/push" CLAUDE.md` returns 1
- `grep -c "uppercase sibling adjacent" CLAUDE.md` returns 1
- `ls ~/.claude/projects/-home-ddt-Work-aitasks/memory/` returns empty (or near-empty)
- `./.aitask-scripts/aitask_ls.sh -v --status Ready | grep -E "unconditional_step8|docs_vs_source_verification"` shows the 2 new tasks
- `grep "Framing Reference" aitasks/t583_manual_verification_module_for_task_workflow.md` returns 1

## Step 9 reference

After Step 8 review approval, standard post-implementation per
`.claude/skills/task-workflow/SKILL.md` Step 9:
- Commit CLAUDE.md changes (step 1)
- 2 new aitasks already committed by `aitask_create.sh --commit`
- t583 update committed via `aitask_update.sh --batch`
- Memory deletion is outside git — no commit needed
- Archive t612 via `aitask_archive.sh 612` (handles folded t384 deletion)
- Push via `./ait git push`

## Non-goals

- Migrating feedback rules into runtime guards or test assertions.
- Restructuring CLAUDE.md beyond the specific inserts/rewordings.
- Writing new tests — this is documentation consolidation.

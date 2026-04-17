---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [claudeskills, documentation]
created_at: 2026-04-17 11:03
updated_at: 2026-04-17 11:03
---

## Context

The project's auto-memory directory
(`~/.claude/projects/-home-ddt-Work-aitasks/memory/`) has accumulated
13 memory files plus a stale index entry. The user prefers to keep
durable guidance in `CLAUDE.md` (visible, version-controlled,
shared via git) rather than in per-user, machine-local memory that
is invisible to other contributors and future Claude sessions on
different machines.

## Goal

Review every current memory file, decide which to keep, and migrate
the kept content to `CLAUDE.md`. Delete all memories at the end.
Only very special cases (e.g., genuinely per-user preferences that
should NOT be shared with the team) should stay as memories.

## Current memory inventory (as of 2026-04-17)

Located at `~/.claude/projects/-home-ddt-Work-aitasks/memory/`:

**Feedback (12 files on disk, 1 stale index entry):**
- `feedback_test_followup.md` — `/aitask-qa` replaces Step 8b
- `feedback_guard_variables.md` — guard variables over prose
- `feedback_folded_semantics.md` — folded = merged, not superseded
- `feedback_platform_commands.md` — encapsulate `gh`/`glab` in scripts
- `feedback_archive_encapsulation.md` — **stale index entry, file missing**
- `feedback_doc_forward_only.md` — docs describe current state only
- `feedback_debug_failing_path.md` — debug the actual failing command
- `feedback_confirm_dialog_transparency.md` — list every item's fate
- `feedback_agent_specific_procedures.md` — extract to procedure file
- `feedback_new_frontmatter_propagation.md` — touch 3 layers for new fields
- `feedback_textual_priority_bindings.md` — scope query_one to screen
- `feedback_tui_create_task_shortcut.md` — `n` is the create-task key
- `feedback_model_switch_mid_session.md` — check `/model` before system msg

**Project (1 file):**
- `project_diffviewer_brainstorm.md` — diffviewer is transitional

## Implementation Plan

### Step 1. Read every memory file
Read each `.md` file in the memory directory. Note the rule, the
"Why", and the "How to apply".

### Step 2. Classify each memory
Assign one of:
- **PROMOTE** — content is a durable team-wide convention → fold
  into a section of `CLAUDE.md` (existing or new subsection).
- **KEEP AS MEMORY** — genuinely per-user/per-machine preference
  not appropriate for the shared repo (should be rare — document
  why in the decision log).
- **DROP** — obsolete, situation-specific, or already codified
  elsewhere (e.g., in SKILL.md, in a skill's procedure file, or
  in existing CLAUDE.md content).

Produce a short decision log (one line per memory) in the plan file.

### Step 3. Organize `CLAUDE.md` additions
Group promoted content by theme. Candidate sections to add or
extend in `CLAUDE.md`:
- **Documentation conventions** (doc_forward_only,
  confirm_dialog_transparency)
- **Skill / workflow authoring conventions**
  (agent_specific_procedures, guard_variables, platform_commands,
  archive_encapsulation once its content is recovered from memory
  summary or git history)
- **Framework semantics** (folded_semantics)
- **TUI conventions** (tui_create_task_shortcut,
  textual_priority_bindings)
- **Task frontmatter conventions** (new_frontmatter_propagation)
- **Model attribution conventions** (model_switch_mid_session)
- **Debugging conventions** (debug_failing_path)
- **Project-specific notes** (diffviewer_brainstorm)

Fold `/aitask-qa` / Step 8b deprecation info into the existing
task-workflow section in `CLAUDE.md` if not already present.

For PROMOTE entries, rewrite each into CLAUDE.md's style: concise,
imperative, no "I" voice, no memory-format metadata (`name`,
`description`, `type`, `originSessionId`). Preserve the **Why** and
**How to apply** rationale inline when it's not self-evident.

### Step 4. Handle the stale `feedback_archive_encapsulation.md`
The file is missing but referenced in `MEMORY.md`. Either:
- Recover the intent from the one-line summary and promote it to
  CLAUDE.md (recommended), OR
- Drop the index reference silently.

### Step 5. Remove all memories
After `CLAUDE.md` is updated:
1. Delete every `.md` file in
   `~/.claude/projects/-home-ddt-Work-aitasks/memory/` EXCEPT
   `MEMORY.md` itself and any memories classified KEEP.
2. Rewrite `MEMORY.md` as an empty index (header only) OR as just
   the KEEP entries.
3. If KEEP set is empty, leave `MEMORY.md` with only the
   `# Memory Index` header so the auto-memory system still works
   without crashing.

### Step 6. Verify
- `CLAUDE.md` reads coherently — sections flow, no duplicate
  guidance, no memory-format residue.
- Diff review: confirm every PROMOTE rule has a home in CLAUDE.md.
- No broken MEMORY.md references.
- Display the final `ls ~/.claude/projects/-home-ddt-Work-aitasks/memory/`
  for the user to confirm.

### Step 7. Commit
Two separate commits per CLAUDE.md conventions:
- CLAUDE.md change: `documentation: Migrate persistent guidance
  from auto-memory to CLAUDE.md (t<N>)`
- (Optional) a follow-up commit if any skill SKILL.md changes are
  needed to align with the promoted rules.

Memory files live outside the repo, so their deletion is not a git
operation.

## Deliverables

- Updated `CLAUDE.md` with all durable guidance incorporated
- Decision log in the plan's Final Implementation Notes listing
  PROMOTE / KEEP / DROP per memory file
- Empty (or minimal) auto-memory directory

## Reference files for patterns

- `CLAUDE.md` (project root) — existing structure and tone
- `~/.claude/projects/-home-ddt-Work-aitasks/memory/MEMORY.md` —
  current index
- `~/.claude/projects/-home-ddt-Work-aitasks/memory/*.md` —
  source content to classify

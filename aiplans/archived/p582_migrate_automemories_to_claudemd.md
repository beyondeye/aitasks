---
Task: t582_migrate_automemories_to_claudemd.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
---

# Plan: Migrate auto-memories to CLAUDE.md

## Context

The project's auto-memory directory (`~/.claude/projects/-home-ddt-Work-aitasks/memory/`)
holds 12 feedback files + 1 project file + `MEMORY.md` index (plus one stale
index entry for a deleted file). The user wants durable, team-wide guidance
that currently lives in per-user memory to move into `CLAUDE.md` so it is
visible, version-controlled, and shared via git.

Only genuinely per-user/per-machine preferences should stay as memories.
Reviewing all 13 files, **none qualify** as per-user-only — every entry is a
durable team convention or project fact. So the expected outcome is a full
migration: CLAUDE.md gains several new sections, and the memory directory is
emptied.

## Decision log (PROMOTE / KEEP / DROP)

All 12 present files are PROMOTE. The missing `feedback_archive_encapsulation.md`
is reconstructed from its one-line summary (it generalizes the same pattern as
`feedback_platform_commands.md`).

| Memory | Classification | CLAUDE.md destination |
|---|---|---|
| `feedback_agent_specific_procedures.md` | PROMOTE | Skill / Workflow Authoring Conventions |
| `feedback_confirm_dialog_transparency.md` | PROMOTE | UI & Dialog Conventions |
| `feedback_debug_failing_path.md` | PROMOTE | Debugging Conventions |
| `feedback_doc_forward_only.md` | PROMOTE | Documentation Writing |
| `feedback_folded_semantics.md` | PROMOTE | Architecture → Task File Format note |
| `feedback_guard_variables.md` | PROMOTE | Skill / Workflow Authoring Conventions |
| `feedback_model_switch_mid_session.md` | PROMOTE | Model Attribution Conventions |
| `feedback_new_frontmatter_propagation.md` | PROMOTE | Architecture → Task File Format note |
| `feedback_platform_commands.md` | PROMOTE | Shell Conventions (new bullet) |
| `feedback_archive_encapsulation.md` (missing) | PROMOTE (reconstructed) | Shell Conventions (new bullet) |
| `feedback_test_followup.md` | PROMOTE | QA Workflow |
| `feedback_textual_priority_bindings.md` | PROMOTE | TUI (Textual) Conventions |
| `feedback_tui_create_task_shortcut.md` | PROMOTE | TUI (Textual) Conventions |
| `project_diffviewer_brainstorm.md` | PROMOTE | Project-Specific Notes |

Nothing is DROP (each item is a durable rule, and none are already fully
codified in CLAUDE.md — though a couple overlap partially with procedure
files; we PROMOTE rather than rely on scattered procedure guards).

Nothing is KEEP-AS-MEMORY.

## Target file: `CLAUDE.md`

Additions layered into the existing structure:

### Change 1 — Extend `## Architecture` section
Add two subsections after **Task Hierarchy**:

- **Folded task semantics** — folded tasks are *merged* (not superseded);
  content incorporated at fold time; the folded file exists only as a
  reference for archival cleanup.
- **Adding new frontmatter fields** — any new field must touch three layers:
  (1) `aitask_create.sh` + `aitask_update.sh` (write path), (2)
  `aitask_fold_mark.sh` (union on fold, when applicable), (3)
  `aitask_board.py` `TaskDetailScreen` widget + subprocess wiring.

### Change 2 — Extend `## Shell Conventions` section
Add two bullets alongside the existing portability notes:

- **Platform-specific CLIs:** encapsulate `gh`, `glab`, `bitbucket`, etc. in
  bash scripts (pattern: `detect_platform()` routing). Never call platform
  CLIs directly from `SKILL.md`.
- **Archive format details:** encapsulate `tar.gz`/`tar.zst` / zstd commands
  in bash scripts. SKILL.md must call a script subcommand, never raw archive
  tooling.

### Change 3 — New `## Debugging Conventions` section
Debug the *actual* failing invocation, not isolated components; use tracing
(`bash -x`, `2>/tmp/log`, `tee`). When isolated pieces all pass, the fault is
in composition (env vars, shim, PATH, caller context). Compare invocation
paths when symptoms vary (e.g., `./ait ide` vs `ait ide`).

### Change 4 — New `## Documentation Writing` section
Describe the current state only. No "previously we recommended…",
"earlier versions said…", "this corrects…". Version history belongs in git,
not doc bodies. Applies to user-facing website/docs; internal plan files can
still record deviations.

### Change 5 — New `## UI & Dialog Conventions` section
Destructive-action confirmations must list each affected item with its
specific fate (`Will be ARCHIVED`, `Will be DELETED`, `Will be UPDATED`,
`Blocking`). Annotate rows with status metadata. Never merge multi-fate
operations into a flat file list. Centralize the formatting in one helper.

### Change 6 — New `## TUI (Textual) Conventions` section
- **`n` is the create-task key** across all aitasks TUIs (board, codebrowser,
  minimonitor, monitor, brainstorm, switcher modal). Do not default to `c`.
- **Priority bindings + `query_one` gotcha:** when `App` and a pushed
  `Screen` share an action name with `priority=True`, scope guard queries to
  `self.screen.query_one(...)`, not `App.query_one(...)` (which walks the
  whole stack). On guard-miss, raise `textual.actions.SkipAction` so the
  active screen's binding fires.

### Change 7 — New `## Model Attribution` section
When running agent attribution, scan the conversation for mid-session
`/model` command outputs (`<local-command-stdout>Set model to …</…>`)
*before* falling back to the initial system-message model ID. The system
message is frozen at session start — a mid-session `/model` switch otherwise
records the wrong attribution. Map the human name via
`aitask_resolve_detected_agent.sh --agent claudecode --cli-id <id>`.

### Change 8 — New `## QA Workflow` section
After implementation, run `/aitask-qa <task_id>` for test coverage analysis.
The embedded Step 8b test-followup procedure is deprecated. Profile keys
`qa_mode` and `qa_run_tests` control automation level.

### Change 9 — Extend `## WORKING ON SKILLS / CUSTOM COMMANDS`
Add a **Skill / Workflow Authoring Conventions** subsection before the
per-agent list:

- **Agent-specific steps live in their own procedure file.** If a workflow
  step applies only to one code agent (e.g., Claude Code plan
  externalization), extract it to `.claude/skills/task-workflow/<name>.md`
  and reference it with a conditional wrapper ("if running in Claude
  Code…"). Do not inline.
- **Use guard variables, not prose.** When a procedure could be triggered
  from multiple code paths, add an explicit guard boolean (e.g.,
  `feedback_collected`) to the context-variables table and check it at
  entry. Prose alone ("this only fires once") is not enough for LLMs.

### Change 10 — New `## Project-Specific Notes` section
- **`diffviewer` TUI is transitional** — will be folded into `brainstorm`
  later. Do not document it in user-facing website/docs. Keep it in
  `KNOWN_TUIS` inside `.aitask-scripts/lib/tui_switcher.py` — removal waits
  for the brainstorm integration.

## Style rules when rewriting each item

- Terse, imperative, no "I" voice.
- Strip memory-format metadata (`name`, `description`, `type`,
  `originSessionId`).
- Preserve the rule; preserve the **why** inline only when non-obvious;
  drop the **how to apply** if it is self-evident from the rule.
- Match the existing CLAUDE.md register (short bullets, minimal prose,
  no preamble).

## Files changed

- `CLAUDE.md` — sole code change.
- Auto-memory directory (outside repo) — all files deleted except
  `MEMORY.md`, which is reset to header only.

## Implementation Steps

1. **Edit `CLAUDE.md`** with all 10 changes above. Single Write (full
   rewrite) is cleaner than many Edits because several sections interleave
   and the final ordering matters — but Edits at section boundaries are
   also acceptable. Use Write for clarity; the file is short (~150 lines).

2. **Verify `CLAUDE.md` reads coherently** — diff review; no duplication;
   no memory-format residue (no `name:`/`description:` headers, no "I"
   voice, no references to memory filenames).

3. **Delete memory files:**
   - `rm` each `feedback_*.md` in the memory directory (12 files).
   - `rm` `project_diffviewer_brainstorm.md`.
   - Do NOT delete `MEMORY.md` (the auto-memory system expects it).

4. **Reset `MEMORY.md`** to just:
   ```
   # Memory Index
   ```
   (no entries; header only, so the auto-memory loader still works).

5. **Final listing** — show `ls` of the memory directory so the user can
   confirm only `MEMORY.md` remains.

6. **Commit** (just the CLAUDE.md change — memory files live outside the
   repo):
   ```
   documentation: Migrate persistent guidance from auto-memory to CLAUDE.md (t582)
   ```
   Standard plain `git commit` for CLAUDE.md (not `./ait git` — CLAUDE.md
   is a code file, not `aitasks/` / `aiplans/`).

7. **(Optional follow-up, NOT in this task)** — The
   `feedback_model_switch_mid_session` rule is also a candidate for folding
   into `.claude/skills/task-workflow/model-self-detection.md` so the
   procedure itself is correct. Mention this to the user as a suggested
   follow-up aitask; do not execute here.

## Verification

- `cat CLAUDE.md` reads cleanly; all 10 new sections/bullets are present.
- `ls ~/.claude/projects/-home-ddt-Work-aitasks/memory/` shows only
  `MEMORY.md`.
- `cat MEMORY.md` shows only the `# Memory Index` header.
- `git diff --stat` shows a single-file change to `CLAUDE.md` (+ line count
  roughly 60–80).
- Commit lands with the `documentation:` prefix + `(t582)` suffix, per
  CLAUDE.md's own commit format rules.

## Reference to Step 9 (Post-Implementation)

After commit, the task-workflow Step 9 flow proceeds: no branch/worktree
cleanup (fast profile kept us on `main`), then
`./.aitask-scripts/aitask_archive.sh 582` handles status → Done, archival,
lock release, and the archival commit; then `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Added 10 sections/bullets to `CLAUDE.md` covering
  folded task semantics, new frontmatter propagation, platform CLI and
  archive encapsulation (Shell Conventions), debugging conventions,
  documentation writing, UI & dialog conventions, TUI (Textual)
  conventions, model attribution, QA workflow, skill authoring
  conventions, and project-specific notes (diffviewer). Deleted all 13
  promoted memory files and reset `MEMORY.md` to a header-only index.
- **Deviations from plan:** None. Wrote `CLAUDE.md` with the Write tool
  (plan's preferred option — cleaner than multiple Edits for
  interleaved additions).
- **Issues encountered:**
  - Plan externalization initially returned `MULTIPLE_CANDIDATES` because
    three recent Claude Code plan files fell within the recency window.
    Resolved by re-running with `--internal <chosen-path>`.
  - `feedback_archive_encapsulation.md` on disk was missing (stale
    `MEMORY.md` reference). Reconstructed the rule from the index's
    one-line summary and the parallel `feedback_platform_commands.md`
    pattern — now expressed as the "Archive format details" bullet under
    Shell Conventions.
- **Key decisions:**
  - All 13 memories classified PROMOTE; none KEEP-AS-MEMORY; none DROP.
    Every memory encoded a durable team convention or project fact.
  - The `model_switch_mid_session` rule was promoted to a new "Model
    Attribution" section in CLAUDE.md rather than folded into
    `.claude/skills/task-workflow/model-self-detection.md`. A follow-up
    aitask can codify the fix in the procedure file itself (noted in
    the plan's Step 7 follow-up).
  - `project_diffviewer_brainstorm` promoted to a "Project-Specific
    Notes" section rather than kept as a memory — the "don't document
    in website docs" rule is still team-wide guidance useful for anyone
    editing the Hugo site.
- **Verification:**
  - `ls ~/.claude/projects/-home-ddt-Work-aitasks/memory/` confirms only
    `MEMORY.md` remains (15 bytes, header only).
  - `git diff --stat CLAUDE.md` shows `+70 insertions` (within the
    predicted 60–80 range).
  - `.claude/settings.local.json` was touched by permission approvals
    during the session and is excluded from this commit (uncommitted
    working-tree change).

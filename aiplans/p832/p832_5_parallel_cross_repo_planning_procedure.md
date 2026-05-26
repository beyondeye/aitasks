---
Task: t832_5_parallel_cross_repo_planning_procedure.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_5_parallel_cross_repo_planning_procedure
Branch: aitask/t832_5_parallel_cross_repo_planning_procedure
Base branch: main
---

# Plan: parallel cross-repo planning procedure (Scope 3)

See parent plan §t832_5. Depends on t832_1, t832_3, t832_7.

## Goal

Add a new shared procedure under `task-workflow` that lets a planning
agent design and write a single coordinated change spanning two aitasks
projects, using `xdeps` / `xdeprepo` for cross-repo edges.

## Architecture

- **Location:** `.claude/skills/task-workflow/parallel-cross-repo-planning.md`
  (shared module per user decision, NOT a separate skill).
- **Wire-in:** planning sites in `aitask-explore` and `aitask-create`.
- **Trigger:** prompt mentions a registered cross-repo project name OR
  task body contains the `<name>#<id>` notation.
- **Rule (load-bearing):** never a single parent whose children straddle
  two repos. Two parents, one per repo.

## Implementation steps

1. **Author the procedure file** with these sections (matching the
   parent plan §t832_5):
   - Trigger condition (registry name mention OR `aitasks#N_M` regex match).
   - 5-step procedure (resolve both, paired design, two parents, numbering
     lockstep, driver symmetry).
   - Commit-ordering protocol.
   - Failure-mode handling ("cross-repo committed but did not push"
     warning).
   - Multi-agent porting note (Claude Code first; suggest follow-ups
     for Codex/Gemini/OpenCode).

2. **Edit `.claude/skills/aitask-explore/SKILL.md.j2`** — at the
   planning site (likely near EnterPlanMode or the
   complexity-assessment branch), add a trigger check. On match,
   read and execute `parallel-cross-repo-planning.md`.

3. **Edit `.claude/skills/aitask-create/SKILL.md.j2`** — same wire-in.

4. **Re-render skills** for each profile via
   `./.aitask-scripts/aitask_skill_render.sh aitask-explore --agent claude`
   etc. Verify with `aitask_skill_verify.sh`.

5. **Regenerate goldens** for the affected `.md.j2` outputs in the same
   commit (per `aidocs/skill_authoring_conventions.md`).

## Tests

- `./.aitask-scripts/aitask_skill_verify.sh` passes for aitask-explore
  and aitask-create across all profiles.
- `tests/test_parallel_cross_repo_planning_procedure.sh`:
  - Two fake projects.
  - Dry-run procedure exercising numbering lockstep (verify cross-repo
    IDs are reserved BEFORE local children are written).
  - Simulate cross-repo `--commit` push failure (offline remote in the
    fake project); assert the "committed but did not push" warning fires.
  - Invoke with a single-parent-spanning-repos request; assert the
    "two parents, never one" precondition error fires.
- Smoke test: invoke `/aitask-explore` against a real cross-repo
  scenario (e.g., applink wire protocol change spanning `aitasks` and
  `aitasks_mobile`) and visually verify the procedure triggers.

## Coordination with sibling tasks

- **t832_7 (cross-repo update)** is required for symmetric cross-edges
  in step 4 (numbering lockstep back-fill). Confirm t832_7 has landed
  before testing the back-fill path.
- **t832_3 (xdeps parser)** must be live for the procedure's
  `aitask_create.sh --xdeps ... --xdeprepo ...` calls to succeed.

## Multi-agent porting follow-ups

After this lands, file 3 follow-up aitasks:
- Port to Codex CLI (`.agents/skills/task-workflow/`).
- Port to Gemini CLI (`.gemini/skills/task-workflow/`).
- Port to OpenCode (`.opencode/skills/task-workflow/`).

Each follow-up is a separate top-level aitask (NOT a child of t832 — t832
is "Done" by then).

## Out of scope

- The Codex/Gemini/OpenCode ports (separate follow-ups).
- Cross-repo merge coordination / transactional commits (parent t826 scope).
- TUI surfacing of in-progress paired plans (t832_8 for board).

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)

---
Task: t832_11_aitask_explore_cross_repo.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/archived/t832/t832_*_*.md (all siblings archived)
Archived Sibling Plans: aiplans/archived/p832/p832_5_parallel_cross_repo_planning_procedure.md, aiplans/archived/p832/p832_10_aitask_create_interactive_cross_repo.md
Base branch: main
Worktree: (none — profile 'fast': current branch)
Branch: main
---

# Plan: aitask-explore cross-repo paired-planning trigger (t832_11)

## Context

t832_5 (Done, archived) added two task-workflow closure procedures and wired
them into `/aitask-pick`:
- `planning-cross-repo.md` — read-only cross-repo **design**, dispatched from
  `task-workflow/planning.md` §6.1.
- `cross-repo-child-assignment.md` — post-approval **creation**, dispatched from
  `task-workflow/SKILL.md` Step 7.

This task extends paired-planning to `aitask-explore`.

**Architectural finding (resolves the task's "crux" — the trigger source):**
`aitask-explore` has **no planning/implementation phase of its own**. Step 5
hands off to `task-workflow/SKILL.md` at Step 3, which flows through Step 6
planning (`planning.md` §6.1 — design dispatch already present) and Step 7
(creation dispatch already present). Both fire automatically on any task whose
frontmatter carries a non-empty `xdeprepo` scalar (metadata-only trigger).

So the only gap is the trigger source: `/aitask-pick` reads `xdeprepo` from an
*existing* task, but explore *creates* the task — so explore must **set
`xdeprepo` at creation time**. Once set, the existing task-workflow dispatch
handles design + creation. No dispatch is duplicated into explore.

**Trigger UX (per user direction): auto-detect from the exploration's free
text, not an always-on prompt.** The cross-repo scope is discovered from what
the user *says* they want to explore — if their free-text description mentions a
project in the resolved cross-repo registry (or uses `<name>#<id>` /
`<name>:<path>` notation), the exploration *becomes* cross-repo-scoped. The
registry is **not read before the first prompt** (the initial "What would you
like to explore?" `AskUserQuestion` must fire with no I/O latency). The
cross-repo "Create as paired task" option appears only when the run actually
became cross-repo-scoped.

## Rejected alternatives

1. **Re-wire both procedures into `aitask-explore/SKILL.md.j2`** (the task's
   literal plan). Rejected: explore has no read-only plan-mode phase, and
   `planning-cross-repo.md` Step 1 needs an *already-existing* task to read
   `xdeprepo` from. Duplicating the dispatch re-implements the task-workflow
   handoff for zero behavioral gain.
2. **Probe the registry up front + always show a cross-repo option.** Rejected
   (user): adds I/O before the first prompt and clutters every single-repo
   explore with an irrelevant option.

## Runtime context variables (new — threaded through Steps 1→2→3)

These are workflow-run-local variables the agent maintains across steps
(analogous to the pre-Jinja execution-profile context variables — *not* Jinja /
profile keys). All default empty:

| Variable | Meaning |
|----------|---------|
| `cross_repo_scope` | Resolved registry project name the exploration became scoped to (`""` = single-repo). Drives Step 2 cross-repo exploration and the Step 3 option. |
| `cross_repo_root` | Filesystem root of `cross_repo_scope` (from `aitask_project_resolve.sh <name>` → `RESOLVED:<root>`). |
| `cross_repo_files` | Cross-repo file paths resolved from `<name>:<relative/path>` notation (`<root>/<relative/path>`), fed to Step 2 exploration as high-priority reads. |
| `cross_repo_xdeps` | Candidate cross-repo dep task IDs parsed from `<name>#<id>` notation (CSV), pre-filled as `--xdeps` in Step 3. |

## Key files to modify

| File | Change |
|------|--------|
| `.claude/skills/aitask-explore/SKILL.md.j2` | Add the runtime-variable preamble; a **cross-repo scope detection** sub-step *after* Step 1's free-text capture (no registry read before the first prompt); cross-repo-aware exploration in Step 2; a conditional 3rd proposal option + `--xdeprepo`/`--xdeps` append in Step 3; an inheritance note. |
| `tests/golden/skills/aitask-explore/SKILL-{default,fast,remote}-claude.md` | Regenerate (3 canonical claude goldens) after the `.j2` edit. |
| `tests/test_skill_render_aitask_explore.sh` | Add assertions (below). |

No edits to `planning-cross-repo.md`, `cross-repo-child-assignment.md`,
`task-workflow/planning.md`, `task-workflow/SKILL.md`, or `task-creation-batch.md`.

## Implementation detail — `aitask-explore/SKILL.md.j2`

Reference for registry mechanics: `select_xdeprepo()` at
`.aitask-scripts/aitask_create.sh:823-866` (list → exclude current repo →
RESOLVED only; STALE skipped with a warn). Reference for notation resolution:
`planning-cross-repo.md` Step 4 (`<name>#<id>` and `<name>:<path>`).

**(a) Preamble** — document the four runtime variables above near the top of the
workflow (all default empty).

**(b) Step 1 — unchanged first prompt.** The initial "What would you like to
explore?" `AskUserQuestion` fires immediately; **no registry read precedes it.**

**(c) New sub-step "Cross-repo scope detection" (end of Step 1, after the
free-text follow-up is captured):**
- Read the resolved registry: `./.aitask-scripts/aitask_project_resolve.sh list`;
  collect `<name>` from `PROJECT:<name>:<path>:RESOLVED` lines where `<path>` ≠
  current repo root (skip `STALE`).
- Scan the user's free-text exploration description for: a resolved `<name>`
  mention, or `<name>#<id>` / `<name>:<relative/path>` notation.
- On a match: set `cross_repo_scope = <name>`; resolve
  `cross_repo_root` via `aitask_project_resolve.sh <name>` → `RESOLVED:<root>`;
  for each `<name>:<path>` add `<root>/<path>` to `cross_repo_files`; for each
  `<name>#<id>` add `<id>` to `cross_repo_xdeps` (and optionally resolve its
  title via `aitask_query_files.sh --project <name> task-file <id>` for the
  exploration question).
- No match → variables stay empty; continue as a normal single-repo explore.

**(d) Step 2 — cross-repo-aware exploration.** If `cross_repo_scope` is set,
extend the exploration loop to span both repos: spawn an `Explore` agent rooted
in `cross_repo_root` (alongside the local one) and include `cross_repo_files` as
high-priority reads; report cross-repo findings alongside local ones.

**(e) Step 3 — conditional cross-repo option.** In the existing proposal
`AskUserQuestion` (Header "Task"), add a 3rd option **only when
`cross_repo_scope` is non-empty**:
- "Create as cross-repo paired task" — description: "Exploration is scoped to
  `<cross_repo_scope>`; sets `xdeprepo` and designs a paired decomposition
  during planning."

"If 'Create as cross-repo paired task'": optionally confirm/edit the cross-repo
dep IDs (default `cross_repo_xdeps`), then in the "Create the task" block append
`--xdeprepo "<cross_repo_scope>"` and, only when deps are non-empty,
`--xdeps "<ids>"` (both-or-neither; `--xdeprepo` alone is the valid intent-only
form per `validate_xdeps_pair`).

**(f) Inheritance note** (prose, no dispatch): the created task carries
`xdeprepo`; the Step 5 handoff to `task-workflow/SKILL.md` runs the Cross-Repo
Planning Procedure (design, §6.1) and the Cross-Repo Child Assignment Procedure
(creation, Step 7, post-approval). explore dispatches neither itself.

The change is profile- and agent-invariant (no new `{% if profile %}` /
`{% if agent %}`), so codex/opencode renders stay byte-identical (Test 1b) and
auto-render — **no cross-agent port follow-up needed**.

## Tests / goldens

- Edit `.j2`, then regenerate the 3 claude goldens (the test's golden-regen path,
  or `./.aitask-scripts/aitask_skill_render.sh aitask-explore --profile <p>
  --agent claude` captured into each `SKILL-<p>-claude.md`).
- Extend `tests/test_skill_render_aitask_explore.sh`:
  - Each rendered profile contains the detection sub-step (`aitask_project_resolve.sh
    list`), the `cross_repo_scope` variable, `xdeprepo`, and the conditional
    "cross-repo paired" option gated on `cross_repo_scope`.
  - Each rendered profile does **NOT** contain `planning-cross-repo.md` or
    `cross-repo-child-assignment.md` (asserts inheritance, not duplication).
  - The initial "What would you like to explore?" prompt still precedes any
    `aitask_project_resolve.sh` call (no upfront registry read).
  - Existing cross-agent invariance (Test 1b) still passes.

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` → PASS for aitask-explore across
   all profiles.
2. `bash tests/test_skill_render_aitask_explore.sh` → all assertions pass.
3. Regression: `bash tests/test_parallel_cross_repo_planning_procedure.sh`,
   `bash tests/test_skill_render_task_workflow.sh` → pass (untouched).
4. Confirm goldens committed in the same commit as the `.j2` edit.

## Step 9 (Post-Implementation)

Profile 'fast', current branch (no worktree/merge). Child-task archival via
`./.aitask-scripts/aitask_archive.sh 832_11`, then `./ait git push`. This
completes the "wire the dispatch into aitask-explore" follow-up named in
`cross-repo-child-assignment.md` Step 8. The multi-agent ports of the two
*procedures* (Codex/agy/OpenCode) remain separate, already-tracked follow-ups.

## Risk

### Code-health risk: low
- Additive change to one `.md.j2` (preamble + detection sub-step + Step 2/3
  branches gated on a runtime variable) plus one test. The single-repo explore
  path is unchanged when `cross_repo_scope` stays empty. Blast radius: one skill
  template + its 3 goldens + one test. · severity: low · → mitigation: None

### Goal-achievement risk: low
- Relies on the explore→task-workflow handoff reaching §6.1 (design) and Step 7
  (creation) — verified in `task-workflow-fast-/planning.md` §6.1 (line 168) and
  `SKILL.md` Step 7 (line 259); both dispatch on the `xdeprepo` trigger explore
  now sets. Detection is heuristic (free-text name/notation match) but
  fail-safe: a miss simply yields a normal single-repo explore, and the paired
  flow is still confirmed downstream at the §6.1 confirmation gate. · severity: low · → mitigation: None

No mitigations planned (no risk warrants a before/after follow-up task).

## Final Implementation Notes

- **Actual work done:** Wired cross-repo paired-planning into `aitask-explore`
  by making explore **set `xdeprepo` at task-creation time** (auto-detected),
  then letting the existing task-workflow handoff drive the design + creation
  dispatch. Edited only `.claude/skills/aitask-explore/SKILL.md.j2`:
  (a) a runtime-variable preamble (`cross_repo_scope`, `cross_repo_root`,
  `cross_repo_files`, `cross_repo_xdeps`); (b) a new **Cross-repo scope
  detection** sub-step at the end of Step 1 that reads the resolved registry
  *after* the first prompt and matches the user's free text against registered
  project names / `<name>#<id>` / `<name>:<path>` notation; (c) Step 2
  cross-repo-aware exploration (Explore agent rooted in `cross_repo_root` +
  `cross_repo_files`); (d) a Step 3 proposal option "Create as cross-repo
  paired task" shown only when `cross_repo_scope` is set, plus the
  `--xdeprepo`/`--xdeps` append in "Create the task" and an inheritance note.
  Regenerated the 3 canonical claude goldens; added Test 6 to
  `tests/test_skill_render_aitask_explore.sh` (detection present,
  procedures NOT dispatched directly, first prompt precedes the registry read).
- **Deviations from plan:** None from the approved (revised) plan. Note the
  approved plan itself deviates from the original task's literal Implementation
  Plan — explore does NOT dispatch `planning-cross-repo.md` /
  `cross-repo-child-assignment.md` itself; it sets `xdeprepo` and inherits both
  dispatches via the `task-workflow/SKILL.md` handoff (Step 3→6 §6.1 design,
  Step 7 creation). Confirmed with the user before implementation.
- **Issues encountered:** None. `ait codeagent coauthor` resolved cleanly;
  `aitask_skill_verify.sh` re-rendered per-agent variants without error.
- **Key decisions:** (1) Trigger via free-text auto-detection rather than an
  always-on prompt; registry is NOT read before the first `AskUserQuestion`
  (latency to first prompt matters — user direction). (2) Runtime context
  variables threaded across steps in the style of the pre-Jinja
  execution-profile variables. (3) Change is profile- and agent-invariant
  (no new `{% if %}`), so codex/opencode auto-render and need no port task.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** The metadata-only `xdeprepo` trigger is the
  load-bearing contract shared with `/aitask-pick` (t832_5). Any skill that
  *creates* a task and wants paired planning only needs to set `xdeprepo` at
  creation — the task-workflow handoff supplies design (`planning.md` §6.1) and
  creation (`SKILL.md` Step 7); do not duplicate the dispatches. The two
  cross-repo *procedures* still have separate, already-tracked multi-agent port
  follow-ups (Codex/agy/OpenCode); this task did not touch them. This completes
  the "wire the dispatch into aitask-explore" item named in
  `cross-repo-child-assignment.md` Step 8.

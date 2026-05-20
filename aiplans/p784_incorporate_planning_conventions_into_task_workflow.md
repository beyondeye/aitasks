---
Task: t784_incorporate_planning_conventions_into_task_workflow.md
Base branch: main
plan_verified: []
---

# t784 — Incorporate planning conventions into the task-workflow planning procedure

## Context

t783 compacted `CLAUDE.md` by externalising specialist rules into focused
`aidocs/` files. One of those, `aidocs/planning_conventions.md`, holds six
rules for authoring/reviewing implementation plans. They were extracted as a
side document, but they really belong inside the planning procedure the
task-workflow skill runs — so they fire at plan-authoring time instead of
relying on the agent to remember to read a separate doc. `planning_conventions.md`
itself carries a "Future refactor note" naming exactly this promotion.

This task moves all six rules into the planning procedure, deletes the now-empty
aidoc, and removes its `CLAUDE.md` pointer.

## Key architectural facts (verified)

- **Source of truth:** `.claude/skills/task-workflow/planning.md` is a Jinja
  *closure procedure* (named `.md` but contains `{% %}`/`{{ }}`), rendered by
  `skill_template.py` into per-profile/per-agent variants
  (`task-workflow-{default,fast,remote}-/` under `.claude/`, `.agents/`,
  `.gemini/`, `.opencode/`).
- **No manual mirroring needed.** There is *no* `.agents/skills/task-workflow/`
  (etc.) source dir — only rendered `*-/` variants, which are gitignored
  (`git check-ignore` confirmed). The task's "mirror into sibling agent trees"
  step is satisfied automatically by rendering; the only committed artifacts to
  update are the goldens. (Deviation from the task's "Files to touch" list,
  which assumed source dirs in each agent tree.)
- **Goldens:** `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`
  are committed and diff-checked by `tests/test_skill_render_task_workflow.sh`
  Test 1. They must be regenerated in the same commit.
- **Render-neutrality:** all added text is plain prose (no Jinja), so it renders
  identically across the 3 profiles — the golden diff will be the same prose
  block in all three files.
- `planning_conventions.md` is referenced in exactly one place outside the
  rendered/golden trees: `CLAUDE.md:242` (grep-confirmed).

## Rule placement (per the task's own mapping)

Four rules become per-step inline notes; two design-time anti-patterns go in a
new section near the top of `planning.md`.

| Rule | Placement in `planning.md` |
|------|----------------------------|
| 1. Refactor duplicates before adding to them | §6.1, new bullet right after "Create a detailed, step-by-step implementation plan" |
| 2. Plan split: in-scope sibling children | §6.1, first sub-bullet of the "If creating child tasks:" branch |
| 3. Dead code goes into the sibling refactor task | §6.1, sub-bullet inside "Write implementation plans for ALL child tasks" |
| 4. Gate plans on in-flight related tasks | §6.1, new bullet in the "While in plan mode:" list, after "Explore the codebase…" |
| 5. No fallback-read workarounds for sync/desync | new "## Planning Anti-patterns" section |
| 6. Audit-only tasks with zero findings | new "## Planning Anti-patterns" section |

All six land in `planning.md` → `aidocs/planning_conventions.md` is deleted and
its `CLAUDE.md` pointer removed (per the task's "if all rules land" branch).

## Implementation

### 1. Edit `.claude/skills/task-workflow/planning.md`

**1a. Table of Contents** — add as first list entry:
```
- [Planning Anti-patterns](#planning-anti-patterns)
```

**1b. New section** — insert between the `---` line and `## 6.0: Check for Existing Plan`:

```markdown
## Planning Anti-patterns

Design-time rules — keep these in mind whenever drafting or reviewing a plan,
regardless of which numbered step you are on.

- **No fallback-read workarounds for sync/desync root causes.** For
  local-vs-remote desync symptoms, do NOT plan to extend resolver helpers
  (`resolve_task_file`, `resolve_plan_file`) with `git show <remote_ref>:...`
  fallback tiers — they hide the desync, bloat resolver chains, and mask stale
  local state. The right fix makes desync *visible and resolvable*:
  best-effort `warn` at script entry points and integration with the syncer
  TUI / monitor surfaces. Reading from `origin` behind the user's back is not
  a "deeper fix."

- **Audit-only tasks with zero findings produce audit-only plans.** When a
  follow-up audit task ("grep the codebase for the same class of bug") finds
  zero occurrences beyond the single known case, do NOT plan a regression
  test, AST scanner, or lint rule as the deliverable. The audit itself is the
  deliverable: document method + findings + "no code changes." A one-off bug
  with a known mechanism is not evidence of an ongoing pattern — note the
  trigger for revisiting under "Out of scope" and only build infrastructure if
  a second occurrence appears.

---
```

**1c. Rule 1** — after the "Create a detailed, step-by-step implementation plan" bullet in §6.1, insert:
```markdown
- **Refactor duplicates before adding to them.** If the plan would edit the
  same list, set, or config in three or more separate files (e.g. adding one
  value to `DEFAULT_TUI_NAMES`, `_DEFAULT_TUI_NAMES`, `KNOWN_TUIS`, and
  `project_config.yaml`), propose a single-source-of-truth extraction before
  accepting the duplicated edit — duplicated state is the mechanism that
  produces drift bugs. Also evaluate merge/additive semantics for config
  overrides over code defaults; they prevent drift as new framework features
  land.
```

**1d. Rule 4** — in the "While in plan mode:" list, after the "Explore the codebase to understand the relevant architecture" bullet, insert:
```markdown
- **Gate plans on in-flight related tasks.** While exploring, scan
  `aitasks/t<id>_*.md` for `status: Implementing` or `Editing`. If the planned
  task **mirrors, clones, or extends** rendering/data owned by an in-flight
  task, do NOT plan to implement it in parallel — forking ahead ships an
  extension that misses the in-flight task's new fields. Instead add a
  "Sequencing — wait for tN to land" section to the plan, mark the new task
  `depends: [N]` (or `Postponed`), externalize and commit the plan now, then
  exit via the "Approve and stop here" checkpoint.
```

**1e. Rule 2** — as the first sub-bullet of the "If creating child tasks:" branch (before "Ask how many subtasks…"):
```markdown
    - **Split into in-scope siblings, not deferred follow-ups.** Default to all
      phases as sibling children (in scope), plus a trailing
      retrospective-evaluation child that depends on the others. Do NOT mark
      later phases as "out-of-scope follow-up tasks" once the parent has scoped
      them. When committing to a design choice under partial information
      ("we'll know the right shape once we benchmark"), make the retrospective
      child explicit — it is bounded by the parent, documents outcomes, and
      files standalone follow-ups only if the collected data justifies them.
```

**1f. Rule 3** — sub-bullet inside the "Write implementation plans for ALL child tasks" block (after "Each plan should leverage the codebase exploration…"):
```markdown
      - **Dead code goes into the sibling refactor task — never a vague
        follow-up.** If a child-task plan would leave a function, global,
        branch, or file unreachable after the change lands, do NOT write
        "leave it for a future cleanup." Name the sibling task whose scope is
        `cleanup / refactor / migrate / remove` and drop a one-line note
        (file path + line range) into its task file under `## Notes for
        sibling tasks`. If no sibling fits, surface a new task creation as part
        of the current plan — do not bury cleanup intent in a `# DEPRECATED`
        comment alone.
```

### 2. Delete `aidocs/planning_conventions.md`

All six rules now live in `planning.md`; the aidoc has no remaining content.

### 3. Edit `CLAUDE.md`

Remove the planning-conventions pointer block (lines ~240-246) under
"## Planning / Testing / Code Conventions", leaving the `testing_conventions.md`
and `code_conventions.md` pointers intact:

```
> **Read `aidocs/planning_conventions.md`** when writing or reviewing an
> implementation plan — especially before splitting a complex task into
> children, deferring follow-ups, or proposing edits to a list/config that
> appears in 3+ files. (These rules are a candidate for future promotion
> into the task-workflow planning procedure.)
>
```

### 4. Regenerate goldens

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/planning.md \
    aitasks/metadata/profiles/$profile.yaml claude \
    > tests/golden/procs/task-workflow/planning-${profile}.md
done
```

The three golden diffs must be identical (same prose, no Jinja) — review them.

## Files to touch

- `.claude/skills/task-workflow/planning.md` — primary edit (ToC + new section + 4 inline rules)
- `aidocs/planning_conventions.md` — delete
- `CLAUDE.md` — remove planning-conventions pointer
- `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md` — regenerated

## Verification

- `bash tests/test_skill_render_task_workflow.sh` — Test 1 golden diffs pass for
  `planning × {default,fast,remote}`; Test 3 still finds the unchanged
  AskUserQuestion prose.
- `./.aitask-scripts/aitask_skill_verify.sh` — closure walk for every `.j2`
  resolves and renders cleanly (planning.md is reachable from aitask-pick's
  closure).
- `grep -rn planning_conventions CLAUDE.md aidocs/` — returns nothing (no
  dangling pointer; file gone).
- Spot-check `git diff` on the three regenerated goldens: each shows the same
  added prose block, nothing else.

## Step 9 (Post-Implementation)

Single parent task, no children, working on the current branch. After review &
commit (Step 8) → Step 9 archival via `./.aitask-scripts/aitask_archive.sh 784`.

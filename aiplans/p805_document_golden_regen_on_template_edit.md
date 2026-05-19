---
Task: t805_document_golden_regen_on_template_edit.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan: Document golden regeneration on template edit (t805)

## Context

Goldens at `tests/golden/skills/<skill>/SKILL-<profile>-<agent>.md` and
`tests/golden/procs/task-workflow/*.md` are byte-for-byte snapshots of
rendered template output. Any edit to a `.md.j2` (or any file in its
render closure) that shifts rendered bytes fails the corresponding
`tests/test_skill_render_*.sh::Test 1` `assert_eq`.

Two existing docs gesture at this rule but neither states it as a
workflow requirement:

- `aidocs/skill_authoring_conventions.md:206-216` — render-neutrality
  paragraph, scoped only to Jinja comment edits.
- `aidocs/stub-skill-pattern.md:233-238` (Pilot Finding #3) — frames
  goldens as a one-time conversion-time decision, not an ongoing rule.

Without a stated rule, future template edits land without golden regen
and goldens silently diverge from rendered output. Loud failure happens
at the next `bash tests/test_skill_render_*.sh` run, but a contributor
unfamiliar with the convention may regenerate goldens blindly to "fix
the test" rather than reviewing the diff (which IS the audit signal —
see memory `feedback_golden_file_tests_for_template_engines`).

## Drift audit results (completed during planning)

Ran all four golden test suites:

- `tests/test_skill_render_aitask_pick.sh` → **116/116 PASS**, no drift.
- `tests/test_skill_render_aitask_review.sh` → **124/124 PASS**, no drift.
- `tests/test_skill_render_task_workflow.sh` → **38/38 PASS**, no drift.
- `tests/test_skill_render_aitask_explore.sh` → **106/118, 12 FAIL** —
  all 12 golden diffs (`SKILL-{default,fast,remote}-{claude,codex,gemini,opencode}.md`)
  drifted.

**Root cause:** commit `2bf6747e enhancement: Defer aitask-explore sync
to Step 2b for faster first prompt (t800)` edited
`.claude/skills/aitask-explore/SKILL.md.j2` (moved the sync step from
Step 0 to inside Step 2b) without regenerating the goldens. This is
exactly the workflow gap this task is meant to close.

**Resolution:** the t800 template change was intentional and is the
canonical truth. The 12 stale goldens will be regenerated and committed
as part of this task. Drift count is 12 files but all from a single
commit on a single template — within the "drift > 3 files" escalation
threshold but with unambiguous single-source intent, so no separate
fix-up task is warranted; bundling in this task is appropriate.

## Implementation

### Step 1: Regenerate the 12 stale aitask-explore goldens

Run the render loop (same pattern used by `tests/test_skill_render_aitask_explore.sh::Test 1`,
inverted to write into goldens):

```bash
PYTHON="$(./.aitask-scripts/lib/python_resolve.sh 2>/dev/null; cat)" # use require_ait_python
# Concretely, use the helper directly:
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
RENDER="$PYTHON .aitask-scripts/lib/skill_template.py"
TEMPLATE=".claude/skills/aitask-explore/SKILL.md.j2"
PROFILES_DIR="aitasks/metadata/profiles"
GOLDEN_DIR="tests/golden/skills/aitask-explore"

for profile in default fast remote; do
  for agent in claude codex gemini opencode; do
    $RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" \
      > "$GOLDEN_DIR/SKILL-${profile}-${agent}.md"
  done
done
```

Then `git diff tests/golden/skills/aitask-explore/` — every diff should
match the t800 template change (sync block moved from Step 0 to inside
Step 2b). No surprises expected; if any diff has unrelated content,
investigate.

### Step 2: Add subsection to `aidocs/skill_authoring_conventions.md`

Immediately after the existing render-neutrality paragraph (currently
ends at line 216, before `## Do not route skill invocation through …`),
add a new top-level subsection:

```markdown
## Regenerate goldens after any `.md.j2` or closure edit

When you edit a `.md.j2` template OR any `.md` file in its render
closure (procedure files under `.claude/skills/task-workflow/`,
sibling procedures, includes, etc.), regenerate the affected goldens
and commit them in the same change. Skipping this step causes
`tests/test_skill_render_*.sh::Test 1` (`assert_eq` against committed
golden) to fail on the next run; the failure surfaces in CI / locally
but the template edit ships with stale goldens until someone notices.

**The diff is the audit signal — review it, don't rubber-stamp it.**
Goldens exist precisely so the template engine cannot silently shift
rendered output (whitespace, comment placement, conditional bodies,
reference-rewrite regressions). The intended diff for a template edit
should match what you changed; an unrelated diff means a regression
(see memory `feedback_golden_file_tests_for_template_engines`).

**Regenerate command** (3 profiles × 4 agents per entry-point skill):

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
RENDER="$PYTHON .aitask-scripts/lib/skill_template.py"
TEMPLATE=".claude/skills/<skill>/SKILL.md.j2"
PROFILES_DIR="aitasks/metadata/profiles"
GOLDEN_DIR="tests/golden/skills/<skill>"

for profile in default fast remote; do
  for agent in claude codex gemini opencode; do
    $RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" \
      > "$GOLDEN_DIR/SKILL-${profile}-${agent}.md"
  done
done
```

For procedure goldens under `tests/golden/procs/<scope>/` (e.g.
`task-workflow/`), the render target is a procedure file; see the
loop in `tests/test_skill_render_task_workflow.sh` for the agent
flattening (procedure goldens drop the agent dimension).

**Enforcement:** `tests/test_skill_render_*.sh` (per-skill) and
`tests/test_skill_render_task_workflow.sh` run Test 1 with `assert_eq`
on every golden. Run the relevant test after regenerating to confirm
all green before committing.

**Commit rule.** Goldens and the template edit land in the **same
commit**. A separate "regenerate goldens" follow-up commit hides the
intent (reviewer cannot tell whether the diff is intended without
diffing against the prior commit's template).

The narrower Jinja-comment render-neutrality rule above is a special
case of this rule — there the diff MUST be empty; here the diff is
whatever the template edit produced and MUST be reviewed.
```

### Step 3: Extend `aidocs/stub-skill-pattern.md` Pilot Finding #3

Edit the existing Finding #3 (lines 232-238) to add an explicit
operational rule. Replace the closing of Finding #3 (currently ends
with the canonical-memory pointer) with an additional sentence:

```markdown
3. **Golden-file tests are mandatory.** `./ait skill verify` and "renders
   without error" catch fewer regressions than committed goldens; the
   template engine can silently shift output (whitespace, comment
   placement, conditional bodies). 12 goldens caught the t777_26
   profile-resolution mismatch the moment it landed. Canonical memory:
   `feedback_golden_file_tests_for_template_engines`.

   **Operational rule:** Goldens must be regenerated and committed
   alongside *any* edit to a `.md.j2` or closure file — not just at
   conversion time. See "Regenerate goldens after any `.md.j2` or
   closure edit" in `aidocs/skill_authoring_conventions.md` for the
   regenerate command and the commit-in-same-commit rule.
```

### Step 4: Add a one-line pointer to `CLAUDE.md`

In the existing "Working on Skills / Custom Commands" section (after
the current paragraph about Codex CLI / Gemini CLI / OpenCode being
adapted from the Claude Code version, and before the existing
`aitask_skill_verify.sh` pre-commit reminder), add a one-line sentence
pointing at the new aidocs subsection:

```markdown
**After editing any `.md.j2` or closure procedure, regenerate the
affected goldens — see "Regenerate goldens after any `.md.j2` or
closure edit" in `aidocs/skill_authoring_conventions.md`.**
```

This sits naturally next to the existing `aitask_skill_verify.sh` line
so contributors see both pre-commit checks in one place.

### Optional helper (evaluated and DEFERRED)

The task suggested `.aitask-scripts/aitask_skill_regenerate_goldens.sh
<skill>` as an optional convenience wrapper. **Decision: defer.** The
inline 3×4 loop is short (8 lines), already present in the test
scripts, and lives next to the goldens — easier to discover than a
named helper. Adding a helper now would duplicate one logical block
across two files (test loop + helper) for minimal ergonomic gain.
Revisit only if multiple future tasks ask for it.

## Files to modify

- `aidocs/skill_authoring_conventions.md` — new subsection inserted
  after line 216.
- `aidocs/stub-skill-pattern.md` — extend Pilot Finding #3 (lines
  232-238) with the operational rule paragraph.
- `CLAUDE.md` — add a one-line pointer in "Working on Skills / Custom
  Commands" section.
- `tests/golden/skills/aitask-explore/SKILL-{default,fast,remote}-{claude,codex,gemini,opencode}.md`
  — 12 regenerated golden files (the t800 stale-goldens fix-up).

## Reference files (read-only)

- `aidocs/skill_authoring_conventions.md:206-216` — render-neutrality
  paragraph, model for the new subsection.
- `aidocs/stub-skill-pattern.md:211-262` — Pilot Findings section.
- `tests/test_skill_render_aitask_review.sh:80-90` — Test 1 loop
  (canonical render+assert pattern).
- `tests/test_skill_render_aitask_explore.sh:75-90` — same shape.
- `tests/test_skill_render_task_workflow.sh` — procedure-goldens
  variant (no agent dimension).
- `.aitask-scripts/aitask_skill_render.sh` — wrapper that delegates to
  `skill_template.py walk-write` (closure-aware skip-if-fresh; not the
  right tool for "render-to-stdout for golden capture" — use direct
  `skill_template.py` invocation as shown above).

## Verification

1. Drift-audit re-run after golden regen: all four test suites green:
   ```bash
   bash tests/test_skill_render_aitask_pick.sh      # 116/116
   bash tests/test_skill_render_aitask_review.sh    # 124/124
   bash tests/test_skill_render_aitask_explore.sh   # 118/118 (was 106/118)
   bash tests/test_skill_render_task_workflow.sh    #  38/38
   ```
2. `./.aitask-scripts/aitask_skill_verify.sh` → OK.
3. Manually re-read the new aidocs subsection: does a fresh
   contributor know exactly what to run after editing a `.md.j2`, that
   they should review (not rubber-stamp) the diff, and that goldens
   land in the same commit as the template edit?
4. Confirm CLAUDE.md one-liner sits cleanly next to the existing
   `aitask_skill_verify.sh` reminder.

## Step 9 (Post-Implementation)

Per task-workflow Step 9: commit code (CLAUDE.md, aidocs/*, regenerated
goldens — these are code, not aiplans/aitasks, so plain `git`), commit
plan separately with `./ait git`, push, then archive via
`./.aitask-scripts/aitask_archive.sh 805`. Profile 'fast' works on
the current branch so no worktree/branch merge gate is needed.

## Final Implementation Notes (to be filled in at Step 8)

- **Drift audit findings:** 12 stale goldens in
  `tests/golden/skills/aitask-explore/` caused by t800 (`2bf6747e`)
  editing the template without regenerating goldens. Resolution: all
  12 regenerated in this task (intended drift). No other skill
  (`aitask-pick`, `aitask-review`, `task-workflow`) had drift.
- **Actual work done:** (TBD at Step 8)
- **Deviations from plan:** (TBD at Step 8)
- **Issues encountered:** (TBD at Step 8)
- **Key decisions:**
  - Skipped the optional `aitask_skill_regenerate_goldens.sh` helper —
    inline loop is short and already in test scripts.
  - Bundled the 12-file drift fix into this task rather than splitting
    out (single template, single root-cause commit, unambiguous
    intent).
- **Upstream defects identified:** None. (The t800 stale-goldens are
  caught and fixed in this task — that's the task's purpose, not an
  upstream defect surfaced during diagnosis.)

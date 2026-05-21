---
Task: t818_align_detailer_planning_plan_contract.md
Base branch: main
plan_verified: []
---

# t818 — Align detailer/planning plan-content contract

## Context

Two pipelines author implementation plans and both feed `aiplans/`:

- **`.claude/skills/task-workflow/planning.md`** §6.1 — a code agent's plan,
  authored interactively, externalized to `aiplans/p<task>.md`.
- **`.aitask-scripts/brainstorm/templates/detailer.md`** — a brainstorm
  detailer crew agent's plan, written to `br_plans/<node>_plan.md` and later
  copied to `aiplans/p<task>_<node>.md` by `finalize_session()`.

Because planning.md §6.0 ("Check for Existing Plan") lets a code agent consume
a brainstorm-detailer-authored plan, the two pipelines share an
**implementation-plan content contract**: exact file paths, per-file changes,
code snippets for non-trivial changes, dependency-ordered steps (no forward
refs), prerequisites, testing strategy, verification checklist, and the
authoring rules. Today that contract is duplicated — richly in `detailer.md`
(`## Output` + `## Rules`), thinly in `planning.md` (one paragraph at the end
of §6.1). Improving one does not propagate to the other; they drift.

This task single-sources that contract into one canonical fragment that both
pipelines include.

## The bridge problem (requirement #3) and the chosen design

The two pipelines use **different** include mechanisms:

| Pipeline | Renderer | Include syntax | Base dir |
|----------|----------|----------------|----------|
| detailer.md | `resolve_template_includes()` (bash, in `agentcrew_utils.sh`) | `<!-- include: X -->` | `.aitask-scripts/brainstorm/templates/` |
| planning.md | minijinja via `skill_template.py` dep-walker | `{% include "X" %}` | minijinja `load_from_path` = `[<skill dir>, <skills root>]` |

The canonical fragment must live at
`.aitask-scripts/brainstorm/templates/_plan_contract.md` (requirement #1).
detailer.md reaches it trivially (same dir). minijinja's loader for planning.md
currently searches only `.claude/skills/task-workflow/` and `.claude/skills/`
— it cannot see the brainstorm `templates/` dir.

**Chosen bridge: extend the minijinja include search path.** `render_skill()`
in `skill_template.py` will add `<repo>/.aitask-scripts/brainstorm/templates/`
to its `load_from_path` list. planning.md then uses
`{% include "_plan_contract.md" %}` and minijinja resolves it to the same
canonical file the bash resolver uses. This keeps a true single source of
truth — no symlink, no copy, no second drift surface — and the renderer change
is ~10 lines. (Rejected: a symlink in the skills tree is portability-fragile
and confuses the dep-walker's tree scan; pre-resolving `<!-- include -->` in
Python would re-implement the bash resolver — ironic for a de-dup task.)

**Staleness closure:** minijinja resolves `{% include %}` *during* render, so
an included file never appears in the dep-walker's closure `plan` list and
`_is_stale()` would not re-render planning.md when only `_plan_contract.md`
changes. The fix folds `{% include %}` targets into the staleness check (see
Step 4) so editing the contract correctly invalidates the rendered skill.

## What the canonical fragment contains

`_plan_contract.md` holds the *content requirements* (what a plan must
contain) and the *authoring rules* — **marker-free**, because planning.md must
not carry brainstorm `<!-- section: … -->` markers. Brainstorm-specific
machinery (the `--- DETAILED_PLAN_* ---` delimiters, `<!-- section -->`
markers, `[dimensions: …]` attributes, per-component nesting) stays in
detailer.md as a thin overlay around the include.

---

## Implementation Plan

### Prerequisites

- No new tools/libraries. minijinja is already the skill template engine and
  already supports `{% include %}` (per `skill_template.py` docstring).
- Repo must have the framework venv with `minijinja` (the render tests
  `SKIP:` cleanly otherwise).

### Step 1 — Create the canonical fragment

**New file:** `.aitask-scripts/brainstorm/templates/_plan_contract.md`

Marker-free markdown. No `{{ }}` / `{% %}` (it is rendered verbatim by
minijinja) and no `*.md` filename mentions (so the dep-walker's ref scanner
ignores it). Opens with a one-line HTML comment naming both consumers, then:

```markdown
<!-- _plan_contract.md — canonical implementation-plan content contract.
     Shared by .aitask-scripts/brainstorm/templates/detailer.md (bash
     <!-- include --> resolver) and .claude/skills/task-workflow/planning.md
     (minijinja {% include %}). Single source of truth — edit here only. -->
An implementation plan must be concrete enough that a developer — or a fresh
agent context — can execute it without further design decisions. It must
contain:

### Prerequisites
- Tools, libraries, and versions required
- Environment variables and configuration
- Infrastructure provisioning (if needed)
- Access or permissions

### Step-by-Step Changes
For each step:
- **Files:** exact paths to create or modify
- **Changes:** specific instructions, with code snippets for non-trivial
  modifications
- **Why:** brief rationale linking the step to the design

Steps must be in dependency order — no step may reference a file or component
created in a later step.

### Testing
- Unit test strategy per component
- Integration test strategy
- Performance checks that validate the design's assumptions

### Verification Checklist
A checkable list of criteria that confirm the implementation matches the
design.

### Authoring Rules
1. Be maximally specific. Instead of "create the database schema," write
   "create migrations/001_create_users.sql with columns: id (UUID primary
   key), email (unique, not null), created_at (timestamp default now)."
2. Reference exact file paths from the codebase. Do not invent paths that do
   not match the project's conventions.
3. If the codebase reveals patterns (naming conventions, directory structure,
   testing framework), follow them exactly.
4. Do not include architectural discussion — the plan is purely operational:
   what to do, in what order, how to verify.
```

(Exact prose finalized at implementation time; the diff of detailer.md /
planning.md goldens is the audit signal.)

### Step 2 — Rewire `detailer.md` to include the fragment

**File:** `.aitask-scripts/brainstorm/templates/detailer.md`

Restructure the `## Output` section (currently lines ~20–95) and drop the now-
duplicated `## Rules` block (lines ~82–95):

- Keep the `<!-- include: _section_format.md -->` line and the
  `--- DETAILED_PLAN_START/END ---` delimiter explanation.
- Replace the four hand-written `<!-- section: … -->`-wrapped `### …` blocks
  with: a lead-in sentence + `<!-- include: _plan_contract.md -->`.
- Add a brainstorm-specific **"Section markers"** subsection that tells the
  agent to wrap each contract section in `<!-- section: <name> -->` markers:
  `prerequisites`, `step_by_step [dimensions: component_*]` (with nested
  `#### Steps for <Component>` sub-sections per `component_*` key),
  `testing`, `verification [dimensions: assumption_*]`. Fold the old Rule 3
  ("every assumption maps to a verification step") into the `verification`
  marker instruction. Keep the "If no Dimension Keys block is present, omit
  `[dimensions: …]`" sentence.
- Delete `## Rules` — rules 1, 2, 4, 5 now live in the fragment's "Authoring
  Rules"; rule 3 is folded into the verification marker instruction. Leave
  `## Section-Targeted Re-Detailing` and the `## Phase 1/2/3` body untouched.

Net: detailer's brainstorm machinery is preserved; only the duplicated
*content* contract is removed in favor of the include.

### Step 3 — Embed the fragment in `planning.md`

**File:** `.claude/skills/task-workflow/planning.md`

In §6.1, replace the thin "Detailed means…" bullet (lines ~254–257) so the
plan-authoring instruction reads as a lead-in followed by the include:

```
- Create a detailed, step-by-step implementation plan — not a high-level
  overview. The plan must satisfy the shared implementation-plan content
  contract:

{% include "_plan_contract.md" %}

- Include a reference to **Step 9 (Post-Implementation)** in the plan for the
  cleanup, archival, and merge steps
- Use `ExitPlanMode` when ready for user approval
```

The `{% include %}` tag sits at column 0 on its own line; the fragment's
`### …` headers render as sub-sections of `## 6.1: Planning`. This is the
first `{% include %}` used by any skill `.md` (verified: none exist today).

### Step 4 — Extend the minijinja renderer (the bridge + staleness)

**File:** `.aitask-scripts/lib/skill_template.py`

1. Add a repo-root finder and the brainstorm-templates include dir, with no
   change to `render_skill()`'s signature (so the legacy CLI path used by the
   golden tests keeps working):
   ```python
   def _find_repo_root(start: Path) -> Path | None:
       for p in [start, *start.parents]:
           if (p / ".aitask-scripts").is_dir():
               return p
       return None

   def _include_search_dirs(template_path: Path) -> list[Path]:
       dirs = [template_path.parent, template_path.parent.parent]
       root = _find_repo_root(template_path)
       if root is not None:
           bt = root / ".aitask-scripts" / "brainstorm" / "templates"
           if bt.is_dir():
               dirs.append(bt)
       return dirs
   ```
2. In `render_skill()`, build `load_from_path` from `_include_search_dirs(...)`
   instead of the hard-coded 2-dir list. Document the bridge in a comment.
3. **Staleness:** add `INCLUDE_RE = re.compile(r'\{%-?\s*include\s+["\']([^"\']+)["\']')`.
   In `walk_closure()`, after reading each source, scan its raw text for
   `{% include %}` directives, resolve each name against
   `_include_search_dirs(src)`, and collect existing hits into an
   `include_deps: set[Path]`. Change `_is_stale(plan, profile_yaml)` →
   `_is_stale(plan, profile_yaml, include_deps)` and fold the include-dep
   mtimes into `max_source_mtime`. This makes a `_plan_contract.md` edit
   correctly re-render planning.md on the next `aitask_skill_render.sh` run.

No change needed to `aitask_skill_render.sh` or `aitask_skill_verify.sh` —
both route through `render_skill()` / `walk_closure()`.

### Step 5 — Regenerate task-workflow goldens

**Files:** `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`

Regenerate per `aidocs/skill_authoring_conventions.md` ("Regenerate goldens"):
```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/planning.md \
    aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/procs/task-workflow/planning-$p.md
done
```
The intended diff is exactly the embedded contract block. Only `planning-*`
goldens change; `SKILL-*`, `manual-verification-followup-*`,
`satisfaction-feedback-*`, `remote-drift-check-*` are untouched.

### Step 6 — Extend tests

- **`tests/test_skill_render_task_workflow.sh`**
  - Test 1 picks up the regenerated `planning-*` goldens automatically.
  - Test 3: add an assertion that rendered `planning.md` contains a
    distinctive contract phrase (e.g. `Verification Checklist`) and a
    `assert_not_contains` that no literal `{% include` survives in the output
    (proves the include resolved).
  - Add a planning.md agent byte-identity check (the include resolves
    agent-agnostically — same shape as the existing Test 2 for SKILL.md).
- **`tests/test_crew_template_includes.sh`**
  - Add Test 8: copy the real `detailer.md` + `_section_format.md` +
    `_plan_contract.md` into a temp `templates/` dir, run
    `resolve_template_includes`, assert the contract content appears and no
    residual `<!-- include:` directive remains.

### Step 7 — Cross-agent port (requirement #5)

No manual port is required, and the plan will say so explicitly:

- `planning.md` lives only at the Claude source-of-truth path
  (`.claude/skills/task-workflow/planning.md`); the dep-walker renders it into
  all four agent trees (`.claude`, `.agents`, `.gemini`, `.opencode`)
  automatically. Those `*-/` per-profile trees are **git-ignored**
  (`git check-ignore` confirmed) and regenerate on demand.
- `detailer.md` and `_plan_contract.md` are agent-agnostic brainstorm
  templates — one copy, no per-agent variants.
- `skill_template.py` is agent-agnostic.

Verification of the port = rendering all four agents and confirming
byte-identical planning.md output (Step "Verification" below).

### Out of scope (called out, not changed)

- `aidocs/planning_conventions.md` — its rules are plan-*review* heuristics, a
  different concern from the content contract; its own "Future refactor note"
  already tracks its own promotion. Not edited.
- `_OPERATION_HELP["detail"]` in `brainstorm_app.py` — condensed UI help text;
  detailer still produces Prerequisites/Step-by-Step/Testing/Verification, so
  the summary stays accurate. Not edited. (Note: `brainstorm_app.py` /
  `brainstorm_session.py` already carry unrelated uncommitted edits — commits
  in Step 8 will be scoped to this task's files only.)

## Critical files

| File | Change |
|------|--------|
| `.aitask-scripts/brainstorm/templates/_plan_contract.md` | **new** — canonical fragment |
| `.aitask-scripts/brainstorm/templates/detailer.md` | include the fragment; drop duplicated `## Rules` + section bodies |
| `.claude/skills/task-workflow/planning.md` | `{% include "_plan_contract.md" %}` in §6.1 |
| `.aitask-scripts/lib/skill_template.py` | extend minijinja loader path; track `{% include %}` staleness |
| `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md` | regenerated |
| `tests/test_skill_render_task_workflow.sh` | new assertions |
| `tests/test_crew_template_includes.sh` | new Test 8 |

## Verification

1. **Render correctness**
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   "$PYTHON" .aitask-scripts/lib/skill_template.py \
     .claude/skills/task-workflow/planning.md \
     aitasks/metadata/profiles/fast.yaml claude | grep -A3 'Verification Checklist'
   ```
   Confirm the contract is embedded and no literal `{% include` remains.
2. **Cross-agent byte-identity** — render planning.md for `claude`, `codex`,
   `gemini`, `opencode`; outputs must be identical.
3. **Closure verify** — `./.aitask-scripts/aitask_skill_verify.sh` passes
   (its `walk-check` renders planning.md through the new loader path).
4. **Brainstorm include** — `resolve_template_includes` on the real
   `detailer.md` yields the contract content and no residual directive.
5. **Test suites**
   ```bash
   bash tests/test_skill_render_task_workflow.sh
   bash tests/test_crew_template_includes.sh
   bash tests/test_skill_render.sh
   bash tests/test_skill_render_uniform.sh
   bash tests/test_skill_verify.sh
   ```
6. **Staleness** — `touch` `_plan_contract.md`, run `aitask_skill_render.sh`
   for a consuming skill (e.g. `aitask-pick --profile fast --agent claude`),
   confirm the rendered `task-workflow-fast-/planning.md` is rewritten.
7. `shellcheck` the two edited test scripts.

## Post-Implementation

Follow **Step 9** of the task-workflow: review (Step 8), commit code +
plan separately, archive t818, push.

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

| Pipeline | Renderer | Include syntax | Base dir(s) |
|----------|----------|----------------|-------------|
| detailer.md | `resolve_template_includes()` (bash, in `agentcrew_utils.sh`) | `<!-- include: X -->` | single base dir (today) — `.aitask-scripts/brainstorm/templates/` |
| planning.md | minijinja via `skill_template.py` dep-walker | `{% include "X" %}` | minijinja `load_from_path` = `[<skill dir>, <skills root>]` |

The canonical fragment lives at a **neutral, shared-includes location**:
`.aitask-scripts/skill_templates/_plan_contract.md`. Parking it under
`brainstorm/templates/` would mis-signal ownership — the fragment is shared
between brainstorm (`detailer.md`) and a skill (`planning.md`), neither of
which is privileged. A dedicated `skill_templates/` dir also makes the
"includes only, never rendered standalone" intent explicit.

**Chosen bridge: teach both resolvers about the neutral dir.**

1. **Bash side:** extend `resolve_template_includes()` to accept multiple
   base dirs and search them in order. Callers pass their primary dir (e.g.
   the work2do dir for crew agents) plus a fallback to
   `.aitask-scripts/skill_templates/`. This lets `detailer.md` keep
   `<!-- include: _section_format.md -->` (brainstorm-local) AND add
   `<!-- include: _plan_contract.md -->` (resolved against the neutral dir).
   `_section_format.md` stays where it is — it is brainstorm-specific.
2. **minijinja side:** `render_skill()` in `skill_template.py` adds
   `<repo>/.aitask-scripts/skill_templates/` to its `load_from_path` list.
   planning.md uses `{% include "_plan_contract.md" %}` and minijinja resolves
   it to the same canonical file the bash resolver uses.

This keeps a true single source of truth — no symlink, no copy, no second
drift surface. Rejected: a symlink in the skills tree is portability-fragile
and confuses the dep-walker's tree scan; pre-resolving `<!-- include -->` in
Python would re-implement the bash resolver — ironic for a de-dup task.
Rejected (earlier draft): keeping the fragment under `brainstorm/templates/`
— rejected because the fragment is not brainstorm-owned.

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

**New file:** `.aitask-scripts/skill_templates/_plan_contract.md`
**New dir:** `.aitask-scripts/skill_templates/` (dedicated to includes-only,
shared between bash crew templates and minijinja skill templates).

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

### Step 4a — Extend the bash resolver (`resolve_template_includes`)

**File:** `.aitask-scripts/lib/agentcrew_utils.sh`

Today the resolver takes a single `base_dir`. Extend it to accept multiple
base dirs and search them in order; the first hit wins. This lets the
brainstorm detailer keep `_section_format.md` next to it (resolved against
the brainstorm templates dir) AND add `_plan_contract.md` (resolved against
the neutral `skill_templates/` dir).

```bash
# resolve_template_includes <base_dir> [base_dir2 ...]
# Reads template content from stdin, writes resolved content to stdout.
# Resolves <!-- include: filename --> directives by searching each base_dir
# in order. The first existing match wins. One-level only. Missing includes
# emit a warning and preserve the directive line as-is.
resolve_template_includes() {
    local base_dirs=("$@")
    [[ ${#base_dirs[@]} -eq 0 ]] && die "resolve_template_includes: requires at least one base_dir"
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ \<\!--[[:space:]]+include:[[:space:]]+([^[:space:]]+)[[:space:]]+--\> ]]; then
            local inc_name="${BASH_REMATCH[1]}"
            local found=""
            for d in "${base_dirs[@]}"; do
                if [[ -f "$d/$inc_name" ]]; then
                    found="$d/$inc_name"
                    break
                fi
            done
            if [[ -n "$found" ]]; then
                cat "$found"
            else
                warn "Template include not found in any base_dir: $inc_name"
                printf '%s\n' "$line"
            fi
        else
            printf '%s\n' "$line"
        fi
    done
}
```

Update the lone production caller in `aitask_crew_addwork.sh`:

```bash
# Before:
WORK2DO_CONTENT="$(printf '%s\n' "$WORK2DO_CONTENT" | resolve_template_includes "$WORK2DO_DIR")"
# After:
SKILL_TEMPLATES_DIR="$(cd "$AIT_REPO_ROOT/.aitask-scripts/skill_templates" 2>/dev/null && pwd || true)"
if [[ -n "$SKILL_TEMPLATES_DIR" ]]; then
    WORK2DO_CONTENT="$(printf '%s\n' "$WORK2DO_CONTENT" | resolve_template_includes "$WORK2DO_DIR" "$SKILL_TEMPLATES_DIR")"
else
    WORK2DO_CONTENT="$(printf '%s\n' "$WORK2DO_CONTENT" | resolve_template_includes "$WORK2DO_DIR")"
fi
```

(`AIT_REPO_ROOT` already resolved by `ait` dispatcher; verify the exact var
name at implementation time and fall back to a repo-root finder helper if
needed.)

### Step 4b — Extend the minijinja renderer (the bridge + staleness)

**File:** `.aitask-scripts/lib/skill_template.py`

1. Add a repo-root finder and the shared-includes dir, with no change to
   `render_skill()`'s signature (so the legacy CLI path used by the golden
   tests keeps working):
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
           st = root / ".aitask-scripts" / "skill_templates"
           if st.is_dir():
               dirs.append(st)
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
  - Update the existing tests' invocations to the new variadic signature
    (one base dir still works — backward-compatible).
  - Add Test 8: multi-base-dir resolution. Place an include target in a
    secondary base dir and confirm the resolver finds it after the primary
    dir misses. Use the real `detailer.md` + `_section_format.md` (primary
    dir) + `_plan_contract.md` (secondary dir), run
    `resolve_template_includes <primary> <secondary>`, assert both
    `_section_format.md` and the contract content appear and no residual
    `<!-- include:` directive remains.

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
| `.aitask-scripts/skill_templates/_plan_contract.md` | **new** — canonical fragment (new dir) |
| `.aitask-scripts/brainstorm/templates/detailer.md` | include the fragment (resolved against new neutral dir); drop duplicated `## Rules` + section bodies |
| `.claude/skills/task-workflow/planning.md` | `{% include "_plan_contract.md" %}` in §6.1 |
| `.aitask-scripts/lib/agentcrew_utils.sh` | `resolve_template_includes()` accepts multiple base dirs |
| `.aitask-scripts/aitask_crew_addwork.sh` | pass `skill_templates/` as fallback base dir |
| `.aitask-scripts/lib/skill_template.py` | extend minijinja loader path with `skill_templates/`; track `{% include %}` staleness |
| `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md` | regenerated |
| `tests/test_skill_render_task_workflow.sh` | new assertions |
| `tests/test_crew_template_includes.sh` | new Test 8 for multi-base-dir resolution |

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
   `detailer.md` (with both `brainstorm/templates/` and `skill_templates/`
   as base dirs) yields both `_section_format.md` content and the contract
   content, with no residual directive.
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

## Post-Review Changes

### Change Request 1 (2026-05-25 — first user review)

- **Requested by user:**
  1. planning.md must not pull in the detailer's contract verbatim — the two
     specs are similar but **not equal**. planning.md's included fragment
     must match the *current* planning.md spec verbatim.
  2. detailer.md was structurally rewritten by the refactor: the
     `<!-- section: ... -->` markers (parsed by `ait brainstorm` to identify
     sections and dimensions) moved from inline section bodies into a
     separated "Section markers" subsection. **detailer.md must remain
     byte-identical to its pre-task state.**
  3. The architectural mistake was unifying the contract across two
     pipelines that have different structures (detailer: two-level
     proposal + plan; planning.md: single-level plan). Keep them separate.
- **Changes made:**
  1. Reverted detailer.md to its committed (pre-task) content (verified
     `git diff` empty for that file).
  2. Deleted `.aitask-scripts/skill_templates/_plan_contract.md` (the
     unified fragment) and replaced it with
     `.aitask-scripts/skill_templates/_planning_plan_contract.md`, whose
     body is the current planning.md "Detailed" spec **verbatim** (same
     four-line bullet, same indentation). Switched the include directive
     to `{%- include "_planning_plan_contract.md" -%}` (whitespace strip)
     so the rendered planning.md is byte-identical to its committed
     pre-task version (verified `git diff` empty for all three
     `tests/golden/procs/task-workflow/planning-*.md`).
  3. `test_skill_render_task_workflow.sh` Test 2c: replaced the
     contract-Verification-Checklist assertions with positive checks for
     the planning-specific phrasing AND **negative** checks that ensure
     detailer-specific headings (`Verification Checklist`, `### Authoring
     Rules`) do NOT leak into planning.md — this regresses if anyone
     re-unifies the two contracts.
  4. `test_crew_template_includes.sh` Test 8: rewrote in terms of
     synthetic fragments (`_primary_only.md`, `_fallback_only.md`) so it
     still exercises multi-base-dir resolution + first-hit-wins + missing-
     in-all-dirs semantics without depending on a (now non-existent)
     shared brainstorm-side include. Removed Test 9 entirely (its
     real-file dependency on detailer.md importing `_plan_contract.md` no
     longer holds).
- **Preserved (per user's "preserve this refactoring"):**
  - `.aitask-scripts/skill_templates/` directory as a neutral home for
    skill-side template fragments.
  - `resolve_template_includes()` multi-base-dir capability (general infra
    even though brainstorm uses single-dir today).
  - `aitask_crew_addwork.sh` passes `skill_templates/` as fallback base
    dir — harmless when the include is brainstorm-local, useful if a
    future brainstorm template wants to consume a shared fragment.
  - `skill_template.py`: `_find_repo_root`, `_include_search_dirs`,
    `INCLUDE_RE`, `_resolve_include_deps`, and the include-deps fold into
    `_is_stale` — minijinja `{% include %}` is now first-class with
    correct staleness propagation.
- **Files affected:**
  - `.aitask-scripts/brainstorm/templates/detailer.md` (reverted)
  - `.aitask-scripts/skill_templates/_plan_contract.md` (deleted)
  - `.aitask-scripts/skill_templates/_planning_plan_contract.md` (new)
  - `.claude/skills/task-workflow/planning.md` (include line + whitespace
    strip)
  - `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`
    (re-regenerated — now byte-identical to pre-task committed state)
  - `tests/test_skill_render_task_workflow.sh` (Test 2c rewritten +
    negative anti-leak assertions)
  - `tests/test_crew_template_includes.sh` (Test 8 rewritten with
    synthetic fragments, Test 9 removed)

### Change Request 2 (2026-05-25 — second user review)

- **Requested by user:** "Since jinja templating is not used in practice in
  any of brainstorm ops, how can we document that it is supported? Can
  you introduce a short fragment (the main planning instructions) from
  the detailer, without messing up with sections and dimensions comments,
  so that we have templating active and tested in unit tests?"
- **Reading:** Change Request 1 reverted detailer.md, which left the new
  `.aitask-scripts/skill_templates/` neutral dir with no brainstorm-side
  consumer — the bridge infrastructure existed but was never crossed in
  production. User wants the bridge actually exercised (not just
  capability-tested in synthetic fixtures).
- **Changes made:**
  1. Extracted detailer.md's `## Rules` body (5 numbered authoring rules,
     lines 84–95 of the pre-task file) into
     `.aitask-scripts/skill_templates/_detailer_rules.md` — verbatim.
     Chose `## Rules` because it lives **outside** all
     `<!-- section: ... -->` markers (no risk to brainstorm's section/
     dimensions parsing) and is the closest thing detailer.md has to
     general "planning instructions".
  2. Replaced the extracted body in detailer.md with a single line
     `<!-- include: _detailer_rules.md -->`. After bash resolution
     through `(brainstorm/templates/, skill_templates/)`, detailer.md
     reads byte-identically to its pre-task content — verified by
     resolving and diffing against `git show HEAD:detailer.md` (the only
     residual diff is the pre-existing `_section_format.md` include,
     which also expanded — that's identical behavior to pre-task).
  3. Added Test 9 in `test_crew_template_includes.sh` covering the
     **production** bridge: runs the resolver on the real `detailer.md`
     with both real dirs and asserts (a) rule prose appears, (b) the
     include directive is gone, (c) brainstorm's section markers
     (`prerequisites`, `step_by_step`, `verification`) are still in
     their original positions with their `dimensions:` attributes
     intact, (d) **without** the `skill_templates/` fallback the
     resolver warns about the missing include — proving the fragment
     genuinely lives in the neutral dir and is not silently shadowed by
     a stray copy under `brainstorm/templates/`.
  4. Added `.aitask-scripts/skill_templates/README.md` documenting the
     dir's role: production consumers (planning.md and detailer.md), the
     two renderer pipelines that search it (minijinja loader + bash
     resolver), staleness behavior, and which test files exercise each
     side.
- **Files affected:**
  - `.aitask-scripts/brainstorm/templates/detailer.md` (Rules body
    replaced by `<!-- include: _detailer_rules.md -->`; section markers
    untouched)
  - `.aitask-scripts/skill_templates/_detailer_rules.md` (new — verbatim
    Rules content)
  - `.aitask-scripts/skill_templates/README.md` (new — bridge
    documentation)
  - `tests/test_crew_template_includes.sh` (new Test 9 covering the
    production bridge + missing-fallback warning path)

## Final Implementation Notes

- **Actual work done:** Extended the framework's template-include
  infrastructure so minijinja-rendered skill templates and bash-resolved
  brainstorm templates share a common neutral fragments dir
  (`.aitask-scripts/skill_templates/`). Both pipelines now actively cross
  the bridge in production: `task-workflow/planning.md` includes
  `_planning_plan_contract.md` (minijinja side), and
  `brainstorm/templates/detailer.md` includes `_detailer_rules.md` (bash
  side). The two fragments contain pipeline-specific content — the dir
  shares infrastructure, not content. README at
  `.aitask-scripts/skill_templates/README.md` documents the bridge.
- **Deviations from plan:** The original plan unified the contract across
  detailer.md and planning.md. User review (Change Request 1) rejected the
  unification because the two pipelines have fundamentally different
  structures (two-level proposal+plan vs single-level plan) and because
  the detailer's `<!-- section: ... -->` markers are parsed by
  `ait brainstorm` and must stay in their original positions. Final state
  keeps the infrastructure but uses **separate** per-pipeline contracts.
  User review (Change Request 2) then asked that the bridge actually be
  exercised on the brainstorm side (not only on the skill side), so a
  short safe fragment (the 5 `## Rules` authoring rules — outside all
  section markers) was extracted from detailer.md into the shared dir.
  Final detailer.md is byte-identical post-resolution to its pre-task
  content (verified).
- **Issues encountered:**
  - Initial fragment HTML comment contained literal `{% include %}` syntax
    which tripped the minijinja parser inside planning.md's render — fixed
    by rephrasing the comment to avoid the literal Jinja tag syntax (later
    moot when the fragment was replaced).
  - `{% include "..." %}` without whitespace-control inserted leading and
    trailing blank lines in the rendered output, breaking byte-identity
    with the pre-task planning.md golden. Switched to `{%- ... -%}` (strip
    both sides). The Jinja-only comment `{# ... #}` inside the fragment is
    invisible to minijinja's renderer, preserving verbatim output.
  - `walk_closure()` needed to read each source file's RAW text (pre-render)
    to capture `{% include %}` directives even when conditionals would
    suppress execution — added a separate `src.read_text()` call before
    `render_skill()` for include-dep scanning. Without this, profile-gated
    include sites would silently bypass staleness tracking.
- **Key decisions:**
  - Multi-base-dir resolver design (variadic args, first-hit-wins) chosen
    over keyword args or a separate "shared" arg to keep the interface
    minimal and backward-compatible (callers passing a single dir still
    work — tests 1–7 unchanged).
  - `_resolve_include_deps()` collects deps across the entire closure walk
    (set union), folded once into `_is_stale()` — avoids re-resolving
    includes on every staleness check and correctly handles the case where
    multiple sources include the same fragment.
  - `aitask_crew_addwork.sh`'s skill_templates fallback now has a
    production consumer (`detailer.md` → `_detailer_rules.md`); the
    fallback search is no longer hypothetical.
  - Chose `## Rules` for the brainstorm-side extraction because it is the
    largest detailer.md region that lives **outside** all
    `<!-- section: ... -->` markers — a fragment containing or
    surrounding a marker would change the marker's textual position in
    the rendered file, which `ait brainstorm`'s section parser would
    see. Test 9 pins this by asserting all three section markers
    (`prerequisites`, `step_by_step`, `verification`) and their
    `dimensions:` attributes still appear in the post-resolution output.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** N/A (parent task, no children).
